#!/usr/bin/env python3
"""HOLD 웹 확장 web-0.1 — Modern Web Guidance 고정 버전 설치 (사람이 실행, R17).

hold.toml [web] 의 mwg_version·mwg_integrity 로 패키지를 검증한 뒤, 정책과 함께 다음을 만듭니다.
  .claude/skills/modern-web-guidance/SKILL.md, LICENSE   고정 skill + "HOLD 프로젝트 규칙" 절
  .mwgrc                                                 MWG 자체 정책 파일 (hold.toml 에서 생성)
  docs/hold/web/guides.json                              가이드 ID 목록 (R16 대조)
  docs/hold/web/lock.json                                생성물 해시와 정책 (web_check.py 가 대조)

  python .claude/hold-web/sync.py --pin 1.0.0             # 버전을 정하고(npm 의 무결성 값 기록) 설치
  python .claude/hold-web/sync.py                         # hold.toml 그대로 다시 설치 (정책을 바꾼 뒤)
  python .claude/hold-web/sync.py --tarball mwg-1.0.0.tgz # 미리 받은 패키지로 (폐쇄망)
  python .claude/hold-web/sync.py --pin 1.0.0 --tarball mwg-1.0.0.tgz   # 폐쇄망에서 처음 고정 (무결성은 파일에서 계산)

설치는 무결성 값이 맞는 패키지로만 됩니다. 같은 입력이면 같은 바이트가 나오므로,
누가 실행하든 hold.toml(사람 소유) 이 허락한 결과만 만들어집니다.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c  # noqa: E402


def set_web_keys(root: Path, updates: dict[str, str]) -> None:
    """hold.toml 의 [web] 표에서 키 값을 바꾼다 (없으면 표 끝에 더함). 사람이 실행할 때만 쓰인다."""
    f = root / "hold.toml"
    text = f.read_text(encoding="utf-8")
    m = re.search(r"^\[web\]\s*$", text, re.M)
    if not m:
        raise c.SyncError("hold.toml 에 [web] 표가 없습니다. extensions/web/install.py 로 먼저 설치하세요")
    nxt = re.search(r"^\[", text[m.end():], re.M)
    end = m.end() + (nxt.start() if nxt else len(text) - m.end())
    block = text[m.end():end]
    for k, v in updates.items():
        line = f'{k} = "{v}"'
        if re.search(rf"^{k}\s*=.*$", block, re.M):
            block = re.sub(rf"^{k}\s*=.*$", line, block, count=1, flags=re.M)
        else:
            block = block.rstrip("\n") + "\n" + line + "\n"
    f.write_text(text[: m.end()] + block + text[end:], encoding="utf-8")


def npm_integrity(version: str) -> str:
    npm = shutil.which("npm")
    if not npm:
        raise c.SyncError("npm 이 없습니다. --tarball 로 미리 받은 패키지를 함께 주세요")
    res = subprocess.run([npm, "view", f"{c.PKG}@{version}", "dist.integrity"], capture_output=True, text=True, timeout=60)
    val = res.stdout.strip()
    if res.returncode != 0 or not val.startswith("sha512-"):
        raise c.SyncError(f"npm 에서 {c.PKG}@{version} 의 무결성 값을 얻지 못했습니다: {(res.stderr or val)[-200:]}")
    return val


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="HOLD 웹 확장: MWG 고정 버전 설치 (사람이 실행)")
    ap.add_argument("--root", type=Path, default=c.project_root())
    ap.add_argument("--tarball", type=Path, help="미리 받은 modern-web-guidance-<버전>.tgz")
    ap.add_argument("--pin", metavar="VERSION", help="고정 버전을 정하고 무결성 값을 hold.toml 에 적는다")
    args = ap.parse_args(argv)
    if "CLAUDECODE" in os.environ:
        print("이 스크립트는 사람이 실행합니다 (HOLD R17). 에이전트는 멈추고, 어떤 버전·정책으로 왜 바꿔야 하는지 보고하세요.",
              file=sys.stderr)
        return 1
    root = args.root.resolve()
    try:
        data_from_file = args.tarball.read_bytes() if args.tarball else None
        if args.pin:
            if not re.fullmatch(r"\d+\.\d+\.\d+", args.pin):
                raise c.SyncError("--pin 은 1.2.3 형식의 정확한 버전입니다")
            integrity = c.sri(data_from_file) if data_from_file else npm_integrity(args.pin)
            set_web_keys(root, {"mwg_version": args.pin, "mwg_integrity": integrity})
            if data_from_file:
                print("주의: 무결성 값을 주어진 파일에서 계산했습니다. 그 파일을 신뢰할 수 있는 경로로 받았는지 확인하세요.")
        cfg = c.load_toml(root)
        w, errors = c.web_config(cfg)
        if errors:
            raise c.SyncError("hold.toml [web] 설정 오류:\n- " + "\n- ".join(errors))
        if not w["mwg_integrity"]:
            raise c.SyncError("[web].mwg_integrity 가 비어 있습니다. --pin <버전> 으로 고정하세요")
        data = data_from_file or c.obtain_tarball(w, None, offline_only=False)
        if data is None:
            raise c.SyncError(f"{c.PKG}@{w['mwg_version']} 패키지를 얻지 못했습니다 (npm, 네트워크 확인 또는 --tarball)")
        if c.sri(data) != w["mwg_integrity"]:
            raise c.SyncError("패키지의 무결성 값이 hold.toml 의 mwg_integrity 와 다릅니다. 설치를 멈춥니다")
        files = c.render(c.read_tarball(data), w)
    except c.SyncError as e:
        print(f"FAIL {e}", file=sys.stderr)
        return 1
    for rel, b in files.items():
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(b)
    print(f"{c.PKG}@{w['mwg_version']} 를 고정 설치했습니다 (무결성 확인):")
    for rel in files:
        print(f"  - {rel}")
    if not w["enabled"]:
        print("  ! hold.toml [web].enabled 가 false 입니다")
    print("\n다음 할 일\n"
          "  1. 생성물을 검토하고 사람이 커밋한다 (모두 보호 경로)\n"
          "  2. python .claude/hold-web/web_check.py 가 통과하는지 본다\n"
          "  3. Claude Code 를 다시 시작해 skill 을 불러온다. MWG 플러그인이 전역에 있으면 이 프로젝트에서는 끈다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
