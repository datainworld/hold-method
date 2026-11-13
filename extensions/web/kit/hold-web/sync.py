#!/usr/bin/env python3
"""HOLD 웹 확장 web-0.1 — Modern Web Guidance 고정 설치 (사람·CI 가 실행, R17).

hold.toml [web] 의 mwg_version·mwg_integrity 로 패키지를 검증해 사본을 두고, 정책과 함께 생성물을 만듭니다.
  .hold/web-pkg/<버전>/, <패키지>.tgz                    검증된 사본 (Git 밖. 래퍼·검사가 이것만 실행)
  .claude/skills/modern-web-guidance/SKILL.md, LICENSE   고정 skill (실행 명령은 래퍼로) + "HOLD 프로젝트 규칙" 절
  .mwgrc                                                 MWG 정책 파일 (hold.toml 에서 생성)
  docs/hold/web/guides.json, lock.json                   가이드 ID 목록, 생성물·사본 해시와 정책

  python .claude/hold-web/sync.py --pin 1.0.0                        # npm 에서 무결성 값을 받아 hold.toml 에 적고 설치
  python .claude/hold-web/sync.py                                    # hold.toml 그대로 다시 설치 (정책을 바꾼 뒤)
  python .claude/hold-web/sync.py --tarball mwg.tgz                  # 미리 받은 패키지로 (폐쇄망)
  python .claude/hold-web/sync.py --pin 1.0.0 --tarball mwg.tgz --integrity sha512-…   # 폐쇄망에서 처음 고정
  python .claude/hold-web/sync.py --fetch-only                       # 사본만 받아 검증 (CI: 이어서 web_check.py)

무결성 값은 사람이 신뢰할 수 있는 경로(npm 레지스트리)에서 얻은 것만 씁니다. 파일에서 계산하지 않습니다.
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
        raise c.SyncError("npm 이 없습니다. 폐쇄망이면 --tarball 과 --integrity 를 함께 주세요")
    res = subprocess.run([npm, "view", f"{c.PKG}@{version}", "dist.integrity"], capture_output=True, text=True, timeout=60)
    val = res.stdout.strip()
    if res.returncode != 0 or not val.startswith("sha512-"):
        raise c.SyncError(f"npm 에서 {c.PKG}@{version} 의 무결성 값을 얻지 못했습니다: {(res.stderr or val)[-200:]}")
    return val


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="HOLD 웹 확장: MWG 고정 설치 (사람·CI 가 실행)")
    ap.add_argument("--root", type=Path, default=c.project_root())
    ap.add_argument("--tarball", type=Path, help="미리 받은 modern-web-guidance-<버전>.tgz")
    ap.add_argument("--pin", metavar="VERSION", help="고정 버전을 정하고 무결성 값을 hold.toml 에 적는다")
    ap.add_argument("--integrity", help="--pin 과 함께: npm 의 dist.integrity 값 (폐쇄망에서 사람이 따로 받아 온 값)")
    ap.add_argument("--fetch-only", action="store_true", help="검증된 사본만 받는다 (생성물은 그대로)")
    args = ap.parse_args(argv)
    if "CLAUDECODE" in os.environ:
        print("이 스크립트는 사람이 실행합니다 (HOLD R17). 에이전트는 멈추고, 어떤 버전·정책으로 왜 바꿔야 하는지 보고하세요.",
              file=sys.stderr)
        return 1
    root = args.root.resolve()
    try:
        if args.pin:
            if not re.fullmatch(r"\d+\.\d+\.\d+", args.pin):
                raise c.SyncError("--pin 은 1.2.3 형식의 정확한 버전입니다")
            integrity = args.integrity or npm_integrity(args.pin)
            if not re.fullmatch(r"sha512-[A-Za-z0-9+/]+=*", integrity):
                raise c.SyncError("--integrity 는 'sha512-…' 값이어야 합니다")
            set_web_keys(root, {"mwg_version": args.pin, "mwg_integrity": integrity})
        elif args.integrity:
            raise c.SyncError("--integrity 는 --pin 과 함께만 씁니다")
        cfg = c.load_toml(root)
        w, errors = c.web_config(cfg)
        if errors:
            raise c.SyncError("hold.toml [web] 설정 오류:\n- " + "\n- ".join(errors))
        if not w["mwg_integrity"]:
            raise c.SyncError("[web].mwg_integrity 가 비어 있습니다. --pin <버전> 으로 고정하세요")
        data = c.fetch(w, args.tarball)
        if data is None:
            raise c.SyncError(f"{c.PKG}@{w['mwg_version']} 패키지를 얻지 못했습니다 (npm·네트워크 확인, 또는 --tarball)")
        tree = c.store_package(root, w, data)       # 무결성이 다르면 여기서 멈춤
        if args.fetch_only:
            print(f"검증된 사본을 받았습니다: {c.PKG_STORE}/{w['mwg_version']} (트리 {tree[:12]}…)")
            return 0
        files = c.render(c.tar_files(data), w)
    except c.SyncError as e:
        print(f"FAIL {e}", file=sys.stderr)
        return 1
    for rel, b in files.items():
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(b)
    print(f"{c.PKG}@{w['mwg_version']} 를 고정 설치했습니다 (무결성 확인):")
    for rel in [f"{c.PKG_STORE}/{w['mwg_version']}/ (Git 밖)", *files]:
        print(f"  - {rel}")
    print("\n다음 할 일\n"
          "  1. 생성물을 검토하고 사람이 커밋한다 (모두 보호 경로)\n"
          "  2. python .claude/hold-web/web_check.py 가 통과하는지 본다\n"
          "  3. Claude Code 를 다시 시작해 skill 을 불러온다. MWG 플러그인이 전역에 있으면 이 프로젝트에서는 끈다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
