# 목적함수 변경 최소 파일럿

이 폴더만 추가한다. 기반 main: d18b00d2e7093cf5cb1b9cb10e9d70c4e3a9038e. 기존 실험, baseline, archive, simulator를 수정하지 않는다. 사용자 요청은 저장소 AGENTS.md의 기존 Experiment 1/2 범위보다 우선하며 이 독립 예비실험에만 적용한다.

## 사전 설계
- Canonical Final 1-DOF geared DC motor, payload 1 kg. 기존 sampled voltage PID, derivative-on-measurement, antiwindup와 RK4 simulator를 import한다. config 전체는 results/config.json.
- A = (IAE,CAV), B = (IAE, integral torque squared). 동일 NSGA-II(pymoo 0.6.1.5), population 16, generations 4, seed 731/732/733, 총 64 candidate evaluations/run (infeasible 포함), 384 candidates. 각 candidate는 공통 noise seed 51001/51002의 2 rollouts. 초기 LHS 후보 16개 동일 여부 assertion. SBX prob .9 eta15, PM eta20, 나머지 pymoo 고정 버전 기본값.
- Gains: Kp [0,800], Ki [0,400], Kd [0,80]. Nominal 5s, 0→60° quintic. Current ≤3.84 A, |angle|≤π, |velocity|≤15 rad/s, numerical guard 1e8, voltage saturation ±24V. Current threshold is the repository's design assumption, not validated hardware safety. Feasibility uses integration-substep peaks, not just output samples; inherited constraint margin for optimizer. No new error/oscillation constraint from Zidan is claimed.
- Torque τ = η N Kt i, delivered electromagnetic torque at joint in this model. PID command is voltage; τ is not the original paper's direct torque-command signal. Neither τ² integral nor RMS is electrical/mechanical energy.
- Zidan et al. (2018), DOI 10.5220/0006899802400247, p.241 Eq.(1): IAE=Σ|e(i)|ΔT; Eq.(2): CAV=Σ|τ(i+1)−τ(i)|, no ΔT multiplier. Original attached PDF was read from the conversation's recovered temporary attachment, not /mnt/data (absent). In this scalar adaptation all n+1 output samples t=0,...,T are used. CAV includes initial zero current and final endpoint; no fictitious post-T return to zero. IAE uses sum, not RMSE. Integral τ² uses trapezoidal control-grid quadrature; RMS=sqrt(integral/T). CAV is total variation, not statistical variance. This is NOT a direct PUMA560 reproduction.
- Validation: every train-feasible candidate assessed with independent common 61001/61002 noise seeds. For fixed IAE targets .005/.010/.025 rad s, retain validation-feasible candidates within ±10%; choose lowest own effort metric, tie by IAE then candidate order. No interpolation, combined objective normalization, pooled cross-arm control borrowing, or test-based controller tuning. Candidate archive includes all evaluated points, not only final NSGA-II population.
- A pair is validation-matched only if actual IAE relative gap |A−B|/mean(A,B)≤5%. Empty target windows are reported, never replaced after seeing results. This is a modest decision-rule comparison, not proof of global optimal fronts. If arms select the same gains, report it as no objective-induced difference.
- Independent tests: nominal 5s 60°, short 4s 45°, reverse 6s −45°, all rest-to-rest from 0; noise 71001/71002/71003 shared. Report all metrics, feasibility and test IAE gap, also for failed validation matches. Test IAE matching is a diagnostic, not a selection rule. Only pairs matched on both validation and test with both feasible support matched-error descriptive statements. Also inspect each test noise seed rather than treating rollouts as independent optimizer repeats.
- No-optimization sanity: fixed gains [70,30,5] from canonical pilot.balanced, no tuning, same independent test trajectories/noises. Metric identities and common initial candidates checked automatically. Raw output-grid traces saved compressed; constraints use original full-resolution simulator peaks.
- Tiny n=3 optimizer repetitions, 64 evaluations: no significance test, no algorithm ranking or hardware/general superiority claim. Own-metric improvement alone cannot establish benefit. RMS and τ² integral are algebraically linked at fixed duration and are not independent evidence.

## Reproduction
From repository root, Python 3.13:

```sh
python3 -m venv .venv-pilot
.venv-pilot/bin/python -m pip install -r pilot/objective-effort-20261110/requirements.txt
MPLCONFIGDIR=/tmp/kroc-pilot-mpl NUMBA_CACHE_DIR=/tmp/kroc-pilot-numba .venv-pilot/bin/python pilot/objective-effort-20261110/run.py > pilot/objective-effort-20261110/execution.log 2>&1
```

Exact executed dependency versions: results/environment.txt. The script reuses repository src via an explicit path, and regenerates only this pilot/results directory. Candidate evaluation budget excludes validation/test/sanity rollouts; raw_rollouts.csv exposes all phases. execution.log contains actual run output; checks.json records assertions; sha256.json records output hashes. See INTERPRETATION_KO.md for numerical findings.

## 실행 호환성 수정
첫 실행은 pymoo 0.6.1.5가 NumPy 2.5.3에서 제거된 row_stack alias를 호출해 중단됐다. 초기 실패 로그를 보존했다. 파일럿 내부에서 해당 alias를 동일 연산인 vstack으로 연결하고 같은 설계/seed로 처음부터 재실행했다. 기존 simulator나 라이브러리 파일은 변경하지 않았다.

After run.py, execute `.venv-pilot/bin/python pilot/objective-effort-20261110/analyze.py` to reproduce per-noise pair diagnostics, candidate divergence audit, and the final plot with validation-match marker distinctions. Plot circles are validation matched; crosses failed validation matching. Only points left of the 5% test threshold that are circles qualify for matched-error interpretation.

The first full simulation completed, but the final RMS identity check mistakenly squared the average RMS over noise realizations. Mean(RMS)^2 is not Mean(RMS^2). That check was corrected to test each raw rollout, and the entire experiment rerun with unchanged seeds/selection. The failed-check log is preserved separately. No thresholds were changed based on these results.
