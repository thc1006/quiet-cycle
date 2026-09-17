"""Optional local HTTP adapter. No HTML, database, authentication, or implicit telemetry.

Install quiet-cycle[api] and run behind your own authenticated application in production.
The SDK does not import this module unless the caller asks for it.
"""
from __future__ import annotations

from typing import Any

from .learning import FittedModel

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from .errors import InputError
from .models import PipelineRequest, PipelineResult, VERSION
from .pipeline import CyclePipeline
from .serialization import MAX_BYTES, loads, parse_model


class _ContractApp(FastAPI):
    _request_definitions: dict[str, Any]

    def openapi(self) -> dict[str, Any]:
        if self.openapi_schema is None:
            document = super().openapi()
            document.setdefault("components", {}).setdefault("schemas", {}).update(self._request_definitions)
            document["jsonSchemaDialect"] = "https://json-schema.org/draft/2020-12/schema"
            self.openapi_schema = document
        return self.openapi_schema


def create_app(*, model: FittedModel | None = None) -> FastAPI:
    app = _ContractApp(title="Quiet Cycle API", version=VERSION, docs_url=None, redoc_url=None)
    app.openapi_version = "3.1.0"
    pipeline = CyclePipeline()
    schema = PipelineRequest.model_json_schema(ref_template="#/components/schemas/{model}")
    app._request_definitions = schema.pop("$defs", {})

    @app.exception_handler(InputError)
    async def input_error(request: Request, exc: InputError) -> JSONResponse:
        status = 413 if exc.code == "input_too_large" else 422
        return JSONResponse(exc.to_dict(), status_code=status, headers={"Cache-Control": "no-store"})

    @app.exception_handler(ValidationError)
    async def model_error(request: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse({"error": {"code": "schema_validation_failed"}}, status_code=422,
                            headers={"Cache-Control": "no-store"})

    async def read_request(request: Request) -> PipelineRequest | JSONResponse:
        if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
            return JSONResponse({"error": {"code": "json_content_type_required"}}, status_code=415,
                                headers={"Cache-Control": "no-store"})
        if request.headers.get("content-encoding", "identity") != "identity":
            return JSONResponse({"error": {"code": "compressed_requests_unsupported"}}, status_code=415,
                                headers={"Cache-Control": "no-store"})
        data = bytearray()
        async for chunk in request.stream():
            if len(data) + len(chunk) > MAX_BYTES:
                raise InputError("input_too_large")
            data.extend(chunk)
        try:
            text = data.decode("utf-8")
        except UnicodeError:
            raise InputError("invalid_utf8") from None
        return parse_model(PipelineRequest, loads(text))

    request_body = {"requestBody": {"required": True, "content": {"application/json": {"schema": schema}}}}
    responses = {422: {"description": "Invalid input; error values are redacted"},
                 413: {"description": "Input exceeds 16 MiB"}}

    @app.post("/v2/predict", response_model=PipelineResult, responses=responses, openapi_extra=request_body)
    async def predict(request: Request) -> JSONResponse:
        body = await read_request(request)
        if isinstance(body, JSONResponse):
            return body
        result = pipeline.run(body.dataset, body.query)
        return JSONResponse(result.model_dump(mode="json"), headers={"Cache-Control": "no-store"})

    if model is not None:
        from .learning import MultiFactorPipeline, LearnedPrediction
        learned = MultiFactorPipeline(model)

        @app.post("/v3/forecast", response_model=LearnedPrediction, responses=responses,
                  openapi_extra=request_body)
        async def forecast(request: Request) -> JSONResponse:
            body = await read_request(request)
            if isinstance(body, JSONResponse):
                return body
            result = learned.run(body.dataset, body.query)
            return JSONResponse(result.model_dump(mode="json"), headers={"Cache-Control": "no-store"})

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": VERSION}

    return app
