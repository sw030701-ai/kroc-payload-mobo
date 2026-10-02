# 실험 수정 1–4 이력

아래 번호는 사용자가 2026-10-01 확인한 구분이다: 수정 1=첫 물리모델 설정, 수정 2=400 상한 실험단계, 수정 3=800 상한 실험단계, 수정 4=현재 추가 진단. 날짜·Git commit·보존 보고서로 각 단계에 함께 수행한 변경과 실험을 연결했다. `[400,200,40]`과 `[800,400,80]`은 **탐색 상한**이며 실제 선택된 CT gain 벡터와 동일한 뜻이 아니다. 실패한 탐색이나 제약 위반도 삭제하지 않는다.

| 단계 | 날짜 / 계기 | 변경 | 결과와 판단 | 남은 한계 / 근거 |
|---|---|---|---|---|
| 수정 1 — 첫 물리모델 설정 | 2026-09-23 | RE35/GP42C 1-DOF 모델, full 5 s quintic, qLogNEHVI, 5×40회, bounds [200,100,20] | nominal min JT 평균 0.0031232 rad. CE가 zero PID로 퇴화하고 CT가 상한에 접함 | [원 보고서](../reports/archive/canonical-final-20260923/REPORT.md), GitHub `2f21d55` |
| 수정 2 — 대표 선택과 baseline 공정성 | 2026-09-24 | paired bounds 비교 후 [400,200,40]; zero+9 Sobol 초기점; 대표 선택만 JT≤0.05; CT/CB/CE 재선정; Exp.1/2 재실행 | bounds 비교 min JT 48.04% 감소. CE 퇴화 제거. HV/retention 보조지표화 | CT 상한, 2/3 kg에서 transfer가 local tracking보다 우수한 coverage 문제 남음. [보고서](../reports/archive/canonical-final-20260924-budget40/REPORT.md), `8618d58`–`87a9826` |
| 수정 3 — 800 bounds와 80회 | 2026-09-27 | 두 bounds 모두 80회로 400/800 비교; [800,400,80] 채택; 전체 Exp.1/2를 5×80회로 재실행 | nominal JT 50.51% 감소, CT JE 13.40% 증가. 동일 bounds 40→80회 JT 개선: 1/2/3 kg 1.05/10.63/17.43% | CT 5/5 상한; 3 kg CT 2/5 전류 초과(4.054780, 3.884308 A). Feasible heavy transfer 8/8이 local min JT보다 낮음. [보존 보고서](../reports/archive/canonical-final-20260927-budget80/REPORT.md), `5d05a2a`–`83e8883` |
| 수정 4 — bounds 고정, 탐색 충분성 보조 진단 | 2026-10-01 | main budget 80과 bounds [800,400,80] 유지. 2/3 kg만 기존 80→160 continuation; 40회 tracking-only constrained BO; 새 확인 seed 평가 | 80→160 min JT 개선: 2 kg 9.16%, 3 kg 26.93%. SO40 fresh confirmation에서 CT보다 좋은 feasible 후보 0/5씩. [진단 보고서](../reports/heavy-diagnostics-20261001/REPORT.md) | 5% 미만도 관측 예산 민감도만 판정. 전역 최적/실제 Pareto front 수렴을 주장하지 않음. 사전 protocol commit `37412f7` |

## 각 단계에 함께 수행한 변경과 실험

### 수정 1 — 첫 물리모델 설정

- 사용자 지정 RE35 24 V / GP42C 126:1 모델, eta=0.72, 모터·기어 관성 반영, 0.20 m/0.50 kg 링크, tip payload 1/2/3 kg을 canonical 기준으로 고정했다. 1-DOF simulation이며 실제 3-DOF 하드웨어 모델로 주장하지 않았다.
- Full 5 s quintic 0→60°(hold 없음), ±24 V clipping과 peak current 3.84 A feasibility, JT RMSE와 signed terminal JE를 정의했다. Train/selection/test seed를 분리했다.
- Pilot controller 및 RK4 16→32 substep 비교로 수치 적분을 점검했다. 초기 qNEHVI 시도는 NaN acquisition gradient로 중단되었고, 완료된 canonical 결과는 명시적으로 qLogNEHVI를 사용했다. 실패 run은 성공 결과와 구분해 보존했다.
- Experiment 1: payload별 독립 MOBO 5반복×40회, 총 600 candidate. Experiment 2: nominal 대표 CT/CB/CE와 전체 front를 retuning 없이 전이 평가. 표·그림·raw rollout·seed·manifest를 생성했다.
- 문제 발견: zero-PID CE 퇴화, CT 상한 접촉, payload별 zero-baseline 포함 불일치, HV 변동. 이 단계의 low-effort CE는 실용 controller가 아니므로 다음 단계에서 선택 규칙을 바꿨다.

### 수정 2 — [400,200,40] 상한 실험단계

- 1 kg에서 기존 [200,100,20]과 확대 [400,200,40]을 각각 5반복×40회로 비교했다(400 candidate). 이 sensitivity는 anchor 변경 전 조건을 맞춰 bounds 효과를 분리했다. Min JT 평균 48.04% 개선으로 확대를 채택했다.
- 모든 payload/repeat의 initial 10점에 zero PID 1개+Sobol 9개를 동일하게 포함했다. Zero anchor는 전체 Pareto front에 유지하되 대표 후보에서는 제외했다.
- 대표 선택에만 JT≤0.05 rad를 적용했다. CT=min JT, CE=criterion 내 min JE, CB=정규화 utopia distance 최소로 정의하고 tie/중복 역할 규칙을 저장했다. Full front 자체는 자르지 않았다.
- 확대 bounds와 anchor로 Experiment 1 전체 1/2/3 kg을 5×40회 재실행했다(600 candidate). 새 CT/CB/CE로 Experiment 2 전체를 retuning 없이 재실행하고 JT/JE, nominal-relative delta, feasible을 primary로 저장했다. HV/retention은 supplementary로 분리했다.
- Raw mean/seed/selection/frozen gain/provenance와 45개 대표 조건의 16→32 적분 검증을 수행했다. 같은 test seed 비교에서 heavy-payload local tracking coverage 부족을 기록했다. 원래 보고서·ZIP을 보존했다.

### 수정 3 — [800,400,80] 상한 실험단계

- 1 kg에서 [400,200,40]과 [800,400,80] 모두 5반복×80회로 비교했다(800 candidate). 전압 포화 비율과 최대 전류도 확인했다. Min JT 50.51% 개선과 CT JE 13.40% 증가를 함께 보고했다.
- Bounds 확대와 main budget 40→80을 적용해 Experiment 1 전체를 처음부터 5×3×80회 재실행했다(1,200 candidate). Zero anchor, practical 선택과 물리모델은 유지했다. 새 nominal CT/CB/CE를 고른 뒤 Experiment 2 전체를 재실행했다.
- 동일 새 bounds에서 첫 40개와 전체 80개 후보를 같은 selection seed로 비교했다. 1/2/3 kg min JT 개선은 1.05/10.63/17.43%로, bounds 효과와 budget 효과를 구분했다.
- Same-test comparison은 10개 heavy 조건 모두 transfer JT가 낮았지만, 3 kg CT 2개 조건이 infeasible이므로 feasible tracking-gap 근거는 8개로 제한했다. JT≤0.05 단독은 45/45, feasible+practical은 43/45였다. 전류 위반을 삭제하거나 retune하지 않았다.
- 테스트 34개, 데이터/provenance/적분 검증 680개, 전체 raw ZIP·수정 figure/table·선택 근거·해시를 저장하고 GitHub에 push했다. 이전 2개 단계 보고서는 별도 archive에 보존했다.

### 수정 4 — bounds 고정과 추가 진단

- Bounds는 [800,400,80]에서 중단하고 main Experiment 1/2의 80회 결과·대표 gains를 그대로 유지한다. 상한 접촉과 전류 위반을 근거로 전역 최적 또는 포화 수렴을 주장하지 않는다.
- 2/3 kg에만 5반복씩 MOBO80→160 continuation을 수행한다. 기존 80개 관측을 그대로 계승하고 조건당 80개를 추가한다(신규 800 candidate). 추가 평가는 main 예산에 섞지 않고 별도 비용으로 제시한다.
- 2/3 kg에만 40회×5반복의 constrained JT-only BO를 추가한다(신규 400 candidate). Zero+nominal CT+8 Sobol initial design으로 targeted warm-start 진단임을 명시한다. JE는 최적화하지 않지만 결과로 저장한다.
- MOBO80/MOBO160/SO40/기존 CT를 기존 test 10 seeds와 새 confirmation 10 seeds에서 동일하게 평가한다(800 held-out rollout). 선택 후 gains를 고정하며, 제약과 paired JT 차이/조건부 95% interval을 함께 보고한다.
- 이 단계의 결과·비교표·그림·검증·raw archive는 독립 진단 보고서에 저장하고 main report에는 연결된 보조 결과로만 추가한다. 별도의 Experiment 3, 1 kg MOBO 재탐색, CT/CB/CE 재선정 또는 전체 전이 실험 교체는 하지 않는다.

- 완료 결과: 두 payload 모두 평균 최소 JT 개선이 5% 이상이므로 80회 tracking coverage에 예산 민감도가 남는다. 160회 수렴도 입증되지 않았다. Fresh confirmation에서 기존 CT와 SO40은 3 kg에서 각각 3/5만 feasible하며, SO40에서 CT보다 좋은 feasible tracking 후보를 발견하지 못했다. 이는 더 좋은 PID의 부재를 뜻하지 않는다. 실험은 2026-10-01 완료, 최종 자료 정리는 2026-10-03 수행했다.

## 수정 4의 해석 원칙

- 전류 제약 위반은 공격적인 controller의 cross-payload 적용을 제한한다는 관측이다. 전압 포화가 성능 한계를 형성했다거나 constrained global optimum을 찾았다는 증거는 아니다.
- Bounds를 더 넓히지 않는 것은 연구 범위와 계산 예산에 대한 결정이다. 동일 예산에서 큰 도메인의 탐색 부담이 증가할 수 있으나 adaptive MOBO의 실제 탐색 밀도를 체적만으로 입증하지 않는다.
- 160회 결과는 80회 main result를 조용히 교체하지 않는 보조 진단이다. 신규 평가 80×2 payload×5 repeat=800개를 별도 비용으로 공개한다.
- SO40은 nominal CT를 초기점에 넣은 targeted diagnostic이다. 초기 정보가 다른 MOBO와 알고리즘 효율 우열을 주장하지 않는다. 한 후보도 못 찾으면 '존재하지 않는다'가 아니라 '이 예산에서 발견하지 못했다'고 쓴다.
- Min JT 비교는 같은 잡음 seed와 같은 물리적 제약에서 수행한다. Infeasible transfer의 낮은 JT를 feasible 성능 우위로 세지 않는다.
- 논문은 적은 평가 횟수에서 관측한 tracking–energy trade-off와 전이를 기술한다. 이 실험만으로 MOBO의 다른 optimizer 대비 sample efficiency 우위를 입증하지 않는다.

## 전 단계에 유지한 범위

Experiment 1/2 및 그 보조 진단만 수행한다. Canonical 모델은 1-DOF이며 3-DOF coupled/hardware 결과가 아니다. No hold, constant gear efficiency, no thermal/backlash/detailed driver model을 limitation으로 유지한다. 전류 3.84 A는 peak feasibility constraint이며 current clipping을 구현하지 않았다.

## Git 이력 차이

수정 2의 초기 로컬 commit `ef04ab6/17da804/5bc2af3/39c067d`는 GitHub 이력 위에 cherry-pick되어 `8618d58/1cc5ff5/3fe0d74/87a9826`으로 게시되었다. 보존 문서의 옛 로컬 commit 표기는 당시 provenance이므로 수정하지 않는다. 각 단계의 raw ZIP, frozen config, seeds, source hashes와 archive SHA256 inventory를 함께 확인한다.
