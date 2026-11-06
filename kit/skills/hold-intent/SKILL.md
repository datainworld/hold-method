---
name: hold-intent
description: HOLD Stage 1 — 새 아이디어나 요청을 인터뷰해 changes/<날짜-이름>/intent.md 초안을 만든다. "이런 기능을 만들고 싶다", "이거 바꿔 줘"처럼 형태가 잡히지 않은 요청이 들어오면 사용한다.
---
# HOLD intent 인터뷰

목표: 발안자의 말을 잃지 않고, 다음 단계(Design)가 바로 읽을 수 있는 intent.md를 만든다.

## 먼저 읽을 것
1. `hold.toml` — 프로필과 경로
2. `docs/architecture/stakeholders.md` — 이해관계자 정의서
3. `docs/architecture/module-map.md` — 모듈 지도
4. `changes/_template/intent.md` — 양식

## 인터뷰 (한 번에 한두 개씩, 발안자의 말로)
- 지금 무엇을 할 수 없나? 누가 불편한가?
- 이 일에 관련된 사람은 누구인가? **함께 쓰는 사람, 결과를 받는 사람**까지 묻는다.
- 이 일에 관련된 **외부 시스템**은 무엇인가? (API, DB, 메일, 메신저 등)
- 무엇이 되면 성공인가? 어떻게 확인하나?
- 꼭 지켜야 할 조건은? 하지 말아야 할 것은?
- 아직 모르는 것은? → 답을 지어내지 말고 "열린 질문"으로 남긴다.

## 쓰기 규칙
- 폴더: `changes/<YYYYMMDD-짧은이름>/intent.md` (양식 그대로)
- `## 이해관계자`에는 정의서의 SH-ID만 쓴다. 정의서에 없는 대상은 `## 정의서 추가 제안`에 적는다. **정의서 파일은 직접 고치지 않는다** (사람 소유).
- `## 영향 모듈`은 추정치임을 밝힌다.
- 업무 흐름이 바뀌면 `## 뷰`에 before/after 흐름(flowchart)을 넣고, 아니면 `생략: 이유`.
- 다 쓰면 `python scripts/check_views.py changes/<폴더>`를 돌리고 출력을 보고한다.
- 발안자가 내용을 확인·수정한 뒤에 커밋한다.
