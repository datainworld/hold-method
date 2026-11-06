"""hold-kit 테스트 공용 픽스처: 임시 폴더에 키트를 설치한 프로젝트."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
KIT = REPO / "kit"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    subprocess.run([sys.executable, str(KIT / "scripts/hold_init.py"), "--target", str(root)],
                   check=True, capture_output=True, text=True)
    return root


def run_hook(root: Path, hook: str, payload: dict) -> subprocess.CompletedProcess:
    """설치된 훅을 Claude Code 처럼 호출한다 (stdin JSON, CLAUDE_PROJECT_DIR)."""
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(root)}
    return subprocess.run([sys.executable, str(root / ".claude/hooks" / hook)], input=json.dumps(payload),
                          capture_output=True, text=True, cwd=root, env=env)


def run_script(root: Path, script: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(root / "scripts" / script), "--root", str(root), *args],
                          capture_output=True, text=True, cwd=root)


def write(root: Path, rel: str, text: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p
