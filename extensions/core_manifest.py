#!/usr/bin/env python3
"""HOLD 코어 동결 매니페스트 — 확장 규약 조건 3("확장은 코어 파일을 바꾸지 않는다")의 기계 증명.

코어 = method/ (본문·부록), kit/, tests/, examples/, method-adr/0001-*.md
동결 시점의 코어 파일 목록과 내용 해시를 extensions/core-v0.1.sha256 에 적어 두고,
지금의 코어가 그와 같은지 검사합니다. 줄바꿈(CRLF/LF)은 같게 취급합니다 (Windows 체크아웃 대비).

사용법:
  python extensions/core_manifest.py --check     # 다르면 종료 코드 1 과 차이 목록
  python extensions/core_manifest.py --write     # 매니페스트 다시 쓰기 — 코어 판을 올릴 때만, 사람이, ADR 과 함께
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MANIFEST = REPO / "extensions" / "core-v0.1.sha256"
CORE_DIRS = ["method", "kit", "tests", "examples"]
CORE_GLOBS = ["method-adr/0001-*.md"]
SKIP_PARTS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}


def core_files(repo: Path = REPO) -> list[Path]:
    files: set[Path] = set()
    for d in CORE_DIRS:
        for p in (repo / d).rglob("*"):
            if p.is_file() and not SKIP_PARTS.intersection(p.relative_to(repo).parts) and p.suffix != ".pyc":
                files.add(p)
    for g in CORE_GLOBS:
        files.update(p for p in repo.glob(g) if p.is_file())
    return sorted(files)


def digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def current(repo: Path = REPO) -> dict[str, str]:
    return {p.relative_to(repo).as_posix(): digest(p) for p in core_files(repo)}


def recorded(manifest: Path = MANIFEST) -> dict[str, str]:
    out = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            h, path = line.split(None, 1)
            out[path.strip()] = h
    return out


def diff(repo: Path = REPO, manifest: Path = MANIFEST) -> list[str]:
    want, have = recorded(manifest), current(repo)
    problems = [f"바뀜: {p}" for p in sorted(want.keys() & have.keys()) if want[p] != have[p]]
    problems += [f"없어짐: {p}" for p in sorted(want.keys() - have.keys())]
    problems += [f"추가됨: {p}" for p in sorted(have.keys() - want.keys())]
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="HOLD 코어 동결 매니페스트")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)
    if args.write:
        lines = ["# HOLD 코어 v0.1 동결 매니페스트 (sha256, 줄바꿈 LF 정규화). 코어 판을 올릴 때만 사람이 다시 씁니다."]
        lines += [f"{h}  {p}" for p, h in current().items()]
        MANIFEST.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"매니페스트를 썼습니다: {len(lines) - 1}개 파일")
        return 0
    problems = diff()
    for p in problems:
        print("FAIL " + p)
    if not problems:
        print(f"OK  코어 v0.1 파일 {len(recorded())}개가 동결 시점과 같습니다")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
