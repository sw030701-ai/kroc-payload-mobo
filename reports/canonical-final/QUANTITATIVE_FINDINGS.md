# Quantitative findings

각 ±는 optimization repeats n=5의 SD. 각 repeat 성능은 test seeds 10개의 평균.

1. 1 kg paired bounds 비교에서 5회 평균 최소 JT는 0.0031232→0.0016229 rad로 48.04% 감소했다. Expanded CT 5/5회가 기존 범위 밖이며 4/5회는 새 상한에 접했다.

2. Revised independent fronts에서 JT≤0.01 rad를 만족하는 관측 최소 JE의 평균±SD는 1 kg: 2.4835±0.0031 J; 2 kg: 5.5668±0.0299 J; 3 kg: 9.6770±0.0419 J. 이는 공통 tracking 예산 비교이며 같은 JT에서의 보간값이 아니다.

3. Retuning 없는 CT의 3 kg JT는 0.0019688 ± 8.7624e-05 rad이고, 같은 controller의 1 kg 대비 JT 변화율은 24.75 ± 1.072%, JE 변화율은 276.5 ± 0.08758%였다.

4. CE의 3 kg JT는 0.018952 ± 0.0054871 rad였다. 3 kg에서 CT 대비 CE 에너지 절감률은 2.691 ± 1.653%였다. Practical criterion 충족은 5/5회로 별도 보고한다.

5. 모든 payload/repeat의 초기 설계 15/15개에 zero-PID anchor가 포함되었고 대표 선택의 zero PID는 0개였다. 대표 test 조건의 물리적 feasibility는 45/45, JT≤0.05 rad까지 충족한 조건은 45/45였다.
