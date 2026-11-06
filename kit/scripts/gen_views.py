#!/usr/bin/env python3
"""HOLD 사실 뷰 생성 — 원칙 H8 "보이게 만든다", 규칙 R08 (의도 뷰는 사람이 그리고, 사실 뷰는 코드에서 만든다).

v0.1(Lite)에서는 계약 클래스 뷰 하나를 만듭니다.
  - 계약 패키지(hold.toml [paths].contracts, 기본 app/contracts)의 Pydantic 모델과 Enum 을 읽어
  - Mermaid classDiagram 을 docs/architecture/views/generated/contracts.md 에 씁니다.
계약 게이트(Stage 2.5)에서 사람이 승인하는 자료는 이 그림입니다. Python 을 읽지 않고도 계약을 검토할 수 있습니다.

사용법:
  python scripts/gen_views.py           # 다시 생성
  python scripts/gen_views.py --check   # 커밋된 뷰가 코드와 같은지 확인 (다르면 종료 코드 1)
"""
from __future__ import annotations

import argparse
import enum
import importlib
import inspect
import os
import sys
import typing
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    tomllib = None  # type: ignore[assignment]

HEADER = (
    "<!-- 생성된 파일입니다. 손으로 고치지 마세요. 다시 만들기: python scripts/gen_views.py -->\n"
    "# 계약 클래스 뷰 (사실 뷰)\n\n"
    "누구의 어떤 질문: 계약 승인자 — 모듈 경계를 넘는 데이터는 어떤 모양이고 무엇을 참조하는가?\n\n"
)


def load_config(root: Path) -> dict:
    f = root / "hold.toml"
    if tomllib is None or not f.exists():
        return {}
    with f.open("rb") as fh:
        return tomllib.load(fh)


def import_contract_modules(root: Path, contracts: Path) -> list:
    sys.path.insert(0, str(root))
    modules = []
    for py in sorted(contracts.rglob("*.py")):
        if py.name.startswith("_draft"):
            continue  # 승인 전 초안은 사실 뷰에 넣지 않는다
        rel = py.relative_to(root).with_suffix("")
        parts = list(rel.parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        modules.append(importlib.import_module(".".join(parts)))
    return modules


def collect(modules: list) -> tuple[list[type], list[type]]:
    from pydantic import BaseModel  # 프로젝트 의존성

    models, enums, seen = [], [], set()
    for mod in modules:
        for _, obj in inspect.getmembers(mod, inspect.isclass):
            if obj.__module__ != mod.__name__ or obj in seen:
                continue
            seen.add(obj)
            if issubclass(obj, BaseModel) and not obj.__name__.startswith("_"):
                models.append(obj)
            elif issubclass(obj, enum.Enum):
                enums.append(obj)
    key = lambda c: (c.__module__, c.__name__)
    return sorted(models, key=key), sorted(enums, key=key)


def type_name(tp: object) -> str:
    origin = typing.get_origin(tp)
    if origin is None:
        if tp is type(None):
            return "None"
        return getattr(tp, "__name__", str(tp).replace("typing.", ""))
    args = typing.get_args(tp)
    if origin in (typing.Union, getattr(__import__("types"), "UnionType", None)):
        # Mermaid 클래스 멤버에서 '|'는 깨질 수 있어 Optional~X~ / A or B 로 쓴다
        rest = [a for a in args if a is not type(None)]
        if len(rest) == 1 and len(args) == 2:
            return f"Optional~{type_name(rest[0])}~"
        return " or ".join(type_name(a) for a in args)
    if origin is typing.Literal:
        return "Literal"
    if origin is typing.Annotated:
        return type_name(args[0])
    name = getattr(origin, "__name__", str(origin))
    return f"{name}~{', '.join(type_name(a) for a in args)}~"


def referenced(tp: object, names: set[str]) -> set[str]:
    found = set()
    if getattr(tp, "__name__", None) in names:
        found.add(tp.__name__)  # type: ignore[union-attr]
    for a in typing.get_args(tp):
        found |= referenced(a, names)
    return found


def render(models: list[type], enums: list[type]) -> str:
    names = {m.__name__ for m in models} | {e.__name__ for e in enums}
    lines = ["```mermaid", "classDiagram"]
    relations = []
    for m in models:
        lines.append(f"    class {m.__name__} {{")
        for fname, finfo in m.model_fields.items():
            lines.append(f"        +{type_name(finfo.annotation)} {fname}")
            for target in sorted(referenced(finfo.annotation, names) - {m.__name__}):
                relations.append(f"    {m.__name__} --> {target} : {fname}")
        for cname in getattr(m, "model_computed_fields", {}):
            lines.append(f"        +{cname}() computed")
        lines.append("    }")
    for e in enums:
        lines.append(f"    class {e.__name__} {{")
        lines.append("        <<enumeration>>")
        for member in e:
            lines.append(f"        {member.name}")
        lines.append("    }")
    lines += sorted(set(relations))
    lines.append("```")
    return HEADER + "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="HOLD 사실 뷰 생성 (계약 클래스 뷰)")
    ap.add_argument("--root", type=Path, default=Path(os.environ.get("CLAUDE_PROJECT_DIR") or "."))
    ap.add_argument("--check", action="store_true", help="생성 결과가 커밋된 파일과 같은지만 확인")
    args = ap.parse_args(argv)
    root = args.root.resolve()
    paths = load_config(root).get("paths", {})
    contracts = root / paths.get("contracts", "app/contracts")
    out = root / paths.get("generated_views", "docs/architecture/views/generated") / "contracts.md"

    if not contracts.exists():
        print(f"SKIP 계약 패키지가 아직 없습니다: {contracts.relative_to(root)}")
        return 0
    models, enums = collect(import_contract_modules(root, contracts))
    text = render(models, enums)

    if args.check:
        current = out.read_text(encoding="utf-8") if out.exists() else ""
        if current != text:
            print(f"FAIL {out.relative_to(root)}\n  - 계약 코드와 사실 뷰가 다릅니다. python scripts/gen_views.py 로 다시 생성하고 함께 커밋하세요")
            return 1
        print("OK  사실 뷰가 계약 코드와 같습니다")
        return 0

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"WROTE {out.relative_to(root)} ({len(models)} models, {len(enums)} enums)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
