# KRoC: Payload별 Tracking–Energy Pareto 실험

> **Canonical Final Model — 이 작업에서 “우리 최종 모델” 또는 “final model”은 [Canonical Final Model](docs/CANONICAL_MODEL.md)만을 의미합니다. 기존 placeholder 설정으로 되돌리지 않습니다.**
> 기본 실행 설정은 `configs/canonical_final.toml`입니다. 이전 illustrative 설정과 결과는 과거 구현 검증용이며 최종 모델의 결과가 아닙니다.

1-DOF 로봇 관절 + DC motor + 전압 PID를 Python으로 시뮬레이션하고, BoTorch/GPyTorch의 다목적 Bayesian optimization으로 tracking RMSE와 **모터 단자 순전기 에너지**의 trade-off를 탐색합니다. 실험 설계는 연구자의 논문 초안과 최종 실험 메모를 반영했습니다. 실험 결과가 나오기 전에 trade-off, knee, payload 효과 또는 특정 controller의 우수성을 가정하지 않습니다.

## 연구 질문

1. 같은 궤적·제약·탐색 예산에서 payload 변화에 따라 달성 가능한 tracking–energy 근사 Pareto front가 얼마나 달라지는가?
2. Nominal payload에서 찾은 **Pareto controller set 전체**의 이득을 고정하여 다른 payload로 옮기면, 실행 가능성·비지배 관계·hypervolume이 얼마나 유지되는가?
3. Nominal front에서 선택한 tracking-oriented **CT**, balanced **CB**, energy-oriented **CE**의 응답은 어떻게 달라지는가?

이 프로젝트는 optimizer 성능 비교 연구가 아닙니다. 유한 예산으로 얻은 front는 전역 최적 Pareto front의 근사입니다.

## 설치와 빠른 실행

Python 3.11 이상이 필요합니다. 실제 검증 환경은 Python 3.13, macOS ARM64이며 정확한 설치 버전은 `requirements-lock.txt`에 기록했습니다. 다른 운영체제에서는 `pyproject.toml`의 호환 범위로 설치할 수 있습니다. GPU 없이 CPU double precision으로 실행합니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
pytest -q

# 기본 qLogNEHVI로 pilot → exp1 → exp2 → 그림/표 생성
kroc-mobo all --smoke --out results/smoke
```

검증 환경의 버전을 재설치하려면:

```bash
python -m pip install -r requirements-lock.txt
python -m pip install --no-deps -e .
```

`--smoke`는 1회 반복, payload당 초기 4개 + BO 2개, 각 단계 잡음 seed 2개로 줄입니다. **5초 궤적, 1 ms 제어 주기, 1/2/3 kg 조건은 그대로**입니다. 후보가 적어 대표 controller가 3개 미만일 수 있으며 이 경우 원인을 기록하고 Fig. 2를 생략합니다. 이미 사용한 단계의 결과는 덮어쓰지 않으므로 재실행 시 새 출력 경로를 사용하세요.

단계별 실행:

```bash
kroc-mobo pilot --config configs/canonical_final.toml --out results/pilot
kroc-mobo plot --out results/pilot

kroc-mobo exp1 --config configs/canonical_final.toml --out results/full
kroc-mobo exp2 --out results/full
kroc-mobo plot --out results/full

# 수치적으로 개선된 acquisition을 명시적으로 선택 가능
kroc-mobo exp1 --smoke --backend qlognehvi --out results/smoke-log

# 실행 경로만 확인하는 Sobol 기준선; MOBO 결과로 표기하지 않음
kroc-mobo all --smoke --backend sobol --out results/smoke-sobol
```

동일한 기능을 `python experiments/pilot_test.py`, `python experiments/exp1_pareto.py`, `python experiments/exp2_transfer.py`, `python analysis/make_figures.py`로도 실행할 수 있습니다. 옵션은 CLI와 같습니다. `exp2`와 `plot`은 `--out/config.json`의 동결된 설정을 읽으므로 `--smoke`를 다시 전달하지 않습니다.

## 실험 구조

| 단계 | 입력 및 동작 | 주요 출력 |
|---|---|---|
| Pilot | 수동 PID 3개 × payload 3개; RK4 적분 간격을 절반으로 줄인 결과 비교 | 각도·오차·전압·전류·전력·누적 에너지, 실행 가능성, 수치 수렴 |
| Exp. 1 | payload마다 새 GP/탐색 이력; 같은 초기 Sobol points, bounds, 예산, paired noise seeds | 모든 후보와 rollout 로그, 독립 selection seed 재평가, payload별 근사 Pareto front |
| Exp. 2 | nominal selection front 전체를 고정한 채 모든 payload에서 재평가; local front도 같은 test seeds로 재평가 | retention 두 정의, HV loss, CT/CB/CE 성능 및 시간응답 |
| Analysis | repeat별 결과를 유지하고 요약 | Fig. 1·2, Table 1·2 CSV, PNG 300 dpi, PDF |

기본 설정: payload 1/2/3 kg, nominal 1 kg, **5개 독립 optimization repeats**, 초기 10개를 포함한 총 40개 후보, train 3·selection 5·test 10개 잡음 seed입니다. Exp. 1의 최적화 비용은 1,800 rollout, selection 비용은 3,000 rollout이며 Exp. 2와 그림용 rollout은 별도 기록합니다. 전체 실행은 smoke보다 훨씬 오래 걸립니다.

## 모델과 목적함수

RE35 323890 + GP42C 126:1 감속 구동, 수직 회전면, 아래쪽 수직을 θ=0으로 하는 단일 관절입니다. Payload는 반경 rₚ의 점질량이며 한 rollout 동안 일정합니다.

```text
Jl = ml l²/3
Ja = N²(Jm + Jg)
Ieq = Ja + Jl + mp rp²
Ieq θ̈ = η N Kt i − b θ̇ − (ml rl + mp rp) g sin θ
L i̇ = V − R i − Ke N θ̇

θd(t) = θ0 + (θf − θ0)(10s³ − 15s⁴ + 6s⁵), s = t/T
JT = sqrt((1/T) ∫ [θd(t) − θ(t)]² dt)         [rad]
JE = ∫ V(t) i(t) dt                          [J]
```

- JT는 **잡음이 없는 실제 각도**에 대한 시간 적분 RMSE입니다.
- JE는 **포화 후 실제 전압**의 부호 있는 순에너지입니다. 음의 전력을 회생으로 공제하므로 비회생 전원의 소비량과 동일하지 않습니다. `energy_drawn = ∫max(Vi,0)dt`, `energy_returned = ∫max(−Vi,0)dt`도 보관합니다. 드라이버 손실은 모델에 없습니다.
- 사용자 지정 Kt=0.0292, Ke=0.0291을 그대로 사용합니다. 전기 입력에서 저장 에너지·저항·점성 항과 `∫N(Ke−ηKt)iωdt`를 뺀 수치 잔차를 검증합니다. 마지막 항은 지정 방정식의 signed transmission exchange이며 모든 동작에서 양의 실제 감속기 손실을 뜻하지 않습니다. 일정 효율식은 실제 역구동/회생 효율을 검증한 모델이 아닙니다.
- 제어는 1 ms마다 갱신하고 전압을 zero-order hold합니다. Plant와 목적함수의 적분 상태를 함께 RK4로 계산합니다. 기본 내부 적분 간격은 0.0625 ms (16 substeps)입니다. 한계 감시는 내부 적분 완료 지점에서 수행하므로 연속시간 한계의 수학적 보증이 아닙니다.
- PID는 측정각의 저역통과 미분, 전압 saturation, back-calculation anti-windup을 사용합니다. 적분 상태는 V 단위이며 `z_dot = Ki*e + Kaw*(V-u)`입니다. 미분 필터는 sample hold 입력에 대한 정확한 1차 상태 갱신, 적분 상태는 전진 Euler입니다. Feedforward는 없습니다.
- 잡음은 독립 Gaussian sample을 설정 주기 동안 유지합니다. `variance = noise.power / noise.sample_dt`. 기본값은 1e-7 rad²입니다. 특정 Simulink 난수열과 비트 단위로 같은 구현은 아닙니다.
- 전류·속도·각도 한계 초과를 feasibility로 기록합니다. **전류나 토크를 clip하지 않습니다.** 한계 위반 후에도 유한 시뮬레이션은 끝까지 계산합니다. 수치 실패는 목적값 NaN으로 남기고 목적 GP에서 제외합니다.

## MOBO와 공정한 평가

`[Kp, Ki, Kd]`를 같은 경계로 [0,1]³에 정규화합니다. 각 목적과 집계 제약에 독립적인 Matérn 5/2 ARD GP를 둡니다. Train seed 평균의 SEM²를 목적 관측 잡음으로 사용하고, 매우 작은 분산은 고정 floor를 적용합니다. 모든 train seed에서의 최대 정규화 한계 초과량을 하나의 제약으로 모델링합니다. 이것은 표본에서 관측한 실행 가능성이며 확률적 안전 보증은 아닙니다.

BoTorch는 최대화를 사용하므로 두 목적에 음수를 적용합니다. `objective_scales`와 `reference_point`는 raw 단위로 config에 고정하고 모든 payload/repeat에 공유합니다. GP의 `Standardize`는 posterior의 raw GP 출력 단위로 역변환되며 보고용 목적 축·HV 척도와 구분됩니다.

최종 실행 acquisition은 **constrained qLogNEHVI, q=1**입니다. 원래 qNEHVI 실행이 NaN 기울기로 중단되어 별도 새 실행에서 수치 안정화 버전을 사용합니다. BoTorch의 알려진 수치 문제 안내에 따라 `qlognehvi`도 선택할 수 있습니다. 선택한 알고리즘은 config와 CSV에 기록하며 자동으로 바꾸지 않습니다. 유효 목적값이 2개 미만이거나 중복 제안인 경우만 명시적으로 표기한 Sobol recovery 후보를 평가합니다. GP fitting이나 프로그램 오류는 실행을 중단하며 성공 결과로 숨기지 않습니다.

실패 후보도 40개 예산에 포함합니다. 모든 후보를 독립 **selection seeds**로 재평가한 후 feasible non-dominated set을 구성합니다. 반복 간에는 seed가 다르며, 같은 반복에서는 payload와 controller 사이에 동일 잡음열을 사용합니다. Exp. 2는 selection에 쓰지 않은 **test seeds**를 사용하고 local·transfer set 모두 같은 조건으로 평가합니다. Raw rollout 값, seed 목록, 설정 hash, 패키지 버전, Git revision을 기록합니다.

## Exp. 2 지표의 정확한 의미

`N0`는 nominal **selection front**의 controller 수입니다. 모든 payload에서 gain과 필터·anti-windup·한계를 고정합니다.

- `N_ret`, `R_P = 100 N_ret/N0`: 전이된 집합 내부에서 실행 가능하고 non-dominated로 남는 controller 비율입니다. 모든 전이 controller가 local front에 밀려도 이 값이 클 수 있습니다.
- `N_ret_union`, `R_P_union`: 전이된 집합과 대상 payload의 독립 local set을 합친 비교 집합에서 non-dominated인 전이 controller 비율입니다. 어느 쪽도 전역 Pareto 최적성의 증명은 아닙니다.
- `L_HV = 100 (HV_local − HV_transfer)/HV_local`: 같은 고정 척도·기준점으로 계산한 정확한 2D minimization hypervolume 차이입니다. **음수 손실은 그대로 보존**합니다. 유한 탐색에서는 transfer set이 local set보다 좋을 수 있습니다. Local HV=0이면 NaN과 사유를 남깁니다. 기준점을 지배하지 못하는 점은 HV에 기여하지 않으며 개수를 보고합니다.
- 새로운 test seed에서 nominal 내부 순위나 feasibility도 바뀔 수 있으므로 nominal `R_P`를 100%로 강제하지 않습니다. Nominal local/transfer는 같은 controller와 paired seeds로 계산하므로 유효한 경우 `L_HV=0`입니다.
- CT는 JT 최소, CE는 JE 최소, CB는 양 끝점을 제외한 후보 중 **nominal 목적범위로 정규화한 이상점까지 거리가 최소**인 점입니다. CB를 기하학적 knee라고 부르지 않습니다. 동률은 다른 목적값과 Kp/Ki/Kd의 오름차순으로 결정합니다.
- 유효한 서로 다른 front controller가 3개 미만이면 세 영역 비교를 만들지 않습니다. `selection_status.json`에 사유를 기록합니다. 실험을 원하는 결론에 맞춰 점을 추가하거나 controller를 다시 선택하지 않습니다.
- 대표 controller의 단위 있는 변화량과 백분율을 기록합니다. 기준 JT/JE가 1e-9 이하이거나 순에너지가 음수면 해당 백분율은 NaN입니다. Noise 평균·표준편차와 optimization repeat 간 평균·표준편차는 별도로 취급합니다.

## 생성되는 파일

```text
kroc-payload-mobo/
├── configs/canonical_final.toml       # 최종 모델, 단위, seeds, budget, HV 설정
├── src/kroc_mobo/
│   ├── plant.py / pid.py / trajectory.py / simulation.py
│   ├── mobo.py                    # BoTorch/GPyTorch
│   ├── metrics.py                 # Pareto, retention, HV, representatives
│   ├── experiments.py / analysis.py / cli.py
│   └── config.py / io.py
├── experiments/                   # pilot / exp1 / exp2 실행 스크립트
├── analysis/                      # 그림·분석 실행 스크립트
├── tests/                         # 물리 수지, 목적, HV, 실제 acquisition, E2E
├── docs/                          # 실험 실행·실제 파라미터 교체 안내
├── requirements-lock.txt
└── results/<run>/                 # Git에서 제외
    ├── config.json                # 동결 설정
    ├── pilot/                     # 수동 제어기·적분 수렴·시간응답
    ├── exp1/
    │   ├── manifest.json
    │   ├── pareto_all.csv / selection_all.csv
    │   └── repeat_00/payload_1kg/  # train, selection, raw rollouts, seeds, pareto
    ├── exp2/
    │   ├── representatives_frozen.csv / selection_status.json
    │   ├── transfer_summary.csv / representative_performance.csv
    │   ├── test_rollouts.csv / transfer_all.csv / local_retested_all.csv
    │   └── repeat_00/payload_1kg/  # transfer, local_retested, trace_CT/CB/CE
    └── analysis/
        ├── fig1_payload_pareto.png/.pdf
        ├── fig2_representative_r00.png/.pdf
        ├── transfer_vs_local_r00.png/.pdf
        ├── diagnostic_angle_power_r00.png/.pdf
        ├── table1_setup.csv
        ├── table2_transfer_per_repeat.csv / table2_transfer_across_repeats.csv
        └── common_budget_comparison.csv
```

Fig. 1은 반복별 front를 별도 선으로 표시합니다. 서로 다른 repeat를 합친 front를 반복 실험 결과처럼 제시하지 않습니다. Fig. 2는 CT/CB/CE별 tracking angle·error·power·누적 순에너지를 합친 4×3 그림이며 **첫 번째 paired test seed의 예시 응답**입니다. 별도 그림에서 각도와 전력을 확인할 수 있습니다. 공통 budget 표는 front의 겹치는 범위 안에서 실제 관측한 점만 비교하고 외삽하지 않습니다.

현재는 중간 CSV checkpoint를 남기지만 중단 실행 자동 재개는 지원하지 않습니다. 실패한 run을 보관하고 새 출력 경로로 다시 실행하세요. 미완료 manifest에서는 후속 단계를 실행할 수 없습니다. 자동 병렬화는 하지 않으며 비교용 random state를 명시적으로 고정합니다.

## 최종 모델 및 결과 해석

물리값과 단위 환산, 모델 한계는 [최종 모델 명세](docs/CANONICAL_MODEL.md)를 따릅니다. Experiment 1·2만 수행하며 Experiment 3은 수행하지 않습니다. 3.84 A는 연속전류 참고치를 보수적인 **순간 전류 feasibility 상한**으로 적용한 연구 설정입니다. 실제 전류제어기/열모델 또는 제조사 peak-current rating을 뜻하지 않습니다.

5초 전체에 걸쳐 0→60° quintic 운동을 수행하며 별도 hold 구간은 없습니다. Noise, PID 탐색 경계, 필터/anti-windup, 각도·속도 수치 한계, 최적화 예산은 데이터시트 값이 아닌 공개된 실험 설계입니다. 이 설정으로 검증되지 않은 하드웨어 성능을 주장하지 않습니다.

```bash
# 최종 모델 전체 실험; 기존 결과와 별도 경로
kroc-mobo all --config configs/canonical_final.toml --out results/canonical-final-v1
```

Pilot에서 관측된 약 2.57–9.98 J 범위를 참고하여, 최적화 전에 공통 HV 기준점 `[1 rad, 20 J]`와 척도 `[0.1 rad, 10 J]`를 고정했습니다. Hypervolume loss는 이 기준점에 의존하며 물리적 에너지 손실률과 다릅니다.

## 참고 구현 자료

- [BoTorch constrained multi-objective tutorial](https://botorch.org/docs/tutorials/constrained_multi_objective_bo): objective/constraint GP와 qNEHVI API.
- [BoTorch 0.17.2 multi-objective tutorial](https://botorch.org/docs/v0.17.2/tutorials/multi_objective_bo): 최대화 convention, noise-aware hypervolume acquisition.
- [Daulton et al., qNEHVI (2021)](https://arxiv.org/abs/2105.08195).
- [DC motor model, University of Michigan CTMS](https://ctms.engin.umich.edu/CTMS/?example=MotorPosition&section=SimulinkSimscape).
- [MathWorks Band-Limited White Noise](https://www.mathworks.com/help/simulink/slref/bandlimitedwhitenoise.html).

원본 논문 초안과 스크린샷 자체는 저장소에 복사하지 않았습니다. 원고의 최종 식·파라미터·지표 정의와 구현을 실제 실험 전에 대조하세요.
