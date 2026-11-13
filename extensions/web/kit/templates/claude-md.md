<!-- hold-web:start (extensions/web/install.py 가 넣은 절. 다시 설치하면 이 사이가 바뀝니다) -->
## 웹 프런트엔드 — HOLD 웹 확장 web-0.1

- HTML·CSS·클라이언트 JS 작업은 `modern-web-guidance` skill로 가이드를 먼저 찾는다. 실행은 **`python .claude/hold-web/mwg.py <search|retrieve|list> …`로만** 한다 (사람이 고정·검증한 사본, 텔레메트리 없음). `npx`·`npm`·`node`로 직접 부르지 않는다 (R17. 훅이 설치되어 있으면 막는다).
- 브라우저 지원 기준과 대체 동작 정책의 원본은 `hold.toml`의 `[web]`이다. 이 파일이나 `AGENTS.md`, `.mwgrc`에 지원 정책을 쓰지 않는다. 바꿔야 한다고 판단되면 멈추고 보고한다 (R14).
- 가이드가 대체 전략을 둘 이상 제시하면 고르지 말고 spec.md `## 계약 질문 목록`에 `(웹)` 질문으로 남긴다 (R18).
- spec.md `## 참조 가이드`에 retrieve한 가이드를 `mwg:<id>`로 적는다. 쓰지 않았으면 `생략: <이유>` (R16).
- 프런트엔드 파일을 바꾼 뒤 커밋 전에 `python .claude/hold-web/web_scan.py`로 레거시 패턴을 검사한다 (훅이 있으면 자동). 오탐이라고 판단되면 코드를 비틀지 말고 보고한다 (R15).
- 검사가 실패하면 고치거나 보고한다. `--no-verify`나 `core.hooksPath`로 pre-commit을 건너뛰지 않는다.
<!-- hold-web:end -->
