"""가상 예제가 키트 검사를 모두 통과하는지 — 문서가 보여 주는 예제가 실제로 동작해야 한다."""
import shutil
import subprocess
import sys

from conftest import KIT, REPO, run_script


def test_가상_예제는_키트_검사를_통과한다(tmp_path):
    root = tmp_path / "example"
    shutil.copytree(REPO / "examples/virtual-travel-guide", root)
    subprocess.run([sys.executable, str(KIT / "scripts/hold_init.py"), "--target", str(root)], check=True, capture_output=True)

    res = run_script(root, "check_views.py")
    assert res.returncode == 0, res.stdout
    res = run_script(root, "gen_views.py", "--check")
    assert res.returncode == 0, res.stdout
    res = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/golden"], cwd=root, capture_output=True, text=True)
    assert res.returncode == 0, res.stdout
