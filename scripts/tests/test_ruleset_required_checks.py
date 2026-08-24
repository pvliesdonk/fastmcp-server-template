"""Guard the required checks and `extra_required_checks` seam in branch rulesets.

A generated project makes a check that lives outside the template-owned
`ci.yml` merge-blocking by listing its context in `extra_required_checks`;
the answer renders into the `required_status_checks` array of both branch
rulesets, which `bootstrap.yml` then applies verbatim.

Two properties matter and neither is visible by reading the template:

- With the default empty answer the rendered JSON must require the two
  template-owned checks, in a fixed order.
- With a non-empty answer the result must still be valid JSON.  The array
  is assembled by a Jinja loop inside a JSON literal, so a missing comma or
  an unescaped quote in a check name produces a file that parses as nothing
  — and `bootstrap.yml` would `gh api --input` it straight at GitHub.

Rendering here goes through a plain Jinja environment rather than a full
copier render: the templates use only a `for` loop and `tojson`, both plain
Jinja, and a copier render per case costs a minute for no extra coverage.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jinja2 import Environment

_REPO = Path(__file__).resolve().parents[2]
_RULESETS = _REPO / ".github" / "rulesets"
_BRANCH_RULESETS = ("protect-main.json.jinja", "protect-release-branches.json.jinja")


def _render(template: Path, extra_required_checks: list[str]) -> dict:
    env = Environment(keep_trailing_newline=True, autoescape=False)
    rendered = env.from_string(template.read_text(encoding="utf-8")).render(
        extra_required_checks=extra_required_checks
    )
    return json.loads(rendered)


def _contexts(ruleset: dict) -> list[str]:
    for rule in ruleset["rules"]:
        if rule["type"] == "required_status_checks":
            checks = rule["parameters"]["required_status_checks"]
            return [check["context"] for check in checks]
    raise AssertionError(f"{ruleset['name']} has no required_status_checks rule")


@pytest.mark.parametrize("name", _BRANCH_RULESETS)
def test_default_answer_requires_template_owned_checks(name: str) -> None:
    ruleset = _render(_RULESETS / name, [])
    assert _contexts(ruleset) == ["CI Success", "Release Notes Gate"], (
        f"{name} with no extra_required_checks must render the template-owned "
        f"contexts, but rendered {_contexts(ruleset)}"
    )


@pytest.mark.parametrize("name", _BRANCH_RULESETS)
def test_extra_checks_are_appended_in_order(name: str) -> None:
    ruleset = _render(_RULESETS / name, ["SPA sources", "Vendored assets"])
    assert _contexts(ruleset) == [
        "CI Success",
        "Release Notes Gate",
        "SPA sources",
        "Vendored assets",
    ], (
        f"{name} must require the template-owned checks and every declared domain "
        f"context, but rendered {_contexts(ruleset)}"
    )


@pytest.mark.parametrize("name", _BRANCH_RULESETS)
def test_check_names_needing_json_escaping_survive(name: str) -> None:
    # A context is a display name, so it can legitimately carry a quote,
    # a backslash, or a non-ASCII character.  `tojson` is what keeps such a
    # name from terminating the JSON string early; a bare `"{{ check }}"`
    # would render a file GitHub rejects, on an answer the project had every
    # right to write.
    awkward = ['Domain "SPA" check', "back\\slash", "café ✓"]
    ruleset = _render(_RULESETS / name, awkward)
    assert _contexts(ruleset) == ["CI Success", "Release Notes Gate", *awkward]
