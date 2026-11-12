#!/usr/bin/env python3
"""HOLD 웹 확장 — Modern Web Guidance 고정 버전 설치·검사 (규칙 R14·R16·R17, 방법론 9장).

사람이 실행하는 스크립트입니다. hold.toml [web].mwg_version 의 MWG 패키지에서 다음을 만듭니다.

  .claude/skills/modern-web-guidance/SKILL.md  MWG skill 을 고정 버전으로 바꾸고 "HOLD 프로젝트 규칙" 절을 붙인 것
  .claude/skills/modern-web-guidance/LICENSE   MWG 라이선스 (Apache-2.0) 사본
  docs/hold/web/guides.json                     그 버전의 가이드 ID 목록 (check_views.py 가 참조 가이드를 대조)

세 곳 모두 보호 경로라 에이전트는 고칠 수 없습니다. 버전을 올리는 일은 사람의 변경입니다.

사용법:
  python scripts/hold_web_sync.py                         # npm 에서 고정 버전을 받아 설치
  python scripts/hold_web_sync.py --tarball mwg-1.0.0.tgz # 미리 받은 패키지로 설치 (폐쇄망)
  python scripts/hold_web_sync.py --check                 # 설치본이 hold.toml 과 같은 버전인지 검사 (읽기 전용)
종료 코드: 0 성공, 1 실패.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    tomllib = None  # type: ignore[assignment]

PKG = "modern-web-guidance"
SKILL_DIR = ".claude/skills/modern-web-guidance"
MEMBERS = {
    "skill": "package/skills/modern-web-guidance/SKILL.md",
    "skill_version": "package/skills/modern-web-guidance/skill-version.txt",
    "guides": "package/skills/modern-web-guidance/gen/guides.json",
    "license": "package/LICENSE",
}
NOTICE_RE = re.compile(r"<!-- hold-kit: .*?modern-web-guidance@([\w.\-]+)")
LATEST = f"{PKG}@latest"


class SyncError(Exception):
    pass


def load_config(root: Path) -> dict:
    f = root / "hold.toml"
    if tomllib is None or not f.exists():
        return {}
    with f.open("rb") as fh:
        return tomllib.load(fh)


def web_settings(cfg: dict) -> dict:
    web = cfg.get("web") or {}
    return {
        "enabled": bool(web.get("enabled", False)),
        "ext_version": str(web.get("ext_version", "0.1")),
        "mwg_version": str(web.get("mwg_version", "1.0.0")),
        "baseline": str(web.get("baseline", "widely")),
        "fallback_policy": str(web.get("fallback_policy", "") or "").strip(),
        "telemetry": bool(web.get("telemetry", False)),
    }


def guides_path(root: Path, cfg: dict) -> Path:
    return root / (cfg.get("paths", {}).get("web_guides") or "docs/hold/web/guides.json")


def describe_baseline(baseline: str) -> str:
    b = baseline.strip().lower()
    if b in ("widely", "widely available", ""):
        return ("Baseline Widely available (MWG 기본값). "
                "Baseline Widely available 이 아닌 기능은 가이드의 대체 코드 권고를 따른다.")
    if b in ("newly", "newly available"):
        return ("Allow Newly Available features if feature-detected with graceful degradation. "
                "Baseline Newly available 기능까지 쓰되, 기능 감지와 우아한 저하를 전제로 한다.")
    if re.fullmatch(r"\d{4}", b):
        return (f"This project's Baseline target is Baseline {b}. "
                f"가이드의 'Baseline since' 연도가 {b} 이하인 기능은 대체 코드 없이 쓴다.")
    return f"{baseline} (hold.toml 에 사람이 적은 그대로)"


def hold_section(web: dict) -> str:
    fallback = web["fallback_policy"] or (
        "별도 정책 없음. 가이드의 Fallback 권고를 따르되, 전략이 둘 이상이면 아래 '대체 동작 선택' 규칙대로 사람에게 묻는다."
    )
    ver = web["mwg_version"]
    return f"""

## HOLD 프로젝트 규칙 (이 절이 위 내용보다 우선한다)

이 프로젝트는 HOLD 방법론의 웹 프런트엔드 확장 web-{web['ext_version']}을 따른다. 정책의 원본은 `hold.toml`의 `[web]`이고, 사람이 소유한다 (보호 경로).

### 브라우저 지원 정책 (R14)
- 지원 기준: {describe_baseline(web['baseline'])}
- 대체 동작 정책: {fallback}
- 위 "Reactive Policy Discovery"를 따르지 않는다. 지원 정책을 `CLAUDE.md`나 `AGENTS.md`에 쓰거나 쓰자고 제안하지 않는다. 정책이 작업과 맞지 않으면 멈추고, 이유와 선택지를 보고하거나 `changes/` 아래에 intent.md를 제안한다.

### 대체 동작 선택은 계약 질문이다 (R18, H5)
- 가이드가 대체 전략을 둘 이상 제시하거나, 지원 기준 밖 브라우저에서 기능을 빼야 할 때는 스스로 고르지 않는다. spec.md의 `## 계약 질문 목록`에 `(웹)`으로 시작하는 질문으로 남긴다.

### 참조 가이드 기록 (R16)
- Stage 2(Design)에서 search·retrieve한 가이드는 spec.md의 `## 참조 가이드` 절에 ID를 백틱으로 적는다. 예: ``- `dialog` — 모달은 <dialog>와 showModal()로, 닫힘은 Esc·뒤로 가기 제스처 모두``.
- 가이드를 쓰지 않은 변경이면 그 절에 `생략: 이유` 한 줄을 적는다.
- 응답 끝의 `### Modern Web Guidance` 절은 그대로 쓰되, 그것은 증거가 아니다. 증거는 spec.md의 ID 목록, 그리고 검사 명령의 출력이다 (H9).

### 버전 (R17)
- 이 skill과 가이드는 `{PKG}@{ver}`로 고정되어 있다. `@latest`로 바꿔 실행하지 않는다.
- 업데이트 경고가 나와도 사용자를 설득하지 않는다. 경고 내용을 그대로 보고만 한다. 버전을 올리는 일은 사람의 변경이다.

### 레거시 패턴 검사 (R15)
- 프런트엔드 파일을 고치면 훅이 `legacy-scan`을 고정 버전으로 돌린다. 직접 돌리지 않아도 된다.
- 검출이 오탐이라고 판단되면(이미 대체 코드가 있음, 외부 코드, 비슷하지만 다른 패턴) 검사를 통과시키려고 코드를 비틀지 않는다. 멈추고 보고한다. 받아들일 검출은 사람이 `hold.toml`의 `[web].legacy_allow`에 적는다.

### 범위
- 백엔드(Python, SQL, LangGraph, 인프라)에는 쓰지 않는다. 위 "DO NOT trigger" 목록과 같다.
"""


def transform_skill(text: str, web: dict, skill_version: str) -> str:
    ver = web["mwg_version"]
    count = text.count(LATEST)
    if count == 0:
        raise SyncError(
            f"MWG SKILL.md 에서 '{LATEST}' 를 찾지 못했습니다. 원본 형식이 바뀌었을 수 있습니다. "
            "hold_web_sync.py 의 변환 규칙을 확인하세요 (방법론 9장 '알려진 한계')."
        )
    out = text.replace(LATEST, f"{PKG}@{ver}")
    if not web["telemetry"]:
        out = re.sub(r"(?<!DISABLE_TELEMETRY=1 )\b(npx -y |pnpx )(" + re.escape(PKG) + r"@)", r"DISABLE_TELEMETRY=1 \1\2", out)
    notice = (
        f"<!-- hold-kit: hold_web_sync.py 가 {PKG}@{ver} (skill {skill_version}) 에서 생성했습니다. "
        "원본: Google LLC, Apache-2.0 (같은 폴더의 LICENSE). "
        f"변경: '@latest' 를 '@{ver}' 로 고정"
        + (", 텔레메트리 끔(DISABLE_TELEMETRY=1)" if not web["telemetry"] else "")
        + ", 끝에 'HOLD 프로젝트 규칙' 절 추가. 보호 경로이므로 손으로 고치지 말고 스크립트로 다시 만드세요. -->\n"
    )
    m = re.match(r"^---\n.*?\n---\n", out, re.S)
    if m:
        out = out[: m.end()] + "\n" + notice + out[m.end():]
    else:
        out = notice + out
    return out.rstrip("\n") + hold_section(web)


def fetch_tarball(ver: str, dest: Path) -> Path:
    npm = shutil.which("npm")
    if not npm:
        raise SyncError("npm 이 없습니다. Node.js 22 이상을 설치하거나 --tarball 로 미리 받은 패키지를 지정하세요")
    res = subprocess.run([npm, "pack", f"{PKG}@{ver}", "--pack-destination", str(dest)],
                         capture_output=True, text=True)
    if res.returncode != 0:
        raise SyncError(f"npm pack {PKG}@{ver} 실패: {(res.stderr or res.stdout).strip()[-300:]}")
    found = sorted(dest.glob(f"{PKG}-*.tgz"))
    if not found:
        raise SyncError("npm pack 결과 파일을 찾지 못했습니다")
    return found[-1]


def read_members(tarball: Path) -> dict[str, str]:
    """필요한 파일만 메모리로 읽는다 (디스크에 풀지 않음)."""
    out: dict[str, str] = {}
    with tarfile.open(tarball, "r:gz") as tf:
        for key, name in MEMBERS.items():
            try:
                fh = tf.extractfile(name)
            except KeyError:
                fh = None
            if fh is None:
                raise SyncError(f"패키지에 {name} 이(가) 없습니다. MWG 패키지 구조가 바뀌었을 수 있습니다")
            out[key] = fh.read().decode("utf-8")
    return out


def package_version(tarball: Path) -> str | None:
    with tarfile.open(tarball, "r:gz") as tf:
        try:
            fh = tf.extractfile("package/package.json")
        except KeyError:
            return None
        return json.loads(fh.read().decode("utf-8")).get("version") if fh else None


def sync(root: Path, tarball: Path | None) -> list[str]:
    cfg = load_config(root)
    web = web_settings(cfg)
    ver = web["mwg_version"]
    with tempfile.TemporaryDirectory() as tmp:
        tgz = tarball or fetch_tarball(ver, Path(tmp))
        pkg_ver = package_version(tgz)
        if pkg_ver and pkg_ver != ver:
            raise SyncError(f"패키지 버전 {pkg_ver} 이(가) hold.toml 의 mwg_version {ver} 과 다릅니다")
        m = read_members(tgz)
    skill_version = m["skill_version"].strip()
    guides = json.loads(m["guides"])
    ids = sorted({g["id"] for g in guides if isinstance(g, dict) and g.get("id")})
    if not ids:
        raise SyncError("가이드 목록이 비어 있습니다")

    written = []
    skill_dir = root / SKILL_DIR
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(transform_skill(m["skill"], web, skill_version), encoding="utf-8")
    (skill_dir / "LICENSE").write_text(m["license"], encoding="utf-8")
    written += [f"{SKILL_DIR}/SKILL.md", f"{SKILL_DIR}/LICENSE"]

    gp = guides_path(root, cfg)
    gp.parent.mkdir(parents=True, exist_ok=True)
    index = {
        "mwg_version": ver,
        "skill_version": skill_version,
        "generated_by": "hold_web_sync.py",
        "count": len(ids),
        "guides": [{"id": g["id"], "category": g.get("category", ""), "description": g.get("description", "")}
                   for g in sorted(guides, key=lambda g: g.get("id", "")) if isinstance(g, dict) and g.get("id")],
    }
    gp.write_text(json.dumps(index, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    written.append(gp.relative_to(root).as_posix())
    return written


def check(root: Path) -> list[str]:
    """설치본이 hold.toml 의 고정 버전과 일치하는지 (읽기 전용). 문제 목록을 돌려준다."""
    cfg = load_config(root)
    web = web_settings(cfg)
    if not web["enabled"]:
        return []
    ver = web["mwg_version"]
    problems = []
    skill = root / SKILL_DIR / "SKILL.md"
    if not skill.exists():
        problems.append(f"{SKILL_DIR}/SKILL.md 가 없습니다. 사람이 python scripts/hold_web_sync.py 를 실행하세요")
    else:
        text = skill.read_text(encoding="utf-8")
        m = NOTICE_RE.search(text)
        if not m:
            problems.append(f"{SKILL_DIR}/SKILL.md 가 hold_web_sync.py 로 만든 파일이 아닙니다 (MWG 플러그인 원본이거나 손으로 고친 파일)")
        elif m.group(1) != ver:
            problems.append(f"설치된 skill 은 {m.group(1)}, hold.toml 은 {ver} 입니다. hold_web_sync.py 를 다시 실행하세요")
        if LATEST in text:
            problems.append(f"{SKILL_DIR}/SKILL.md 에 '{LATEST}' 가 남아 있습니다 (버전 고정 위반, R17)")
    gp = guides_path(root, cfg)
    if not gp.exists():
        problems.append(f"{gp.relative_to(root).as_posix()} 가 없습니다. hold_web_sync.py 를 실행하세요")
    else:
        try:
            got = json.loads(gp.read_text(encoding="utf-8")).get("mwg_version")
        except json.JSONDecodeError:
            got = None
        if got != ver:
            problems.append(f"가이드 목록은 {got}, hold.toml 은 {ver} 입니다. hold_web_sync.py 를 다시 실행하세요")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="HOLD 웹 확장: MWG 고정 버전 설치·검사")
    ap.add_argument("--root", type=Path, default=Path(os.environ.get("CLAUDE_PROJECT_DIR") or "."))
    ap.add_argument("--tarball", type=Path, help="미리 받은 modern-web-guidance-<버전>.tgz (npm pack 결과)")
    ap.add_argument("--check", action="store_true", help="설치본과 hold.toml 의 버전 일치만 검사 (읽기 전용)")
    args = ap.parse_args(argv)
    root = args.root.resolve()

    if args.check:
        problems = check(root)
        for p in problems:
            print("FAIL " + p)
        if not problems:
            print("OK  웹 확장 고정 버전 검사 통과 (또는 확장 꺼짐)")
        return 1 if problems else 0

    # R17: 버전 설치·변경은 사람의 일. Claude Code 의 Bash 도구 안에서는 실행하지 않는다 (휴리스틱).
    if os.environ.get("CLAUDECODE"):
        print("이 스크립트는 사람이 실행합니다 (HOLD R17). 에이전트는 멈추고, 어떤 버전으로 왜 바꿔야 하는지 보고하세요.",
              file=sys.stderr)
        return 1
    try:
        written = sync(root, args.tarball.resolve() if args.tarball else None)
    except SyncError as e:
        print(f"FAIL {e}", file=sys.stderr)
        return 1
    cfg = load_config(root)
    web = web_settings(cfg)
    print(f"MWG {PKG}@{web['mwg_version']} 를 고정 설치했습니다:")
    for w in written:
        print(f"  - {w}")
    if not web["enabled"]:
        print("  ! hold.toml 의 [web].enabled 가 false 입니다. 확장을 쓰려면 true 로 바꾸세요")
    print(
        "\n다음 할 일\n"
        "  1. 위 파일을 검토하고 사람이 커밋한다 (보호 경로)\n"
        "  2. Claude Code 를 다시 시작해 skill 을 불러온다\n"
        "  3. 같은 skill 의 MWG 플러그인이 전역으로 설치되어 있으면 이 프로젝트에서는 끈다 (@latest 원본과 겹침)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
