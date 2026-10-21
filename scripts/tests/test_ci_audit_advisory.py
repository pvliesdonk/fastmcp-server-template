"""Keep the dependency audit out of the required CI Success aggregate (#813)."""

from pathlib import Path

import pytest
import yaml
from jinja2 import Environment

REPO = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("structural_gate", [False, True])
def test_audit_runs_but_does_not_gate(structural_gate: bool) -> None:
    env = Environment(keep_trailing_newline=True)
    workflow = yaml.safe_load(
        env.from_string((REPO / ".github/workflows/ci.yml.jinja").read_text()).render(
            enable_structural_gate=structural_gate,
            include_mcp_apps_scaffold=True,
        )
    )
    jobs = workflow["jobs"]
    assert jobs["audit"]["name"] == "Dependency Audit"
    assert "audit" not in jobs["ci-success"]["needs"]
