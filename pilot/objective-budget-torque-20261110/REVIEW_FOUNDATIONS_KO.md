# 실험·선행연구 검토: 최종 결과 전 고정한 해석 원칙

## 저장소와 이전 실패

실제 origin/main은 d18b00d2e7093cf5cb1b9cb10e9d70c4e3a9038e이다. GitHub fetch로 확인했다. 별도 worktree objective-budget-study와 pilot/objective-budget-torque-20261110 브랜치를 만들었다. 모든 추가 파일은 pilot/objective-budget-torque-20261110/ 아래이다. main 본실험 코드/결과, canonical model, sources/는 변경하지 않는다. 저장소 AGENTS.md는 기존 canonical model과 실험1/2 범위를 보존하도록 한다. 이번 사용자의 명시적 새 실험 지시에 따라 별도 benchmark를 추가하며 canonical final model로 부르지 않는다.

기존 pilot/objective-effort-20261110은 최종 실행이 성공한 실험이다. 초기 실패는 pymoo의 np.row_stack과 설치된 NumPy의 호환성 문제였고, 두 번째 실패는 rollout 수준 항등식을 여러 rollout의 평균 RMS에 적용한 집계 검사 오류였다. 이를 과학적 가설 실패와 혼동해서는 안 된다. 과학적 한계는 1DOF 전압 PID와 PUMA560 torque PID의 차이, 작은64회 예산/3seed, 서로 다른 후보 archive, 동일 gain 선택, 독립 검증 IAE 매칭 실패, CAV의 샘플링/노이즈 의존성이다. 최종 보고서에 384후보,1393rollouts, validation·test IAE 매칭을 통과한 서로 다른 제어기 비교3건만 남았다는 점이 명시되어 있다. 이 결과를 CAV 우월성으로 재사용하지 않는다.

환경은 기존 로컬 venv의 Python3.13 및 requirements.txt의 실제 고정 버전을 사용했다. 전체 freeze도 보관했다. 저장소 주 의존성 BoTorch/Torch는 이번 독립 GA 실험에는 사용하지 않는다. 새 코드는 설치된 numba에서 float(bool)이 지원되지 않아 컴파일 단계에서 한 번 실패했다. 조건식을 1./0.으로 바꾸어 수정했고, 과학적 설정 변경이나 완료된 후보 삭제는 없었다. 로그 보존.

## 원문으로 확인한 사실과 재현 범위

- [Eltayeb et al.,2024](https://www.mdpi.com/2673-4052/5/3/14): 원문 HTML의 식1,5–8과 표2–5를 직접 확인했다. 2DOF, GA, IAE/ISE/ITAE/ITSE 비교는 맞다. l1=.2m,l2=.1m,m1=10kg,m2=5kg,g=9.81. GA population100/generations100, crossover.8/mutation.01, Kp0–200/Ki0–50/Kd0–10이다. 초기[0,0],목표[1,.5]rad. 두 번째 시나리오는 m2=6kg와 Coulomb마찰50을 함께 바꾼다. 그 교란을 이번 실험에는 도입하지 않았다.
- 인쇄된 모델의 C2는 dq2²이지만, 같은 질량행렬의 표준 Lagrange 모델은 dq1²을 요구한다. 중력항의 cos(q1)cos(q2) 역시 cos(q1+q2)와 다르며 혼합 편미분 대칭성을 깨뜨린다. 이는 본 검증에서 도출한 수학적 지적이며 저자의 실제 Simulink 코드에 같은 오류가 있었다고 단정하지 않는다. 원문의 ITSE 설명 중 earlier-error 강조 문장도 식 t*e²와 일치하지 않는다. 늦은 오차 가중이라는 수식을 기준으로 해석한다. 정확한 solver/미분 kick/seed/관절 합산과 코드를 확보하지 못해 표7–9의 수치 재현을 주장할 수 없다. 표5 gain을 보정 모델에 넣은 sanity 결과만 별도 저장했다.
- [Massoud & Libby,2024](https://doi.org/10.1109/ACCESS.2024.3480834): 저자 업로드 [원문 전문 텍스트](https://www.researchgate.net/publication/384914809_Comparative_Analysis_of_Evolutionary_Algorithms_for_PID_Controller_Optimization_in_Pneumatic_Soft_Robotic_Systems_A_Simulation_and_Experimental_Study)의 II–VI절·Algorithm5를 확인했다. GA/PSO/SA/SBO×4오차적분 목적함수, PWM valve 압력PID이다. 50초 측정데이터로 nonlinear System Identification 모델을 구성하고12PSI에서 평가한다. 관절 토크 PID 원문이 아니다. 원문 표 이미지의 세부 gains·수치와 식별 모델 파일은 회수하지 못했다(PDF403). 이전 대화의 표6 PSO 숫자를 이번 정량 근거로 재사용하지 않는다.
- [Azeez et al.,2023](https://www.nature.com/articles/s41598-023-37895-3.pdf): 원문 PDF를 실제 다운로드·추출해 표1–2, 식24–33, optimization절을 확인했다. 3DOF 각1kg/.5m/Izz=.020833, ABC/MGABC colony20/40iterations, RK4 .001s,5s,관절 torque±200Nm. LBF와 IAE/ISE/ITAE/MAE/MRSE를 비교한다. ITSE까지 동일한4종 비교라는 이전의 단순화는 수정한다. 데이터는 요청 시 제공이라고 되어 있어 완전한 독립 재현을 완료한 것은 아니다.
- [Zidan et al.,2018](https://www.scitepress.org/Papers/2018/68998/68998.pdf): publisher PDF를 다시 받았으며, /mnt/data/68998.pdf 자체는 현재 환경에 없지만 이전 첨부 기록과 SHA256 344b7ff021a4bf133014babae7521a816038a2caf99d9b8e055ab21ff2585d82가 정확히 일치했다. p241 식1/2는 IAE와 토크 차이 절댓값 합 CAV이다. PUMA560의 첫3관절,4초,40population/100iterations/30repeats. 최대 오차·토크 위반 시 큰 벌점을 주는 sudden-death 처리이며, saturation clipping과는 다른 문제다. CAV 명칭에 variance가 들어가도 식은 total variation이다.

## 왜 이 설계인가

원문 재현이 가능한 척하기보다, 물리 파라미터와 탐색범위·training step을 맞춘 별도 point-mass 모델을 사용했다. 질량행렬 양의 정부호, 운동에너지 항등식, 중력 potential gradient, 정적 평형과 포화를 검증한다. 마찰·모델오차·payload를 동시에 바꾸지 않아 objective×actuator 효과의 해석을 단순화한다. 이는 현실의 강인성 검증을 대신하지 않는다.

토크 한계 [70,10]/[42,6]Nm는 전역 정적 중력 상한[34.335,4.905]Nm의 약2배/1.2배를 반올림했다. 결과를 보고 순위 반전을 만들기 위해 정하지 않았다. 두 조건 모두 모든 자세에서 정지 토크 여유는 있지만 가속·감속 여유는 다르다. 특정 상용 actuator/gearbox 사양이 아니므로 실용 하드웨어 토크 한계라고 주장하지 않는다. 이 설계에 있는 torque headroom 차이는 제어기와 동역학의 교호작용을 조사하기 위한 것이다. 무한 actuator는 원문 gain sanity에만 사용한다.

IAE(rad s),ISE(rad² s),ITAE(rad s²),ITSE(rad² s²)는 단위와 수치 스케일이 달라 원시 최솟값끼리 우열을 비교할 수 없다. 같은 horizon에서 ISE와 RMSE는 단조 대응하지만 그 관계는 training 궤적에 한정된다. IAE는 큰오차·작은오차를 선형 누적하고 ISE는 큰오차를 더 강조한다. 시간 가중은 후반 오차를 강조한다. 관절별 크기 정규화 없이 동일 가중 합을 쓰므로 목표 진폭이 큰 관절의 영향이 더 클 수 있다. GA는 토너먼트 순위 선택이라 목적함수에 양의 상수를 곱한 것 자체는 탐색 순서를 바꾸지 않는다. 실제 차이는 오차의 시간·크기 구조에서 나와야 한다.

동일 seed의 초기32후보를 모든 목적함수/토크 조건에 정확히 공유하고, 이후 공통 RNG stream을 쓰되 선택된 부모가 달라지면 후보도 달라진다. 동일 후보 전체를 강제한 random search를 GA라고 부르지 않는다. 신규 평가·실패·중복 후보를 모두 예산에 센다. checkpoint는 같은1024회 실행의 prefix이며 서로 독립 실험이 아니다. 32회는 초기 모집단 성능,128–1024는 점진적 GA 탐색 성능이다. 같은 조건에서 optimizer seed가 독립 단위이며 trajectory를 반복수로 부풀리지 않는다.

train[1,.5]rad 계단, held-out[.8,.7]rad 계단, held-out[1.2,.3]rad/2초 quintic 이동으로 고정했다. 새로운 궤적에서 좋아지는지 확인하되 소수 궤적 전체에 대한 광범위한 일반화를 주장하지 않는다. smooth 이동의 settling·overshoot는 공통 step-response 정의가 부적절하므로 NaN으로 두고 RMSE/IAE를 비교한다. 수치 실패와 terminal2관절오차≤.02rad의 tracking feasibility를 구분한다. terminal feasibility는 전구간 safety 제약이나 수학적 안정성 증명이 아니다.

95% CI는 optimizer seed 단위 paired bootstrap10000회이다. 모든6목적함수쌍을 저장하고 primary IAE–ITAE 대비를 명확히 한다. sign-flip p의 대칭성 가정과 작은n의 한계를 인정하며, family별6비교 Holm값도 저장한다. CI는 다중비교 보정하지 않은 기술적 구간이고 여러 budget/trajectory 전체에 대한 familywise 보장은 아니다. .05/.1rad RMSE 달성 예산은 결과 요약용 추가 기술통계이며 사전 채택 기준이 아니다. 관측 checkpoint에서 최초 달성한 값일 뿐 정확한 최소 평가 횟수는 아니다.

## 4페이지 KRoC에서 허용되는 기여 주장

조건을 붙였다는 것만으로는 약하다. 기존 연구에 objective 비교와 torque constraint가 이미 있다. 유용한 기여는 공정한 예산으로 반복한 목적함수 선택의 조건부 효과, held-out성능과 불확실성, 실용적인 실패/포화 기록, 모델 일관성을 검증한 공개 artifact이다. 다만 재현성 개선은 방법론적 장점이며 단독으로 새 제어 기법을 제안한 것과 같지 않다. 모든 로봇에서 동일한 추천을 도출했다거나 최신 모든 논문에 없는 최초 결과라고 주장하지 않는다. 본 문헌 점검은 핵심4편을 확인한 것이며 체계적 전체 문헌조사가 아니다.

최종 판정은 결과를 보고 별도 REPORT_KO.md에 기록한다. 증거가 약하면 새 objective를 억지로 골라 유리한 결과를 만드는 pivot을 하지 않고 보류/축소를 권한다. Torque-aware objective는 오차와 토크의 명시적 운용 tradeoff가 필요한 별도 후속 질문으로 삼아야 하며, 이번4종 실험의 음성 결과를 숨기는 대체 결과가 되어서는 안 된다.
