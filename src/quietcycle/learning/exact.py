"""Small dense exact ridge solver. No BLAS, RNG, float fallback or matrix inversion."""
from __future__ import annotations

from fractions import Fraction

from ..errors import InputError


def median(values: list[Fraction]) -> Fraction:
    if not values:
        raise InputError("empty_median")
    s = sorted(values)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def round_day(value: Fraction) -> int:
    """Nearest integer, ties toward the future (+infinity)."""
    shifted = value + Fraction(1, 2)
    return shifted.numerator // shifted.denominator


def solve(matrix: list[list[Fraction]], rhs: list[Fraction]) -> tuple[Fraction, ...]:
    n = len(rhs)
    if n == 0 or n > 128 or len(matrix) != n or any(len(row) != n for row in matrix):
        raise InputError("linear_system_shape")
    if any(type(x) is not Fraction for row in matrix for x in row) or any(type(x) is not Fraction for x in rhs):
        raise InputError("fraction_matrix_required")
    a = [row[:] + [rhs[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = next((j for j in range(col, n) if a[j][col]), None)
        if pivot is None:
            raise InputError("singular_linear_system")
        a[col], a[pivot] = a[pivot], a[col]
        divisor = a[col][col]
        a[col] = [x / divisor for x in a[col]]
        for j in range(col + 1, n):
            factor = a[j][col]
            if factor:
                a[j] = [a[j][k] - factor * a[col][k] for k in range(n + 1)]
        if any(max(abs(x.numerator).bit_length(), x.denominator.bit_length()) > 6800 for row in a for x in row):
            raise InputError("linear_precision_budget")
    answer = [Fraction(0)] * n
    for j in range(n - 1, -1, -1):
        answer[j] = a[j][-1] - sum((a[j][k] * answer[k] for k in range(j + 1, n)), Fraction(0))
    return tuple(answer)


def ridge(rows: list[tuple[Fraction, ...]], outcomes: list[Fraction], penalty: int) -> tuple[Fraction, ...]:
    if type(penalty) is not int or penalty <= 0 or not rows or len(rows) != len(outcomes):
        raise InputError("invalid_ridge_input")
    p = len(rows[0])
    if p == 0 or p > 128 or any(len(r) != p or r[0] != 1 for r in rows):
        raise InputError("ridge_requires_intercept")
    if any(type(x) is not Fraction for row in rows for x in row) or any(type(x) is not Fraction for x in outcomes):
        raise InputError("fraction_matrix_required")
    gram = [[sum((r[i] * r[j] for r in rows), Fraction(0)) + (penalty if i == j and i else 0)
             for j in range(p)] for i in range(p)]
    rhs = [sum((r[i] * y for r, y in zip(rows, outcomes)), Fraction(0)) for i in range(p)]
    solution = solve(gram, rhs)
    if any(sum((gram[i][j] * solution[j] for j in range(p)), Fraction(0)) != rhs[i] for i in range(p)):
        raise InputError("normal_equation_certificate_failed")
    return solution


def conformal_radius(scores: tuple[int, ...], coverage_ppm: int) -> int | None:
    if type(coverage_ppm) is not int or not 0 < coverage_ppm < 1000000 or any(type(s) is not int or s < 0 for s in scores):
        raise InputError("invalid_calibration")
    rank = ((len(scores) + 1) * coverage_ppm + 999999) // 1000000
    # The +infinity atom is essential, especially for small calibration sets.
    return sorted(scores)[rank - 1] if 0 < rank <= len(scores) else None
