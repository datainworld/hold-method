"""가상 장소 API(SH-S02) 가장자리. 실제 구현에서는 여기에만 네트워크 호출과 재시도를 둔다."""
from __future__ import annotations

from app.contracts.travel import DiningRequest, Restaurant


class SearchFailed(Exception):
    """장소 API가 재시도 후에도 실패했다."""


async def run(req: DiningRequest) -> list[Restaurant]:  # pragma: no cover - 예제의 자리표시
    raise SearchFailed("가상 예제에는 실제 장소 API 연결이 없습니다")
