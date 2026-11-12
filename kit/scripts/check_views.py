#!/usr/bin/env python3
"""HOLD 산출물 검사 — 원칙 H3·H8, 규칙 R05·R06.

검사하는 것 (프로필에 따라 다름):
  Stage 0  이해관계자 정의서에 ID가 하나 이상 있고, 컨텍스트 뷰에 mermaid 블록이 있다
  Stage 1  intent.md 에 "## 이해관계자" 절이 있고 정의서 ID를 하나 이상 적었다
  Stage 2  spec.md 에 "## 이해관계자 영향" 절(ID 포함)과 "## 뷰" 절이 있고,
           "## 뷰" 절에 sequenceDiagram 이 있다 (Standard 이상은 컴포넌트 뷰도 필수)
  Stage 3  plan.md 에 "## 모듈별 작업 범위" 절이 있다
  공통     산출물에 적힌 SH-ID 가 모두 정의서에 있다
           mermaid 블록이 렌더링된다 (mmdc 가 설치된 경우에만, 없으면 경고)

사용법:
  python scripts/check_views.py                 # 프로젝트 전체 검사
  python scripts/check_views.py changes/20261110-dining   # 변경 하나만 검사
종료 코드: 0 통과, 1 실패.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    tomllib = None  # type: ignore[assignment]

SH_ID = re.compile(r"\bSH-[A-Z]\d{2,3}\b")
MERMAID_BLOCK = re.compile(r"```mermaid\s*\n(.*?)```", re.S)
COMPONENT_KINDS = ("C4Component", "C4Container", "flowchart", "graph ")
SKIP_LINE = re.compile(r"^\s*>?\s*생략\s*:", re.M)

DEFAULTS = {
    "stakeholders": "docs/architecture/stakeholders.md",
    "context_view": "docs/architecture/views/context.md",
    "changes": "changes",
}


@dataclass
class Report:
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def fail(self, where: Path | str, msg: str) -> None:
        self.failures.append(f"FAIL {where}\n  - {msg}")

    def warn(self, msg: str) -> None:
        self.warnings.append(f"WARN {msg}")


def load_config(root: Path) -> dict:
    f = root / "hold.toml"
    if tomllib is None or not f.exists():
        return {}
    with f.open("rb") as fh:
        return tomllib.load(fh)


def sections(text: str) -> dict[str, str]:
    """'## 제목' 단위로 본문을 나눈다. 키는 제목 텍스트."""
    out: dict[str, str] = {}
    current = None
    buf: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if current is not None:
                out[current] = "\n".join(buf)
            current, buf = line[3:].strip(), []
        elif current is not None:
            buf.append(line)
    if current is not None:
        out[current] = "\n".join(buf)
    return out


def find_section(secs: dict[str, str], name: str) -> str | None:
    for title, body in secs.items():
        if title == name or title.startswith(name + " ") or title.startswith(name + "("):
            return body
    return None


def registry_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    ids = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and SH_ID.fullmatch(cells[0]):
            ids.add(cells[0])
    return ids


def check_mermaid_render(blocks: list[str], where: Path, report: Report) -> None:
    mmdc = shutil.which("mmdc")
    if not mmdc:
        return
    for i, block in enumerate(blocks, 1):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "in.mmd"
            src.write_text(block, encoding="utf-8")
            res = subprocess.run([mmdc, "-i", str(src), "-o", str(Path(tmp) / "out.svg")],
                                 capture_output=True, text=True)
            if res.returncode != 0:
                first = (res.stderr or res.stdout).strip().splitlines()[:1]
                report.fail(where, f"mermaid 블록 {i}이(가) 렌더링되지 않습니다: {' '.join(first)}")


def check_ids(text: str, known: set[str], where: Path, report: Report) -> None:
    for sid in sorted(set(SH_ID.findall(text)) - known):
        report.fail(where, f"{sid} 는 이해관계자 정의서에 없는 ID 입니다. 정의서에 추가를 제안하거나 ID를 고치세요")


def check_stage0(root: Path, paths: dict, report: Report) -> set[str]:
    reg = root / paths["stakeholders"]
    ids = registry_ids(reg)
    if not reg.exists():
        report.fail(reg.relative_to(root), "이해관계자 정의서가 없습니다 (Stage 0)")
    elif not ids:
        report.fail(reg.relative_to(root), "정의서 표에 SH-ID 행이 하나도 없습니다. 예: | SH-U01 | 여행자 | 사용자 | …")
    ctx = root / paths["context_view"]
    if not ctx.exists():
        report.fail(ctx.relative_to(root), "시스템 컨텍스트 뷰 파일이 없습니다 (Stage 0)")
    else:
        blocks = MERMAID_BLOCK.findall(ctx.read_text(encoding="utf-8"))
        if not blocks:
            report.fail(ctx.relative_to(root), "컨텍스트 뷰에 mermaid 블록이 없습니다")
        check_mermaid_render(blocks, ctx.relative_to(root), report)
    return ids


def check_change(change: Path, root: Path, ids: set[str], profile: str, report: Report) -> None:
    rel = change.relative_to(root)
    intent, spec, plan = change / "intent.md", change / "spec.md", change / "plan.md"

    if not intent.exists():
        report.fail(rel, "intent.md 가 없습니다 (모든 변경은 intent 로 시작합니다)")
    else:
        text = intent.read_text(encoding="utf-8")
        body = find_section(sections(text), "이해관계자")
        if body is None:
            report.fail(rel / "intent.md", "'## 이해관계자' 절이 없습니다")
        elif not SH_ID.search(body):
            report.fail(rel / "intent.md", "'## 이해관계자' 절에 정의서 ID(SH-…)가 없습니다")
        check_ids(text, ids, rel / "intent.md", report)
        check_mermaid_render(MERMAID_BLOCK.findall(text), rel / "intent.md", report)

    if spec.exists():
        text = spec.read_text(encoding="utf-8")
        secs = sections(text)
        impact = find_section(secs, "이해관계자 영향")
        if impact is None:
            report.fail(rel / "spec.md", "'## 이해관계자 영향' 절이 없습니다")
        elif not SH_ID.search(impact):
            report.fail(rel / "spec.md", "'## 이해관계자 영향' 절에 정의서 ID(SH-…)가 없습니다")
        views = find_section(secs, "뷰")
        if views is None:
            report.fail(rel / "spec.md", "'## 뷰' 절이 없습니다")
        else:
            blocks = MERMAID_BLOCK.findall(views)
            if not any(b.lstrip().startswith("sequenceDiagram") for b in blocks):
                report.fail(rel / "spec.md", "'## 뷰'에 sequenceDiagram 블록이 없습니다 (핵심 상호작용, 실패 경로 포함)")
            if profile in ("standard", "regulated") and not any(b.lstrip().startswith(COMPONENT_KINDS) for b in blocks):
                if not SKIP_LINE.search(views):
                    report.fail(rel / "spec.md", "'## 뷰'에 컴포넌트 뷰(C4 또는 flowchart)가 없습니다. 바뀌지 않으면 '생략: 이유'를 적으세요")
        check_ids(text, ids, rel / "spec.md", report)
        check_mermaid_render(MERMAID_BLOCK.findall(text), rel / "spec.md", report)

    if plan.exists():
        text = plan.read_text(encoding="utf-8")
        if find_section(sections(text), "모듈별 작업 범위") is None:
            report.fail(rel / "plan.md", "'## 모듈별 작업 범위' 절이 없습니다 (모듈 = worktree 단위)")
        check_ids(text, ids, rel / "plan.md", report)


def run(root: Path, only: list[Path] | None = None, profile: str | None = None) -> Report:
    cfg = load_config(root)
    paths = {**DEFAULTS, **cfg.get("paths", {})}
    profile = (profile or cfg.get("hold", {}).get("profile") or "lite").lower()
    report = Report()
    ids = check_stage0(root, paths, report)

    changes_dir = root / paths["changes"]
    if only:
        targets = [p if p.is_absolute() else root / p for p in only]
    elif changes_dir.exists():
        targets = sorted(p for p in changes_dir.iterdir() if p.is_dir() and not p.name.startswith(("_", ".")))
    else:
        targets = []
    for change in targets:
        if change.is_dir():
            check_change(change, root, ids, profile, report)
    if not shutil.which("mmdc"):
        report.warn("mmdc(mermaid-cli)가 없어 렌더 검사를 생략했습니다. 설치: npm i -g @mermaid-js/mermaid-cli")
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="HOLD 산출물·필수 뷰 검사")
    ap.add_argument("changes", nargs="*", type=Path, help="검사할 변경 폴더 (생략하면 전체)")
    ap.add_argument("--root", type=Path, default=Path(os.environ.get("CLAUDE_PROJECT_DIR") or "."))
    ap.add_argument("--profile", choices=["lite", "standard", "regulated"])
    args = ap.parse_args(argv)
    report = run(args.root.resolve(), args.changes or None, args.profile)
    for w in report.warnings:
        print(w, file=sys.stderr)
    if report.failures:
        print("\n".join(report.failures))
        return 1
    print("OK  HOLD 산출물 검사 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())
