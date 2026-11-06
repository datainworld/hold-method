"""dining 모듈의 유일한 공개 창구."""
from __future__ import annotations

from app.contracts.travel import DiningRequest, DiningShortlist, Restaurant
from app.modules.dining._internal import search


def apply_constraint(req: DiningRequest, found: list[Restaurant]) -> DiningShortlist:
    """불변조건: 식사 조건이 제외한 재료가 확인된 식당은 결과에 없다 (LLM이 아니라 코드가 거른다)."""
    kept = [j for j in (req.constraint.judge(r) for r in found) if j is not None]
    return DiningShortlist(restaurants=kept, dropped=len(found) - len(kept))


async def recommend(req: DiningRequest) -> DiningShortlist:
    """식사 조건을 지키는 식당 후보를 찾는다. 장소 API가 실패하면 빈 목록 + notes."""
    try:
        found = await search.run(req)
    except search.SearchFailed as exc:
        return DiningShortlist(restaurants=[], notes=f"검색 실패: {exc}")
    return apply_constraint(req, found)
