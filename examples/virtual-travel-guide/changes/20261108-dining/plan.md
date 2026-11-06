# Plan: 식당 추천

근거: [spec.md](spec.md) · 승인: 여행자 A

## 모듈별 작업 범위

### dining
- 작업 범위: `app/modules/dining/`
- 수정 금지: `app/contracts/`, `tests/contracts/`, `tests/golden/`, 다른 모듈
- 할 일: `api.recommend` — 검색 결과에 `MealConstraint.judge`를 적용해 제외·확인 필요를 나눈다. 검색은 `_internal/search.py`.
- 완료 조건: `pytest tests/golden -q` 통과, `lint-imports` 통과, `pyright app` 오류 0

### agent
- 작업 범위: `app/agent/`
- 할 일: 도구 `suggest_dining` 추가 (State에서 요청 읽기 → 계약 검증 → `dining.api.recommend` → JSON 반환)
- 완료 조건: 가짜 LLM 통합 테스트 `test_dining_flow` 통과

## 순서
1. dining 모듈 (worktree `feat/dining`)
2. agent 도구 (worktree `feat/dining-agent`, 1과 병렬 가능)

## 위험
- 필터를 LLM 프롬프트로 처리하면 놓칠 수 있다 → 필터는 코드(`MealConstraint.judge`)로만

## 증명
- `tests/golden/test_dining_golden.py` 3개 통과

## 계획 변경 기록
- 없음
