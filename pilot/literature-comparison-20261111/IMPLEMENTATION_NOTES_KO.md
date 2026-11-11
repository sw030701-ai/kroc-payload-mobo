# 구현·도구 이력

- 최초 설치 요청에 PDF 렌더링 라이브러리의 불필요한 대형 의존성이 포함되어 중단하고, numba/numpy/pypdf만 설치했다. pandas/scipy/matplotlib은 기존 시스템 설치를 사용한다. 모델 실험 실행 전의 환경 준비이며 완료된 실험 삭제·재실행은 없다.
- 원문 publisher HTML 다운로드는 MDPI 403, Nature 웹 도구 인증 redirect로 실패했다. 출판사 static PDF 및 curl 경로에서는 Eltayeb/Azeez 원문 확보에 성공했다. 접근 실패와 성공을 구분한다.
- 일반 git clone은 DNS 오류로 실패했고 네트워크 허용 경로의 clone은 성공했다.
- GitHub repository metadata는 push=true를 반환했으나 create_branch는 403 Resource not accessible by integration으로 실패했다. 로컬 gh auth status도 일반 제한 환경에서는 invalid token을 표시했다. 이후 네트워크 허용 환경에서는 같은 기존 계정의 정상 로그인과 repo scope를 확인했다. connector403과 로컬 환경 오류를 구분하며, 최종 원격 게시 상태는 별도로 검증한다.
- GitHub Fetch의 Actions artifacts collection URL은 허용된 endpoint가 아니라는 400을 반환했다. 이 경로의 artifact 존재 여부를 감사 완료라고 하지 않는다. Releases는 빈 목록이었다.
- 후속으로20개 Actions run을조회하고각run의전용artifact도구를사용했다. 모두artifacts=[]였다. 따라서처음의collection접근실패와달리run별첨부검색은완료했으며오늘stage파일은없었다.
- 기존 PR1 해시 manifest는 results 디렉터리 기준, PR2/3은 실험 루트 기준이다. 처음 감사 스크립트는 PR1의 기준 경로를 잘못 적용해 missing을 출력했다. 기준 경로를 수정한 뒤 PR1 130개/PR2 47개/PR3 43개 hash가 모두 일치했다. 이는 파일 누락이나 연구 실패가 아니었다.
- 신규 실행 시작 뒤 분석 코드에서 실패 rollout의 objective를 1e12로 복원하는 검사를 모든 목적함수에 적용하도록 수정했다. 실행 모델·gain 선택·예산·seed는 변경하지 않았다. 최초 fingerprint의 analyze.py 해시와 최종 해시가 다른 이유다. 결과 유리성을 위한 변경이 아니다.
- 같은분석코드에고정원문gain대비seed단위CI를추가했다.사전primary8개대비는변경하지않고gain-transfer추가비교는탐색적으로표기한다.
- main핵심Gulbahce원문PDF는timeout·resume미지원·인증HTML로실패했다.이후ResearchGate의publisher제공전문으로방법절·표·식접근을보완했다.PDF파일로보존했다고주장하지않는다.
- 통계 설계의 제한: n=8의 양측 exact sign-flip 최솟값은2/256=.0078125다. primary8개 Holm의 첫 단계는최소.0625이므로5%familywise기각은불가능하다. CI는보정하지않은탐색적기술구간으로해석한다. 결과를본뒤표본수나primaryfamily를바꾸지않았다. p비유의를동등성증거로해석하지않는다.
- PEN의 overshoot 벌점은 step 학습에만 적용된다. Quintic은 step overshoot를 정의하지 않아0으로 처리한다. 이는실행전experiment.py에고정된동작이며,실행후수식이나점수를변경하지않았다. smooth에서오버슈트를전혀평가하지않아도좋다는일반적제어지침은아니다.

- 로컬 GitHub 로그인 경로로 별도 연구 브랜치 push와 [초안 PR #4](https://github.com/sw030701-ai/kroc-payload-mobo/pull/4) 생성을 완료했다. GitHub 연결 도구의 403은 위에 보존했다. 원격 main SHA는 작업 전후 동일하다.
- Git 검사에서 원본 PDF를 텍스트로 판정하고 CSV의 CRLF를 공백 오류로 오인해, 이 폴더에만 `.gitattributes`를 추가했다. 원본 PDF와 raw CSV의 바이트는 수정하지 않았다.
