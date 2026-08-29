"""Contracts of reusable-ci.yml, the CI gate every downstream runs (#538).

The rendered ``ci.yml`` is a stub calling this repo's reusable workflow, so
downstream test suites can no longer introspect the gate's job bodies. The
contracts they used to assert move here, template-side, against the source
file itself:

- the own-branch ``codecov/patch`` poster reports under all outcomes
  (mirrors the fork-fallback half still asserted downstream in
  ``tests/test_release_flow_contract.py``);
- the two workflow_call inputs exist with the defaults copier.yml declares,
  so a stub rendered from default answers and a caller omitting an input
  agree;
- the stub's ``with:``/``secrets:`` wiring matches the declared surface.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
REUSABLE_CI = REPO / ".github" / "workflows" / "reusable-ci.yml"
STUB = REPO / ".github" / "workflows" / "ci.yml.jinja"


def _workflow_call() -> dict:
    doc = yaml.safe_load(REUSABLE_CI.read_text(encoding="utf-8"))
    # PyYAML parses the bare key `on:` as boolean True.
    on = doc.get("on") or doc.get(True)
    return on["workflow_call"]


def test_codecov_patch_poster_posts_under_all_outcomes() -> None:
    """The own-branch ``codecov/patch`` poster reports something, always.

    Same invariant, and the same drift history (#476), as the fork-fallback
    half asserted in the rendered ``test_release_flow_contract.py``: a
    required context that never reports leaves a pull request waiting
    forever, so "post an ``error``" and "post nothing" are not equivalent.
    """
    text = REUSABLE_CI.read_text(encoding="utf-8")
    poster = text.index("name: Post codecov/patch status")
    step = text[poster : poster + 2000]
    assert "always()" in step, (
        "the codecov/patch posting step must run under all outcomes"
    )
    assert "'error'" in step or '"error"' in step, (
        "the posting step must default to an `error` state when the "
        "coverage result is missing"
    )


def test_inputs_match_copier_answer_defaults() -> None:
    """workflow_call input defaults mirror copier.yml's answer defaults.

    A caller that omits an input (or a hand-written stub) must behave like a
    default-answers render; a drifted default silently flips a gate on or
    off for exactly those callers.
    """
    copier = yaml.safe_load((REPO / "copier.yml").read_text(encoding="utf-8"))
    inputs = _workflow_call()["inputs"]
    expected = {
        "include-mcp-apps-scaffold": copier["include_mcp_apps_scaffold"]["default"],
        "enable-structural-gate": copier["enable_structural_gate"]["default"],
    }
    for name, default in expected.items():
        assert inputs[name]["type"] == "boolean", name
        assert inputs[name].get("default") == default, (
            f"workflow_call input {name!r} defaults to "
            f"{inputs[name].get('default')!r}, but copier.yml's answer "
            f"defaults to {default!r}"
        )


def test_stub_wires_the_declared_surface() -> None:
    """The stub passes exactly the inputs and secrets the workflow declares."""
    wc = _workflow_call()
    stub = STUB.read_text(encoding="utf-8")
    for name in wc["inputs"]:
        assert f"{name}:" in stub, f"stub does not pass input {name!r}"
    for name in wc["secrets"]:
        assert f"{name}:" in stub, f"stub does not pass secret {name!r}"
    assert "reusable-ci.yml@{{ _copier_conf.vcs_ref_hash }}" in stub, (
        "stub must pin the reusable workflow to the rendering template commit"
    )
