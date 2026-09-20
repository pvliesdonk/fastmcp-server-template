"""Keep coverage mandatory without instrumenting every interpreter (#641)."""

import shlex
import tomllib
from pathlib import Path

import pytest
import yaml
from jinja2 import Environment

REPO = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("structural_gate", [False, True])
@pytest.mark.parametrize("apps_scaffold", [False, True])
def test_one_required_interpreter_collects_and_consumes_coverage(
    structural_gate: bool, apps_scaffold: bool
) -> None:
    env = Environment(keep_trailing_newline=True)
    workflow = yaml.safe_load(
        env.from_string((REPO / ".github/workflows/ci.yml.jinja").read_text()).render(
            enable_structural_gate=structural_gate,
            include_mcp_apps_scaffold=apps_scaffold,
        )
    )
    job = workflow["jobs"]["test"]
    entries = job["strategy"]["matrix"]["include"]
    assert {entry["python-version"] for entry in entries} == {
        "3.11",
        "3.12",
        "3.13",
        "3.14",
    }
    assert job["continue-on-error"] == "${{ matrix.experimental || false }}"
    assert job["timeout-minutes"] == 20
    test_steps = [
        step for step in job["steps"] if step.get("run", "").startswith("uv run pytest")
    ]
    assert len(test_steps) == 2
    covered = [step for step in test_steps if "--cov" in shlex.split(step["run"])]
    assert len(covered) == 1
    covered_step = covered[0]
    condition = covered_step["if"]
    assert condition == "matrix.python-version == '3.14'"
    assert all(not entry["experimental"] for entry in entries)
    assert "--cov-report=xml" in shlex.split(covered_step["run"])
    assert "--cov-fail-under" not in covered_step["run"]
    bare_step = next(step for step in test_steps if step is not covered_step)
    assert bare_step["if"] == "matrix.python-version != '3.14'"
    assert shlex.split(bare_step["run"]) == ["uv", "run", "pytest", "--durations=20"]
    assert all("--durations=20" in step["run"] for step in test_steps)
    assert all(not step.get("continue-on-error", False) for step in test_steps)

    consumers = [
        step
        for step in job["steps"]
        if "coverage" in step.get("name", "").lower()
        or step.get("name") == "Fetch base branch for diff-cover"
        or step.get("name") == "Post codecov/patch status"
    ]
    assert len(consumers) == 7
    assert all(step["if"].startswith(condition) for step in consumers)
    patch_step = next(s for s in consumers if s["name"] == "Check patch coverage")
    assert "--fail-under=80" in patch_step["run"]
    assert "test" in workflow["jobs"]["ci-success"]["needs"]

    config = tomllib.loads(
        env.from_string((REPO / "pyproject.toml.jinja").read_text()).render(
            python_module="smoke_test", project_name="smoke-test"
        )
    )
    assert config["tool"]["coverage"]["run"]["branch"] is True
    assert config["tool"]["coverage"]["report"]["fail_under"] == 80
