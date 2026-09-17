"""Deterministic JSON and bounded local-file input. This is not RFC 8785 JCS."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from .errors import InputError, invalid

MAX_BYTES = 16 * 1024 * 1024
M = TypeVar("M", bound=BaseModel)


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise InputError("duplicate_json_key")
        out[key] = value
    return out


def _reject_decimal(value: str) -> Any:
    raise InputError("decimal_requires_string")


def _constant(value: str) -> Any:
    raise InputError("non_finite_json_number")


def loads(text: str, *, source_decimals: bool = False) -> Any:
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise InputError("input_too_large")
    try:
        # Source quantities retain their exact decimal spelling, not binary floats.
        return json.loads(text, object_pairs_hook=_object,
                          parse_float=str if source_decimals else _reject_decimal,
                          parse_constant=_constant)
    except (ValueError, RecursionError) as exc:
        if isinstance(exc, InputError):
            raise
        raise InputError("invalid_json") from None


def parse_model(model: type[M], value: Any) -> M:
    try:
        return model.model_validate(value)
    except ValidationError as exc:
        invalid(exc)


def _plain(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _plain(value.model_dump(mode="json"))
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise InputError("json_keys_must_be_strings")
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if value is None or type(value) in (str, int, bool):
        return value
    # In particular, never silently accept float probabilities.
    raise InputError("unsupported_json_value")


def canonical_json(value: Any) -> str:
    return json.dumps(_plain(value), sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False)


def read_text(path: str | Path) -> str:
    try:
        with Path(path).open("rb") as stream:
            data = stream.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise InputError("input_too_large")
        return data.decode("utf-8-sig")
    except (OSError, UnicodeError):
        raise InputError("input_unreadable") from None


def write_private(path: str | Path, text: str) -> None:
    """Atomically replace a local output. Unix permissions are 0600; Windows needs ACLs."""
    target = Path(path)
    temporary: str | None = None
    try:
        fd, temporary = tempfile.mkstemp(prefix=".quiet-cycle-", dir=target.parent)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        temporary = None
    except OSError:
        raise InputError("output_unwritable") from None
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary)
            except OSError:
                pass
