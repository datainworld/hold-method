"""웹 확장 테스트 공통 — 가짜 npx·npm, 가짜 MWG 패키지, 설치된 프로젝트 픽스처.

네트워크 없이 돌고, Windows 에서도 돌도록 가짜 실행 파일은 .cmd 로도 만듭니다.
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
EXT = REPO / "extensions" / "web"
CORE_INIT = REPO / "kit" / "scripts" / "hold_init.py"

SKILL_SRC = """---
name: modern-web-guidance
description: |
  Search tool for modern web development best practices.
---

# Modern Web Guidance

```sh
npx -y modern-web-guidance@latest search "<query>" --skill-version 2026_11_09-test
npx -y modern-web-guidance@latest retrieve "<id>"
```

- **Reactive Policy Discovery**: Suggest documenting a policy in `AGENTS.md` or `CLAUDE.md`.
- allowlist `npx -y modern-web-guidance@latest *` (or `pnpx modern-web-guidance@latest *`)
"""
GUIDES = [
    {"id": "dialog", "description": "Build a dialog", "category": "html"},
    {"id": "light-dismiss-a-dialog", "description": "Light dismiss", "category": "ui-behaviors"},
    {"id": "ime-safe-enter-submit", "description": "IME-safe enter", "category": "forms"},
]
LEGACY = "el.addEventListener('keydown', e => { if (e.key === 'Enter') send(); });\n"

# 가짜 node: 래퍼·검사가 "node <사본>/modern-web.mjs <하위 명령> …" 으로 부르면 MWG 처럼 응답한다
FAKE_NODE = r'''
import json, os, sys
args = sys.argv[2:]          # argv[1] = modern-web.mjs 경로
log = os.environ.get("FAKE_LOG")
if log:
    with open(log, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"cli": sys.argv[1], "args": args,
                             "telemetry_off": os.environ.get("DISABLE_TELEMETRY") == "1"}) + "\n")
mode = os.environ.get("FAKE_SCAN")
if "legacy-scan" in args:
    if mode == "error":
        print(json.dumps({"totalFindings": 0, "guides": [], "error": "Unknown option"})); sys.exit(0)
    if mode == "garbage":
        print("not json"); sys.exit(0)
    target = args[args.index("legacy-scan") + 1]
    findings = []
    for dp, _, fns in os.walk(target):
        for fn in fns:
            p = os.path.join(dp, fn)
            if "e.key === 'Enter'" in open(p, encoding="utf-8", errors="replace").read():
                findings.append({"file": os.path.relpath(p, target).replace(os.sep, "/"), "line": 1,
                                 "message": "Keydown Enter without isComposing"})
    guides = [{"guideId": "ime-safe-enter-submit", "count": len(findings),
               "rules": [{"ruleId": "ime-safe-enter-submit", "findings": findings}]}] if findings else []
    print(json.dumps({"totalFindings": len(findings), "guides": guides}))
elif "retrieve" in args:
    ids = args[args.index("retrieve") + 1].split(",")
    print("\n".join(f"--- Guide for {i} ---\n# {i}\n" for i in ids if i != "made-up"))
elif "search" in args:
    print(json.dumps([{"id": "dialog", "description": "x"}]))
'''


def make_tarball(path: Path, *, version: str = "1.0.0", skill: str = SKILL_SRC, extra: str = "") -> Path:
    files = {
        "package/package.json": json.dumps({"name": "modern-web-guidance", "version": version}),
        "package/LICENSE": "Apache License 2.0 (test copy)" + extra,
        "package/skills/modern-web-guidance/SKILL.md": skill,
        "package/skills/modern-web-guidance/skill-version.txt": "2026_11_09-test\n",
        "package/skills/modern-web-guidance/gen/guides.json": json.dumps(GUIDES),
        "package/skills/modern-web-guidance/modern-web.mjs": "// fake cli",
    }
    with tarfile.open(path, "w:gz") as tf:
        for name, text in files.items():
            data = text.encode("utf-8")
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mtime = 0
            tf.addfile(info, io.BytesIO(data))
    return path


def _exe(d: Path, name: str, src: str) -> None:
    script = d / f"fake_{name}.py"
    script.write_text(src, encoding="utf-8")
    if os.name == "nt":
        (d / f"{name}.cmd").write_text(f'@"{sys.executable}" "{script}" %*\r\n', encoding="utf-8")
    else:
        sh = d / name
        sh.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8")
        sh.chmod(0o755)


def clean_env(**extra: str) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "DISABLE_TELEMETRY", "CLAUDE_PROJECT_DIR")}
    env.update(extra)
    return env


def write(root: Path, rel: str, text: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def set_toml(root: Path, old: str, new: str) -> None:
    f = root / "hold.toml"
    t = f.read_text(encoding="utf-8")
    assert old in t, old
    f.write_text(t.replace(old, new, 1), encoding="utf-8")


class Proj:
    def __init__(self, root: Path, bin_dir: Path, tmp: Path, tarball: Path):
        self.root, self.bin, self.tmp, self.tarball = root, bin_dir, tmp, tarball
        self.calls = tmp / "node_calls.jsonl"

    def env(self, path: list[Path] | None = None, **extra: str) -> dict:
        dirs = path if path is not None else [self.bin]
        env = clean_env(CLAUDE_PROJECT_DIR=str(self.root), PATH=os.pathsep.join(map(str, dirs)),
                        FAKE_LOG=str(self.calls), **extra)
        if os.name == "nt":
            env["PATHEXT"] = os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD")
            env["SYSTEMROOT"] = os.environ.get("SYSTEMROOT", "")
        return env

    def hook(self, payload: dict, path: list[Path] | None = None, **extra: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(self.root / ".claude/hooks/web_guard.py")], input=json.dumps(payload),
                              capture_output=True, text=True, cwd=self.root, env=self.env(path, **extra))

    def pre(self, tool: str, **ti) -> subprocess.CompletedProcess:
        return self.hook({"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": ti})

    def post(self, tool: str, response=None, **ti) -> subprocess.CompletedProcess:
        return self.hook({"hook_event_name": "PostToolUse", "tool_name": tool, "tool_input": ti,
                          "tool_response": response or {}})

    def run(self, script: str, *args: str, path: list[Path] | None = None, **extra: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(self.root / ".claude/hold-web" / script), "--root", str(self.root), *args],
                              capture_output=True, text=True, cwd=self.root, env=self.env(path, **extra))

    def log(self, hook: str) -> list[dict]:
        f = self.root / ".hold/logs/hooks.jsonl"
        if not f.exists():
            return []
        return [r for r in map(json.loads, f.read_text(encoding="utf-8").splitlines()) if r.get("hook") == hook]

    def check(self, *args: str, **extra: str) -> subprocess.CompletedProcess:
        return self.run("web_check.py", *args, **extra)


def core_init(root: Path, profile: str) -> None:
    subprocess.run([sys.executable, str(CORE_INIT), "--target", str(root), "--profile", profile],
                   check=True, capture_output=True, text=True)


def ext_install(root: Path, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(EXT / "install.py"), "--target", str(root), "--since", "20261112", *args],
                          capture_output=True, text=True, env=env or clean_env())


@pytest.fixture
def fake_bin(tmp_path: Path) -> Path:
    d = tmp_path / "fakebin"
    d.mkdir()
    _exe(d, "node", FAKE_NODE)
    return d


def sri_of(path: Path) -> str:
    import base64
    import hashlib
    return "sha512-" + base64.b64encode(hashlib.sha512(path.read_bytes()).digest()).decode()


def sync_cmd(root: Path, *args: str) -> list[str]:
    return [sys.executable, str(root / ".claude/hold-web/sync.py"), "--root", str(root), *args]


def build(tmp_path: Path, fake_bin: Path, profile: str = "standard", ready: bool = True) -> Proj:
    root = tmp_path / "proj"
    core_init(root, profile)
    res = ext_install(root)
    assert res.returncode == 0, res.stderr
    tarball = make_tarball(tmp_path / "mwg-1.0.0.tgz")
    p = Proj(root, fake_bin, tmp_path, tarball)
    if ready:
        res = subprocess.run(sync_cmd(root, "--pin", "1.0.0", "--tarball", str(tarball), "--integrity", sri_of(tarball)),
                             capture_output=True, text=True, env=clean_env())
        assert res.returncode == 0, res.stderr
        usage = root / "docs/architecture/usage-environments.md"
        usage.write_text(usage.read_text(encoding="utf-8").replace(
            "<사용 환경 — 예: 기관 내부망, 관리형 Edge 최신 / 시민, 모바일 Safari·삼성 인터넷>", "시민, 모바일 Chrome 최신"), encoding="utf-8")
        snippet = (EXT / "kit/templates/pre-commit-snippet.yaml").read_text(encoding="utf-8")
        pc = root / ".pre-commit-config.yaml"
        pc.write_text(pc.read_text(encoding="utf-8").rstrip("\n") + "\n" + snippet, encoding="utf-8")
        p.pre("Bash", command="ls")   # 지속 스냅샷의 기준을 만든다 (처음 훅은 기준만 남김)
    return p


@pytest.fixture
def proj(tmp_path: Path, fake_bin: Path) -> Proj:
    """코어 v0.1 (standard) + 웹 확장 설치 + 가짜 패키지로 고정 + 사람이 할 일을 마친 프로젝트."""
    return build(tmp_path, fake_bin)
