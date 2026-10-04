# 양자얽힘 (Quantum Entanglement)
## 개요
Qiskit으로 양자얽힘 상태를 직접 만들어 보고, 정말 고전적으로 설명할 수 없는 상관관계가 나오는지 시뮬레이션으로 확인하는 프로그램.

## 설명
- `build_bell_circuit`: H 게이트 + CNOT 게이트로 벨 상태 |Φ+> = (|00> + |11>) / √2 를 만든다.
- `build_ghz_circuit`: n개 큐비트 GHZ 상태 (|00...0> + |11...1>) / √2 를 만든다.
- `entanglement_entropy`: 한 큐비트의 축소 밀도행렬 엔트로피를 계산한다. 최대 얽힘이면 1 bit, 얽히지 않았으면 0 bit.
- `chsh_value`: CHSH 부등식 값 S 를 계산한다. 고전 이론은 |S| ≤ 2 이지만 양자역학은 2√2 ≈ 2.828 까지 나온다.

## 실행 방법
```
pip install -r requirements.txt
python main.py      # 시뮬레이션 실행
pytest              # 테스트 실행
```

## 메모
- 벨 상태를 측정하면 항상 두 큐비트가 같은 값(00 또는 11)으로만 나온다. 01, 10은 절대 안 나옴.
- CHSH 값이 2를 넘는다는 것은 "측정 전에 이미 값이 정해져 있었다"는 국소 숨은 변수 이론으로는 설명이 안 된다는 뜻.

## 실행 결과
```
     ┌───┐     ┌─┐
q_0: ┤ H ├──■──┤M├───
     └───┘┌─┴─┐└╥┘┌─┐
q_1: ─────┤ X ├─╫─┤M├
          └───┘ ║ └╥┘
c: 2/═══════════╩══╩═
                0  1
Bell state counts (10000 shots): {'11': 4934, '00': 5066}
Entanglement entropy of qubit 0: 1.0000 bit
GHZ(3) counts (10000 shots): {'000': 5007, '111': 4993}
CHSH S value: 2.8210 (classical limit 2, quantum limit 2.8284)
```
