# 방법론 ADR 0002 첨부: 적대적 리뷰 원문 (3차)

- 대상: 커밋 97ef8e1 (`feat/web-ext-mwg`, 2차 재설계판)
- 검토자: 1·2차와 같은 검토자 (작성에 관여하지 않음). 임시 복사본(`/tmp/advr3/`)에서 실제 공격을 실행
- 날짜: 2026-11-13
- 처리 결과: [ADR 0002](0002-web-extension-mwg.md)의 "3차 리뷰와 처리" 표

아래는 검토자의 보고서 원문입니다. 가리키는 코드는 97ef8e1 기준이며, 이후 수정으로 바뀌었습니다.

---

# HOLD web-0.1 확장 3차 적대적 검토 (97ef8e1, `feat/web-ext-mwg`)

검토 중 `/home/claude/hold-method`는 수정하지 않았고, 작업은 `/tmp/advr3/`에서만 했습니다. 아래 "미수행"에 적은 항목은 시간 안에 끝내지 못했습니다.

## 1. 총평

**병합 보류 (조건부)** 를 권합니다. 위협 모델이 "실수하는 협조적 에이전트"인데도, 에이전트가 정상적인 방법으로 가드를 그대로 통과하는 경로가 확인됐습니다.

- `mwg.py --limit install search`로 래퍼가 `install`을 실행합니다. 이는 "래퍼가 유일한 경로이고 하위명령 화이트리스트를 강제한다"는 핵심 설계 주장을 깨는 결함입니다.
- 가장 흔한 단축형인 `git commit -nm`이 pre-commit 차단을 통과하고, 실제로 커밋 훅을 건너뜁니다. 위협 모델이 "마지막 방어선"으로 지정한 층을 우회하는 경로입니다.
- 한 줄 수정(VALUE_OPTIONS를 node와 동일하게)과 정규식 보강으로 대부분 막을 수 있어 재설계는 필요 없습니다. 아래 높음 3건을 고치면 병합 가능으로 판단합니다.

## 2. 발견 목록

### 높음

**ADV3-01 래퍼 `VALUE_OPTIONS` 불일치로 `install`/`update` 실행 (재현됨)**
- 분류: 가드 우회, 설계 주장 위반.
- 대상: `common.py`의 `VALUE_OPTIONS`와 `first_positional()`, `mwg.py`의 하위명령 검사.
- 문제: 래퍼는 `--limit`, `--agent`, `--format`, `--category`를 값을 받는 옵션으로 간주해 뒤따르는 토큰을 건너뜁니다. 반면 node `util.parseArgs`는 `strict:false`에서 `--skill-version`만 값 옵션으로 선언합니다. 그래서 래퍼는 `search`를 첫 위치 인자로 보고 통과시키지만, MWG는 `install`을 실행합니다.
- 재현: `python3 .claude/hold-web/mwg.py --limit install search`, `--limit update search`
- 관찰: 두 명령 모두 MWG `install`/`update`가 실제로 실행되어 핀 고정된 스킬이 고정되지 않은 `@latest` 스킬로 교체됐습니다. `web_check`는 사후에야 탐지합니다.
- 고치는 법: 래퍼의 값 옵션 집합을 `{"--skill-version"}` 하나로 맞춥니다. 더 안전하게는 허용 하위명령이 첫 번째 인자 위치에 정확히 있을 것을 요구합니다. 알 수 없는 `-` 옵션이 하위명령보다 앞에 오면 거부합니다.

**ADV3-02 `git commit -nm`/`-anm` 등 단축 옵션이 `--no-verify` 차단을 통과하고 훅을 실제로 건너뜀 (재현됨)**
- 분류: 가드 우회. 커밋 검사가 "마지막 방어선"인 구조이므로 높음.
- 재현 (훅 판정): `git commit -nm wip`, `git commit -anm wip`는 통과. `git commit --no-verify`, `git push --no-verify`는 차단.
- 재현 (실제 git): exit 1을 내는 pre-commit 훅이 있을 때 일반 커밋은 막히지만 `git commit -nqm x`는 훅 없이 커밋됨.
- 같은 방식: `--no-verif`(접두 약어)가 우회 후보. 훅 통과만 확인했고 실제 git 동작은 확인하지 않음.
- 고치는 법: `commit`/`merge`/`push`에서 `-[a-zA-Z]*n[a-zA-Z]*` 결합 단축 옵션과 `--no-verify` 접두 약어를 모두 차단.

**ADV3-03 `GIT_CONFIG_COUNT`/`KEY_n`/`VALUE_n` 환경변수와 `.git/hooks/pre-commit` 직접 수정으로 pre-commit 무력화 (재현됨)**
- 분류: 가드 우회. 높음/중간 경계(협조적 에이전트가 하기 쉬운 실수는 아니어서 중간에 가까움). 훅 검사 층이 비어 있다는 점에서 높음.
- 재현 (훅 판정): 다음이 모두 통과. `GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.hooksPath GIT_CONFIG_VALUE_0=/dev/null git commit -m x`, `echo 'exit 0' > .git/hooks/pre-commit`, `chmod -x .git/hooks/pre-commit`, `rm .git/hooks/pre-commit`, `pre-commit uninstall`. `.git/hooks/pre-commit`·`.git/config` Write도 통과.
- 재현 (실제 git): 훅이 exit 1인 상태에서 환경변수 방식, 훅 파일 덮어쓰기 방식 모두 커밋 성공.
- 참고: `git config core.hooks''Path`, `git config --local core.hooksPath`는 차단됨.
- 고치는 법: `.git/hooks/`, `.git/config`, `.pre-commit-config.yaml`을 보호 경로에 추가. Bash에서 `GIT_CONFIG_*`, `GIT_DIR`, `pre-commit uninstall`, `SKIP=`, `.git/hooks` 대상 `chmod`/`rm` 차단. CI에서는 서버 쪽 검사가 최종 방어선임을 문서에 명시.

### 중간

**ADV3-04 `git clean -fdx`가 증거를 삭제하고 훅이 통과시킴 (재현됨)**
- 재현: `git clean -fdx`는 훅을 통과해 `.hold/`를 삭제. `git reset`, `git checkout .`, `git restore .`도 보호 토큰이 명령줄에 없으면 통과.
- 영향: `.hold/web-pkg/`(검증된 사본)와 `.hold/logs/web_snap.json`이 사라지면 다음 훅은 스냅샷 없음으로 간주하고 "기준선만 기록"하므로 변경 탐지가 처음부터 다시 시작됨.
- 고치는 법: `git clean`, `git reset --hard`, `git checkout -- .`, `git restore .`, `git stash -u`를 차단하거나 사람 확인 대상으로. 스냅샷 부재 시 기준선 기록 대신 실패를 내는 방식도 가능.

**ADV3-05 위반이 한 번만 보고되고 이후 사라짐, 첫 훅 기준선은 미검사 (재현됨)**
- 재현: 위반이 있는 변경을 한 번 보고하면 스냅샷이 덮어써져, 다음 훅에서 같은 파일이 변경 목록에 나타나지 않아 보고되지 않음. 스냅샷이 없을 때 첫 호출은 기준선만 저장하고 그 시점의 모든 파일을 검사하지 않음.
- 영향: 에이전트가 한 번 경고를 무시하고 넘어가면 위반이 사라짐. 마지막 층은 `web_check`/pre-commit이므로 "지속 스냅샷이 훅 사이의 변경을 잡는다"는 서술은 "첫 보고 1회"로 정정해야 함.
- 고치는 법: 위반이 해결되기 전까지 스냅샷에서 해당 파일의 해시를 갱신하지 않음. 또는 위반 목록을 누적해 `web_check`가 읽도록 함.

**ADV3-06 `mwg_direct_calls()` 직접 호출 우회 다수 (재현됨, 훅 판정 기준)**
- 재현 (모두 통과): 문자열 조립(변수 `$X`, `$(echo npx)`), 글롭(`/usr/bin/np?`), 중괄호(`{npx,}`), `echo ... | sh`, `source <(…)`.
- 영향: 셸 해석기가 fail-closed라고 설명되지만, 동적 문자열이 들어간 명령은 정적으로 해석할 수 없어 통과함. 의도적 우회는 범위 밖이라는 모델에는 맞지만 "fail-closed" 표현은 맞지 않음.
- 고치는 법: 동적 확장(`$`, 백틱, `<(`, 글롭, 중괄호)이 명령 위치에 있으면 거부. 파이프 오른쪽이 `sh`/`bash`/`python -c`이면 거부.

### 낮음

**ADV3-07 보호 경로 목록에 `.npmrc`, `package.json`, `.gitignore`, `CLAUDE.md`, `.hold/web_snap2.json` 없음 (재현됨)**
- 재현: 모두 Write 통과.
- 영향: `.gitignore` 변경은 `legacy-scan` 대상 범위에 영향 가능. `.npmrc`/`package.json`은 npm 설정과 스크립트 경로에 영향하나 직접 `npx/npm/node`가 차단되어 제한적.
- 고치는 법: `.gitignore`는 `web_check`가 `legacy-scan` 입력 집합과 비교. `.npmrc`는 보호 경로에 추가.

## 3. 견고했던 것

- 보호 경로 쓰기 판정: `.mwgrc` 대소문자 변형, `::$DATA`, 끝의 점과 공백, Windows 드라이브 경로, `.hold/web-pkg/*`, `.hold/logs/web_snap.json`, `.pre-commit-config.yaml`, `.mwgrc` 심볼릭 링크가 모두 차단됨.
- git 쓰기 옵션 차단: `--no-verify`, `git -c core.hooksPath=...`, `git push --no-verify`, 따옴표로 쪼갠 `core.hooks''Path` 차단.
- 2차 수정 유지: 글롭/python/perl/cp/sed/dd/tee 경로 쓰기, 중립 이름 임시 사본 scan 범위, `touch -r` 탐지.
- 비UTF-8 파일명은 `ensure_ascii=True`와 fail-closed 훅으로 해결됨.
- `core_manifest.py --check` 58개 파일 OK, 코어 파일 미수정.

## 4. 과장·틀린 문서 주장

1. **"래퍼 `mwg.py`가 유일한 경로이며 하위명령 화이트리스트를 강제"**: ADV3-01로 `install`/`update`가 실행되므로 틀림.
2. **"직접 npx/npm/node 차단, 셸 해석기 fail-closed"**: 동적 문자열·글롭·`| sh` 등은 통과(ADV3-06). "정적으로 해석 가능한 호출만 차단"으로 정정 필요.
3. **"git 쓰기 옵션·`--no-verify`·`core.hooksPath` 차단"**: `-nm`, `GIT_CONFIG_*`, `.git/hooks` 직접 수정은 통과(ADV3-02, 03).
4. **"지속 내용 해시 스냅샷으로 훅 사이의 변경을 포착"**: 위반이 1회만 보고되고, `git clean`으로 스냅샷이 삭제되면 기준선부터 다시 시작(ADV3-04, 05).
5. **"강제 0 / 부분 4 / 안내만 1" 표기**: R14~R17을 "부분"으로 표시한 것은 위 우회를 감안하면 오히려 낙관적. 최소한 R14·R15에 "협조적 에이전트 전제, 알려진 우회 있음" 한계 문구를 덧붙여야 정확.
6. **위협 모델 범위**: "의도적 우회는 커밋 검사·CI가 마지막 방어선"이라는 서술은, 커밋 검사 자체가 `-nm`과 훅 파일 수정으로 무력화되므로(ADV3-02, 03) CI(서버 쪽)가 유일한 실질 방어선이라고 명시해야 함.

## 5. 2차(ADV2-01~13) 해결 현황

이 세션 요약만으로는 ADV2 항목 번호별 설명을 모두 복원하지 못했습니다. 이번 라운드에서 실제로 확인한 것만 적습니다.

| 항목 | 상태 | 근거 |
|---|---|---|
| ADV2-06 (비UTF-8 파일명) | 해결됨 | `ensure_ascii=True`와 fail-closed 훅 확인 |
| git 쓰기 옵션 계열 | 부분 해결 | `--no-verify`는 막힘, `-nm`은 통과(ADV3-02) |
| 글롭/python/perl/cp/sed/dd/tee 경로 쓰기 | 해결됨 | 재확인 |
| 중립 이름 scan 범위, `touch -r` | 해결됨 | 재확인 |
| 직접 호출 우회 계열 | 부분 해결 | 문자열 조립·`\| sh` 등 통과(ADV3-06) |
| ADV2-01, 02, 03, 04, 05, 07, 08, 09, 10, 11, 12, 13 | 미확인 | 이번 라운드에서 번호별로 재검증하지 못함 |

## 미수행

- 래퍼의 `SAVED_TO` 증거 위조 가능성.
- `CLAUDE_PROJECT_DIR`/`--root` 리다이렉션.
- MANIFEST/`web_check` 자기 검증 약점.
- 스냅샷 병렬 훅 경합.
- R16 폴더명과 `since` 회피.
- `legacy_allow` 글롭.
- `disabled_reason` 트립와이어.
- 위 항목은 결과가 없으며, "견고했다"로 읽지 마시기 바랍니다.
