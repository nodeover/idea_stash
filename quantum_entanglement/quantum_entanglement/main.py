"""Qiskit으로 양자얽힘(벨 상태)을 만들고 측정하는 프로그램."""

from math import pi

from qiskit import QuantumCircuit, transpile
from qiskit.quantum_info import Statevector, partial_trace, entropy
from qiskit_aer import AerSimulator


def build_bell_circuit(measure=True):
    """벨 상태 |Φ+> = (|00> + |11>) / √2 를 만드는 회로를 반환한다.

    1. 0번 큐비트에 하다마드(H) 게이트를 걸어 중첩 상태를 만든다.
    2. 0번 큐비트를 제어, 1번 큐비트를 대상으로 CNOT 게이트를 걸어 얽힘을 만든다.
    """
    qc = QuantumCircuit(2, 2)
    qc.h(0)
    qc.cx(0, 1)
    if measure:
        qc.measure([0, 1], [0, 1])
    return qc


def build_ghz_circuit(num_qubits=3, measure=True):
    """n개 큐비트 GHZ 상태 (|00...0> + |11...1>) / √2 회로를 반환한다."""
    if num_qubits < 2:
        raise ValueError("GHZ 상태는 큐비트가 2개 이상 필요합니다.")
    qc = QuantumCircuit(num_qubits, num_qubits)
    qc.h(0)
    for target in range(1, num_qubits):
        qc.cx(0, target)
    if measure:
        qc.measure(range(num_qubits), range(num_qubits))
    return qc


def get_statevector(circuit):
    """측정 없는 회로의 상태벡터를 반환한다."""
    return Statevector.from_instruction(circuit)


def entanglement_entropy(circuit, qubit=0):
    """주어진 큐비트의 축소 밀도행렬 폰 노이만 엔트로피(bit 단위)를 반환한다.

    최대로 얽힌 2큐비트 상태라면 1.0, 분리 가능한 상태라면 0.0이 나온다.
    """
    state = get_statevector(circuit)
    others = [q for q in range(circuit.num_qubits) if q != qubit]
    reduced = partial_trace(state, others)
    return float(entropy(reduced, base=2))


def run_counts(circuit, shots=10000, seed=None):
    """AerSimulator로 회로를 실행하고 측정 결과 횟수를 반환한다."""
    simulator = AerSimulator(seed_simulator=seed)
    compiled = transpile(circuit, simulator)
    result = simulator.run(compiled, shots=shots).result()
    return result.get_counts()


def chsh_circuits():
    """CHSH 부등식 검증용 네 가지 측정 기저 조합 회로를 반환한다.

    Alice(0번 큐비트) 기저: a=0, a'=π/2
    Bob(1번 큐비트)  기저: b=π/4, b'=3π/4
    각 큐비트를 Y축으로 -θ 만큼 회전한 뒤 Z 기저로 측정하면 θ 방향 측정과 같다.
    """
    settings = {
        "ab": (0, pi / 4),
        "ab'": (0, 3 * pi / 4),
        "a'b": (pi / 2, pi / 4),
        "a'b'": (pi / 2, 3 * pi / 4),
    }
    circuits = {}
    for name, (theta_a, theta_b) in settings.items():
        qc = build_bell_circuit(measure=False)
        qc.ry(-theta_a, 0)
        qc.ry(-theta_b, 1)
        qc.measure([0, 1], [0, 1])
        circuits[name] = qc
    return circuits


def correlation(counts):
    """측정 결과로부터 상관값 E = P(같음) - P(다름) 을 계산한다."""
    total = sum(counts.values())
    same = counts.get("00", 0) + counts.get("11", 0)
    diff = counts.get("01", 0) + counts.get("10", 0)
    return (same - diff) / total


def chsh_value(shots=10000, seed=None):
    """CHSH 값 S = E(a,b) - E(a,b') + E(a',b) + E(a',b') 를 계산한다.

    고전(국소 숨은 변수) 이론은 |S| <= 2 이고,
    양자역학은 최대 2√2 ≈ 2.828 까지 가능하다.
    """
    circuits = chsh_circuits()
    e = {name: correlation(run_counts(qc, shots, seed)) for name, qc in circuits.items()}
    return e["ab"] - e["ab'"] + e["a'b"] + e["a'b'"]


if __name__ == "__main__":
    shots = 10000

    bell = build_bell_circuit()
    print(bell.draw(output="text"))
    print(f"Bell state counts ({shots} shots): {run_counts(bell, shots)}")
    print(f"Entanglement entropy of qubit 0: {entanglement_entropy(build_bell_circuit(measure=False)):.4f} bit")

    ghz = build_ghz_circuit(3)
    print(f"GHZ(3) counts ({shots} shots): {run_counts(ghz, shots)}")

    s = chsh_value(shots)
    print(f"CHSH S value: {s:.4f} (classical limit 2, quantum limit {2 * 2 ** 0.5:.4f})")
