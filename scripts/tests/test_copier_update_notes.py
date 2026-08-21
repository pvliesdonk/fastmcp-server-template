"""Tests for scripts/copier_update_notes.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "copier_update_notes.py"
_spec = importlib.util.spec_from_file_location("copier_update_notes", SCRIPT)
assert _spec and _spec.loader
copier_update_notes = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(copier_update_notes)

parse_minor = copier_update_notes.parse_minor
select_sections = copier_update_notes.select_sections
pick_target = copier_update_notes.pick_target

UPGRADING = """# Upgrading generated projects

Preamble prose with reading instructions.

## Before every upgrade

Generic checklist.

## v3.1 - Safe post-update generation

Patch v3.1.2 migration step.

## v3.2 - Tool visibility

Rescue the manifest bumper.

## v4.0 - Release branches

Re-run bootstrap.

## Unreleased

Rename the env var.
"""


def test_parse_minor_accepts_tags_and_rejects_shas() -> None:
    assert parse_minor("v3.1.3") == (3, 1)
    assert parse_minor("v4.0") == (4, 0)
    assert parse_minor("deadbeef") is None
    assert parse_minor("main") is None


def test_range_spans_previous_minor_through_target_minor() -> None:
    """The previous minor is included: its later patches may carry
    migration work the project has not done yet."""
    notes = select_sections(UPGRADING, "v3.1.1", "v3.2.0")
    assert "## v3.1 - Safe post-update generation" in notes
    assert "## v3.2 - Tool visibility" in notes
    assert "## v4.0" not in notes
    assert "## Unreleased" not in notes


def test_preamble_and_generic_checklist_are_never_embedded() -> None:
    notes = select_sections(UPGRADING, "v3.1.1", "v4.0.0")
    assert "Preamble prose" not in notes
    assert "## Before every upgrade" not in notes


def test_same_minor_jump_still_surfaces_that_minor_section() -> None:
    """v3.1.1 -> v3.1.3: the v3.1 section may describe v3.1.2/v3.1.3 work."""
    notes = select_sections(UPGRADING, "v3.1.1", "v3.1.3")
    assert "## v3.1" in notes
    assert "## v3.2" not in notes


def test_unversioned_target_runs_through_unreleased() -> None:
    """A branch/sha run may carry notes not yet under a version heading."""
    notes = select_sections(UPGRADING, "v3.2.0", "deadbeef")
    assert "## v3.2" in notes
    assert "## v4.0" in notes
    assert "## Unreleased" in notes
    assert "## v3.1" not in notes


def test_unparseable_previous_selects_nothing() -> None:
    """First tracked update: the caller links the full file instead."""
    assert select_sections(UPGRADING, "", "v4.0.0") == ""
    assert select_sections(UPGRADING, "abc123", "v4.0.0") == ""


def test_sections_keep_their_bodies_and_file_order() -> None:
    notes = select_sections(UPGRADING, "v3.1.0", "v4.0.0")
    assert "Patch v3.1.2 migration step." in notes
    assert "Rescue the manifest bumper." in notes
    assert "Re-run bootstrap." in notes
    assert notes.index("## v3.1") < notes.index("## v3.2") < notes.index("## v4.0")


TAGS = [
    "v3.1.2",
    "v3.1.3",
    "v3.2.0",
    "v4.0.0",
    "v4.1.0",
    "v4.1.1",
    "v5.0.0",
    "v5.4.0",
    "v5.5.0-rc.1",
]


def test_pick_target_steps_one_major_to_its_newest_stable_tag() -> None:
    assert pick_target("v3.1.1", TAGS) == "v4.1.1"
    assert pick_target("v4.0.0", TAGS) == "v5.4.0"


def test_pick_target_defers_to_copier_default_within_a_major() -> None:
    """Minor/patch drift only: print nothing, copier's latest-tag default
    already does the right thing."""
    assert pick_target("v5.0.0", TAGS) == ""


def test_pick_target_skips_release_candidates() -> None:
    """v5.5.0-rc.1 must never become an automated target."""
    assert pick_target("v4.1.1", TAGS) == "v5.4.0"


def test_pick_target_bridges_a_missing_major() -> None:
    """A fleet that never shipped a v4: from v3, the smallest major ahead
    is v5."""
    tags = ["v3.6.0", "v5.0.0", "v5.1.0"]
    assert pick_target("v3.6.0", tags) == "v5.1.0"


def test_pick_target_on_unversioned_previous_prints_nothing() -> None:
    assert pick_target("deadbeef", TAGS) == ""
    assert pick_target("", TAGS) == ""


def _run_cli(tmp_path: Path, monkeypatch, *extra: str) -> Path:
    upgrading = tmp_path / "UPGRADING.md"
    upgrading.write_text(UPGRADING, encoding="utf-8")
    output = tmp_path / "notes.md"
    monkeypatch.setattr(
        "sys.argv",
        [
            "copier_update_notes.py",
            "notes",
            "--upgrading",
            str(upgrading),
            "--previous",
            "v3.1.1",
            "--target",
            "v4.0.0",
            "--output",
            str(output),
            *extra,
        ],
    )
    assert copier_update_notes.main() == 0
    return output


def test_cli_writes_the_selection(tmp_path: Path, monkeypatch) -> None:
    output = _run_cli(tmp_path, monkeypatch)
    assert "## v3.1" in output.read_text(encoding="utf-8")


def test_cli_replaces_an_oversized_selection_with_a_note(
    tmp_path: Path, monkeypatch
) -> None:
    """A GitHub PR body caps at 65536 chars; past --max-chars the embed
    gives way to a pointer at the linked full file."""
    output = _run_cli(tmp_path, monkeypatch, "--max-chars", "10")
    text = output.read_text(encoding="utf-8")
    assert "too long to embed" in text
    assert "## v3.1" not in text


def test_cli_pick_target_prints_the_chosen_ref(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    tags_file = tmp_path / "tags.txt"
    tags_file.write_text("\n".join(TAGS) + "\n", encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "copier_update_notes.py",
            "pick-target",
            "--previous",
            "v3.1.1",
            "--tags",
            str(tags_file),
        ],
    )
    assert copier_update_notes.main() == 0
    assert capsys.readouterr().out.strip() == "v4.1.1"
