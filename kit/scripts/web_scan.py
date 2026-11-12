#!/usr/bin/env python3
"""HOLD 웹 확장 — 레거시 패턴 검사 (규칙 R15, 방법론 9장).

Modern Web Guidance(MWG)의 `legacy-scan` 을 hold.toml 이 고정한 버전으로 실행하고,
사람이 받아들인 검출(허용 목록)을 뺀 나머지를 HOLD 형식으로 돌려줍니다.

MWG 의 legacy-scan 은 검출이 있어도 종료 코드 0 을 돌려주므로 그대로는 통제 장치가 되지 않습니다.
이 래퍼가 JSON 의 검출 건수를 읽어 판정을 내립니다.

사용법:
  python scripts/web_scan.py                    # 프로젝트 전체
  python scripts/web_scan.py web/index.html …   # 지정한 파일만 (pre-commit)
종료 코드: 0 통과(또는 확장 꺼짐·log 모드), 1 검출 있음(block 모드).

post_edit.py 훅이 이 모듈을 import 해 수정한 파일 하나를 검사합니다.
npx 가 없거나 시간이 초과되면 건너뜁니다 (훅이 작업을 막지 않게, 키트의 다른 검사와 같은 규칙).
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    tomllib = None  # type: ignore[assignment]

WEB_DEFAULTS: dict = {
    "enabled": False,
    "ext_version": "0.1",
    "mwg_version": "1.0.0",
    "baseline": "widely",
    "fallback_policy": "",
    "telemetry": False,
    "legacy_scan": "auto",
    "legacy_allow": [],
    "frontend_suffixes": [".html", ".htm", ".css", ".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".vue", ".svelte"],
    "skip_dirs": ["node_modules", "dist", "build", ".next", ".nuxt", "vendor", ".venv"],
}
SCAN_TIMEOUT = 90  # 초. 첫 실행은 npm 에서 패키지를 받으므로 여유를 둔다
BATCH_LIMIT = 5    # 이보다 많은 파일은 프로젝트를 한 번에 검사하고 걸러낸다


@dataclass
class Finding:
    guide: str
    rule: str
    file: str   # 프로젝트 루트 기준 posix 경로
    line: int | None
    message: str


@dataclass
class ScanResult:
    findings: list[Finding] = field(default_factory=list)
    allowed: list[Finding] = field(default_factory=list)
    skipped: str | None = None  # 검사를 건너뛴 이유 (npx 없음, 시간 초과 등)


def load_config(root: Path) -> dict:
    f = root / "hold.toml"
    if tomllib is None or not f.exists():
        return {}
    with f.open("rb") as fh:
        return tomllib.load(fh)


def web_config(cfg: dict) -> dict:
    return {**WEB_DEFAULTS, **(cfg.get("web") or {})}


def resolve_mode(wcfg: dict, profile: str) -> str:
    """off | log | block"""
    mode = str(wcfg.get("legacy_scan", "auto")).lower()
    if not wcfg.get("enabled"):
        return "off"
    if mode == "auto":
        return "log" if profile == "lite" else "block"
    return mode if mode in ("off", "log", "block") else "log"


def is_frontend(rel: Path, wcfg: dict) -> bool:
    if rel.suffix.lower() not in {s.lower() for s in wcfg["frontend_suffixes"]}:
        return False
    return not any(part in set(wcfg["skip_dirs"]) for part in rel.parts)


def mwg_env(wcfg: dict) -> dict:
    env = dict(os.environ)
    if not wcfg.get("telemetry", False):
        env["DISABLE_TELEMETRY"] = "1"
    return env


def mwg_command(wcfg: dict, *args: str) -> list[str] | None:
    npx = shutil.which("npx")
    if not npx:
        return None
    return [npx, "-y", f"modern-web-guidance@{wcfg['mwg_version']}", *args]


def is_allowed(f: Finding, allow: list[str]) -> bool:
    for entry in allow:
        guide, _, pattern = str(entry).partition(":")
        if guide != f.guide:
            continue
        if not pattern or fnmatch.fnmatch(f.file, pattern):
            return True
    return False


def _run_scan(root: Path, target: str, wcfg: dict) -> tuple[dict | None, str | None]:
    cmd = mwg_command(wcfg, "legacy-scan", target, "--json")
    if cmd is None:
        return None, "npx 가 없어 레거시 패턴 검사를 건너뛰었습니다 (Node.js 22 이상 필요)"
    try:
        res = subprocess.run(cmd, cwd=root, capture_output=True, text=True, encoding="utf-8",
                             env=mwg_env(wcfg), timeout=SCAN_TIMEOUT)
    except subprocess.TimeoutExpired:
        return None, f"legacy-scan 이 {SCAN_TIMEOUT}초 안에 끝나지 않아 건너뛰었습니다 (오프라인이면 npm 캐시를 확인)"
    try:
        return json.loads(res.stdout), None
    except json.JSONDecodeError:
        tail = (res.stderr or res.stdout).strip().splitlines()[-1:] or [""]
        return None, f"legacy-scan 출력을 읽지 못해 건너뛰었습니다: {tail[0][:200]}"


def _findings(data: dict, base: str | None, single: str | None) -> list[Finding]:
    out: list[Finding] = []
    for g in data.get("guides", []):
        for r in g.get("rules", []):
            for m in r.get("findings", []):
                if single is not None:
                    file = single
                else:
                    raw = str(m.get("file", "")).replace("\\", "/")
                    file = f"{base}/{raw}" if base not in (None, "", ".") else raw
                out.append(Finding(guide=g.get("guideId", "?"), rule=r.get("ruleId", "?"), file=file,
                                   line=m.get("line"), message=str(m.get("message", "")).strip()))
    return out


def scan(root: Path, cfg: dict, files: list[Path] | None = None) -> ScanResult:
    """files 가 None 이면 프로젝트 전체, 아니면 그 파일들(루트 기준 상대 경로)만 검사한다."""
    wcfg = web_config(cfg)
    result = ScanResult()
    if files is not None:
        files = [f for f in files if is_frontend(f, wcfg)]
        if not files:
            return result
    raw: list[Finding] = []
    if files is not None and len(files) <= BATCH_LIMIT:
        for f in files:
            data, skip = _run_scan(root, f.as_posix(), wcfg)
            if skip:
                result.skipped = skip
                return result
            raw += _findings(data or {}, None, f.as_posix())
    else:
        data, skip = _run_scan(root, ".", wcfg)
        if skip:
            result.skipped = skip
            return result
        raw = _findings(data or {}, ".", None)
        wanted = {f.as_posix() for f in files} if files is not None else None
        raw = [f for f in raw if is_frontend(Path(f.file), wcfg) and (wanted is None or f.file in wanted)]
    allow = list(wcfg.get("legacy_allow") or [])
    for f in raw:
        (result.allowed if is_allowed(f, allow) else result.findings).append(f)
    return result


def format_findings(findings: list[Finding], wcfg: dict) -> str:
    ver = wcfg["mwg_version"]
    lines = ["레거시 웹 패턴이 검출되었습니다 (R15, 고정 가이드 modern-web-guidance@" + ver + ")."]
    by_guide: dict[str, list[Finding]] = {}
    for f in findings:
        by_guide.setdefault(f.guide, []).append(f)
    for guide, items in by_guide.items():
        lines.append(f"\n[{guide}]  가이드 읽기: npx -y modern-web-guidance@{ver} retrieve {guide}")
        for f in items[:5]:
            where = f"{f.file}:{f.line}" if f.line else f.file
            lines.append(f"  - {where} — {f.message[:200]}")
        if len(items) > 5:
            lines.append(f"  - … 외 {len(items) - 5}건")
    lines.append(
        "\n가이드를 읽고 고치세요. 검출이 오탐(이미 대체 코드가 있음, 외부 코드 등)이라고 판단되면 코드를 비틀지 말고 멈춰서 "
        "사람에게 보고하세요. 받아들일 검출은 사람이 hold.toml 의 [web].legacy_allow 에 적습니다."
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="HOLD 웹 확장 레거시 패턴 검사 (R15)")
    ap.add_argument("files", nargs="*", type=Path, help="검사할 파일 (생략하면 프로젝트 전체)")
    ap.add_argument("--root", type=Path, default=Path(os.environ.get("CLAUDE_PROJECT_DIR") or "."))
    ap.add_argument("--profile", choices=["lite", "standard", "regulated"])
    args = ap.parse_args(argv)
    root = args.root.resolve()
    cfg = load_config(root)
    wcfg = web_config(cfg)
    profile = (args.profile or cfg.get("hold", {}).get("profile") or "lite").lower()
    mode = resolve_mode(wcfg, profile)
    if mode == "off":
        print("OK  웹 확장이 꺼져 있거나 legacy_scan = off 입니다")
        return 0
    files = None
    if args.files:
        files = []
        for f in args.files:
            p = f if f.is_absolute() else root / f
            try:
                files.append(p.resolve().relative_to(root))
            except ValueError:
                continue
    result = scan(root, cfg, files)
    if result.skipped:
        print("WARN " + result.skipped, file=sys.stderr)
        return 0
    if result.allowed:
        print(f"INFO 허용 목록으로 제외한 검출 {len(result.allowed)}건", file=sys.stderr)
    if not result.findings:
        print("OK  레거시 웹 패턴 검사 통과")
        return 0
    print(format_findings(result.findings, wcfg))
    return 1 if mode == "block" else 0


if __name__ == "__main__":
    sys.exit(main())
