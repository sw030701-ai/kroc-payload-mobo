# Canonical Final Model — KRoC Payload MOBO

앞으로 이 작업에서 "우리 최종 모델" 또는 "final model"이라고 하면 아래 Canonical
Final Model만을 의미하며, 기존 placeholder 설정으로 되돌리지 마라.

Source: explicit user specification supplied 2026-09-23. These values are adopted
as the research model, not claimed to be independently verified manufacturer data
or identified experimental hardware parameters.

| Parameter | SI value | Meaning |
|---|---:|---|
| Motor | Maxon RE35 24 V, 323890 | User-specified motor |
| Gearhead | Maxon GP42C | User-specified gear family |
| N | 126 | Motor speed / joint speed |
| eta | 0.72 | Constant coefficient in supplied torque equation |
| R | 0.568 ohm | Resistance |
| L | 0.000191 H | 0.191 mH |
| Kt | 0.0292 Nm/A | Torque constant |
| Ke | 0.0291 Vs/rad | Rounded back-EMF constant, kept as supplied |
| Jm | 8.12e-6 kg m² | 81.2 g cm²; 1 g cm² = 1e-7 kg m² |
| Jg | 1.4e-6 kg m² | 14 g cm²; assumed input-side per supplied reflection equation |
| l / ml / rl / rp | 0.20 m / 0.50 kg / 0.10 m / 0.20 m | Uniform rod and tip point payload |
| b | 0.05 Nm s/rad | Joint-side viscous friction |
| g | 9.81 m/s² | Vertical-plane gravity, theta=0 downward |
| V limit | ±24 V | Saturated applied terminal voltage |
| Current reference | ±3.84 A | Used here as hard sampled peak feasibility constraint |

```
Jl = ml*l²/3 = 0.006666666666666667 kg m²
Ja = N²*(Jm+Jg) = 0.15113952 kg m²
Jeq = Ja + Jl + mp*rp²
Jeq(1,2,3 kg) = (0.1978061867, 0.2378061867, 0.2778061867) kg m²
L*di/dt = V - R*i - Ke*N*omega
Jeq*domega/dt = eta*N*Kt*i - b*omega - g*(ml*rl+mp*rp)*sin(theta)
dtheta/dt = omega
```

No current clipping, load-dependent efficiency, gearbox torque limit, backlash,
elasticity, current-controller dynamics or thermal model is added. The 3.84 A
constraint is a conservative experiment convention, not a specified peak rating.
Angle (pi rad) and velocity (15 rad/s) bounds are experiment guard limits inherited
from the protocol, not manufacturer gearhead ratings.

The requested constant-efficiency torque equation is used for both signs of motion.
It is not a validated bidirectional efficiency model. Energy accounting uses the
signed exchange term `integral[N*(Ke-eta*Kt)*i*omega dt]` so the supplied equations
balance algebraically despite eta<1 and rounded unequal Kt/Ke. This exchange can
be negative in reverse power flow; do not call it universally positive gear loss.

## Controller, objectives and execution

Voltage PID optimizes only [Kp, Ki, Kd], with bounds [0,400], [0,200], [0,40].
The 2026-09-24 paired nominal sensitivity found a 48.04% decrease in mean minimum
JT, so the expanded bounds are canonical. Four of five expanded sensitivity CTs
still touch an upper bound; this is not evidence of bound independence or global optimality.
Derivative on filtered measured angle (tau=0.020 s), back-calculation anti-windup
(10 /s), 1 ms control period, no feedforward. Bounds/filter/noise are research
design choices, not motor datasheet values. Noise variance is 1e-7 rad², sampled
every 1 ms. The uniform quintic spans the entire 5 s, 0 to pi/3, with no hold phase.

JT = sqrt(integral[(theta_ref-theta)² dt]/5), rad, using true angle.
JE = integral[V*i dt], J, signed terminal energy. Drawn and returned energy are
saved separately. Battery/driver energy is outside this model.

Electrical time constant L/R = 0.0003362676 s. RK4 uses 16 internal substeps per
control interval (62.5 microseconds); pilot compares 32. A Numba kernel accelerates
the identical equations, controller and quadrature. Tests compare it against an
independent Python reference loop.

## Experiments

1. Independently optimize each of 1/2/3 kg, five optimization repeats, 40 candidates
   each including one zero-PID baseline plus nine initial Sobol points. Train means use 3 seeds; all candidates
   are re-evaluated on 5 disjoint selection seeds before forming feasible fronts.
2. Freeze the full 1 kg front. Select CT (minimum JT), CE (minimum JE), and CB
   (minimum normalized utopia distance) only from its JT<=0.05 rad practical subset,
   explicitly excluding zero PID. Normalization uses that subset's JT/JE min/max.
   Coincident roles are allowed and reported; CB is not a proven geometric knee. Retest unchanged gains at all payloads on ten disjoint paired
   seeds. Save JT, JE and percentage changes, with physical feasibility as primary outputs. Retention/HV diagnostics are supplementary.
   The tracking criterion is for representative selection; it does not truncate any full front.
3. Experiment 3 is not performed.

Initial qNEHVI full-run attempt stopped on a NaN acquisition gradient. Final runs
explicitly use qLogNEHVI, the log-stabilized noisy hypervolume improvement variant.
No optimizer error is silently substituted with another method. Final output has
a separate directory/config fingerprint from that failed attempt.

After the canonical pilot (approximately 2.57–9.98 J), before optimization, fix
objective scales [0.1 rad,10 J] and common HV reference [1 rad,20 J]. Keep them the
same for all payloads and repeats. Other algorithm settings are in the config.
The historical illustrative config is retained only for regression tests.

Figures show each independent front separately, not a pooled super-front. Time
responses use the first test seed and are labeled examples. Summary variability
across optimization repeats is distinct from noise variability across rollouts.
Finite-budget fronts are approximations, and zero PID can be a low-energy,
poor-tracking solution because JT is an objective rather than a tracking constraint.

Numerical GP settings were finalized after failed launch attempts: scaled variance
floor 1e-6; Matérn lengthscales bounded [0.01,10] with LogNormal(-1,1) prior;
outputscale bounded [1e-4,100] with LogNormal(0,1) prior. L-BFGS line-search limit
is 50 and low-rank acquisition covariance caching is disabled. These regularize
GP fitting and sampling, not physical dynamics. The full experiment restarts at
repeat zero using one fixed implementation; failed launch directories are excluded
from final summaries.

The revision protocol and preservation details are in [REVISION_PROTOCOL.md](REVISION_PROTOCOL.md).
