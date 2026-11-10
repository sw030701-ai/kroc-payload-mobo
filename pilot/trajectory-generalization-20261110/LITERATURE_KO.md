# 원문 재조사와 피벗의 신규성 평가 — 2026-11-10

이번 세션에서 publisher HTML 또는 저자 원문을 다시 열었다. 선행연구의 수치와 우리 수치를 직접 나눠 개선율을 만들지 않는다. 로봇·제어 구조·목표·예산이 달라 공통 baseline이 아니기 때문이다. PR2의 REVIEW_FOUNDATIONS_KO.md에는 이전 선택적 문헌검토와 원문 gain sanity가 보존되어 있다.

|문헌·원문 접근|직접 확인한 위치와 중복|우리 실험과 차이 / 금지할 주장|
|---|---|---|
|[Eltayeb et al. 2024](https://www.mdpi.com/2673-4052/5/3/14), 전체 HTML|식1의 M,C,G, 6.1절, 표2–5. 2DOF, 4오차적분, GA, paper bounds [200,50,10], 초기0와 목표[1,.5]. GA pop100/generation100/crossover.8/mutation.01.|우리 모델은 인쇄 C/G를 보정한 point-mass 동역학, pop32/토너먼트/좌표당1/6 Gaussian mutation, sampled PI-D와 antiwindup. 같은 파라미터만으로 완전 재현 아님. 원문 표 대비 성능 향상을 주장할 수 없음.|
|[Joyo et al. 2019](https://www.mdpi.com/2079-9292/8/8/826), 이번에는 전체 HTML 접근 성공|서론의4objective, 5절의 두 linearized subsystem independent control with saturation limits, step input, PSO/ABC; hardware RAX-1 실험도 보고.|‘포화 있는2관절에서4목적함수 비교’는 신규성이 낮음. 우리 것은 coupled nonlinear model·GA·rollout예산·새궤적·범위민감도. 이것이 충분한 논문 기여인지는 별도 판단 필요.|
|[Roveda, Forgione & Piga 2020 저자 원문](https://ipg.idsia.ch/preprints/roveda2020a.pdf),38p PDF 텍스트; [정식 DOI](https://doi.org/10.1016/j.conengprac.2020.104488)|5.2의 variable-frequency sinusoidal/Cartesian 경로,5.6과Fig11(p31): 한 자극궤적에서 튜닝한 제어기를 다른 두궤적에 전이. 25parameters/7DOF Franka, feedback linearization+feedforward+PID, BO.|궤적선택을 통한 generalization 자체도 기존 연구. 우리 혼합학습은 새로운 일반화 방법이 아니라 제한예산 내 allocation의 독립 수치 비교. 원문 real hardware 및 최대오차와 우리2DOF RMSE는 직접비교 불가.|
|[Navarro-Cabrera et al. 2023 v1](https://arxiv.org/html/2309.08988),전체 HTML|III–IV절: NSGA-II torquePD, Kuka iiwa LBR7DOF Gazebo, generic vs specific trajectory tuning, trajectory duration3–6초와 교차시험,각5회 반복.|계단→궤적 일반화만으로 최초성 주장 금지. v1은 시뮬레이션이며 실물은 future work; 2025 관련 후속 제목은 검색됐지만 전문확인 전 수치를 재사용하지 않음.|

## 엄격한 귀결

목적함수4개를 비교하거나 saturation/budget를 붙이는 것만으로 신규기법이 되지 않는다. ‘학습에 smooth를 추가하면 smooth test가 좋아진다’도 예상 가능한 현상이다. 남길 수 있는 기여 후보는 **동일 물리 시뮬레이터 실행비용 아래 목적함수 선택보다 학습궤적·탐색범위가 결과 해석에 미치는 영향을 직접 대비하고, 실패/부정적 결과까지 재현 가능하게 공개하는 제한된 empirical finding**이다. 이 조합의 최초성을 입증하는 체계적 문헌조사는 완료하지 않았다.

새 simulator는 PR2의 core를 복사하고 새 target/duration만 추가했다. 새 모델을 canonical final model로 부르지 않는다. 문헌과 동일 solver·code·PID구현·seed를 얻지 못했으므로 replication-success/새 알고리즘 우월성/실물성능 주장은 배제한다. 이 제한은 불리한 결과를 숨기기 위한 것이 아니라 비교 가능한 범위를 지키기 위한 것이다.
