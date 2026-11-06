# 모듈 지도

| 모듈 | 업무 책임 (한 문장) | 맞닿는 이해관계자 | 소유 데이터 | 공개 창구 |
|---|---|---|---|---|
| agent | 요청을 이해하고 모듈에 일을 나눈다 | SH-U01, SH-S01, SH-S03 | 대화 기록 (agent 스키마) | `run(message)` |
| places | 관광지 후보를 찾는다 | SH-S02 | 없음 | `places/api.py` |
| dining | 식사 조건을 지키는 식당 후보를 찾는다 | SH-U02, SH-S02 | 없음 | `dining/api.py` |
| itinerary | 후보를 시간 순서로 배치한다 (LLM 없음) | SH-U01 | 없음 | `itinerary/api.py` |

`places`와 `dining`은 같은 장소 API를 쓰지만 바뀌는 이유가 다르다(관광지 평가 기준 vs 식사 조건 규칙). 그래서 다른 모듈이다.
