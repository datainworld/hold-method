#!/usr/bin/env python3
"""HOLD 보호 경로 훅 (PreToolUse) — 원칙 H1 "사람의 역할", 규칙 R01·R04·R10.

사람이 소유한 경로(계약, 채점 기준, 이해관계자 정의서, 설정)를 에이전트가 고치려 하면
도구 실행 전에 막고, 이유와 할 일을 에이전트에게 돌려줍니다.

- 파일 도구(Edit, Write, MultiEdit, NotebookEdit): 대상 경로로 판정 (정확)
- Bash: 보호 경로와 쓰기형 명령이 함께 보이면 차단 (휴리스틱, 우회 가능 — v0.1 한계)

종료 코드 0 = 허용, 2 = 차단 (stderr 메시지가 에이전트에게 전달됨).
보호 경로 목록은 hold.toml 의 [protect].paths 에서 읽습니다.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    tomllib = None  # type: ignore[assignment]

DEFAULT_PROTECTED = [
    "app/contracts/",
    "tests/contracts/",
    "tests/golden/",
    "tests/evals/",
    "docs/architecture/stakeholders.md",
    "hold.toml",
    ".importlinter",
    ".claude/",
]
FILE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
# Bash 명령 중 파일을 바꿀 수 있는 명령어 (휴리스틱)
WRITE_WORDS = re.compile(
    r"(\btee\b|\bsed\s+-i|\brm\b|\bmv\b|\bcp\b|\btruncate\b|\bchmod\b|"
    r"\bgit\s+(checkout|restore|rm|mv)\b|\bperl\s+-pi|\bdd\b|\bSet-Content\b|\bOut-File\b)"
)
# 리다이렉션 대상 (2>&1, >/dev/null 같은 무해한 형태는 제외)
REDIRECT_TARGET = re.compile(r"(?<![0-9&])>>?\s*([^\s<>;&|]+)")
SEGMENT_SPLIT = re.compile(r"&&|\|\||;|\|")

MESSAGE = (
    "{path} 는 사람이 소유한 파일입니다 (HOLD H1). 수정하지 마세요.\n"
    "변경이 필요하면 작업을 멈추고, 무엇을 왜 바꿔야 하는지와 선택지를 사람에게 보고하세요.\n"
    "계약이나 채점 기준이 원인이라면 changes/ 아래에 intent.md 초안을 제안하는 것도 방법입니다."
)


def project_root() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()).resolve()


def load_config(root: Path) -> dict:
    cfg_file = root / "hold.toml"
    if tomllib is None or not cfg_file.exists():
        return {}
    with cfg_file.open("rb") as fh:
        return tomllib.load(fh)


def protected_paths(cfg: dict) -> list[str]:
    paths = cfg.get("protect", {}).get("paths") or DEFAULT_PROTECTED
    return [p.replace("\\", "/") for p in paths]


def to_relative(raw: str, root: Path) -> str:
    raw = raw.replace("\\", "/")
    p = Path(raw)
    if p.is_absolute():
        try:
            return p.resolve().relative_to(root).as_posix()
        except ValueError:
            return p.as_posix()  # 프로젝트 밖 경로: 보호 대상 아님
    return Path(os.path.normpath(raw)).as_posix()


def is_protected(rel: str, protected: list[str]) -> str | None:
    for p in protected:
        if p.endswith("/"):
            if rel == p.rstrip("/") or rel.startswith(p):
                return p
        elif rel == p:
            return p
    return None


def log(root: Path, cfg: dict, record: dict) -> None:
    rel = cfg.get("paths", {}).get("hook_log", ".hold/logs/hooks.jsonl")
    try:
        f = root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        with f.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), **record}, ensure_ascii=False) + "\n")
    except OSError:
        pass  # 로그 실패는 판정에 영향을 주지 않음


def check(data: dict, root: Path, cfg: dict) -> tuple[bool, str]:
    """(허용 여부, 메시지)를 돌려준다."""
    tool = data.get("tool_name", "")
    tool_input = data.get("tool_input") or {}
    protected = protected_paths(cfg)

    if tool in FILE_TOOLS:
        raw = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        if not raw:
            return True, ""
        rel = to_relative(raw, root)
        hit = is_protected(rel, protected)
        if hit:
            return False, MESSAGE.format(path=rel)
        return True, ""

    if tool == "Bash":
        cmd = (tool_input.get("command") or "").replace("\\", "/")
        for seg in SEGMENT_SPLIT.split(cmd):
            targets = [t for t in REDIRECT_TARGET.findall(seg) if t not in {"/dev/null", "&1", "&2"}]
            for t in targets:
                hit = is_protected(to_relative(t, root), protected)
                if hit:
                    return False, MESSAGE.format(path=t) + "\n(셸 리다이렉션으로 보호 경로를 바꾸는 것도 같은 규칙입니다.)"
            if WRITE_WORDS.search(seg):
                for p in protected:
                    if p.rstrip("/") and p.rstrip("/") in seg:
                        return False, MESSAGE.format(path=p) + "\n(셸 명령으로 보호 경로를 바꾸는 것도 같은 규칙입니다.)"
        return True, ""

    return True, ""


def main() -> int:
    root = project_root()
    cfg = load_config(root)
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0  # 입력을 읽지 못하면 막지 않는다 (훅 고장이 작업을 멈추지 않게)
    allowed, message = check(data, root, cfg)
    if not allowed:
        log(root, cfg, {"hook": "protect_paths", "verdict": "block", "tool": data.get("tool_name"), "detail": message.splitlines()[0]})
        print(message, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
