# 7장. 측정

측정하지 않으면 방법론이 효과가 있는지 말할 수 없습니다. v0.1의 측정은 1인이 손으로 기록할 수 있는 수준으로 줄였고, 대부분 git 이력과 훅 로그에서 바로 읽힙니다.

## 측정 시트

위치: `docs/hold/measurement.csv`. 변경(`changes/<id>/`) 하나마다 한 행입니다.

| 열 | 뜻 | 출처 |
| --- | --- | --- |
| `change_id` | 변경 폴더 이름 | 폴더 |
| `profile` | 그 변경에 적용한 프로필 | `hold.toml` |
| `intent_commit` | intent.md 첫 커밋 시각 | `git log --diff-filter=A -- changes/<id>/intent.md` |
| `spec_commit` | spec.md 승인 커밋 시각 | git log |
| `contract_commit` | 계약 게이트 커밋 시각 (없으면 비움) | git log |
| `first_pass_merged` | 재작업 없이 병합됐는가 (y/n) | PR 이력 |
| `check_failures` | 수정 직후 검사가 잡은 건수 | `.hold/logs/hooks.jsonl`의 `post_edit` |
| `protect_blocks` | 에이전트가 보호 경로를 넘으려 한 건수 | `.hold/logs/hooks.jsonl`의 `protect_paths` |
| `human_interventions` | 사람이 직접 고치거나 결정한 횟수 | 수기 |
| `friction_ids` | 연결된 마찰 기록 ID | `docs/hold/friction/` |
| `notes` | 한 줄 메모 | 수기 |

## 지표

| 지표 | 계산 | 무엇을 보나 | 종류 |
| --- | --- | --- | --- |
| intent → spec 시간 | `spec_commit − intent_commit` | 요구와 설계를 한 세션으로 압축했는가 | 선행 |
| 계약 게이트 대기 | `contract_commit − spec_commit` | 사람의 결정이 병목인가 | 선행 |
| 첫 패스 병합률 | `first_pass_merged = y` 비율 | 계획과 계약이 충분히 단단했는가 | 후행 |
| 보호 경로 차단 | `protect_blocks` 합계 | 사람의 선이 실제로 시험받았는가 | 관찰 |
| 검사 실패 | `check_failures` 합계 | 안내(스킬)만으로 충분했는가 | 관찰 |
| 사람 개입 | `human_interventions` 합계 | 사람이 어디에 시간을 썼나 | 관찰 |
| 마찰 밀도 | 마찰 기록 수 / 변경 수 | 방법론 자체의 비용 | 방법론 |

## 해석 규칙

- **보호 경로 차단이 0이면 좋은 것이 아닐 수 있습니다.** 에이전트가 경계를 넘을 일이 없었는지, 우회했는지 확인합니다(Bash 휴리스틱의 한계).
- **검사 실패가 많으면 안내가 약한 것입니다.** 같은 실패가 두 번 나오면 CLAUDE.md "알려진 함정"에 한 줄을 넣습니다.
- **사람 개입은 줄이는 것이 목표가 아닙니다.** 개입이 계약 결정과 리뷰에 모이고 있는지, 단순 수정에 흩어져 있는지를 봅니다.
- **실증 한 번의 숫자로 효과를 주장하지 않습니다.** 근거 등급은 8장의 규칙으로만 올립니다.
