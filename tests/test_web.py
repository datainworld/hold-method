"""웹 프런트엔드 확장 (방법론 9장, R14~R17) — 장치가 위반을 잡고 정상 작업은 통과시키는지.

네트워크 없이 돌도록 가짜 npx 와 가짜 MWG 패키지(tarball)를 씁니다.
실제 modern-web-guidance 패키지와의 통합은 method-adr/0002 의 '통합 확인' 절에 기록합니다.
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

from conftest import KIT, write

SKILL_SRC = """---
name: modern-web-guidance
description: |
  Search tool for modern web development best practices.
---

# Modern Web Guidance

```sh
npx -y modern-web-guidance@latest search "<query>" --skill-version 2026_11_09-test
```

```sh
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
SCAN_HIT = {
    "targetDir": "x", "totalFindings": 1,
    "guides": [{
        "guideId": "ime-safe-enter-submit",
        "retrieveCommand": "npx modern-web-guidance retrieve ime-safe-enter-submit",
        "count": 1,
        "rules": [{"ruleId": "ime-safe-enter-submit", "summary": "s", "count": 1,
                   "findings": [{"file": "app.js", "line": 3,
                                 "message": "Keydown Enter listener without event.isComposing"}]}],
    }],
}
FAKE_NPX = r'''
import json, os, sys
log = os.environ.get("FAKE_NPX_LOG")
if log:
    with open(log, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"args": sys.argv[1:], "telemetry_off": os.environ.get("DISABLE_TELEMETRY") == "1"}) + "\n")
if "legacy-scan" in sys.argv:
    path = os.environ.get("FAKE_SCAN_JSON")
    print(open(path, encoding="utf-8").read() if path else json.dumps({"guides": []}))
'''
INTENT = "# Intent\n## 이해관계자\n- SH-U01\n"
SEQ = "```mermaid\nsequenceDiagram\n    U->>C: 요청\n    alt 정상\n        C-->>U: 응답\n    else 실패\n        C-->>U: 안내\n    end\n```"


def spec(refs: str) -> str:
    return (f"# Spec\n## 이해관계자 영향\n| ID | 방향 | 내용 | 승인 |\n|---|---|---|---|\n| SH-U01 | → | x | 아니오 |\n"
            f"## 참조 가이드\n{refs}\n## 뷰\n누구의 어떤 질문: 엔지니어 — 실패하면?\n{SEQ}\n"
            "생략: 컴포넌트 변화 없음\n")  # web 픽스처는 standard 라 컴포넌트 뷰가 필수


def make_tarball(path: Path, *, version: str = "1.0.0", skill: str = SKILL_SRC) -> Path:
    files = {
        "package/package.json": json.dumps({"name": "modern-web-guidance", "version": version}),
        "package/LICENSE": "Apache License 2.0 (test copy)",
        "package/skills/modern-web-guidance/SKILL.md": skill,
        "package/skills/modern-web-guidance/skill-version.txt": "2026_11_09-test\n",
        "package/skills/modern-web-guidance/gen/guides.json": json.dumps(GUIDES),
    }
    with tarfile.open(path, "w:gz") as tf:
        for name, text in files.items():
            data = text.encode("utf-8")
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return path


def clean_env(**extra: str) -> dict:
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    env.update(extra)
    return env


@pytest.fixture
def fake_bin(tmp_path: Path) -> Path:
    """PATH 맨 앞에 둘 가짜 npx (posix 는 셸 스크립트, Windows 는 .cmd)."""
    d = tmp_path / "fakebin"
    d.mkdir()
    script = d / "fake_npx.py"
    script.write_text(FAKE_NPX, encoding="utf-8")
    if os.name == "nt":
        (d / "npx.cmd").write_text(f'@"{sys.executable}" "{script}" %*\r\n', encoding="utf-8")
    else:
        sh = d / "npx"
        sh.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8")
        sh.chmod(0o755)
    return d


def init(tmp_path: Path, *args: str) -> Path:
    root = tmp_path / "webproj"
    subprocess.run([sys.executable, str(KIT / "scripts/hold_init.py"), "--target", str(root), *args],
                   check=True, capture_output=True, text=True)
    return root


def set_toml(root: Path, old: str, new: str) -> None:
    f = root / "hold.toml"
    text = f.read_text(encoding="utf-8")
    assert old in text, old
    f.write_text(text.replace(old, new, 1), encoding="utf-8")


def sync(root: Path, tarball: Path, *extra: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(root / "scripts/hold_web_sync.py"), "--root", str(root),
                           "--tarball", str(tarball), *extra], capture_output=True, text=True, env=env or clean_env())


def hook(root: Path, name: str, payload: dict, path_dirs: list[Path], **env_extra: str) -> subprocess.CompletedProcess:
    env = clean_env(CLAUDE_PROJECT_DIR=str(root), PATH=os.pathsep.join(str(p) for p in path_dirs), **env_extra)
    if os.name == "nt":
        env["PATHEXT"] = os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD")
    return subprocess.run([sys.executable, str(root / ".claude/hooks" / name)], input=json.dumps(payload),
                          capture_output=True, text=True, cwd=root, env=env)


def hook_log(root: Path, name: str) -> list[dict]:
    f = root / ".hold/logs/hooks.jsonl"
    if not f.exists():
        return []
    return [r for r in map(json.loads, f.read_text(encoding="utf-8").splitlines()) if r.get("hook") == name]


@pytest.fixture
def web(tmp_path: Path, fake_bin: Path):
    """웹 확장을 켜고 가짜 패키지로 고정 버전을 설치한 standard 프로젝트."""
    root = init(tmp_path, "--profile", "standard", "--web")
    res = sync(root, make_tarball(tmp_path / "mwg.tgz"))
    assert res.returncode == 0, res.stderr
    scan = tmp_path / "scan.json"
    scan.write_text(json.dumps(SCAN_HIT), encoding="utf-8")
    calls = tmp_path / "npx_calls.jsonl"
    return {"root": root, "bin": fake_bin, "scan": scan, "calls": calls}


def edit_js(w: dict, rel: str = "web/app.js", scan: Path | None = None) -> subprocess.CompletedProcess:
    write(w["root"], rel, "el.addEventListener('keydown', e => { if (e.key === 'Enter') send(); });\n")
    return hook(w["root"], "post_edit.py", {"tool_name": "Write", "tool_input": {"file_path": rel}},
                [w["bin"]], FAKE_SCAN_JSON=str(scan or w["scan"]), FAKE_NPX_LOG=str(w["calls"]))


# ── 설치 ──────────────────────────────────────────────────────────────

def test_web_옵션으로_설치하면_확장이_켜지고_측정_열이_늘어난다(tmp_path):
    root = init(tmp_path, "--web")
    toml = (root / "hold.toml").read_text(encoding="utf-8")
    assert "\nenabled = true" in toml
    header = (root / "docs/hold/measurement.csv").read_text(encoding="utf-8").splitlines()[0]
    assert header.endswith("web_ext,mwg_version,guides_referenced,guides_retrieved,legacy_findings,legacy_allowed")
    assert (root / "scripts/web_scan.py").exists() and (root / "scripts/hold_web_sync.py").exists()
    assert "docs/hold/web/" in toml


def test_기본_설치는_확장이_꺼져_있다(project):
    assert "\nenabled = false" in (project / "hold.toml").read_text(encoding="utf-8")


# ── R17 고정 버전 설치 (hold_web_sync.py) ────────────────────────────

def test_sync는_고정_버전_skill과_가이드_목록을_만든다(web):
    root = web["root"]
    skill = (root / ".claude/skills/modern-web-guidance/SKILL.md").read_text(encoding="utf-8")
    assert "modern-web-guidance@latest" not in skill
    assert "DISABLE_TELEMETRY=1 npx -y modern-web-guidance@1.0.0 search" in skill
    assert "DISABLE_TELEMETRY=1 pnpx modern-web-guidance@1.0.0" in skill
    assert skill.startswith("---\nname: modern-web-guidance")  # frontmatter 유지 (skill 로 인식되게)
    assert "<!-- hold-kit:" in skill and "## HOLD 프로젝트 규칙" in skill
    assert "Reactive Policy Discovery\"를 따르지 않는다" in skill
    assert "Baseline Widely available" in skill
    assert (root / ".claude/skills/modern-web-guidance/LICENSE").exists()
    index = json.loads((root / "docs/hold/web/guides.json").read_text(encoding="utf-8"))
    assert index["mwg_version"] == "1.0.0" and index["count"] == 3
    res = subprocess.run([sys.executable, str(root / "scripts/hold_web_sync.py"), "--root", str(root), "--check"],
                         capture_output=True, text=True, env=clean_env())
    assert res.returncode == 0, res.stdout


def test_sync는_지원_기준과_대체_정책을_skill에_옮긴다(tmp_path):
    root = init(tmp_path, "--web")
    set_toml(root, 'baseline = "widely"', 'baseline = "2024"')
    set_toml(root, 'fallback_policy = ""', 'fallback_policy = "외부 폴리필 금지, 20줄 이하 대체 코드만"')
    assert sync(root, make_tarball(tmp_path / "m.tgz")).returncode == 0
    skill = (root / ".claude/skills/modern-web-guidance/SKILL.md").read_text(encoding="utf-8")
    assert "This project's Baseline target is Baseline 2024." in skill
    assert "외부 폴리필 금지, 20줄 이하 대체 코드만" in skill


def test_hold_toml의_버전을_올리고_다시_설치하지_않으면_check가_실패한다(web):
    root = web["root"]
    set_toml(root, 'mwg_version = "1.0.0"', 'mwg_version = "1.1.0"')
    res = subprocess.run([sys.executable, str(root / "scripts/hold_web_sync.py"), "--root", str(root), "--check"],
                         capture_output=True, text=True, env=clean_env())
    assert res.returncode == 1
    assert "설치된 skill 은 1.0.0, hold.toml 은 1.1.0" in res.stdout


def test_check는_플러그인_원본을_그대로_복사한_skill을_잡는다(web):
    root = web["root"]
    (root / ".claude/skills/modern-web-guidance/SKILL.md").write_text(SKILL_SRC, encoding="utf-8")
    res = subprocess.run([sys.executable, str(root / "scripts/hold_web_sync.py"), "--root", str(root), "--check"],
                         capture_output=True, text=True, env=clean_env())
    assert res.returncode == 1
    assert "hold_web_sync.py 로 만든 파일이 아닙니다" in res.stdout and "@latest" in res.stdout


def test_sync는_에이전트_셸에서_실행을_거부한다(tmp_path):
    root = init(tmp_path, "--web")
    res = sync(root, make_tarball(tmp_path / "m.tgz"), env=clean_env(CLAUDECODE="1"))
    assert res.returncode == 1 and "사람이 실행합니다" in res.stderr
    assert not (root / ".claude/skills/modern-web-guidance/SKILL.md").exists()


def test_sync는_원본_형식이_바뀌면_멈춘다(tmp_path):
    root = init(tmp_path, "--web")
    res = sync(root, make_tarball(tmp_path / "m.tgz", skill=SKILL_SRC.replace("@latest", "")))
    assert res.returncode == 1 and "형식이 바뀌었을 수 있습니다" in res.stderr


def test_sync는_패키지_버전이_다르면_멈춘다(tmp_path):
    root = init(tmp_path, "--web")
    res = sync(root, make_tarball(tmp_path / "m.tgz", version="0.9.0"))
    assert res.returncode == 1 and "mwg_version 1.0.0 과 다릅니다" in res.stderr


# ── R15 레거시 패턴 검사 (post_edit → web_scan) ──────────────────────

def test_standard는_레거시_검출을_에이전트에게_되돌린다(web):
    res = edit_js(web)
    assert res.returncode == 2
    assert "R15" in res.stderr and "ime-safe-enter-submit" in res.stderr
    assert "modern-web-guidance@1.0.0 retrieve ime-safe-enter-submit" in res.stderr
    assert "web/app.js:3" in res.stderr
    calls = [json.loads(line) for line in web["calls"].read_text(encoding="utf-8").splitlines()]
    assert calls[0]["args"][:2] == ["-y", "modern-web-guidance@1.0.0"] and "legacy-scan" in calls[0]["args"]
    assert calls[0]["telemetry_off"] is True
    rec = hook_log(web["root"], "web_scan")[-1]
    assert rec["verdict"] == "fail" and rec["mode"] == "block" and rec["guides"] == ["ime-safe-enter-submit"]
    assert hook_log(web["root"], "post_edit")[-1]["verdict"] == "fail"  # 측정 시트 check_failures 에 잡힘


def test_lite는_레거시_검출을_로그로만_남긴다(web):
    set_toml(web["root"], 'profile = "standard"', 'profile = "lite"')
    res = edit_js(web)
    assert res.returncode == 0, res.stderr
    rec = hook_log(web["root"], "web_scan")[-1]
    assert rec["verdict"] == "fail" and rec["mode"] == "log"
    assert hook_log(web["root"], "post_edit") == []  # 에이전트에게 돌려준 실패가 아니므로 check_failures 아님


def test_허용_목록의_검출은_통과한다(web):
    set_toml(web["root"], "legacy_allow = []", 'legacy_allow = ["ime-safe-enter-submit:web/*.js"]')
    res = edit_js(web)
    assert res.returncode == 0, res.stderr
    assert hook_log(web["root"], "web_scan")[-1]["allowed"] == ["ime-safe-enter-submit"]


def test_허용_목록은_경로가_맞을_때만_적용된다(web):
    set_toml(web["root"], "legacy_allow = []", 'legacy_allow = ["ime-safe-enter-submit:legacy/*.js"]')
    assert edit_js(web).returncode == 2


def test_외부_코드_폴더는_검사하지_않는다(web):
    res = edit_js(web, rel="node_modules/lib/app.js")
    assert res.returncode == 0
    assert not web["calls"].exists()


def test_파이썬_파일에는_웹_검사를_하지_않는다(web):
    write(web["root"], "app/x.py", "x = 1\n")
    res = hook(web["root"], "post_edit.py", {"tool_name": "Write", "tool_input": {"file_path": "app/x.py"}},
               [web["bin"]], FAKE_SCAN_JSON=str(web["scan"]), FAKE_NPX_LOG=str(web["calls"]))
    assert res.returncode == 0 and not web["calls"].exists()


def test_npx가_없으면_건너뛰고_기록한다(web, tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    write(web["root"], "web/app.js", "x\n")
    res = hook(web["root"], "post_edit.py", {"tool_name": "Write", "tool_input": {"file_path": "web/app.js"}}, [empty])
    assert res.returncode == 0
    assert hook_log(web["root"], "web_scan")[-1]["verdict"] == "skip"


def test_확장이_꺼져_있으면_프런트_파일을_검사하지_않는다(project, fake_bin, tmp_path):
    calls = tmp_path / "calls.jsonl"
    scan = tmp_path / "scan.json"
    scan.write_text(json.dumps(SCAN_HIT), encoding="utf-8")
    write(project, "web/app.js", "x\n")
    res = hook(project, "post_edit.py", {"tool_name": "Write", "tool_input": {"file_path": "web/app.js"}},
               [fake_bin], FAKE_SCAN_JSON=str(scan), FAKE_NPX_LOG=str(calls))
    assert res.returncode == 0 and not calls.exists()


def test_web_scan_명령은_block에서_실패하고_log에서_통과한다(web):
    write(web["root"], "web/app.js", "x\n")
    env = clean_env(PATH=str(web["bin"]), FAKE_SCAN_JSON=str(web["scan"]))
    cmd = [sys.executable, str(web["root"] / "scripts/web_scan.py"), "--root", str(web["root"]), "web/app.js"]
    res = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=web["root"])
    assert res.returncode == 1 and "ime-safe-enter-submit" in res.stdout
    res = subprocess.run(cmd + ["--profile", "lite"], capture_output=True, text=True, env=env, cwd=web["root"])
    assert res.returncode == 0


# ── R17 고정 버전 호출 (protect_paths, PreToolUse) ───────────────────

@pytest.mark.parametrize("cmd", [
    'npx -y modern-web-guidance@latest search "light dismiss dialog"',
    "npx modern-web-guidance retrieve dialog",
    "DISABLE_TELEMETRY=1 npx -y modern-web-guidance@1.1.0 retrieve dialog",
    "npx -y modern-web-guidance@1.0.0 set-allow-volatile-features",
    "cd web && npx -y modern-web-guidance@1.0.0 update",
])
def test_고정_버전이_아닌_호출과_설정_변경_명령은_막는다(web, cmd):
    res = hook(web["root"], "protect_paths.py", {"tool_name": "Bash", "tool_input": {"command": cmd}}, [web["bin"]])
    assert res.returncode == 2, cmd
    assert "R17" in res.stderr


@pytest.mark.parametrize("cmd", [
    'DISABLE_TELEMETRY=1 npx -y modern-web-guidance@1.0.0 search "light dismiss dialog" --skill-version 2026_11_09-test',
    'npx -y modern-web-guidance@1.0.0 retrieve "dialog,light-dismiss-a-dialog"',
    "grep -n modern-web-guidance@latest README.md",
])
def test_고정_버전_호출과_단순_언급은_허용한다(web, cmd):
    res = hook(web["root"], "protect_paths.py", {"tool_name": "Bash", "tool_input": {"command": cmd}}, [web["bin"]])
    assert res.returncode == 0, res.stderr


def test_확장이_꺼져_있으면_MWG_호출을_막지_않는다(project, fake_bin):
    res = hook(project, "protect_paths.py",
               {"tool_name": "Bash", "tool_input": {"command": "npx -y modern-web-guidance@latest search x"}}, [fake_bin])
    assert res.returncode == 0


@pytest.mark.parametrize("rel", [".claude/skills/modern-web-guidance/SKILL.md", "docs/hold/web/guides.json"])
def test_고정_skill과_가이드_목록은_보호_경로다(web, rel):
    res = hook(web["root"], "protect_paths.py", {"tool_name": "Write", "tool_input": {"file_path": rel}}, [web["bin"]])
    assert res.returncode == 2


# ── H9 실제 참조 기록 (post_edit, Bash) ──────────────────────────────

def test_실제로_실행한_retrieve를_훅_로그에_남긴다(web):
    cmd = 'DISABLE_TELEMETRY=1 npx -y modern-web-guidance@1.0.0 retrieve "dialog,light-dismiss-a-dialog"'
    res = hook(web["root"], "post_edit.py", {"tool_name": "Bash", "tool_input": {"command": cmd}}, [web["bin"]])
    assert res.returncode == 0
    rec = hook_log(web["root"], "web_guidance")[-1]
    assert rec["action"] == "retrieve" and rec["ids"] == ["dialog", "light-dismiss-a-dialog"]
    assert rec["mwg_version"] == "1.0.0"


# ── R14·R16 산출물 검사 (check_views) ────────────────────────────────

def run_check(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(root / "scripts/check_views.py"), "--root", str(root)],
                          capture_output=True, text=True, env=clean_env())


def test_웹_확장_설치_직후에도_통과한다(web):
    res = run_check(web["root"])
    assert res.returncode == 0, res.stdout


@pytest.mark.parametrize("refs,ok", [
    ("- `dialog` — 모달은 <dialog> 와 showModal()", True),
    ("- `dialog`\n- `light-dismiss-a-dialog` — closedby", True),
    ("생략: 프런트엔드 변경 없음", True),
    ("- `made-up-guide` — 기억으로 쓴 ID", False),
    ("(나중에 적음)", False),
])
def test_spec의_참조_가이드는_고정_목록과_대조한다(web, refs, ok):
    root = web["root"]
    write(root, "changes/20261112-modal/intent.md", INTENT)
    write(root, "changes/20261112-modal/spec.md", spec(refs))
    res = run_check(root)
    assert (res.returncode == 0) is ok, res.stdout
    if not ok:
        assert "R16" in res.stdout


def test_spec에_참조_가이드_절이_없으면_실패한다(web):
    root = web["root"]
    write(root, "changes/20261112-modal/intent.md", INTENT)
    write(root, "changes/20261112-modal/spec.md", spec("x").replace("## 참조 가이드\nx\n", ""))
    res = run_check(root)
    assert res.returncode == 1 and "'## 참조 가이드' 절이 없습니다" in res.stdout


def test_확장이_꺼져_있으면_참조_가이드를_요구하지_않는다(project):
    write(project, "changes/20261112-modal/intent.md", INTENT)
    write(project, "changes/20261112-modal/spec.md", spec("x").replace("## 참조 가이드\nx\n", ""))
    assert run_check(project).returncode == 0


def test_plan의_참조_가이드도_대조한다(web):
    root = web["root"]
    write(root, "changes/20261112-modal/intent.md", INTENT)
    write(root, "changes/20261112-modal/spec.md", spec("- `dialog`"))
    write(root, "changes/20261112-modal/plan.md", "# Plan\n## 모듈별 작업 범위\n- web\n## 참조 가이드\n- `dialgo`\n")
    res = run_check(root)
    assert res.returncode == 1 and "`dialgo`" in res.stdout


def test_정의서에_사용_환경_칸이_없으면_실패한다(web):
    reg = web["root"] / "docs/architecture/stakeholders.md"
    reg.write_text(reg.read_text(encoding="utf-8").replace(" 사용 환경 |", " 비고 |"), encoding="utf-8")
    res = run_check(web["root"])
    assert res.returncode == 1 and "'사용 환경' 칸이 없습니다" in res.stdout


def test_가이드_목록이_없으면_설치를_요구한다(tmp_path):
    root = init(tmp_path, "--web")
    res = run_check(root)
    assert res.returncode == 1 and "hold_web_sync.py" in res.stdout
