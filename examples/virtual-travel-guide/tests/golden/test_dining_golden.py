"""사람 소유 · 보호 — 사람의 결정("육수도 제외", "모르면 확인 필요")을 고정하는 골든 테스트.

  입력 4곳, 조건: 고기·생선 제외 (채식)
  - 채소 덮밥집 {dairy}           → 남음
  - 돈코츠 라멘집 {meat}           → 제외 (육수에 돼지뼈)
  - 소바집 {fish} (가쓰오 육수)     → 제외 (육수에 생선)
  - 재료 정보 없는 카페 None         → 남음, needs_check
  기대: 2곳 남음, 2곳 제외, 확인 필요 1곳
"""
from app.contracts.travel import DiningRequest, Ingredient, MealConstraint, Restaurant
from app.modules.dining.api import apply_constraint

VEGETARIAN = MealConstraint(excluded=frozenset({Ingredient.MEAT, Ingredient.FISH}))
REQ = DiningRequest(city="Kyoto", party_size=2, constraint=VEGETARIAN)
FOUND = [
    Restaurant(name="채소 덮밥집", price_level=1, ingredients=frozenset({Ingredient.DAIRY})),
    Restaurant(name="돈코츠 라멘집", price_level=1, ingredients=frozenset({Ingredient.MEAT})),
    Restaurant(name="소바집", price_level=2, ingredients=frozenset({Ingredient.FISH})),
    Restaurant(name="재료 정보 없는 카페", price_level=2, ingredients=None),
]


def test_broth_is_excluded():
    result = apply_constraint(REQ, FOUND)
    assert [r.name for r in result.restaurants] == ["채소 덮밥집", "재료 정보 없는 카페"]
    assert result.dropped == 2


def test_unknown_ingredients_need_check():
    result = apply_constraint(REQ, FOUND)
    assert result.needs_check_count == 1
    assert result.restaurants[1].needs_check is True


def test_no_constraint_keeps_everything():
    req = DiningRequest(city="Kyoto", party_size=2, constraint=MealConstraint())
    assert apply_constraint(req, FOUND).dropped == 0
