# 4장. 아키텍처 규칙

이 장은 DeepData 내부 가이드 "AI-friendly 모듈러 아키텍처 7원칙"을 HOLD의 규칙 A1~A7로 흡수한 것입니다. 예제는 **가상의 여행 가이드 앱**으로 새로 썼습니다. 원칙 H5(계약 우선), H6(경계는 가져오고 분산은 피한다), H7(통제는 기계), H9(증거)가 이 장의 바탕입니다.

> MSA처럼 설계하고, 모놀리스처럼 배포하고, 운영 특성이 갈라지는 지점에서만 쪼갠다.

## 규칙 한눈에

| 규칙 | 묻는 질문 | 산출물 | 누가 지키나 |
| --- | --- | --- | --- |
| A1 경계 | 어디서 나누나 | 모듈 폴더, `api.py`/`_internal/`, 모듈별 CLAUDE.md | import-linter |
| A2 계약 | 경계를 넘는 데이터는 어떤 모양과 뜻인가 | `app/contracts/`, 계약 테스트 | pyright, Pydantic, 계약 테스트, 보호 훅 |
| A3 집행 | 규칙을 누가 지키게 하나 | `.importlinter`, `.claude/`, 미들웨어 | (집행 계층 자체) |
| A4 데이터 | 데이터는 누구 것인가 | 모듈별 스키마, 읽기 전용 연결, 고정 SQL | DB 권한 |
| A5 통신 | 경계를 어떻게 건너나 | 함수 호출, 가장자리 재시도, (필요 시) Outbox | 코드 구조, 의존 규칙 |
| A6 관측 | 실제로 무슨 일이 있었나 | JSON 로그, cid, 추적 메타데이터 | (기록 장치) |
| A7 검증 | 무엇이 합격인가 | 계약·골든·통합·단위·평가 테스트 | 보호 훅 |

A1·A2·A4·A5는 사람이 정하는 내용이고, A3은 그것을 기계가 지키게 하는 집행 계층이며, A6·A7은 결과를 확인하는 장치입니다.

## 예제: 가상 여행 가이드

사용자가 "내일 교토에서 점심 먹을 곳과 오후 일정을 추천해 줘"라고 하면, 코디네이터 에이전트가 요청을 정리한 뒤 세 모듈에 일을 나눕니다.

| 모듈 | 하는 일 | 외부 자원 | 바뀌는 이유 |
| --- | --- | --- | --- |
| `places` | 관광지 후보 찾기 | 장소 API | 관광지 평가 기준 |
| `dining` | 식사 조건에 맞는 식당 찾기 | 장소 API (식당 범주) | 식사 조건 규칙 |
| `itinerary` | 시간 순서로 일정 배치 | 없음 (결정론적 계산) | 배치 규칙 |

`dining`과 `places`는 같은 외부 API를 쓰지만 바뀌는 이유가 다르므로 다른 모듈입니다(A1의 네 질문 중 ③).

## A1. 경계: 모노레포 + 모듈러 모놀리스

저장소 하나, 배포 하나. 그 안을 모듈로 엄격하게 나눕니다. 에이전트가 전체를 볼 수 있어야 맥락을 잃지 않고(모노레포), 모듈이 작아야 한 번에 한 부분만 정확히 고칩니다(모듈).

```
app/
├── contracts/         # 사람 소유 (A2) — 모듈 사이 입출력 계약
├── platform/          # 공통 인프라만: 설정, 로깅, 외부 연결
├── modules/
│   ├── places/{CLAUDE.md, api.py, _internal/}
│   ├── dining/{CLAUDE.md, api.py, _internal/}
│   └── itinerary/{CLAUDE.md, api.py, _internal/}
├── agent/             # 코디네이터: 판단과 위임만
└── serving/           # CLI, API 서버
```

**모듈을 나누는 네 질문**: ① 업무 용어로 설명되는가 ② 자기만의 외부 자원이 있는가 ③ 바뀌는 이유가 하나인가 ④ 에이전트가 한 번에 읽을 만한 크기인가.

**공개 창구는 얇게.** 다른 모듈은 `api.py`만 부릅니다. `api.py`는 로그를 남기고, 내부 구현을 부르고, 불변조건을 강제합니다.

```python
# app/modules/dining/api.py
from app.contracts.travel import DiningRequest, DiningShortlist
from app.modules.dining._internal import search
from app.platform.logging import get_logger, log_span

logger = get_logger("modules.dining")

async def recommend(req: DiningRequest) -> DiningShortlist:
    """식사 조건을 지키는 식당 후보를 찾는다."""
    with log_span(logger, "dining.recommend", city=req.city):
        found = await search.run(req)
    # 불변조건: 식사 조건을 어기는 후보는 결과에 없다 (LLM이 놓쳐도 코드가 거른다)
    kept = [r for r in found.restaurants if req.constraint.allows(r)]
    return found.model_copy(update={"restaurants": kept, "dropped": len(found.restaurants) - len(kept)})
```

**코디네이터는 얇은 조율자.** `agent/`에는 판단과 위임만 둡니다. 검색·SQL·계산은 각 모듈 안에 있습니다. 코디네이터 생성 함수는 모델을 주입할 수 있게 열어 두어, 테스트에서 가짜 모델로 전체 흐름을 검증합니다(A7).

**범위 개념.** 프로젝트 ⊃ Git ⊃ 배포 범위는 넓게 하나로 잡아 에이전트가 전체를 보게 하고, 그 안을 모듈 범위로 세로로 잘라 한 번에 한 조각만 보게 합니다. Git 범위는 "볼 수 있는 것", 모듈 범위는 "봐야 하는 것"입니다.

## A2. 계약 우선

계약은 모듈 사이에서 오가는 데이터의 **모양·허용 범위·의미·실패 방식**을 구현보다 먼저 사람이 코드로 확정하고, 도구가 강제하게 하는 것입니다.

| 층 | 무엇을 약속하나 | 예 |
| --- | --- | --- |
| 형태 | 어떤 필드가 어떤 타입으로 | `party_size: int`, `restaurants: list[Restaurant]` |
| 허용 범위 | 어떤 값까지 받나 | `ge=1, le=20`, `extra="forbid"` |
| 의미 | 그 값이 무엇을 뜻하나 | `price_level`은 "1인 기준 가격대(1~4)" |
| 실패 방식 | 안 될 때 어떻게 알리나 | 결과 없음 → 빈 목록 + `notes`, 외부 장애 → 실패 메시지 |

```python
# app/contracts/travel.py — 사람 소유 (보호 경로)
class _Contract(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

class Ingredient(str, Enum):
    MEAT = "meat"
    FISH = "fish"
    DAIRY = "dairy"

class MealConstraint(_Contract):
    """식사 조건. 사람이 정한 결정: '육수에 든 재료도 제외 대상이다'."""
    excluded: frozenset[Ingredient] = Field(default=frozenset(), description="Ingredients to exclude, including broth")

    def allows(self, r: "Restaurant") -> bool:
        return not (self.excluded & r.ingredients)

class DiningRequest(_Contract):
    city: str = Field(min_length=2)
    party_size: int = Field(ge=1, le=20, description="Number of diners (integer)")
    constraint: MealConstraint
```

**계약 우선의 세 조건.** 먼저(구현 전에 경계를 정한다), 사람이(계약은 사람이 소유하고 에이전트는 수정할 수 없다), 넓게(타입뿐 아니라 범위·의미·실패 방식·불변조건까지).

**현실적인 작성법.** 사람이 계약을 전부 손으로 쓰지 않습니다.

1. 계약은 **모듈 사이 이음매에만** 둡니다: 모듈 api의 입출력, 코디네이터 State, LLM 구조화 출력, 외부 API·DB와 맞닿는 데이터.
2. **초안은 에이전트, 결정은 사람.** 에이전트는 `changes/<id>/contract_draft.py`와 질문 목록을 씁니다. 사람은 "가격은 1인 기준인가 총액인가?" 같은 질문에 답합니다. 이것은 코딩이 아니라 요구사항 분석입니다.
3. **처음엔 느슨하게, 문제가 생길 때 조입니다.** 필수 필드와 핵심 의미만 먼저 고정합니다.
4. **이미 있는 명세에서 생성합니다.** 공공데이터 포털처럼 OpenAPI 명세가 있으면 `datamodel-code-generator`로 모델을 만들고 사람은 범위와 의미만 확인합니다.
5. **승인한 결정은 테스트로 고정합니다.** `test_육수에_든_재료도_제외한다` 같은 계약 테스트가 사람의 결정을 기억합니다.

**SI 비유.** 인터페이스 정의서 = `contracts/`, 인수 기준 = 계약·골든 테스트, 발주처 승인 없이 정의서 변경 불가 = 보호 훅. 차이는 하나입니다. 정의서가 코드라서, 매 수정마다 기계가 대조합니다.

## A3. 규칙을 도구로 강제

CLAUDE.md에 규칙을 적는 것은 안내이고, 어기면 검사가 실패하게 만드는 것은 통제입니다.

| 지킬 규칙 | 정한 곳 | 집행 도구 | 잡는 시점 |
| --- | --- | --- | --- |
| 모듈 경계 | A1 | import-linter (`.importlinter`) | 수정 직후(훅), 커밋, CI |
| 계약의 형태·범위 | A2 | pyright, Pydantic 실행 중 검증 | 수정 직후, 실행 중 |
| 계약의 의미·불변조건 | A2 | 계약 테스트 | 커밋, CI |
| 계약·채점 기준 보호 | A2, A7 | `protect_paths.py` | 수정 시도 순간 |
| 호출 횟수, 문자 형식 등 운영 규칙 | 운영 | LangChain 미들웨어(예: `ToolCallLimitMiddleware`), 코드 변환 | 실행 중 |

`.importlinter` 견본(`kit/templates/importlinter.example`)의 세 규칙: ① 의존 방향은 `serving → agent → modules → contracts → platform` ② 도메인 모듈끼리는 서로 import하지 않는다 ③ 모듈 `_internal`은 밖에서 직접 import하지 않는다(`api.py`를 거치는 간접 경로는 허용).

**한 도구로는 부족합니다.** 경계만 어긴 코드(공개 창구를 건너뛰고 `_internal`을 직접 부름)는 타입 검사와 계약 테스트를 통과합니다. 계약 의미만 어긴 코드(총액 자리에 1인 가격)는 import 검사와 타입 검사를 통과합니다. 그래서 세 겹이 다 필요합니다.

**프롬프트 부탁을 코드로.** "검색은 10회까지만 하라", "악센트 문자를 쓰지 마라" 같은 지시는 LLM이 어길 수 있습니다. 횟수는 미들웨어가 세고, 문자 변환은 코드가 합니다.

## A4. 데이터 소유권

데이터는 소유 모듈만 읽고 씁니다. 다른 모듈과 LLM은 공개 함수로만 받습니다. 코드 경계만 있고 데이터 경계가 없으면, 모듈이 SQL로 다른 모듈의 테이블을 직접 읽어 A1을 우회합니다.

| 허용 | 금지 |
| --- | --- |
| 소유 모듈이 정해진 SQL로 읽기 | LLM이 만든 SQL 실행 |
| 다른 모듈이 공개 함수로 결과 받기 | 다른 모듈이 테이블에 직접 접근 |
| 매개변수 바인딩 | 문자열을 이어 붙여 SQL 만들기 |
| 필요한 권한만 (읽기 전용 연결, 스키마별 계정) | 모든 모듈이 관리자 계정 하나를 공유 |

PostgreSQL에서는 모듈마다 스키마와 계정을 나눕니다. 예: `places` 스키마에는 `hold_places` 계정이 SELECT만, LangGraph 체크포인트용 `agent` 스키마에는 `hold_agent` 계정이 생성·쓰기 권한을 갖습니다.

## A5. 함수 호출 우선, 이벤트는 Outbox

모듈끼리는 네트워크 대신 함수로 부릅니다. 함수 호출에는 타임아웃·재시도·부분 실패가 없습니다. 네트워크 호출은 외부 시스템과 맞닿는 **가장자리**에만 두고, 그곳에 재시도·호출 상한·"실패를 예외 대신 메시지로 돌려주기"를 한꺼번에 둡니다.

- 한 모듈이 실패해도 코디네이터는 나머지로 결과를 완성합니다. 장소 API가 죽어도 일정 배치(`itinerary`)는 동작합니다.
- 비동기 이벤트(예: 매일 밤 영업시간 재확인)는 필요해질 때만 Outbox 테이블 + 워커로 추가합니다. 처리 함수는 멱등이어야 합니다.

**서비스로 떼어내는 기준**은 "코드가 커져서"가 아니라 "운영 특성이 달라서"입니다. 하드웨어가 다른가(자체 sLLM을 GPU 서버에서 운영), 확장 패턴이 다른가, 장애 격리가 필요한가, 배포 주기가 다른가 — 하나라도 "예"면 그 모듈만 검토하고 ADR을 씁니다. A2·A4를 지켜 왔다면 계약과 데이터가 이미 분리되어 있어, 호출 방식만 함수에서 HTTP로 바꾸면 됩니다.

## A6. 에이전트가 읽는 관측성

요청 하나에 추적 번호(correlation ID, cid) 하나를 붙여 코디네이터부터 각 모듈까지 같은 번호로 묶습니다. 로그는 JSON 한 줄씩 남기고, 같은 cid를 LangSmith 같은 추적 도구의 메타데이터에도 기록합니다. Python의 `contextvars`로 cid를 전달하면 비동기 요청이 섞이지 않습니다.

```json
{"ts":"2026-12-08T12:02:14","level":"INFO","logger":"app.modules.dining","cid":"7c41e2a9","msg":"dining.recommend.end","duration_ms":812,"dropped":2}
```

문제가 생기면 "로그 파일 경로 + cid"만 에이전트에게 넘깁니다. 에이전트가 흐름을 재구성하고, 원인 모듈을 특정하고, 고치기 전에 재현 테스트를 씁니다. 사고 기록(Stage 6)의 재구성 시퀀스 뷰도 이 로그로 그립니다.

## A7. 검증 계층은 사람이 소유

합격 기준은 사람이 정하고, 에이전트는 그 기준을 통과하는 코드를 씁니다.

| 계층 | 위치 | 소유 | LLM | 외부 API | 언제 |
| --- | --- | --- | --- | --- | --- |
| 계약 테스트 | `tests/contracts/` | 사람 · 보호 | 없음 | 없음 | 매 커밋 |
| 골든 테스트 | `tests/golden/` | 사람 · 보호 | 없음 | 없음 | 매 커밋 |
| 통합 테스트 | `tests/integration/` | 공동 · 리뷰 | 가짜 | 가짜 | 매 커밋 |
| 단위 테스트 | `app/**/tests/` | 에이전트 | 없음 | 가짜 | 매 커밋 |
| 서비스 평가 | `tests/evals/` | 사람 · 보호 | 실제 | 실제 | 배포 전 |

- **골든 테스트는 손으로 검산할 수 있어야 합니다.** 작은 입력을 테스트 안에서 만들고, 기대값의 계산 과정을 주석으로 풀어 적습니다.
- **가짜 LLM 통합 테스트.** 정해진 대본대로 답하는 가짜 모델을 코디네이터에 넣고, 전문 모듈은 가짜 함수로 바꿔 State 흐름만 검사합니다. API 키 없이 몇 초 안에 끝나므로 매 커밋에 돌릴 수 있습니다.
- **실제 LLM 평가는 문장이 아니라 행동을 봅니다.** 무엇을 기록했고 어떤 도구를 불렀는지를 검사합니다.
- **서비스 평가와 하네스 평가를 구분합니다.** 서비스 평가(`tests/evals/`)는 우리가 만든 에이전트의 행동을, 하네스 평가(Standard 이상, `evals/harness/`)는 코딩 에이전트가 이 저장소의 규칙을 지키며 구현하는지를 봅니다.

## 안티패턴

| 안티패턴 | 증상 | 처방 |
| --- | --- | --- |
| LLM에게 계산 맡기기 | 합계·정렬이 가끔 틀림 | 계산은 코드로, 합계는 `computed_field` (A2) |
| LLM에게 SQL 맡기기 | LLM이 만든 쿼리를 그대로 실행 | 고정 SQL, 읽기 전용 연결 (A4) |
| 프롬프트로 제한하기 | "10회까지만"을 LLM이 셈 | 미들웨어로 강제 (A3) |
| 계약 없는 자유 텍스트 | 모듈 결과를 문장으로 넘김 | Pydantic 계약 + 구조화 출력 (A2) |
| 뚱뚱한 코디네이터 도구 | 도구 함수에 검색·필터·계산이 다 들어감 | 도구는 State 읽기 → 계약 검증 → api 호출 → 반환만 (A1) |
| 에이전트가 테스트까지 수정 | 기대값을 바꿔 통과 | 채점 기준 보호 (A7, H1) |
| 에이전트가 계약까지 정함 | 단위·의미를 추측 | 질문 목록으로 사람에게 (A2) |
| AI가 빠르니 서비스 10개로 시작 | 배포·모니터링·장애 대응이 서비스 수만큼 | 모듈러 모놀리스로 시작 (A5) |
| 분산 모놀리스 | 서비스는 나눴는데 DB 공유 | 합치거나 데이터부터 분리 (A4) |
| 주인 없는 폴더 | `temp/`, `output/`, `utils/` | 폴더 하나에 주인 하나 (H2) |
