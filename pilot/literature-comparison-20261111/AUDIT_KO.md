# 저장소·이전 대화 감사

기준일: 2026-11-11 KST. main=d18b00d2e7093cf5cb1b9cb10e9d70c4e3a9038e. 전체 clone으로 origin의 main 및 연구 브랜치 6개, PR #1–#3을 확인했다. `audit/branch_inventory.json`에 각 SHA와 파일 수, ZIP 목록을 저장했다. PR #3은 main이 아니라 PR #2 브랜치를 base로 삼는다. 이번 연구는 main에서 분기한 독립 브랜치이므로 이전 PR 코드를 덮어쓰지 않는다.

## 확인 가능한 증거

|구분|확인 결과|신규 실험 횟수 포함|
|---|---|---|
|main 4페이지 원고|1DOF 전압 PID, qLogNEHVI, RMSE–signed terminal energy, 1/2/3kg 전이. 최신 문서와 kernel/선정 규칙을 대조했고 canonical artifact110개 hash가 일치했다.|아니오|
|PR #1|후보 CSV 384행, optimizer seed731–733. 결과 기준 manifest130개 hash 일치.|아니오|
|PR #2|후보 CSV88,064행, seed101–103/201–210. manifest47개 일치.|아니오|
|PR #3|후보 CSV24,576행, seed301–308. manifest43개 일치.|아니오|
|오늘 1차|대화 본문은 신규 최적화가 없는 문헌·데이터 감사라고 명시.|아니오|
|오늘 2차|대화 본문은 seed501–504,32최적화,4,608후보를 주장. 원 ZIP/CSV는 미확보.|아니오|
|오늘 3차|대화 본문은 2차 gain을 재사용한 배포768회라고 명시. 원 ZIP/CSV는 미확보.|아니오|
|오늘 4차|대화 본문은 seed601–605,40최적화,5,120후보를 주장. 원 ZIP/CSV는 미확보.|아니오|
|오늘 5차|대화 본문은 bootstrap 재분석. 신규 최적화가 아니며 원 통계 코드/CSV는 미확보.|아니오|

이전 대화 본문은 읽기 도구로 회수해 로컬 작업 기록에만 보존했다. 공개 PR에는 대화 원문을 포함하지 않았다. 첨부 목록은 비어 있었다. 링크는 `sandbox:/mnt/data/...`여서 이 실행 환경의 파일 경로가 아니다. 사용자가 저장소에서 찾아보라고 지시한 뒤 모든 브랜치 tip, Git 추적 이력의 stage명/날짜, 28개 ZIP의 내부 목록과 releases를 확인했다. 해당2–5차 파일은 발견되지 않았다. 따라서 이전 수치를 조작·허위라고 판정하지도, 원자료 검증 완료라고 판정하지도 않는다. 원자료 부재는 미해결 감사 항목이다.

manifest 일치는 저장된 파일의 무결성 근거이며, 과거 전체 최적화를 독립 재실행한 증거는 아니다. 이번 감사에서 과거 결과를 신규 실행으로 합산하지 않았다. 기존 gain을 baseline으로 호출한 횟수도 신규 튜닝 후보 수에 포함하지 않는다.

추가로20개Actions run의artifact목록을각각조회했으며모두빈목록이었다.원본응답은`audit/actions_artifact_search.json`에보존했다.과거Git이력의추적파일명에서도해당stage명/날짜는발견되지않았다.

## main과 후속 주제의 차이

main 원고의 nominal CT=[800,400,0]이며 3kg 전이에서 peak current 기준을5반복 중2회 위반했다는 문서와 요약표가 일치한다. kernel은 ±24V 적용전압 clipping, 내부 RK4 소구간의 peak state 기록, signed V*i 적분을 사용한다. `metrics.py`는 infeasible 전이를 유지율 분모에 남기고 practical subset에서 CT/CB/CE를 고른다. 이는 주석·문서 정의와 일치하는 코드 감사이며 전체 원자료의 독립 재최적화는 아니다.

main의 전압포화0%를 토크포화 활성의 증거로 바꾸어 해석하면 안 된다. 후속2DOF 모델은 모터전기회로·전류제약·signed terminal energy가 없어서 main의1DOF 추종–에너지 주장을 직접 대체하거나 검증하지 못한다. 이번 연구의 applied torque RMS는 에너지(J)가 아니다.

main 설명의 user-specified motor/gear 수치는 실물식별·제조사 독립검증 수치로 간주하지 않는다. 이번2DOF 물리값·torque limit도 하드웨어 정격이라고 주장하지 않는다. 원고의 저자/소속 placeholder는 아직 남아 있다. 신규성·원문 직접비교·실물모델 타당성을 보완하지 않은 상태에서 제출 가능하다는 판정은 하지 않는다.

## 접근 및 쓰기 상태

GitHub 읽기는 성공했다. metadata의 push=true와 달리 원격 branch create는403 `Resource not accessible by integration`이다. 로컬 gh는 일반 제한 환경에서 invalid token을 표시했으나 네트워크 허용 환경에서는 기존 로그인이 정상으로 확인됐다. 따라서 로컬 Git 경로로 게시를 진행하며, 성공 여부는 최종 원격 SHA 및 PR로 별도 검증한다. 일반 네트워크 clone DNS실패 후 허용된 네트워크 경로에서 clone 성공. 도구별 오류와 이후 상태는 `IMPLEMENTATION_NOTES_KO.md` 및 최종 게시 상태를 참고한다.
