# HTTP adapter

Install `.[api]`, then:

```sh
python -m uvicorn quietcycle.api:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log
```

`POST /v2/predict` takes `PipelineRequest` JSON, exactly the CLI request contract.
`GET /health` returns status/version. `GET /openapi.json` exposes OpenAPI 3.1.0,
selected for the installed FastAPI integration; this is not a claim it is the latest
OpenAPI version. There are no HTML docs, frontend routes, cookies, or accounts.

```sh
curl --fail-with-body -H 'Content-Type: application/json'   --data-binary @examples/request.json http://127.0.0.1:8000/v2/predict
```

Results and input errors use `Cache-Control: no-store`. Requests over 16 MiB return
413; invalid schema or semantic input returns 422. Other content types and compressed
bodies return 415. Exact decimal strings and duplicate-key checks match CLI behavior.

This wrapper has no authentication, authorization, TLS, rate limiting, durable
storage, or per-tenant isolation beyond the explicit subject selection in the request.
A caller who can submit data chooses the subject ID. Deploy only behind your own
trusted application boundary. Configure reverse-proxy body and execution limits,
request-log redaction, authentication, and private transport. Do not put tokens or
health data in URLs. The SDK itself is the recommended embedding interface.

The default endpoint performs bounded local work. Caller-supplied research models
may require additional execution limits because exact rational denominators can grow.
They are intentionally not exposed on the default HTTP endpoint.

## Attach a fitted 0.3 model

Load the model at application startup, not from each untrusted request:

```python
from pathlib import Path
from quietcycle.api import create_app
from quietcycle.learning import FittedModel
from quietcycle.serialization import loads

model = FittedModel.model_validate(loads(Path("model.json").read_text()))
app = create_app(model=model)
```

This adds `POST /v3/forecast` using the same `PipelineRequest` input and returning
`LearnedPrediction`. Without an explicitly supplied model the route is absent.
The actual app's OpenAPI includes that route and its result schema; the committed
`contracts/openapi.json` describes the default baseline-only factory. SDK, CLI and
HTTP invoke the same learned pipeline. No model-upload or training endpoint exists.
Do not load the synthetic example artifact for patient-facing operation.
