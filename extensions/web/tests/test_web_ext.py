"""HOLD 웹 확장 web-0.1 — 적대적 리뷰(method-adr/0002-adversarial-review.md)의 공격을 회귀 테스트로 고정.

테스트 이름 앞의 ADV-xx 는 리뷰의 발견 번호입니다.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import (LEGACY, REPO, Proj, build, clean_env, core_init, ext_install, make_tarball, set_toml,
                      write)

sys.path.insert(0, str(REPO / "extensions"))
import core_manifest  # noqa: E402

GOOD = "DISABLE_TELEMETRY=1 npx -y modern-web-guidance@1.0.0"


# ── 코어 무수정 (ADV-13) ─────────────────────────────────────────────

def test_ADV13_코어_파일은_동결_시점과_같다():
    assert core_manifest.diff() == []


def test_ADV13_설치해도_코어_키트가_설치한_파일은_그대로다(proj: Proj):
    for rel in [".claude/hooks/protect_paths.py", ".claude/hooks/post_edit.py", "scripts/check_views.py"]:
        src = {"protect_paths.py": "kit/hooks/protect_paths.py", "post_edit.py": "kit/hooks/post_edit.py",
               "check_views.py": "kit/scripts/check_views.py"}[Path(rel).name]
        assert (proj.root / rel).read_bytes() == (REPO / src).read_bytes()
    settings = json.loads((proj.root / ".claude/settings.json").read_text(encoding="utf-8"))
    cmds = [h["command"] for e in settings["hooks"]["PreToolUse"] + settings["hooks"]["PostToolUse"] for h in e["hooks"]]
    assert "python .claude/hooks/protect_paths.py" in cmds and "python .claude/hooks/post_edit.py" in cmds


# ── 설치 (ADV-03, ADV-14, ADV-16) ────────────────────────────────────

def test_ADV03_실증_중인_v0_1_프로젝트에도_같은_절차로_설치된다(proj: Proj):
    settings = json.loads((proj.root / ".claude/settings.json").read_text(encoding="utf-8"))
    mine = [e for ev in ("PreToolUse", "PostToolUse") for e in settings["hooks"][ev]
            if any("web_guard.py" in h["command"] for h in e["hooks"])]
    assert [e["matcher"] for e in mine] == ["Bash|Edit|Write|MultiEdit|NotebookEdit", "Bash|Edit|Write|MultiEdit"]
    assert all(h["timeout"] >= 120 for e in mine for h in e["hooks"])
    res = proj.check()
    assert res.returncode == 0, res.stdout


def test_설치를_두_번_해도_절과_훅이_하나씩이다(proj: Proj):
    assert ext_install(proj.root).returncode == 0
    settings = json.loads((proj.root / ".claude/settings.json").read_text(encoding="utf-8"))
    n = sum(1 for ev in settings["hooks"].values() for e in ev for h in e["hooks"] if "web_guard" in h["command"])
    assert n == 2
    assert (proj.root / "CLAUDE.md").read_text(encoding="utf-8").count("hold-web:start") == 1
    assert (proj.root / "hold.toml").read_text(encoding="utf-8").count("[web]") == 1


def test_설치는_에이전트_셸과_코어_없는_폴더에서_거부된다(tmp_path):
    assert ext_install(tmp_path / "x").returncode == 1
    root = tmp_path / "p"
    core_init(root, "lite")
    assert ext_install(root, env=clean_env(CLAUDECODE="")).returncode == 1


def test_ADV14_확장을_설치하지_않은_프로젝트의_양식은_코어_그대로다(tmp_path):
    root = tmp_path / "p"
    core_init(root, "lite")
    spec = (root / "changes/_template/spec.md").read_text(encoding="utf-8")
    assert "(웹)" not in spec and "참조 가이드" not in spec
    assert "사용 환경" not in (root / "docs/architecture/stakeholders.md").read_text(encoding="utf-8")


def test_ADV16_설정_형_오류는_훅이_판단을_멈추고_막는다(proj: Proj):
    set_toml(proj.root, "telemetry = false", 'telemetry = "false"')
    res = proj.pre("Bash", command="ls")
    assert res.returncode == 2 and "telemetry" in res.stderr
    assert proj.check().returncode == 1


def test_확장을_끄면_아무것도_막지_않는다(proj: Proj):
    set_toml(proj.root, "enabled = true", "enabled = false")
    assert proj.pre("Bash", command="npx modern-web-guidance@latest update").returncode == 0
    assert proj.pre("Write", file_path=".mwgrc").returncode == 0
    assert proj.check().returncode == 0


# ── R17 고정 버전·하위 명령·텔레메트리 (ADV-01, 07, 08) ─────────────

@pytest.mark.parametrize("cmd", [
    f"{GOOD} set-baseline limited",                                  # ADV-01
    f"{GOOD} set-allow-volatile-features",
    f'{GOOD} "update"',                                              # ADV-08
    f"{GOOD} --skill-version x update",
    f"{GOOD} -- update",
    f"{GOOD} \\\n set-allow-origin-trials",
    "echo update | DISABLE_TELEMETRY=1 xargs npx -y modern-web-guidance@1.0.0",
    "npm i modern-web-guidance@1.0.0 && ./node_modules/.bin/modern-web-guidance update",
    "npx -p modern-web-guidance@1.0.0 modern-web-guidance update",
    "npx -y modern-web-guidance@latest search dialog",
    "DISABLE_TELEMETRY=1 npx modern-web-guidance retrieve dialog",
    'bash -c "DISABLE_TELEMETRY=1 npx -y modern-web-guidance@1.0.0 update"',
    'echo "$(npx -y modern-web-guidance@latest retrieve x)"',
    "node -e \"require('child_process').execSync('npx modern-web-guidance@latest search x')\"",
    "npx -y modern-web-guidance@1.0.0 retrieve dialog",               # ADV-07 텔레메트리 접두어 없음
    f'{GOOD} search "unclosed',
])
def test_고정_버전_화이트리스트_텔레메트리를_벗어난_호출은_막는다(proj: Proj, cmd):
    res = proj.pre("Bash", command=cmd)
    assert res.returncode == 2, cmd


@pytest.mark.parametrize("cmd", [
    f'{GOOD} search "light dismiss dialog" --skill-version 2026_11_09-test',
    f'{GOOD} retrieve "dialog,light-dismiss-a-dialog" | head -5',
    "env DISABLE_TELEMETRY=1 npx -y modern-web-guidance@1.0.0 list",
    f"cd web && {GOOD} legacy-scan . --json",
    "grep -rn modern-web-guidance@latest README.md",
    'git commit -m "note about modern-web-guidance"',
])
def test_정상_호출과_단순_언급은_허용한다(proj: Proj, cmd):
    res = proj.pre("Bash", command=cmd)
    assert res.returncode == 0, res.stderr


# ── 보호 경로 (ADV-01, 02, 09, 12) ──────────────────────────────────

@pytest.mark.parametrize("path", [".mwgrc", "web/.mwgrc", "/tmp/elsewhere/.mwgrc", "docs/hold/web/guides.json",
                                  "docs/hold/web/lock.json", ".hold/logs/hooks.jsonl", ".claude/hold-web/common.py",
                                  "docs/architecture/usage-environments.md"])
def test_확장_보호_파일은_편집_도구로_쓸_수_없다(proj: Proj, path):
    assert proj.pre("Write", file_path=path).returncode == 2


@pytest.mark.parametrize("cmd", [
    "CLAUDECODE= python3 .claude/hold-web/sync.py --tarball evil.tgz",   # ADV-02
    "env -u CLAUDECODE python .claude/hold-web/sync.py --pin 9.9.9",
    "python3 -c \"open('.mwgrc','w').write('{}')\"",
    "printf '{}' | tee ~/.mwgrc",
    "echo '{}' >> .hold/logs/hooks.jsonl",                               # ADV-09
    "sed -i s/a/b/ docs/hold/web/lock.json",
    "cp /tmp/x.py .claude/hold-web/web_scan.py",                         # ADV-12
])
def test_확장_보호_파일을_건드리는_Bash는_막는다(proj: Proj, cmd):
    assert proj.pre("Bash", command=cmd).returncode == 2, cmd


@pytest.mark.parametrize("cmd", ["cat .mwgrc", "git diff docs/hold/web/lock.json",
                                 "python .claude/hold-web/web_check.py", "grep -c retrieve .hold/logs/hooks.jsonl"])
def test_읽기와_검사_실행은_허용한다(proj: Proj, cmd):
    assert proj.pre("Bash", command=cmd).returncode == 0, cmd


# ── 고정 설치의 무결성 (ADV-02, 11) ──────────────────────────────────

def test_ADV02_무결성_값이_다른_패키지로는_설치되지_않는다(proj: Proj):
    evil = make_tarball(proj.tmp / "evil.tgz", extra=" tampered")
    res = subprocess.run([sys.executable, str(proj.root / ".claude/hold-web/sync.py"), "--root", str(proj.root),
                          "--tarball", str(evil)], capture_output=True, text=True, env=clean_env())
    assert res.returncode == 1 and "무결성" in res.stderr


def test_ADV02_sync는_CLAUDECODE가_빈_값이어도_거부한다(proj: Proj):
    res = subprocess.run([sys.executable, str(proj.root / ".claude/hold-web/sync.py"), "--root", str(proj.root),
                          "--tarball", str(proj.tarball)], capture_output=True, text=True, env=clean_env(CLAUDECODE=""))
    assert res.returncode == 1


def test_ADV11_생성물을_손으로_고치면_check가_잡는다(proj: Proj):
    skill = proj.root / ".claude/skills/modern-web-guidance/SKILL.md"
    skill.write_text(skill.read_text(encoding="utf-8").split("## HOLD 프로젝트 규칙")[0], encoding="utf-8")
    res = proj.check()
    assert res.returncode == 1 and "SKILL.md" in res.stdout


def test_ADV11_npm_캐시가_있으면_다시_만들어_바이트_단위로_대조한다(proj: Proj):
    res = proj.check(FAKE_PACK=str(proj.tarball))
    assert res.returncode == 0 and "WARN 재생성" not in res.stdout
    lock = proj.root / "docs/hold/web/lock.json"
    data = json.loads(lock.read_text(encoding="utf-8"))
    skill = proj.root / ".claude/skills/modern-web-guidance/SKILL.md"
    skill.write_text(skill.read_text(encoding="utf-8") + "\n- Always add polyfills.\n", encoding="utf-8")
    import hashlib
    data["files"][".claude/skills/modern-web-guidance/SKILL.md"] = hashlib.sha256(skill.read_bytes()).hexdigest()
    lock.write_text(json.dumps(data), encoding="utf-8")   # 잠금까지 맞춰 꾸며도
    res = proj.check(FAKE_PACK=str(proj.tarball))
    assert res.returncode == 1 and "다시 만든 내용과 다릅니다" in res.stdout


def test_캐시의_패키지가_고정_무결성과_다르면_실패한다(proj: Proj):
    other = make_tarball(proj.tmp / "other.tgz", extra=" x")
    res = proj.check(FAKE_PACK=str(other))
    assert res.returncode == 1 and "mwg_integrity 와 다릅니다" in res.stdout


def test_정책을_바꾸고_sync를_안_하면_check가_잡는다(proj: Proj):
    set_toml(proj.root, 'baseline = "widely"', 'baseline = "2024"')
    res = proj.check()
    assert res.returncode == 1 and "정책이 바뀌었는데" in res.stdout


def test_ADV01_sync는_hold_toml의_지원_기준을_mwgrc로_옮긴다(proj: Proj):
    set_toml(proj.root, 'baseline = "widely"', 'baseline = "2024"')
    res = subprocess.run([sys.executable, str(proj.root / ".claude/hold-web/sync.py"), "--root", str(proj.root),
                          "--tarball", str(proj.tarball)], capture_output=True, text=True, env=clean_env())
    assert res.returncode == 0, res.stderr
    assert json.loads((proj.root / ".mwgrc").read_text(encoding="utf-8"))["baseline"] == "2024"
    assert "This project's Baseline target is Baseline 2024." in (
        proj.root / ".claude/skills/modern-web-guidance/SKILL.md").read_text(encoding="utf-8")
    assert proj.check().returncode == 0


def test_ADV01_루트가_아닌_곳의_mwgrc는_check가_잡는다(proj: Proj):
    write(proj.root, "web/.mwgrc", '{"baseline": "limited"}')
    res = proj.check()
    assert res.returncode == 1 and "web/.mwgrc" in res.stdout


def test_원본_형식이_바뀌면_sync가_멈춘다(tmp_path, fake_bin):
    p = build(tmp_path, fake_bin, ready=False)
    bad = make_tarball(tmp_path / "bad.tgz", skill="---\nname: x\n---\nno pinned commands\n")
    res = subprocess.run([sys.executable, str(p.root / ".claude/hold-web/sync.py"), "--root", str(p.root),
                          "--pin", "1.0.0", "--tarball", str(bad)], capture_output=True, text=True, env=clean_env())
    assert res.returncode == 1 and "형식이 바뀌었을" in res.stderr


def test_생성된_skill은_고정_버전과_텔레메트리_접두어와_HOLD_절을_가진다(proj: Proj):
    skill = (proj.root / ".claude/skills/modern-web-guidance/SKILL.md").read_text(encoding="utf-8")
    assert "modern-web-guidance@latest" not in skill
    assert f"{GOOD} search" in skill and "DISABLE_TELEMETRY=1 pnpx modern-web-guidance@1.0.0" in skill
    assert skill.startswith("---\nname: modern-web-guidance") and "## HOLD 프로젝트 규칙" in skill
    assert "mwg:<id>" in skill


# ── R15 레거시 패턴 검사 (ADV-04, 05, 06, 16) ───────────────────────

def test_standard는_편집한_프런트_파일의_검출을_되돌린다(proj: Proj):
    write(proj.root, "web/app.js", LEGACY)
    res = proj.post("Write", file_path="web/app.js")
    assert res.returncode == 2 and "R15" in res.stderr and "web/app.js:1" in res.stderr
    assert f"{GOOD} retrieve ime-safe-enter-submit" in res.stderr          # ADV-07: 안내 명령에도 접두어
    call = json.loads(proj.calls.read_text(encoding="utf-8").splitlines()[-1])
    assert call["args"][:2] == ["-y", "modern-web-guidance@1.0.0"] and call["telemetry_off"]


def test_lite는_기록만_한다(proj: Proj):
    set_toml(proj.root, 'profile = "standard"', 'profile = "lite"')
    write(proj.root, "web/app.js", LEGACY)
    assert proj.post("Write", file_path="web/app.js").returncode == 0
    assert proj.log("web_scan")[-1]["verdict"] == "fail"


def test_ADV05_Bash로_쓴_프런트_파일도_검사한다(proj: Proj):
    payload = {"tool_name": "Bash", "tool_use_id": "t1", "tool_input": {"command": "cat > web/b.js <<EOF"}}
    assert proj.hook({**payload, "hook_event_name": "PreToolUse"}).returncode == 0
    write(proj.root, "web/b.js", LEGACY)
    res = proj.hook({**payload, "hook_event_name": "PostToolUse", "tool_response": {"stdout": ""}})
    assert res.returncode == 2 and "web/b.js" in res.stderr
    assert proj.log("web_scan")[-1]["via"] == "bash"


def test_ADV06_대시로_시작하는_파일도_검사한다(proj: Proj):
    write(proj.root, "-x.js", LEGACY)
    res = proj.post("Write", file_path="-x.js")
    assert res.returncode == 2 and "-x.js" in res.stderr


def test_ADV06_검사기의_오류_출력은_통과가_아니다(proj: Proj):
    write(proj.root, "web/app.js", LEGACY)
    res = proj.hook({"hook_event_name": "PostToolUse", "tool_name": "Write", "tool_input": {"file_path": "web/app.js"}},
                    FAKE_SCAN="error")
    assert res.returncode == 2 and "실패" in res.stderr
    assert proj.log("web_scan")[-1]["verdict"] == "error"


def test_ADV04_gitignore와_상관없이_여러_파일을_검사한다(proj: Proj):
    files = [f"web/f{i}.js" for i in range(7)]
    for f in files:
        write(proj.root, f, LEGACY)
    write(proj.root, ".gitignore", "web/\n")
    res = proj.run("web_scan.py", *files)
    assert res.returncode == 1 and res.stdout.count("web/f") >= 5


def test_ADV16_허용_목록의_별표는_폴더를_넘지_않는다(proj: Proj):
    set_toml(proj.root, "legacy_allow = []", 'legacy_allow = ["ime-safe-enter-submit:web/*.js"]')
    write(proj.root, "web/a.js", LEGACY)
    write(proj.root, "web/sub/b.js", LEGACY)
    assert proj.post("Write", file_path="web/a.js").returncode == 0
    assert proj.post("Write", file_path="web/sub/b.js").returncode == 2
    set_toml(proj.root, '"ime-safe-enter-submit:web/*.js"', '"ime-safe-enter-submit:web/**"')
    assert proj.post("Write", file_path="web/sub/b.js").returncode == 0


def test_ADV16_jinja_템플릿도_HTML로_검사한다(proj: Proj):
    write(proj.root, "app/templates/chat.j2", "<script>" + LEGACY + "</script>")
    res = proj.post("Write", file_path="app/templates/chat.j2")
    assert res.returncode == 2 and "app/templates/chat.j2" in res.stderr


def test_npx가_없으면_건너뛰고_regulated는_막는다(proj: Proj):
    empty = proj.tmp / "empty"
    empty.mkdir()
    write(proj.root, "web/app.js", LEGACY)
    payload = {"hook_event_name": "PostToolUse", "tool_name": "Write", "tool_input": {"file_path": "web/app.js"}}
    assert proj.hook(payload, path=[empty]).returncode == 0
    assert proj.log("web_scan")[-1]["verdict"] == "skip"
    set_toml(proj.root, 'profile = "standard"', 'profile = "regulated"')
    assert proj.hook(payload, path=[empty]).returncode == 2


def test_외부_코드와_파이썬_파일은_검사하지_않는다(proj: Proj):
    write(proj.root, "node_modules/x/a.js", LEGACY)
    write(proj.root, "app/x.py", "x = 1\n")
    assert proj.post("Write", file_path="node_modules/x/a.js").returncode == 0
    assert proj.post("Write", file_path="app/x.py").returncode == 0
    assert not proj.calls.exists()


# ── H9 retrieve 증거 (ADV-09) ───────────────────────────────────────

def test_ADV09_실제_출력에서_확인된_ID만_기록한다(proj: Proj):
    out = "--- Guide for dialog ---\n# Dialog\n--- Guide for made-up ---\n"
    proj.post("Bash", {"stdout": out}, command=f'{GOOD} retrieve "dialog,ime-safe-enter-submit" --skill-version x')
    rec = proj.log("web_guidance")[-1]
    assert rec["requested"] == ["dialog", "ime-safe-enter-submit"] and rec["confirmed"] == ["dialog"]


def test_ADV09_출력이_파일로_저장된_경우_그_파일을_읽는다(proj: Proj, tmp_path):
    saved = tmp_path / "mwg-guide-1-2.md"
    saved.write_text("--- Guide for light-dismiss-a-dialog ---\n...", encoding="utf-8")
    proj.post("Bash", {"stdout": f"Output (12 KB) saved to {saved} to prevent truncation."},
              command=f"{GOOD} retrieve light-dismiss-a-dialog")
    assert proj.log("web_guidance")[-1]["confirmed"] == ["light-dismiss-a-dialog"]


@pytest.mark.parametrize("cmd", ['echo "modern-web-guidance retrieve dialog"',
                                 "true # modern-web-guidance@1.0.0 retrieve dialog"])
def test_ADV09_실행이_아닌_언급은_기록하지_않는다(proj: Proj, cmd):
    proj.post("Bash", {"stdout": "--- Guide for dialog ---"}, command=cmd)
    assert proj.log("web_guidance") == []


# ── R14 사용 환경 (ADV-15) ──────────────────────────────────────────

def test_ADV15_사용_환경이_양식_그대로면_실패한다(tmp_path, fake_bin):
    p = build(tmp_path, fake_bin, ready=False)
    res = p.check()
    assert res.returncode == 1 and "SH-U01 의 사용 환경" in res.stdout


def test_모두_해당_없음이면_실패하고_정의서에_없는_ID도_실패한다(proj: Proj):
    usage = proj.root / "docs/architecture/usage-environments.md"
    t = usage.read_text(encoding="utf-8").replace("시민, 모바일 Chrome 최신", "해당 없음")
    usage.write_text(t + "| SH-U99 | 시민 | x |\n", encoding="utf-8")
    res = proj.check()
    assert "한 명도 없습니다" in res.stdout and "SH-U99" in res.stdout


# ── R16 참조 가이드 (ADV-10) ────────────────────────────────────────

SPEC_HEAD = "# Spec\n## 이해관계자 영향\n| ID | 방향 | 내용 | 승인 |\n|---|---|---|---|\n| SH-U01 | → | x | 아니오 |\n"


def spec_with(refs: str) -> str:
    return SPEC_HEAD + "## 참조 가이드\n" + refs + "\n## 뷰\n생략: 테스트\n"


@pytest.mark.parametrize("refs,ok", [
    ("- mwg:dialog — 모달은 <dialog>", True),
    ("- mwg:dialog\n- mwg:light-dismiss-a-dialog — closedby", True),
    ("생략: 프런트엔드 변경 없음 (API 응답 형식만 바뀜)", True),
    ("생략: <이유 — 예: 프런트엔드 변경 없음>", False),       # 양식 그대로
    ("- `dialog`", False),                                   # mwg: 표기 아님
    ("- mwg:dialog\n- dialog-polyfil", False),               # 평문 가짜 ID
    ("- mwg:dialog-polyfil", False),                         # 목록에 없는 ID
    ("- mwg:dialog\n생략: 없음입니다", False),                 # 둘 다
    ("(나중에)", False),
    ("생략: x", False),                                      # 이유가 너무 짧음
])
def test_ADV10_spec의_참조_가이드(proj: Proj, refs, ok):
    write(proj.root, "changes/20261112-modal/spec.md", spec_with(refs))
    res = proj.check()
    assert (res.returncode == 0) is ok, res.stdout


def test_ADV10_참조_가이드_절이_여러_개면_실패한다(proj: Proj):
    write(proj.root, "changes/20261112-modal/spec.md",
          SPEC_HEAD + "## 참조 가이드\n- mwg:made-up\n## 참조 가이드\n생략: 프런트엔드 변경 없음\n")
    res = proj.check()
    assert res.returncode == 1 and "여러 개" in res.stdout


def test_확장을_켜기_전의_변경은_검사하지_않는다(proj: Proj):
    write(proj.root, "changes/20261101-old/spec.md", SPEC_HEAD)
    assert proj.check().returncode == 0


def test_spec을_고치면_훅이_바로_참조_가이드를_검사한다(proj: Proj):
    write(proj.root, "changes/20261112-modal/spec.md", spec_with("- mwg:made-up"))
    res = proj.post("Write", file_path="changes/20261112-modal/spec.md")
    assert res.returncode == 2 and "mwg:made-up" in res.stderr


def test_pre_commit_등록은_standard에서_필수_lite에서_경고(tmp_path, fake_bin):
    p = build(tmp_path, fake_bin)
    pc = p.root / ".pre-commit-config.yaml"
    pc.write_text(pc.read_text(encoding="utf-8").replace("hold-web-check", "x"), encoding="utf-8")
    assert p.check().returncode == 1
    set_toml(p.root, 'profile = "standard"', 'profile = "lite"')
    res = p.check()
    assert res.returncode == 0 and "WARN .pre-commit-config.yaml" in res.stdout


def test_측정_집계(proj: Proj):
    proj.post("Bash", {"stdout": "--- Guide for dialog ---"}, command=f"{GOOD} retrieve dialog")
    proj.pre("Bash", command="npx modern-web-guidance@latest search x")
    m = json.loads(proj.check("--metrics").stdout)
    assert m["retrieve_confirmed"] == 1 and m["guard_block"] == 1 and m["guides_confirmed"] == ["dialog"]
