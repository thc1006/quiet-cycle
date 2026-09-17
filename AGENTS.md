# Repository rules

No frontend. The public surface is Python types, versioned JSON, import functions,
CLI and optional HTTP. Keep dependency boundaries small; the exact learner does
not import NumPy, sklearn or cloud clients at runtime.

Before editing read README's equations and the test report. Fit selection uses
training and tuning only; calibration stays separate and test stays untouched.
Do not make a changing signal fixture easier after seeing its test error.

Treat event time and knowledge time separately. Unknown is not absent. Do not merge
sensor streams or guess onset continuity. Fixed-landmark artifacts must reject a
different landmark. A direct feature API must enforce the same scope guards.

New equations require new tests, documented formulas and changed artifact identity.
Preserve source attribution and limitations. Human-trained model statistics remain
sensitive. Do not publish synthetic weights as a validated product.

Validate with pytest, contracts, installed artifacts, exact independent checks,
mutation tests and static tools when available. Never replace an unavailable check
with a claimed pass. Keep unsuccessful benchmark results in the report.
