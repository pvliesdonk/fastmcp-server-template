"""Tests for scripts/gen_reference.py (#716).

No ``from __future__ import annotations`` here: FastMCP appends a JSON-schema
sentence to every prompt argument under postponed annotations.
"""

import sys
from enum import StrEnum
from pathlib import Path

import pytest
import typer
from fastmcp import FastMCP

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from gen_reference import (
    GenerationError,
    check,
    collect,
    render,
    update_nav,
    write,
)


class Mode(StrEnum):
    fast = "fast"
    slow = "slow"


def _server() -> FastMCP:
    mcp = FastMCP("demo")

    @mcp.tool(
        annotations={"title": "Read Note", "read_only_hint": True},
        tags={"group:reading", "vault"},
    )
    async def read(path: str, mode: Mode = Mode.fast, limit: int | None = None) -> str:
        """Read a note; returns its text and etag.

        Use search for notes you cannot name.

        Args:
            path: Vault-relative path ending in .md.
            mode: How much to read.
            limit: Lines to return; omit for all.

        Returns:
            The note's text and its etag.

        Raises:
            ToolError: the path names no note.
        """
        return f"{path}{mode}{limit}"

    @mcp.tool(
        annotations={
            "title": "Save Note",
            "read_only_hint": False,
            "destructive_hint": True,
            "idempotent_hint": True,
        },
        tags={"write"},
    )
    async def save(path: str, content: str) -> dict[str, str]:
        """Create or replace a note; returns its path_etag pair, see `etag`.

        Args:
            path: Vault-relative path.
            content: Complete Markdown.
        """
        return {"path": path, "content": content}

    @mcp.tool(
        annotations={"title": "Ping", "read_only_hint": True},
        meta={"ui": {"visibility": ["app"]}},
    )
    async def ping() -> str:
        """Check that the service is alive; returns "pong". Cheap to call."""
        return "pong"

    @mcp.resource("vault://conventions", mime_type="text/markdown")
    def conventions() -> str:
        """The vault's writing conventions."""
        return "# Conventions"

    @mcp.resource("note://{path}")
    def note(path: str) -> str:
        """One note by path."""
        return path

    @mcp.prompt
    def summarise(path: str, style: str = "short") -> str:
        """Summarise a note.

        Args:
            path: The note to summarise.
            style: short or long.
        """
        return f"{style}: {path}"

    return mcp


def _app() -> typer.Typer:
    app = typer.Typer(help="Demo server.")

    @app.command()
    def serve(
        transport: str = typer.Option("stdio", envvar="DEMO_TRANSPORT", help="Wire."),
        port: int = typer.Option(8000, help="TCP port."),
    ) -> None:
        """Run the server."""

    @app.command()
    def reindex(vault: Path = typer.Argument(..., help="Vault to index.")) -> None:  # noqa: B008
        """Rebuild the index."""

    return app


@pytest.fixture
def reference():
    return collect(_server(), _app(), "demo")


def test_groups_come_from_the_tag_then_the_module(reference) -> None:
    assert list(reference.groups) == ["reading", "test_gen_reference"]
    assert [t.name for t in reference.groups["reading"]] == ["read"]
    assert [t.name for t in reference.groups["test_gen_reference"]] == ["save", "ping"]


def test_two_group_tags_is_an_error() -> None:
    mcp = FastMCP("bad")

    @mcp.tool(tags={"group:a", "group:b"})
    def t() -> str:
        """Two homes."""
        return ""

    with pytest.raises(GenerationError, match="t"):
        collect(mcp, _app(), "demo")


def test_tool_entry_carries_wire_description_and_docstring_sections(reference) -> None:
    read = reference.groups["reading"][0]
    assert read.title == "Read Note"
    assert read.description == (
        "Read a note; returns its text and etag.\n\nUse search for notes you cannot name."
    )
    assert "Returns:" not in read.description
    assert read.returns == "The note's text and its etag."
    assert read.raises == ["ToolError: the path names no note."]
    assert read.security == ["Read-only."]
    assert read.tags == ["vault"]
    assert [(p.name, p.type, p.default) for p in read.params] == [
        ("path", "string", "required"),
        ("mode", "fast | slow", '"fast"'),
        ("limit", "integer | null", "null"),
    ]
    assert read.params[0].description == "Vault-relative path ending in .md."


def test_security_line_and_output_type(reference) -> None:
    save, ping = reference.groups["test_gen_reference"]
    assert save.security == ["Destructive.", "Idempotent."]
    assert save.returns == ""
    assert save.output_type == "object"
    assert ping.params == []
    assert ping.output_type == "string"
    assert (
        ping.description
        == 'Check that the service is alive; returns "pong". Cheap to call.'
    )
    assert ping.security == ["Read-only.", "Visible to: app."]


def test_resources_prompts_and_cli(reference) -> None:
    assert [(r.name, r.uri, r.mime_type) for r in reference.resources] == [
        ("conventions", "vault://conventions", "text/markdown"),
        ("note", "note://{path}", "text/plain"),
    ]
    assert reference.resources[1].parameters == ["path"]
    (prompt,) = reference.prompts
    assert prompt.name == "summarise"
    assert [(a.name, a.required, a.description) for a in prompt.arguments] == [
        ("path", True, "The note to summarise."),
        ("style", False, "short or long."),
    ]
    assert reference.cli.name == "demo"
    assert reference.cli.help == "Demo server."
    serve, reindex = reference.cli.commands
    assert serve.name == "serve"
    assert [(o.name, o.envvar, o.default, o.help) for o in serve.options] == [
        ("--transport", "DEMO_TRANSPORT", "stdio", "Wire."),
        ("--port", "", "8000", "TCP port."),
    ]
    assert [(a.name, a.help) for a in reindex.arguments] == [
        ("VAULT", "Vault to index.")
    ]


def test_render_produces_the_page_set_with_slots(reference, tmp_path: Path) -> None:
    pages = render(reference, tmp_path / "docs")
    assert sorted(pages) == [
        "reference/cli.md",
        "reference/prompts.md",
        "reference/resources.md",
        "reference/tools/index.md",
        "reference/tools/reading.md",
        "reference/tools/test_gen_reference.md",
    ]
    reading = pages["reference/tools/reading.md"]
    assert reading.startswith("---\ndescription:")
    assert "kind: reference" in reading
    assert "<!-- generated by scripts/gen_reference.py" in reading
    assert "<!-- DOMAIN-INTRO-START -->" in reading
    assert "## `read`" in reading
    order = [
        reading.index(s)
        for s in (
            "## `read`",
            "Read-only.",
            "Use search for notes",
            "**Parameters**",
            "| `path` | string | required |",
            "**Returns**",
            "**Outcomes and errors**",
            "<!-- DOMAIN-EXAMPLE-read-START -->",
        )
    ]
    assert order == sorted(order)
    index = pages["reference/tools/index.md"]
    assert "security-model.md" in index
    assert "| [`read`](reading.md#read) |" in index
    assert '| Ping | Check that the service is alive; returns "pong". |' in index
    assert (
        "| Test gen reference | [`save`](test_gen_reference.md#save) | Save Note |"
        in index
    )
    assert "## `demo serve`" in pages["reference/cli.md"]
    assert "`DEMO_TRANSPORT`" in pages["reference/cli.md"]
    assert "`note://{path}`" in pages["reference/resources.md"]
    assert "<!-- DOMAIN-EXAMPLE-summarise-START -->" in pages["reference/prompts.md"]
    saving = pages["reference/tools/test_gen_reference.md"]
    assert "returns its `path_etag` pair, see `etag`" in saving


def test_slots_survive_regeneration_and_orphans_fail(reference, tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    write(docs, render(reference, docs))
    page = docs / "reference" / "tools" / "reading.md"
    text = page.read_text(encoding="utf-8")
    text = text.replace(
        "<!-- DOMAIN-INTRO-START -->",
        "<!-- DOMAIN-INTRO-START -->\nReading is where you start.",
    ).replace(
        "<!-- DOMAIN-EXAMPLE-read-START -->",
        "<!-- DOMAIN-EXAMPLE-read-START -->\n```python\nread('a.md')\n```",
    )
    page.write_text(text, encoding="utf-8")
    again = render(reference, docs)["reference/tools/reading.md"]
    assert "Reading is where you start." in again
    assert "read('a.md')" in again
    page.write_text(
        text.replace("DOMAIN-EXAMPLE-read-", "DOMAIN-EXAMPLE-gone-"), encoding="utf-8"
    )
    with pytest.raises(GenerationError, match="DOMAIN-EXAMPLE-gone"):
        render(reference, docs)


def test_check_reports_drift_and_stale_files(reference, tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    pages = render(reference, docs)
    assert check(docs, pages) != []
    write(docs, pages)
    assert check(docs, pages) == []
    stale = docs / "reference" / "tools" / "old.md"
    stale.write_text(pages["reference/tools/reading.md"], encoding="utf-8")
    assert any("old.md" in line for line in check(docs, pages))
    write(docs, pages)
    assert not stale.exists()
    (docs / "reference" / "tools" / "hand.md").write_text("# mine\n", encoding="utf-8")
    write(docs, pages)
    assert (docs / "reference" / "tools" / "hand.md").exists()


def test_update_nav_fills_the_generated_region(reference) -> None:
    before = (
        "nav:\n"
        "  - Reference:\n"
        "      - Tools:\n"
        "          - Overview: reference/tools/index.md\n"
        "          # GENERATED-NAV-TOOLS-START — one entry per tool group; written by scripts/gen_reference.py\n"
        "          - Old: reference/tools/old.md\n"
        "          # GENERATED-NAV-TOOLS-END\n"
        "      - Resources: reference/resources.md\n"
    )
    after = update_nav(before, reference)
    assert "          - Reading: reference/tools/reading.md\n" in after
    assert (
        "          - Test gen reference: reference/tools/test_gen_reference.md\n"
        in after
    )
    assert "old.md" not in after
    assert after.endswith("      - Resources: reference/resources.md\n")
    assert update_nav(after, reference) == after
    with pytest.raises(GenerationError, match="GENERATED-NAV-TOOLS"):
        update_nav("nav:\n  - Home: index.md\n", reference)


def test_project_discovery_falls_back_to_project_scripts(tmp_path: Path) -> None:
    from gen_reference import BuildError, _project

    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\n[project.scripts]\ndemo-mcp = "demo_mcp.cli:main"\n',
        encoding="utf-8",
    )
    assert _project(tmp_path) == ("demo_mcp", "demo-mcp")
    (tmp_path / ".copier-answers.yml").write_text(
        "python_module: other\nproject_name: other-mcp\n", encoding="utf-8"
    )
    assert _project(tmp_path) == ("other", "other-mcp")
    (tmp_path / ".copier-answers.yml").unlink()
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\n', encoding="utf-8"
    )
    with pytest.raises(BuildError):
        _project(tmp_path)


def test_prose_formatting_leaves_links_and_abbreviations_alone() -> None:
    from gen_reference import _first_sentence, _prose

    assert _prose("see [the guide](vault_guide.md) and `raw_id` or my_var") == (
        "see [the guide](vault_guide.md) and `raw_id` or `my_var`"
    )
    assert _first_sentence("Reads notes, e.g. daily ones. Then more.") == (
        "Reads notes, e.g. daily ones."
    )
