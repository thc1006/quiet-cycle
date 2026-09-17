"""Three predeclared synthetic scenarios. Keep the failure scenario in the report."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples"))
from synthetic_cohort import cohort
from quietcycle.learning import evaluate, fit, model_digest
from quietcycle.serialization import canonical_json

reports = {}
for regime in ("signal", "noise", "drift"):
    request, test, _, rejected = cohort(regime=regime)
    model = fit(request)
    report = evaluate(model, test)
    report.update({"selected_candidate": model.selected.name, "blend": model.selected.blend,
                   "model_sha256": model_digest(model), "case_build_rejections": rejected,
                   "split_counts": [len(request.train), len(request.tune), len(request.calibration), len(test)]})
    reports[regime] = report
output = {"scope": "synthetic-software-experiment-not-clinical-evidence", "scenarios": reports}
path = ROOT / "evidence" / "learning-benchmark.json"
path.parent.mkdir(exist_ok=True)
path.write_text(json.dumps(json.loads(canonical_json(output)), indent=2, sort_keys=True)+"\n")
for regime, report in reports.items():
    print(regime, report["selected_candidate"], "MAE", report["mae_days"], "baseline", report["baseline_mae_same_estimated_cases"])
