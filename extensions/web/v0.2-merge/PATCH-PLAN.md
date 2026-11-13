# v0.2 편입 변경 계획 (코어 파일별)

v0.2 회고에서 "유지" 판정이 난 뒤, 사람이 `method/`·`kit/`를 고치는 PR에서 아래를 적용합니다. 이 PR(web-0.1)에서는 아무것도 적용하지 않았습니다.

## A. 방법론 본문 (`method/`)

| 파일 | 변경 |
| --- | --- |
| `method/09-web.md` (새 파일) | [method-09-web.md](method-09-web.md) 를 옮기고 회고 판정(유지된 규칙만, 강도, 근거 등급)을 반영 |
| `method/00-charter.md` | 적용 범위에 "웹 프런트엔드 바인딩은 9장" 한 줄 |
| `method/01-principles.md` | 원칙 표는 **그대로**. 근거 등급은 회고 결과로만 올림 |
| `method/02-process.md` | 단계별 표(9.4)와 겹치지 않게 "웹 UI가 있으면 9.4 참조" 한 줄 |
| `method/05-kit.md` | 5.5 통제 대응표에 R14~R18 행 추가(웹 바인딩 설치 시). 훅을 편입하면 5.2에 `web_guard.py` 추가 |
| `method/06-profiles.md` | 9.6 내용을 프로필 표에 반영 |
| `method/07-measurement.md` | 웹 측정 시트 열 정의 추가 |
| `method/08-revision.md` | **확장 규약**을 개정 규칙에 편입할지 판정. 편입하면 "확장은 코어를 고치지 않는다(1~6)"를 절로 추가하고, `extensions/README.md`의 "제안" 표시를 뺌. 실증 계획 표의 2차 행 갱신 |
| `method/appendix-glossary.md` | MWG, 지원 기준(Baseline), 사용 환경, 참조 가이드 용어 |
| `method/appendix-evidence.md` | 제작사 평가(57% → 88%)를 **외부 근거**로 표시 (HOLD 등급 아님) |

## B. 키트 (`kit/`) — 편입 범위는 회고가 정함

| 선택 | 내용 |
| --- | --- |
| 최소 편입 (권장 시작점) | `extensions/web/kit/hold-web/` (sync, mwg, web_check, web_scan, common)와 `templates/`를 `kit/`로 올림. `hold_init.py`에 `--web` 옵션. 훅 제외 |
| 훅 포함 | `web_guard.py`를 코어 훅 체계에 통합. 코어 `protect_paths.py`와 보호 경로 판정 코드를 **한 벌**로 합침(아래 C). 4차 적대적 재공격 필수 |
| 편입 안 함 | `extensions/web/` 그대로 유지. 코어 판과 계속 분리 |

`install.py`의 표식 절 삽입(CLAUDE.md, spec 양식)은 편입 시 `kit/templates/`를 직접 고치는 방식으로 바뀌므로 표식 코드를 제거합니다.

## C. 코어 훅의 알려진 약점 (확장과 별개로 v0.1.x 또는 v0.2에서 수정)

`kit/hooks/protect_paths.py`에 확장 리뷰가 확인한 우회가 같은 방식으로 있습니다. 확장은 자기 경로만 더 엄격히 판정했고 코어는 고치지 않았습니다.

| 약점 | 확인한 방식 | 수정 방향 |
| --- | --- | --- |
| 읽기 전용 git 명령의 쓰기 옵션 | `git show --output=<보호 경로>` | `--output`·`-o`·`--ext-diff` 거부 (확장 `GIT_WRITE_OPTS`) |
| 글롭·중괄호 경로 | `.c?aude/…`, `{a,b}` | 경로 정규화와 글롭 전개 후 판정 (확장 `token_hits`) |
| 대소문자·NTFS 변형 | `.MWGRC`, `file::$DATA`, 끝의 점·공백 | `casefold` 정규화 (확장 `norm`) |
| 셸 해석 | 정규식 기반 | `shlex` 기반 해석기 (확장 `split_commands`) — 단 정적 해석의 한계는 같다 |

(확장의 `common.py`에서 해당 함수를 코어 훅으로 옮기고, 매니페스트를 새 판으로 `--write` 한다.)

## D. 테스트와 매니페스트

1. 확장 테스트(165개)를 `tests/`로 옮기되, `core_manifest` 관련 테스트는 새 판의 매니페스트로 바꾼다.
2. `extensions/core-v0.1.sha256`은 v0.1의 기록으로 남기고, 새 판 매니페스트 `core-v0.2.sha256`을 `core_manifest.py --write`로 만든다. **사람이, ADR과 함께** 한다(확장 규약).
3. 코어 테스트 37개는 통과해야 한다. 변경이 기존 규칙(R01~R13)의 동작을 바꾸면 ADR에 이유를 쓴다.

## E. ADR

`method-adr/0003-web-binding-merge.md` 에 다음을 적습니다: 배경(회고 판정), 선택지(최소 편입 / 훅 포함 / 편입 안 함), 결정, 근거(마찰 기록·측정 ID), 결과, 적대적 리뷰 첨부. 이 PR의 ADR 0002와 리뷰 원문 3개는 이력으로 그대로 둡니다.
