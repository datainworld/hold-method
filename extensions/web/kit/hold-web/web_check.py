#!/usr/bin/env python3
"""HOLD 웹 확장 web-0.1 검사 — 설치·고정 버전(R17), 사용 환경(R14), 참조 가이드(R16).

  python .claude/hold-web/web_check.py              # 전체 검사 (pre-commit: hold-web-check)
  python .claude/hold-web/web_check.py --metrics    # 훅 로그 집계 (측정)
종료 코드: 0 통과(또는 확장 꺼짐), 1 실패.

설치·고정 검사: 확장 코드 매니페스트, 훅 등록, lock.json, 그리고 검증된 사본(.hold/web-pkg/)으로 생성물을
다시 만들어 바이트 단위로 대조합니다. 사본이 없으면 Lite 는 경고, Standard 이상은 실패입니다
(CI 는 sync.py --fetch-only 로 사본을 받은 뒤 실행). 이 검사는 프로젝트 안의 확장 코드로 돌기 때문에,
확장 코드 자체가 원본과 같은지는 CI 에서 extensions/web/install.py --verify 로 확인합니다.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c  # noqa: E402

REQUIRED_MATCH = {"PreToolUse": {"Bash", "Edit", "Write", "MultiEdit", "NotebookEdit"},
                  "PostToolUse": {"Bash", "Edit", "Write", "MultiEdit"}}
SKIP_LINE = re.compile(r"^\s*>?\s*생략\s*:(.*)$", re.M)
LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+(.*)$", re.M)
MWG_ID = re.compile(r"\bmwg:([a-z0-9][a-z0-9-]*)")
COMMENT = re.compile(r"<!--.*?-->", re.S)


class Report:
    def __init__(self) -> None:
        self.fails: list[str] = []
        self.warns: list[str] = []

    def fail(self, where: str, msg: str) -> None:
        self.fails.append(f"{where}: {msg}")

    def warn(self, where: str, msg: str) -> None:
        self.warns.append(f"{where}: {msg}")


# ── 설치·고정 버전 (R17) ─────────────────────────────────────────────

def check_install(root: Path, cfg: dict, w: dict, rep: Report) -> None:
    check_ext_code(root, rep)
    if w["ext_version"] != c.EXT_VERSION:
        rep.fail("hold.toml", f"[web].ext_version {w['ext_version']} 과 설치된 확장 {c.EXT_VERSION} 이 다릅니다")
    if w["guard"]:
        check_settings(root, rep)

    if not w["mwg_integrity"]:
        rep.fail("hold.toml", "[web].mwg_integrity 가 비어 있습니다. 사람이 python .claude/hold-web/sync.py --pin <버전> 을 실행하세요")
        return
    lock_file = root / c.LOCK_PATH
    if not lock_file.exists():
        rep.fail(c.LOCK_PATH, "고정 버전이 설치되지 않았습니다. 사람이 python .claude/hold-web/sync.py 를 실행하세요")
        return
    try:
        lock = json.loads(lock_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        rep.fail(c.LOCK_PATH, "읽을 수 없습니다. sync.py 로 다시 만드세요")
        return
    if lock.get("mwg_version") != w["mwg_version"] or lock.get("mwg_integrity") != w["mwg_integrity"]:
        rep.fail(c.LOCK_PATH, f"설치본({lock.get('mwg_version')})이 hold.toml 의 고정 버전({w['mwg_version']})·무결성 값과 다릅니다. sync.py 를 다시 실행하세요")
    if lock.get("policy") != c.policy_inputs(w):
        rep.fail(c.LOCK_PATH, "hold.toml [web] 의 정책이 바뀌었는데 생성물에 반영되지 않았습니다. 사람이 sync.py 를 다시 실행하세요")
    for rel, h in (lock.get("files") or {}).items():
        f = root / rel
        if not f.exists():
            rep.fail(rel, "생성물이 없습니다")
        elif c.sha256(f.read_bytes()) != h:
            rep.fail(rel, "생성물이 sync.py 가 만든 내용과 다릅니다 (손으로 고쳤거나 다른 도구가 바꿈)")

    # 검증된 사본으로 생성물 전체를 다시 만들어 바이트 대조 (lock 까지 맞춘 위조도 잡는다)
    tgz, _ = c.pkg_paths(root, w)
    if not tgz.exists():
        msg = (f"검증된 MWG 사본({c.PKG_STORE}/)이 없어 재생성 대조를 못 했습니다. "
               "사람은 sync.py, CI 는 sync.py --fetch-only 를 먼저 실행하세요")
        (rep.warn if c.profile_of(cfg) == "lite" else rep.fail)("재생성 대조", msg)
    else:
        data = tgz.read_bytes()
        if c.sri(data) != w["mwg_integrity"]:
            rep.fail(c.PKG_STORE, "보관된 패키지가 hold.toml 의 mwg_integrity 와 다릅니다")
        else:
            try:
                files = c.tar_files(data)
                expected = c.render(files, w)
            except c.SyncError as e:
                rep.fail("재생성 대조", str(e))
                files, expected = {}, {}
            for rel, b in expected.items():
                f = root / rel
                if f.exists() and f.read_bytes().replace(b"\r\n", b"\n") != b.replace(b"\r\n", b"\n"):
                    rep.fail(rel, "검증된 패키지와 hold.toml 로 다시 만든 내용과 다릅니다")
            _, err = c.verify_package(root, w, lock)
            if err:
                rep.fail(c.PKG_STORE, err)

    for stray in find_mwgrc(root, w):
        rep.fail(stray, "루트가 아닌 곳의 .mwgrc 는 그 폴더에서 MWG 정책을 덮어씁니다 (R14). 지우세요 — 정책은 hold.toml [web] 에서만")
    check_precommit(root, cfg, rep)


PRECOMMIT_HOOKS = {
    "hold-web-check": "python .claude/hold-web/web_check.py",
    "hold-web-legacy-scan": "python .claude/hold-web/web_scan.py",
}


def check_precommit(root: Path, cfg: dict, rep: Report) -> None:
    pc = root / c.PRECOMMIT
    text = pc.read_text(encoding="utf-8") if pc.exists() else ""
    live = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))
    missing = [hid for hid, entry in PRECOMMIT_HOOKS.items()
               if not re.search(rf"^\s*-\s*id:\s*{re.escape(hid)}\s*$", live, re.M)
               or not re.search(rf"^\s*entry:\s*{re.escape(entry)}\s*$", live, re.M)]
    if missing:
        msg = f"pre-commit 에 {', '.join(missing)} 가 없습니다 (extensions/web/kit/templates/pre-commit-snippet.yaml)"
        (rep.warn if c.profile_of(cfg) == "lite" else rep.fail)(c.PRECOMMIT, msg)
    hook = root / ".git/hooks/pre-commit"
    if (root / ".git").is_dir() and not hook.exists():
        rep.warn(".git/hooks/pre-commit", "pre-commit 이 설치되어 있지 않습니다 (pre-commit install). 최종 방어선은 CI 입니다")


def check_ext_code(root: Path, rep: Report) -> None:
    """설치된 확장 코드가 install.py 가 기록한 매니페스트와 같은지. (원본과의 대조는 install.py --verify)"""
    mf = root / c.EXT_MANIFEST
    try:
        manifest = json.loads(mf.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        rep.fail(c.EXT_MANIFEST, "확장 코드 매니페스트가 없습니다. 사람이 extensions/web/install.py 로 다시 설치하세요")
        return
    if manifest.get("ext_version") != c.EXT_VERSION:
        rep.fail(c.EXT_MANIFEST, f"확장 코드가 web-{c.EXT_VERSION} 이 아닙니다")
    files = manifest.get("files") or {}
    present = {p.relative_to(root).as_posix() for p in (root / c.EXT_DIR).glob("*.py")} | (
        {c.GUARD} if (root / c.GUARD).exists() else set())
    for rel in sorted(present - set(files)):
        rep.fail(rel, "매니페스트에 없는 확장 코드 파일입니다")
    for rel, h in sorted(files.items()):
        f = root / rel
        if not f.exists():
            rep.fail(rel, "확장 코드 파일이 없습니다")
        elif c.sha256(f.read_bytes()) != h:
            rep.fail(rel, "확장 코드가 설치된 내용과 다릅니다 (훅·검사 로직이 바뀌었을 수 있음)")


def check_settings(root: Path, rep: Report) -> None:
    f = root / ".claude/settings.json"
    try:
        settings = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        rep.fail(".claude/settings.json", "읽을 수 없습니다")
        return
    hooks = settings.get("hooks") or {}
    for event, need in REQUIRED_MATCH.items():
        ok = False
        for entry in hooks.get(event) or []:
            cmds = [h for h in entry.get("hooks") or [] if "web_guard.py" in str(h.get("command", ""))]
            if not cmds:
                continue
            matched = set(str(entry.get("matcher", "")).split("|"))
            if need <= matched and all(int(h.get("timeout") or 60) >= c.HOOK_TIMEOUT_MIN for h in cmds):
                ok = True
        if not ok:
            rep.fail(".claude/settings.json", f"{event} 에 web_guard.py 가 ({'|'.join(sorted(need))}, timeout {c.HOOK_TIMEOUT_MIN}초 이상) 등록되어 있지 않습니다")


def find_mwgrc(root: Path, w: dict) -> list[str]:
    import os
    out = []
    skip = set(w["skip_dirs"]) - {".hold"}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip]
        if ".mwgrc" in filenames and Path(dirpath).resolve() != root:
            out.append((Path(dirpath) / ".mwgrc").relative_to(root).as_posix())
    return out


# ── 사용 환경 (R14) ──────────────────────────────────────────────────

def table_rows(text: str, heading: str | None) -> list[list[str]]:
    if heading:
        m = re.search(rf"^##\s+{re.escape(heading)}\s*$(.*?)(?=^##\s|\Z)", text, re.M | re.S)
        text = m.group(1) if m else ""
    rows = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("|") and not re.fullmatch(r"\|[\s:|-]+\|?", s):
            rows.append([x.strip() for x in s.strip("|").split("|")])
    return rows


def check_usage(root: Path, rep: Report) -> None:
    reg = root / "docs/architecture/stakeholders.md"
    usage = root / c.USAGE_PATH
    if not reg.exists():
        return
    people = [r[0] for r in table_rows(reg.read_text(encoding="utf-8"), "사람·조직") if re.fullmatch(r"SH-[A-Z]\d+", r[0])]
    if not usage.exists():
        rep.fail(c.USAGE_PATH, "사용 환경 정의가 없습니다 (R14). extensions/web/install.py 가 만든 양식을 사람이 채우세요")
        return
    rows = {r[0]: r for r in table_rows(usage.read_text(encoding="utf-8"), None) if re.fullmatch(r"SH-[A-Z]\d+", r[0])}
    real = 0
    for pid in people:
        r = rows.get(pid)
        val = r[1] if r and len(r) > 1 else ""
        if not val or "<" in val or ">" in val:
            rep.fail(c.USAGE_PATH, f"{pid} 의 사용 환경이 비었거나 양식 그대로입니다 (R14)")
        elif val != "해당 없음":
            real += 1
    for extra in sorted(set(rows) - set(people)):
        rep.fail(c.USAGE_PATH, f"{extra} 는 이해관계자 정의서의 사람·조직에 없는 ID 입니다")
    if people and real == 0:
        rep.fail(c.USAGE_PATH, "웹 UI 를 쓰는 사람이 한 명도 없습니다. 모두 '해당 없음'이면 웹 확장을 끄세요")


# ── 참조 가이드 (R16) ────────────────────────────────────────────────

def sections(text: str, title: str) -> list[str]:
    parts = re.split(r"^##\s+(.+?)\s*$", text, flags=re.M)
    return [parts[i + 1] for i in range(1, len(parts) - 1, 2) if parts[i].strip() == title]


def check_refs(body: str, known: set[str], where: str, rep: Report) -> None:
    body = COMMENT.sub("", body)
    ids = MWG_ID.findall(body)
    skips = [s.strip() for s in SKIP_LINE.findall(body)]
    for item in LIST_ITEM.findall(body):
        if "mwg:" not in item:
            rep.fail(where, f"'## 참조 가이드'의 목록 항목은 mwg:<id> 로 시작해야 합니다: {item[:60]!r} (R16)")
    if ids and skips:
        rep.fail(where, "'## 참조 가이드'에 가이드 ID 와 '생략:'이 함께 있습니다 (R16)")
    if not ids and not skips:
        rep.fail(where, "'## 참조 가이드'에 mwg:<id> 도 '생략: 이유'도 없습니다 (R16)")
    for s in skips:
        if len(s) < 4 or "<" in s or ">" in s:
            rep.fail(where, f"'생략:'의 이유가 비었거나 양식 그대로입니다: {s!r} (R16)")
    if ids and not known:
        rep.fail(where, "고정 버전 가이드 목록이 없어 ID 를 대조할 수 없습니다. 사람이 sync.py 를 실행하세요")
    for gid in sorted(set(ids) - known if known else set()):
        rep.fail(where, f"mwg:{gid} 는 고정 버전 가이드 목록에 없는 ID 입니다. search 결과의 id 를 그대로 적으세요 (R16)")


def git_added_date(root: Path, cdir: Path) -> str | None:
    """변경 폴더가 Git 에 처음 들어온 날짜 (YYYYMMDD). Git 밖이거나 아직 커밋 전이면 None."""
    import subprocess
    try:
        res = subprocess.run(["git", "log", "--diff-filter=A", "--format=%ad", "--date=format:%Y%m%d", "--", str(cdir)],
                             cwd=root, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    dates = [d for d in res.stdout.split() if re.fullmatch(r"\d{8}", d)]
    return min(dates) if res.returncode == 0 and dates else None


def check_change(root: Path, cdir: Path, w: dict, known: set[str], rep: Report) -> None:
    rel = cdir.relative_to(root).as_posix()
    m = re.match(r"(\d{8})-", cdir.name)
    if not m:
        rep.fail(rel, "변경 폴더 이름은 YYYYMMDD-이름 형식이어야 합니다 (웹 확장 R16 적용 판단에 씁니다)")
        return
    if w["since"] and m.group(1) < w["since"]:
        # 이름의 날짜가 이르더라도, Git 에 들어온 날짜가 없거나(새 폴더) since 이후면 검사한다 (이름만 바꿔 피하지 못하게)
        added = git_added_date(root, cdir)
        if added is not None and added < w["since"]:
            return  # 확장을 켜기 전의 변경
    spec = cdir / "spec.md"
    if spec.exists():
        secs = sections(spec.read_text(encoding="utf-8"), "참조 가이드")
        if not secs:
            rep.fail(f"{rel}/spec.md", "'## 참조 가이드' 절이 없습니다 (R16)")
        elif len(secs) > 1:
            rep.fail(f"{rel}/spec.md", "'## 참조 가이드' 절이 여러 개입니다 (R16)")
        else:
            check_refs(secs[0], known, f"{rel}/spec.md", rep)
    plan = cdir / "plan.md"
    if plan.exists():
        secs = sections(plan.read_text(encoding="utf-8"), "참조 가이드")
        if len(secs) > 1:
            rep.fail(f"{rel}/plan.md", "'## 참조 가이드' 절이 여러 개입니다 (R16)")
        for s in secs[:1]:
            check_refs(s, known, f"{rel}/plan.md", rep)


def check_changes(root: Path, cfg: dict, w: dict, rep: Report, only: Path | None = None) -> None:
    changes = root / (cfg.get("paths", {}).get("changes") or "changes")
    if not changes.exists():
        return
    known = c.known_guides(root)
    dirs = [only] if only else sorted(d for d in changes.iterdir() if d.is_dir() and not d.name.startswith("_"))
    for d in dirs:
        check_change(root, d, w, known, rep)


# ── 실행 ─────────────────────────────────────────────────────────────

def run(root: Path) -> tuple[Report, bool]:
    cfg = c.load_toml(root)
    w, errors = c.web_config(cfg)
    rep = Report()
    for e in errors:
        rep.fail("hold.toml", e)
    if not w["enabled"]:
        # 설치된 확장을 조용히 끄지 못하게 (tripwire): 끄려면 사람이 이유를 적는다
        if (root / c.LOCK_PATH).exists() and not w["disabled_reason"].strip():
            rep.fail("hold.toml", "웹 확장이 설치되어 있는데 꺼져 있습니다. 끈 것이 맞다면 사람이 [web].disabled_reason 에 이유를 적으세요")
        return rep, False
    check_install(root, cfg, w, rep)
    check_usage(root, rep)
    check_changes(root, cfg, w, rep)
    return rep, True


def metrics(root: Path) -> dict:
    f = root / c.HOOK_LOG
    out = {"retrieve_confirmed": 0, "retrieve_unconfirmed": 0, "scan_fail": 0, "scan_pass": 0, "scan_skip": 0,
           "scan_error": 0, "guard_block": 0, "guides_confirmed": set()}
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("hook") == "web_guidance":
                out["retrieve_confirmed"] += len(r.get("confirmed", []))
                out["retrieve_unconfirmed"] += len(set(r.get("requested", [])) - set(r.get("confirmed", [])))
                out["guides_confirmed"].update(r.get("confirmed", []))
            elif r.get("hook") == "web_scan":
                k = f"scan_{r.get('verdict')}"
                if k in out:
                    out[k] += 1
            elif r.get("hook") == "web_guard":
                out["guard_block"] += 1
    out["guides_confirmed"] = sorted(out["guides_confirmed"])
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="HOLD 웹 확장 검사")
    ap.add_argument("--root", type=Path, default=c.project_root())
    ap.add_argument("--metrics", action="store_true", help="훅 로그 집계만 출력")
    args = ap.parse_args(argv)
    root = args.root.resolve()
    if args.metrics:
        print(json.dumps(metrics(root), ensure_ascii=False, indent=1))
        return 0
    rep, enabled = run(root)
    for w in rep.warns:
        print("WARN " + w)
    for f in rep.fails:
        print("FAIL " + f)
    if not rep.fails:
        print("OK  웹 확장 검사 통과" if enabled else "OK  웹 확장이 꺼져 있습니다")
    return 1 if rep.fails else 0


if __name__ == "__main__":
    sys.exit(main())
