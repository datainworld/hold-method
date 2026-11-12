#!/usr/bin/env python3
"""HOLD 웹 확장 web-0.1 검사 — 설치·고정 버전(R17), 사용 환경(R14), 참조 가이드(R16).

  python .claude/hold-web/web_check.py              # 전체 검사 (pre-commit: hold-web-check)
  python .claude/hold-web/web_check.py --metrics    # 훅 로그 집계 (측정)
종료 코드: 0 통과(또는 확장 꺼짐), 1 실패.

설치·고정 검사는 npm 캐시에 고정 버전 패키지가 있으면 그것으로 생성물을 다시 만들어 바이트 단위로 대조합니다.
캐시가 없으면 lock.json 의 해시로만 대조하고 경고합니다.
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

def check_install(root: Path, cfg: dict, w: dict, rep: Report, regen: bool = True) -> None:
    ver_file = root / ".claude/hold-web/VERSION"
    if not ver_file.exists() or ver_file.read_text(encoding="utf-8").strip() != c.EXT_VERSION:
        rep.fail(".claude/hold-web/VERSION", f"확장 코드가 web-{c.EXT_VERSION} 이 아닙니다. 사람이 extensions/web/install.py 로 다시 설치하세요")
    if w["ext_version"] != c.EXT_VERSION:
        rep.fail("hold.toml", f"[web].ext_version {w['ext_version']} 과 설치된 확장 {c.EXT_VERSION} 이 다릅니다")
    if not (root / ".claude/hooks/web_guard.py").exists():
        rep.fail(".claude/hooks/web_guard.py", "웹 확장 훅이 없습니다")
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

    if regen:
        data = c.obtain_tarball(w, None, offline_only=True)
        if data is None:
            rep.warn("재생성 대조", "npm 캐시에 고정 버전 패키지가 없어 lock.json 해시로만 대조했습니다")
        elif c.sri(data) != w["mwg_integrity"]:
            rep.fail("재생성 대조", "npm 캐시의 패키지가 hold.toml 의 mwg_integrity 와 다릅니다 (캐시 오염 또는 버전 혼동)")
        else:
            try:
                expected = c.render(c.read_tarball(data), w)
            except c.SyncError as e:
                rep.fail("재생성 대조", str(e))
                expected = {}
            for rel, b in expected.items():
                f = root / rel
                if f.exists() and f.read_bytes().replace(b"\r\n", b"\n") != b.replace(b"\r\n", b"\n"):
                    rep.fail(rel, "고정 패키지와 hold.toml 로 다시 만든 내용과 다릅니다")

    for stray in find_mwgrc(root, w):
        rep.fail(stray, "루트가 아닌 곳의 .mwgrc 는 그 폴더에서 MWG 정책을 덮어씁니다 (R14). 지우세요 — 정책은 hold.toml [web] 에서만")
    pc = root / ".pre-commit-config.yaml"
    if not pc.exists() or "hold-web-check" not in pc.read_text(encoding="utf-8"):
        msg = "pre-commit 에 hold-web-check 가 없습니다 (extensions/web/kit/templates/pre-commit-snippet.yaml)"
        (rep.warn if c.profile_of(cfg) == "lite" else rep.fail)(".pre-commit-config.yaml", msg)


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


def check_change(root: Path, cdir: Path, w: dict, known: set[str], rep: Report) -> None:
    m = re.match(r"(\d{8})", cdir.name)
    if not m or (w["since"] and m.group(1) < w["since"]):
        return  # 확장을 켜기 전의 변경
    rel = cdir.relative_to(root).as_posix()
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

def run(root: Path, regen: bool = True) -> tuple[Report, bool]:
    cfg = c.load_toml(root)
    w, errors = c.web_config(cfg)
    rep = Report()
    for e in errors:
        rep.fail("hold.toml", e)
    if not w["enabled"]:
        return rep, False
    check_install(root, cfg, w, rep, regen)
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
    ap.add_argument("--no-regen", action="store_true", help="npm 캐시로 다시 만들어 대조하는 단계를 건너뜀")
    args = ap.parse_args(argv)
    root = args.root.resolve()
    if args.metrics:
        print(json.dumps(metrics(root), ensure_ascii=False, indent=1))
        return 0
    rep, enabled = run(root, regen=not args.no_regen)
    for w in rep.warns:
        print("WARN " + w)
    for f in rep.fails:
        print("FAIL " + f)
    if not rep.fails:
        print("OK  웹 확장 검사 통과" if enabled else "OK  웹 확장이 꺼져 있습니다")
    return 1 if rep.fails else 0


if __name__ == "__main__":
    sys.exit(main())
