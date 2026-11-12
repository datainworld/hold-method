#!/usr/bin/env python3
"""HOLD 웹 확장 web-0.1 훅 — PreToolUse 와 PostToolUse 를 한 파일에서 처리합니다.

코어 훅(protect_paths.py, post_edit.py)과 별도 항목으로 등록되며, 코어 파일을 고치지 않습니다.

PreToolUse  (Bash|Edit|Write|MultiEdit|NotebookEdit)
  - 보호 경로 쓰기 차단: 글롭·대소문자·NTFS 표기 변형 포함. 읽기 전용 명령과 허락된 스크립트만 예외
  - MWG 를 npx·npm·node 로 직접 부르면 차단 — 래퍼(.claude/hold-web/mwg.py)만 허용 (R17)
  - 사람 전용 스크립트(sync.py, install.py)와 pre-commit 우회(--no-verify, core.hooksPath) 차단
  - 지난 훅 이후 바뀐 파일 검사 (백그라운드 실행이나 실패한 명령이 바꾼 파일도 다음 호출에서 잡힘)
PostToolUse (Bash|Edit|Write|MultiEdit)
  - 지난 훅 이후 바뀐 프런트엔드 파일 레거시 검사 (R15), 바뀐 changes/ 산출물 참조 가이드 검사 (R16)

변경 감지는 지속 스냅샷(.hold/logs/web_snap.json)의 내용 해시로 합니다. mtime 을 되돌려도 잡힙니다.
훅 자체가 예외로 죽으면 막는 쪽(종료 코드 2)으로 끝납니다.
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()).resolve()
sys.path.insert(0, str(ROOT / ".claude" / "hold-web"))

FILE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}


def block(c, msg: str, record: dict | None = None) -> int:
    c.log(ROOT, {"hook": "web_guard", **(record or {}), "reason": msg[:160]})
    print(msg, file=sys.stderr)
    return 2


def drift(c, web_check, cfg: dict, w: dict, when: str) -> list[str]:
    """지난 훅 이후 바뀐 파일을 검사한다. 되돌려 줄 문제 목록."""
    changed = c.changed_files(ROOT, w, cfg)
    if not changed:
        return []
    problems: list[str] = []
    profile = c.profile_of(cfg)
    mode = c.scan_mode(w, profile)
    front = [r for r in changed if c.is_frontend(r, w)]
    if front and mode != "off":
        res = c.scan(ROOT, w, front)
        rec = {"hook": "web_scan", "mode": mode, "via": when, "files": front, "mwg_version": w["mwg_version"]}
        if res.skipped:
            c.log(ROOT, {**rec, "verdict": "skip", "detail": res.skipped})
            if profile == "regulated":
                problems.append(f"레거시 패턴 검사를 하지 못했습니다 (R15): {res.skipped}")
        elif res.error:
            c.log(ROOT, {**rec, "verdict": "error", "detail": res.error})
            if mode == "block":
                problems.append(f"레거시 패턴 검사가 실패했습니다 (R15): {res.error}")
        else:
            c.log(ROOT, {**rec, "verdict": "fail" if res.findings else "pass",
                         "guides": sorted({f.guide for f in res.findings}), "allowed": sorted({f.guide for f in res.allowed})})
            if res.findings and mode == "block":
                problems.append(c.format_findings(res.findings, w))
    folders = sorted({"/".join(r.split("/")[:2]) for r in changed if c.is_change_doc(r, cfg)})
    for folder in folders:
        rep = web_check.Report()
        web_check.check_changes(ROOT, cfg, w, rep, only=ROOT / folder)
        problems += [f"웹 확장 산출물 검사 실패: {f}" for f in rep.fails]
    return problems


def run(data: dict) -> int:
    import common as c
    import web_check
    cfg = c.load_toml(ROOT)
    w, errors = c.web_config(cfg)
    if not w["enabled"]:
        return 0
    event = data.get("hook_event_name") or ("PostToolUse" if "tool_response" in data else "PreToolUse")
    tool = data.get("tool_name")
    ti = data.get("tool_input") or {}
    if errors:
        if event == "PreToolUse":
            return block(c, "hold.toml [web] 설정에 오류가 있어 웹 확장 장치가 판단할 수 없습니다. 사람이 고쳐야 합니다:\n- "
                         + "\n- ".join(errors))
        return 0
    if event == "PreToolUse":
        if tool in FILE_TOOLS:
            raw = ti.get("file_path") or ti.get("notebook_path") or ""
            if raw and c.is_protected_path(ROOT, raw):
                return block(c, f"{raw} 는 웹 확장이 지키는 파일입니다 (HOLD H1, R14·R17). 바꿔야 하면 멈추고 사람에게 보고하세요.",
                             {"tool": tool, "path": raw})
        elif tool == "Bash":
            cmd = ti.get("command") or ""
            msg = c.check_bash_protected(cmd, ROOT) or c.check_mwg_calls(cmd)
            if msg:
                return block(c, msg, {"tool": "Bash"})
        problems = drift(c, web_check, cfg, w, "between")
        if problems:
            print("지난 작업 이후 바뀐 파일에 문제가 있습니다. 먼저 고치세요.\n\n" + "\n\n".join(problems), file=sys.stderr)
            return 2
        return 0
    problems = drift(c, web_check, cfg, w, "bash" if tool == "Bash" else "edit")
    if problems:
        print("\n\n".join(problems), file=sys.stderr)
        return 2
    return 0


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    try:
        return run(data)
    except Exception:  # noqa: BLE001 — fail-closed
        tb = traceback.format_exc(limit=3)
        print("웹 확장 훅이 오류로 판단하지 못했습니다. 안전을 위해 막습니다. 사람에게 보고하세요.\n" + tb[-800:], file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
