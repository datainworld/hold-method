"""사실 뷰 생성·드리프트 검사, 그리고 설치 스크립트의 동작."""
import subprocess
import sys

from conftest import KIT, run_script, write

CONTRACT = '''from decimal import Decimal
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field, computed_field


class _Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Ingredient(str, Enum):
    MEAT = "meat"
    FISH = "fish"


class MealConstraint(_Contract):
    excluded: frozenset[Ingredient] = Field(default=frozenset(), description="제외할 재료")


class Dish(_Contract):
    name: str
    price: Decimal


class DiningRequest(_Contract):
    city: str = Field(min_length=2)
    constraint: MealConstraint


class DiningShortlist(_Contract):
    dishes: list[Dish]

    @computed_field
    @property
    def total(self) -> Decimal:
        return sum((d.price for d in self.dishes), Decimal("0"))
'''


def test_계약에서_클래스_뷰를_만들고_드리프트를_잡는다(project):
    write(project, "app/__init__.py", "")
    write(project, "app/contracts/__init__.py", "")
    contract = write(project, "app/contracts/dining.py", CONTRACT)
    res = run_script(project, "gen_views.py")
    assert res.returncode == 0, res.stderr
    view = (project / "docs/architecture/views/generated/contracts.md").read_text(encoding="utf-8")
    assert "classDiagram" in view
    assert "DiningRequest --> MealConstraint : constraint" in view
    assert "MealConstraint --> Ingredient : excluded" in view
    assert "+total() computed" in view
    assert "_Contract" not in view

    assert run_script(project, "gen_views.py", "--check").returncode == 0
    contract.write_text(CONTRACT.replace("    price: Decimal\n", "    price: Decimal\n    spicy: bool = False\n"), encoding="utf-8")
    res = run_script(project, "gen_views.py", "--check")
    assert res.returncode == 1 and "다릅니다" in res.stdout


def test_계약_초안은_사실_뷰에_넣지_않는다(project):
    write(project, "app/__init__.py", "")
    write(project, "app/contracts/__init__.py", "")
    write(project, "app/contracts/_draft_venue.py", "from pydantic import BaseModel\nclass Venue(BaseModel):\n    name: str\n")
    run_script(project, "gen_views.py")
    view = (project / "docs/architecture/views/generated/contracts.md").read_text(encoding="utf-8")
    assert "Venue" not in view


def test_재설치는_사람이_고친_파일을_덮어쓰지_않는다(project):
    (project / "CLAUDE.md").write_text("# 내가 고친 규칙\n", encoding="utf-8")
    res = subprocess.run([sys.executable, str(KIT / "scripts/hold_init.py"), "--target", str(project)],
                         capture_output=True, text=True, check=True)
    assert (project / "CLAUDE.md").read_text(encoding="utf-8") == "# 내가 고친 규칙\n"
    assert "건너뜀: CLAUDE.md" in res.stdout
    assert (project / ".claude/settings.hold.json").exists()  # 기존 settings.json 은 보존


def test_설치는_프로필과_필수_폴더를_만든다(tmp_path):
    root = tmp_path / "p"
    subprocess.run([sys.executable, str(KIT / "scripts/hold_init.py"), "--target", str(root), "--profile", "standard"],
                   check=True, capture_output=True)
    assert 'profile = "standard"' in (root / "hold.toml").read_text(encoding="utf-8")
    for d in ["changes/_template", "docs/adr", "tests/golden", ".claude/skills/hold-views"]:
        assert (root / d).is_dir(), d
    assert ".hold/logs/" in (root / ".gitignore").read_text(encoding="utf-8")
