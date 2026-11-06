# 시스템 컨텍스트 뷰 (의도 뷰, C4 Level 1)

누구의 어떤 질문: 모든 이해관계자 — 이 시스템은 누구·무엇과 맞닿는가?

상자 하나가 [이해관계자 정의서](../stakeholders.md)의 행 하나입니다. 정의서를 고치면 이 그림도 함께 고칩니다.

```mermaid
flowchart LR
    subgraph 사람
        U01["SH-U01 여행자"]
    end
    SYS(["<시스템 이름>"])
    subgraph 연관시스템["연관 시스템"]
        S01["SH-S01 LLM 제공자 API"]
    end
    U01 -- "질문·피드백" --> SYS
    SYS -- "추론 요청" --> S01
```
