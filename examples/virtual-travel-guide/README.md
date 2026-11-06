# 가상 예제: 여행 가이드 앱 (HOLD Lite)

HOLD v0.1을 적용한 프로젝트의 모습을 보여 주는 **가상 예제**입니다. 등장하는 사람, 식사 조건, 외부 서비스는 모두 지어낸 것입니다.

이 예제에는 프로젝트 고유의 산출물만 들어 있습니다. 키트 파일(훅, 스크립트, 스킬)은 설치해서 씁니다.

```bash
python ../../kit/scripts/hold_init.py --target .    # 이미 있는 파일은 건너뜀
python scripts/check_views.py
python scripts/gen_views.py --check
```

## 보여 주는 것

| 단계 | 산출물 |
| --- | --- |
| 0 착수 | [이해관계자 정의서](docs/architecture/stakeholders.md), [컨텍스트 뷰](docs/architecture/views/context.md), [모듈 지도](docs/architecture/module-map.md) |
| 1 Plan | [intent.md](changes/20261108-dining/intent.md) — 열린 질문 "육수도 제외인가?" |
| 2 Design | [spec.md](changes/20261108-dining/spec.md) — 이해관계자 영향 표, 실패 분기가 있는 시퀀스 뷰 |
| 2.5 계약 | [app/contracts/travel.py](app/contracts/travel.py) — 사람의 답("육수도 제외")이 계약이 됨, [계약 클래스 뷰](docs/architecture/views/generated/contracts.md) |
| 3 Build | [plan.md](changes/20261108-dining/plan.md), [dining/api.py](app/modules/dining/api.py) |
| 4 Test | [골든 테스트](tests/golden/test_dining_golden.py) — 육수에 든 재료로 걸러지는지 |
