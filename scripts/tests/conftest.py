# scripts/tests/conftest.py
"""Fixtures for aggregator tests."""

from __future__ import annotations

import json
from pathlib import (
    Path,  # noqa: TC003  # used at runtime as fixture return-type via tmp_path / ...
)

import pytest


@pytest.fixture
def write_job_json(tmp_path: Path):
    """Helper: write a JSON object to tmp_path/<name>.json and return the path."""

    def _write(name: str, payload: dict) -> Path:
        p = tmp_path / f"{name}.json"
        p.write_text(json.dumps(payload), encoding="utf-8")
        return p

    return _write
