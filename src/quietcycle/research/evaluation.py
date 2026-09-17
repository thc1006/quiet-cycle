"""Small exact evaluators. Valid coverage still requires an appropriate study design."""
from __future__ import annotations

from fractions import Fraction

from ..errors import InputError


def conformal_radius(absolute_errors: tuple[int, ...], *, coverage: Fraction) -> int | None:
    """Split-conformal order statistic; None means no finite sample radius exists.

    The numerical rule alone does not provide exchangeability or time-series validity.
    """
    if not isinstance(coverage, Fraction) or not 0 < coverage < 1 or any(type(x) is not int or x < 0 for x in absolute_errors):
        raise InputError("invalid_calibration_data")
    rank_value = (len(absolute_errors) + 1) * coverage
    rank = (rank_value.numerator + rank_value.denominator - 1) // rank_value.denominator
    return sorted(absolute_errors)[rank - 1] if 1 <= rank <= len(absolute_errors) else None


def mean_absolute_error(predicted: tuple[int, ...], observed: tuple[int, ...]) -> Fraction:
    if not predicted or len(predicted) != len(observed) or any(type(v) is not int for v in predicted + observed):
        raise InputError("invalid_score_data")
    return Fraction(sum(abs(a - b) for a, b in zip(predicted, observed)), len(predicted))
