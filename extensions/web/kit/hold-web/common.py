"""HOLD 웹 확장 web-0.1 공통 모듈 — 설정 검증, 셸 명령 해석, 보호 경로, 고정 버전 생성물, 레거시 검사.

설치 위치: <프로젝트>/.claude/hold-web/common.py (보호 경로). 코어 키트 파일은 import 하지 않습니다.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    tomllib = None  # type: ignore[assignment]

EXT_VERSION = "0.1"
PKG = "modern-web-guidance"
ALLOWED_SUBCOMMANDS = {"search", "retrieve", "list", "legacy-scan"}
VALUE_OPTIONS = {"--skill-version", "--agent", "--format", "--limit", "--category"}
SCAN_TIMEOUT = 100          # 초. 훅 timeout(120초)보다 짧게
HOOK_TIMEOUT_MIN = 120

# 생성물 (sync 가 쓰고, web_check 가 대조)
SKILL_PATH = ".claude/skills/modern-web-guidance/SKILL.md"
LICENSE_PATH = ".claude/skills/modern-web-guidance/LICENSE"
GUIDES_PATH = "docs/hold/web/guides.json"
LOCK_PATH = "docs/hold/web/lock.json"
MWGRC_PATH = ".mwgrc"
USAGE_PATH = "docs/architecture/usage-environments.md"
SNAP_DIR = ".hold/logs/web_snap"
HOOK_LOG = ".hold/logs/hooks.jsonl"

# 확장이 스스로 지키는 경로 (코어 보호 목록과 별개 — 코어 파일을 고치지 않기 위해)
PROTECTED_PREFIXES = (
    "docs/hold/web/",
    ".hold/logs/",
    ".claude/hold-web/",
    ".claude/skills/modern-web-guidance/",
    ".claude/hooks/web_guard.py",
    USAGE_PATH,
)
PROTECTED_BASENAMES = (".mwgrc",)   # 위치와 상관없이 (MWG 는 상위 폴더·홈의 .mwgrc 도 읽는다)
HUMAN_ONLY_SCRIPTS = (".claude/hold-web/sync.py", "extensions/web/install.py", "hold-web/sync.py")
READONLY_ALLOWED_SCRIPTS = ("hold-web/web_check.py", "hold-web/web_scan.py")
READONLY_COMMANDS = {"cat", "less", "more", "head", "tail", "grep", "egrep", "fgrep", "rg", "ls", "wc",
                     "diff", "stat", "file", "md5sum", "sha256sum", "sha1sum", "type", "realpath"}
READONLY_GIT = {"diff", "log", "show", "status", "blame", "ls-files"}
WRAPPERS = {"env", "command", "exec", "time", "nohup", "sudo", "nice", "builtin", "xargs", "timeout", "stdbuf"}
WRAPPER_VALUE_OPTS = {"-u", "--unset", "-C", "--chdir", "-I", "-i", "-n", "-L", "-d", "-P", "-s", "-E", "-k", "--signal"}
# 패키지 이름이 나와도 실행으로 보지 않는 명령 (fail-closed 예외)
MENTION_OK = READONLY_COMMANDS | {"echo", "printf", "cd", "pushd", "popd", "test", "[", "git", "true"}
SHELLS = {"bash", "sh", "zsh", "dash"}

DEFAULTS: dict = {
    "enabled": False,
    "ext_version": EXT_VERSION,
    "since": "",
    "mwg_version": "1.0.0",
    "mwg_integrity": "",
    "baseline": "widely",
    "fallback_policy": "",
    "telemetry": False,
    "allow_origin_trials": False,
    "allow_volatile_features": False,
    "legacy_scan": "auto",
    "legacy_allow": [],
    "frontend_suffixes": [".html", ".htm", ".css", ".js", ".mjs", ".cjs", ".jsx", ".ts", ".mts", ".cts", ".tsx", ".vue", ".svelte"],
    "template_suffixes": [".jinja", ".jinja2", ".j2", ".njk"],
    "skip_dirs": ["node_modules", "dist", "build", ".next", ".nuxt", "vendor", ".venv", ".git", ".hold"],
}
TYPES = {k: type(v) for k, v in DEFAULTS.items()}


# ── 설정 ──────────────────────────────────────────────────────────────

def project_root() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()).resolve()


def load_toml(root: Path) -> dict:
    f = root / "hold.toml"
    if tomllib is None or not f.exists():
        return {}
    with f.open("rb") as fh:
        return tomllib.load(fh)


def web_config(cfg: dict) -> tuple[dict, list[str]]:
    """[web] 을 기본값과 합치고 형을 검사한다. (설정, 오류 목록)."""
    raw = cfg.get("web") or {}
    errors: list[str] = []
    out = dict(DEFAULTS)
    for k, v in raw.items():
        if k not in TYPES:
            errors.append(f"[web].{k} 는 알 수 없는 키입니다")
            continue
        want = TYPES[k]
        if not isinstance(v, want) or (want is int and isinstance(v, bool)):
            errors.append(f"[web].{k} 는 {want.__name__} 이어야 합니다 (지금: {type(v).__name__} {v!r})")
            continue
        if want is list and not all(isinstance(x, str) for x in v):
            errors.append(f"[web].{k} 는 문자열 목록이어야 합니다")
            continue
        out[k] = v
    if not re.fullmatch(r"\d+\.\d+\.\d+", out["mwg_version"]):
        errors.append(f"[web].mwg_version 은 1.2.3 형식의 정확한 버전이어야 합니다 (지금: {out['mwg_version']!r})")
    if out["mwg_integrity"] and not re.fullmatch(r"sha512-[A-Za-z0-9+/]+=*", out["mwg_integrity"]):
        errors.append("[web].mwg_integrity 는 npm 의 'sha512-…' 값이어야 합니다")
    if out["baseline"] not in ("widely", "newly", "limited") and not re.fullmatch(r"\d{4}", out["baseline"]):
        errors.append(f"[web].baseline 은 widely, newly, limited, 또는 4자리 연도입니다 (지금: {out['baseline']!r})")
    if out["legacy_scan"] not in ("off", "log", "block", "auto"):
        errors.append(f"[web].legacy_scan 은 off, log, block, auto 중 하나입니다 (지금: {out['legacy_scan']!r})")
    if out["since"] and not re.fullmatch(r"\d{8}", out["since"]):
        errors.append("[web].since 는 YYYYMMDD 입니다")
    return out, errors


def profile_of(cfg: dict) -> str:
    return str((cfg.get("hold") or {}).get("profile") or "lite").lower()


def scan_mode(w: dict, profile: str) -> str:
    if not w["enabled"]:
        return "off"
    if w["legacy_scan"] == "auto":
        return "log" if profile == "lite" else "block"
    return w["legacy_scan"]


def log(root: Path, record: dict) -> None:
    try:
        import datetime as _dt
        f = root / HOOK_LOG
        f.parent.mkdir(parents=True, exist_ok=True)
        record = {"ts": _dt.datetime.now().isoformat(timespec="seconds"), "ext": f"web-{EXT_VERSION}", **record}
        with f.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass


# ── 경로 ──────────────────────────────────────────────────────────────

def rel_posix(root: Path, raw: str) -> str | None:
    """프로젝트 루트 기준 posix 경로. 루트 밖이면 None."""
    p = Path(raw)
    p = (p if p.is_absolute() else root / p)
    try:
        p = p.resolve()
    except OSError:
        p = Path(os.path.abspath(p))
    try:
        return p.relative_to(root).as_posix()
    except ValueError:
        return None


def is_protected_path(root: Path, raw: str) -> bool:
    name = raw.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
    if name in PROTECTED_BASENAMES:
        return True
    rel = rel_posix(root, raw)
    if rel is None:
        return False
    return any(rel == p.rstrip("/") or rel.startswith(p) for p in PROTECTED_PREFIXES)


def token_mentions_protected(tok: str) -> bool:
    t = tok.replace("\\", "/")
    if any(b in t for b in PROTECTED_BASENAMES):
        return True
    return any(p.rstrip("/") in t for p in PROTECTED_PREFIXES)


def glob_match(path: str, pattern: str) -> bool:
    """'*' 는 '/' 를 넘지 않고, '**' 는 넘는다."""
    rx = ""
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            rx += "(?:.*/)?"
            i += 3
        elif pattern.startswith("**", i):
            rx += ".*"
            i += 2
        elif pattern[i] == "*":
            rx += "[^/]*"
            i += 1
        elif pattern[i] == "?":
            rx += "[^/]"
            i += 1
        else:
            rx += re.escape(pattern[i])
            i += 1
    return re.fullmatch(rx, path) is not None


def is_frontend(rel: str, w: dict) -> bool:
    p = PurePosixPath(rel)
    if set(w["skip_dirs"]).intersection(p.parts[:-1]):
        return False
    suf = p.suffix.lower()
    return suf in {s.lower() for s in w["frontend_suffixes"]} or suf in {s.lower() for s in w["template_suffixes"]}


def frontend_snapshot(root: Path, w: dict) -> dict[str, list[int]]:
    snap: dict[str, list[int]] = {}
    skip = set(w["skip_dirs"])
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip]
        for fn in filenames:
            full = Path(dirpath) / fn
            rel = full.relative_to(root).as_posix()
            if is_frontend(rel, w):
                try:
                    st = full.stat()
                    snap[rel] = [st.st_mtime_ns, st.st_size]
                except OSError:
                    pass
    return snap


# ── 셸 명령 해석 ──────────────────────────────────────────────────────

@dataclass
class SimpleCmd:
    argv: list[str]
    assigns: dict[str, str] = field(default_factory=dict)
    redirects: list[str] = field(default_factory=list)


class ParseError(Exception):
    pass


def split_commands(cmd: str, depth: int = 0) -> list[SimpleCmd]:
    """셸 명령을 단순 명령 목록으로. 따옴표·연산자·리다이렉트·bash -c·npx -c 를 다룬다."""
    if depth > 4:
        raise ParseError("중첩이 너무 깊습니다")
    text = cmd.replace("\\\r\n", " ").replace("\\\n", " ").replace("`", " ; ").replace("\r\n", "\n").replace("\n", " ; ")
    lex = shlex.shlex(text, posix=True, punctuation_chars=";&|()<>")
    lex.whitespace_split = True
    try:
        tokens = list(lex)
    except ValueError as e:
        raise ParseError(str(e)) from e
    out: list[SimpleCmd] = []
    cur: list[str] = []
    redirects: list[str] = []
    expect_redirect = False
    for tok in tokens:
        if tok and set(tok) <= set(";&|()"):
            if cur or redirects:
                out.extend(_finish(cur, redirects, depth))
            cur, redirects, expect_redirect = [], [], False
            continue
        if tok and set(tok) <= set("<>&") and (">" in tok or "<" in tok):
            expect_redirect = ">" in tok
            continue
        if expect_redirect:
            redirects.append(tok)
            expect_redirect = False
            continue
        if tok == "$":          # "$(" 의 앞부분 — 괄호 안은 별도 명령으로 나뉜다
            continue
        cur.append(tok)
    if cur or redirects:
        out.extend(_finish(cur, redirects, depth))
    return out


def _finish(tokens: list[str], redirects: list[str], depth: int) -> list[SimpleCmd]:
    assigns: dict[str, str] = {}
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", t):
            k, _, v = t.partition("=")
            assigns[k] = v
            i += 1
            continue
        base = t.rsplit("/", 1)[-1]
        if base in WRAPPERS:
            i += 1
            if base == "timeout" and i < len(tokens) and not tokens[i].startswith("-"):
                i += 1  # timeout 의 시간 인자
            while i < len(tokens) and tokens[i].startswith("-"):
                if tokens[i] in ("-S", "--split-string") and i + 1 < len(tokens):
                    return [SimpleCmd([], assigns, redirects)] + split_commands(tokens[i + 1], depth + 1)
                if tokens[i] in WRAPPER_VALUE_OPTS:
                    i += 1
                i += 1
            continue
        break
    argv = tokens[i:]
    result = [SimpleCmd(argv, assigns, redirects)]
    # 따옴표 안의 명령 치환 "$(…)" 과 `…` (앞에서 ' ; ' 로 바뀐 것)
    for t in tokens:
        for m in re.finditer(r"\$\((.*)\)", t, re.S):
            result += split_commands(m.group(1), depth + 1)
        if " ; " in t:
            result += split_commands(t, depth + 1)
    if argv and argv[0].rsplit("/", 1)[-1] in SHELLS:
        for j, a in enumerate(argv[1:], 1):
            if a == "-c" or (a.startswith("-") and "c" in a[1:] and not a.startswith("--")):
                if j + 1 < len(argv):
                    result += split_commands(argv[j + 1], depth + 1)
                break
    if argv and argv[0] == "eval":
        result += split_commands(" ".join(argv[1:]), depth + 1)
    return result


@dataclass
class MwgCall:
    version: str | None      # None = 생략
    sub: str | None          # 첫 위치 인자 (하위 명령)
    args: list[str]          # 하위 명령 뒤 인자
    telemetry_off: bool
    direct: bool = False     # 패키지 실행기 없이 바이너리·파일을 직접 실행
    install: bool = False    # npm install 등


def _pkg_spec(tok: str) -> tuple[bool, str | None]:
    """'modern-web-guidance@1.0.0' → (True, '1.0.0'). 패키지가 아니면 (False, None)."""
    t = tok.strip()
    if t == PKG:
        return True, None
    if t.startswith(PKG + "@"):
        return True, t[len(PKG) + 1:]
    return False, None


def _sub_and_args(rest: list[str]) -> tuple[str | None, list[str]]:
    i = 0
    while i < len(rest):
        a = rest[i]
        if a == "--":
            return (rest[i + 1], rest[i + 2:]) if i + 1 < len(rest) else (None, [])
        if a.startswith("-"):
            if "=" not in a and a in VALUE_OPTIONS:
                i += 1
            i += 1
            continue
        return a, rest[i + 1:]
    return None, []


def find_mwg_calls(cmd: str, hook_env_telemetry_off: bool) -> list[MwgCall]:
    calls: list[MwgCall] = []
    for sc in split_commands(cmd):
        if not sc.argv:
            continue
        before = len(calls)
        _calls_for(sc, hook_env_telemetry_off, calls)
        # fail-closed: 실행 명령에 패키지 이름이 있는데 정상 호출로 해석되지 않았다
        if len(calls) == before and sc.argv[0].rsplit("/", 1)[-1] not in MENTION_OK \
                and any(PKG in t for t in sc.argv):
            calls.append(MwgCall(None, None, sc.argv, False, direct=True))
    return calls


def _calls_for(sc: SimpleCmd, hook_env_telemetry_off: bool, calls: list[MwgCall]) -> None:
    for _ in (0,):
        tel = sc.assigns.get("DISABLE_TELEMETRY") == "1" or hook_env_telemetry_off
        exe = sc.argv[0].rsplit("/", 1)[-1]
        args = sc.argv[1:]
        # 바이너리·CLI 파일 직접 실행
        if exe == PKG or any("modern-web.mjs" in a for a in sc.argv[:3]):
            calls.append(MwgCall(None, None, args, tel, direct=True))
            continue
        runner_args: list[str] | None = None
        if exe in ("npx", "pnpx", "bunx"):
            runner_args = args
        elif exe in ("npm", "pnpm", "yarn", "bun") and args:
            if args[0] in ("exec", "x", "dlx"):
                runner_args = args[1:]
            elif args[0] in ("i", "install", "add", "ci", "update", "up", "upgrade", "link") and any(_pkg_spec(a)[0] for a in args[1:]):
                calls.append(MwgCall(None, None, args, tel, install=True))
                continue
        if runner_args is None:
            continue
        pkg_version: str | None = None
        found = False
        i = 0
        while i < len(runner_args):
            a = runner_args[i]
            if a in ("-c", "--call") and i + 1 < len(runner_args):
                for inner in find_mwg_calls(runner_args[i + 1], tel):
                    calls.append(inner)
                i += 2
                continue
            if a.startswith("--package=") or a in ("-p", "--package"):
                val = a.split("=", 1)[1] if "=" in a else (runner_args[i + 1] if i + 1 < len(runner_args) else "")
                ok, ver = _pkg_spec(val)
                if ok:
                    found, pkg_version = True, ver
                i += 1 if "=" in a else 2
                continue
            if a == "--":
                i += 1
                continue
            if a.startswith("-"):
                i += 1
                continue
            ok, ver = _pkg_spec(a)
            if ok:
                found, pkg_version = True, ver
                sub, rest = _sub_and_args(runner_args[i + 1:])
                calls.append(MwgCall(pkg_version, sub, rest, tel))
            elif found and a == PKG:  # --package=… 뒤 bin 이름
                sub, rest = _sub_and_args(runner_args[i + 1:])
                calls.append(MwgCall(pkg_version, sub, rest, tel))
            elif found:
                calls.append(MwgCall(pkg_version, None, runner_args[i:], tel, direct=True))
            break


def check_mwg_calls(cmd: str, w: dict) -> str | None:
    """에이전트의 Bash 명령 중 MWG 호출을 검사. 막을 이유가 있으면 메시지를 돌려준다 (R17·텔레메트리)."""
    pinned = w["mwg_version"]
    env_off = os.environ.get("DISABLE_TELEMETRY") == "1"
    try:
        calls = find_mwg_calls(cmd, env_off)
    except ParseError:
        if PKG in cmd:
            return "명령을 해석할 수 없어 Modern Web Guidance 호출을 확인하지 못했습니다 (R17). 따옴표를 닫고 단순한 형태로 다시 실행하세요."
        return None
    good = f"DISABLE_TELEMETRY=1 npx -y {PKG}@{pinned} <search|retrieve|list> …"
    for c in calls:
        if c.install:
            return f"{PKG} 를 설치하는 명령은 사람이 실행합니다 (R17). 이 프로젝트는 npx 고정 버전으로만 씁니다: {good}"
        if c.direct:
            return f"{PKG} 를 직접 실행할 수 없습니다 (R17). 고정 버전으로 실행하세요: {good}"
        if c.version != pinned:
            got = f"@{c.version}" if c.version else "버전 생략"
            return f"{PKG} 는 hold.toml [web].mwg_version = {pinned} 으로 고정되어 있습니다 ({got}, R17). {good}"
        if c.sub not in ALLOWED_SUBCOMMANDS:
            what = f"'{c.sub}'" if c.sub else "하위 명령 없음"
            return (f"{PKG} 에서 에이전트가 쓸 수 있는 하위 명령은 search, retrieve, list, legacy-scan 뿐입니다 ({what}, R17). "
                    "정책·설정·버전을 바꾸는 명령(set-baseline, set-allow-*, install, update 등)은 사람이 hold.toml 과 sync.py 로 합니다.")
        if not w["telemetry"] and not c.telemetry_off:
            return f"텔레메트리를 끈 프로젝트입니다. 명령 앞에 DISABLE_TELEMETRY=1 을 붙이세요: {good}"
    return None


def check_bash_protected(cmd: str, root: Path) -> str | None:
    """확장 보호 경로를 건드리는 Bash 명령인지. 읽기 전용 명령과 검사 스크립트만 허용한다."""
    try:
        cmds = split_commands(cmd)
    except ParseError:
        if any(token_mentions_protected(t) for t in [cmd]):
            return "명령을 해석할 수 없는데 웹 확장 보호 경로가 들어 있습니다."
        return None
    for sc in cmds:
        tokens = sc.argv + list(sc.assigns.values())
        for t in sc.argv:
            if any(t.replace("\\", "/").endswith(s) for s in HUMAN_ONLY_SCRIPTS):
                return f"{t} 는 사람이 실행하는 스크립트입니다 (R17). 버전·정책을 바꿔야 한다고 판단되면 멈추고 보고하세요."
        if any(token_mentions_protected(r) for r in sc.redirects):
            return "웹 확장 보호 경로에 리다이렉트로 쓸 수 없습니다."
        refs = [t for t in tokens if token_mentions_protected(t)]
        if not refs or not sc.argv:
            continue
        exe = sc.argv[0].rsplit("/", 1)[-1]
        if exe in READONLY_COMMANDS and not any(a in ("-i", "--in-place") for a in sc.argv[1:]):
            continue
        if exe == "git" and len(sc.argv) > 1 and sc.argv[1] in READONLY_GIT:
            continue
        if exe.startswith("python") and len(sc.argv) > 1 and any(sc.argv[1].replace("\\", "/").endswith(s) for s in READONLY_ALLOWED_SCRIPTS):
            if all(not token_mentions_protected(t) or t == sc.argv[1] for t in tokens):
                continue
        return f"웹 확장 보호 경로({refs[0]})를 건드리는 명령입니다. 읽기는 cat·grep 등으로만 하세요."
    return None


# ── 고정 버전 생성물 (sync 와 web_check 가 같은 함수를 씀) ─────────────

MEMBERS = {
    "package": "package/package.json",
    "skill": "package/skills/modern-web-guidance/SKILL.md",
    "skill_version": "package/skills/modern-web-guidance/skill-version.txt",
    "guides": "package/skills/modern-web-guidance/gen/guides.json",
    "license": "package/LICENSE",
}


class SyncError(Exception):
    pass


def sri(data: bytes) -> str:
    return "sha512-" + base64.b64encode(hashlib.sha512(data).digest()).decode()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def read_tarball(data: bytes) -> dict[str, str]:
    import io
    out: dict[str, str] = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
        for key, name in MEMBERS.items():
            try:
                fh = tf.extractfile(name)
            except KeyError:
                fh = None
            if fh is None:
                raise SyncError(f"패키지에 {name} 이(가) 없습니다. MWG 패키지 구조가 바뀌었을 수 있습니다")
            out[key] = fh.read().decode("utf-8")
    return out


def npm_pack(version: str, dest: Path, offline: bool) -> Path | None:
    npm = shutil.which("npm")
    if not npm:
        return None
    cmd = [npm, "pack", f"{PKG}@{version}", "--pack-destination", str(dest)] + (["--offline"] if offline else [])
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return None
    if res.returncode != 0:
        return None
    found = sorted(dest.glob(f"{PKG}-*.tgz"))
    return found[-1] if found else None


def obtain_tarball(w: dict, tarball: Path | None, offline_only: bool) -> bytes | None:
    if tarball:
        return tarball.read_bytes()
    with tempfile.TemporaryDirectory() as tmp:
        p = npm_pack(w["mwg_version"], Path(tmp), offline=True)
        if p is None and not offline_only:
            p = npm_pack(w["mwg_version"], Path(tmp), offline=False)
        return p.read_bytes() if p else None


def policy_inputs(w: dict) -> dict:
    keys = ("ext_version", "mwg_version", "mwg_integrity", "baseline", "fallback_policy", "telemetry",
            "allow_origin_trials", "allow_volatile_features")
    return {k: w[k] for k in keys}


def describe_baseline(b: str) -> str:
    if b == "widely":
        return "Baseline Widely available (MWG 기본값). 이 기준에 못 미치는 기능은 가이드의 대체 권고를 따른다."
    if b == "newly":
        return "Baseline Newly available 까지 대체 코드 없이 쓴다."
    if b == "limited":
        return "Limited availability 기능까지 대체 코드 없이 쓴다 (지원 브라우저가 통제된 환경)."
    return f"This project's Baseline target is Baseline {b}. 'Baseline since' 연도가 {b} 이하인 기능은 대체 코드 없이 쓴다."


def hold_section(w: dict) -> str:
    fb = w["fallback_policy"].strip() or "별도 정책 없음. 가이드의 Fallback 권고를 따르되, 전략이 둘 이상이면 아래 R18 대로 사람에게 묻는다."
    ver = w["mwg_version"]
    return f"""

## HOLD 프로젝트 규칙 (이 절이 위 내용보다 우선한다)

이 프로젝트는 HOLD 웹 확장 web-{w['ext_version']}을 따른다. 정책의 원본은 `hold.toml`의 `[web]`이고 사람이 소유한다. `.mwgrc`는 그 정책에서 생성된 파일이다.

### 브라우저 지원 정책 (R14)
- 지원 기준: {describe_baseline(w['baseline'])}
- 대체 동작 정책: {fb}
- 위 "Reactive Policy Discovery"를 따르지 않는다. 지원 정책을 `CLAUDE.md`·`AGENTS.md`·`.mwgrc`에 쓰거나 쓰자고 제안하지 않는다. 정책이 작업과 맞지 않으면 멈추고, 이유와 선택지를 보고한다.

### 대체 동작 선택은 계약 질문이다 (R18)
- 가이드가 대체 전략을 둘 이상 제시하거나, 지원 기준 밖 브라우저에서 기능을 빼야 할 때는 스스로 고르지 않는다. spec.md의 `## 계약 질문 목록`에 `(웹)`으로 시작하는 질문으로 남긴다.

### 참조 가이드 기록 (R16)
- Stage 2에서 search·retrieve한 가이드는 spec.md의 `## 참조 가이드` 절에 `mwg:<id>` 형식으로 적는다. 예: `- mwg:light-dismiss-a-dialog — 바깥 클릭 닫기는 closedby="any"`.
- 가이드를 쓰지 않은 변경이면 그 절에 `생략: <구체적인 이유>` 한 줄만 적는다.
- 응답 끝의 `### Modern Web Guidance` 절은 증거가 아니다. 증거는 retrieve 명령의 실제 출력(훅이 기록)과 검사 출력이다 (H9).

### 버전과 명령 (R17)
- 이 skill과 가이드는 `{PKG}@{ver}`로 고정되어 있다. 에이전트는 `search`·`retrieve`·`list`만 쓴다. 다른 버전, 다른 하위 명령(`set-baseline`, `set-allow-*`, `install`, `update`), 텔레메트리 접두어(`DISABLE_TELEMETRY=1`)가 빠진 호출은 훅이 막는다.
- 업데이트 경고가 나와도 사용자를 설득하지 않는다. 경고 내용을 그대로 보고만 한다.

### 레거시 패턴 검사 (R15)
- 프런트엔드 파일을 고치면(편집 도구든 Bash든) 훅이 `legacy-scan`을 고정 버전으로 돌린다. 직접 돌리지 않아도 된다.
- 검출이 오탐이라고 판단되면 코드를 비틀지 말고 멈춰서 보고한다. 받아들일 검출은 사람이 `hold.toml`의 `[web].legacy_allow`에 적는다.

### 범위
- 백엔드(Python, SQL, LangGraph, 인프라)에는 쓰지 않는다. 위 "DO NOT trigger" 목록과 같다.
"""


def transform_skill(text: str, w: dict, skill_version: str) -> str:
    latest = f"{PKG}@latest"
    if text.count(latest) == 0:
        raise SyncError(f"MWG SKILL.md 에서 '{latest}' 를 찾지 못했습니다. 원본 형식이 바뀌었을 수 있습니다")
    ver = w["mwg_version"]
    out = text.replace(latest, f"{PKG}@{ver}")
    if not w["telemetry"]:
        out = re.sub(r"(?<!DISABLE_TELEMETRY=1 )\b(npx -y |pnpx )(" + re.escape(PKG) + r"@)", r"DISABLE_TELEMETRY=1 \1\2", out)
    notice = (f"<!-- hold-web: sync.py 가 {PKG}@{ver} (skill {skill_version}, {w['mwg_integrity'][:20]}…) 에서 생성. "
              "원본: Google LLC, Apache-2.0 (같은 폴더의 LICENSE). 변경: 버전 고정"
              + (", 텔레메트리 끔" if not w["telemetry"] else "")
              + ", 'HOLD 프로젝트 규칙' 절 추가. 보호 경로 — 손으로 고치지 마세요. -->\n")
    m = re.match(r"^---\n.*?\n---\n", out, re.S)
    out = (out[: m.end()] + "\n" + notice + out[m.end():]) if m else notice + out
    return out.rstrip("\n") + hold_section(w)


def render(members: dict[str, str], w: dict) -> dict[str, bytes]:
    """tarball 내용과 [web] 정책에서 생성물 전부를 만든다. 결정적(같은 입력 → 같은 바이트)."""
    pkg_ver = json.loads(members["package"]).get("version")
    if pkg_ver != w["mwg_version"]:
        raise SyncError(f"패키지 버전 {pkg_ver} 이(가) hold.toml 의 mwg_version {w['mwg_version']} 과 다릅니다")
    skill_version = members["skill_version"].strip()
    guides = [g for g in json.loads(members["guides"]) if isinstance(g, dict) and g.get("id")]
    if not guides:
        raise SyncError("가이드 목록이 비어 있습니다")
    index = {
        "mwg_version": w["mwg_version"],
        "skill_version": skill_version,
        "count": len(guides),
        "guides": [{"id": g["id"], "category": g.get("category", ""), "description": g.get("description", "")}
                   for g in sorted(guides, key=lambda g: g["id"])],
    }
    mwgrc = {"baseline": w["baseline"], "allowOriginTrials": w["allow_origin_trials"],
             "allowVolatileFeatures": w["allow_volatile_features"]}
    files = {
        SKILL_PATH: transform_skill(members["skill"], w, skill_version).encode("utf-8"),
        LICENSE_PATH: members["license"].encode("utf-8"),
        GUIDES_PATH: (json.dumps(index, ensure_ascii=False, indent=1) + "\n").encode("utf-8"),
        MWGRC_PATH: (json.dumps(mwgrc, indent=2) + "\n").encode("utf-8"),
    }
    lock = {
        "generated_by": f"hold-web {EXT_VERSION} sync.py",
        "mwg_version": w["mwg_version"],
        "mwg_integrity": w["mwg_integrity"],
        "skill_version": skill_version,
        "policy": policy_inputs(w),
        "files": {p: sha256(b) for p, b in sorted(files.items())},
    }
    files[LOCK_PATH] = (json.dumps(lock, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
    return files


# ── 레거시 패턴 검사 ──────────────────────────────────────────────────

@dataclass
class Finding:
    guide: str
    rule: str
    file: str
    line: int | None
    message: str


@dataclass
class ScanResult:
    findings: list[Finding] = field(default_factory=list)
    allowed: list[Finding] = field(default_factory=list)
    skipped: str | None = None
    error: str | None = None


def mwg_env(w: dict) -> dict:
    env = dict(os.environ)
    if not w["telemetry"]:
        env["DISABLE_TELEMETRY"] = "1"
    return env


def scan(root: Path, w: dict, rels: list[str]) -> ScanResult:
    """대상 파일을 임시 폴더에 복사해 한 번에 검사한다 (.gitignore·파일 이름·경로의 영향을 받지 않게)."""
    result = ScanResult()
    rels = sorted({r for r in rels if is_frontend(r, w) and (root / r).is_file()})
    if not rels:
        return result
    npx = shutil.which("npx")
    if not npx:
        result.skipped = "npx 가 없어 레거시 패턴 검사를 건너뛰었습니다 (Node.js 22 이상 필요)"
        return result
    tmpl = {s.lower() for s in w["template_suffixes"]}
    with tempfile.TemporaryDirectory(prefix="hold-web-scan-") as tmp:
        back: dict[str, str] = {}
        for r in rels:
            name = r + ".html" if PurePosixPath(r).suffix.lower() in tmpl else r
            dst = Path(tmp) / "src" / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / r, dst)
            back[name] = r
        cmd = [npx, "-y", f"{PKG}@{w['mwg_version']}", "legacy-scan", str(Path(tmp) / "src"), "--json"]
        try:
            res = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True, encoding="utf-8",
                                 env=mwg_env(w), timeout=SCAN_TIMEOUT)
        except subprocess.TimeoutExpired:
            result.skipped = f"legacy-scan 이 {SCAN_TIMEOUT}초 안에 끝나지 않았습니다 (오프라인이면 npm 캐시를 확인)"
            return result
        try:
            data = json.loads(res.stdout)
        except json.JSONDecodeError:
            tail = ((res.stderr or res.stdout).strip().splitlines() or [""])[-1]
            result.error = f"legacy-scan 출력을 읽지 못했습니다: {tail[:200]}"
            return result
        if not isinstance(data, dict) or data.get("error") or not isinstance(data.get("guides"), list):
            result.error = f"legacy-scan 이 오류를 돌려줬습니다: {str(data.get('error') if isinstance(data, dict) else data)[:200]}"
            return result
        for g in data["guides"]:
            for r in g.get("rules", []):
                for m in r.get("findings", []):
                    raw = str(m.get("file", "")).replace("\\", "/").lstrip("./")
                    file = back.get(raw) or back.get(raw.removeprefix("src/")) or raw
                    result.findings.append(Finding(g.get("guideId", "?"), r.get("ruleId", "?"), file,
                                                   m.get("line"), str(m.get("message", "")).strip()))
    keep: list[Finding] = []
    for f in result.findings:
        if any(_allowed(f, e) for e in w["legacy_allow"]):
            result.allowed.append(f)
        else:
            keep.append(f)
    result.findings = keep
    return result


def _allowed(f: Finding, entry: str) -> bool:
    guide, _, pattern = entry.partition(":")
    return guide == f.guide and (not pattern or glob_match(f.file, pattern))


def format_findings(findings: list[Finding], w: dict) -> str:
    ver = w["mwg_version"]
    pre = "" if w["telemetry"] else "DISABLE_TELEMETRY=1 "
    lines = [f"레거시 웹 패턴이 검출되었습니다 (R15, 고정 가이드 {PKG}@{ver})."]
    by: dict[str, list[Finding]] = {}
    for f in findings:
        by.setdefault(f.guide, []).append(f)
    for guide, items in by.items():
        lines.append(f"\n[{guide}]  가이드 읽기: {pre}npx -y {PKG}@{ver} retrieve {guide}")
        for f in items[:5]:
            lines.append(f"  - {f.file}{':' + str(f.line) if f.line else ''} — {f.message[:200]}")
        if len(items) > 5:
            lines.append(f"  - … 외 {len(items) - 5}건")
    lines.append("\n가이드를 읽고 고치세요. 오탐이라고 판단되면 코드를 비틀지 말고 멈춰서 보고하세요. "
                 "받아들일 검출은 사람이 hold.toml [web].legacy_allow 에 적습니다.")
    return "\n".join(lines)


# ── retrieve 증거 (H9) ────────────────────────────────────────────────

GUIDE_MARK = re.compile(r"^--- Guide for ([a-z0-9][a-z0-9-]*) ---", re.M)
SAVED_TO = re.compile(r"saved to (\S+\.md)")


def retrieved_ids(tool_response) -> list[str]:
    """retrieve 의 실제 출력에서 가이드 ID 를 찾는다. 출력이 파일로 저장되었으면 그 파일을 읽는다."""
    texts: list[str] = []

    def walk(v):
        if isinstance(v, str):
            texts.append(v)
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
    walk(tool_response)
    ids: list[str] = []
    for t in texts:
        ids += GUIDE_MARK.findall(t)
        for p in SAVED_TO.findall(t):
            fp = Path(p.rstrip(".,"))
            if fp.name.startswith("mwg-guide-") and fp.exists():
                try:
                    ids += GUIDE_MARK.findall(fp.read_text(encoding="utf-8", errors="replace"))
                except OSError:
                    pass
    return sorted(set(ids))


def known_guides(root: Path) -> set[str]:
    try:
        data = json.loads((root / GUIDES_PATH).read_text(encoding="utf-8"))
        return {g["id"] for g in data.get("guides", []) if isinstance(g, dict) and g.get("id")}
    except (OSError, json.JSONDecodeError):
        return set()
