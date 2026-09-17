from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from pydantic import BaseModel

from quietcycle import CyclePipeline, InputError
from quietcycle.adapters.csv import CSVAdapter
from quietcycle.adapters.records import from_jsonl
from quietcycle.adapters.fhir import FHIRObservationAdapter
from quietcycle.serialization import canonical_json

ROOT = Path(__file__).resolve().parents[1]


def cli(*args, stdin=None, cwd=None):
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    return subprocess.run([sys.executable, "-m", "quietcycle", *args], input=stdin,
                          text=True, encoding="utf-8", capture_output=True, env=env, cwd=cwd or ROOT)


def test_cli_and_all_import_paths_identical(sample):
    expected = canonical_json(CyclePipeline().run(sample.dataset, sample.query))
    for fmt, filename in [("json", "dataset.json"), ("jsonl", "events.jsonl"), ("csv", "events.csv")]:
        result = cli("run", "--format", fmt, f"examples/{filename}", "--query", "examples/query.json")
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == expected
        assert result.stderr == ""
    result = cli("predict", "-", stdin=(ROOT / "examples/request.json").read_text())
    assert result.stdout.strip() == expected


def test_cli_error_redacted_and_atomic_export(tmp_path):
    result = cli("predict", "-", stdin='{"password":"PRIVATE-MARKER"}')
    assert result.returncode == 2 and not result.stdout
    assert "PRIVATE-MARKER" not in result.stderr
    output = tmp_path / "result.json"
    result = cli("predict", "examples/request.json", "--output", str(output))
    assert result.returncode == 0 and not result.stdout
    assert json.loads(output.read_text())["schema_version"] == "2.0"
    if os.name != "nt":
        assert output.stat().st_mode & 0o777 == 0o600
    assert cli("predict", "file-does-not-exist").returncode == 2


def test_cli_schema_export():
    for name in ["dataset", "query", "request", "result", "duration-model", "duration-result"]:
        result = cli("schema", name)
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["$schema"].endswith("2020-12/schema")


def test_json_schema_examples_and_openapi():
    jsonschema = pytest.importorskip("jsonschema")
    for kind in ("dataset", "query", "request", "result"):
        schema = json.loads((ROOT / f"src/quietcycle/schemas/{kind}.schema.json").read_text())
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(schema).validate(json.loads((ROOT / f"examples/{kind}.json").read_text()))
    document = json.loads((ROOT / "contracts/openapi.json").read_text())
    assert document["openapi"] == "3.1.0"
    assert set(document["paths"]) == {"/health", "/v2/predict"}


def test_http_strictness_and_sdk_agreement(sample):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from quietcycle.api import create_app
    client = TestClient(create_app())
    response = client.post("/v2/predict", content=canonical_json(sample), headers={"content-type": "application/json"})
    assert response.status_code == 200, response.text
    assert response.json() == CyclePipeline().run(sample.dataset, sample.query).model_dump(mode="json")
    assert response.headers["cache-control"] == "no-store"
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/health").json()["status"] == "ok"
    for content in ['{"schema_version":"2.0","schema_version":"2.0"}', '{"secret":"PRIVATE-MARKER"}', '{"n":NaN}', '\\uINVALID']:
        response = client.post("/v2/predict", content=content, headers={"content-type": "application/json"})
        assert response.status_code == 422
        assert "PRIVATE-MARKER" not in response.text
        assert response.headers["cache-control"] == "no-store"
    assert client.post("/v2/predict", content="{}").status_code == 415
    response = client.post("/v2/predict", content="{}", headers={"content-type": "application/json", "content-encoding": "gzip"})
    assert response.status_code == 415 and response.headers["cache-control"] == "no-store"
    assert client.get("/openapi.json").json() == json.loads((ROOT / "contracts/openapi.json").read_text())


def test_regression_nested_float_serialization():
    class Foreign(BaseModel):
        value: float
    with pytest.raises(InputError, match="unsupported_json_value"):
        canonical_json(Foreign(value=0.1))


@pytest.mark.parametrize("bad", ["--1", "１２", "1.0", "+1", "1" * 20])
def test_regression_csv_integer_errors_redacted(bad):
    with pytest.raises(InputError, match="csv_integer_required"):
        CSVAdapter().loads(f"revision,kind\n{bad},onset\n")


def test_regression_jsonlines_reports_physical_row():
    with pytest.raises(InputError) as error:
        from_jsonl('\n\n{"kind":"onset"}\n')
    assert error.value.row == 3


def test_regression_malformed_adapter_configuration():
    with pytest.raises(InputError):
        CSVAdapter(column_map=["invalid"])
    adapter = FHIRObservationAdapter(subject_map={}, imported_at="2025-07-02T00:00:00Z", utc_offset_minutes=0)
    with pytest.raises(InputError, match="invalid_fhir_links"):
        adapter.from_mapping({"resourceType": "Bundle", "type": "collection", "link": None})


def test_cli_in_process_and_error_paths(sample, monkeypatch, capsys, tmp_path):
    from io import StringIO
    from quietcycle.cli import main
    for argv in [
        ["validate", "examples/request.json"],
        ["predict", "examples/request.json"],
        ["run", "--format", "csv", "examples/events.csv", "--query", "examples/query.json"],
        ["import", "--format", "jsonl", "examples/events.jsonl"],
        ["schema", "request"],
        ["migrate-v1", "examples/legacy-v1.json", "--subject", "demo"],
    ]:
        monkeypatch.chdir(ROOT)
        assert main(argv) == 0
        out = capsys.readouterr()
        assert json.loads(out.out)
        assert not out.err
    monkeypatch.setattr(sys, "stdin", StringIO("{bad-json"))
    assert main(["predict", "-"]) == 2
    assert json.loads(capsys.readouterr().err)["error"]["code"] == "invalid_json"
    target = tmp_path / "result.json"
    assert main(["predict", "examples/request.json", "--output", str(target)]) == 0
    assert target.exists()
    assert main(["predict", "examples/request.json", "--output", str(tmp_path / "missing" / "result.json")]) == 2
    assert "output_unwritable" in capsys.readouterr().err
    assert main(["predict", "nonexistent.json"]) == 2
    capsys.readouterr()


def test_unit_registry_signature_separates_features(sample):
    from fractions import Fraction
    from quietcycle import DefaultFeatureBuilder, UnitRegistry, UnitRule
    a = DefaultFeatureBuilder()
    b = DefaultFeatureBuilder(UnitRegistry({("lab_value", "{score}"): UnitRule("{score}", Fraction(2))}))
    assert a.builder_id != b.builder_id
    assert CyclePipeline(feature_builder=a).run(sample.dataset, sample.query).feature_builder_id == a.builder_id
