"""Every plain `scripts/*.py` a render ships must pass through template-ci's
structural gate, with the same `per-file-ignores` a downstream's
`pyproject.toml` carries (#524).

The gate lists its files and its ignores by hand. A shipped script left off
the list lints green here and reddens every adopter's structural diff-gate
on the first `copier update` that touches it — `migrate_agent_instructions.py`
did exactly that for three adopters. `.jinja` scripts are out of reach: they
cannot be linted before a render, and the rendered project's own gate covers
them.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
_GATE_STEP = "Structural gate on shipped scripts (matches downstream diff-gate)"


def _excluded_scripts() -> set[str]:
    """`scripts/<name>.py` entries copier's `_exclude` keeps out of a render."""
    copier = yaml.safe_load((REPO / "copier.yml").read_text(encoding="utf-8"))
    return {
        entry for entry in copier["_exclude"] if re.fullmatch(r"scripts/\w+\.py", entry)
    }


def _shipped_plain_scripts() -> set[str]:
    return {
        f"scripts/{path.name}" for path in (REPO / "scripts").glob("*.py")
    } - _excluded_scripts()


def _gate_run() -> str:
    workflow = yaml.safe_load(
        (REPO / ".github" / "workflows" / "template-ci.yml").read_text(encoding="utf-8")
    )
    for job in workflow["jobs"].values():
        for step in job.get("steps", ()):
            if step.get("name") == _GATE_STEP:
                return step["run"]
    raise AssertionError(f"template-ci.yml has no step named {_GATE_STEP!r}")


def _gate_files(run: str) -> set[str]:
    return set(
        re.findall(r"scripts/\w+\.py(?=\s|$)", run.split("--target-version")[-1])
    )


def _gate_ignores(run: str) -> dict[str, set[str]]:
    match = re.search(r'--per-file-ignores "([^"]*)"', run)
    assert match, "the structural gate declares no --per-file-ignores"
    ignores: dict[str, set[str]] = {}
    for item in match.group(1).split(","):
        path, code = item.split(":")
        ignores.setdefault(path, set()).add(code)
    return ignores


def _pyproject_script_ignores() -> dict[str, set[str]]:
    """`scripts/` keys of the rendered project's structural-gate ignore block."""
    text = (REPO / "pyproject.toml.jinja").read_text(encoding="utf-8")
    block = text.split("{% if enable_structural_gate %}", 1)[1].split("{% endif %}", 1)[
        0
    ]
    found: dict[str, set[str]] = {}
    for path, codes in re.findall(r'^"(scripts/\w+\.py)" = \[([^\]]*)\]', block, re.M):
        found[path] = set(re.findall(r'"(S\d+)"', codes))
    return found


def test_every_shipped_plain_script_is_gated():
    missing = _shipped_plain_scripts() - _gate_files(_gate_run())
    assert not missing, (
        f"shipped scripts absent from template-ci's {_GATE_STEP!r} step: "
        f"{sorted(missing)} — add them to its argument list (and any needed "
        "per-file-ignores to pyproject.toml.jinja and the step alike)."
    )


def test_gate_ignores_mirror_the_shipped_pyproject():
    """The step restates pyproject.toml.jinja's `scripts/` exemptions so that
    what passes here is what passes downstream; the two must not drift. Only
    the scripts the gate lints are compared: `stamp_manifests.py` is a
    `.jinja` script the rendered project exempts but this gate never sees."""
    run = _gate_run()
    gated = _gate_files(run)
    shipped = {
        path: codes
        for path, codes in _pyproject_script_ignores().items()
        if path in gated
    }
    assert _gate_ignores(run) == shipped
