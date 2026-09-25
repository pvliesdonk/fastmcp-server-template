"""Tests for scripts/repo_about.py and the bootstrap step that sends its output.

GitHub rejects the whole topics PUT when any one name breaks its rules, so a
single keyword like "Model Context Protocol" in `PROJECT-KEYWORDS` would fail
every bootstrap run.  The normaliser is what stands between the two.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import yaml
from jinja2 import Environment

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "repo_about.py"
_spec = importlib.util.spec_from_file_location("repo_about", SCRIPT)
assert _spec and _spec.loader
repo_about = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(repo_about)

_TOPIC = re.compile(r"^[a-z0-9][a-z0-9-]{0,49}$")


def _render(template: Path, **context: object) -> str:
    env = Environment(keep_trailing_newline=True, autoescape=False)
    return env.from_string(template.read_text(encoding="utf-8")).render(**context)


def test_normalise_topic_meets_github_rules() -> None:
    assert repo_about.normalise_topic("Model Context Protocol") == (
        "model-context-protocol"
    )
    assert repo_about.normalise_topic("OCR/PDF") == "ocr-pdf"
    assert repo_about.normalise_topic("--vault--") == "vault"
    assert repo_about.normalise_topic("___") == ""
    long = repo_about.normalise_topic("a" * 49 + "-bcd")
    assert len(long) <= 50
    assert not long.endswith("-")


def test_topics_puts_fixed_first_dedupes_and_caps() -> None:
    names = repo_about.topics(["mcp", "MCP", "mcp-server", "", *map(str, range(30))])
    assert names[:2] == ["mcp-server", "mcp"]
    assert len(names) == len(set(names)) == 20
    assert all(_TOPIC.match(name) for name in names)


def test_about_leaves_out_fields_pyproject_lacks() -> None:
    assert repo_about.about({}) == {"names": ["mcp-server"]}
    assert repo_about.about({"project": {"description": "  "}}) == {
        "names": ["mcp-server"]
    }


def test_about_from_the_rendered_pyproject() -> None:
    context = {
        "project_name": "demo-mcp",
        "pypi_name": "demo-mcp",
        "python_module": "demo_mcp",
        "github_org": "acme",
        "domain_description": "Demo things over MCP",
        "author_name": "A",
        "author_email": "a@example.com",
    }
    pyproject = tomllib.loads(_render(REPO / "pyproject.toml.jinja", **context))
    about = repo_about.about(pyproject)
    assert about["description"] == "Demo things over MCP"
    assert about["homepage"] == "https://acme.github.io/demo-mcp/"
    names = about["names"]
    assert isinstance(names, list)
    assert names[0] == "mcp-server"
    assert {"mcp", "model-context-protocol", "fastmcp", "demo-mcp"} <= set(names)
    assert all(_TOPIC.match(name) for name in names)


def test_cli_prints_json(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\ndescription = "X"\nkeywords = ["Vault"]\n'
        '[project.urls]\nDocumentation = "https://d.example/"\n',
        encoding="utf-8",
    )
    out = subprocess.run(
        [sys.executable, str(SCRIPT), str(pyproject)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert json.loads(out) == {
        "description": "X",
        "homepage": "https://d.example/",
        "names": ["mcp-server", "vault"],
    }


def test_bootstrap_sends_the_about_block() -> None:
    workflow = yaml.safe_load(
        _render(REPO / ".github" / "workflows" / "bootstrap.yml.jinja")
    )
    # PyYAML reads the bare `on:` key as boolean True.
    paths = workflow[True]["push"]["paths"]
    assert "pyproject.toml" in paths, "a keyword edit must re-sync the topics"
    assert "scripts/repo_about.py" in paths
    steps = {s.get("name"): s for s in workflow["jobs"]["settings"]["steps"]}
    step = steps["Set description, website and topics"]
    assert step["env"]["GH_TOKEN"] == "${{ secrets.RELEASE_TOKEN }}", (
        "editing the About block needs administration:write"
    )
    run = step["run"]
    assert "python3 scripts/repo_about.py" in run
    assert 'gh api -X PATCH "repos/${REPO}" --input -' in run
    assert 'gh api -X PUT "repos/${REPO}/topics" --input -' in run
