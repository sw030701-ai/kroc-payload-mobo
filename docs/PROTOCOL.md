# 실험 프로토콜

모든 기본 설정은 **PLACEHOLDER / illustrative**이다. 연구 질문의 긍정적인 결과를 보장하지 않는다.

## 실행 전 동결할 사항

| 설정 | 확인할 근거 |
|---|---|
| Jm, Jl, ml, rl, rp | CAD, 관성 식별 또는 측정; Jl에 payload를 중복 포함하지 않기 |
| R, L, Kt, Ke | 데이터시트/식별, 온도, SI 단위, 전기·기계 power 변환 |
| b, gravity | 회전면과 마찰 모델; Coulomb 마찰은 현재 미포함 |
| Vmax, Imax, angle/velocity limits | 모터·드라이버 정격과 시험 범위 |
| trajectory, initial state | 초기 아래쪽 수직, 정지·무전류; 5초 rest-to-rest quintic |
| noise | power/sample_dt convention; train/selection/test의 분리 |
| PID filter/anti-windup | 전압 입력에 맞는 gain 단위, 고정된 구현 주기 |
| gain bounds, scales, reference | pilot 이후 확정; 모든 payload/repeat에 공유 |
| budget and repeats | 성공·실패 모두 동일하게 비용에 포함 |

현재 `simulation.duration`은 이동 시간과 평가 시간을 함께 정한다. 별도 hold 구간은 없다. PID qf 초기값은 θ0, 적분 전압 z=0, 전류=0, 속도=0이다. 초기각을 바꿔도 초기 중력 보상이나 feedforward를 추가하지 않는다.

## 수치 검증

Pilot의 `integration_convergence.csv`는 **제어 주기와 동일 잡음열을 유지**한 채 내부 RK4 substeps를 2배로 늘린다. 제어 주기 자체의 수렴은 별도 config에서 `control_dt`를 절반으로 줄이고 `noise.sample_dt`를 원래 값으로 유지해 검사할 수 있다. 시간 간격 변경 결과를 이전 run에 덮어쓰지 않는다.

전류를 제한해 feasibility를 만족시키는 모델이 아니다. 한계 위반을 별도 제약 관측으로 기록한다. 수치 발산은 objective NaN, infeasible 처리한다. GP 제약의 numerical-failure 관측값 +1은 실제 물리적 초과량이 아니라 실패 표지라는 점을 구분한다. 현재 numerical failure 부근의 constraint GP는 연속 surrogate의 근사이며 전역 안정성 또는 안전 보증을 제공하지 않는다.

고정 seed와 CPU double precision을 사용하지만, 운영체제·BLAS·라이브러리 변경에 따른 비트 단위 동일성을 약속하지 않는다. 실행별 manifest와 lock 파일을 함께 보존한다.

## 선택 편향과 transfer

1. Training objective에는 train seed 평균만 사용한다.
2. Exp. 1은 평가한 모든 gain을 selection seeds로 재평가한다. Feasible validation front가 각 반복의 local set이다.
3. Nominal local set을 P0로 동결한다. 같은 nominal 목적값으로 CT/CB/CE를 선택하고 먼저 CSV에 기록한다.
4. P0의 **모든 controller**를 각 payload의 동일 test seeds에서 재평가한다. Target outcome으로 대표 controller를 다시 고르지 않는다.
5. 해당 target의 local set도 같은 test seeds에서 재평가한다. Local set과 transfer set의 평가 잡음 차이를 optimizer 차이로 해석하지 않는다.
6. Internal retention과 union retention을 분리해 보고한다. Feasibility 실패는 분모 N0에서 제거하지 않는다.
7. Fresh test에서 nominal retention도 감소할 수 있다. 이를 100%로 보정하지 않는다. HV loss<0도 보존한다.

Exp. 2의 local comparator는 Exp. 1에서 동결된 selection front를 test seed로 재평가한 것이다. Test 결과를 본 뒤 Exp. 1의 다른 후보를 추가하거나 새로 최적화하지 않는다.

## 논문 그림·표

- Figure 1: payload별 selection front, repeat별 별도 선, 공통 raw JT/JE 축.
- Figure 2: nominal CT/CB/CE의 payload별 오차 및 누적 순에너지. Caption에 repeat ID와 첫 paired test seed임을 명시.
- Table 1: config에서 생성한 setup CSV를 원고 공간에 맞게 요약하고 임시값을 최종 근거 값으로 교체.
- Table 2: N0/Nret, internal retention, union retention, HV loss, feasible count. Repeat별 값과 반복 간 요약을 구분.
- 대표 controller 표: 고정 gain, 평균±표준편차, 단위 있는 변화량, 적용 가능한 경우 백분율, 한계 위반.

1회 반복에서는 반복 간 std가 NaN인 것이 정상이다. CSV의 std/SEM는 센서 잡음에 대한 것이고, Table 2 집계 std는 optimization 반복 간 변동이다. H1/H2/H3를 지지하지 않는 결과나 퇴화한 front도 그대로 남긴다.
