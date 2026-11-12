# CHANGELOG

판 번호 규칙: `v0.N`은 실증 회고를 거친 개정판, `v0.N.x`는 작업을 막는 결함만 고친 패치입니다. 자세한 규칙은 [method/08-revision.md](method/08-revision.md). `extensions/`의 실험 확장은 코어 판과 따로 `<이름>-0.N`으로 적습니다(제안, [extensions/README.md](extensions/README.md)).

## 실험 확장 web-0.1 — 2026-11-12 (코어 v0.1 무수정)

웹 프런트엔드 확장. Google Chrome의 Modern Web Guidance 1.0.0을 고정 버전으로 들이고, 정책·버전·허용 목록을 사람이 소유하게 합니다. 문서 [extensions/web/README.md](extensions/web/README.md), 결정 기록 [method-adr/0002](method-adr/0002-web-extension-mwg.md).

- 초판은 코어 파일을 고쳤다가 적대적 리뷰(16건, 병합 보류)를 받고 코어 무수정으로 다시 설계했습니다. 재설계판도 2차 리뷰(13건, 병합 보류)를 받아 검증된 사본 + 래퍼 방식으로 한 번 더 보강했습니다. 리뷰 원문과 처리 결과는 ADR 0002에 있습니다.
- 확장 규약(제안): 코어 무수정, 별도 훅 등록, 발행 전 적대적 리뷰, 실증과 측정 분리. 코어 동결 매니페스트(`extensions/core-v0.1.sha256`)로 무수정을 검사합니다.
- 장치: `web_guard.py`(실행 전후 훅), `mwg.py`(MWG 실행 래퍼), `sync.py`(무결성 검증 고정 설치, 검증된 사본·`.mwgrc` 생성), `web_check.py`(설치·고정·사용 환경·참조 가이드 검사, 측정 집계), `web_scan.py`(레거시 검사), `install.py`(새 프로젝트·실증 중 프로젝트 공통).
- 확장 규칙 R14~R18: 강제 0, 부분 4, 안내만 1. 위협 모델은 "실수하는 협조적 에이전트"이고, 의도적 우회는 커밋 검사·CI가 마지막 방어선입니다.
- 공개: 일부 우회(git `--output`, 글롭, 대소문자)는 코어 v0.1의 `protect_paths.py`에도 있습니다. 코어는 동결이라 고치지 않았고 v0.1.x 또는 v0.2 안건입니다.
- 테스트 129개(매개변수 포함). 코어 테스트 37개와 코어 파일은 그대로입니다.

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
