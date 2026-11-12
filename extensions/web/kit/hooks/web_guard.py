#!/usr/bin/env python3
"""HOLD 웹 확장 web-0.1 훅 — PreToolUse 와 PostToolUse 를 한 파일에서 처리합니다.

코어 훅(protect_paths.py, post_edit.py)과 따로 등록되며, 코어 파일을 고치지 않습니다.

PreToolUse  (Bash|Edit|Write|MultiEdit|NotebookEdit)
  - 확장 보호 경로(.mwgrc 는 위치 무관, docs/hold/web/, .hold/logs/, .claude/hold-web/ 등) 쓰기 차단
  - MWG 호출 검사: 고정 버전, 하위 명령 화이트리스트(search·retrieve·list·legacy-scan), 텔레메트리 접두어 (R17)
  - 사람 전용 스크립트(sync.py, install.py) 실행 차단
  - Bash 실행 전 프런트엔드 파일 스냅샷 (실행 후 바뀐 파일을 찾기 위해)
PostToolUse (Bash|Edit|Write|MultiEdit)
  - 바뀐 프런트엔드 파일 레거시 검사 (편집 도구든 Bash 든) (R15)
  - changes/ 아래 산출물을 고치면 참조 가이드 검사 (R16)
  - retrieve 의 실제 출력에서 가이드 ID 를 확인해 기록 (H9)
종료 코드 0 = 통과, 2 = 차단·되돌림 (stderr 가 에이전트에게 전달됨).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()).resolve()
sys.path.insert(0, str(ROOT / ".claude" / "hold-web"))
import common as c  # noqa: E402
import web_check  # noqa: E402

FILE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}


def block(msg: str, record: dict | None = None) -> int:
    c.log(ROOT, {"hook": "web_guard", **(record or {}), "reason": msg[:160]})
    print(msg, file=sys.stderr)
    return 2


def pre(data: dict, w: dict) -> int:
    tool = data.get("tool_name")
    ti = data.get("tool_input") or {}
    if tool in FILE_TOOLS:
        raw = ti.get("file_path") or ti.get("notebook_path") or ""
        if raw and c.is_protected_path(ROOT, raw):
            return block(f"{raw} 는 웹 확장이 지키는 파일입니다 (HOLD H1, R14·R17). 바꿔야 하면 멈추고 사람에게 보고하세요.",
                         {"tool": tool, "path": raw})
        return 0
    if tool == "Bash":
        cmd = ti.get("command") or ""
        msg = c.check_bash_protected(cmd, ROOT) or c.check_mwg_calls(cmd, w)
        if msg:
            return block(msg, {"tool": "Bash"})
        if c.scan_mode(w, c.profile_of(CFG)) != "off":
            snap_dir = ROOT / c.SNAP_DIR
            snap_dir.mkdir(parents=True, exist_ok=True)
            key = str(data.get("tool_use_id") or "last").replace("/", "_")
            (snap_dir / f"{key}.json").write_text(json.dumps(c.frontend_snapshot(ROOT, w)), encoding="utf-8")
    return 0


def scan_and_report(rels: list[str], w: dict, via: str) -> str | None:
    profile = c.profile_of(CFG)
    mode = c.scan_mode(w, profile)
    rels = [r for r in rels if c.is_frontend(r, w)]
    if mode == "off" or not rels:
        return None
    res = c.scan(ROOT, w, rels)
    rec = {"hook": "web_scan", "mode": mode, "via": via, "files": rels, "mwg_version": w["mwg_version"]}
    if res.skipped:
        c.log(ROOT, {**rec, "verdict": "skip", "detail": res.skipped})
        return f"레거시 패턴 검사를 하지 못했습니다 (R15): {res.skipped}" if profile == "regulated" else None
    if res.error:
        c.log(ROOT, {**rec, "verdict": "error", "detail": res.error})
        return f"레거시 패턴 검사가 실패했습니다 (R15): {res.error}" if mode == "block" else None
    c.log(ROOT, {**rec, "verdict": "fail" if res.findings else "pass",
                 "guides": sorted({f.guide for f in res.findings}), "allowed": sorted({f.guide for f in res.allowed})})
    if res.findings and mode == "block":
        return c.format_findings(res.findings, w)
    return None


def post(data: dict, w: dict) -> int:
    tool = data.get("tool_name")
    ti = data.get("tool_input") or {}
    problems: list[str] = []
    if tool in FILE_TOOLS:
        raw = ti.get("file_path") or ti.get("notebook_path") or ""
        rel = c.rel_posix(ROOT, raw) if raw else None
        if rel:
            msg = scan_and_report([rel], w, "edit")
            if msg:
                problems.append(msg)
            changes = (CFG.get("paths", {}).get("changes") or "changes").rstrip("/") + "/"
            parts = rel.split("/")
            if rel.startswith(changes) and rel.endswith(".md") and len(parts) >= 3:
                rep = web_check.Report()
                web_check.check_changes(ROOT, CFG, w, rep, only=ROOT / "/".join(parts[:-1]))
                problems += [f"웹 확장 산출물 검사 실패: {f}" for f in rep.fails]
    elif tool == "Bash":
        cmd = ti.get("command") or ""
        try:
            calls = c.find_mwg_calls(cmd, True)
        except c.ParseError:
            calls = []
        requested = []
        for call in calls:
            if call.sub == "retrieve":
                first, _ = c._sub_and_args(call.args)   # 옵션을 건너뛴 첫 인자 = ID 목록
                requested += [i.strip() for i in (first or "").split(",") if i.strip()]
        if requested or any(call.sub == "retrieve" for call in calls):
            known = c.known_guides(ROOT)
            confirmed = [i for i in c.retrieved_ids(data.get("tool_response")) if i in known]
            c.log(ROOT, {"hook": "web_guidance", "action": "retrieve", "requested": requested, "confirmed": confirmed})
        key = str(data.get("tool_use_id") or "last").replace("/", "_")
        snap_file = ROOT / c.SNAP_DIR / f"{key}.json"
        if snap_file.exists():
            try:
                before = json.loads(snap_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                before = {}
            snap_file.unlink(missing_ok=True)
            after = c.frontend_snapshot(ROOT, w)
            changed = sorted(r for r, v in after.items() if before.get(r) != v)
            msg = scan_and_report(changed, w, "bash")
            if msg:
                problems.append(msg)
    if problems:
        print("\n\n".join(problems), file=sys.stderr)
        return 2
    return 0


def main() -> int:
    global CFG
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    CFG = c.load_toml(ROOT)
    w, errors = c.web_config(CFG)
    if not w["enabled"]:
        return 0
    event = data.get("hook_event_name") or ("PostToolUse" if "tool_response" in data else "PreToolUse")
    if errors:
        if event == "PreToolUse":
            return block("hold.toml [web] 설정에 오류가 있어 웹 확장 장치가 판단할 수 없습니다. 사람이 고쳐야 합니다:\n- "
                         + "\n- ".join(errors))
        return 0
    return pre(data, w) if event == "PreToolUse" else post(data, w)


CFG: dict = {}

if __name__ == "__main__":
    sys.exit(main())
