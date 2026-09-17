"""Public error codes. Do not include health values in diagnostics."""
from __future__ import annotations

from typing import NoReturn

from pydantic import ValidationError


class InputError(ValueError):
    """An input cannot be interpreted without guessing or losing information."""

    def __init__(self, code: str, *, row: int | None = None) -> None:
        self.code = code
        self.row = row
        super().__init__(code)

    def to_dict(self) -> dict[str, object]:
        detail: dict[str, object] = {"code": self.code}
        if self.row is not None:
            detail["row"] = self.row
        return {"error": detail}


def invalid(error: ValidationError) -> NoReturn:
    # Pydantic's normal exception includes input values. Never forward it through CLI/HTTP.
    raise InputError("schema_validation_failed") from None
