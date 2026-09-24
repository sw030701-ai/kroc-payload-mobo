"""Generate the revised canonical report from immutable completed experiment outputs."""

import argparse
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from kroc_mobo.analysis import _save, plt
from kroc_mobo.io import load_snapshot, require_complete
from kroc_mobo.metrics import GAINS


def markdown(frame):
    def fmt(x):
        if isinstance(x, float):
            return "—" if pd.isna(x) else f"{x:.6g}"
        return str(x)

    return "\n".join(
        [
            "| " + " | ".join(frame.columns) + " |",
            "| " + " | ".join(["---"] * len(frame.columns)) + " |",
            *["| " + " | ".join(map(fmt, row)) + " |" for row in frame.itertuples(index=False, name=None)],
        ]
    )


def mean_sd(values, digits=5):
    return f"{values.mean():.{digits}g} ± {values.std(ddof=1):.{digits}g}"


def table(out, name, frame):
    frame.to_csv(out / f"{name}.csv", index=False)
    frame.to_latex(out / f"{name}.tex", index=False, escape=True, float_format="%.6g", na_rep="—")


def build(root, out, sensitivity):
    root, out, sensitivity = Path(root), Path(out), Path(sensitivity)
    if (out / "REPORT.md").exists():
        raise FileExistsError("Report already exists; preserve it and use a fresh output directory")
    for stage in ("pilot", "exp1", "exp2"):
        require_complete(root, stage)
    c = load_snapshot(root)
    if not c["mobo"].get("include_zero_anchor") or "selection" not in c:
        raise ValueError("This report requires the revised anchor/practical-selection protocol")
    decision = json.loads((sensitivity / "decision.json").read_text())
    out.mkdir(parents=True, exist_ok=True)
    for path in (root / "analysis").glob("*"):
        if path.suffix in (".csv", ".png", ".pdf") and not path.name.startswith("trace_"):
            shutil.copy2(path, out / path.name)
    for path in sensitivity.glob("*"):
        if path.is_file():
            (out / "sensitivity").mkdir(exist_ok=True)
            shutil.copy2(path, out / "sensitivity" / path.name)
    shutil.copy2(root / "config.json", out / "config.json")
    manifests = {}
    for stage in ("pilot", "exp1", "exp2"):
        manifests[stage] = json.loads((root / stage / "manifest.json").read_text())
        shutil.copy2(root / stage / "manifest.json", out / f"manifest_{stage}.json")
    for name in ("representatives_frozen.csv", "selection_status.json", "selection_rule.json"):
        shutil.copy2(root / "exp2" / name, out / name)
    fronts = pd.read_csv(root / "exp1/pareto_all.csv")
    per = pd.read_csv(root / "analysis/exp1_results_per_repeat.csv")
    reps = pd.read_csv(root / "exp2/representative_performance.csv")
    frozen = pd.read_csv(root / "exp2/representatives_frozen.csv")
    threshold = c["selection"]["practical_JT_max"]
    setup = pd.DataFrame(
        [
            ("Model", "1-DOF geared joint; RE35 323890 / GP42C"),
            ("N / eta", "126 / 0.72"),
            ("R / L", "0.568 ohm / 0.000191 H"),
            ("Kt / Ke", "0.0292 Nm/A / 0.0291 Vs/rad"),
            ("Jm / Jg", "8.12e-6 / 1.4e-6 kg m^2"),
            ("Link l / mass / COM / payload radius", "0.20 m / 0.50 kg / 0.10 m / 0.20 m"),
            ("Payloads / nominal", "1, 2, 3 kg / 1 kg"),
            ("Jeq (1, 2, 3 kg)", "0.19780619, 0.23780619, 0.27780619 kg m^2"),
            ("b / g", "0.05 Nm s/rad / 9.81 m/s^2"),
            ("Voltage / current", "±24 V saturation / ±3.84 A peak feasibility, no current clipping"),
            ("Trajectory / horizon", "quintic 0→60 deg over full 5 s, no hold"),
            ("Control / RK4 step", "1 ms / 62.5 microseconds"),
            ("PID bounds Kp / Ki / Kd", " / ".join(str(c["search"][k]) for k in GAINS)),
            ("Noise variance / sampling", "1e-7 rad^2 / 1 ms"),
            (
                "Acquisition / repeats / evaluations",
                f"qLogNEHVI / {c['experiment']['repeats']} / {c['mobo']['n_evaluations']} per payload",
            ),
            ("Initial design", "1 zero-PID anchor + 9 Sobol = 10 included in 40"),
            ("Train / selection / test replicates", "3 / 5 / 10; disjoint phase seeds, paired payload seeds"),
            ("Representative tracking criterion", f"JT <= {threshold:g} rad; selection only"),
            ("HV reference / scales (supplementary)", "[1 rad,20 J] / [0.1 rad,10 J]"),
        ],
        columns=["Condition", "Value"],
    )
    table(out, "table1_common_conditions", setup)
    summary = (
        per.groupby("payload")
        .agg(
            Pareto_mean=("pareto_count", "mean"),
            Pareto_std=("pareto_count", "std"),
            feasible_mean=("feasible", "mean"),
            feasible_std=("feasible", "std"),
            min_JT_mean=("JT_min", "mean"),
            min_JT_std=("JT_min", "std"),
            seconds_mean=("elapsed_seconds", "mean"),
        )
        .reset_index()
    )
    table(out, "exp1_compact", summary)
    fixed = pd.DataFrame(
        [
            dict(repeat=r, payload=p, JT_budget_rad=0.01, best_observed_JE=g.loc[g.JT <= 0.01, "JE"].min())
            for (r, p), g in fronts.groupby(["repeat", "payload"])
        ]
    )
    table(out, "tracking_budget_001rad", fixed)
    fixed_stats = fixed.groupby("payload").best_observed_JE.agg(["mean", "std", "count"])
    primary = pd.DataFrame(
        [
            dict(
                role=role,
                payload=payload,
                JT_rad=mean_sd(g.JT),
                JE_J=mean_sd(g.JE),
                delta_JT_pct=mean_sd(g.delta_JT_pct),
                delta_JE_pct=mean_sd(g.delta_JE_pct),
                feasible=f"{int(g.feasible.sum())}/{len(g)}",
                practical_satisfied=f"{int(g.practical_satisfied.sum())}/{len(g)}",
            )
            for (role, payload), g in reps.groupby(["role", "payload"], sort=False)
        ]
    )
    table(out, "table2_primary_transfer", primary)
    first = reps.loc[
        reps.repeat == 0,
        [
            "role",
            "payload",
            *GAINS,
            "JT",
            "JE",
            "delta_JT_pct",
            "delta_JE_pct",
            "feasible",
            "practical_satisfied",
        ],
    ]
    table(out, "table_representatives_repeat00", first)
    selection = frozen[
        [
            "repeat",
            "role",
            *GAINS,
            "JT",
            "JE",
            "utopia_distance",
            "practical_candidate_count",
            "selection_status",
        ]
    ]
    table(out, "table_selection", selection)
    transfer = pd.read_csv(root / "analysis/table2_transfer_across_repeats.csv")
    supplementary = transfer[["payload", "R_P_mean", "R_P_std", "L_HV_mean", "L_HV_std"]]
    table(out, "supplementary_transfer", supplementary)
    # Preserve the full observed fronts, including the actually evaluated anchor.
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for i, payload in enumerate(c["experiment"]["payloads"]):
        for repeat, group in fronts.loc[fronts.payload == payload].groupby("repeat"):
            group = group.sort_values("JT")
            for ax, view in zip(axes, [group, group.loc[group.JT <= 0.06]]):
                ax.plot(
                    view.JT,
                    view.JE,
                    "o-",
                    color=f"C{i}",
                    alpha=0.55,
                    ms=3,
                    label=f"{payload:g} kg" if repeat == 0 else None,
                )
    anchors = fronts.loc[(fronts[GAINS] == 0).all(axis=1)]
    axes[0].scatter(anchors.JT, anchors.JE, color="black", marker="*", s=80, label="Evaluated zero anchor")
    axes[0].set_title("Full observed fronts (separate repeats)")
    axes[1].set(xlim=(0, 0.06), title="Practical-region view")
    axes[1].axvline(threshold, color="grey", ls="--")
    for ax in axes:
        ax.set(xlabel="Tracking RMSE JT [rad]", ylabel="Net electrical energy JE [J]")
        ax.grid(alpha=0.2)
    axes[0].legend(fontsize=7)
    _save(fig, out, "fig1_full_and_zoom", "Canonical revision | expanded bounds | initial zero anchor")
    fig, ax = plt.subplots(figsize=(7, 4))
    p = fronts.loc[(fronts.repeat == 0) & (fronts.payload == 1) & (fronts.JT <= 0.06)]
    ax.plot(p.JT, p.JE, "o-", color="grey", label="Nominal observed front")
    for role, marker, color in zip(["CT", "CB", "CE"], ["s", "D", "^"], ["C0", "C1", "C2"]):
        row = frozen.loc[(frozen.repeat == 0) & (frozen.role == role)].iloc[0]
        ax.scatter(row.JT, row.JE, marker=marker, color=color, s=90, label=role, zorder=3)
    ax.axvline(threshold, color="black", ls="--", label="Selection criterion 0.05 rad")
    ax.set(xlabel="Nominal selection JT [rad]", ylabel="Nominal selection JE [J]")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.2)
    _save(fig, out, "fig_selection_r00", "Practical representative selection | repeat 0")
    # Quantitative findings use repeat-level means; do not treat 50 noise seeds as n=50 optimizations.
    ct3 = reps.loc[(reps.role == "CT") & (reps.payload == 3)]
    ce3 = reps.loc[(reps.role == "CE") & (reps.payload == 3)]
    merged = reps.loc[reps.role == "CT", ["repeat", "payload", "JE"]].merge(
        reps.loc[reps.role == "CE", ["repeat", "payload", "JE"]],
        on=["repeat", "payload"],
        suffixes=("_CT", "_CE"),
    )
    merged["CE_energy_saving_vs_CT_pct"] = 100 * (merged.JE_CT - merged.JE_CE) / merged.JE_CT
    table(out, "CE_energy_saving_vs_CT", merged)
    findings = [
        f"1 kg paired bounds 비교에서 5회 평균 최소 JT는 {decision['original_mean_min_JT']:.7f}→{decision['expanded_mean_min_JT']:.7f} rad로 {decision['min_JT_improvement_pct']:.2f}% 감소했다. Expanded CT {decision['expanded_CT_outside_old_count']}/5회가 기존 범위 밖이며 {decision['expanded_CT_at_upper_count']}/5회는 새 상한에 접했다.",
        "Revised independent fronts에서 JT≤0.01 rad를 만족하는 관측 최소 JE의 평균±SD는 "
        + "; ".join(f"{p:g} kg: {r['mean']:.4f}±{r['std']:.4f} J" for p, r in fixed_stats.iterrows())
        + ". 이는 공통 tracking 예산 비교이며 같은 JT에서의 보간값이 아니다.",
        f"Retuning 없는 CT의 3 kg JT는 {mean_sd(ct3.JT)} rad이고, 같은 controller의 1 kg 대비 JT 변화율은 {mean_sd(ct3.delta_JT_pct, 4)}%, JE 변화율은 {mean_sd(ct3.delta_JE_pct, 4)}%였다.",
        f"CE의 3 kg JT는 {mean_sd(ce3.JT)} rad였다. 3 kg에서 CT 대비 CE 에너지 절감률은 {mean_sd(merged.loc[merged.payload == 3, 'CE_energy_saving_vs_CT_pct'], 4)}%였다. Practical criterion 충족은 {int(ce3.practical_satisfied.sum())}/5회로 별도 보고한다.",
        f"모든 payload/repeat의 초기 설계 {len(anchors)}/15개에 zero-PID anchor가 포함되었고 대표 선택의 zero PID는 0개였다. 대표 test 조건의 물리적 feasibility는 {int(reps.feasible.sum())}/{len(reps)}, JT≤{threshold:g} rad까지 충족한 조건은 {int(reps.practical_satisfied.sum())}/{len(reps)}였다.",
    ]
    (out / "QUANTITATIVE_FINDINGS.md").write_text(
        "# Quantitative findings\n\n각 ±는 optimization repeats n=5의 SD. 각 repeat 성능은 test seeds 10개의 평균.\n\n"
        + "\n\n".join(f"{i + 1}. {s}" for i, s in enumerate(findings))
        + "\n"
    )
    sensitivity_per = pd.read_csv(sensitivity / "per_repeat.csv")
    sensitivity_compact = sensitivity_per[
        [
            "repeat",
            "original_min_JT",
            "expanded_min_JT",
            "improvement_pct",
            "expanded_CT_outside_old",
            "expanded_CT_at_upper",
        ]
    ]
    sensitivity_practical = pd.DataFrame(
        [
            dict(
                arm=arm,
                practical_count_mean=sensitivity_per[f"{arm}_practical_count"].mean(),
                practical_min_JE_mean=sensitivity_per[f"{arm}_practical_min_JE"].mean(),
                practical_min_JE_std=sensitivity_per[f"{arm}_practical_min_JE"].std(),
            )
            for arm in ("original", "expanded")
        ]
    )
    table(out, "sensitivity_practical_impact", sensitivity_practical)
    convergence = pd.read_csv(root / "pilot/integration_convergence.csv")
    coincident = frozen.groupby("repeat").selection_status.first()
    boundary = frozen.loc[frozen.role == "CT", GAINS].to_numpy()
    upper = np.array([c["search"][g][1] for g in GAINS])
    boundary_count = int(((upper - boundary) <= 0.001 * upper).any(axis=1).sum())
    findings_markdown = "\n\n".join(f"{i + 1}. {s}" for i, s in enumerate(findings))
    report = f"""# Canonical Final Model — revised Experiment 1·2

2026-09-24 revision. **Step 1 판정: expanded bounds 채택**. Experiment 1·2를 모두 새로 실행했다.
Experiment 3은 수행하지 않았다. 모델은 기존 **1-DOF geared joint**이며, 참고 대화 제목의
3-DOF 시스템에 대한 결과로 해석하지 않는다. 물리값은 사용자 지정 연구 모델이다.

- Run: `{root.as_posix()}`
- Config SHA256: `{manifests["exp1"]["config_sha256"]}`
- 실험 code commit: `{manifests["exp1"]["git_revision"]}`; manifest의 source SHA256으로 실행 코드를 식별한다.
- 이전 보고서 전체: [2026-09-23 archive](../archive/canonical-final-20260923/REPORT.md).
  이전 raw run `results/canonical-final-qlog-v3`와 원본 ZIP도 그대로 보존했다.
- 사전 고정한 설계: [REVISION_PROTOCOL.md](../../docs/REVISION_PROTOCOL.md).

## Step 1 — 1 kg gain-bound sensitivity

두 arm 모두 5 repeats × 40 evaluations (10 initial Sobol), train/selection noise seeds 3/5개로
동일하게 실행했다. Bounds 이외의 모델·optimizer·seed는 동일하다. 이 비교는 Step 2 전
프로토콜을 사용하므로 두 arm 모두 새 zero anchor를 강제하지 않았다. 이후 canonical
재실행은 anchor를 포함하므로 sensitivity arm 결과와 canonical 결과를 섞지 않는다.

Primary improvement는 **repeat별 최소 JT의 평균** 사이 상대 감소율이다. 기준은 개선 ≥5%
또는 expanded CT의 어느 gain이든 기존 상한을 기존 범위의 1%보다 크게 초과하면 expanded 채택이다.
기존 bounds 유지는 개선 <5%, 명백한 범위 이탈 없음, front near-overlap을 모두 만족할 때만 허용한다.
Near-overlap은 tracking(JT≤0.01) 및 practical(JT≤0.05) 구간의 paired pooled-range 정규화
bidirectional discrete Hausdorff 거리 ≤0.05가 모든 반복에서 성립하는 것으로 사전 정의했다.
기준 미충족 시 보수적으로 expanded를 채택한다. 이는 통계적 유의성 검정이 아니다.

**결과: {decision["original_mean_min_JT"]:.8f} → {decision["expanded_mean_min_JT"]:.8f} rad,
{decision["min_JT_improvement_pct"]:.2f}% 개선. {decision["expanded_CT_outside_old_count"]}/5회가 기존 bounds 밖.**
따라서 canonical upper bounds를 **[400,200,40]**으로 바꾸고 모든 payload를 재실행했다.
새 CT가 expanded 상한 0.1% 이내인 반복도 {decision["expanded_CT_at_upper_count"]}/5회다.
이 확인은 기존 bounds의 영향을 입증하지만, 확장 후 bounds 독립성이나 전역 최적을 입증하지 않는다.

{markdown(sensitivity_compact)}

![Sensitivity](sensitivity/bounds_sensitivity.png)

점 사이 선은 관측 연결선이다. 상세 gains는 `sensitivity/tracking_extremes.csv`,
고정 JT 예산 0.005/0.01/0.02/0.05 rad의 관측 최소 JE는
`sensitivity/tracking_budget_comparison.csv`에 기록했다. Practical front coverage 및
에너지 극점은 유한 예산 때문에 달라질 수 있다. 빠른 tracking 개선을 front 전체 우월성으로 해석하지 않는다.
자동 분기와 모든 기준은 `sensitivity/decision.json`에 보존했다.

Practical 영역의 coverage와 관측 최소 JE는 다음과 같다. 에너지 쪽 개선을 일괄 주장하지 않는다.

{markdown(sensitivity_practical)}

Tracking-side 정규화 Hausdorff 거리는 {sensitivity_per.tracking_hausdorff.min():.3f}–{sensitivity_per.tracking_hausdorff.max():.3f},
practical-region 거리는 {sensitivity_per.practical_hausdorff.min():.3f}–{sensitivity_per.practical_hausdorff.max():.3f}였다.
모두 사전 near-overlap 기준 0.05를 넘었다. 개별 반복 값은 `sensitivity/per_repeat.csv`에 있다.

## Table 1 — common conditions

{markdown(setup)}

전류는 clipping하지 않고 한계 위반 여부를 기록한다. `feasible`은 평가한 모든 noise rollout에서
전류·각도·속도 및 수치 유효성 제약을 만족했다는 뜻이다. 무한시간 안정성 보증은 아니다.

## Experiment 1 — independent payload fronts

각 payload를 독립 최적화했다. 각 repeat의 initial 10점은 **zero PID 1점 + Sobol 9점**이다.
Anchor도 40회 평가 예산에 포함하며 train/selection에 똑같이 평가한다. 이미 끝난 front에 사후 추가하지 않았다.
Full Pareto front는 practical criterion으로 잘라내지 않는다.
최적화 rollout {manifests["exp1"]["optimization_rollouts"]:,}개,
독립 selection 재평가 {manifests["exp1"]["selection_rollouts"]:,}개.
실행시간 {manifests["exp1"]["elapsed_seconds"]:.1f}초. 아래 SD는 optimization repeats n=5의 변동이다.

{markdown(summary)}

![Figure 1](fig1_full_and_zoom.png)

별표는 실제 초기 설계에서 평가한 zero anchor이다. 각 선은 하나의 독립 반복이며 pooled super-front가 아니다.
JT=약 0.65546 rad, JE=0인 zero PID는 움직이지 않는 baseline으로 남기되 CT/CB/CE 후보에서는 제외했다.

JT≤0.01 rad라는 공통 tracking 예산에서의 관측 최소 JE:

{markdown(fixed_stats.reset_index())}

이 예산은 결과 설명용이며 대표 선택 기준 0.05 rad와 다르다. 정확히 같은 JT에서의 보간이나
연속 front의 추정이 아니다. 빈 구간은 관측 coverage 부족이며 물리적 불가능의 증거가 아니다.

## Steps 3–4 — practical CT/CB/CE selection

**JT≤{threshold:g} rad RMSE(약 {np.degrees(threshold):.3f}°)**를 revised run 전에 설정했다.
이는 **대표 controller 선택용 practical criterion이며 Pareto front 자체를 잘라내지 않는다**.
하드웨어에서 검증한 허용오차는 아니다. Nominal 1 kg의 feasible selection Pareto front에서
이 조건을 만족하고 gains가 [0,0,0]이 아닌 subset만 사용한다.

- CT: minimum JT; ties by JE, Kp, Ki, Kd.
- CE: minimum JE subject to JT≤{threshold:g}; ties by JT, Kp, Ki, Kd.
- CB: 같은 practical subset의 min/max로 JT와 JE를 각각 [0,1]에 정규화하고,
  utopia (0,0)까지 Euclidean distance가 최소인 점. Zero-range 축은 0으로 둔다.
  Ties by JT, JE, Kp, Ki, Kd. 기하학적 knee로 주장하지 않는다.

정확한 정의가 같은 점을 고르면 role 중복을 그대로 보고한다. 이번 선택의 상태:
`{coincident.to_dict()}`. 모든 gains·selection JT/JE·정규화 경계·거리·후보 수는
`representatives_frozen.csv`에 저장했고, 해당 repeat의 target test 평가 전에 동결했다.
Selection 값과 아래의 독립 test 성능은 구별한다.

{markdown(selection)}

![Selection](fig_selection_r00.png)

## Step 5 / Table 2 — primary cross-payload results

Nominal에서 고른 gains를 **retuning 없이 1/2/3 kg**에 적용했다. 각 repeat의 성능은
10개 독립 test seed 평균이며 아래 ±는 그 평균들의 반복 간 SD(n=5)이다.
변화율은 먼저 각 repeat/controller의 1 kg 대비 계산한 뒤 평균했다.
`delta_J_pct = 100*(J(payload)-J(1kg))/J(1kg)`; 0 분모는 undefined로 둔다.
`practical_satisfied`는 test 평균 JT와 물리적 feasibility를 함께 확인하는 별도 진단이다.

{markdown(primary)}

![Primary transfer](fig3_primary_transfer.png)

### Repeat 0 — preselected example

실행 순서상 첫 repeat를 예시로 고정했다. 다른 repeat보다 유리해서 고른 것이 아니다.

{markdown(first)}

![Representative responses](fig2_representative_r00.png)

응답 그림은 repeat 0의 첫 paired test seed이다. 모든 5회 그림과 raw test rollout은 함께 보존했다.

## Supplementary — retention and HV

Retention/HV는 **보조지표**다. Primary evidence는 위 JT·JE·within-controller 변화율·feasibility이다.
전체 nominal front를 전이한 집합을 사용하므로 zero anchor도 포함된다. 모든 local front 역시
같은 anchor를 초기 설계에 포함해 baseline coverage 비대칭을 줄였다. 이것만으로 나머지 front
coverage나 유한 탐색 예산에 따른 불확실성까지 제거되지는 않는다.

{markdown(supplementary)}

R_P는 전이 집합 내부 비지배 유지율, L_HV는 같은 기준점으로 계산한 local 대비 상대 HV 차이(%)다.
음수 L_HV는 유한 예산 local comparator보다 transfer set의 관측 HV가 컸다는 뜻이다.
3 kg HV 변동이나 작은 평균 loss를 강건성 증명의 주 근거로 사용하지 않는다.
기존 `table2_transfer_*` 파일명은 호환용이며 그 내용도 모두 supplementary이다.

## Paper-ready quantitative findings

{findings_markdown}

## Validation and provenance

Pilot의 적분 간격을 절반으로 줄인 비교에서 최대 |delta JE|는
{convergence.delta_JE.abs().max():.3g} J였다. Expanded 대표 gains의 추가 수치 점검,
raw-result cross-check 및 archive checksum 검증은 `VALIDATION.txt`와 `audit/`에 기록한다.
실험 source manifest, config snapshot, seed 목록과 train/selection/test 원자료를 보존한다.
상세 로그에 남은 GP의 small-noise 경고는 고정 variance floor의 수치 경고이며 숨기지 않는다.
Optimizer 오류를 Sobol로 조용히 대체하지 않는다.

## LIMITATIONS

- **No hold:** 5초 전체가 이동이며 종료 후 hold는 없다. Settling time, 정상상태 유지 전력,
  장시간 운전을 평가하지 않는다.
- **Constant gear efficiency:** eta=0.72의 지정 식을 사용한다. 부하·속도 의존 손실과
  GP42C의 실제 역구동 손실/torque rating을 검증하지 않았다.
- **No thermal/backlash/detailed driver model:** 열, backlash, elasticity, 상세 드라이버,
  current loop 및 배터리 효율을 추가하지 않았다. JE는 signed motor-terminal energy이다.
- **Finite-budget and residual bounds:** revised canonical CT {boundary_count}/5회가 expanded 상한에
  접한다. 전역 최적·bounds 독립성·탐색 수렴을 주장하지 않는다. 고정 40회 예산의 front coverage 한계가 있다.
- **Selection criterion:** 0.05 rad는 대표 선택을 위한 연구 설계 기준이며 payload 전이 후의
  충족을 보장하지 않는다. 이 threshold를 만족하지 못한 target 결과도 그대로 보고했다.
- **Model scope:** 시뮬레이션 기반 1-DOF 결과이다. 3-DOF coupled system 및 실물 검증은 수행하지 않았다.

## Reproduction and deliverables

```sh
# Step 1 uses the preserved pre-anchor configs (include_zero_anchor is absent/false).
kroc-mobo exp1 --config configs/sensitivity_original.toml --out results/new-sensitivity/original
kroc-mobo exp1 --config configs/sensitivity_expanded.toml --out results/new-sensitivity/expanded
python -m kroc_mobo.sensitivity --original results/new-sensitivity/original --expanded results/new-sensitivity/expanded --out results/new-sensitivity/analysis
# Current canonical config records the observed expanded decision and the new anchor/selection rule.
kroc-mobo all --config configs/canonical_final.toml --out results/new-canonical
python analysis/build_report.py --out results/new-canonical --sensitivity results/new-sensitivity/analysis --report reports/new-canonical
python analysis/audit_revision.py --out results/new-canonical --audit reports/new-canonical/audit
```

실행/보고서 디렉터리의 기존 결과를 덮어쓰지 않도록 보호한다.
`raw-results.zip`에는 sensitivity 두 arm과 revised canonical의 원자료·traces·logs·source snapshot이 포함된다.
`ARTIFACTS.sha256.json`은 최종 전달 파일 inventory다. 이전 run은 archive와 별도 원본 디렉터리에 보존한다.
"""
    (out / "REPORT.md").write_text(report)
    print(summary.to_string(index=False))
    print(primary.to_string(index=False))
    print("\n".join(findings))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--report", default="reports/canonical-final")
    parser.add_argument("--sensitivity", required=True)
    args = parser.parse_args()
    build(args.out, args.report, args.sensitivity)
