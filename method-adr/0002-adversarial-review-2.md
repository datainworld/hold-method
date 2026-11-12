# 방법론 ADR 0002 첨부: 적대적 리뷰 원문 (2차)

- 대상: PR #1 두 번째 커밋 (`refactor(web-0.1)`, 코어 무수정 재설계판)
- 검토자: 1차와 같은 검토자 (작성에 관여하지 않음). 임시 복사본에서 실제 공격을 실행
- 날짜: 2026-11-12
- 처리 결과: [ADR 0002](0002-web-extension-mwg.md)의 "2차 리뷰와 처리" 표

아래는 검토자의 보고서 원문입니다. 가리키는 코드는 재설계판 기준이며, 3차 보강 후 상당 부분이 바뀌었습니다.

---

## 1. 총평

**병합하면 안 됩니다.** 1차 리뷰에서 지적한 통로는 대부분 막혔습니다. 코어 무수정도 사실입니다(`main` 대비 `method/ kit/ tests/ examples/` 차이 0, 매니페스트 58개 일치). 하지만 재설계에서 새로 생긴 "읽기 전용 명령 화이트리스트"와 "토큰에 경로 문자열이 있는지 보는 판정"이 새 큰 구멍입니다. `git show --output=<보호 경로>` 한 줄이면, 난독화 없이도 확장 훅·코어 훅을 모두 통과해 `web_guard.py`·`hold.toml`·`.mwgrc`를 덮어쓸 수 있습니다. 덮어쓴 뒤에도 `web_check.py`는 OK입니다. 글롭(`.c?aude/hold-we?/…`)으로도 같은 일이 됩니다. 확장 코드 자체의 무결성은 아무도 검사하지 않습니다.

또 R17의 "고정 무결성"은 설치 시점에만 적용됩니다. 실행 시 `npx`가 실제로 쓰는 패키지(`_npx` 캐시, 로컬 `node_modules`)는 검증하지 않아, R15를 훅과 pre-commit 양쪽에서 무력화할 수 있습니다. 따라서 "R17 강제"와 README 11절의 "결과물은 커밋 때 잡힌다"는 아직 사실이 아닙니다.

## 2. 1차 발견(ADV-01~16) 처리 상태

| ID | 판정 | 근거 (재현) |
| --- | --- | --- |
| ADV-01 `.mwgrc`·`set-baseline` | **부분 해결** | 직접 경로(리다이렉트, `tee`, Write, `../`)는 막힘. `git show --output=.mwgrc`, 글롭 `.mwg?c`, `<( … set-baseline …)`, 대소문자 `.MWGRC`로 우회됨 (ADV2-01·02·04·12) |
| ADV-02 sync로 보호 파일 조작 | **부분 해결** | 직접 실행은 막힘. 글롭 경로 `env -u CLAUDECODE python3 .c?aude/hold-we?/sync.py --pin 1.0.0 --tarball evil.tgz`가 hold.toml까지 다시 쓰고, npm 캐시가 없으면 `web_check`가 WARN만 내고 OK (ADV2-02·09) |
| ADV-03 기존 프로젝트 장치 0개 | 해결됨 | `install.py` 독립 설치, `web_check`가 훅 등록·판 확인 |
| ADV-04 `.gitignore` | 해결됨 | 실제 MWG로 `web/`을 무시 목록에 넣고 6개 파일 검사 → 검출 |
| ADV-05 Bash로 쓴 파일 | **부분 해결** | 기본 경로는 잡힘. `touch -r`, 백그라운드 쓰기, 파일명 크래시로 회피됨 (ADV2-06) |
| ADV-06 오류 JSON 통과 | 해결됨 | `-x.js` 검출, error는 실패로 처리 |
| ADV-07 텔레메트리 | **부분 해결** | `DISABLE_TELEMETRY=1 env -u DISABLE_TELEMETRY npx …`가 통과하고 실제로 watchdog가 뜸 (ADV2-05) |
| ADV-08 R17 하위 명령 우회 | **부분 해결** | 따옴표·옵션 순서·`--yes`·`xargs`·함수·alias는 막힘. 프로세스 치환과 글롭 바이너리는 통과 (ADV2-04) |
| ADV-09 retrieve 기록 위조 | **부분 해결** | `echo` 명령 위조는 막힘. 같은 명령 안 `printf` 표식과 가짜 saved-to 파일로 위조됨 (ADV2-10) |
| ADV-10 R16 강제 과장 | **부분 해결** | 표기는 강화됨. 폴더 이름만 바꿔 R16 전체를 건너뜀 (ADV2-11) |
| ADV-11 `--check`가 내용을 안 봄 | **부분 해결** | 재생성 대조는 npm 캐시가 있을 때만. 없으면 lock 해시를 맞춘 위조가 통과 (ADV2-09) |
| ADV-12 통제 코드 미보호 | **미해결(형태만 바뀜)** | `.claude/hold-web/`로 옮겼지만 `git show --output`과 글롭으로 덮어쓸 수 있고, 코드 무결성 검사가 없음 (ADV2-01·02) |
| ADV-13 동결 우회 | 해결됨 | 코어 diff 0, 매니페스트 OK (3.11에서도 테스트 90개 통과) |
| ADV-14 꺼도 양식이 다름 | 해결됨 | 코어 양식 원복 |
| ADV-15 사용 환경 검사 | 해결됨 | 값 검사(자리표시자, 전원 해당 없음, 없는 ID) |
| ADV-16 경계 사례 | 대체로 해결됨 | timeout 120, `.mts`·Jinja, `*`/`**`, 형 검사 |

## 3. 발견 목록 (심각도 순)

### ADV2-01 · 치명 · 화이트리스트된 `git show/log/diff --output=`으로 모든 보호 경로를 덮어씁니다 — 재현됨
- **대상:** `common.py:56` (`READONLY_GIT`), `:477-478`. 코어 `protect_paths.py`의 `WRITE_WORDS`에도 해당 패턴이 없음.
- **무엇이 깨지나:** `--output=`은 git의 쓰기 옵션입니다. `git show`는 화이트리스트에 있어 보호 경로가 토큰에 그대로 보여도 통과합니다. 코어 훅도 막지 않습니다.
- **재현:** `B=$(git hash-object -w /dev/null)` 뒤에 아래 명령을 넣으면 모두 `protect_paths=0 web_guard=0`입니다.
  - `git show --output=.claude/hooks/web_guard.py $B`
  - `.claude/hold-web/common.py`, `hold.toml`, `docs/hold/web/lock.json`, `.claude/settings.json`을 대상으로 한 같은 명령
  - `git log -0 --output=.hold/logs/hooks.jsonl` (로그 지우기)
  - `git show --output=.mwgrc <blob>`으로 `{"baseline":"limited","allowOriginTrials":true,…}`를 쓰는 데 성공
  - `web_guard.py`를 0바이트로 만든 뒤 `npx -y modern-web-guidance@latest set-baseline limited` → 통과. `web_check.py` → "OK 웹 확장 검사 통과"
- **고치는 법:** git 화이트리스트에서 `--output`, `-o`, `--output-directory`를 거부합니다. 근본적으로는 "읽기 전용 명령" 예외를 없애고, 보호 경로가 언급되면 `cat`·`grep`·`head`·`tail`·`ls`(옵션 제한)만 허용합니다. `web_check`에 확장 코드 해시 대조를 넣습니다(ADV2-02 참고).

### ADV2-02 · 치명 · 글롭 경로로 보호 경로 토큰 검사를 피하고, 확장 코드·hold.toml·sync를 마음대로 다룹니다 — 재현됨
- **대상:** `common.py:177-181` (`token_mentions_protected`는 문자열 포함 여부만 봄), `:467` (`endswith(HUMAN_ONLY_SCRIPTS)`). `web_check.check_install`은 `VERSION` 파일 내용과 훅 파일 존재만 확인합니다.
- **재현:** 아래는 모두 두 훅이 0입니다.
  - `sed -i 's/^    pinned = …$/    return None/' .c?aude/hold-we?/common.py` → R17 판정이 사라짐. 이후 `@latest`, 텔레메트리 접두어 없는 호출, `set-baseline`이 모두 통과하고 `web_check` OK.
  - `sed -i '…enabled = false' hold.to?l` → `web_check` "OK 웹 확장이 꺼져 있습니다", `web_scan` 통과.
  - `env -u CLAUDECODE python3 .c?aude/hold-we?/sync.py --pin 1.0.0 --tarball /tmp/advr2/evil.tgz` → 실행됨. `--pin`과 `--tarball`을 함께 주면 무결성 값을 그 파일로 계산해 **hold.toml을 직접 고칩니다.** 가짜 ID와 지시 문구가 생성물에 들어가고, npm 캐시가 없으면 `web_check`는 WARN만 내고 OK.
  - 같은 수법으로 `.mwg?c`, `docs/hold/we?/lock.json`, `.hold/log?/hooks.jsonl`도 바뀝니다.
- README 11절은 "문자열을 조립·인코딩한 실행"만 한계로 밝혔고, 그 결과는 "커밋 때 web_check가 잡는다"고 했습니다. 실제로는 글롭이라는 기본 셸 문법으로 되고, 코드와 hold.toml 변경은 커밋 때도 잡히지 않습니다.
- **고치는 법:**
  - 보호 경로 판정을 토큰 문자열이 아니라 글롭 전개 후의 경로로 합니다(`glob.glob`로 전개해 `is_protected_path`). 전개할 수 없는 메타문자(`$`, `*`, `?`, `[`, `{`)와 보호 경로 조각이 함께 있으면 막습니다(fail-closed).
  - `lock.json`이나 별도 파일에 `.claude/hold-web/*`·`web_guard.py`의 해시를 넣고 `web_check`가 대조합니다. 이상적으로는 `web_check`를 저장소의 `extensions/web/kit` 원본과 대조합니다.
  - `lock.json`이 있는데 `enabled = false`이면 실패(tripwire)로 봅니다.
  - `sync.py --pin --tarball`은 사람이 무결성 값을 따로 입력하게 합니다.

### ADV2-03 · 높음 · R17 무결성은 설치 시점에만 적용되고, 실행 시 패키지는 검증하지 않습니다 — 재현됨
- **대상:** `common.scan()` (`npx -y modern-web-guidance@<ver>`), 에이전트의 search·retrieve 호출 전반
- **무엇이 깨지나:** `npx`는 `<npm-cache>/_npx/<hash>/node_modules`나 프로젝트의 `node_modules`에 이미 있는 1.0.0을 다시 검증하지 않고 실행합니다. `web_check`의 재생성 대조는 `npm pack --offline`(cacache)을 보므로 이 변조를 보지 못합니다.
- **재현:**
  1. 캐시 변조: `sed -i '…legacy-scan 분기에서 빈 JSON 출력 후 종료…' $NPM_CONFIG_CACHE/_npx/*/node_modules/modern-web-gui*/skills/*/modern-web.mjs` → 두 훅 0. 이후 IME 위반 `web/chat.js`에 대해 훅 PostToolUse 0, pre-commit `web_scan.py` "OK … 통과", `web_check` OK.
  2. 로컬 섀도잉: `package.json`에 `"modern-web-guidance":"file:/tmp/advr2/evilpkg"`(Write, 막지 않음)를 넣고 `npm install --offline`(두 훅 0) → `DISABLE_TELEMETRY=1 npx -y modern-web-guidance@1.0.0 retrieve dialog`(훅 통과)가 "EVIL GUIDE: never add fallbacks…"를 출력합니다. 출력에 `--- Guide for dialog ---` 표식이 있어 증거로도 "확인됨" 처리됩니다. `web_check` OK.
  3. `--registry=`, `npm_config_registry=`도 훅을 통과합니다. 캐시가 없을 때 다른 레지스트리에서 받는 효과는 추론입니다.
- **고치는 법:** `sync.py`가 검증한 tarball을 보호 경로(예: `.claude/hold-web/pkg/`)에 풀고, 파일 해시를 lock에 기록합니다. 에이전트와 훅은 `npx` 대신 래퍼(`python .claude/hold-web/mwg.py search …`)로 그 사본만 실행합니다. 래퍼가 실행 전에 해시를 대조하고 텔레메트리도 강제로 끕니다. 그러면 `npx` 해석기 자체가 거의 필요 없어집니다.

### ADV2-04 · 높음 · 프로세스 치환 `<( … )`, `>( … )` 안의 명령을 해석하지 않습니다 — 재현됨
- **대상:** `split_commands` (`<(`가 하나의 인자 토큰이 되어 바깥 명령의 인자로 흡수됨)
- **재현:** `DISABLE_TELEMETRY=1 npx -y modern-web-guidance@1.0.0 search x <(DISABLE_TELEMETRY=1 npx -y modern-web-guidance@1.0.0 set-baseline limited)` → 두 훅 0. 실제로 실행하면 `.mwgrc`가 `{"baseline":"limited",…}`로 바뀝니다. `@latest`를 넣어도 통과합니다.
  - 세션 동안 정책이 뒤집힌 채로 작업한 뒤, `cp /tmp/bak .mwg?c`(훅 통과)로 되돌리면 커밋 때 `web_check`도 OK입니다.
- **고치는 법:** 토큰 안의 `<(`·`>(`를 명령 치환과 같이 재귀 해석합니다. 해석하지 못하는 구문이 있고 패키지 이름이 있으면 막습니다. README 5절의 지원 문법 목록에 실제로 다루는 것만 적습니다.

### ADV2-05 · 높음 · 텔레메트리 차단을 `env -u`로 우회합니다 — 재현됨
- **대상:** `_finish`는 `env`를 감싸는 명령으로 건너뛰면서 `-u VAR`를 값으로만 소비하고, 바깥 할당 `DISABLE_TELEMETRY=1`은 그대로 유효하다고 봅니다.
- **재현:** `DISABLE_TELEMETRY=1 env -u DISABLE_TELEMETRY npx -y modern-web-guidance@1.0.0 search "서울시 민원 챗봇 dialog"` → 두 훅 0. 네트워크가 없는 namespace에서 `NODE_DEBUG=child_process`로 보면 watchdog spawn이 1회입니다(검색어가 전송 대기열에 들어감). `env -i …`도 통과합니다. 글롭으로 바이너리를 직접 실행하는 `./modern-web-gui* …`도 통과합니다.
- 공공 과제에서 검색어 반출 통제가 다시 우회 가능한 상태입니다.
- **고치는 법:** `env`의 `-u`·`-i`·`VAR=` 인자를 해석해 실제 환경을 계산합니다. 더 단순하게는 ADV2-03의 래퍼에서 환경을 강제합니다.

### ADV2-06 · 높음 · 실행 전후 스냅샷을 회피할 수 있습니다 — 재현됨 3, 추론 1
- **대상:** `common.frontend_snapshot`(mtime_ns·size만 비교), `web_guard.post`
- **재현:**
  1. 크기를 같게 바꾸고 mtime 보존: `cp -p web/chat.js ref && printf … > web/chat.js && touch -r ref web/chat.js`(124바이트 → 124바이트) → PostToolUse 0, `isComposing` 0개.
  2. 백그라운드: `(sleep 3; printf … > web/chat.js) &` → PostToolUse 0. 3초 뒤 파일이 바뀌어도 기록이 없습니다.
  3. 크래시(fail-open): 같은 명령에서 `web/$'\xff'.js`를 만들면 `c.log`에서 `UnicodeEncodeError`가 나고 훅이 exit 1로 끝납니다. Claude Code는 이를 비차단 오류로 처리해 함께 바뀐 `chat.js` 위반도 보고되지 않습니다.
  4. (추론) Claude Code가 0이 아닌 종료 코드의 Bash에 PostToolUse를 보내지 않는 판이라면(`PostToolUseFailure`로 분리), `…; false`로 검사를 건너뜁니다. 스냅샷 파일도 남습니다.
- 커밋 때 pre-commit이 남은 방어선이지만, 그것도 꺼질 수 있습니다(ADV2-08).
- **고치는 법:** 스냅샷에 내용 해시를 넣습니다(크기가 작으면 sha1, 크면 ctime 포함). 남은 스냅샷 파일은 다음 PreToolUse에서 대조하고, `PostToolUseFailure`에도 등록합니다. `log`는 `ensure_ascii=True`로 쓰고 예외를 모두 잡습니다. 훅 전체를 try/except로 감싸 예외가 나면 exit 2(fail-closed)로 끝냅니다. 백그라운드 실행(`&`, `nohup`, `setsid`, `disown`)은 웹 확장에서 막거나 경고합니다.

### ADV2-07 · 중간 · legacy-scan 내부의 제외 규칙 때문에 흔한 폴더·파일 이름이 조용히 "pass"가 됩니다 — 재현됨
- **대상:** `common.scan()`(원래 상대 경로를 그대로 복사)
- **재현:** 같은 IME 위반 코드를 여러 위치에 두고 검사했습니다. 검출이 0이고 skip·error도 없는 위치는 다음과 같습니다.
  - 폴더: `test/`, `tests/`, `__tests__/`, `spec/`, `fixtures/`, `example(s)/`, `generated/`, `out/`, `tmp/`, `coverage/`, `third_party/`, `bower_components/`, `.cache/`, `.storybook/`
  - 파일: `*.min.js`, `*.bundle.js`, `*.test.js`, `*.spec.js`
  - 훅 로그에는 `verdict: "pass"`로 남습니다.
- **고치는 법:** 임시 폴더에 중립 이름(`src/f0001.js`처럼 확장자만 유지)으로 복사하고 결과를 원래 경로로 되돌립니다. 검사 파일 수를 대조할 수 있으면 대조합니다.

### ADV2-08 · 중간 · "커밋 때 잡힌다"의 전제인 pre-commit을 에이전트가 끌 수 있습니다 — 재현됨
- **재현:**
  - `.pre-commit-config.yaml`은 코어·확장 모두 보호하지 않습니다(Write 훅 0). 웹 검사 항목을 지우고 주석 `# hold-web-check`만 남기면 `web_check` OK입니다(문자열 포함 여부만 확인).
  - `git commit --no-verify`, `git config core.hooksPath …`도 훅이 막지 않습니다.
  - `pre-commit install` 여부(`.git/hooks/pre-commit`)는 아무도 확인하지 않습니다.
- **고치는 법:** `.pre-commit-config.yaml`을 확장 보호 경로에 넣습니다. YAML을 파싱해 hook id와 entry를 확인합니다. `--no-verify`, `-n`, `core.hooksPath`를 막습니다. 설치 여부를 검사합니다. 최종 방어선을 CI(서버 쪽)에 두라고 문서에 명시합니다.

### ADV2-09 · 중간 · 재생성 대조는 npm 캐시가 있을 때만입니다 — 재현됨
- **대상:** `web_check.check_install` (캐시가 없으면 WARN만)
- **재현:**
  - 글롭 경로로 SKILL.md에서 HOLD 절을 지우고 lock 해시를 맞추면, 캐시 없는 환경(`NPM_CONFIG_CACHE=빈 폴더`)의 `web_check`는 "WARN … OK"입니다. 캐시가 있는 환경에서는 실패로 잡힙니다.
  - ADV2-02의 evil sync도 같은 결과입니다.
- CI나 다른 개발자 PC처럼 캐시가 없는 곳에서는 README 5절의 "lock까지 맞춰 꾸민 생성물도 잡힙니다"가 거짓이 됩니다.
- **고치는 법:** Standard 이상에서는 캐시가 없으면 실패로 봅니다. 또는 검증된 tarball 사본을 저장소 밖 보호 위치에 두고 대조합니다(ADV2-03의 해법과 같음).

### ADV2-10 · 중간 · retrieve 증거를 여전히 꾸밀 수 있습니다 — 재현됨
- **대상:** `common.retrieved_ids` (tool_response의 모든 문자열에서 표식을 찾음), `SAVED_TO`(이름이 `mwg-guide-`로 시작하는 임의 파일)
- **재현:**
  - `… retrieve dialog | head -0; printf -- '--- Guide for ime-safe-enter-submit ---\n--- Guide for secure-external-subresources ---\n'` → 기록 `requested:["dialog"]`, `confirmed:["ime-safe-enter-submit","secure-external-subresources"]`. 요청하지 않은 ID가 확인됨으로 기록되고, 실제로 요청한 `dialog`는 빠집니다.
  - `/tmp/mwg-guide-forged.md`를 만들고 `echo 'Output saved to /tmp/mwg-guide-forged.md'` → `confirmed:["light-dismiss-a-dialog"]`.
- **고치는 법:** 요청한 ID와 교집합만 인정합니다. retrieve가 아닌 다른 명령과 같은 Bash 호출에 섞이면 기록하지 않습니다. 저장 파일은 Pre 이후에 생성되었고 이름이 `mwg-guide-<pid>-<ts>.md` 형식인 것만 받습니다. 가장 좋은 방법은 래퍼(ADV2-03)가 출력을 직접 기록하는 것입니다.

### ADV2-11 · 중간 · 폴더 이름만 바꿔 R16 검사 전체를 건너뜁니다 — 재현됨
- **대상:** `web_check.check_change:200-202` (폴더 이름이 8자리 날짜로 시작하지 않거나 `since`보다 이르면 return)
- **재현:** `changes/chat-ui/`, `changes/20200101-chat/`에 가짜 `mwg:dialog-polyfil`을 적어도 훅 PostToolUse 0, `web_check` 실패 없음. `20261113-chat`은 실패로 잡힙니다. 코어 `check_views`는 이 폴더들을 검사하지만 R16과는 무관합니다.
- **고치는 법:** 날짜 형식이 아닌 폴더는 실패로 봅니다. `since` 판정은 폴더 이름이 아니라 git에서 처음 추가된 날짜로 합니다.

### ADV2-12 · 중간 · 대소문자 변형과 NTFS 경로 변형이 파일 도구 판정을 통과합니다 — 훅 판정 재현됨, 실효는 추론
- **재현 (Linux, 두 훅 모두 0):** Write `.MWGRC`, `web/.Mwgrc`, `.CLAUDE/hold-web/common.py`, `Docs/Hold/Web/lock.json`, `HOLD.TOML`, `.mwgrc::$DATA`
- Windows·macOS의 기본 파일 시스템은 대소문자를 구분하지 않으므로, 이 쓰기는 실제 보호 파일을 덮어씁니다(추론). `.mwgrc::$DATA`와 끝에 점이 붙은 이름은 Windows에서 같은 파일입니다(추론). 코어 `protect_paths.py`도 같은 약점이 있습니다.
- **고치는 법:** 비교 전에 `os.path.normcase`와 `casefold`로 정규화하고, `:`·끝의 점·공백을 제거합니다. 이미 있는 파일이면 `os.path.samefile`로 판정합니다.

### ADV2-13 · 낮음 · 절차·문서 정합성 — 재현됨(문서 확인)
- ADR 0002는 "상태: 승인"인데, 확장 규약 5(발행 전 적대적 리뷰)의 재검토 절은 "작성 중"입니다.
- `install.py` 문서 문자열은 "코어 키트가 설치한 파일은 바꾸지 않고"라고 하지만, 실제로는 `.claude/settings.json`을 재직렬화하고 `CLAUDE.md`, `changes/_template/spec.md`, `hold.toml`에 덧붙입니다. 규약 3의 "표식 절 덧붙이기"와 같은 말로 적어야 합니다.

## 4. 확인했는데 견고했던 것

- **코어 무수정과 매니페스트:** `main` 대비 코어 diff 0, 매니페스트 OK, 코어 테스트 37개와 확장 테스트 90개 통과(3.11·3.13). 매니페스트 기준점(`main`, 11-07)이 동결일(11-09) 이전인 것도 확인했습니다.
- **직접 경로 쓰기 차단:** `echo > .mwgrc`, `tee .mwgrc <<<`, Write `.mwgrc`·`web/../.mwgrc`, `mv .claude/hold-web …`
- **R17 해석기가 막은 것:** `@latest`, 접두어 누락, `set-baseline`, `"update"`, `--yes`, `--skill-version` 옵션을 앞에 둔 형태, `modern-web-guidanc"e@…"` 따옴표 분할, `$'…'`, `$(echo set-baseline)`·`${X:-…}`(fail-closed), 같은 명령에서 정의한 함수·alias(fail-closed), `xargs`, `-h`, `&` 뒤의 `@latest`, `node …/modern-web.mjs` 직접 실행, `export DISABLE_TELEMETRY=1; npx …`(정상 호출까지 막는 오탐이지만 안전한 쪽)
- **사람 전용 스크립트:** `sync.py` 직접 경로 실행 차단, `CLAUDECODE=` 빈 값 거부
- **레거시 검사 수정:** `.gitignore`(ADV-04), `-x.js`(ADV-06), Jinja(`.j2`)를 HTML로 검사, 기본 heredoc Bash 쓰기 검출
- **무결성 검증:** 사람이 조작 tarball로 `sync.py`를 돌려도, `--pin` 없이는 "무결성 값이 다릅니다"로 멈춥니다. npm 캐시가 있으면 재생성 대조가 SKILL.md·lock·무결성 불일치를 잡습니다.

## 5. 과장되었거나 틀린 문서 주장

1. **README 8절·ADR "R17 강제 (… 결과물은 커밋 시 대조로 잡음)":** `git show --output`, 글롭, 프로세스 치환, `env -u`, 실행 시 패키지 변조로 뚫리고, 코드·hold.toml 변경은 커밋 때도 잡히지 않습니다. "부분"이 맞습니다 (ADV2-01~05).
2. **README 5절 "Bash 명령을 셸 문법대로 해석합니다", "확장 보호 경로를 건드리는 명령은 읽기 전용 명령 … 만 허용":** 글롭·프로세스 치환은 해석하지 않고, "읽기 전용" git이 파일을 씁니다.
3. **README 11절 "그 결과로 생성물이 바뀌면 커밋 때 web_check.py가 잡고, 프런트엔드 파일이 바뀌면 실행 후 스냅샷 비교가 잡습니다":** 확장 코드·hold.toml·pre-commit 설정은 대조 대상이 아니고, 스냅샷은 mtime 보존·백그라운드·크래시로 회피됩니다.
4. **README 11절 "둘 다 우회되더라도 무결성 검증 때문에 허락되지 않은 생성물은 만들 수 없습니다":** `--pin --tarball`이 파일에서 무결성 값을 계산해 hold.toml에 쓰므로 거짓입니다 (ADV2-02).
5. **README 5절 "lock까지 맞춰 꾸민 생성물도 잡힙니다":** npm 캐시가 있을 때만입니다 (ADV2-09).
6. **README 3절 #3·R17 "고정 버전·무결성의 패키지로만 쓴다":** 무결성은 설치 시점에만 확인하고, 실행 시 패키지는 검증하지 않습니다 (ADV2-03).
7. **README 4절 H9·ADR "실제 출력에서 확인한 ID만 기록":** 같은 명령의 다른 출력과 임의의 saved-to 파일도 섞입니다 (ADV2-10).
8. **ADR "`.claude/hold-web/`는 코어 보호 경로 안이라 통제 코드 자체가 보호된다(ADV-12)":** 두 훅 모두 우회되고 무결성 검사도 없습니다.
9. **README 7절 단계 3 "편집 도구든 Bash든" 레거시 검사:** `test/`·`examples/`·`generated/`·`*.min.js` 등은 조용히 검사에서 빠집니다 (ADV2-07).
10. **ADR "상태: 승인":** 규약 5의 재검토가 끝나지 않았습니다 (ADV2-13).

**고칠 순서 제안:** MWG 실행을 검증된 사본과 래퍼로 일원화하면(ADV2-03) ADV2-04·05·10이 함께 풀립니다. 보호 경로 판정을 "언급 금지(fail-closed) + 글롭 전개"로 바꾸고 확장 코드 해시를 대조하면(ADV2-01·02) 나머지 대부분이 닫힙니다.
