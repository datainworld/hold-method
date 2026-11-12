#!/usr/bin/env python3
"""HOLD 웹 확장 web-0.1 — Modern Web Guidance 실행 래퍼 (에이전트가 쓰는 유일한 실행 경로, R17).

  python .claude/hold-web/mwg.py search "light dismiss dialog"
  python .claude/hold-web/mwg.py retrieve "dialog,light-dismiss-a-dialog"
  python .claude/hold-web/mwg.py list
  python .claude/hold-web/mwg.py legacy-scan web/ --json

하는 일
  1. 사본 확인: .hold/web-pkg/ 의 사본이 sync.py 가 무결성을 확인하고 lock.json 에 기록한 것과 같은지 대조
  2. 하위 명령 제한: search, retrieve, list, legacy-scan 만
  3. 텔레메트리 강제 끔 (hold.toml [web].telemetry = false 일 때), 프로젝트 루트에서 실행 (.mwgrc 가 루트 것으로 정해짐)
  4. retrieve 의 증거 기록: 자기 출력(파일로 저장된 출력 포함)에서 요청한 ID 중 실제로 나온 것만 훅 로그에 남김 (H9)
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    root = c.project_root()
    cfg = c.load_toml(root)
    w, errors = c.web_config(cfg)
    if errors:
        print("hold.toml [web] 설정 오류 (사람이 고쳐야 합니다):\n- " + "\n- ".join(errors), file=sys.stderr)
        return 2
    if not w["enabled"]:
        print("웹 확장이 꺼져 있습니다 (hold.toml [web].enabled).", file=sys.stderr)
        return 2
    sub, rest = c.first_positional(args)
    if sub not in c.ALLOWED_SUBCOMMANDS:
        print(f"하위 명령은 {', '.join(c.ALLOWED_SUBCOMMANDS)} 만 쓸 수 있습니다 (R17). "
              "정책·설정·버전은 사람이 hold.toml 과 sync.py 로 바꿉니다.", file=sys.stderr)
        c.log(root, {"hook": "web_guard", "tool": "mwg.py", "reason": f"sub={sub}"})
        return 2
    cli, err = c.verify_package(root, w)
    if err:
        print(err, file=sys.stderr)
        return 2
    if sub in ("search", "retrieve") and "--skill-version" not in args and not any(a.startswith("--skill-version=") for a in args):
        sv = c.skill_version_of(root, w)
        if sv:
            args += ["--skill-version", sv]
    cmd = c.node_command(cli, args)
    if cmd is None:
        print("node 가 없습니다 (Node.js 22 이상 필요).", file=sys.stderr)
        return 2
    start = time.time()
    res = subprocess.run(cmd, cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace",
                         env=c.mwg_env(w))
    sys.stdout.write(res.stdout)
    sys.stderr.write(res.stderr)
    if sub == "retrieve":
        ids_arg, _ = c.first_positional(rest)
        requested = [i.strip() for i in (ids_arg or "").split(",") if i.strip()]
        found = set(c.GUIDE_MARK.findall(res.stdout))
        for p in c.SAVED_TO.findall(res.stdout):
            fp = Path(p.rstrip(".,"))
            try:
                if fp.name.startswith("mwg-guide-") and fp.stat().st_mtime >= start - 1:
                    found |= set(c.GUIDE_MARK.findall(fp.read_text(encoding="utf-8", errors="replace")))
            except OSError:
                pass
        known = c.known_guides(root)
        confirmed = sorted(i for i in requested if i in found and i in known)
        c.log(root, {"hook": "web_guidance", "action": "retrieve", "requested": requested, "confirmed": confirmed,
                     "mwg_version": w["mwg_version"], "rc": res.returncode})
    return res.returncode


if __name__ == "__main__":
    sys.exit(main())
