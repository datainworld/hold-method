#!/usr/bin/env python3
"""HOLD 수정 직후 검사 훅 (PostToolUse) — 규칙 R02·R03·R05·R06.

에이전트가 파일을 고친 직후, 고친 파일의 종류에 맞는 검사를 돌리고
실패하면 그 결과를 에이전트에게 돌려줍니다 (종료 코드 2).

- changes/**/*.md, 이해관계자 정의서, 컨텍스트 뷰 → scripts/check_views.py (해당 변경만)
- *.py → lint-imports (.importlinter 가 있을 때), pyright <파일> (설치되어 있을 때)
검사 도구가 설치되어 있지 않으면 건너뜁니다 (훅이 작업을 막지 않게).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    tomllib = None  # type: ignore[assignment]


def project_root() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()).resolve()


def load_config(root: Path) -> dict:
    f = root / "hold.toml"
    if tomllib is None or not f.exists():
        return {}
    with f.open("rb") as fh:
        return tomllib.load(fh)


def rel_path(raw: str, root: Path) -> Path | None:
    p = Path(raw.replace("\\", "/"))
    if not p.is_absolute():
        p = root / p
    try:
        return p.resolve().relative_to(root)
    except ValueError:
        return None


def log(root: Path, cfg: dict, record: dict) -> None:
    rel = cfg.get("paths", {}).get("hook_log", ".hold/logs/hooks.jsonl")
    try:
        f = root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        with f.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), **record}, ensure_ascii=False) + "\n")
    except OSError:
        pass


def run_tool(cmd: list[str], root: Path) -> str | None:
    """실패하면 출력의 앞부분을, 성공하면 None 을 돌려준다."""
    res = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
    if res.returncode == 0:
        return None
    out = (res.stdout + res.stderr).strip().splitlines()
    return f"$ {' '.join(cmd)}\n" + "\n".join(out[:30])


def checks_for(rel: Path, root: Path, cfg: dict) -> list[str]:
    paths = cfg.get("paths", {})
    changes = Path(paths.get("changes", "changes"))
    docs = {Path(paths.get("stakeholders", "docs/architecture/stakeholders.md")),
            Path(paths.get("context_view", "docs/architecture/views/context.md"))}
    failures: list[str] = []

    if rel.suffix == ".md" and (rel.parts[:1] == changes.parts[:1] or rel in docs):
        sys.path.insert(0, str(root / "scripts"))
        import check_views  # noqa: E402 — 키트가 설치한 scripts/check_views.py

        only = None
        if rel.parts[: len(changes.parts)] == changes.parts and len(rel.parts) > len(changes.parts) + 1:
            only = [root / changes / rel.parts[len(changes.parts)]]
        report = check_views.run(root, only)
        failures += report.failures

    if rel.suffix == ".py":
        if (root / ".importlinter").exists() and shutil.which("lint-imports"):
            r = run_tool(["lint-imports"], root)
            if r:
                failures.append("모듈 경계 위반 (R02):\n" + r)
        if shutil.which("pyright"):
            r = run_tool(["pyright", str(rel)], root)
            if r:
                failures.append("타입 검사 실패 (R03):\n" + r)
    return failures


def main() -> int:
    root = project_root()
    cfg = load_config(root)
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    raw = (data.get("tool_input") or {}).get("file_path") or ""
    rel = rel_path(raw, root) if raw else None
    if rel is None:
        return 0
    failures = checks_for(rel, root, cfg)
    if failures:
        log(root, cfg, {"hook": "post_edit", "verdict": "fail", "file": rel.as_posix(), "count": len(failures)})
        print("HOLD 검사가 실패했습니다. 아래를 고친 뒤 계속하세요.\n\n" + "\n\n".join(failures), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
