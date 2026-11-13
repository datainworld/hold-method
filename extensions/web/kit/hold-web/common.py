"""HOLD 웹 확장 web-0.1 공통 모듈.

설치 위치: <프로젝트>/.claude/hold-web/common.py (보호 경로). 코어 키트 파일은 import 하지 않습니다.

위협 모델 (extensions/web/README.md 1절): 실수하는 협조적 에이전트. 훅은 실수와 흔한 셸 형태를 막고,
의도적인 우회의 최종 방어선은 커밋 검사와 CI(install.py --verify, web_check.py) 입니다.
"""
from __future__ import annotations

import base64
import fnmatch
import glob as _glob
import hashlib
import io
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
ALLOWED_SUBCOMMANDS = ("search", "retrieve", "list", "legacy-scan")
# MWG(node util.parseArgs, strict:false)가 값을 받는 옵션으로 선언한 것은 --skill-version 뿐이다 (ADV3-01)
VALUE_OPTIONS = {"--skill-version"}
SCAN_TIMEOUT = 100
HOOK_TIMEOUT_MIN = 120
HASH_LIMIT = 1 << 20     # 이보다 작은 파일은 스냅샷에 내용 해시를 넣는다

# 경로
WRAPPER = ".claude/hold-web/mwg.py"
EXT_DIR = ".claude/hold-web"
EXT_MANIFEST = ".claude/hold-web/MANIFEST.json"
GUARD = ".claude/hooks/web_guard.py"
SKILL_PATH = ".claude/skills/modern-web-guidance/SKILL.md"
LICENSE_PATH = ".claude/skills/modern-web-guidance/LICENSE"
GUIDES_PATH = "docs/hold/web/guides.json"
LOCK_PATH = "docs/hold/web/lock.json"
MWGRC_PATH = ".mwgrc"
USAGE_PATH = "docs/architecture/usage-environments.md"
PKG_STORE = ".hold/web-pkg"          # 검증된 패키지 사본 (Git 밖, 확장이 보호)
SNAP_FILE = ".hold/logs/web_snap.json"
HOOK_LOG = ".hold/logs/hooks.jsonl"
PRECOMMIT = ".pre-commit-config.yaml"

# 확장이 지키는 경로 (코어 보호 목록과 별개). 코어가 이미 지키는 hold.toml·.claude/ 도 Bash 판정을 더 엄격히 하려고 넣는다
PROTECTED_PREFIXES = (".claude/", ".git/hooks/", ".git/config", "hold.toml", "docs/hold/web/", ".hold/logs/", PKG_STORE + "/", USAGE_PATH, PRECOMMIT)
PROTECTED_BASENAMES = (".mwgrc",)    # 위치 무관 (MWG 는 상위 폴더·홈의 .mwgrc 도 읽는다)
PROTECTED_CANDIDATES = (             # 글롭 패턴과 대조할 구체적인 이름
    ".git/hooks", ".git/hooks/pre-commit", ".git/config", ".claude", ".claude/settings.json", ".claude/settings.local.json", GUARD, EXT_DIR, WRAPPER, EXT_MANIFEST,
    EXT_DIR + "/common.py", EXT_DIR + "/sync.py", EXT_DIR + "/web_check.py", EXT_DIR + "/web_scan.py", EXT_DIR + "/VERSION",
    ".claude/skills/modern-web-guidance", SKILL_PATH, LICENSE_PATH, "hold.toml", ".mwgrc", "docs/hold/web",
    GUIDES_PATH, LOCK_PATH, ".hold", ".hold/logs", HOOK_LOG, SNAP_FILE, PKG_STORE, USAGE_PATH, PRECOMMIT,
)
HUMAN_ONLY = (EXT_DIR + "/sync.py", "extensions/web/install.py")
AGENT_SCRIPTS = (WRAPPER, EXT_DIR + "/web_check.py", EXT_DIR + "/web_scan.py")
READONLY_COMMANDS = {"cat", "less", "more", "head", "tail", "grep", "egrep", "fgrep", "rg", "ls", "wc",
                     "diff", "stat", "file", "md5sum", "sha256sum", "sha1sum", "realpath", "readlink", "type"}
READONLY_GIT = {"diff", "log", "show", "status", "blame", "ls-files"}
GIT_WRITE_OPTS = ("--output", "-o", "--output-directory", "--ext-diff")
GIT_GATE_SUBS = {"commit", "merge", "push", "rebase", "cherry-pick", "am", "revert", "pull"}
GIT_ENV_BAD = re.compile(r"^(GIT_CONFIG\w*|GIT_DIR|GIT_WORK_TREE|GIT_INDEX_FILE|GIT_COMMON_DIR|SKIP|PRE_COMMIT\w*|HUSKY)=")
WRAPPERS = {"env", "command", "exec", "time", "nohup", "sudo", "nice", "builtin", "xargs", "timeout", "stdbuf", "setsid"}
WRAPPER_VALUE_OPTS = {"-u", "--unset", "-C", "--chdir", "-I", "-i", "-n", "-L", "-d", "-P", "-s", "-E", "-k", "--signal"}
SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}
MENTION_OK = READONLY_COMMANDS | {"echo", "printf", "cd", "pushd", "popd", "test", "[", "git", "true"}
GLOB_META = set("*?[")

DEFAULTS: dict = {
    "enabled": False,
    "guard": False,            # 실행 시점 훅(web_guard.py)을 쓰는지. 기본은 쓰지 않음 (방법론 통합만)
    "disabled_reason": "",
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
    """훅 로그. ensure_ascii 로 써서 이상한 파일 이름에도 깨지지 않는다."""
    try:
        import datetime as _dt
        f = root / HOOK_LOG
        f.parent.mkdir(parents=True, exist_ok=True)
        record = {"ts": _dt.datetime.now().isoformat(timespec="seconds"), "ext": f"web-{EXT_VERSION}", **record}
        with f.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=True) + "\n")
    except Exception:  # noqa: BLE001 — 기록 실패가 판정을 바꾸지 않게
        pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def sha256_raw(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sri(data: bytes) -> str:
    return "sha512-" + base64.b64encode(hashlib.sha512(data).digest()).decode()


# ── 경로 정규화와 보호 판정 ──────────────────────────────────────────

_STREAM = re.compile(r":(?::?\$data|[^/:]*)$", re.I)


def norm(p: str) -> str:
    """대소문자·구분자·NTFS 대체 스트림·끝의 점과 공백을 정규화한 posix 문자열."""
    s = p.replace("\\", "/").strip()
    s = re.sub(r"^[a-zA-Z]:/", "/", s)          # 드라이브 문자
    s = _STREAM.sub("", s) if ":" in s.rsplit("/", 1)[-1] else s
    parts = [seg.rstrip(" .") if seg not in (".", "..") else seg for seg in s.split("/")]
    return "/".join(parts).casefold()


def rel_posix(root: Path, raw: str) -> str | None:
    p = Path(raw.replace("\\", "/"))
    p = p if p.is_absolute() else root / p
    try:
        p = p.resolve()
    except OSError:
        p = Path(os.path.abspath(p))
    try:
        return p.relative_to(root).as_posix()
    except ValueError:
        return None


def _prefix_hit(rel_norm: str) -> bool:
    for pre in PROTECTED_PREFIXES:
        pn = pre.casefold()
        if pn.endswith("/"):
            if rel_norm == pn.rstrip("/") or rel_norm.startswith(pn):
                return True
        elif rel_norm == pn:
            return True
    return False


def is_protected_path(root: Path, raw: str) -> bool:
    n = norm(raw)
    if n.rstrip("/").rsplit("/", 1)[-1] in PROTECTED_BASENAMES:
        return True
    rel = rel_posix(root, raw)
    if rel is None:
        return False
    if _prefix_hit(norm(rel)):
        return True
    # 대소문자를 무시하는 파일 시스템에서 다른 표기로 같은 파일을 가리키는 경우
    try:
        target = (root / rel)
        if target.exists():
            for cand in PROTECTED_CANDIDATES:
                c = root / cand
                if c.exists() and os.path.samefile(c, target):
                    return True
    except OSError:
        pass
    return False


def expand_braces(tok: str) -> list[str]:
    m = re.search(r"\{([^{}]*,[^{}]*)\}", tok)
    if not m:
        return [tok]
    out: list[str] = []
    for alt in m.group(1).split(","):
        out += expand_braces(tok[: m.start()] + alt + tok[m.end():])
    return out[:64]


def token_paths(tok: str) -> list[str]:
    """토큰에 들어 있을 수 있는 경로 조각: '--opt=값'의 값, 중괄호 전개 결과."""
    vals = [tok]
    if tok.startswith("-") and "=" in tok:
        vals.append(tok.split("=", 1)[1])
    out: list[str] = []
    for v in vals:
        out += expand_braces(v)
    return out


def token_hits(tok: str, root: Path, candidates: tuple[str, ...] = PROTECTED_CANDIDATES,
               substring: bool = True) -> bool:
    """토큰이 보호 경로를 가리키는가. 글자 그대로의 언급, 글롭 패턴, 대소문자 변형을 모두 본다."""
    root_n = norm(str(root))
    for t in token_paths(tok):
        n = norm(t)
        s = re.sub(r"^(?:\./)+", "", n)          # 앞의 "./" 만 떼어 낸다 (".claude" 의 점은 남김)
        if substring:
            if any(b in n for b in PROTECTED_BASENAMES):
                return True
            if any(p.casefold().rstrip("/") in n for p in PROTECTED_PREFIXES):
                return True
        else:
            if any(s == c.casefold() or s.endswith("/" + c.casefold()) for c in candidates):
                return True
        if GLOB_META & set(t):
            for c in candidates:
                cn = c.casefold()
                if "/" not in s:
                    # 슬래시 없는 패턴은 현재 폴더(루트)의 이름만 가리킨다
                    if "/" not in cn and fnmatch.fnmatchcase(cn, s):
                        return True
                elif fnmatch.fnmatchcase(cn, s) or fnmatch.fnmatchcase(f"{root_n}/{cn}", s) \
                        or fnmatch.fnmatchcase(f"x/{cn}", s):
                    return True
            try:
                base = t if os.path.isabs(t) else str(root / t)
                for hit in _glob.glob(base, recursive=True)[:200]:
                    if is_protected_path(root, hit) if substring else any(
                            rel_posix(root, hit) == c for c in candidates):
                        return True
            except (OSError, re.error):
                return True   # 전개할 수 없는 패턴은 막는 쪽으로
    return False


# ── 셸 명령 해석 ──────────────────────────────────────────────────────

@dataclass
class SimpleCmd:
    argv: list[str]
    assigns: dict[str, str] = field(default_factory=dict)
    redirects: list[str] = field(default_factory=list)


class ParseError(Exception):
    pass


def split_commands(cmd: str, depth: int = 0) -> list[SimpleCmd]:
    """셸 명령을 단순 명령 목록으로. 따옴표·연산자·리다이렉트·명령/프로세스 치환·bash -c 를 다룬다."""
    if depth > 4:
        raise ParseError("중첩이 너무 깊습니다")
    text = (cmd.replace("\\\r\n", " ").replace("\\\n", " ").replace("`", " ; ")
            .replace("\r\n", "\n").replace("\n", " ; "))
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
        if tok and set(tok) <= set(";&|()<>"):
            if "(" in tok or ")" in tok or set(tok) & set(";|") or tok in ("&", "&&"):
                if cur or redirects:
                    out.extend(_finish(cur, redirects, depth))
                cur, redirects, expect_redirect = [], [], False
                continue
            expect_redirect = ">" in tok      # > >> &> >| 는 쓰기 대상, < 는 읽기
            continue
        if expect_redirect:
            redirects.append(tok)
            expect_redirect = False
            continue
        if tok == "$":
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
                i += 1
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
    for t in tokens + redirects:
        for m in re.finditer(r"[$<>]\((.*)\)", t, re.S):
            result += split_commands(m.group(1), depth + 1)
        if " ; " in t:
            result += split_commands(t, depth + 1)
    if argv and argv[0].rsplit("/", 1)[-1] in SHELLS:
        for j, a in enumerate(argv[1:], 1):
            if a == "-c" or (a.startswith("-") and not a.startswith("--") and "c" in a[1:]):
                if j + 1 < len(argv):
                    result += split_commands(argv[j + 1], depth + 1)
                break
    if argv and argv[0] in ("eval", "source", "."):
        result += split_commands(" ".join(argv[1:]), depth + 1) if argv[0] == "eval" else []
    return result


def _pkg_spec(tok: str) -> bool:
    t = tok.strip()
    return t == PKG or t.startswith(PKG + "@")


def mwg_direct_calls(cmd: str) -> list[str]:
    """npx·npm·node 등으로 MWG 를 직접 부르는 단순 명령 목록 (모두 금지 — 래퍼만 허용)."""
    hits: list[str] = []
    for sc in split_commands(cmd):
        if not sc.argv:
            continue
        exe = sc.argv[0].rsplit("/", 1)[-1]
        args = sc.argv[1:]
        joined = " ".join(sc.argv)
        if exe == PKG or any("modern-web.mjs" in a for a in sc.argv):
            hits.append(joined)
        elif exe in ("npx", "pnpx", "bunx") or (exe in ("npm", "pnpm", "yarn", "bun") and args):
            if any(_pkg_spec(a) or (a.startswith("--package=") and _pkg_spec(a.split("=", 1)[1])) for a in sc.argv):
                hits.append(joined)
            else:
                for j, a in enumerate(args):
                    if a in ("-c", "--call") and j + 1 < len(args):
                        hits += mwg_direct_calls(args[j + 1])
        elif exe in SHELLS and not any(a == "-c" or (a.startswith("-") and not a.startswith("--") and "c" in a[1:]) for a in args) and PKG in cmd:
            hits.append(joined)   # echo … | sh 처럼 표준입력으로 읽는 셸
        elif exe in ("source", ".", "eval") and PKG in cmd:
            hits.append(joined)
        elif exe not in MENTION_OK and any(PKG in t for t in sc.argv):
            hits.append(joined)   # 실행 명령에 패키지 이름이 있는데 해석되지 않음
        elif re.search(r"[$*?\[{]", exe) and re.search(r"npx|npm|node|modern|guidance|mjs", cmd):
            hits.append(joined)   # 명령어 자리에 변수·글롭·중괄호가 있고 node 계열 이름이 보이면 막음 (정적 해석 불가)
    return hits


def check_mwg_calls(cmd: str) -> str | None:
    try:
        hits = mwg_direct_calls(cmd)
    except ParseError:
        return ("명령을 해석할 수 없어 Modern Web Guidance 호출 여부를 확인하지 못했습니다 (R17). 따옴표를 닫고 단순한 형태로 다시 실행하세요."
                if PKG in cmd or "modern-web.mjs" in cmd else None)
    if hits:
        return (f"이 프로젝트는 Modern Web Guidance 를 래퍼로만 씁니다 (R17): python {WRAPPER} <search|retrieve|list> …\n"
                "래퍼가 검증된 고정 사본을 텔레메트리 없이 실행합니다. npx·npm·node 로 직접 부르지 마세요.")
    return None


def _git_sub(argv: list[str]) -> tuple[str | None, list[str]]:
    """git 전역 옵션(-c k=v, -C dir, --opt)을 건너뛴 하위 명령과 그 뒤 인자."""
    i = 1
    while i < len(argv):
        a = argv[i]
        if a in ("-c", "-C", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--config-env") and "=" not in a:
            i += 2
        elif a.startswith("-"):
            i += 1
        else:
            return a, argv[i + 1:]
    return None, []


def _git_gate(sc: "SimpleCmd") -> str | None:
    """pre-commit 을 건너뛰게 하거나, 증거(.hold)를 지울 수 있는 git·pre-commit 사용을 막는다 (ADV3-02·03·04)."""
    argv = sc.argv
    bad_env = [k for k in sc.assigns if GIT_ENV_BAD.match(k + "=")] + [t.split("=", 1)[0] for t in argv if GIT_ENV_BAD.match(t)]
    if bad_env:
        return f"{bad_env[0]} 환경변수로 git·pre-commit 동작을 바꿀 수 없습니다 (커밋 검사 우회 방지)."
    if not argv:
        return None
    exe = argv[0].rsplit("/", 1)[-1]
    if exe == "pre-commit" and any(a in ("uninstall", "install", "init-templatedir") for a in argv[1:]):
        return "pre-commit 설치·해제는 사람이 합니다."
    if exe != "git":
        return None
    low = [a.casefold() for a in argv]
    if any("core.hookspath" in a for a in low):
        return "core.hooksPath 로 pre-commit 을 우회할 수 없습니다."
    sub, rest = _git_sub(argv)
    allr = [a.casefold() for a in rest]
    for a in allr + low:
        name = a.split("=", 1)[0]
        if len(name) >= 8 and name.startswith("--no-ver") and "--no-verify".startswith(name):
            return "pre-commit 검사를 건너뛰는 git 옵션입니다 (--no-verify). 검사가 실패하면 고치거나 사람에게 보고하세요."
    if sub in GIT_GATE_SUBS and any(re.fullmatch(r"-[a-z]*n[a-z]*", a) and a != "-n" or a == "-n" for a in rest if not a.startswith("--")):
        return "pre-commit 검사를 건너뛰는 git 단축 옵션(-n)입니다. 검사가 실패하면 고치거나 사람에게 보고하세요."
    if sub == "clean" or (sub == "reset" and "--hard" in allr) or (sub == "stash" and any(a in ("-u", "-a", "--include-untracked", "--all") for a in allr)) \
            or (sub in ("checkout", "restore", "switch") and any(a in (".", "-f", "--force", ":/") for a in allr)):
        return "작업 증거(.hold/)와 검증된 사본을 지울 수 있는 git 명령입니다 (clean, reset --hard, checkout ., stash -u). 사람이 실행하세요."
    return None


def check_bash_protected(cmd: str, root: Path) -> str | None:
    """보호 경로를 건드리는 Bash 명령인지. 읽기 전용 명령과 허락된 스크립트 실행만 허용한다."""
    try:
        cmds = split_commands(cmd)
    except ParseError:
        return "명령을 해석할 수 없는데 웹 확장 보호 경로가 들어 있습니다." if token_hits(cmd, root) else None
    for sc in cmds:
        argv = sc.argv
        for t in argv:
            if token_hits(t, root, HUMAN_ONLY, substring=False):
                return f"{t} 는 사람이 실행하는 스크립트입니다 (R17). 버전·정책을 바꿔야 한다고 판단되면 멈추고 보고하세요."
        msg = _git_gate(sc)
        if msg:
            return msg
        if any(token_hits(r, root) for r in sc.redirects):
            return "웹 확장 보호 경로에 리다이렉트로 쓸 수 없습니다."
        refs = [t for t in argv + list(sc.assigns.values()) if token_hits(t, root)]
        if not refs or not argv:
            continue
        exe = argv[0].rsplit("/", 1)[-1]
        if exe in READONLY_COMMANDS and not any(a in ("-i", "--in-place") or a.startswith("--in-place") for a in argv[1:]):
            continue
        if exe == "git" and len(argv) > 1 and argv[1] in READONLY_GIT \
                and not any(a == o or a.startswith(o + "=") for a in argv[2:] for o in GIT_WRITE_OPTS):
            continue
        if exe.startswith("python") and len(argv) > 1 and token_hits(argv[1], root, AGENT_SCRIPTS, substring=False):
            if all(t == argv[1] or not token_hits(t, root) for t in argv + list(sc.assigns.values())):
                continue
        return f"웹 확장 보호 경로({refs[0]})를 건드리는 명령입니다. 읽기는 cat·grep 등으로만 하세요."
    return None


# ── 검증된 패키지 사본 ───────────────────────────────────────────────

MEMBERS = {
    "package": "package/package.json",
    "skill": "package/skills/modern-web-guidance/SKILL.md",
    "skill_version": "package/skills/modern-web-guidance/skill-version.txt",
    "guides": "package/skills/modern-web-guidance/gen/guides.json",
    "license": "package/LICENSE",
}
CLI_REL = "skills/modern-web-guidance/modern-web.mjs"


class SyncError(Exception):
    pass


def tar_files(data: bytes) -> dict[str, bytes]:
    """tarball 의 'package/' 아래 일반 파일만 (경로 → 내용). 링크·절대 경로·'..'는 거부."""
    out: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
        for m in tf.getmembers():
            if m.isdir():
                continue
            name = m.name
            if not m.isfile() or name.startswith("/") or ".." in PurePosixPath(name).parts or not name.startswith("package/"):
                raise SyncError(f"패키지에 허용하지 않는 항목이 있습니다: {name}")
            fh = tf.extractfile(m)
            out[name[len("package/"):]] = fh.read() if fh else b""
    return out


def tree_hash(files: dict[str, bytes]) -> str:
    h = hashlib.sha256()
    for rel in sorted(files):
        h.update(rel.encode() + b"\0" + sha256_raw(files[rel]).encode() + b"\n")
    return h.hexdigest()


def dir_files(d: Path) -> dict[str, bytes]:
    return {p.relative_to(d).as_posix(): p.read_bytes() for p in d.rglob("*") if p.is_file()}


def members(files: dict[str, bytes]) -> dict[str, str]:
    out = {}
    for key, name in MEMBERS.items():
        rel = name[len("package/"):]
        if rel not in files:
            raise SyncError(f"패키지에 {name} 이(가) 없습니다. MWG 패키지 구조가 바뀌었을 수 있습니다")
        out[key] = files[rel].decode("utf-8")
    if CLI_REL not in files:
        raise SyncError(f"패키지에 {CLI_REL} 이(가) 없습니다")
    return out


def pkg_paths(root: Path, w: dict) -> tuple[Path, Path]:
    base = root / PKG_STORE
    return base / f"{PKG}-{w['mwg_version']}.tgz", base / w["mwg_version"]


def npm_pack(version: str, dest: Path, offline: bool) -> Path | None:
    npm = shutil.which("npm")
    if not npm:
        return None
    cmd = [npm, "pack", f"{PKG}@{version}", "--pack-destination", str(dest)] + (["--offline"] if offline else [])
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        return None
    if res.returncode != 0:
        return None
    found = sorted(dest.glob(f"{PKG}-*.tgz"))
    return found[-1] if found else None


def fetch(w: dict, tarball: Path | None, offline_only: bool = False) -> bytes | None:
    if tarball:
        return tarball.read_bytes()
    with tempfile.TemporaryDirectory() as tmp:
        p = npm_pack(w["mwg_version"], Path(tmp), offline=True)
        if p is None and not offline_only:
            p = npm_pack(w["mwg_version"], Path(tmp), offline=False)
        return p.read_bytes() if p else None


def store_package(root: Path, w: dict, data: bytes) -> str:
    """무결성을 확인한 tarball 과 풀린 사본을 PKG_STORE 에 둔다. 트리 해시를 돌려준다."""
    if sri(data) != w["mwg_integrity"]:
        raise SyncError("패키지의 무결성 값이 hold.toml 의 mwg_integrity 와 다릅니다. 멈춥니다")
    files = tar_files(data)
    tgz, d = pkg_paths(root, w)
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    for rel, b in files.items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b)
    tgz.write_bytes(data)
    return tree_hash(files)


def verify_package(root: Path, w: dict, lock: dict | None = None) -> tuple[Path | None, str | None]:
    """실행 전에 사본을 확인한다. (CLI 경로, 오류)."""
    tgz, d = pkg_paths(root, w)
    if not d.exists() or not tgz.exists():
        return None, f"검증된 MWG 사본이 없습니다 ({PKG_STORE}/). 사람이 python {EXT_DIR}/sync.py 를 실행하세요"
    if lock is None:
        try:
            lock = json.loads((root / LOCK_PATH).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None, f"{LOCK_PATH} 를 읽을 수 없습니다. 사람이 sync.py 를 실행하세요"
    if lock.get("mwg_integrity") != w["mwg_integrity"] or lock.get("mwg_version") != w["mwg_version"]:
        return None, "lock.json 의 고정 버전·무결성 값이 hold.toml 과 다릅니다. 사람이 sync.py 를 실행하세요"
    if tree_hash(dir_files(d)) != lock.get("pkg_tree"):
        return None, f"MWG 사본({PKG_STORE}/{w['mwg_version']})이 검증한 내용과 다릅니다. 사람이 sync.py 로 다시 설치하세요"
    return d / CLI_REL, None


def node_command(cli: Path, args: list[str]) -> list[str] | None:
    node = shutil.which("node")
    return [node, str(cli), *args] if node else None


def mwg_env(w: dict) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in ("NODE_OPTIONS", "NODE_PATH")}  # 사본 밖 코드 주입 차단
    if not w["telemetry"]:
        env["DISABLE_TELEMETRY"] = "1"
    return env


# ── 고정 버전 생성물 ─────────────────────────────────────────────────

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
    return f"""

## HOLD 프로젝트 규칙 (이 절이 위 내용보다 우선한다)

이 프로젝트는 HOLD 웹 확장 web-{w['ext_version']}을 따른다. 정책의 원본은 `hold.toml`의 `[web]`이고 사람이 소유한다. `.mwgrc`는 그 정책에서 생성된 파일이다.

### 실행 방법 (R17)
- Modern Web Guidance는 **`python {WRAPPER} <search|retrieve|list|legacy-scan> …`로만** 실행한다. 위 본문의 `npx`·`pnpx`·`npx.cmd`·네트워크 허용 요청 안내는 이 프로젝트에 해당하지 않는다.
- 래퍼는 사람이 고정하고 무결성을 확인한 `{PKG}@{w['mwg_version']}` 사본을 텔레메트리 없이 실행한다. 다른 하위 명령(`set-baseline`, `set-allow-*`, `install`, `update`)은 래퍼와 훅이 막는다.
- 업데이트 경고가 나와도 사용자를 설득하지 않는다. 경고 내용을 그대로 보고만 한다.

### 브라우저 지원 정책 (R14)
- 지원 기준: {describe_baseline(w['baseline'])}
- 대체 동작 정책: {fb}
- 위 "Reactive Policy Discovery"를 따르지 않는다. 지원 정책을 `CLAUDE.md`·`AGENTS.md`·`.mwgrc`에 쓰거나 쓰자고 제안하지 않는다. 정책이 작업과 맞지 않으면 멈추고, 이유와 선택지를 보고한다.

### 대체 동작 선택은 계약 질문이다 (R18)
- 가이드가 대체 전략을 둘 이상 제시하거나, 지원 기준 밖 브라우저에서 기능을 빼야 할 때는 스스로 고르지 않는다. spec.md의 `## 계약 질문 목록`에 `(웹)`으로 시작하는 질문으로 남긴다.

### 참조 가이드 기록 (R16)
- Stage 2에서 retrieve한 가이드는 spec.md의 `## 참조 가이드` 절에 `mwg:<id>` 형식으로 적는다. 예: `- mwg:light-dismiss-a-dialog — 바깥 클릭 닫기는 closedby="any"`.
- 가이드를 쓰지 않은 변경이면 그 절에 `생략: <구체적인 이유>` 한 줄만 적는다.
- 응답 끝의 `### Modern Web Guidance` 절은 증거가 아니다. 증거는 래퍼가 기록한 retrieve 출력과 검사 출력이다 (H9).

### 레거시 패턴 검사 (R15)
- 프런트엔드 파일이 바뀌면(편집 도구든 Bash든) 훅이 고정 사본으로 레거시 검사를 한다. 직접 돌리지 않아도 된다.
- 검출이 오탐이라고 판단되면 코드를 비틀지 말고 멈춰서 보고한다. 받아들일 검출은 사람이 `hold.toml`의 `[web].legacy_allow`에 적는다.

### 범위
- 백엔드(Python, SQL, LangGraph, 인프라)에는 쓰지 않는다. 위 "DO NOT trigger" 목록과 같다.
"""


RUNNER_FORMS = re.compile(r"(?:DISABLE_TELEMETRY=1 )?(?:npx -y |pnpx |npx )" + re.escape(PKG) + r"@latest")


def transform_skill(text: str, w: dict, skill_version: str) -> str:
    n = len(RUNNER_FORMS.findall(text))
    if n == 0:
        raise SyncError(f"MWG SKILL.md 에서 '{PKG}@latest' 실행 명령을 찾지 못했습니다. 원본 형식이 바뀌었을 수 있습니다")
    out = RUNNER_FORMS.sub(f"python {WRAPPER}", text)
    if f"{PKG}@latest" in out:
        raise SyncError(f"MWG SKILL.md 에 바꾸지 못한 '{PKG}@latest' 형식이 남았습니다. 원본 형식이 바뀌었을 수 있습니다")
    notice = (f"<!-- hold-web: sync.py 가 {PKG}@{w['mwg_version']} (skill {skill_version}, {w['mwg_integrity'][:20]}…) 에서 생성. "
              f"원본: Google LLC, Apache-2.0 (같은 폴더의 LICENSE). 변경: 실행 명령을 래퍼({WRAPPER})로, "
              "'HOLD 프로젝트 규칙' 절 추가. 보호 경로 — 손으로 고치지 마세요. -->\n")
    m = re.match(r"^---\n.*?\n---\n", out, re.S)
    out = (out[: m.end()] + "\n" + notice + out[m.end():]) if m else notice + out
    return out.rstrip("\n") + hold_section(w)


def render(files: dict[str, bytes], w: dict) -> dict[str, bytes]:
    """패키지 내용과 [web] 정책에서 생성물 전부를 만든다. 결정적."""
    m = members(files)
    pkg_ver = json.loads(m["package"]).get("version")
    if pkg_ver != w["mwg_version"]:
        raise SyncError(f"패키지 버전 {pkg_ver} 이(가) hold.toml 의 mwg_version {w['mwg_version']} 과 다릅니다")
    skill_version = m["skill_version"].strip()
    guides = [g for g in json.loads(m["guides"]) if isinstance(g, dict) and g.get("id")]
    if not guides:
        raise SyncError("가이드 목록이 비어 있습니다")
    index = {"mwg_version": w["mwg_version"], "skill_version": skill_version, "count": len(guides),
             "guides": [{"id": g["id"], "category": g.get("category", ""), "description": g.get("description", "")}
                        for g in sorted(guides, key=lambda g: g["id"])]}
    mwgrc = {"baseline": w["baseline"], "allowOriginTrials": w["allow_origin_trials"],
             "allowVolatileFeatures": w["allow_volatile_features"]}
    out = {
        SKILL_PATH: transform_skill(m["skill"], w, skill_version).encode("utf-8"),
        LICENSE_PATH: m["license"].encode("utf-8"),
        GUIDES_PATH: (json.dumps(index, ensure_ascii=False, indent=1) + "\n").encode("utf-8"),
        MWGRC_PATH: (json.dumps(mwgrc, indent=2) + "\n").encode("utf-8"),
    }
    lock = {"generated_by": f"hold-web {EXT_VERSION} sync.py", "mwg_version": w["mwg_version"],
            "mwg_integrity": w["mwg_integrity"], "skill_version": skill_version, "pkg_tree": tree_hash(files),
            "policy": policy_inputs(w), "files": {p: sha256(b) for p, b in sorted(out.items())}}
    out[LOCK_PATH] = (json.dumps(lock, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
    return out


def skill_version_of(root: Path, w: dict) -> str:
    _, d = pkg_paths(root, w)
    try:
        return (d / "skills/modern-web-guidance/skill-version.txt").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


# ── 스냅샷 (바뀐 파일 찾기) ──────────────────────────────────────────

def is_frontend(rel: str, w: dict) -> bool:
    p = PurePosixPath(rel)
    if set(w["skip_dirs"]).intersection(p.parts[:-1]):
        return False
    suf = p.suffix.lower()
    return suf in {s.lower() for s in w["frontend_suffixes"]} or suf in {s.lower() for s in w["template_suffixes"]}


def is_change_doc(rel: str, cfg: dict) -> bool:
    changes = (cfg.get("paths", {}).get("changes") or "changes").rstrip("/")
    parts = rel.split("/")
    return len(parts) >= 3 and parts[0] == changes and rel.endswith(".md") and not parts[1].startswith("_")


def snapshot(root: Path, w: dict, cfg: dict, prev: dict | None = None) -> dict[str, list]:
    """프런트엔드 파일과 changes/ 산출물의 (mtime, ctime, 크기, 내용 해시). 메타데이터가 같으면 이전 해시를 재사용."""
    prev = prev or {}
    snap: dict[str, list] = {}
    skip = set(w["skip_dirs"])
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip]
        for fn in filenames:
            full = Path(dirpath) / fn
            rel = full.relative_to(root).as_posix()
            if not (is_frontend(rel, w) or is_change_doc(rel, cfg)):
                continue
            try:
                st = full.stat()
            except OSError:
                continue
            meta = [st.st_mtime_ns, st.st_ctime_ns, st.st_size]
            old = prev.get(rel)
            if old and old[:3] == meta:
                snap[rel] = old
                continue
            digest = ""
            if st.st_size <= HASH_LIMIT:
                try:
                    digest = hashlib.sha1(full.read_bytes()).hexdigest()
                except OSError:
                    pass
            snap[rel] = meta + [digest]
    return snap


def forget_files(root: Path, rels: list[str]) -> None:
    """검사에서 문제가 난 파일은 스냅샷에서 빼서, 고쳐질 때까지 다음 훅에서도 다시 검사한다 (ADV3-05)."""
    f = root / SNAP_FILE
    try:
        snap = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    for r in rels:
        snap.pop(r, None)
    f.write_text(json.dumps(snap, ensure_ascii=True), encoding="utf-8")


def changed_files(root: Path, w: dict, cfg: dict) -> list[str] | None:
    """지난 훅 이후 바뀐 파일. 처음이면 기준만 남기고 None."""
    f = root / SNAP_FILE
    prev = None
    if f.exists():
        try:
            prev = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            prev = None
    cur = snapshot(root, w, cfg, prev)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(cur, ensure_ascii=True), encoding="utf-8")
    if prev is None:
        return sorted(cur) if (root / LOCK_PATH).exists() else None   # 설치된 프로젝트의 첫 훅은 전체를 본다 (ADV3-05)

    def differs(old: list | None, new: list) -> bool:
        if not old:
            return True
        if new[3] or old[3]:
            return old[3] != new[3]          # 내용 해시로 판단 (mtime 을 되돌려도 잡힘)
        return old[:3] != new[:3]            # 큰 파일: ctime 포함 메타데이터로 판단
    return sorted(r for r, v in cur.items() if differs(prev.get(r), v))


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


def scan(root: Path, w: dict, rels: list[str]) -> ScanResult:
    """대상 파일을 임시 폴더에 중립 이름(f0001.js 등)으로 복사해 검증된 사본으로 한 번에 검사한다."""
    result = ScanResult()
    rels = sorted({r for r in rels if is_frontend(r, w) and (root / r).is_file()})
    if not rels:
        return result
    cli, err = verify_package(root, w)
    if err:
        result.error = err
        return result
    tmpl = {s.lower() for s in w["template_suffixes"]}
    with tempfile.TemporaryDirectory(prefix="hold-web-scan-") as tmp:
        src = Path(tmp) / "src"
        src.mkdir()
        back: dict[str, str] = {}
        for i, r in enumerate(rels, 1):
            suf = PurePosixPath(r).suffix.lower()
            name = f"f{i:04d}{'.html' if suf in tmpl else suf}"
            shutil.copyfile(root / r, src / name)
            back[name] = r
        cmd = node_command(cli, ["legacy-scan", str(src), "--json"])
        if cmd is None:
            result.skipped = "node 가 없어 레거시 패턴 검사를 건너뛰었습니다 (Node.js 22 이상 필요)"
            return result
        try:
            res = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True, encoding="utf-8",
                                 errors="replace", env=mwg_env(w), timeout=SCAN_TIMEOUT)
        except subprocess.TimeoutExpired:
            result.skipped = f"legacy-scan 이 {SCAN_TIMEOUT}초 안에 끝나지 않았습니다"
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
                    raw = PurePosixPath(str(m.get("file", "")).replace("\\", "/")).name
                    result.findings.append(Finding(g.get("guideId", "?"), r.get("ruleId", "?"), back.get(raw, raw),
                                                   m.get("line"), str(m.get("message", "")).strip()))
    keep: list[Finding] = []
    for f in result.findings:
        (result.allowed if any(_allowed(f, e) for e in w["legacy_allow"]) else keep).append(f)
    result.findings = keep
    return result


def glob_match(path: str, pattern: str) -> bool:
    """'*' 는 '/' 를 넘지 않고, '**' 는 넘는다."""
    rx, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            rx, i = rx + "(?:.*/)?", i + 3
        elif pattern.startswith("**", i):
            rx, i = rx + ".*", i + 2
        elif pattern[i] == "*":
            rx, i = rx + "[^/]*", i + 1
        elif pattern[i] == "?":
            rx, i = rx + "[^/]", i + 1
        else:
            rx, i = rx + re.escape(pattern[i]), i + 1
    return re.fullmatch(rx, path) is not None


def _allowed(f: Finding, entry: str) -> bool:
    guide, _, pattern = entry.partition(":")
    return guide == f.guide and (not pattern or glob_match(f.file, pattern))


def format_findings(findings: list[Finding], w: dict) -> str:
    lines = [f"레거시 웹 패턴이 검출되었습니다 (R15, 고정 가이드 {PKG}@{w['mwg_version']})."]
    by: dict[str, list[Finding]] = {}
    for f in findings:
        by.setdefault(f.guide, []).append(f)
    for guide, items in by.items():
        lines.append(f"\n[{guide}]  가이드 읽기: python {WRAPPER} retrieve {guide}")
        for f in items[:5]:
            lines.append(f"  - {f.file}{':' + str(f.line) if f.line else ''} — {f.message[:200]}")
        if len(items) > 5:
            lines.append(f"  - … 외 {len(items) - 5}건")
    lines.append("\n가이드를 읽고 고치세요. 오탐이라고 판단되면 코드를 비틀지 말고 멈춰서 보고하세요. "
                 "받아들일 검출은 사람이 hold.toml [web].legacy_allow 에 적습니다.")
    return "\n".join(lines)


# ── 기타 ─────────────────────────────────────────────────────────────

GUIDE_MARK = re.compile(r"^--- Guide for ([a-z0-9][a-z0-9-]*) ---", re.M)
SAVED_TO = re.compile(r"saved to (\S+\.md)")


def known_guides(root: Path) -> set[str]:
    try:
        data = json.loads((root / GUIDES_PATH).read_text(encoding="utf-8"))
        return {g["id"] for g in data.get("guides", []) if isinstance(g, dict) and g.get("id")}
    except (OSError, json.JSONDecodeError):
        return set()


def first_positional(args: list[str]) -> tuple[str | None, list[str]]:
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--":
            return (args[i + 1], args[i + 2:]) if i + 1 < len(args) else (None, [])
        if a.startswith("-"):
            i += 2 if ("=" not in a and a in VALUE_OPTIONS) else 1
            continue
        return a, args[i + 1:]
    return None, []
