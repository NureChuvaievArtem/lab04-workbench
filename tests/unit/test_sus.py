"""Unit-тести обчислення шкали SUS (eval/sus.py)."""

from __future__ import annotations

import pytest

from eval.sus import sus_score


def test_sus_score_formula() -> None:
    # Відповіді з п. 13 контролю МВ: 4, 2, 4, 2, 4, 2, 4, 2, 4, 2 -> 75.0
    assert sus_score([4, 2, 4, 2, 4, 2, 4, 2, 4, 2]) == pytest.approx(75.0)
    with pytest.raises(ValueError):
        sus_score([4, 2])
