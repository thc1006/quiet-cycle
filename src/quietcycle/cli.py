"""JSON on stdout, redacted errors on stderr. No log output contaminates the wire stream."""
from __future__ import annotations

import argparse
import sys
from importlib.resources import files
from typing import Any

from pydantic import ValidationError

from .adapters import CSVAdapter, FHIRObservationAdapter, from_json, from_jsonl, from_v1
from .errors import InputError
from .models import CycleDataset, PipelineRequest, Query, VERSION
from .pipeline import CyclePipeline
from .serialization import MAX_BYTES, canonical_json, loads, parse_model, read_text, write_private


def _read(path: str) -> str:
    if path != "-":
        return read_text(path)
    text = sys.stdin.read(MAX_BYTES + 1)
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise InputError("input_too_large")
    return text


def _dataset(args: argparse.Namespace) -> CycleDataset:
    text = _read(args.input)
    if args.format == "json":
        return from_json(text)
    if args.format == "jsonl":
        return from_jsonl(text)
    if args.format == "csv":
        settings = {} if args.mapping is None else loads(read_text(args.mapping))
        if not isinstance(settings, dict) or any(k not in ("column_map", "defaults") for k in settings):
            raise InputError("invalid_csv_mapping")
        return CSVAdapter(**settings).loads(text)
    if args.subject_map is None or args.imported_at is None or args.utc_offset_minutes is None:
        raise InputError("fhir_import_options_required")
    subjects = loads(read_text(args.subject_map))
    if not isinstance(subjects, dict):
        raise InputError("invalid_subject_map")
    return FHIRObservationAdapter(subject_map=subjects, imported_at=args.imported_at,
                                  utc_offset_minutes=args.utc_offset_minutes, source_id=args.source_id).loads(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="quiet-cycle", description="Import health events and run deterministic research forecasts.")
    parser.add_argument("--version", action="version", version=VERSION)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("predict", "validate"):
        command = sub.add_parser(name)
        command.add_argument("input", help="Request JSON path, or - for stdin")
        command.add_argument("-o", "--output")
    for name in ("run", "import"):
        command = sub.add_parser(name)
        command.add_argument("input", help="Dataset path, or - for stdin")
        command.add_argument("--format", choices=("json", "jsonl", "csv", "fhir-r4"), required=True)
        command.add_argument("--mapping", help="CSV column_map/defaults JSON file")
        command.add_argument("--subject-map", help="FHIR patient-reference to local-pseudonym JSON file")
        command.add_argument("--imported-at")
        command.add_argument("--source-id", default="fhir-r4", help="FHIR source namespace")
        command.add_argument("--utc-offset-minutes", type=int)
        command.add_argument("-o", "--output")
        if name == "run":
            command.add_argument("--query", required=True)
    for name in ("fit", "forecast", "evaluate"):
        command = sub.add_parser(name)
        command.add_argument("input", help="Fit request, forecast request, or labelled cases JSON; - for stdin")
        command.add_argument("-o", "--output")
        if name != "fit":
            command.add_argument("--model", required=True, help="Fitted JSON artifact, never a pickle")
    migrate = sub.add_parser("migrate-v1")
    migrate.add_argument("input")
    migrate.add_argument("--subject-id", required=True)
    migrate.add_argument("--imported-at", help="Set on live imports; omit only for a historical replay you can substantiate")
    migrate.add_argument("-o", "--output")
    schema = sub.add_parser("schema")
    schema.add_argument("name", choices=("dataset", "query", "request", "result", "duration-model", "duration-result", "landmark", "labelled-case", "fit-request", "fitted-model", "learned-prediction"))
    schema.add_argument("-o", "--output")
    args = parser.parse_args(argv)
    try:
        result: Any
        if args.command in ("fit", "forecast", "evaluate"):
            from .learning import FitRequest, FittedModel, LabelledCase, MultiFactorPipeline, evaluate, fit
            if args.command == "fit":
                result = fit(parse_model(FitRequest, loads(_read(args.input))))
            else:
                model = parse_model(FittedModel, loads(read_text(args.model)))
                if args.command == "forecast":
                    request = parse_model(PipelineRequest, loads(_read(args.input)))
                    result = MultiFactorPipeline(model).run(request.dataset, request.query)
                else:
                    cases = loads(_read(args.input))
                    if not isinstance(cases, list) or len(cases) > 5000:
                        raise InputError("invalid_evaluation_cases")
                    result = evaluate(model, tuple(parse_model(LabelledCase, c) for c in cases))
        elif args.command == "schema":
            result = loads(files("quietcycle.schemas").joinpath(args.name + ".schema.json").read_text(encoding="utf-8"))
        elif args.command in ("predict", "validate"):
            request = parse_model(PipelineRequest, loads(_read(args.input)))
            calculated = CyclePipeline().run(request.dataset, request.query)
            result = calculated if args.command == "predict" else {"valid": True, "forecast_status": calculated.forecast.status}
        elif args.command == "migrate-v1":
            result = from_v1(loads(_read(args.input)), subject_id=args.subject_id, imported_at=args.imported_at)
        else:
            dataset = _dataset(args)
            result = dataset if args.command == "import" else CyclePipeline().run(dataset, parse_model(Query, loads(read_text(args.query))))
        output = canonical_json(result)
        if args.output:
            write_private(args.output, output)
        else:
            sys.stdout.write(output + "\n")
        return 0
    except InputError as exc:
        sys.stderr.write(canonical_json(exc.to_dict()) + "\n")
        return 2
    except ValidationError:
        sys.stderr.write('{"error":{"code":"schema_validation_failed"}}\n')
        return 2
    except (OSError, UnicodeError):
        sys.stderr.write('{"error":{"code":"io_error"}}\n')
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
