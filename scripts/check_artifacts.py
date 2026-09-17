"""Install the wheel outside the checkout and exercise the published interfaces.

Uses already installed dependency versions (--no-deps), explicitly not a full
isolated dependency-resolution test. Never uploads or fetches patient data.
"""
from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def run(argv: list[str], *, env: dict[str, str], cwd: Path, input_text: str | None = None) -> str:
    result = subprocess.run(argv, input=input_text, text=True, encoding="utf-8", capture_output=True,
                            env=env, cwd=cwd, timeout=45)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {argv[0:3]}\n{result.stderr}")
    return result.stdout


def main() -> None:
    wheel = ROOT / "dist/quiet_cycle-0.3.0-py3-none-any.whl"
    source = ROOT / "dist/quiet_cycle-0.3.0.tar.gz"
    checks = []
    skipped = []
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        assert "quietcycle/py.typed" in names
        assert len([n for n in names if n.startswith("quietcycle/schemas/") and n.endswith(".json")]) == 11
        assert not any(n.endswith((".html", ".css", ".js", ".mjs")) or n.startswith("tests/") for n in names)
        records = next(n for n in names if n.endswith(".dist-info/RECORD"))
        for name, digest, length in csv.reader(io.StringIO(archive.read(records).decode())):
            if digest:
                algorithm, expected = digest.split("=", 1)
                assert algorithm == "sha256"
                content = archive.read(name)
                actual = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b"=").decode()
                assert actual == expected and len(content) == int(length)
        checks.extend(["wheel-typing-marker", "eleven-packaged-schemas", "no-frontend-or-tests-in-wheel", "wheel-record-hashes"])
    with tarfile.open(source) as archive:
        members = archive.getmembers()
        assert all(not m.name.startswith("/") and ".." not in Path(m.name).parts and not m.issym() and not m.islnk() for m in members)
        assert any(m.name.endswith("/tests/test_reference.py") for m in members)
        assert any(m.name.endswith("/docs/CONTRACT.md") for m in members)
        checks.append("sdist-source-tests-docs-and-safe-paths")
    with tempfile.TemporaryDirectory(prefix="quiet-cycle-installed-") as temporary:
        workspace = Path(temporary)
        target = workspace / "site"
        env = {**os.environ, "PYTHONPATH": str(target), "PYTHONNOUSERSITE": "1"}
        run([sys.executable, "-m", "pip", "install", "--no-deps", "--no-index", "--target", str(target), str(wheel)], env=env, cwd=workspace)
        copied = workspace / "examples"
        shutil.copytree(ROOT / "examples", copied)
        code = '''import json, pathlib, typing, importlib.metadata, quietcycle, sys
from importlib.resources import files
assert pathlib.Path(quietcycle.__file__).resolve().is_relative_to(pathlib.Path(sys.argv[1]))
assert importlib.metadata.version("quiet-cycle") == "0.3.0"
assert "fastapi" not in sys.modules
assert files("quietcycle").joinpath("py.typed").is_file()
assert typing.get_type_hints(quietcycle.CyclePipeline.run)["return"] is quietcycle.PipelineResult
assert len(list(files("quietcycle.schemas").iterdir())) >= 6
print("installed-typed-core")
'''
        assert run([sys.executable, "-c", code, str(target)], env=env, cwd=workspace).strip() == "installed-typed-core"
        checks.extend(["installed-location-and-version", "core-does-not-import-fastapi", "installed-type-hints-and-resources"])
        expected = json.loads((copied / "result.json").read_text())
        actual = json.loads(run([sys.executable, "-m", "quietcycle", "predict", str(copied / "request.json")], env=env, cwd=workspace))
        assert actual == expected
        checks.append("installed-cli-equals-golden")
        for name in ("basic.py", "from_rows.py", "custom_predictor.py", "research_pipeline.py", "fhir_import.py"):
            output = run([sys.executable, str(copied / name)], env=env, cwd=workspace)
            assert output.strip()
            if name == "basic.py":
                assert json.loads(output) == expected
            if name == "research_pipeline.py":
                assert json.loads(output)["result"]["steps"][0]["mass"] == {"numerator": "3", "denominator": "4"}
            checks.append("installed-example-" + name)
        if shutil.which("node"):
            node_env = {**env, "PYTHON": sys.executable}
            actual = json.loads(run([shutil.which("node"), str(copied / "node_client.mjs")], env=node_env, cwd=workspace))
            assert actual == expected
            checks.append("node-to-installed-python-json")
        else:
            skipped.append("node-client-tool-unavailable")
        learned_dir = workspace / "learned"
        run([sys.executable, str(copied / "train_multifactor.py"), "--output", str(learned_dir)], env=env, cwd=workspace)
        learned_expected = json.loads((learned_dir / "prediction.json").read_text())
        learned_actual = json.loads(run([sys.executable, "-m", "quietcycle", "forecast", str(learned_dir / "request.json"),
            "--model", str(learned_dir / "model.json")], env=env, cwd=workspace))
        assert learned_actual == learned_expected
        checks.append("installed-learned-training-to-cli-equals-sdk")
        evaluated = json.loads(run([sys.executable, "-m", "quietcycle", "evaluate", str(learned_dir / "test-cases.json"),
            "--model", str(learned_dir / "model.json")], env=env, cwd=workspace))
        assert evaluated == json.loads((learned_dir / "evaluation.json").read_text())
        checks.append("installed-learned-evaluation-equals-sdk")
        for schema_name in ("landmark", "labelled-case", "fit-request", "fitted-model", "learned-prediction"):
            document = json.loads(run([sys.executable, "-m", "quietcycle", "schema", schema_name], env=env, cwd=workspace))
            assert document["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        checks.append("installed-learning-wire-schemas")
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        log = (workspace / "uvicorn.log").open("w")
        server = subprocess.Popen([sys.executable, "-m", "uvicorn", "quietcycle.api:create_app", "--factory",
            "--host", "127.0.0.1", "--port", str(port), "--no-access-log"], cwd=workspace, env=env, stdout=log, stderr=log)
        try:
            url = f"http://127.0.0.1:{port}"
            for _ in range(100):
                if server.poll() is not None:
                    raise RuntimeError("Local HTTP process exited; inspect installed API dependencies")
                try:
                    with urllib.request.urlopen(url + "/health", timeout=1) as response:
                        assert json.load(response)["status"] == "ok"
                    break
                except (OSError, TimeoutError):
                    time.sleep(0.1)
            else:
                raise RuntimeError("Local HTTP process did not become ready")
            request = urllib.request.Request(url + "/v2/predict", data=(copied / "request.json").read_bytes(), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=10) as response:
                assert response.headers["Cache-Control"] == "no-store"
                assert json.load(response) == expected
            with urllib.request.urlopen(url + "/openapi.json", timeout=5) as response:
                assert json.load(response) == json.loads((ROOT / "contracts/openapi.json").read_text())
            checks.extend(["live-local-http-equals-sdk-and-cli", "live-http-no-store", "live-openapi-equals-committed"])
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()
            log.close()
        app_file = workspace / "bound_app.py"
        app_file.write_text("from pathlib import Path\nfrom quietcycle.api import create_app\nfrom quietcycle.learning import FittedModel\nfrom quietcycle.serialization import loads\n" +
            "model=FittedModel.model_validate(loads(Path(" + repr(str(learned_dir / "model.json")) + ").read_text()))\napp=create_app(model=model)\n")
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            learned_port = sock.getsockname()[1]
        learned_log = (workspace / "learned-http.log").open("w")
        learned_server = subprocess.Popen([sys.executable, "-m", "uvicorn", "bound_app:app", "--app-dir", str(workspace),
            "--host", "127.0.0.1", "--port", str(learned_port), "--no-access-log"], env=env, cwd=workspace, stdout=learned_log, stderr=learned_log)
        try:
            learned_url = f"http://127.0.0.1:{learned_port}"
            for _ in range(100):
                if learned_server.poll() is not None:
                    raise RuntimeError("Model-bound local HTTP exited")
                try:
                    with urllib.request.urlopen(learned_url + "/health", timeout=1) as response:
                        assert json.load(response)["status"] == "ok"
                    break
                except (OSError, TimeoutError):
                    time.sleep(0.1)
            else:
                raise RuntimeError("Model-bound local HTTP failed to start")
            request = urllib.request.Request(learned_url + "/v3/forecast", data=(learned_dir / "request.json").read_bytes(), headers={"Content-Type":"application/json"})
            with urllib.request.urlopen(request,timeout=15) as response:
                assert response.headers["Cache-Control"] == "no-store"
                assert json.load(response) == learned_expected
            with urllib.request.urlopen(learned_url + "/openapi.json",timeout=5) as response:
                assert "/v3/forecast" in json.load(response)["paths"]
            checks.extend(["live-learned-http-equals-cli-and-sdk", "live-learned-http-no-store", "live-learned-openapi"])
        finally:
            learned_server.terminate()
            try:
                learned_server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                learned_server.kill()
                learned_server.wait()
            learned_log.close()
    print(json.dumps({"passed": len(checks), "checks": checks,
        "skipped": skipped, "dependency_isolation": "no-deps-target-install-reuses-host-dependencies",
        "python": sys.version, "network": "localhost-only"}, indent=2))

if __name__ == "__main__":
    main()
