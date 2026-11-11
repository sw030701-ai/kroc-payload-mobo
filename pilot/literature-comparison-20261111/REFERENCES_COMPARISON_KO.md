# 선행연구 원문 비교와 재현 범위

2026-11-11 확인. PDF 해시는 `references/downloaded_originals.json`. `references/`의 발췌 위치·원문 링크와 아래 차이를 함께 본다. 선택적 문헌 감사이며 모든 최신 연구를 망라한 최초성 조사는 아니다.

|원문|직접 확인한 위치|이번 비교와 일치|달라지는 것·허용되지 않는 주장|
|---|---|---|---|
|[Eltayeb et al., Automation 5(3),230–245,2024](https://doi.org/10.3390/automation5030014),16p PDF|p233 식1, p237 표2/3, p238 표4/5, scenario2|2DOF 물리값 l=.2/.1,m=10/5,g=9.81; 4오차적분; 표4 gain범위; 표5 PID gain4세트 직접 전사·렌더링 대조|원문은 PID–FO-PID와 GA100×100, 계단 및 질량+마찰 변화. 이번은 보정한 동역학,32×8 GA,PI-D,중력FF,conditional AW,새 궤적,질량만 변화. 표5 gain-transfer와 같은 예산의4objective 재튜닝만 직접 비교 가능. 원문 표의 개선율을 재현했다고 주장하지 않는다.|
|[Azeez et al., Scientific Reports13,11164,2023](https://doi.org/10.1038/s41598-023-37895-3),19p PDF|p9 optimizer설정/표2, p10 식25–32, payload불확실성절|오차적분·궤적추종·질량불확실성·torque clipping이 이미 연구됐음을 확인|3DOF Simscape와 ABC/MGABC·Lyapunov objective이며 이 실험의2DOF GA와 다르다. MGABC나LBF를 구현한 baseline이라고 부르지 않는다. 이 논문보다 우월하다는 수치 주장은 하지 않는다.|
|[Mishra et al., arXiv2601.18639v3](https://arxiv.org/pdf/2601.18639v3),15p PDF|p4 식8, p5–6 식21/Algorithm1, p9 표6, p11 표7|포화·노력·overshoot 벌점을 함께 평가하는 설계를 PEN에 이식|원문은 first/second-order actuator,robust median,BO와 certification,back-calculation. 이번은 coupled2DOF,GA,2train 평균,normalized effort,conditional AW. HC-SBO를 재현한 것이 아니다. PDF 표6의IAE .687→.470과 abs page .843→.430이 달라 PDF해시를 기준으로 삼는다. 게재 대기 문구는 peer-review 완료 증거로 사용하지 않는다.|
|[Zhou et al., arXiv2603.12099v2 / T-MRB2026](https://arxiv.org/html/2603.12099v2)|원문 모델·중력보상·실물평가절, 표II|중력보상과 feedforward가 제어성능에 큰 영향을 준다는 선행사례|dVRK-Si 실물 모델식별 연구이며 우리 synthetic2DOF를 검증한 것이 아니다. 원문의실물 개선율을 본 연구 성능으로 옮기지 않는다. 현재 원문은 accepted/journal reference를 명시해 단순미심사본으로 묶지 않는다.|
|[Daulton et al., NeurIPS2021](https://arxiv.org/html/2105.08195v2), [Ament et al., NeurIPS2023](https://arxiv.org/html/2310.20708v3)|NEHVI정의절과 LogEI 수치안정성 원문|main의 MOBO/Log계열 선택 근거|이번 GA 실험은 MOBO의성능·새 획득함수를검증하지 않는다. main의1DOF 논문과후속2DOF 주제를구분한다.|

## Eltayeb 인쇄 동역학과 보정 모델

원문 식1은 두 번째 Coriolis 성분에 dq2², 중력에 cos(q1)cos(q2)를 인쇄한다. 같은 질량행렬의 표준 상대관절각 Lagrange 모델은 C2=m2*l1*l2*sin(q2)*dq1²와 G의 cos(q1+q2)를 요구한다. 인쇄 G에서 dG1/dq2와 dG2/dq1도 일반적으로 같지 않다. 이는 수학적 일관성에 대한 이번 검토의 도출이며 저자 Simulink 코드도 오류였다고 단정하지 않는다. 이번 집중질량 모델은 보정식을 사용하고 강체 모델은 COM·관성을 별도로 정의했다.

그 때문에 같은 l,m,g 및 gain을 사용해도 원문 모델 자체의 수치 재현은 아니다. 표5 gain이 우리 조건에서 나빠지더라도 저자 방법을 반박한 것이 아니라 **제어 구조·모델·궤적 전이의 실패**다. 정확 재현에는 저자 코드·solver·미분 kick·joint objective 합산·seed의 복구가 필요하다.

## 비교 공정성의 경계

동일 예산 주장은 이번5개 재튜닝 방법에만 적용한다. 모두256후보×2train=512rollout,공유초기모집단,동일모델·limit·train·test이다. 고정된 원문 gain은 튜닝0회로 평가한 배포 기준이다. 원문 GA의100×100 비용을256으로 줄였으므로 알고리즘간 우월성이나 원문보다 비용절감했다고 주장하지 않는다.

원문 벌점식의 기호와 수식을 참고해 PEN을 정의했지만 관절별 토크를 limit로 정규화했고2train 평균을 사용한다. 이는 Nm 단위 raw effort를 그대로 더할 때 생기는 스케일 차이를 피하기 위한 **사전 고정한 실험 선택**이다. 새 최적화기나 새로운 강인제어법이라는 주장은 하지 않는다. PEN이 포화를 줄이더라도 추종오차를 키우면 그 교환관계를 부정적 결과로 포함한다.

## main 핵심 선행연구의 원문 접근 보완

[Gulbahce, Physica Scripta101,175203,2026](https://doi.org/10.1088/1402-4896/ae6147)는 publisher PDF가 timeout 후 인증HTML로 실패했다. 이후 [ResearchGate의 publisher 제공 전문](https://www.researchgate.net/publication/403940253_Comparative_evaluation_of_GA_and_PSO_for_multi-objective_trajectory_control_of_a_3-DOF_robot_under_payload_variations)에서 본문을 확보해2–4절,식16/19,표1–4를 대조했다. 따라서 **원문 전문 HTML 감사는 수행,완전한 PDF 보존은 실패**로 구분한다.

원문은3DOF 집중질량·5초·±500Nm,20population×20iteration=400평가를20seed 반복한다. 2초에payload를0→1/2/3kg로 증가시킨다. 목적은 추종제곱오차+torque제곱적분(가중치1e-5)+종단오차(가중치100)의 **단일 가중합**이다. main의2목적Pareto·signed V*i 전기에너지와 정의가 다르다. 원문의 control energy는 torque² 적분이며 joule 단자에너지와 동일하지 않다. 본문이 multi-objective라고 표현하더라도 explicit Pareto 연구와 같은 의미로 단순화하지 않는다. 원문400평가와main80평가,20반복과5반복의 수치를 직접 나눠 우월성을 주장할 수 없다. nominal tuning 후payload전이 자체도 이미 선행연구에 있으므로 최초기여가 아니다.

main의차별점 후보는 전기에너지·전류 feasibility·명시적Pareto와대표선정 규칙이지만,물리모델 식별 및 동일benchmark baseline 검증 없이 충분한 신규성이라고 확정할 수 없다. 이번2DOF실험도 Gulbahce의3DOF GA/PSO를 구현하지 않아 그 논문의성능 비교를 대신하지 않는다.
