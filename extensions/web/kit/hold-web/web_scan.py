#!/usr/bin/env python3
"""HOLD 웹 확장 web-0.1 — 레거시 패턴 검사 명령 (R15, pre-commit: hold-web-legacy-scan).

  python .claude/hold-web/web_scan.py [파일 …]    # 생략하면 프로젝트의 프런트엔드 파일 전체
종료 코드: block 모드에서 검출·검사 오류가 있으면 1, Regulated 에서 검사를 못 하면 1, 그 밖에는 0.
대상 파일은 임시 폴더에 복사해 검사하므로 .gitignore 나 파일 이름의 영향을 받지 않습니다.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="HOLD 웹 확장 레거시 패턴 검사 (R15)")
    ap.add_argument("files", nargs="*")
    ap.add_argument("--root", type=Path, default=c.project_root())
    ap.add_argument("--profile", choices=["lite", "standard", "regulated"])
    args = ap.parse_args(argv)
    root = args.root.resolve()
    cfg = c.load_toml(root)
    w, errors = c.web_config(cfg)
    if errors:
        print("FAIL hold.toml [web] 설정 오류:\n- " + "\n- ".join(errors))
        return 1
    profile = args.profile or c.profile_of(cfg)
    mode = c.scan_mode(w, profile)
    if mode == "off":
        print("OK  웹 확장이 꺼져 있거나 legacy_scan = off 입니다")
        return 0
    rels = [r for r in (c.rel_posix(root, f) for f in args.files) if r] if args.files else list(c.frontend_snapshot(root, w))
    res = c.scan(root, w, rels)
    if res.skipped:
        print(("FAIL " if profile == "regulated" else "WARN ") + res.skipped)
        return 1 if profile == "regulated" else 0
    if res.error:
        print(("FAIL " if mode == "block" else "WARN ") + res.error)
        return 1 if mode == "block" else 0
    if res.allowed:
        print(f"INFO 허용 목록으로 제외한 검출 {len(res.allowed)}건")
    if not res.findings:
        print(f"OK  레거시 웹 패턴 검사 통과 ({len(rels)}개 파일)")
        return 0
    print(c.format_findings(res.findings, w))
    return 1 if mode == "block" else 0


if __name__ == "__main__":
    sys.exit(main())
