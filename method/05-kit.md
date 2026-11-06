# 5장. 실천 키트 (hold-kit)

키트는 방법론을 "읽고 따르는" 문서가 아니라 "설치하면 강제되는" 파일 묶음으로 만든 것입니다(H7). 원칙과 프로세스는 도구 중립이고, 키트는 Claude Code와 Python 프로젝트에 묶인 바인딩 층입니다.

## 5.1 설치

```bash
python kit/scripts/hold_init.py --target ../my-project --profile lite
```

- 이미 있는 파일은 덮어쓰지 않습니다(`--force`로 덮어쓰기). 사람이 고친 CLAUDE.md는 재설치해도 남습니다.
- `.claude/settings.json`이 이미 있으면 `.claude/settings.hold.json`으로 따로 쓰고, 합치는 방법을 안내합니다.
- `.gitignore`에 `.env`, `.venv/`, `.hold/logs/` 등을 더합니다.
- 선택: `pip install pre-commit && pre-commit install`로 커밋 전 검사를 켭니다.

설치 후 프로젝트에 생기는 것:

| 위치 | 원본 | 역할 |
| --- | --- | --- |
| `hold.toml` | `templates/hold.toml` | 프로필, 경로, 보호 경로 목록 (사람 소유) |
| `CLAUDE.md` | `templates/CLAUDE.md` | 에이전트용 전역 규칙 |
| `.claude/settings.json` | `settings/settings.json` | 훅 등록, `.env` 읽기 차단 |
| `.claude/hooks/protect_paths.py` | `hooks/` | 보호 경로 차단 (PreToolUse) |
| `.claude/hooks/post_edit.py` | `hooks/` | 수정 직후 검사 (PostToolUse) |
| `.claude/skills/hold-intent/` 등 3개 | `skills/` | 안내 층 |
| `scripts/check_views.py` | `scripts/` | 산출물·필수 뷰 검사 |
| `scripts/gen_views.py` | `scripts/` | 사실 뷰(계약 클래스) 생성·드리프트 검사 |
| `docs/architecture/stakeholders.md` | `templates/` | 이해관계자 정의서 (사람 소유) |
| `docs/architecture/views/context.md` | `templates/` | 시스템 컨텍스트 뷰 |
| `docs/architecture/module-map.md` | `templates/` | 모듈 지도 |
| `changes/_template/{intent,spec,plan}.md` | `templates/change/` | 변경 단위 양식 |
| `docs/hold/templates/module-CLAUDE.md` | `templates/` | 모듈별 CLAUDE.md 양식 |
| `docs/hold/friction/_template.md` | `templates/` | 마찰 기록 양식 |
| `docs/hold/measurement.csv` | `templates/` | 측정 시트 |
| `.importlinter` | `templates/importlinter.example` | 모듈 경계 규칙 견본 (모듈 이름을 고쳐 씀) |
| `.pre-commit-config.yaml` | `templates/` | 커밋 전 검사 |

## 5.2 훅이 하는 일

**`protect_paths.py` (PreToolUse, 수정 시도 순간)**
- 파일 도구(Edit, Write, MultiEdit, NotebookEdit)의 대상이 `hold.toml`의 `[protect].paths`에 들면 종료 코드 2로 막고, "멈추고 이유와 선택지를 보고하라"는 메시지를 에이전트에게 돌려줍니다.
- Bash는 휴리스틱으로 검사합니다. 보호 경로로 향하는 리다이렉션(`>`), `tee`, `sed -i`, `rm`, `mv`, `cp`, `git checkout --` 등을 막습니다. `pytest tests/contracts 2>&1`처럼 읽기만 하는 명령은 통과합니다. 우회 방법이 남아 있는 것은 v0.1의 알려진 한계입니다.
- 차단은 `.hold/logs/hooks.jsonl`에 남아 측정 시트의 "보호 경로 차단" 칸이 됩니다.

**`post_edit.py` (PostToolUse, 수정 직후)**
- `changes/**/*.md`, 정의서, 컨텍스트 뷰를 고치면 `check_views.py`를 그 변경에 대해 돌립니다.
- `*.py`를 고치면 `lint-imports`(`.importlinter`가 있을 때)와 `pyright <파일>`(설치되어 있을 때)를 돌립니다.
- 실패하면 결과를 에이전트에게 돌려줘(종료 코드 2), 에이전트가 바로 고치게 합니다. 검사 도구가 없으면 건너뜁니다.

## 5.3 스크립트

**`check_views.py`** — 프로필에 따라 검사합니다.
- Stage 0: 정의서에 SH-ID 행이 있고, 컨텍스트 뷰에 Mermaid 블록이 있다.
- intent.md: `## 이해관계자` 절에 정의서 ID가 있다.
- spec.md: `## 이해관계자 영향` 절(ID 포함)과 `## 뷰` 절이 있고, `## 뷰`에 `sequenceDiagram`이 있다. Standard 이상은 컴포넌트 뷰도 필수이며, 변화가 없으면 `생략: 이유`로 통과합니다.
- plan.md: `## 모듈별 작업 범위` 절이 있다.
- 산출물에 적힌 SH-ID가 모두 정의서에 있다.
- `mmdc`(mermaid-cli)가 설치되어 있으면 모든 Mermaid 블록의 렌더링까지 검사합니다. 없으면 경고만 냅니다.

**`gen_views.py`** — `app/contracts/`의 Pydantic 모델과 Enum을 읽어 Mermaid classDiagram을 `docs/architecture/views/generated/contracts.md`에 씁니다. `--check`는 커밋된 뷰가 코드와 같은지 확인하고, 다르면 실패합니다. 계약 게이트에서 사람이 승인하는 자료가 이 그림입니다.

**`hold_init.py`** — 5.1의 설치 스크립트입니다.

## 5.4 스킬 (안내 층)

| 스킬 | 언제 | 하는 일 |
| --- | --- | --- |
| `hold-intent` | 새 아이디어·요청 | 인터뷰로 intent.md 초안. 함께 쓰는 사람과 외부 시스템까지 묻고, 모르는 것은 열린 질문으로 |
| `hold-architecture` | spec 작성, 모듈·계약 설계 | 모듈 분할 네 질문, 계약 4층, "정하지 말고 질문으로", 데이터 소유, 분리 판단 |
| `hold-views` | 다이어그램 작성 | 단계별 필수 뷰, "누구의 어떤 질문" 한 줄, 시퀀스의 실패 분기 |

## 5.5 통제 대응표 (Lite)

필수 규칙마다 그것을 지키게 하는 장치를 지정했습니다. v0.1의 규칙 13개 중 **8개는 기계가 강제**하고, 2개는 부분 강제, 3개는 아직 안내에 머뭅니다. 안내만인 규칙은 실증에서 가장 먼저 깨질 후보이므로 마찰 기록에서 특히 지켜봅니다.

| R | 규칙 | 원칙 | 안내 | 통제 장치 | 시점 | v0.1 |
| --- | --- | --- | --- | --- | --- | --- |
| R01 | 보호 경로는 사람만 수정 | H1 | CLAUDE.md | `protect_paths.py` | 수정 시도 순간 | 강제 (Bash는 휴리스틱) |
| R02 | 모듈은 공개 창구로만, 모듈끼리 독립 | H6 | `hold-architecture` | `post_edit.py` → `lint-imports`, pre-commit | 수정 직후, 커밋 | 강제 (도구 설치 시) |
| R03 | 계약의 형태·범위를 지킨다 | H5 | 모듈 CLAUDE.md | `post_edit.py` → `pyright`, Pydantic 검증 | 수정 직후, 실행 중 | 강제 (도구 설치 시) |
| R04 | 계약의 의미를 지킨다 | H5 | 계약 질문 목록 | 계약 테스트 (보호), pre-commit | 커밋 | 강제 |
| R05 | 산출물은 이해관계자를 정의서 ID로 적는다 | H3 | 양식, `hold-intent` | `check_views.py` (훅, pre-commit) | 수정 직후, 커밋 | 강제 |
| R06 | spec에 영향 표와 필수 뷰가 있다 | H3·H8 | `hold-views` | `check_views.py` (훅, pre-commit) | 수정 직후, 커밋 | 강제 |
| R07 | 비밀 파일은 읽지 않는다 | — | — | `permissions.deny` | 읽기 시도 순간 | 강제 |
| R08 | 사실 뷰가 코드와 같다 | H8 | `hold-views` | `gen_views.py --check` (pre-commit) | 커밋 | 강제 |
| R09 | 완료 보고에 도구 출력을 붙인다 | H9 | CLAUDE.md 검증 절 | 검사 명령의 종료 코드 (출력 첨부 여부는 미검사) | 완료 보고 시 | 부분 |
| R10 | 계약 질문은 사람이 답한다 | H1·H5 | `hold-architecture` | 보호 경로가 간접 강제 | 계약 게이트 | 부분 |
| R11 | 구현이 계획에서 벗어나면 plan.md를 같은 커밋에서 고친다 | H4 | CLAUDE.md | — | — | 안내만 |
| R12 | 고치기 전에 재현 테스트를 먼저 쓴다 | H9 | CLAUDE.md | — | — | 안내만 |
| R13 | 마찰은 그날 기록한다 | H10 | 마찰 양식 | — | — | 안내만 |

## 5.6 키트의 검증

키트 자체는 `tests/`의 37개 테스트로 검증합니다. 일부러 넣은 위반이 걸리는지와 정상 작업이 통과하는지를 둘 다 확인합니다.

```bash
cd tests && python -m pytest -q
```

- 보호 경로 8종 수정 시도 → 차단, 절대 경로·Windows 경로 → 차단
- 셸로 보호 경로 수정 5종 → 차단, 읽기 전용 셸 4종 → 허용
- 이해관계자 절 누락, 시퀀스 뷰 누락, 정의서에 없는 ID, 모듈별 작업 범위 누락, 빈 정의서 → 실패
- Standard의 컴포넌트 뷰 누락 → 실패, `생략: 이유` → 통과
- 계약을 바꾸고 사실 뷰를 다시 만들지 않으면 → 실패
- 재설치 시 사람이 고친 파일은 보존
- 가상 예제(`examples/`)가 산출물 검사, 사실 뷰 검사, 골든 테스트를 모두 통과
