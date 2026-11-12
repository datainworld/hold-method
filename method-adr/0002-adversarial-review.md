# 방법론 ADR 0002 첨부: 적대적 리뷰 원문 (1차)

- 대상: PR #1 첫 커밋 (`feat(web-0.1)`, 코어 파일을 고친 초판)
- 검토자: 작성에 관여하지 않은 별도 에이전트. 저장소만 보고, 임시 복사본에서 실제 공격을 실행
- 날짜: 2026-11-12
- 처리 결과: [ADR 0002](0002-web-extension-mwg.md)의 "적대적 리뷰와 처리" 표

아래는 검토자가 낸 보고서를 고치지 않고 옮긴 것입니다. 이 보고서가 가리키는 코드(파일·줄 번호)는 초판 기준이며, 재설계 후 대부분 사라졌습니다.

---

## 1. 한 줄 총평

**병합을 막겠습니다.** 이 확장이 지키겠다는 선(지원 기준, 버전 고정, 참조 가이드 증거)을 에이전트가 평범한 명령 한두 개로 넘을 수 있습니다. 핵심 경로는 둘입니다. MWG 자체 정책 파일 `.mwgrc`가 보호되지 않고, 에이전트가 직접 실행한 `hold_web_sync.py`가 보호 파일을 원하는 내용으로 다시 써도 `--check`가 통과합니다. 게다가 1차 실증 프로젝트처럼 이미 v0.1로 설치된 프로젝트에서는 확장을 켜도 장치가 하나도 동작하지 않는데 검사는 OK가 나옵니다. 문서의 "강제" 표기와 "코어를 바꾸지 않는다"는 주장도 코드와 맞지 않습니다.

## 2. 발견 목록 (심각도 순)

### ADV-01 · 치명 · A/C/E · MWG 자체 정책 파일 `.mwgrc`로 R14 지원 기준을 뒤집고 실험 기능 잠금을 풉니다 — 재현됨
- **대상:** `kit/hooks/protect_paths.py:53` (`MWG_HUMAN_ONLY`), `kit/templates/hold.toml` 보호 경로, `hold_web_sync.py` 전체(`.mwgrc`를 다루지 않음)
- **무엇이 깨지나:**
  - MWG 1.0.0 CLI는 프로젝트 루트의 `.mwgrc`(`baseline`, `allowOriginTrials`, `allowVolatileFeatures`)를 읽습니다. `retrieve` 결과 앞에는 그 기준에 맞춘 지시가 붙습니다.
  - 숨은 하위 명령 `set-baseline`이 이 파일을 씁니다. 이 명령은 도움말에 없고 `MWG_HUMAN_ONLY`에도 없습니다.
  - `.mwgrc`는 보호 경로가 아니어서 Write 도구로도 바로 쓸 수 있습니다.
  - 결과적으로 `hold.toml`(보호)의 `baseline = "widely"`와 상관없이, 에이전트가 받는 가이드 본문이 "대체 코드·폴리필을 넣지 말라"로 바뀝니다. MWG가 "에이전트가 직접 하지 말라"고 막아 둔 Origin Trial·volatile 잠금도 풀립니다.
  - `hold_web_sync.py`가 `hold.toml`의 baseline을 `.mwgrc`에 옮겨 적지 않습니다. 그래서 `baseline = "2024"` 같은 정책도 실제 `retrieve` 출력에는 반영되지 않습니다. 정책 원본이 둘이고, 실제 도구 출력을 정하는 쪽은 보호되지 않은 쪽입니다.
- **재현:**
  - `protect_paths.py`에 `DISABLE_TELEMETRY=1 npx -y modern-web-guidance@1.0.0 set-baseline limited`를 넣으면 exit 0(허용)입니다. 실행하면 `.mwgrc`에 `{"baseline":"limited"}`가 생깁니다.
  - 이후 `retrieve dialog` 출력 첫머리에 다음 문구가 붙습니다: "**Project Baseline Target (`.mwgrc`):** `limited` … **Skip the `## Fallback strategies` section** — **do not** add compatibility fallbacks…"
  - Write 훅에 `/tmp/advr/proj/.mwgrc`를 넣으면 exit 0입니다. `{"allowVolatileFeatures": true, …}`를 쓰면 `retrieve language-detection`이 CAUTION 잠금 대신 가이드 본문을 돌려줍니다.
- **고치는 법:**
  - `hold_web_sync.py`가 `hold.toml [web]`에서 `.mwgrc`를 생성하도록 합니다.
  - `.mwgrc`를 보호 경로에 넣고 `--check`에서 내용이 같은지 대조합니다.
  - `set-baseline`과 알 수 없는 하위 명령은 모두 차단합니다(search·retrieve·list·legacy-scan만 허용하는 화이트리스트).

### ADV-02 · 치명 · A · 에이전트가 `hold_web_sync.py`를 직접 실행해 보호 파일을 원하는 내용으로 바꾸고, `--check`·`check_views`가 그대로 통과합니다 — 재현됨
- **대상:** `hold_web_sync.py:279` (`if os.environ.get("CLAUDECODE")`), `:191-226` (무결성 검증 없음), `:197-199` (package.json이 없으면 버전 대조를 건너뜀)
- **무엇이 깨지나:**
  - `CLAUDECODE=` 접두어로 빈 문자열을 주면 셸 거부가 풀립니다. 이 명령에는 보호 경로 문자열도 쓰기 단어도 없어서 `protect_paths`가 막지 않습니다.
  - `--tarball`은 아무 tgz나 받습니다. `version: "1.0.0"`만 맞추면 SKILL.md와 guides.json의 내용을 마음대로 정할 수 있습니다.
  - 결과로 보호 경로인 `.claude/skills/modern-web-guidance/SKILL.md`와 `docs/hold/web/guides.json`이 에이전트가 정한 내용으로 바뀝니다. 지어낸 ID가 R16을 통과하고 `--check`도 OK입니다.
  - 9.11은 이 거부가 "휴리스틱"이라고만 밝혔습니다. 실제 결과는 보호 경로 전체 우회이고 검사로도 드러나지 않으므로, 공개된 것보다 심각합니다.
- **재현:**
  - 조작 tarball `/tmp/advr/evil.tgz`를 만들었습니다. 지어낸 ID `dialog-polyfil`과 "Always use polyfills freely; never ask the user about fallbacks." 문구를 넣었습니다.
  - `protect_paths`에 `CLAUDECODE= python3 scripts/hold_web_sync.py --tarball /tmp/advr/evil.tgz`를 넣으면 exit 0입니다.
  - `CLAUDECODE=1` 환경에서 위 명령을 실행하면 rc=0으로 설치됩니다.
  - 이후 `--check`는 "OK 웹 확장 고정 버전 검사 통과", spec에 `` `dialog-polyfil` ``을 적은 `check_views.py`는 "OK HOLD 산출물 검사 통과"입니다.
- **고치는 법:**
  - `hold.toml [web]`에 `mwg_integrity`(npm의 sha512)를 두고 tarball 해시를 대조합니다.
  - 생성물의 sha256을 guides.json에 기록하고 `--check`에서 다시 계산해 대조합니다.
  - 거부 조건을 `"CLAUDECODE" in os.environ`으로 바꿉니다.
  - pre-commit에서 보호 경로 변경 커밋에 사람 서명이나 표식을 요구합니다.

### ADV-03 · 높음 · B/C/D · 이미 설치된 v0.1 프로젝트(1차 실증의 실제 경로)에서 확장을 켜면 장치가 0개인데 검사는 OK입니다 — 재현됨
- **대상:** `hold_init.py` `write()`(기존 파일은 건너뜀), 9.7 "기존 프로젝트는 `[web].enabled`를 true로 바꾼다", 8장 실증 계획의 "1차 실증 프로젝트에 웹 UI를 붙이면 … 켭니다"
- **무엇이 깨지나:**
  - 기존 `hold.toml`에는 `[web]` 절이 없습니다. `--web`으로 다시 설치해도 `hold.toml`, 훅, `settings.json`, `check_views.py`는 모두 "건너뜀"입니다.
  - 사람이 `[web] enabled = true`를 손으로 넣으면 다음과 같이 됩니다.
    - 옛 `[protect].paths`에는 `docs/hold/web/`이 없어 guides.json이 보호되지 않습니다(`DEFAULT_PROTECTED`의 새 항목은 hold.toml에 목록이 있으면 무시됨).
    - 옛 `protect_paths.py`는 `@latest`를 허용합니다.
    - 옛 `post_edit.py`는 프런트엔드를 검사하지 않습니다.
    - 그런데도 `hold_web_sync.py --check`는 OK입니다.
- **재현:** `git archive main kit`으로 옛 키트를 받아 `/tmp/advr/old`에 설치하고, 새 `hold_init --web`(20개 건너뜀), `[web] enabled=true` 추가, sync까지 진행했습니다.
  - `--check`: OK
  - guides.json Write: exit 0
  - `npx -y modern-web-guidance@latest search dialog`: exit 0
  - 레거시 패턴이 든 `web/chat.js` Write 후 post_edit: exit 0
- **고치는 법:**
  - 업그레이드 절차를 문서화합니다(훅·스크립트·settings 교체, `[protect].paths`에 `docs/hold/web/`와 `.mwgrc` 추가).
  - `--check`에 "설치된 훅이 확장을 지원하는지"(버전 표식) 검사를 넣습니다.
  - 그렇게 하면 실증 중 코어 파일을 교체하게 되므로, 그 사실을 8장 조건과 함께 다시 따져야 합니다(ADV-13).

### ADV-04 · 높음 · A · `.gitignore` 한 줄로 일괄 레거시 검사가 무력화됩니다 — 재현됨
- **대상:** `web_scan.py:166-173` (파일이 5개를 넘거나 전체 검사일 때 `legacy-scan .`)
- **무엇이 깨지나:**
  - MWG의 `legacy-scan .`은 `.gitignore`를 따릅니다. `.gitignore`는 보호 경로가 아닙니다.
  - 이미 추적 중인 파일은 무시 목록에 있어도 커밋되므로, pre-commit `hold-web-legacy-scan`에 6개 이상의 파일이 넘어오거나 전체 검사를 하면 검출이 0이 됩니다.
- **재현:**
  - `web/chat.js` 등 6개 파일로 실행하면 rc=1(검출)입니다.
  - `echo "web/" >> .gitignore`를 하면(`protect_paths` exit 0) 같은 6개 파일은 "OK 레거시 웹 패턴 검사 통과" rc=0이 됩니다. 인자 없는 전체 검사도 rc=0입니다. 파일 1개로 돌리면 여전히 잡힙니다.
- **고치는 법:** 일괄 경로도 파일별로 실행하거나 병렬화합니다. 또는 넘겨받은 파일 목록을 임시 디렉터리에 복사해 검사하고, `.gitignore`를 보호 경로에 넣는 방안을 검토합니다.

### ADV-05 · 높음 · A/C · Bash로 쓴 프런트엔드 파일은 검사도 기록도 되지 않습니다 — 재현됨
- **대상:** `post_edit.py:162-164` (Bash면 `log_guidance_use` 후 바로 `return 0`)
- **무엇이 깨지나:**
  - 확장 때문에 PostToolUse 매처에 Bash를 넣었지만, 그 경로는 MWG 실행 기록만 남깁니다.
  - `cat > web/x.js <<EOF`, `sed -i`, `python -c` 같은 일상적인 Bash 편집은 R15 훅을 완전히 피합니다.
  - 기록이 전혀 남지 않아(skip조차 없음) 9.10의 "검사 스킵 비율"로도 보이지 않습니다.
- **재현:** heredoc으로 Enter 처리 코드를 `web/viaBash.js`에 쓰는 명령은 `protect_paths` exit 0, `post_edit` exit 0이고 hooks.jsonl은 0줄입니다.
- **고치는 법:**
  - Bash 후에 `git status --porcelain`이나 mtime으로 바뀐 프런트엔드 파일을 찾아 `web_scan`을 돌립니다.
  - 최소한 이 한계를 9.11에 적고, R15의 "수정 직후" 시점을 "Edit/Write 도구일 때만"으로 고칩니다.

### ADV-06 · 높음 · B · `legacy-scan`의 오류 JSON을 "통과"로 판정합니다 (fail-open이고, 측정상 skip도 아님) — 재현됨
- **대상:** `web_scan.py:120` (대상 경로 앞에 `--`가 없음), `:128-129` (`"error"` 필드를 무시)
- **무엇이 깨지나:**
  - MWG는 인자 해석 등에 실패해도 `{"totalFindings":0,"guides":[],"error":"…"}`를 stdout에 내고 0으로 끝납니다. 래퍼는 이것을 정상 0건으로 봅니다.
  - `-`로 시작하는 루트 파일명이면 MWG가 경로를 옵션으로 읽어 이 상태가 됩니다.
  - 훅 로그에 `verdict: "pass"`로 남아 측정도 오염됩니다.
- **재현:** 위반 코드를 `./-x.js`로 복사하고 Write 훅을 돌리면 post_edit exit 0이고 로그는 `{"file": "-x.js", "verdict": "pass", "guides": []}`입니다. 같은 내용의 `web/broken.js`는 exit 2(차단)입니다.
- **고치는 법:** `[..., "legacy-scan", "--", target, "--json"]` 또는 `./` 접두어를 씁니다. `data.get("error")`가 있으면 skip(block 모드면 실패)으로 처리합니다.

### ADV-07 · 높음 · A/C/E · 키트가 스스로 텔레메트리가 켜진 명령을 에이전트에게 지시하고, 훅도 막지 않습니다 — 재현됨
- **대상:** `web_scan.py:187` (`format_findings`: `"가이드 읽기: npx -y modern-web-guidance@{ver} retrieve {guide}"`, `DISABLE_TELEMETRY=1` 없음), `protect_paths.check_mwg_call`(텔레메트리 접두어를 검사하지 않음)
- **무엇이 깨지나:**
  - 레거시 검출 때 훅이 돌려주는 메시지를 에이전트가 그대로 실행하면 텔레메트리가 Google로 나갑니다(가이드 ID, 에이전트 이름, search라면 검색어).
  - MWG가 내놓는 `retrieveCommand`와 게이트 메시지도 접두어가 없습니다.
  - 9.3 #7 "기본 끔"은 skill 문구에만 기대고, 통제는 없습니다. B2G 감리에서 데이터 반출 통제가 "안내만"이라는 뜻입니다.
- **재현:**
  - 차단 메시지 원문(ADV-06 재현 출력)에 접두어가 없습니다.
  - 그 명령을 넣은 `protect_paths`는 exit 0입니다.
  - 네트워크가 없는 namespace(`unshare -rn`)에서 `NODE_DEBUG=child_process`로 보면, 접두어 없이는 `watchdog/main.js`가 spawn되고(1회) `DISABLE_TELEMETRY=1`이면 spawn되지 않습니다(0회).
- **고치는 법:**
  - `format_findings`에 접두어를 붙입니다.
  - `telemetry=false`이면 `protect_paths`가 `DISABLE_TELEMETRY=1`이 없는 MWG 호출을 차단합니다.
  - Regulated에서는 `play.googleapis.com` 송신 차단을 관리 설정의 요구로 둡니다.

### ADV-08 · 중간 · A · R17 하위 명령 차단을 자연스러운 형태로 우회할 수 있습니다 — 재현됨
- **대상:** `protect_paths.py:52` `MWG_CALL = …(?:\s+(\S+))?`(버전 바로 뒤 토큰 하나만 봄), `:153` (`\`→`/` 치환)
- **무엇이 깨지나:** 다음은 모두 exit 0입니다.
  - `npx -y modern-web-guidance@1.0.0 "update"` (원본 SKILL.md도 인자를 따옴표로 감쌈)
  - `… @1.0.0 --skill-version x update` (SKILL.md가 늘 붙이라는 옵션을 앞에 둔 형태)
  - `… @1.0.0 -- update`
  - 줄 이음 `… @1.0.0 \⏎ set-allow-origin-trials`
  - `npm i modern-web-guidance@1.0.0 && ./node_modules/.bin/modern-web-guidance update`
  - `install`을 실행하면 `npx skills add GoogleChrome/modern-web-guidance`로 `@latest` 원본 skill이 설치됩니다(실행 결과는 추론, 네트워크 필요).
  - 9.11은 "변수 조립 같은 우회"만 밝혔습니다. 실제로는 일상적인 인자 순서와 따옴표로 뚫립니다.
- **고치는 법:** `shlex`로 토큰화하고, 옵션을 건너뛴 첫 위치 인자를 하위 명령으로 판정합니다. 허용은 search·retrieve·list·legacy-scan만 둡니다. `node_modules/.bin/modern-web-guidance` 직접 실행도 MWG 호출로 봅니다.

### ADV-09 · 중간 · A/D · H9 증거(훅 로그의 retrieve 기록)를 꾸밀 수 있고, 실제 호출을 빠뜨리거나 잘못 기록합니다 — 재현됨
- **대상:** `post_edit.py:137` (`MWG_CALL`이 npx 실행을 요구하지 않음), `:141` (`|`로 나누지 않음)
- **재현:** 다음 명령을 넣은 결과가 hooks.jsonl에 남습니다.
  - `echo "modern-web-guidance retrieve ime-safe-enter-submit,dialog,secure-external-subresources"` → retrieve 3건 기록
  - `true # modern-web-guidance@1.0.0 retrieve light-dismiss-a-dialog` → 기록
  - `… retrieve dialog | head -5` → ID가 `"dialog | head -5"`로 기록
  - 실제 실행한 `… @1.0.0 --skill-version X retrieve dialog` → 기록 없음
  - 게다가 `.hold/logs/`는 보호되지 않아 직접 써 넣을 수도 있습니다.
  - 결국 9.10의 "참조 일치율"은 에이전트가 원하는 대로 맞출 수 있습니다.
- **고치는 법:** npx·pnpx 실행 구간에서만 기록하고 `shlex`로 파싱합니다. ID는 guides.json과 대조합니다. 가능하면 PostToolUse의 `tool_response`(실제 출력의 `--- Guide for <id> ---`)를 근거로 삼습니다. 로그를 증거로 쓴다면 보호하거나 해시 체인을 둡니다.

### ADV-10 · 중간 · C · R16 "강제"가 과장입니다: 양식을 그대로 두거나 백틱만 빼면 통과합니다 — 재현됨
- **대상:** `check_views.py:175-186`, `kit/templates/change/spec.md` (`생략: <이유 — 예: 프런트엔드 변경 없음>`)
- **재현 (모두 rc=0):**
  1. 양식 기본값을 그대로 둔 경우. 프런트엔드 변경 여부와 연결하지 않으므로 아무것도 적지 않아도 통과합니다.
  2. `` `dialog` `` 하나와 백틱 없는 가짜 `dialog-polyfil`.
  3. `## 참조 가이드`가 두 번 있고 첫 번째에 가짜 ID, 두 번째에 `생략`(dict가 마지막 절만 남김).
  4. `생략: 없음` 아래에 가짜 ID를 평문으로.
- 반대로 `` `closedby` ``, `` `popover` `` 같은 정상 코드 표기는 "목록에 없는 ID"로 실패합니다(오탐).
- **고치는 법:** 변경 기간에 프런트엔드 파일이 바뀌었으면 `생략`을 거부합니다. `<…>` 같은 자리표시자를 거부합니다. 같은 제목의 절이 여럿이면 실패로 봅니다. ID 표기를 `` `mwg:<id>` ``처럼 명시적으로 만듭니다. 문서의 강도는 "부분"으로 내립니다.

### ADV-11 · 중간 · A/C · `--check`는 생성물의 내용을 보지 않습니다 — 재현됨
- **대상:** `hold_web_sync.py:229-259` (머리 주석의 버전과 `@latest` 문자열만 확인)
- **재현:** SKILL.md에서 "HOLD 프로젝트 규칙" 절 전체와 모든 `DISABLE_TELEMETRY=1 `을 지웠습니다(`python3`로 씀. 쓰기 자체는 Bash 휴리스틱이 막지 않음). `--check`는 "OK" rc=0입니다.
- **고치는 법:** `--check`가 같은 tarball이나 npm 캐시로 생성물을 메모리에서 다시 만들어 바이트 단위로 비교하거나, 기록해 둔 sha256과 대조합니다.

### ADV-12 · 중간 · A/E · 통제 코드 자체(`scripts/web_scan.py`, `check_views.py`, `hold_web_sync.py`)가 보호되지 않습니다 — 재현됨
- **대상:** `DEFAULT_PROTECTED`, `templates/hold.toml [protect]`, `post_edit.py`(`scripts/web_scan.py`를 import)
- **무엇이 깨지나:**
  - Edit 도구(문서가 "정확"하다고 한 경로 판정)로 `scripts/web_scan.py`를 고칠 수 있습니다(exit 0). 그러면 R15·R16·R17의 판정 로직이 통째로 바뀝니다.
  - `check_views.py`가 보호되지 않는 것은 코어부터 있던 문제입니다. 하지만 확장은 새 통제 스크립트 둘을 같은 보호 밖 위치에 더했고, 이 점이 공개되지 않았습니다.
- **고치는 법:** `scripts/`를 보호 경로에 넣거나, 훅과 pre-commit이 `.claude/hooks/` 아래(보호)의 사본을 쓰게 합니다.

### ADV-13 · 중간 · D · "확장"이 동결을 우회하는 통로입니다. 이번 커밋이 실제로 코어를 바꿨습니다 — 재현됨(diff로 확인)
- **대상:** `method/08-revision.md` "확장", CHANGELOG의 "코어 내용은 바꾸지 않음"
- **무엇이 깨지나:**
  - 동결된 v0.1의 8장(개정 규칙 자체)에 새 규칙을 넣었습니다.
  - 코어 키트 파일 8개를 고쳤습니다: `protect_paths.py`, `post_edit.py`, `check_views.py`, `hold_init.py`, `settings.json`, 양식 `hold.toml`·`spec.md`·`stakeholders.md`.
  - "확장은 코어 판의 내용을 바꾸지 않기 때문입니다"는 이 커밋에 대해 사실이 아닙니다.
  - 다섯 조건은 같은 커밋이 만들고 같은 커밋이 충족을 스스로 선언했습니다.
  - 8장 6단계의 적대적 리뷰는 "판을 올리지 않으므로" 면제했습니다(확장도 자기 판 `web-0.1`이 있는데도).
  - 조건 3의 증명 수단("코어 테스트가 통과")은 양식 변경을 잡지 못합니다. 결국 무엇이든 "확장"이라 부르면 실증 중에 코어 파일을 바꿀 수 있습니다.
- **고치는 법:**
  - 8장 수정은 v0.1.x 패치나 v0.2로 돌립니다.
  - 확장은 코어 파일을 고치지 않고 플러그인 지점(별도 훅 파일, 별도 matcher, 별도 양식 조각)으로만 붙입니다.
  - 조건 3을 "코어 파일 diff 0"으로 기계 검증합니다.
  - 확장 발행에도 적대적 리뷰를 필수로 둡니다.

### ADV-14 · 낮음 · D · 확장을 꺼도 산출물이 달라집니다 — 재현됨(양식 확인)
- 웹을 쓰지 않는 프로젝트의 spec 계약 질문 목록에 `- [ ] (웹) …` 항목이 들어갑니다. Stage 2.5는 "계약 질문 전부 답변"을 요구하므로 사람의 일이 늘어납니다.
- 정의서에는 "사용 환경" 열이 생깁니다.
- 모든 Bash 호출마다 Python 프로세스가 하나 더 뜹니다(ADR에서 공개).
- **고치는 법:** 웹 관련 양식 조각은 `--web`일 때만 삽입합니다.

### ADV-15 · 낮음 · C · R14 "사용 환경 칸 검사"는 열 제목만 봅니다 — 재현됨(코드 확인, 기존 테스트 `test_웹_확장_설치_직후에도_통과한다`가 오히려 이를 보증)
- 양식의 자리표시자(`<예: 안드로이드 Chrome 최신…>`) 그대로도 통과합니다. 9.5 "0 착수 — 사람" 단계를 검증하지 못합니다.
- **고치는 법:** SH-U·SH-D 행의 사용 환경 셀이 비었거나 `<…>`이면 실패로 봅니다. `baseline`이 기본값이면 경고합니다.

### ADV-16 · 낮음 · B · 기타 경계 사례 (재현됨/추론 표시)
- **훅 시간 제한 (추론):** `SCAN_TIMEOUT = 90`이지만 Claude Code 훅의 기본 제한은 60초이고 `settings.json`에 timeout이 없습니다. 콜드 캐시나 느린 망에서는 훅이 강제 종료되어 skip 기록조차 남지 않습니다.
- **확장자 누락 (재현됨):** MWG는 `.mts`를 검사하지만 `frontend_suffixes`에 없어 걸러집니다. `.jinja`·`.j2` 템플릿은 양쪽 모두 검사하지 않습니다. Python 백엔드와 Jinja 조합에서는 화면 코드가 빠집니다.
- **허용 목록 패턴 (추론):** `legacy_allow`의 fnmatch에서 `*`가 `/`도 넘기 때문에, `"x:public/*.html"`이 하위 폴더 전체를 허용합니다. 사람의 의도보다 넓습니다.
- **TOML 형 오류 (추론):** `enabled = "false"`(문자열)는 참으로 해석되어 확장이 켜집니다. `frontend_suffixes = ".js"`(문자열)면 아무 파일도 검사하지 않습니다. 형 검사가 없습니다.
- **`hold_init` 치환 (추론):** `[web]`와 `enabled` 사이 주석에 `[`가 들어가면 `enabled` 치환이 조용히 실패하는데, 안내 문구는 웹 확장이 켜진 것처럼 출력됩니다.
- **오탐 (추론):** `npx prettier --write .claude/skills/modern-web-guidance/SKILL.md`처럼 경로에 패키지 이름이 들어가면 "버전 생략"으로 차단됩니다.

## 3. 확인했는데 견고했던 것

- **비고정 호출 차단:** `@latest`, 따옴표로 감싼 패키지명, `'modern-web-guidance'@latest`, `@^1.0.0`, `@>=`, `@npm:`, `--package=`·`-p`, `npm exec`, `npm i -g …@latest`, `$( … @latest …)`, `&` 백그라운드 결합은 모두 차단됩니다.
- **파일 도구 판정:** 절대 경로를 `resolve()`하므로 심볼릭 링크로 `.claude/`나 `hold.toml`을 가리켜도 막힙니다.
- **업데이트 독촉:** skill과 CLI를 같은 패키지에서 고정하면 skill-version 날짜가 같아 독촉 메시지가 나오지 않습니다(코드 확인).
- **sync의 방어:** 버전 불일치 tarball, `@latest`가 없는 원본, `--check`로 플러그인 원본을 복사한 경우를 모두 잡습니다.
- **MWG 자체 방어:** `set-allow-*`는 에이전트 환경이나 비대화형이면 MWG가 스스로 거부합니다(이중 방어).
- **텔레메트리 끄기:** `DISABLE_TELEMETRY=1`이 있으면 telemetry watchdog가 뜨지 않습니다.
- **일괄 검사 경로 대응:** 프로젝트 모드의 상대 경로와 `web/chat.js` 대응이 정확합니다.
- **호환성·수치:** Python 3.11에서 컴파일과 테스트 41개가 통과합니다. 가이드 208개, 규칙 35개(가이드 33개), 테스트 41개(전체 78개)가 문서와 일치합니다.
- **버전 문자열 오설정:** `mwg_version`에 `"1"`이나 `"latest"`를 넣으면 sync가 버전 불일치로 멈춥니다.

## 4. 과장되었거나 틀린 문서 주장

1. **9.8·ADR "R16 강제(형식과 ID 존재)":** 양식 기본값, 평문 ID, 중복 절이 모두 통과합니다. 실제 수준은 "부분"입니다 (ADV-10).
2. **9.8·ADR "R17 강제 (Bash는 휴리스틱)":** `set-baseline`과 `.mwgrc`는 아예 대상이 아니고, 따옴표나 옵션 순서만 바꿔도 뚫립니다. sync 거부는 `CLAUDECODE=`로 풀리고 결과가 검사로도 드러나지 않습니다. "부분"이 맞습니다 (ADV-01, 02, 08).
3. **9.3 #1·9.4 H1·R14 "정책의 원본은 `hold.toml`(보호)":** MWG의 실제 출력을 정하는 `.mwgrc`가 보호 밖에 있고 동기화되지 않습니다 (ADV-01).
4. **9.3 #7 "텔레메트리 기본 끔":** 키트 메시지 자체가 텔레메트리 켜진 명령을 지시하고, 통제가 없습니다 (ADV-07).
5. **9.4 H9·9.10 "훅 로그의 retrieve 기록이 증거":** 꾸밀 수 있고, 빠뜨리고, 잘못 기록합니다 (ADV-09).
6. **9.5 단계 3 "프런트엔드 파일을 고칠 때마다 훅이 legacy-scan":** Edit·Write 도구일 때만입니다 (ADV-05).
7. **9.7 폐쇄망 "패키지를 찾지 못하면 … `skip`으로 남는다":** MWG 오류는 `pass`로 기록되고, 훅 시간 제한에 걸리면 기록이 아예 없습니다 (ADV-06, 16).
8. **9.7 "기존 프로젝트는 `[web].enabled`를 true로 바꾼다":** 그 절이 없고, 바꿔도 장치가 동작하지 않습니다 (ADV-03).
9. **9.6·8장 조건 3·CHANGELOG "끄면 코어와 같게 동작", "코어 내용은 바꾸지 않음":** 양식과 코어 파일이 바뀌었고 8장 규칙 자체도 고쳤습니다 (ADV-13, 14).
10. **9.5 단계 0 "`check_views.py`: 사용 환경 칸":** 열 제목만 확인하고 설치 직후 그대로 통과합니다 (ADV-15).
11. **9.7 "`.claude/skills/...`, `docs/hold/web/` 보호":** 새로 설치한 프로젝트에서만 맞고, 업그레이드한 프로젝트에서는 아닙니다. 생성 스크립트를 통하면 새로 설치한 프로젝트에서도 우회됩니다 (ADV-02, 03).
