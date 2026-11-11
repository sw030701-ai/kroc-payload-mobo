# 실행 전 고정 프로토콜 (2026-11-11)

이 연구는 Canonical Final Model을 대체하지 않는 별도 2-DOF benchmark이다. 기존 데이터·gain을 신규 최적화로 세지 않는다. 이전 대화의 stage ZIP은 확보 전까지 미검증이다.

## 독립 신규 실험 4개

E1: 끝점 집중질량 모델, 중력 보상 모델 m2=5kg, 실제 m2=5kg.
E2: 같은 모델, 보상 m2=5kg, 실제 m2=6kg(+20%).
E3: 균일 강체 링크 모델, 보상 m2=5kg, 실제 m2=5kg.
E4: 같은 강체 모델, 보상 m2=5kg, 실제 m2=6kg(+20%).

모든 l1=.2m,l2=.1m,m1=10kg,g=9.81. 집중질량은 r1=l1,r2=l2,I1=I2=0; 강체는 r=l/2,I=m*l²/12. 두 모델은 서로 다른 질량분포 가정이며 서로 다른 실물 로봇으로 해석하지 않는다. 실제 질량은 M,C,G 모두에 적용한다. 보상에는 nominal m2만 사용한다. 마찰은 0으로 고정해 질량오차와 분리한다.

각 실험의 새 최적화 seed는 각각 110101–110108,110201–110208,110301–110308,110401–110408이다. 공개된 이전 seed 101–103,201–210,301–308,501–504,601–605와 겹치지 않는다. 미확보 ZIP 전체와의 중복 여부는 확인할 수 없다.

## 공통 비교

방법: IAE, ISE, ITAE, ITSE, PEN(IAE+포화/노력/overshoot 벌점). 각 방법에 동일 GA 256후보, 모집단32, 8세대, 2개 train rollout/후보 =512 simulator calls. 같은 실험·seed에서 초기 모집단과 RNG stream 공유. 실패·중복도 예산에 포함. 끝까지 모든 평가를 실행하며 test를 이용한 gain 선택·조건 변경은 금지한다.

GA: 2-way tournament, uniform crossover .8, 좌표별 mutation 1/6, 표준편차 .1 normalized, elitism은 incumbent를 다음 모집단 첫 원소로 보존. gain 범위 Eltayeb 표4의 [200,50,10]×2. best는 train objective만으로 선택.

Train: [1,.5] 계단과 [1.2,.3] 2초 quintic, 10초 horizon.
Test: [.7,.6] 계단, [1.1,.4] .7초 quintic, [0.6sin(.8t),0.4sin(1.1t)] 연속 궤적. 모두 10초, train과 분리. 모든 방법과 논문 gain에 동일 test.

각 test는 nominal torque와 tight torque에서 교차 실행한다. nominal torque는 해당 모델 nominal 전체 중력 상한의 2배, tight는 1.25배다. 이 값은 하드웨어 사양이 아닌 연구 조건이다. 학습은 tight에서만 실행. 총 3 tasks×2 limits=6 test/제어기. 실제 saturation duty를 보고하고 0% 조건은 비활성 대조군으로 해석한다. 정적 여유가 있어도 동적 가속에서 포화가 가능하며 step이 활성 조건을 제공한다. 시험 결과를 보고 torque limit를 조정하지 않는다.

제어: u=Kp e+Ki z-Kd qdot+Ghat(q), conditional integration antiwindup, feedforward를 포함한 전체 명령에 torque clip. dt=.002s, RK4 2 substeps, ZOH. 미분 on measurement, 정확 속도 상태 사용. 센서 노이즈·지연은 도입하지 않아 해당 현실성은 주장하지 않는다.

PEN은 Mishra v3 식21의 포화·노력 벌점 설계를 동일 benchmark에 이식한 비교군이며 원문 BO/인증/antiwindup 구현 재현이 아니다. J=IAE/(2T)+max(0,OS_percent-5)^2+5*sat_duty²+0.5*mean((applied/limit)²). 두 train rollout 평균. Nm 입력을 dimensionless 노력으로 정규화하고 mean을 사용하므로 원문과 달라진다. 4오차적분도 두 train 합의 평균.

Eltayeb 표5의 4개 고정 PID gain을 별도 실행한다. 동일 feedforward/antiwindup/모델/시험으로 이식한 gain-transfer baseline이며, 원문 전체 제어기를 재현한 것이 아니다. 0 신규 tuning budget이므로 GA와 동일 비용에서 알고리즘 우월성을 뜻하지 않는다. 원문 수치와 우리 수치를 나눠 개선율을 만들지 않는다.

## 지표와 추론

공통 test 지표: RMSE=sqrt(sum(e1²+e2²)dt/(2T)), IAE=sum(|e1|+|e2|)dt, applied torque RMS=sqrt(mean(tau1²+tau2²)/2), joint-time saturation fraction, tracking feasibility(유한 상태 및 마지막 sample 두 오차≤.02rad), numerical success. 추가 step overshoot와 2% absolute .02rad settling. 실패를 삭제하지 않고 RMSE=20rad,IAE=400rad*s,effort=limit RMS,sat=1,feasible=0로 보수적 대체하고 failure flag와 종료시각 보존.

Primary: tight에서 3개 test 평균 RMSE의 ISE−IAE, PEN−IAE, 각각 E1–E4. Independent optimizer seed n=8 단위 paired bootstrap20000회(95% percentile CI). 같은 seed의 3궤적은 독립 n으로 세지 않는다. 8개 primary sign-flip p는 Holm 보정. CI는 보정하지 않은 기술적 구간. 모든 지표 CI도 seed 평균으로 저장. 고정 baseline의 CI는 동일 deterministic rollout 반복으로 만들지 않는다(NA). 부정적 결과·상충 지표·포화0%를 명시한다.

모델 질량행렬 SPD, potential gradient, Coriolis 에너지 항등식, exact static compensation, torque clipping, 독립 scipy 적분과 RK4 일치 및 제어 dt 고정 substep refinement를 검증한다. 네 실험은 별도 신규 최적화 실행이다. refinement/통계 재분석을 5번째 신규 실험으로 세지 않는다.
