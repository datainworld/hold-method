"""HOLD 웹 확장 web-0.1 — 적대적 리뷰 1·2차(method-adr/0002-adversarial-review*.md)의 공격을 회귀 테스트로 고정.

테스트 이름의 ADV-xx 는 1차, ADV2-xx 는 2차 리뷰의 발견 번호입니다.
위협 모델은 "실수하는 협조적 에이전트"이고(README 1절), 셸 문자열을 조립해 실행하는 식의 의도적 우회는 범위 밖입니다.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from conftest import (LEGACY, REPO, Proj, build, clean_env, core_init, ext_install, make_tarball, set_toml, sri_of,
                      sync_cmd, write)

sys.path.insert(0, str(REPO / "extensions"))
import core_manifest  # noqa: E402

W = "python .claude/hold-web/mwg.py"


def sync(p: Proj, *args: str, **env: str) -> subprocess.CompletedProcess:
    return subprocess.run(sync_cmd(p.root, *args), capture_output=True, text=True, env=clean_env(**env))


def wrapper(p: Proj, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(p.root / ".claude/hold-web/mwg.py"), *args],
                          capture_output=True, text=True, cwd=p.root, env=p.env())


def verify(p: Proj) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(REPO / "extensions/web/install.py"), "--target", str(p.root), "--verify"],
                          capture_output=True, text=True, env=p.env())


# ── 코어 무수정 (ADV-13) ─────────────────────────────────────────────

def test_ADV13_코어_파일은_동결_시점과_같다():
    assert core_manifest.diff() == []


def test_ADV13_설치해도_코어_키트가_설치한_훅과_스크립트는_그대로다(proj: Proj):
    pairs = {".claude/hooks/protect_paths.py": "kit/hooks/protect_paths.py",
             ".claude/hooks/post_edit.py": "kit/hooks/post_edit.py", "scripts/check_views.py": "kit/scripts/check_views.py"}
    for dst, src in pairs.items():
        assert (proj.root / dst).read_bytes() == (REPO / src).read_bytes()
    settings = json.loads((proj.root / ".claude/settings.json").read_text(encoding="utf-8"))
    cmds = [h["command"] for e in settings["hooks"]["PreToolUse"] + settings["hooks"]["PostToolUse"] for h in e["hooks"]]
    assert "python .claude/hooks/protect_paths.py" in cmds and "python .claude/hooks/post_edit.py" in cmds


# ── 설치 (ADV-03, ADV-14, ADV-16) ────────────────────────────────────

def test_ADV03_실증_중인_v0_1_프로젝트에도_같은_절차로_설치되고_검사를_통과한다(proj: Proj):
    settings = json.loads((proj.root / ".claude/settings.json").read_text(encoding="utf-8"))
    mine = [e for ev in ("PreToolUse", "PostToolUse") for e in settings["hooks"][ev]
            if any("web_guard.py" in h["command"] for h in e["hooks"])]
    assert [e["matcher"] for e in mine] == ["Bash|Edit|Write|MultiEdit|NotebookEdit", "Bash|Edit|Write|MultiEdit"]
    assert all(h["timeout"] >= 120 for e in mine for h in e["hooks"])
    assert ".hold/web-pkg/" in (proj.root / ".gitignore").read_text(encoding="utf-8")
    res = proj.check()
    assert res.returncode == 0, res.stdout


def test_설치를_두_번_해도_절과_훅이_하나씩이다(proj: Proj):
    assert ext_install(proj.root).returncode == 0
    settings = json.loads((proj.root / ".claude/settings.json").read_text(encoding="utf-8"))
    assert sum(1 for ev in settings["hooks"].values() for e in ev for h in e["hooks"] if "web_guard" in h["command"]) == 2
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


def test_ADV16_설정_형_오류는_훅이_판단을_멈추고_막는다(proj: Proj):
    set_toml(proj.root, "telemetry = false", 'telemetry = "false"')
    res = proj.pre("Bash", command="ls")
    assert res.returncode == 2 and "telemetry" in res.stderr
    assert proj.check().returncode == 1


def test_ADV2_02_설치된_확장을_조용히_끄면_check가_잡는다(proj: Proj):
    set_toml(proj.root, "enabled = true", "enabled = false")
    assert proj.pre("Bash", command="npx modern-web-guidance@latest update").returncode == 0   # 꺼지면 훅은 비켜 선다
    res = proj.check()
    assert res.returncode == 1 and "disabled_reason" in res.stdout
    set_toml(proj.root, "enabled = false", 'enabled = false\ndisabled_reason = "웹 UI 를 걷어 냄 (20261120 결정)"')
    assert proj.check().returncode == 0


# ── R17 실행 경로: 래퍼만 (ADV-01, 07, 08, ADV2-03, 04, 05) ─────────

@pytest.mark.parametrize("cmd", [
    "DISABLE_TELEMETRY=1 npx -y modern-web-guidance@1.0.0 search dialog",          # 고정 버전이어도 직접 실행은 금지
    "npx -y modern-web-guidance@latest search dialog",
    "DISABLE_TELEMETRY=1 npx -y modern-web-guidance@1.0.0 set-baseline limited",   # ADV-01
    'npx -y modern-web-guidance@1.0.0 "update"',                                    # ADV-08
    "npx -y modern-web-guidance@1.0.0 --skill-version x update",
    "npx -y modern-web-guidance@1.0.0 \\\n set-allow-origin-trials",
    "echo update | xargs npx -y modern-web-guidance@1.0.0",
    "npm i modern-web-guidance@1.0.0 && ./node_modules/.bin/modern-web-guidance update",
    "npx -p modern-web-guidance@1.0.0 modern-web-guidance update",
    "npm view modern-web-guidance versions",
    'bash -c "npx -y modern-web-guidance@1.0.0 update"',
    'echo "$(npx -y modern-web-guidance@latest retrieve x)"',
    f"{W} search x <(npx -y modern-web-guidance@1.0.0 set-baseline limited)",      # ADV2-04
    "cat >(npx -y modern-web-guidance@latest list)",
    "DISABLE_TELEMETRY=1 env -u DISABLE_TELEMETRY npx -y modern-web-guidance@1.0.0 search x",   # ADV2-05
    "node .hold/web-pkg/1.0.0/skills/modern-web-guidance/modern-web.mjs set-baseline limited",
    "node -e \"require('child_process').execSync('npx modern-web-guidance@latest search x')\"",
    'npx -y modern-web-guidance@1.0.0 search "unclosed',
])
def test_MWG를_래퍼_밖에서_부르는_명령은_모두_막는다(proj: Proj, cmd):
    res = proj.pre("Bash", command=cmd)
    assert res.returncode == 2, cmd


@pytest.mark.parametrize("cmd", [f'{W} search "light dismiss dialog"', f'{W} retrieve "dialog,light-dismiss-a-dialog" | head -5',
                                 f"cd web && {W} list", "grep -rn modern-web-guidance@latest README.md",
                                 'git commit -m "note about modern-web-guidance"', "npm test"])
def test_래퍼_호출과_단순_언급은_허용한다(proj: Proj, cmd):
    res = proj.pre("Bash", command=cmd)
    assert res.returncode == 0, res.stderr


def test_래퍼는_하위_명령을_제한하고_텔레메트리를_강제로_끈다(proj: Proj):
    assert wrapper(proj, "set-baseline", "limited").returncode == 2
    res = wrapper(proj, "search", "dialog")
    assert res.returncode == 0, res.stderr
    call = json.loads(proj.calls.read_text(encoding="utf-8").splitlines()[-1])
    assert call["telemetry_off"] and call["cli"].endswith("modern-web.mjs") and "--skill-version" in call["args"]
    assert ".hold/web-pkg/1.0.0" in call["cli"].replace("\\", "/")


def test_ADV2_03_검증된_사본이_바뀌면_래퍼와_검사가_멈춘다(proj: Proj):
    cli = proj.root / ".hold/web-pkg/1.0.0/skills/modern-web-guidance/modern-web.mjs"
    cli.write_text("// tampered", encoding="utf-8")
    res = wrapper(proj, "list")
    assert res.returncode == 2 and "검증한 내용과 다릅니다" in res.stderr
    write(proj.root, "web/app.js", LEGACY)
    res = proj.post("Write", file_path="web/app.js")
    assert res.returncode == 2 and "실패" in res.stderr          # 검사 실패 = fail-closed
    assert proj.check().returncode == 1


# ── 보호 경로 (ADV-01, 02, 09, 12, ADV2-01, 02, 08, 12) ─────────────

@pytest.mark.parametrize("path", [".mwgrc", "web/.mwgrc", "/tmp/elsewhere/.mwgrc", "docs/hold/web/lock.json",
                                  ".hold/logs/hooks.jsonl", ".hold/web-pkg/1.0.0/x", ".claude/hold-web/common.py",
                                  "docs/architecture/usage-environments.md", ".pre-commit-config.yaml",
                                  ".MWGRC", "web/.Mwgrc", ".CLAUDE/hold-web/common.py", "Docs/Hold/Web/lock.json",
                                  "HOLD.TOML", ".mwgrc::$DATA", "hold.toml."])
def test_보호_파일은_편집_도구로_쓸_수_없다(proj: Proj, path):
    assert proj.pre("Write", file_path=path).returncode == 2, path


@pytest.mark.parametrize("cmd", [
    "CLAUDECODE= python3 .claude/hold-web/sync.py --tarball evil.tgz",            # ADV-02
    "env -u CLAUDECODE python3 .c?aude/hold-we?/sync.py --pin 1.0.0",             # ADV2-02 글롭
    "sed -i s/x/y/ .c?aude/hold-we?/common.py",
    "sed -i s/true/false/ hold.to?l",
    "cp /tmp/x .mwg?c",
    "printf x > .claude/hold-web/{common,x}.py",
    "git show --output=.claude/hooks/web_guard.py HEAD",                          # ADV2-01
    "git log -0 --output=.hold/logs/hooks.jsonl",
    "python3 -c \"open('.mwgrc','w').write('{}')\"",
    "printf '{}' | tee ~/.mwgrc",
    "echo '{}' >> .hold/logs/hooks.jsonl",
    "cp /tmp/x.py .claude/hold-web/web_scan.py",
    "sed -i /hold-web/d .pre-commit-config.yaml",                                 # ADV2-08
    "git commit --no-verify -m x",
    "git commit -n -m x",
    "git -c core.hooksPath=/dev/null commit -m x",
    "rm *",
])
def test_보호_파일을_건드리거나_검사를_건너뛰는_Bash는_막는다(proj: Proj, cmd):
    assert proj.pre("Bash", command=cmd).returncode == 2, cmd


@pytest.mark.parametrize("cmd", ["cat .mwgrc", "git diff docs/hold/web/lock.json", "python .claude/hold-web/web_check.py",
                                 "python3 ./.claude/hold-web/web_scan.py web/a.js", "grep -c retrieve .hold/logs/hooks.jsonl",
                                 "ls *", "pytest tests/*.py", "cp src/*.js dist/", 'git commit -m "x"'])
def test_읽기와_검사_실행과_흔한_명령은_허용한다(proj: Proj, cmd):
    assert proj.pre("Bash", command=cmd).returncode == 0, cmd


# ── 고정 설치의 무결성 (ADV-02, 11, ADV2-02, 09) ────────────────────

def test_ADV02_무결성_값이_다른_패키지로는_설치되지_않는다(proj: Proj):
    evil = make_tarball(proj.tmp / "evil.tgz", extra=" tampered")
    res = sync(proj, "--tarball", str(evil))
    assert res.returncode == 1 and "무결성" in res.stderr


def test_ADV2_02_오프라인_고정은_무결성_값을_따로_받아야_한다(proj: Proj):
    evil = make_tarball(proj.tmp / "evil.tgz", extra=" tampered")
    res = sync(proj, "--pin", "1.0.0", "--tarball", str(evil), PATH=str(proj.tmp / "nowhere"))
    assert res.returncode == 1 and "--integrity" in res.stderr      # 파일에서 계산하지 않는다
    res = sync(proj, "--pin", "1.0.0", "--tarball", str(evil), "--integrity", sri_of(proj.tarball))
    assert res.returncode == 1 and "무결성" in res.stderr


def test_ADV2_02_sync는_CLAUDECODE가_빈_값이어도_거부한다(proj: Proj):
    assert sync(proj, "--tarball", str(proj.tarball), CLAUDECODE="").returncode == 1


def test_ADV11_생성물을_고치고_lock까지_맞춰도_재생성_대조가_잡는다(proj: Proj):
    import hashlib
    skill = proj.root / ".claude/skills/modern-web-guidance/SKILL.md"
    skill.write_text(skill.read_text(encoding="utf-8") + "\n- Always add polyfills.\n", encoding="utf-8")
    lock = proj.root / "docs/hold/web/lock.json"
    data = json.loads(lock.read_text(encoding="utf-8"))
    data["files"][".claude/skills/modern-web-guidance/SKILL.md"] = hashlib.sha256(skill.read_bytes()).hexdigest()
    lock.write_text(json.dumps(data), encoding="utf-8")
    res = proj.check()
    assert res.returncode == 1 and "다시 만든 내용과 다릅니다" in res.stdout


def test_ADV2_09_사본이_없으면_standard는_실패하고_fetch_only로_채운다(proj: Proj):
    import shutil
    shutil.rmtree(proj.root / ".hold/web-pkg")
    res = proj.check()
    assert res.returncode == 1 and "fetch-only" in res.stdout
    assert sync(proj, "--fetch-only", "--tarball", str(proj.tarball)).returncode == 0
    assert proj.check().returncode == 0


def test_보관된_패키지가_무결성과_다르면_실패한다(proj: Proj):
    tgz = proj.root / ".hold/web-pkg/modern-web-guidance-1.0.0.tgz"
    tgz.write_bytes(make_tarball(proj.tmp / "o.tgz", extra=" x").read_bytes())
    res = proj.check()
    assert res.returncode == 1 and "mwg_integrity 와 다릅니다" in res.stdout


def test_정책을_바꾸고_sync를_안_하면_check가_잡는다(proj: Proj):
    set_toml(proj.root, 'baseline = "widely"', 'baseline = "2024"')
    res = proj.check()
    assert res.returncode == 1 and "정책이 바뀌었는데" in res.stdout


def test_ADV01_sync는_지원_기준을_mwgrc와_skill로_옮긴다(proj: Proj):
    set_toml(proj.root, 'baseline = "widely"', 'baseline = "2024"')
    assert sync(proj, "--tarball", str(proj.tarball)).returncode == 0
    assert json.loads((proj.root / ".mwgrc").read_text(encoding="utf-8"))["baseline"] == "2024"
    skill = (proj.root / ".claude/skills/modern-web-guidance/SKILL.md").read_text(encoding="utf-8")
    assert "This project's Baseline target is Baseline 2024." in skill
    assert proj.check().returncode == 0


def test_ADV01_루트가_아닌_곳의_mwgrc는_check가_잡는다(proj: Proj):
    write(proj.root, "web/.mwgrc", '{"baseline": "limited"}')
    res = proj.check()
    assert res.returncode == 1 and "web/.mwgrc" in res.stdout


def test_원본_형식이_바뀌면_sync가_멈춘다(tmp_path, fake_bin):
    p = build(tmp_path, fake_bin, ready=False)
    bad = make_tarball(tmp_path / "bad.tgz", skill="---\nname: x\n---\nno pinned commands\n")
    res = sync(p, "--pin", "1.0.0", "--tarball", str(bad), "--integrity", sri_of(bad))
    assert res.returncode == 1 and "형식이 바뀌었을" in res.stderr


def test_생성된_skill은_래퍼로_실행하고_HOLD_절을_가진다(proj: Proj):
    skill = (proj.root / ".claude/skills/modern-web-guidance/SKILL.md").read_text(encoding="utf-8")
    assert "modern-web-guidance@latest" not in skill and "npx -y modern-web-guidance" not in skill
    assert f'{W} search "<query>"' in skill and f'{W} retrieve "<id>"' in skill
    assert skill.startswith("---\nname: modern-web-guidance") and "## HOLD 프로젝트 규칙" in skill and "mwg:<id>" in skill


def test_ADV2_02_확장_코드가_바뀌면_check와_verify가_잡는다(proj: Proj):
    common = proj.root / ".claude/hold-web/common.py"
    common.write_text(common.read_text(encoding="utf-8") + "\n# tampered\n", encoding="utf-8")
    res = proj.check()
    assert res.returncode == 1 and "확장 코드가 설치된 내용과 다릅니다" in res.stdout
    res = verify(proj)
    assert res.returncode == 1 and "원본(extensions/web/kit)과 다릅니다" in res.stdout


def test_ADV2_02_매니페스트에_없는_확장_코드_파일도_잡는다(proj: Proj):
    write(proj.root, ".claude/hold-web/sitecustomize.py", "print('x')\n")
    res = proj.check()
    assert res.returncode == 1 and "매니페스트에 없는" in res.stdout


def test_CI_verify는_원본_코드로_전체_검사를_통과한다(proj: Proj):
    res = verify(proj)
    assert res.returncode == 0, res.stdout


# ── R15 레거시 패턴 검사 (ADV-04, 05, 06, 16, ADV2-06, 07) ──────────

def test_standard는_편집한_프런트_파일의_검출을_되돌린다(proj: Proj):
    write(proj.root, "web/app.js", LEGACY)
    res = proj.post("Write", file_path="web/app.js")
    assert res.returncode == 2 and "R15" in res.stderr and "web/app.js:1" in res.stderr
    assert f"{W} retrieve ime-safe-enter-submit" in res.stderr
    call = json.loads(proj.calls.read_text(encoding="utf-8").splitlines()[-1])
    assert "legacy-scan" in call["args"] and call["telemetry_off"]


def test_lite는_기록만_한다(proj: Proj):
    set_toml(proj.root, 'profile = "standard"', 'profile = "lite"')
    write(proj.root, "web/app.js", LEGACY)
    assert proj.post("Write", file_path="web/app.js").returncode == 0
    assert proj.log("web_scan")[-1]["verdict"] == "fail"


def test_ADV05_Bash로_쓴_프런트_파일도_검사한다(proj: Proj):
    write(proj.root, "web/b.js", LEGACY)
    res = proj.post("Bash", command="cat > web/b.js <<EOF")
    assert res.returncode == 2 and "web/b.js" in res.stderr


def test_ADV2_06_mtime과_크기를_되돌려도_내용_해시로_잡는다(proj: Proj):
    f = write(proj.root, "web/c.js", "x" * len(LEGACY))
    assert proj.post("Write", file_path="web/c.js").returncode == 0
    st = f.stat()
    f.write_text(LEGACY, encoding="utf-8")
    os.utime(f, ns=(st.st_atime_ns, st.st_mtime_ns))
    assert f.stat().st_size == st.st_size
    assert proj.post("Bash", command="touch -r ref web/c.js").returncode == 2


def test_ADV2_06_백그라운드나_실패한_명령이_바꾼_파일은_다음_훅에서_잡는다(proj: Proj):
    write(proj.root, "web/later.js", LEGACY)          # 훅 밖에서 바뀜
    res = proj.pre("Bash", command="ls")
    assert res.returncode == 2 and "web/later.js" in res.stderr and "지난 작업 이후" in res.stderr


def test_ADV2_06_이상한_파일_이름에도_훅이_죽지_않는다(proj: Proj):
    if os.name == "nt":
        pytest.skip("POSIX 바이트 파일 이름")
    os.makedirs(proj.root / "web", exist_ok=True)
    with open(os.fsencode(str(proj.root / "web")) + b"/\xff.js", "w", encoding="utf-8") as fh:
        fh.write(LEGACY)
    res = proj.post("Bash", command="x")
    assert res.returncode == 2 and "R15" in res.stderr


def test_ADV2_06_훅이_예외로_죽으면_막는다(proj: Proj):
    snap = proj.root / ".hold/logs/web_snap.json"
    snap.unlink()
    snap.mkdir()                                         # 스냅샷을 쓸 수 없게
    res = proj.pre("Bash", command="ls")
    assert res.returncode == 2 and "안전을 위해 막습니다" in res.stderr


@pytest.mark.parametrize("rel", ["test/a.test.js", "web/app.min.js", "examples/x.js", "web/-x.js"])
def test_ADV2_07_ADV06_흔한_제외_이름과_대시_이름도_검사한다(proj: Proj, rel):
    write(proj.root, rel, LEGACY)
    res = proj.post("Write", file_path=rel)
    assert res.returncode == 2 and rel in res.stderr


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
    assert proj.post("Write", file_path="web/a.js").returncode == 0
    write(proj.root, "web/sub/b.js", LEGACY)
    assert proj.post("Write", file_path="web/sub/b.js").returncode == 2
    set_toml(proj.root, '"ime-safe-enter-submit:web/*.js"', '"ime-safe-enter-submit:web/**"')
    write(proj.root, "web/sub/b.js", LEGACY + "// 2\n")
    assert proj.post("Write", file_path="web/sub/b.js").returncode == 0


def test_ADV16_jinja_템플릿도_HTML로_검사한다(proj: Proj):
    write(proj.root, "app/templates/chat.j2", "<script>" + LEGACY + "</script>")
    res = proj.post("Write", file_path="app/templates/chat.j2")
    assert res.returncode == 2 and "app/templates/chat.j2" in res.stderr


def test_node가_없으면_건너뛰고_regulated는_막는다(proj: Proj):
    empty = proj.tmp / "empty"
    empty.mkdir()
    payload = {"hook_event_name": "PostToolUse", "tool_name": "Write", "tool_input": {"file_path": "web/app.js"}}
    write(proj.root, "web/app.js", LEGACY)
    assert proj.hook(payload, path=[empty]).returncode == 0
    assert proj.log("web_scan")[-1]["verdict"] == "skip"
    set_toml(proj.root, 'profile = "standard"', 'profile = "regulated"')
    write(proj.root, "web/app.js", LEGACY + "// 2\n")
    assert proj.hook(payload, path=[empty]).returncode == 2


def test_외부_코드와_파이썬_파일은_검사하지_않는다(proj: Proj):
    write(proj.root, "node_modules/x/a.js", LEGACY)
    write(proj.root, "app/x.py", "x = 1\n")
    assert proj.post("Bash", command="x").returncode == 0
    assert not proj.calls.exists()


# ── H9 retrieve 증거 (ADV-09, ADV2-10) ──────────────────────────────

def test_ADV2_10_래퍼는_요청했고_출력에_나온_ID만_확인됨으로_기록한다(proj: Proj):
    assert wrapper(proj, "retrieve", "dialog,made-up,ime-safe-enter-submit").returncode == 0
    rec = proj.log("web_guidance")[-1]
    assert rec["requested"] == ["dialog", "made-up", "ime-safe-enter-submit"]
    assert rec["confirmed"] == ["dialog", "ime-safe-enter-submit"]


@pytest.mark.parametrize("cmd", ['echo "modern-web-guidance retrieve dialog"', "printf -- '--- Guide for dialog ---'"])
def test_ADV09_훅은_명령_문자열이나_출력으로_증거를_만들지_않는다(proj: Proj, cmd):
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


# ── R16 참조 가이드 (ADV-10, ADV2-11) ───────────────────────────────

SPEC_HEAD = "# Spec\n## 이해관계자 영향\n| ID | 방향 | 내용 | 승인 |\n|---|---|---|---|\n| SH-U01 | → | x | 아니오 |\n"


def spec_with(refs: str) -> str:
    return SPEC_HEAD + "## 참조 가이드\n" + refs + "\n## 뷰\n생략: 테스트\n"


@pytest.mark.parametrize("refs,ok", [
    ("- mwg:dialog — 모달은 <dialog>", True),
    ("- mwg:dialog\n- mwg:light-dismiss-a-dialog — closedby", True),
    ("생략: 프런트엔드 변경 없음 (API 응답 형식만 바뀜)", True),
    ("생략: <이유 — 예: 프런트엔드 변경 없음>", False),
    ("- `dialog`", False),
    ("- mwg:dialog\n- dialog-polyfil", False),
    ("- mwg:dialog-polyfil", False),
    ("- mwg:dialog\n생략: 없음입니다", False),
    ("(나중에)", False),
    ("생략: x", False),
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


@pytest.mark.parametrize("folder", ["chat-ui", "20200101-chat"])
def test_ADV2_11_폴더_이름으로_R16을_피하지_못한다(proj: Proj, folder):
    write(proj.root, f"changes/{folder}/spec.md", spec_with("- mwg:dialog-polyfil"))
    res = proj.check()
    assert res.returncode == 1 and folder in res.stdout


def test_확장을_켜기_전에_Git에_들어온_변경은_검사하지_않는다(proj: Proj):
    write(proj.root, "changes/20261101-old/spec.md", SPEC_HEAD)
    env = {**clean_env(), "GIT_AUTHOR_DATE": "2026-11-01T00:00:00", "GIT_COMMITTER_DATE": "2026-11-01T00:00:00",
           "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    for args in (["init", "-q"], ["add", "changes/20261101-old"], ["commit", "-q", "-m", "old"]):
        subprocess.run(["git", *args], cwd=proj.root, check=True, capture_output=True, env=env)
    import shutil
    from pathlib import Path
    res = proj.run("web_check.py", path=[proj.bin, Path(shutil.which("git")).parent])
    assert res.returncode == 0, res.stdout


def test_spec을_고치면_훅이_바로_참조_가이드를_검사한다(proj: Proj):
    write(proj.root, "changes/20261112-modal/spec.md", spec_with("- mwg:made-up"))
    res = proj.post("Write", file_path="changes/20261112-modal/spec.md")
    assert res.returncode == 2 and "mwg:made-up" in res.stderr


# ── pre-commit (ADV2-08), 측정 ──────────────────────────────────────

def test_ADV2_08_pre_commit_항목을_주석으로만_남기면_실패한다(tmp_path, fake_bin):
    p = build(tmp_path, fake_bin)
    pc = p.root / ".pre-commit-config.yaml"
    lines = [("# " + line if "hold-web-check" in line else line) for line in pc.read_text(encoding="utf-8").splitlines()]
    pc.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert p.check().returncode == 1
    set_toml(p.root, 'profile = "standard"', 'profile = "lite"')
    res = p.check()
    assert res.returncode == 0 and "WARN .pre-commit-config.yaml" in res.stdout


def test_측정_집계(proj: Proj):
    wrapper(proj, "retrieve", "dialog")
    proj.pre("Bash", command="npx modern-web-guidance@latest search x")
    m = json.loads(proj.check("--metrics").stdout)
    assert m["retrieve_confirmed"] == 1 and m["guard_block"] == 1 and m["guides_confirmed"] == ["dialog"]
