# CHANGELOG

판 번호 규칙: `v0.N`은 실증 회고를 거친 개정판, `v0.N.x`는 작업을 막는 결함만 고친 패치입니다. 자세한 규칙은 [method/08-revision.md](method/08-revision.md).

## v0.1 — 2026-11 (초판, 동결 예정 2026-11-09)

### 처음 정한 것

- 이름 HOLD (Human-Owned Loop Development), 부제 "사람이 쥐는 AI-Native 개발방법론"
- 원칙 H1~H10 (모두 근거 등급 "가설")
- 8단계 프로세스: Stage 0 착수 ~ Stage 6 운영, Design과 Build 사이의 Stage 2.5 계약 게이트
- 프로필 3종: Lite(완전 정의), Standard·Regulated(추가 항목만 정의)
- 통제 대응표: Lite 규칙 13개 중 8개 강제, 2개 부분 강제, 3개 안내만
- 최소 키트: 템플릿 13종, 훅 2개(`protect_paths.py`, `post_edit.py`), 스크립트 3개(`check_views.py`, `gen_views.py`, `hold_init.py`), 스킬 3개(`hold-intent`, `hold-architecture`, `hold-views`)
- 키트 테스트 37개 (위반 탐지와 정상 통과를 함께 확인), 가상 예제 1개
- 라이선스: 문서 CC BY 4.0, 코드 Apache-2.0

### 기반에서 가져온 것과 더한 것

- AI-Native SDLC playbook: 산출물 체인, 단계별 지표, 훅 기반 게이트
- 모듈러 아키텍처 7원칙: 모듈 경계, 계약 우선, 데이터 소유, 검증 5층 (4장으로 흡수, 예제는 가상 예제로 재작성)
- 새로 더한 것: 이해관계자 정의서(사람 + 연관 시스템), 단계별 필수 뷰(의도 뷰·사실 뷰), 테일러링 프로필, 방법론 자체의 개정 루프

결정 기록: [method-adr/0001](method-adr/0001-name-structure-license.md)
