from math import sqrt

import pytest
from qiskit.quantum_info import Statevector

from main import (
    build_bell_circuit,
    build_ghz_circuit,
    chsh_value,
    correlation,
    entanglement_entropy,
    get_statevector,
    run_counts,
)

SEED = 42


def test_bell_statevector_is_phi_plus():
    state = get_statevector(build_bell_circuit(measure=False))
    expected = Statevector([1 / sqrt(2), 0, 0, 1 / sqrt(2)])
    assert state.equiv(expected)


def test_bell_counts_only_00_and_11():
    counts = run_counts(build_bell_circuit(), shots=4000, seed=SEED)
    assert set(counts) <= {"00", "11"}
    assert counts["00"] + counts["11"] == 4000
    # 두 결과가 대략 절반씩 나와야 한다
    assert abs(counts["00"] / 4000 - 0.5) < 0.05


def test_bell_is_maximally_entangled():
    assert entanglement_entropy(build_bell_circuit(measure=False)) == pytest.approx(1.0, abs=1e-9)


def test_product_state_has_zero_entropy():
    from qiskit import QuantumCircuit

    qc = QuantumCircuit(2)
    qc.h(0)
    qc.h(1)
    assert entanglement_entropy(qc) == pytest.approx(0.0, abs=1e-9)


@pytest.mark.parametrize("n", [2, 3, 4])
def test_ghz_counts_all_zeros_or_all_ones(n):
    counts = run_counts(build_ghz_circuit(n), shots=2000, seed=SEED)
    assert set(counts) <= {"0" * n, "1" * n}
    assert sum(counts.values()) == 2000


def test_ghz_requires_two_or_more_qubits():
    with pytest.raises(ValueError):
        build_ghz_circuit(1)


def test_correlation():
    assert correlation({"00": 50, "11": 50}) == 1.0
    assert correlation({"01": 50, "10": 50}) == -1.0
    assert correlation({"00": 25, "11": 25, "01": 25, "10": 25}) == 0.0


def test_chsh_violates_classical_bound():
    s = chsh_value(shots=10000, seed=SEED)
    assert s > 2.0
    assert s <= 2 * sqrt(2) + 0.1
    assert s == pytest.approx(2 * sqrt(2), abs=0.1)
