"""Supply-chain rules for the workflows a project actually runs (#694).

SonarCloud scores each downstream on its rendered `.github/` tree, while the
template's own analysis cannot read the `.yml.jinja` sources, so a template
change could lower every project's rating without moving the template's.
These tests read the smoke render instead of the sources, which is the tree
SonarCloud sees.  Action pins are held by `test_renovate_custom_manager.py`.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import pytest
import yaml

if TYPE_CHECKING:
    from pathlib import Path

_NOSONAR = "# NOSONAR(githubactions:S8541"


def _workflow_files(render: Path) -> list[Path]:
    github = render / ".github"
    return sorted(
        p for p in github.rglob("*") if p.is_file() and p.suffix in (".yml", ".yaml")
    )


def _run_scripts(node: Any) -> list[str]:
    """Every `run:` value under *node* — workflow steps and composite steps."""
    found: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "run" and isinstance(value, str):
                found.append(value)
            else:
                found += _run_scripts(value)
    elif isinstance(node, list):
        for item in node:
            found += _run_scripts(item)
    return found


def _code_lines(render: Path) -> list[tuple[str, str]]:
    """``(file, command line)`` for every line of every `run:` script.

    Read through YAML so prose (descriptions, comments) never counts.  A
    line keeps the source line's trailing YAML comment when it has one, so
    the documented NOSONAR exceptions stay visible to the checks.
    """
    lines = []
    for path in _workflow_files(render):
        raw = path.read_text(encoding="utf-8")
        rel = str(path.relative_to(render))
        for script in _run_scripts(yaml.safe_load(raw)):
            for line in script.splitlines():
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                source = next((s for s in raw.splitlines() if line.strip() in s), line)
                lines.append((rel, source))
    return lines


@pytest.fixture(scope="module", params=["smoke_render", "review_on_render"])
def render(request: pytest.FixtureRequest) -> Path:
    """The default render, and one with the review workflow it gates off."""
    return request.getfixturevalue(request.param)


@pytest.fixture(scope="module")
def code_lines(render: Path) -> list[tuple[str, str]]:
    return _code_lines(render)


def test_every_uv_run_skips_the_implicit_sync(code_lines) -> None:
    """`uv run` after the job's locked sync must not re-resolve or build."""
    bad = [
        f"{where}: {line.strip()}"
        for where, line in code_lines
        if re.search(r"\buv run\b", line)
        and "--no-sync" not in line
        and "--no-project" not in line
        and "allowedTools" not in line
    ]
    assert not bad, "uv run without --no-sync:\n" + "\n".join(bad)


def test_every_uv_sync_is_locked(code_lines) -> None:
    """A sync resolves from uv.lock, or says why SonarCloud flags it anyway."""
    bad = [
        f"{where}: {line.strip()}"
        for where, line in code_lines
        if re.search(r"\buv sync\b", line)
        and not re.search(r"--(locked|frozen)\b", line)
        and _NOSONAR not in line
    ]
    assert not bad, "uv sync without --locked/--frozen:\n" + "\n".join(bad)


def test_every_curl_is_https_only(code_lines) -> None:
    bad = [
        f"{where}: {line.strip()}"
        for where, line in code_lines
        if re.search(r"\bcurl\b", line) and "--proto '=https'" not in line
    ]
    assert not bad, "curl without --proto '=https':\n" + "\n".join(bad)


def test_nothing_is_downloaded_into_a_shell(code_lines) -> None:
    bad = [
        f"{where}: {line.strip()}"
        for where, line in code_lines
        if re.search(r"\b(curl|wget)\b[^|]*\|\s*(sudo\s+)?(ba|z)?sh\b", line)
    ]
    assert not bad, "downloaded script piped into a shell:\n" + "\n".join(bad)


def test_no_workflow_grants_write_at_workflow_level(render: Path) -> None:
    """Write scopes belong on the job that needs them, not on every job."""
    bad = []
    workflows = sorted((render / ".github" / "workflows").glob("*.yml"))
    assert workflows, "no rendered workflows found"
    for path in workflows:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        permissions = doc.get("permissions") if isinstance(doc, dict) else None
        if permissions == "write-all" or (
            isinstance(permissions, dict) and "write" in permissions.values()
        ):
            bad.append(str(path.relative_to(render)))
    assert not bad, f"workflow-level write permissions in: {bad}"


def test_the_guards_see_the_render(code_lines) -> None:
    """Non-vacuous: the render has workflows, uv runs and a verified download."""
    text = "\n".join(line for _, line in code_lines)
    assert "uv run --no-sync" in text
    assert "sha256sum -c" in text
