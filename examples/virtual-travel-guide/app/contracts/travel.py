"""여행 가이드 계약 — 사람 소유 (보호 경로). 계약 게이트(Stage 2.5)에서 확정.

사람이 내린 결정 (changes/20261108-dining/spec.md 계약 질문 목록):
- 가격은 1인 기준 가격대(1~4)
- 육수에 든 재료도 제외 대상이다
- 재료 정보가 없으면 결과에 남기되 needs_check = True
- 실패는 예외가 아니라 빈 목록 + notes
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, computed_field


class _Contract(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class Ingredient(str, Enum):
    MEAT = "meat"
    FISH = "fish"
    DAIRY = "dairy"
    EGG = "egg"


class Restaurant(_Contract):
    """가상 장소 API(SH-S02) 결과를 계약으로 옮긴 것."""

    name: str = Field(min_length=1)
    price_level: int = Field(ge=1, le=4, description="Price band per person, 1 (cheap) to 4 (expensive)")
    ingredients: frozenset[Ingredient] | None = Field(
        default=None, description="Main ingredients including broth. None means unknown, not 'none'"
    )
    needs_check: bool = Field(default=False, description="True when ingredients are unknown")


class MealConstraint(_Contract):
    """식사 조건 (주인: SH-U02). 결정: 육수에 든 재료도 제외한다."""

    excluded: frozenset[Ingredient] = Field(default=frozenset(), description="Ingredients to exclude, including broth")

    def judge(self, r: Restaurant) -> Restaurant | None:
        """제외 대상이면 None, 재료를 모르면 needs_check 를 켠 사본, 아니면 그대로."""
        if r.ingredients is None:
            return r.model_copy(update={"needs_check": True})
        if self.excluded & r.ingredients:
            return None
        return r


class DiningRequest(_Contract):
    city: str = Field(min_length=2)
    party_size: int = Field(ge=1, le=20, description="Number of diners (integer)")
    constraint: MealConstraint


class DiningShortlist(_Contract):
    restaurants: list[Restaurant]
    dropped: int = Field(default=0, ge=0, description="Restaurants removed by the meal constraint")
    notes: str = ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def needs_check_count(self) -> int:
        return sum(1 for r in self.restaurants if r.needs_check)
