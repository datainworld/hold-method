#!/usr/bin/env python3
"""HOLD 웹 확장 web-0.1 설치·업그레이드 (사람이 실행).

코어 키트(kit/scripts/hold_init.py)로 이미 설치된 프로젝트에 확장을 더합니다. 새 프로젝트든,
실증 중인 v0.1 프로젝트든 같은 절차입니다. 코어 키트가 설치한 파일은 바꾸지 않고, 프로젝트 쪽에
확장 파일을 더하고 몇몇 프로젝트 파일에 절을 덧붙입니다.

    python extensions/web/install.py --target ../my-app

하는 일
  .claude/hooks/web_guard.py, .claude/hold-web/*      확장 코드 (항상 이 판으로 덮어씀, 보호 경로)
  .claude/settings.json                               web_guard 훅 등록을 덧붙임 (코어 훅 항목은 그대로)
  hold.toml                                           [web] 표가 없으면 끝에 덧붙임
  CLAUDE.md, changes/_template/spec.md                hold-web 표식 사이의 절을 덧붙이거나 바꿈
  docs/architecture/usage-environments.md             없으면 정의서의 사람 ID 로 양식 생성 (사람이 채움)
  docs/hold/web-measurement.csv                       없으면 생성
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
KIT = HERE / "kit"
sys.path.insert(0, str(KIT / "hold-web"))
import common as c  # noqa: E402

MARK = re.compile(r"<!-- hold-web:start.*?<!-- hold-web:end -->\n?", re.S)
HOOK_CMD = "python .claude/hooks/web_guard.py"
HOOK_ENTRIES = {
    "PreToolUse": "Bash|Edit|Write|MultiEdit|NotebookEdit",
    "PostToolUse": "Bash|Edit|Write|MultiEdit",
}


def put_block(path: Path, block: str, done: list[str]) -> None:
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    new = MARK.sub(block, text, count=1) if MARK.search(text) else text.rstrip("\n") + "\n\n" + block
    if new != text:
        path.write_text(new, encoding="utf-8")
        done.append(path.name if path.name != "spec.md" else "changes/_template/spec.md")


def merge_settings(root: Path, done: list[str]) -> None:
    f = root / ".claude/settings.json"
    settings = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    hooks = settings.setdefault("hooks", {})
    changed = False
    for event, matcher in HOOK_ENTRIES.items():
        entries = hooks.setdefault(event, [])
        mine = [e for e in entries if any("web_guard.py" in str(h.get("command", "")) for h in e.get("hooks") or [])]
        want = {"matcher": matcher, "hooks": [{"type": "command", "command": HOOK_CMD, "timeout": c.HOOK_TIMEOUT_MIN}]}
        if mine != [want]:
            entries[:] = [e for e in entries if e not in mine] + [want]
            changed = True
    if changed:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        done.append(".claude/settings.json (web_guard 등록)")


def usage_template(root: Path) -> str:
    sys.path.insert(0, str(KIT / "hold-web"))
    import web_check
    reg = root / "docs/architecture/stakeholders.md"
    rows = []
    if reg.exists():
        for r in web_check.table_rows(reg.read_text(encoding="utf-8"), "사람·조직"):
            if re.fullmatch(r"SH-[A-Z]\d+", r[0]):
                name = r[1] if len(r) > 1 else ""
                rows.append(f"| {r[0]} | <사용 환경 — 예: 기관 내부망, 관리형 Edge 최신 / 시민, 모바일 Safari·삼성 인터넷> | {name} |")
    if not rows:
        rows.append("| SH-U01 | <사용 환경> | <이름> |")
    return (
        "# 사용 환경 (HOLD 웹 확장 web-0.1, R14)\n\n"
        "사람 소유 파일 (웹 확장이 보호). 이해관계자 정의서의 **사람·조직** 행마다, 그 사람이 시스템을 쓰는 기기·브라우저·망을 적습니다.\n"
        "웹 UI 를 쓰지 않는 사람은 \"해당 없음\". `hold.toml`의 `[web].baseline`(지원 기준)은 이 표에서 정합니다.\n\n"
        "| ID | 사용 환경 | 이름 (참고) |\n|---|---|---|\n" + "\n".join(rows) + "\n"
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="HOLD 웹 확장 web-0.1 설치 (사람이 실행)")
    ap.add_argument("--target", type=Path, required=True)
    ap.add_argument("--since", default=dt.date.today().strftime("%Y%m%d"), help="R16 을 적용할 변경의 시작 날짜 YYYYMMDD")
    args = ap.parse_args(argv)
    if "CLAUDECODE" in os.environ:
        print("이 스크립트는 사람이 실행합니다 (HOLD R17).", file=sys.stderr)
        return 1
    root = args.target.resolve()
    if not (root / "hold.toml").exists():
        print("hold.toml 이 없습니다. 먼저 코어 키트를 설치하세요: python kit/scripts/hold_init.py --target …", file=sys.stderr)
        return 1
    done: list[str] = []

    # 확장 코드 (확장이 소유 — 항상 이 판으로)
    (root / ".claude/hooks").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(KIT / "hooks/web_guard.py", root / ".claude/hooks/web_guard.py")
    dst = root / ".claude/hold-web"
    dst.mkdir(parents=True, exist_ok=True)
    for f in (KIT / "hold-web").glob("*.py"):
        shutil.copyfile(f, dst / f.name)
    (dst / "VERSION").write_text(c.EXT_VERSION + "\n", encoding="utf-8")
    done.append(".claude/hooks/web_guard.py, .claude/hold-web/")

    # hold.toml [web]
    if "web" not in c.load_toml(root):
        block = (KIT / "templates/hold-web.toml").read_text(encoding="utf-8").replace("{since}", args.since)
        with (root / "hold.toml").open("a", encoding="utf-8") as fh:
            fh.write(block)
        done.append("hold.toml [web]")

    merge_settings(root, done)
    put_block(root / "CLAUDE.md", (KIT / "templates/claude-md.md").read_text(encoding="utf-8"), done)
    put_block(root / "changes/_template/spec.md", (KIT / "templates/spec-section.md").read_text(encoding="utf-8"), done)

    usage = root / c.USAGE_PATH
    if not usage.exists():
        usage.parent.mkdir(parents=True, exist_ok=True)
        usage.write_text(usage_template(root), encoding="utf-8")
        done.append(c.USAGE_PATH)
    meas = root / "docs/hold/web-measurement.csv"
    if not meas.exists():
        meas.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(KIT / "templates/web-measurement.csv", meas)
        done.append("docs/hold/web-measurement.csv")

    print(f"HOLD 웹 확장 web-{c.EXT_VERSION} 을 설치했습니다:")
    for d in done:
        print(f"  - {d}")
    print(
        "\n사람이 할 일\n"
        f"  1. {c.USAGE_PATH} 의 사용 환경을 채우고, hold.toml [web] 의 baseline·fallback_policy 를 정한다\n"
        "  2. python .claude/hold-web/sync.py --pin 1.0.0     # MWG 고정 (Node.js 22+, npm)\n"
        "  3. .pre-commit-config.yaml 에 extensions/web/kit/templates/pre-commit-snippet.yaml 을 붙인다 (Standard 이상 필수)\n"
        "  4. python .claude/hold-web/web_check.py 가 통과하면 커밋하고 Claude Code 를 다시 시작한다\n"
        "  5. 실증 중인 프로젝트라면 이 설치를 changes/ 의 intent 로 남긴다 (extensions/README.md)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
