# Implementation validation — 2026-09-22 KST

**PLACEHOLDER / illustrative. 아래는 구현 검증 기록이며 논문용 결과가 아니다.**

- Python 3.13.1, macOS ARM64, CPU double precision.
- BoTorch 0.17.2, GPyTorch 1.15.2, PyTorch 2.14.0. 전체 설치 버전은 `requirements-lock.txt`.
- `pytest -q`: 19 tests passed. qNEHVI와 qLogNEHVI의 실제 GP fitting/acquisition 최적화, 빈 local front와 전체 transfer 실패 처리를 포함.
- `ruff check src tests experiments analysis`: passed.
- `kroc-mobo all --smoke --out results/smoke-qnehvi`: pilot, Exp. 1, Exp. 2, 그림·표 생성까지 완료.
- 실제 qNEHVI 후보 6개: payload 3개 각각 Sobol 초기 4개 이후 BO 2개. Sobol fallback 없이 실행.
- Exp. 1: train 36 rollout + selection 36 rollout. Exp. 2: test 24 rollout + 대표 시간응답 9개. Nominal/local 동일 gain의 중복 rollout은 cache로 공유.
- Nominal selection front 3개로 CT/CB/CE를 서로 다르게 선택, 이득 고정 확인.
- 총 13종 그림을 PNG(300 dpi) 및 PDF로 생성. Fig. 1/2를 시각적으로 검사.

## 자동 검증의 내용

Quintic 끝점, payload별 관성, DC 방정식, 무입력 평형, 전력·에너지 수지, 실제 각도 기준 JT, RK4 간격 수렴, seed 재현성, 전류를 clip하지 않는 한계 판정, numerical-failure objective 제외, anti-windup, Pareto 동률/NaN, 수작업 HV 예제 및 BoTorch 교차 검증, 두 retention 정의, 음의 HV loss, CB 선택, 원본 설정 보존, 후보 예산, 고정 transfer gain, 같은 초기 탐색점, 전체 파일·분석 연결을 검사했다.

## 관측과 한계

수동 balanced controller의 1 kg 검증 rollout에서 JT 약 0.0230 rad, JE 약 17.35 J, energy-balance residual 약 −6.9e−9 J였다. Pilot의 9개 조합에 대해 내부 RK4 간격을 절반으로 줄였을 때 최대 |ΔJT| 약 9.9e−9 rad, 최대 |ΔJE| 약 3.4e−5 J였다. 이는 **내부 적분 간격**에 관한 검사이며 제어 sampling 주기 자체의 수렴 증명은 아니다.

예시 aggressive PID는 1 kg에서 실행 불가능했고, 결과를 그대로 기록했다. 작은 탐색 예산에서는 transfer가 local comparator보다 높은 HV를 보여 loss가 음수였다. 이는 유한 탐색과 임시값의 예시이며 payload 증가 시 성능 악화 또는 특정 controller 우수성의 근거로 일반화할 수 없다.

BoTorch는 legacy qNEHVI의 수치 문제를 안내한다. 구현은 요청된 qNEHVI를 기본으로 유지하고 qLogNEHVI 옵션을 제공한다. GPyTorch는 매우 작은 표준화 관측 분산을 내부 minimum에 맞춰 조정할 수 있다. 이 경고와 실행 패키지 버전을 보존한다. 대규모 실험 전에 pilot에서 acquisition과 GP 설정을 확정해야 한다.

기본 40후보 × 3 payload × 5반복의 전체 실험, 실제 하드웨어 검증, parameter identification은 아직 수행하지 않았다. CI 설정은 저장소에 포함되어 있으며 클라우드 실행 성공 여부는 별도 확인 대상이다. 로컬 최초 smoke 실행은 Git 초기 commit 전이어서 manifest revision이 `uncommitted`이다.
