---
name: hold-views
description: HOLD 필수 뷰(C4·UML 다이어그램)를 Mermaid로 그린다. intent.md·spec.md·plan.md·사고 기록을 쓰거나, 시스템 컨텍스트 뷰를 만들거나, 다이어그램을 고칠 때 사용한다.
---
# HOLD 필수 뷰

## 세 가지 규칙
1. **뷰는 이해관계자의 관심사에 답한다.** 모든 다이어그램 바로 위에 `누구의 어떤 질문: <독자> — <질문>`을 한 줄 적는다.
2. **그림은 텍스트로 쓴다.** 마크다운 안의 ```mermaid 블록. 이미지 파일은 만들지 않는다.
3. **의도 뷰는 그리고, 사실 뷰는 생성한다.** 이미 있는 구조(계약 관계, 모듈 의존)는 손으로 그리지 말고 `python scripts/gen_views.py`로 만든다. `docs/architecture/views/generated/`는 손대지 않는다.

## 단계별 필수 뷰 (Lite)
| 산출물 | 뷰 | Mermaid | 필수 |
|---|---|---|---|
| `views/context.md` | 시스템 컨텍스트 (C4 L1) | `flowchart LR` + subgraph(사람, 연관 시스템) | 예 |
| `intent.md` | 업무 흐름 before/after | `flowchart` | 흐름이 바뀔 때 |
| `spec.md` | 핵심 상호작용 | `sequenceDiagram` + `alt` 실패 분기 | **예** |
| `spec.md` | 컴포넌트 변경분 (C4 L2·L3) | `flowchart` 또는 `C4Component` | Standard 이상 |
| `spec.md` | 상태 전이 | `stateDiagram-v2` | 상태가 있을 때 |
| 계약 게이트 | 계약 클래스 | 생성 (`gen_views.py`) | 예 |
| 사고 기록 | 사고 재구성 | `sequenceDiagram` (cid 로그 기준) | 예 |

필수가 아닌 뷰를 넣지 않을 때는 그 자리에 `생략: 이유`를 한 줄 적는다.

## 시퀀스 뷰 작성법
- 참여자 이름에 정의서 ID를 붙인다: `actor U as 여행자 (SH-U01)`, `participant M as 지도 API (SH-S02)`
- **실패 경로를 반드시 `alt … else` 로 그린다.** 연관 시스템이 응답하지 않을 때 사용자가 무엇을 보는지가 이 그림의 핵심이다.
- 각 흐름을 고정하는 통합 테스트 이름을 `Note over`로 적는다.

## 컨텍스트 뷰 작성법
- 정의서의 행 하나 = 상자 하나. 정의서를 고치면 그림도 함께 고친다.
- 가운데 시스템, 왼쪽 사람(subgraph 사람), 오른쪽 연관 시스템(subgraph 연관 시스템).
- 선에는 무엇을 주고받는지 짧게 적는다.

## 다 그리면
`python scripts/check_views.py`를 돌리고 출력을 보고한다. mermaid-cli(`mmdc`)가 있으면 렌더링까지 검사한다.
