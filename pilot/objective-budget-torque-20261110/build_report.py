from pathlib import Path
import json
import pandas as pd
from run import ROOT,OUT
S=pd.read_csv(OUT/'selected_metrics.csv');R=pd.read_csv(OUT/'paired_contrasts.csv');A=json.loads((OUT/'audit.json').read_text());E=json.loads((OUT/'execution_summary.json').read_text());I=pd.read_csv(OUT/'integration_checks.csv')
def table(df):
    cols=list(df.columns);out=['|'+'|'.join(cols)+'|','|'+'|'.join(['---']*len(cols))+'|']
    for row in df.itertuples(index=False,name=None):
        out.append('|'+'|'.join(f'{v:.6g}' if isinstance(v,float) else str(v) for v in row)+'|')
    return '\n'.join(out)
B=S[(S.phase=='confirmatory')&(S.budget==1024)&(S.task!=0)]
final=B.groupby(['task','condition','objective'])[['rmse','iae','saturation_duty','tracking_feasible','peak_requested','peak_applied']].mean().reset_index()
primary=R[(R.phase=='confirmatory')&(R.metric=='rmse')&(R.a=='IAE')&(R.b=='ITAE')&(R.budget.isin([256,1024]))]
pairs=R[(R.phase=='confirmatory')&(R.metric=='rmse')&(R.budget==1024)&(R.contrast=='objective_x_torque')]
int_summary=I.groupby('kind').relative_change.agg(['min','max',lambda x:x.abs().max()]).reset_index();int_summary.columns=['kind','min_relative_change','max_relative_change','max_abs_relative_change']
budget=pd.read_csv(OUT/'budget_targets_descriptive.csv');T=budget[(budget.phase=='confirmatory')&(budget.target_rmse==.1)].groupby(['task','condition','objective']).first_observed_budget.agg(['count','median','min','max']).reset_index()
text=f'''# KRoC 주제 엄밀 검토 — 실제 반복 실험 결과

최종 권고와 그 이유는 문서 끝의 판정에 기록한다. 이 보고서는 원문 수치 재현 논문이 아니라, 원문 물리 파라미터를 맞춘 보정 모델의 독립 실험이다. 상세 원문검토·실패원인·설계 이유는 [REVIEW_FOUNDATIONS_KO.md](../REVIEW_FOUNDATIONS_KO.md), 사전 조건은 [PROTOCOL.md](../PROTOCOL.md), 실행은 [README.md](../README.md)를 참조한다.

## 실제 완료 규모

총 {A['optimizer_runs']}회 GA, {A['candidate_count']:,}개 candidate evaluations. 탐색용3seed×4목적함수×2토크×256=6,144후보, 확인용10seed×4×2×1,024=81,920후보. Checkpoint에서 train/held-out2궤적의 selected rollout {A['selected_rollouts']:,}회. 본 run 안에서 최종 held-out160조건의 base 재계산160회와 정밀화320회, representative trace2회가 추가된다. 따라서 본 run의 simulator 호출은 후보88,064 + checkpoint1,416 + refinement base160 + refinement320 + trace2 = 89,962회다. 모델검증,원문gain sanity와 실패한 컴파일 호출은 이 합계 밖의 별도 검증이다. 원문gain sanity12회, 모델검증 script 내부3회(재실행 횟수는 로그에 별도), 통계는 추가 simulator 호출이 아니다.

실행 wall time {E['elapsed_seconds']:.2f}초({E['elapsed_seconds']/60:.2f}분), 초기 JIT와 최종파일쓰기 포함. 조합별 시간은 execution_times.csv. 실제 장소는 로컬 컴퓨터이며 GitHub Actions나 실물 로봇에서 실행한 것이 아니다. 처음 numba 컴파일 오류는 initial_compile_failure.log에 그대로 보존했다.

Numerical failure 후보 {A['failed_numerical_candidates']}개, training terminal tracking-feasible 후보 {A['candidate_tracking_feasible']}개. Numerical failure와 tracking infeasibility는 다르다. Final confirmatory held-out numerical failures는 {A['confirmatory_test_numerical_failures']}개. 실패 후보는 failed_candidates.csv에 gain·seed·조건과 함께 보존하며 교체 평가하지 않았다. Candidate budget은 총 simulator 호출수와 구분한다. Validation/test의 추가 rollout은 모든 arm에 같은 수다.

## 공정성과 독립성

초기32gain이 seed 내8조건에 정확히 같음을 archive로 검사했다. 선택gain은 해당 objective의 해당 budget까지의 최소 training score와 일치하고, own training incumbent는 모두 단조 개선했다. 실패·중복 후보도 예산에 포함된다. Gains가 upper/lower1% 경계에 붙는 비율은 audit.json을 참조한다. 최적해/탐색공간 충분성이나 수학적 전역 안정성은 보장하지 않는다. 동일 trajectory의 sample5000개를 통계 반복수로 쓰지 않았다. n=10은 optimizer seed 수다.

## 최종 예산1,024에서의 공통 독립 시험

Task1=새 계단[.8,.7]rad, Task2=새 quintic[1.2,.3]rad/2초 이동. 각 값은 독립 optimizer10seed의 산술평균이다. Saturation duty는 두 관절×전체 sample 중 requested/applied가 다른 비율이다. Tracking feasibility는 마지막 sampled error가 두 관절 모두≤.02rad인 비율이다. 이 조건은 전구간 safety constraint가 아니다. Peak는 각 rollout 최대 토크의 seed 평균이고, 어느 특정 actuator 정격이 아니다.

{table(final)}

서로 다른 objective의 raw 최솟값은 단위가 달라 비교하지 않는다. 이 표는 모두 같은 RMSE·IAE·토크 지표다. Raw 후보의 네 적분값은 candidates.csv.gz, 선택 gain과 모든 체크포인트 지표는 selected_metrics.csv에 있다. 정착시간은 두 관절이 .02rad 범위에 들어와 마지막 sample까지 유지하는 최초 시간, 미정착은 NaN으로 censor한다. 부드러운 궤적의 정착시간/오버슈트도 NaN이다. Metric summary의 count는 유효값 수이므로 정착한 경우만의 평균을 전체 정착성능처럼 해석하지 않는다.

## 사전에 정한 IAE–ITAE 비교 및 교호작용

아래 a=IAE,b=ITAE, nominal/reduced의 mean은 **ITAE−IAE RMSE**이다. 음수면 ITAE가 낮다. objective_x_torque는 (ITAE−IAE)reduced−(ITAE−IAE)nominal이다. 목적함수 차이가 토크 조건에 따라 달라지는지를 직접 추정한다. objective_x_budget은 최종budget과32회의 차이이고, 3way는 그 torque 대비까지의 차이다. 단순히 한 조건에서 p<.05이고 다른 조건에서 p>.05라는 이유로 교호작용을 주장하지 않는다.

{table(primary[['task','budget','contrast','n','mean','ci_low','ci_high','sign_flip_p','holm_p']])}

CI는 seed단위 paired bootstrap10,000회, unadjusted95% percentile 구간이다. Sign-flip p는 paired contrast의 부호 교환에 대한 정확 열거이며 대칭성 가정이 필요하다. Holm은 같은 task/metric/budget/contrast의6목적함수쌍에 적용했고, 모든 budget·task를 한꺼번에 보정한 것은 아니다. 따라서 다수의 보조 결과를 확증적 발견으로 과장하지 않는다. 모든 RMSE·IAE 쌍별 대비와 실제 seed별 contrast는 각각 paired_contrasts.csv,paired_seed_values.csv에 있다.

최종1,024회의4목적함수 전체 torque교호작용:

{table(pairs[['task','a','b','mean','ci_low','ci_high','holm_p']])}

## 목적함수별 필요한 예산

공통 RMSE .1rad에 최초 도달한 **관측 checkpoint**의 요약이다. Count는10seed 중 도달한 수, median/min/max는 도달한 seed만의 값이다. 미도달은 예산1024보다 크거나 이 설정에서 불가능할 수 있다. .05rad도 원자료에 있다. 이 threshold는 결과 요약용 추가 기술통계이며 연구 채택을 정한 사전 기준은 아니다. Test를 보고 gain을 재선택하지는 않았다. Checkpoint 간의 정확한 최소 예산, 하드웨어 시험 비용,실시간 최적화 가능성을 뜻하지 않는다.

{table(T)}

## 수치·물리 검증

{table(int_summary)}

plant_refined는 controller dt=.002s를 유지하고 RK4 h=.001→.0005s, controller_refined는 controller dt=.002→.001s와 plant h=.001→.0005s를 함께 바꾼 것이다. 후자는 순수 ODE 오차와 sampled controller 변경을 구분해야 한다. 모든 최종 gain×두 held-out 궤적을 검사했고 상대변화 개별값은 integration_checks.csv에 있다. 정밀화에서 controller를 재최적화하지 않았다.

질량행렬의 양의 정부호, C의 kinetic-energy identity, G의 potential gradient, 정적중력 평형, 결정론적 동일trace, saturation 실제적용 검사를 통과했다(model_checks.json). 원문 인쇄 C·G의 일관성 결함도 수치 residual로 저장했다. 이 검증이 저자 실제 코드에 대한 오류 판정이나 모든 gain의 안정성 증명은 아니다.

## 산출물과 재현

![예산별 공통 RMSE](budget_rmse.png)

![IAE–ITAE 토크 교호작용](interaction.png)

![사전 고정 예시의 requested/applied torque](trace.png)

그림의 budget errorbar는10seed 평균±SE이고 interaction errorbar는 paired bootstrap95%CI다. 예시 trace는 사전 고정seed201/IAE/budget1024/held-out step이며 가장 예쁜 결과를 골라낸 것이 아니다. 모든 결과를 그림 한 장에서 추론하지 말고 CSV를 함께 확인한다.

주요 파일: candidates.csv.gz, selected_metrics.csv, metric_summary.csv, paired_contrasts.csv, paired_seed_values.csv, integration_checks.csv, failed_candidates.csv, execution_summary.json, execution_times.csv, audit.json, model_checks.json, paper_gain_sanity.csv, trace_*.csv.gz. Config/seed/전체 dependency freeze/실행명령은 상위폴더에 있다. SHA256 manifest로 파일 무결성을 확인할 수 있다.

## KRoC4페이지 구성과 기여의 한계

1페이지: 문제와 기존 연구 중복, 제한된 토크 여유/평가예산에서 목적함수 선택이라는 질문. 2페이지: 보정 모델·PID·고정GA·조건·독립seed·train/test와 통계. 3페이지: 공통 RMSE의 budget곡선과 최종 feasibility/포화 표. 4페이지: paired 교호작용과 해석·한계·결론·참고문헌. 원문 재현 성공이나 신규최적화알고리즘을 주장하지 않는다. 표와그림을 줄여도 seed수/조건 선택 근거/재현범위는 생략하지 않는다.

실물 검증이 없고 한point-mass plant·두test궤적·한GA·고정bounds에 한정된다. 현실의 마찰,모터전기동역학,기어/센서/전류/열·충돌 제약을 검증하지 않았다. 토크값은 하드웨어 식별값이 아니다. 목표 진폭과 horizon 변경·gain bounds 민감도도 아직 검증하지 않았다. 따라서 보정모델에서 큰효과가 보여도 일반적인 로봇팔 목적함수 추천으로 확장할 수 없다.
'''
(OUT/'REPORT_KO.md').write_text(text)
print('Wrote',OUT/'REPORT_KO.md')
