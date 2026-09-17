"""Fourteen focused mutations; not an exhaustive mutation-coverage claim."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = [
    ("missing-becomes-negative", "predictors.py", "        if past:\n", "        if False:\n", "tests/test_pipeline.py::test_missing_is_not_no_onset"),
    ("future-report-leak", "ledger.py", "event.subject_id != query.subject_id or event.available_at > query.cutoff", "event.subject_id != query.subject_id", "tests/test_pipeline.py::test_late_revision_is_invisible_in_replay"),
    ("wrong-fahrenheit-scale", "units.py", "Fraction(5, 9)", "Fraction(4, 9)", "tests/test_adapters.py::test_unit_cases"),
    ("csv-boolean-inversion", "adapters/csv.py", 'record[name] = text_value == "true"', 'record[name] = text_value == "false"', "tests/test_adapters.py::test_all_file_formats_are_equivalent"),
    ("duplicate-json-last-wins", "serialization.py", "        if key in out:\n", "        if False:\n", "tests/test_models.py::test_wire_parser_rejects_ambiguous_json"),
    ("fhir-source-collision", "adapters/fhir.py", 'self.source_id + "\\0" + reference', 'reference', "tests/test_adapters.py::test_fhir_sources_and_site_mapping"),
    ("drop-residual-mass", "research/duration.py", "Probability.from_fraction(sum(mass.values(), Fraction()))", "Probability.from_fraction(Fraction())", "tests/test_research.py::test_duration_simple_and_residual"),
    ("kernel-flat-not-triangular", "predictors.py", "bandwidth + 1 - abs(delta)", "bandwidth + 1", "tests/test_reference.py::test_1400_kernel_and_allocation_cases"),

    ("conformal-missing-infinity-rank", "learning/exact.py", "(len(scores) + 1) * coverage_ppm", "len(scores) * coverage_ppm", "tests/test_learning.py::test_conformal_rank"),
    ("model-backdated", "learning/prediction.py", "if q.cutoff <= model.available_at:", "if False:", "tests/test_learning.py::test_no_backdated_model"),
    ("direct-scope-bypass", "learning/prediction.py", "if q.context.mode != \"natural-cycle\":", "if False:", "tests/test_learning.py::test_direct_landmark_cannot_bypass_scope"),
    ("round-ties-wrong", "learning/exact.py", "shifted = value + Fraction(1, 2)", "shifted = value", "tests/test_learning.py::test_rounding"),
    ("regularize-intercept", "learning/exact.py", "penalty if i == j and i else 0", "penalty if i == j else 0", "tests/test_learning.py::test_ridge_normal_equation_exact"),
    ("training-time-leak", "learning/fitting.py", "if max(c.outcome_known_at for c in left) >= min(c.landmark.query.cutoff for c in right):", "if False:", "tests/test_learning.py::test_temporal_boundary_rejected"),
]


def main() -> None:
    results = []
    with tempfile.TemporaryDirectory(prefix="quiet-cycle-mutations-") as temporary:
        work = Path(temporary)
        for name in ("src", "tests", "examples"):
            shutil.copytree(ROOT / name, work / name, ignore=shutil.ignore_patterns("__pycache__", "*.egg-info"))
        shutil.copy2(ROOT / "pyproject.toml", work / "pyproject.toml")
        env = {**os.environ, "PYTHONPATH": str(work / "src")}
        for name, filename, old, new, test in MUTATIONS:
            path = work / "src/quietcycle" / filename
            original = path.read_text()
            assert original.count(old) == 1, name
            path.write_text(original.replace(old, new))
            result = subprocess.run([sys.executable, "-m", "pytest", "-q", test], cwd=work,
                env=env, text=True, encoding="utf-8", capture_output=True, timeout=30)
            path.write_text(original)
            # Force fresh bytecode even on filesystems with coarse mtimes.
            for cache in (work / "src").rglob("__pycache__"):
                shutil.rmtree(cache)
            killed = result.returncode == 1 and "FAILED " in result.stdout and "ERROR collecting" not in result.stdout
            results.append({"mutation": name, "test": test, "killed": killed,
                            "exit_code": result.returncode, "summary": result.stdout.splitlines()[-1:]})
            if not killed:
                print(result.stdout, result.stderr, file=sys.stderr)
    report = {"selected_mutations": len(results), "killed": sum(x["killed"] for x in results),
              "scope": "targeted-regressions-not-exhaustive-mutation-coverage", "results": results}
    print(json.dumps(report, indent=2))
    if report["killed"] != len(results):
        raise SystemExit(1)

if __name__ == "__main__":
    main()
