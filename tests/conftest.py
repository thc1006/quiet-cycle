from __future__ import annotations

import json
from pathlib import Path

import pytest

from quietcycle import PipelineRequest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def request_data():
    return json.loads((ROOT / "examples/request.json").read_text())


@pytest.fixture
def sample(request_data):
    return PipelineRequest.model_validate(request_data)
