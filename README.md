# HOLD — 사람이 쥐는 AI-Native 개발방법론

**HOLD (Human-Owned Loop Development)** 는 AI가 개발 루프를 돌리되, 사람이 소유한 선은 에이전트가 넘지 못하게 하는 개발방법론입니다.

> AI가 루프를 돌리고, 모든 산출물에는 주인이 있으며, 사람이 소유한 선은 에이전트가 넘지 못한다.

- 판: **v0.1** (2026-11, 실증 전 — 모든 원칙의 근거 등급은 "가설")
- 확장: **web-0.1** (2026-11-12, 선택) — 웹 프런트엔드, Modern Web Guidance 통합 ([9장](method/09-web-frontend.md))
- 기본 프로필: Lite
- 기술 맥락: Python 3.11+, LangChain·LangGraph, PostgreSQL, Claude Code (원칙과 프로세스는 도구 중립). 웹 확장은 Node.js 22+

## 왜 만들었나

바이브코딩이 유행하면서 "딸깍만으로 앱 개발"이라는 마케팅 용어가 난무하고 있습니다. 딸깍은 **기술부채, 의도부채, 인지부채**를 남기고, 이 부채들이 쌓여 소프트웨어 위기를 부릅니다. 세 부채의 공통 원인은 소유의 실종입니다. HOLD는 모든 산출물에 주인을 정하고, 사람이 소유한 선을 기계로 지킵니다.

## 저장소 구성

| 폴더·파일 | 내용 | 라이선스 |
| --- | --- | --- |
| `method/` | 방법론 본문 0~8장, 확장 9장, 부록 (사람용 원본) | CC BY 4.0 |
| `kit/` | `hold-kit`: 템플릿, 훅, 스크립트, 스킬 (에이전트용) | Apache-2.0 |
| `examples/` | 가상 예제 (실제 실증 기록은 두지 않음) | Apache-2.0 (코드), CC BY 4.0 (문서) |
| `method-adr/` | 방법론 자체의 결정 기록 | CC BY 4.0 |
| `friction/` | 실증 중 마찰 기록 양식과 공개용 요약 | CC BY 4.0 |
| `tests/` | 키트 자체의 테스트 | Apache-2.0 |
| `CHANGELOG.md` | 판별 변경 내역 | CC BY 4.0 |

## 읽는 순서

1. [`method/00-charter.md`](method/00-charter.md) — 헌장: 목적, 문제 인식, 범위
2. [`method/01-principles.md`](method/01-principles.md) — 원칙 H1~H10
3. [`method/02-process.md`](method/02-process.md) — 8단계 프로세스와 게이트
4. [`method/06-profiles.md`](method/06-profiles.md) — 내 프로젝트에 맞는 프로필 고르기
5. [`method/05-kit.md`](method/05-kit.md) — 키트 설치와 통제 대응표
6. [`method/09-web-frontend.md`](method/09-web-frontend.md) — 웹 UI가 있다면: Modern Web Guidance 통합 확장

## 빠른 시작 (Lite)

```bash
# 1. 새 프로젝트에 키트 설치 (웹 UI가 있으면 --web 을 붙인다)
python kit/scripts/hold_init.py --target ../my-project --profile lite

# 2. 설치된 것 확인
cd ../my-project
python scripts/check_views.py          # 정의서·intent·spec의 필수 절과 뷰 검사
python scripts/gen_views.py --check    # 계약에서 생성한 사실 뷰가 최신인지 검사
```

설치 후 할 일은 `docs/architecture/stakeholders.md`(이해관계자 정의서)와 `docs/architecture/views/context.md`(시스템 컨텍스트 뷰)를 채우는 것입니다. 이것이 Stage 0입니다.

웹 확장을 켰다면 정의서의 "사용 환경" 칸과 `hold.toml`의 `[web]`(지원 기준)을 정한 뒤, 사람이 `python scripts/hold_web_sync.py`로 Modern Web Guidance 고정 버전을 설치합니다([9.7](method/09-web-frontend.md#97-키트-구성과-설치)).

## 개정 방식

v0.1은 동결 후 실증 기간 동안 바꾸지 않습니다. 실증 중의 불편은 `friction/`에 기록하고, 실증이 끝나면 회고를 거쳐 다음 판을 냅니다. 작업을 막는 결함만 v0.1.x 패치로 고칩니다. 코어가 다루지 않는 기술 영역은 기본으로 꺼진 확장(`web-0.1` 등)으로 더하며, 확장은 코어의 원칙과 규칙을 바꾸지 않습니다. 자세한 규칙은 [`method/08-revision.md`](method/08-revision.md)에 있습니다.

## 라이선스

- 문서(`method/`, `method-adr/`, `friction/`, 각 폴더의 `.md` 문서): [CC BY 4.0](LICENSE-docs)
- 코드(`kit/`, `examples/`의 코드, `tests/`): [Apache-2.0](LICENSE)

## 기반

- Anthropic, [The AI-Native SDLC playbook](https://claude.com/blog/the-ai-native-sdlc-playbook) (2026-08-21) — 흐름
- AI-friendly 모듈러 아키텍처 7원칙 (DeepData 내부 가이드, 5판) — 구조. 공개본에서는 [4장](method/04-architecture.md)으로 흡수
- ISO/IEC/IEEE 42010 (아키텍처 기술의 이해관계자·관심사·관점), C4 모델, UML — 이해관계자와 관점
- Google Chrome, [Modern Web Guidance](https://github.com/GoogleChrome/modern-web-guidance) (1.0.0, Apache-2.0) — 웹 확장의 가이드 내용. HOLD는 가이드를 고정 버전으로 들이고 정책·버전·허용 목록을 사람이 소유하게 하는 연결층만 만듭니다([9장](method/09-web-frontend.md))
