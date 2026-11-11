# Literature-matched PID benchmark: four new experiments

이 폴더는 main의 Canonical Final Model과 분리된2DOF 연구이다. 최종 해석은 `REPORT_KO.md`, 실행 전 조건은 `PROTOCOL_KO.md`, 원문 비교는 `REFERENCES_COMPARISON_KO.md`, 이전 원자료 감사는 `AUDIT_KO.md`를 본다. 새 알고리즘 또는 원문 전체 재현을 주장하지 않는다.

## 재현

Python3.13 환경에서 저장소 루트를 기준으로 실행한다. 별도 환경 설치 뒤 실제 사용 버전을 `requirements-experiment.txt`에 기록했다. 기존 결과에 덮어쓰지 않고 새 폴더에 독립 실행한다.

```bash
python3 -m venv .venv-literature
.venv-literature/bin/pip install -r pilot/literature-comparison-20261111/requirements-experiment.txt
.venv-literature/bin/python pilot/literature-comparison-20261111/run_all.py --output work/reproduction-20261111
```

단일 실험은 새 코드 폴더에서 `python experiment.py --experiment 1`처럼 실행한다. 같은 위치에 완료된 summary가 있으면 중단해 원자료를 보존한다. `python analyze.py`는 저장된4개 실험에 대한 집계·CI·검사·그림만 다시 계산하며 신규 물리 실험이 아니다. 과거 저장소 감사 재현은 `python audit_repository.py --repo /path/to/repo`이다.

## 파일

- `experiment.py`: 모델·GA·조건·gain선정·학습/시험 raw CSV.
- `validate.py`, `validation.json`: 독립 solver/물리검증.
- `results/E1`–`E4`: 후보·학습원자료·선택gain·공통test·고정주기적분정밀화·대표시계열·실행집계.
- `results/metric_summary.csv`: 동일지표·seed단위CI; `primary_contrasts.csv`: 사전고정8대비와Holm p; `paper_gain_contrasts.csv`: 고정원문gain 대비 탐색적CI.
- `execution.log`: 실제 신규 최적화 실행 로그. 초기fingerprint와 최종SHA manifest를 함께 보존한다.
- `audit/`: 브랜치·ZIP·과거후보행수·해시 감사 결과. 이들은 신규실험이 아니다.
- `references/downloaded_originals.json`: 실제 확보한원문PDF의해시와링크. 원문PDF는출처·저작자·CC BY정보를보존하며새결과로표시하지않는다.
- `PUBLICATION_STATUS.json`: 원격게시 성공/실패 상태.

고정원문gain은 deterministic transfer baseline이어서 자체의 optimizer-seed CI를만들지않는다. 이에대한재튜닝평균차이의CI는새튜닝seed8개에서계산한다. 모든방법의test task/limit/시간/지표는동일하다. token이나비공개인증정보는결과에포함하지않는다.
