"""R01: 보호 경로는 사람만 수정한다 — 일부러 넣은 위반이 걸리는지, 정상 작업은 통과하는지."""
import pytest

from conftest import run_hook


@pytest.mark.parametrize("path", [
    "app/contracts/dining.py",
    "tests/golden/test_dining_golden.py",
    "tests/contracts/test_api.py",
    "docs/architecture/stakeholders.md",
    "hold.toml",
    ".importlinter",
    ".claude/settings.json",
    "app\\contracts\\dining.py",          # Windows 경로
])
def test_보호_경로_수정은_차단된다(project, path):
    res = run_hook(project, "protect_paths.py", {"tool_name": "Edit", "tool_input": {"file_path": path}})
    assert res.returncode == 2
    assert "사람이 소유한 파일" in res.stderr


def test_절대경로도_차단된다(project):
    path = str(project / "app/contracts/dining.py")
    res = run_hook(project, "protect_paths.py", {"tool_name": "Write", "tool_input": {"file_path": path}})
    assert res.returncode == 2


@pytest.mark.parametrize("path", [
    "app/modules/dining/api.py",
    "changes/20261110-dining/contract_draft.py",
    "changes/20261110-dining/spec.md",
    "docs/architecture/views/context.md",
])
def test_보호되지_않은_경로는_허용된다(project, path):
    res = run_hook(project, "protect_paths.py", {"tool_name": "Edit", "tool_input": {"file_path": path}})
    assert res.returncode == 0, res.stderr


@pytest.mark.parametrize("cmd", [
    "echo x > tests/golden/test_a.py",
    "sed -i 's/Decimal/float/' app/contracts/dining.py",
    "cat new.py | tee app/contracts/dining.py",
    "rm -rf tests/evals",
    "git checkout -- app/contracts/dining.py",
])
def test_셸로_보호_경로를_바꾸는_것도_차단된다(project, cmd):
    res = run_hook(project, "protect_paths.py", {"tool_name": "Bash", "tool_input": {"command": cmd}})
    assert res.returncode == 2, cmd


@pytest.mark.parametrize("cmd", [
    "pytest tests/contracts tests/golden -q 2>&1",
    "cat hold.toml",
    "python scripts/check_views.py > /dev/null",
    "lint-imports && pyright app",
])
def test_보호_경로를_읽기만_하는_셸은_허용된다(project, cmd):
    res = run_hook(project, "protect_paths.py", {"tool_name": "Bash", "tool_input": {"command": cmd}})
    assert res.returncode == 0, (cmd, res.stderr)


def test_차단은_측정용_로그에_남는다(project):
    run_hook(project, "protect_paths.py", {"tool_name": "Edit", "tool_input": {"file_path": "app/contracts/a.py"}})
    log = (project / ".hold/logs/hooks.jsonl").read_text(encoding="utf-8")
    assert '"verdict": "block"' in log
