# 결론: 선택 제어기는 달라질 수 있지만, 일관된 개선 근거는 부족하다

최신 GitHub main(d18b00d)에서 별도 브랜치 `pilot/objective-effort-20261110`를 만들고 실제 시뮬레이션을 실행했다. 본실험·기존 baseline·archive는 변경하지 않았다. 실행 장소는 로컬 계산 환경이며 GitHub Actions 또는 하드웨어에서 실행한 것이 아니다.

## 실제 실행 규모와 검증

2 목적함수 × NSGA-II × 3 optimizer seeds × 64 후보 = **384 candidate evaluations**. 각 후보 2 공통 학습 noise rollouts이므로 학습 768회, feasible 후보의 독립 검증 508회, 최종 시험/고정 gain sanity 117회, 총 1,393 rollouts이다. 최초 구현 오류를 수정한 후 같은 조건으로 전체 재실행했으며, 실패 로그도 보존했다. 이 수치는 최종 성공 실행의 예산이며 재실행 비용은 별도다.

각 arm에서 seed 731/732/733의 학습 feasible 후보는 42/40/45개(각 64개 중)였다. 나머지는 제외하지 않고 원시 CSV에 남겼다. 동일 seed의 초기 16개 후보는 정확히 같았고, 이후 48개 중 같은 순서의 동일 후보는 12/32/32개였다. 즉 optimizer가 실제로 작동했고 목적함수 변경 후 탐색이 일부 달라졌다. 후보 수가 같다는 것이 후보 gain이 모두 같다는 뜻은 아니다.

공통 IAE target .005/.010/.025 rad s와 ±10% 허용구간을 적용했다. .005는 양쪽에 후보가 있는 seed가 없어 비교 불가였다. .010에서는 3개 seed 모두 validation IAE 5% 매칭에 성공했지만, seed 732/733은 두 arm이 **같은 gain**을 선택했다. .025에서는 seed 732만 validation 매칭을 통과했다. 전체 선택 6쌍 중 validation 통과는 4쌍이다.

총 18개 쌍×시험궤적 비교 중 validation과 시험 평균 IAE 모두 5% 매칭이며 양쪽 feasible인 것은 9개다. 이 중 6개는 동일 gain이므로 차이가 0이고, 서로 다른 gain으로 비교 가능한 것은 3개뿐이다. 같은 seed의 여러 궤적은 독립 optimizer 반복이 아니다. 시험 평균이 맞아도 개별 noise 실현에서 안 맞는 경우가 있다(seed731/.010/reverse45: 3개 중 2개만 매칭). `paired_test_noise.csv`에 모두 남겼다.

## 실제 수치: 공통 독립 nominal 시험

각 값은 동일 시험 noise seed 3개의 산술평균이다. Peak torque도 각 rollout peak의 평균이며 최악값은 raw_rollouts.csv에 있다. A=IAE+CAV, B=IAE+토크 제곱 적분.

| seed / IAE target | arm | IAE [rad s] | CAV [N m] | torque RMS [N m] | peak torque [N m] | ∫τ²dt [N²m²s] | feasibility |
|---|---|---:|---:|---:|---:|---:|---|
|731 / .010|A|0.0104992|2301.9852|1.44488|3.38972|10.43833|3/3|
|731 / .010|B|0.0103220|3231.8828|1.50328|3.95984|11.29923|3/3|
|732 / .025|A|0.0239922|1739.5583|1.41283|3.05213|9.98044|3/3|
|732 / .025|B|0.0230154|3561.9095|1.52838|4.12449|11.67973|3/3|
|고정 gain [70,30,5]|sanity|0.089610|2530.4739|1.44154|3.51206|10.39014|3/3|

표의 최적화 쌍은 validation과 nominal test IAE 매칭을 모두 통과했다(시험 IAE 차이 각각 1.70%, 4.16%). 이 두 예에서 B의 RMS·peak·토크 제곱 적분은 오히려 더 컸다. 이는 **작은 탐색 예산과 선택·일반화 오차가 있는 관측**이며, CAV 목적함수가 본질적으로 우월하다는 근거가 아니다. 서로 다른 탐색 archive에서 같은 허용구간 내 최저 own-effort를 선택한 결과로, global optimum 또는 정확히 같은 IAE의 counterfactual 비교가 아니다.

seed731/.010은 reverse45에서도 평균 IAE 차이 4.81%로 매칭되지만 short45에서는 7.35%로 실패했다. seed732/.025는 short45/reverse45에서 매칭에 실패했다. 반대로 실패한 validation 쌍에서 시험 IAE만 맞은 사례는 근거 집계에서 제외했다. 좋은 결과만 남기지 않고 모든 비교를 paired_comparison.csv와 그림에 표시했다.

39개 선택 제어기×궤적 요약(117 rollouts)은 모두 inherited 제약을 통과했다. 고정 gain은 세 궤적 모두 feasible이지만 최적화 제어기와 IAE가 다르므로 낮은 토크 수치만으로 우열을 비교할 수 없다. train-feasible 여부와 test-feasible 여부를 혼동하지 않았다.

## 원논문과 해석의 한계

Zidan et al.(2018), p.241 식(1)(2)의 IAE=Σ|e|ΔT, CAV=Σ|Δτ|를 scalar 지표로 적용했다. **PUMA560 재현이 아니다.** 기존 1-DOF voltage PID에서 τ=ηNKt i로 구한 출력축 전자기 토크를 사용했다. 원논문의 torque-command PID, multi-joint model, error/oscillation 제약과 다르며 원논문 수치와 직접 비교할 수 없다.

전기 에너지, 기계적 일, 하드웨어 수명/성능 향상을 주장하지 않는다. 토크 제곱 적분은 여기서 제어 노력 지표일 뿐이다. 같은 duration의 RMS와 ∫τ²dt는 종속 지표다. CSV 요약은 RMS의 평균이므로 요약 평균 RMS를 제곱해 요약 평균 적분과 같아야 한다고 검사하면 안 된다. 개별 rollout에서 항등식을 검사했다.

CAV는 statistical variance가 아니라 total variation이며 noise와 샘플 간격에 민감하다. dt=1ms 출력-grid 토크로 계산했고 integration은 16 substeps이며, fast electrical dynamics의 substep 토크 CAV나 grid-convergence를 확인한 실험이 아니다. 공통 dt와 noise를 유지한 내부 비교만 가능하다. 고정된 물리 파라미터·current threshold는 저장소의 설계/사용자 제공값이며 실측 식별값이 아니다.

**판정:** 목적함수 변경이 일부 탐색·gain·시험 수치에 차이를 만들었다. 그러나 3 seed의 작은 예산에서 동일 gain 선택과 IAE 매칭 실패가 섞였고, 일관된 matched-IAE 성능 개선은 확인하지 못했다. 이 결과를 최종 논문의 개선 효과 또는 새 알고리즘의 우월성으로 쓰기에는 부족하다. 다음 단계는 이 설계를 동결한 채 더 큰 예산/더 많은 독립 optimizer seeds 및 sampling 민감도를 확인하고, PUMA560 재현은 별도 실험으로 수행하는 것이다.

## 파일 안내

- `results/config.json`, `environment.txt`: 전체 조건/기반 commit/실행 환경
- `candidates.csv`, `raw_rollouts.csv`: 모든 후보와 학습·검증·시험의 feasibility/metrics
- `selected.csv`, `selection_status.csv`: gain 선택과 빈 허용구간/매칭 실패
- `test_summary.csv`, `paired_comparison.csv`, `paired_test_noise.csv`: 공통 시험의 실제 수치와 noise별 비교
- `trace_*.csv.gz`: 선택 제어기와 고정 gain의 독립 시험 원시 시계열
- `common_axes.png`: 같은 IAE–CAV / IAE–토크² 좌표에 두 arm 표시. 다른 Pareto 목적축끼리 비교하지 않음
- `matched_iae_test.png`: test IAE gap에 따른 B−A 차이, 원은 validation 매칭, ×는 실패
- `checks.json`, `candidate_audit.json`, `sha256.json`, 실행 로그: 검증과 감사 기록

재현 명령은 PROTOCOL.md 참조.
