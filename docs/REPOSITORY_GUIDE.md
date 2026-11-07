# 최종 저장소 구성과 보존

2026년 11월 7일 제공된 논문 원고를 기준으로 main을 정리했다. 연구 기준은 revision 4 commit `9a27fd0569f2bb9f03b21666192028a53e3298fa`이다. 물리 모델·본실험 수치·선정 gain은 변경하지 않았다.

## 보존한 자료

현재 보고서 `reports/canonical-final/`과 `reports/heavy-diagnostics-20261001/`에는 CSV, 그림, source/config/manifest 및 원자료 ZIP이 있다. `results/`는 계산 출력이며 Git에 추가하지 않는다. 각 원자료 ZIP을 열어 저장 당시 디렉터리 구조를 확인한 뒤 해당 경로에 풀어야 기존 감사·후속 실행이 가능하다.

## main에서 제거한 자료

`reports/archive/` 아래 세 세대 과거 보고서·중복 그림·과거 원자료 ZIP과 해시 목록은 보존 태그로 옮겨 main 작업 트리에서 제거했다. Git 이력 자체를 삭제하거나 저장소 용량 회수를 위한 이력 재작성을 한 것은 아니다. 최종 코드의 회귀 테스트에 필요한 illustrative 설정 및 과거 진단을 재현하는 코드는 유지했다.

원본 로컬 연구 저장소와 동기화된 sources는 편집하지 않았으며, 별도의 final-github 체크아웃에서 정리했다.

## 과거 감사와 보고서 재생성

일부 과거 감사 스크립트는 이전 보고서의 SHA256 보존 검사도 수행한다. 전체 감사를 다시 실행하려면 다음과 같이 archive를 먼저 복구한다. 복구 후에는 새 출력 경로를 사용한다.

```bash
git restore --source archive/pre-final-20261107 -- reports/archive
```

이는 의도적인 보존 의존성이다. archive가 없는 상태에서 해당 스크립트가 실패하면 검사를 제거하거나 성공으로 간주하지 않는다. 저장된 감사 기록은 당시 전체 archive가 존재하는 상태에서 실행한 기록이다.

## 논문과 추가 pilot 구분

`paper/KRoC_Payload_MOBO_4p.docx`는 사용자가 제공한 파일을 바이트 그대로 복사했다. 원고 Table 3·4·5의 값은 기존 80회 본실험이다. 10월 23일 pilot은 추가 검증이며 기존 표에 대체하지 않는다. 논문 최신 내용과 이전 Google Docs 초안의 지적을 혼동하지 않는다.
