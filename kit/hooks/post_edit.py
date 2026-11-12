#!/usr/bin/env python3
"""HOLD 수정 직후 검사 훅 (PostToolUse) — 규칙 R02·R03·R05·R06, 웹 확장 R15.

에이전트가 파일을 고친 직후, 고친 파일의 종류에 맞는 검사를 돌리고
실패하면 그 결과를 에이전트에게 돌려줍니다 (종료 코드 2).

- changes/**/*.md, 이해관계자 정의서, 컨텍스트 뷰 → scripts/check_views.py (해당 변경만)
- *.py → lint-imports (.importlinter 가 있을 때), pyright <파일> (설치되어 있을 때)
- 프런트엔드 파일 (웹 확장이 켜져 있을 때) → scripts/web_scan.py (MWG legacy-scan, 고정 버전)
  log 모드(Lite 기본)는 훅 로그에만 남기고, block 모드는 에이전트에게 되돌립니다.
검사 도구가 설치되어 있지 않으면 건너뜁니다 (훅이 작업을 막지 않게).
"""
from __future__ import annotations

import json
import os
import re
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

    failures += web_checks(rel, root, cfg)
    return failures


def web_checks(rel: Path, root: Path, cfg: dict) -> list[str]:
    """웹 확장 (방법론 9장, R15). 확장이 꺼져 있거나 프런트엔드 파일이 아니면 아무것도 하지 않는다."""
    if not (cfg.get("web") or {}).get("enabled"):
        return []
    script = root / "scripts" / "web_scan.py"
    if not script.exists():
        return []
    sys.path.insert(0, str(root / "scripts"))
    import web_scan  # noqa: E402 — 키트가 설치한 scripts/web_scan.py

    wcfg = web_scan.web_config(cfg)
    profile = str(cfg.get("hold", {}).get("profile") or "lite").lower()
    mode = web_scan.resolve_mode(wcfg, profile)
    if mode == "off" or not web_scan.is_frontend(rel, wcfg):
        return []
    result = web_scan.scan(root, cfg, [rel])
    # 측정 시트의 check_failures(post_edit 실패)와 섞이지 않게 별도 hook 이름으로 남긴다 (7장·9장)
    record = {"hook": "web_scan", "mode": mode, "file": rel.as_posix(),
              "mwg_version": wcfg["mwg_version"]}
    if result.skipped:
        log(root, cfg, {**record, "verdict": "skip", "detail": result.skipped})
        return []
    log(root, cfg, {**record, "verdict": "fail" if result.findings else "pass",
                    "guides": sorted({f.guide for f in result.findings}),
                    "allowed": sorted({f.guide for f in result.allowed})})
    if result.findings and mode == "block":
        return [web_scan.format_findings(result.findings, wcfg)]
    return []


MWG_CALL = re.compile(r"\bmodern-web-guidance(?:@([\w.\-]+))?\s+(search|retrieve|list)\b\s*(.*)")


def log_guidance_use(cmd: str, root: Path, cfg: dict) -> None:
    """웹 확장: 에이전트가 실제로 실행한 MWG search·retrieve 를 훅 로그에 남긴다 (H9 — 말이 아니라 기록).
    spec.md 의 '## 참조 가이드'와 대조하는 측정 자료가 된다 (9장 측정)."""
    if not (cfg.get("web") or {}).get("enabled"):
        return
    for seg in re.split(r"&&|\|\||;|\n", cmd):
        m = MWG_CALL.search(seg)
        if not m:
            continue
        version, action, rest = m.group(1), m.group(2), m.group(3)
        record = {"hook": "web_guidance", "action": action, "mwg_version": version}
        arg = re.split(r"\s--", rest, maxsplit=1)[0].strip().strip("'\"")
        if action == "retrieve":
            record["ids"] = [s.strip() for s in arg.split(",") if s.strip()]
        elif action == "search":
            record["query"] = arg[:120]
        log(root, cfg, record)


def main() -> int:
    root = project_root()
    cfg = load_config(root)
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    if data.get("tool_name") == "Bash":
        log_guidance_use((data.get("tool_input") or {}).get("command") or "", root, cfg)
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
