# CHANGELOG

판 번호 규칙: `v0.N`은 실증 회고를 거친 개정판, `v0.N.x`는 작업을 막는 결함만 고친 패치, `<이름>-0.N`은 기본으로 꺼진 확장의 판입니다. 자세한 규칙은 [method/08-revision.md](method/08-revision.md).

## 확장 web-0.1 — 2026-11-12 (코어 v0.1 동결 유지)

웹 프런트엔드 확장. Chrome 팀의 Modern Web Guidance(MWG) 1.0.0을 HOLD의 선 안으로 들입니다. 기본으로 꺼져 있고, 켜지 않으면 코어 키트의 동작은 같습니다(코어 테스트 37개 그대로 통과).

### 방법론

- 9장 신설: 필요성(에이전트의 오래된 프런트엔드 패턴, v0.1 키트의 프런트엔드 공백), MWG 개요와 직접 확인한 특성, 그대로 들일 때의 충돌 8가지, 원칙·단계별 통합, 설정, 키트, 통제 대응표 R14~R18, 프로필, 측정, 한계
- 8장: 확장의 정의와 다섯 조건, 동결과의 관계, `<이름>-0.N` 판 번호
- 0·5·6장, README: 9장으로 가는 안내만 추가 (코어 내용은 바꾸지 않음)
- 부록 A·B: 용어 9개, 외부 근거 1행과 한계 1항

### 키트

- 새 스크립트: `hold_web_sync.py` (고정 버전 설치·`--check`, 에이전트 셸에서 실행 거부), `web_scan.py` (`legacy-scan` 래퍼: 고정 버전, 판정, 허용 목록)
- `hold.toml`: `[web]` 섹션, `paths.web_guides`, 보호 경로에 `docs/hold/web/`
- `post_edit.py`: 프런트엔드 파일 레거시 검사(R15), MWG `search`·`retrieve` 실행 기록(H9). 기록은 `web_scan`, `web_guidance`로 코어 `post_edit` 실패와 분리
- `protect_paths.py`: 비고정 MWG 호출과 `install`·`update`·`set-allow-*` 차단(R17). 기본 보호 경로에 `docs/hold/web/`
- `check_views.py`: 정의서 "사용 환경" 칸, 가이드 목록, spec·plan의 `## 참조 가이드` 대조(R14·R16)
- `hold_init.py --web`: 확장 켜기, 측정 시트 열 6개 추가
- 양식: 정의서에 "사용 환경" 칸, spec에 `## 참조 가이드` 절과 `(웹)` 계약 질문, CLAUDE.md에 웹 절, pre-commit에 웹 검사 2개
- `settings.json`: PostToolUse 매처에 `Bash` 추가 (확장이 꺼져 있으면 아무것도 하지 않음)
- 테스트 41개 추가 (`tests/test_web.py`), 전체 78개

결정 기록: [method-adr/0002](method-adr/0002-web-extension-mwg.md)

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
