"""R05·R06: 정의서 ID와 필수 뷰 검사 — 빠뜨리면 실패하고, 갖추면 통과하는지."""
from conftest import run_hook, run_script, write

INTENT_OK = """# Intent: 식당 추천
## 이해관계자
- 발안: SH-U01 여행자
## 열린 질문
- 없음
"""

SEQ = """```mermaid
sequenceDiagram
    actor U as 여행자 (SH-U01)
    U->>C: 추천해 줘
    alt 정상
        C-->>U: 후보
    else 실패
        C-->>U: 안내
    end
```"""

SPEC_OK = f"""# Spec: 식당 추천
## 이해관계자 영향
| ID | 방향 | 내용 | 승인 |
|---|---|---|---|
| SH-U01 | 시스템 → 이해관계자 | 추천을 받음 | 아니오 |
## 뷰
누구의 어떤 질문: 엔지니어 — 실패하면?
{SEQ}
"""


def test_설치_직후에는_통과한다(project):
    res = run_script(project, "check_views.py")
    assert res.returncode == 0, res.stdout


def test_정상_변경은_통과한다(project):
    write(project, "changes/20261110-dining/intent.md", INTENT_OK)
    write(project, "changes/20261110-dining/spec.md", SPEC_OK)
    res = run_script(project, "check_views.py")
    assert res.returncode == 0, res.stdout


def test_intent에_이해관계자_절이_없으면_실패한다(project):
    write(project, "changes/20261110-dining/intent.md", "# Intent\n## 문제\n불편하다\n")
    res = run_script(project, "check_views.py")
    assert res.returncode == 1
    assert "'## 이해관계자' 절이 없습니다" in res.stdout


def test_spec에_시퀀스_뷰가_없으면_실패한다(project):
    write(project, "changes/20261110-dining/intent.md", INTENT_OK)
    write(project, "changes/20261110-dining/spec.md", SPEC_OK.replace(SEQ, "(그림은 나중에)"))
    res = run_script(project, "check_views.py")
    assert res.returncode == 1
    assert "sequenceDiagram 블록이 없습니다" in res.stdout


def test_정의서에_없는_ID는_실패한다(project):
    write(project, "changes/20261110-dining/intent.md", INTENT_OK.replace("SH-U01 여행자", "SH-U01 여행자, SH-S09 미지의 API"))
    res = run_script(project, "check_views.py")
    assert res.returncode == 1
    assert "SH-S09 는 이해관계자 정의서에 없는 ID" in res.stdout


def test_standard는_컴포넌트_뷰가_필수이고_생략_사유로_통과한다(project):
    write(project, "changes/20261110-dining/intent.md", INTENT_OK)
    write(project, "changes/20261110-dining/spec.md", SPEC_OK)
    res = run_script(project, "check_views.py", "--profile", "standard")
    assert res.returncode == 1 and "컴포넌트 뷰" in res.stdout
    write(project, "changes/20261110-dining/spec.md", SPEC_OK + "\n### 컴포넌트 뷰\n생략: 모듈 구성 변화 없음\n")
    res = run_script(project, "check_views.py", "--profile", "standard")
    assert res.returncode == 0, res.stdout


def test_plan에_모듈별_작업_범위가_없으면_실패한다(project):
    write(project, "changes/20261110-dining/intent.md", INTENT_OK)
    write(project, "changes/20261110-dining/plan.md", "# Plan\n## 순서\n1. 한다\n")
    res = run_script(project, "check_views.py")
    assert res.returncode == 1 and "모듈별 작업 범위" in res.stdout


def test_수정_직후_훅이_실패를_에이전트에게_돌려준다(project):
    write(project, "changes/20261110-dining/intent.md", INTENT_OK)
    spec = write(project, "changes/20261110-dining/spec.md", SPEC_OK.replace(SEQ, ""))
    res = run_hook(project, "post_edit.py", {"tool_name": "Write", "tool_input": {"file_path": str(spec)}})
    assert res.returncode == 2
    assert "sequenceDiagram" in res.stderr


def test_정의서가_비면_stage0에서_실패한다(project):
    write(project, "docs/architecture/stakeholders.md", "# 이해관계자 정의서\n(아직 없음)\n")
    res = run_script(project, "check_views.py")
    assert res.returncode == 1 and "SH-ID 행이 하나도 없습니다" in res.stdout
