#!/usr/bin/env python3
"""HOLD 키트 설치 — 새 프로젝트(또는 기존 프로젝트)에 hold-kit 을 깝니다.

    python kit/scripts/hold_init.py --target ../my-project --profile lite

이미 있는 파일은 덮어쓰지 않습니다 (--force 로 덮어쓰기). .claude/settings.json 이 이미 있으면
.claude/settings.hold.json 으로 따로 쓰고, 합치는 방법을 안내합니다.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent  # hold-method/kit

# (키트 안 원본, 프로젝트 안 위치)
COPIES = [
    ("hooks/protect_paths.py", ".claude/hooks/protect_paths.py"),
    ("hooks/post_edit.py", ".claude/hooks/post_edit.py"),
    ("scripts/check_views.py", "scripts/check_views.py"),
    ("scripts/gen_views.py", "scripts/gen_views.py"),
    ("skills/hold-intent/SKILL.md", ".claude/skills/hold-intent/SKILL.md"),
    ("skills/hold-architecture/SKILL.md", ".claude/skills/hold-architecture/SKILL.md"),
    ("skills/hold-views/SKILL.md", ".claude/skills/hold-views/SKILL.md"),
    ("templates/CLAUDE.md", "CLAUDE.md"),
    ("templates/stakeholders.md", "docs/architecture/stakeholders.md"),
    ("templates/context.md", "docs/architecture/views/context.md"),
    ("templates/module-map.md", "docs/architecture/module-map.md"),
    ("templates/change/intent.md", "changes/_template/intent.md"),
    ("templates/change/spec.md", "changes/_template/spec.md"),
    ("templates/change/plan.md", "changes/_template/plan.md"),
    ("templates/module-CLAUDE.md", "docs/hold/templates/module-CLAUDE.md"),
    ("templates/friction.md", "docs/hold/friction/_template.md"),
    ("templates/measurement.csv", "docs/hold/measurement.csv"),
    ("templates/importlinter.example", ".importlinter"),
    ("templates/pre-commit-config.yaml", ".pre-commit-config.yaml"),
]
EMPTY_DIRS = ["docs/adr", "docs/issues", "docs/architecture/views/generated", "tests/contracts", "tests/golden", "tests/evals"]
GITIGNORE_LINES = [".env", ".env.*", ".venv/", "__pycache__/", ".hold/logs/"]


def write(dst: Path, text: str | None, src: Path | None, force: bool, done: list[str], skipped: list[str], root: Path) -> None:
    rel = dst.relative_to(root).as_posix()
    if dst.exists() and not force:
        skipped.append(rel)
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if text is not None:
        dst.write_text(text, encoding="utf-8")
    else:
        shutil.copyfile(src, dst)  # type: ignore[arg-type]
    done.append(rel)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="HOLD 키트 설치")
    ap.add_argument("--target", type=Path, required=True, help="설치할 프로젝트 폴더")
    ap.add_argument("--profile", choices=["lite", "standard", "regulated"], default="lite")
    ap.add_argument("--force", action="store_true", help="이미 있는 파일도 덮어쓴다")
    args = ap.parse_args(argv)

    root = args.target.resolve()
    root.mkdir(parents=True, exist_ok=True)
    done: list[str] = []
    skipped: list[str] = []

    # hold.toml — 프로필을 채워서
    toml = (KIT / "templates/hold.toml").read_text(encoding="utf-8")
    toml = re.sub(r'profile = "\w+"', f'profile = "{args.profile}"', toml, count=1)
    write(root / "hold.toml", toml, None, args.force, done, skipped, root)

    for src, dst in COPIES:
        write(root / dst, None, KIT / src, args.force, done, skipped, root)

    # .claude/settings.json — 이미 있으면 따로 쓴다
    settings_src = KIT / "settings/settings.json"
    settings_dst = root / ".claude/settings.json"
    if settings_dst.exists() and not args.force:
        write(root / ".claude/settings.hold.json", None, settings_src, True, done, skipped, root)
        merge_note = "기존 .claude/settings.json 이 있어 .claude/settings.hold.json 으로 썼습니다. hooks·permissions 항목을 직접 합치세요."
    else:
        write(settings_dst, None, settings_src, True, done, skipped, root)
        merge_note = ""

    for d in EMPTY_DIRS:
        p = root / d
        p.mkdir(parents=True, exist_ok=True)
        keep = p / ".gitkeep"
        if not any(p.iterdir()):
            keep.touch()

    gi = root / ".gitignore"
    existing = gi.read_text(encoding="utf-8").splitlines() if gi.exists() else []
    add = [line for line in GITIGNORE_LINES if line not in existing]
    if add:
        with gi.open("a", encoding="utf-8") as fh:
            if existing and existing[-1].strip():
                fh.write("\n")
            fh.write("# HOLD\n" + "\n".join(add) + "\n")
        done.append(".gitignore (+" + ", ".join(add) + ")")

    print(f"HOLD v0.1 키트를 설치했습니다: {root} (profile={args.profile})")
    print(f"  새로 쓴 파일 {len(done)}개, 이미 있어 건너뛴 파일 {len(skipped)}개")
    for s in skipped:
        print(f"  - 건너뜀: {s}")
    if merge_note:
        print("  ! " + merge_note)
    print(
        "\n다음 할 일 (Stage 0)\n"
        "  1. docs/architecture/stakeholders.md 에 사람과 연관 시스템을 적는다\n"
        "  2. docs/architecture/views/context.md 에 컨텍스트 뷰를 그린다\n"
        "  3. .importlinter 의 모듈 이름을 프로젝트에 맞게 고친다\n"
        "  4. python scripts/check_views.py 가 통과하면 커밋한다"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
