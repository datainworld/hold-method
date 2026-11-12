# 이 프로젝트는 HOLD 방법론(v0.1)을 따른다

프로필과 경로는 `hold.toml`을 본다. 방법론 본문: https://github.com/datainworld/hold-method

## 사람이 소유한 것 — 수정 금지
- `hold.toml`의 `[protect].paths` 전부 (계약, 채점 기준 테스트, 이해관계자 정의서, 설정)
- 바꿔야 한다고 판단되면 멈추고 이유·선택지를 보고한다. 훅이 수정을 막는다.
- 계약에 들어갈 결정(단위, 통화, None의 의미, 허용 범위, 실패 방식, 누가 계산하나)은 스스로 정하지 말고 질문으로 남긴다.

## 작업 순서
1. 변경은 `changes/<YYYYMMDD-이름>/intent.md`에서 시작한다. 양식: `changes/_template/`
2. spec.md에는 `## 이해관계자 영향`(정의서 ID)과 `## 뷰`(sequenceDiagram, 실패 경로 포함)를 반드시 쓴다.
3. 계약 변경이 필요하면 `changes/<폴더>/contract_draft.py` 초안과 질문 목록만 만든다. `app/contracts/`로 옮겨 확정하는 것은 사람이 한다.
4. 구현은 plan mode로 시작한다. plan.md의 `## 모듈별 작업 범위`에 모듈별 범위·금지 파일·완료 조건을 쓴다.
5. 구현이 plan.md에서 벗어나면 plan.md를 같은 커밋에서 고친다.

## 구조 규칙
- 모듈끼리는 서로 import하지 않는다. 다른 모듈은 `api.py`로만 부른다. `_internal/`은 그 모듈만 쓴다.
- 계산·정렬·필터·횟수 세기는 LLM이 아니라 코드가 한다. LLM이 만든 SQL은 실행하지 않는다.
- 새 최상위 폴더를 만들지 않는다. 필요하면 이유와 함께 제안한다.

## 검증 — 완료 보고에는 실제 출력을 붙인다
- `python scripts/check_views.py` — 산출물·필수 뷰
- `python scripts/gen_views.py --check` — 사실 뷰 최신성
- `lint-imports`, `pyright app`, `pytest -q`
- 버그를 고칠 때는 재현 테스트를 먼저 쓰고, 그 테스트가 실패하는 것을 확인한 뒤 고친다.
- 실패한 테스트는 코드를 고쳐 통과시킨다. 테스트를 고쳐 통과시키지 않는다.

## 웹 프런트엔드 — `hold.toml`의 `[web].enabled = true`일 때만 (방법론 9장)
- HTML·CSS·클라이언트 JS 작업은 `modern-web-guidance` skill로 가이드를 먼저 찾는다. 버전은 `hold.toml`의 `[web].mwg_version`으로 고정되어 있고, `@latest`나 다른 버전으로 실행하면 훅이 막는다.
- 브라우저 지원 기준과 대체 동작 정책은 `hold.toml`의 `[web]`이 원본이다. 이 파일이나 AGENTS.md에 지원 정책을 쓰지 않는다. 바꿔야 한다고 판단되면 멈추고 보고한다.
- 가이드가 대체 전략을 둘 이상 제시하면 고르지 말고 spec.md `## 계약 질문 목록`에 `(웹)` 질문으로 남긴다 (R18).
- spec.md `## 참조 가이드`에 참조한 가이드 ID를 백틱으로 적는다. 쓰지 않았으면 `생략: 이유`.
- 프런트엔드 파일을 고치면 훅이 레거시 패턴을 검사한다. 오탐이라고 판단되면 코드를 비틀지 말고 보고한다.

## 알려진 함정
- (실증 중 같은 실수가 두 번 나오면 여기에 한 줄 추가한다)
