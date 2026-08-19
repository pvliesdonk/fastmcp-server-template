"""Tests for scripts/promote_upgrading.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "promote_upgrading.py"
_spec = importlib.util.spec_from_file_location("promote_upgrading", SCRIPT)
assert _spec and _spec.loader
promote_upgrading = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(promote_upgrading)

check = promote_upgrading.check
promote = promote_upgrading.promote
PLACEHOLDER = promote_upgrading.PLACEHOLDER

RELEASED = """# Upgrading generated projects

Intro prose.

## v5.0 - Older release

Step one.

## v5.1 - Previous release

Step two.
"""

UNRELEASED = (
    RELEASED
    + """
## Unreleased - New capability

Rename the env var.
"""
)


def test_minor_release_renames_the_heading_and_keeps_its_title() -> None:
    """The whole point: the version is chosen at release time, not before."""
    text, note = promote(UNRELEASED, "v5.2.0")
    assert "## v5.2 - New capability" in text
    assert "Rename the env var." in text
    assert "v5.2" in note


def test_promotion_leaves_a_fresh_unreleased_section_behind() -> None:
    """The next contributor must not have to know to re-create the heading.

    An absent heading is how the file drifted in the first place: with no
    obvious place to write, migration notes either land under a hand-guessed
    version heading or are not written at all.
    """
    text, _ = promote(UNRELEASED, "v5.2.0")
    assert text.rstrip().endswith(PLACEHOLDER)
    assert not check(text), "the promoted file must satisfy its own invariants"


def test_patch_release_appends_into_the_existing_minor_section() -> None:
    """A patch has no section of its own — the file is organised by minor.

    Its own preamble tells readers a patch's migration work lives in its
    minor's section, so promoting a patch to ``## v5.1`` a second time would
    contradict the document and split one minor across two headings.
    """
    text, note = promote(UNRELEASED, "v5.1.1")
    assert "## v5.1 - Previous release" in text
    assert text.count("## v5.1") == 1
    body = text.split("## v5.1 - Previous release")[1].split("## ")[0]
    assert "Step two." in body
    assert "Rename the env var." in body
    assert "v5.1" in note
    # The heading resets to a bare `## Unreleased`: its title described the
    # notes that just moved into v5.1, so leaving it would hand a stale title
    # to whatever the next minor release promotes.
    assert "## Unreleased - New capability" not in text
    assert text.rstrip().endswith(PLACEHOLDER)
    assert not check(text)


def test_an_empty_unreleased_section_is_not_promoted() -> None:
    """Most releases carry no migration steps; they must not gain a section."""
    text = RELEASED + f"\n## Unreleased\n\n{PLACEHOLDER}\n"
    promoted, note = promote(text, "v5.2.0")
    assert promoted == text
    assert "nothing to promote" in note


def test_a_missing_unreleased_section_is_not_an_error() -> None:
    """Releasing straight after a release, before any new notes are written."""
    promoted, note = promote(RELEASED, "v5.2.0")
    assert promoted == RELEASED
    assert "nothing to promote" in note


def test_check_rejects_a_second_unreleased_section() -> None:
    """Two would strand one of them above already-released sections."""
    text = UNRELEASED + "\n## Unreleased - Another\n\nMore.\n"
    problems = check(text)
    assert len(problems) == 1
    assert "exactly one is allowed" in problems[0]


def test_check_rejects_an_unreleased_section_that_is_not_last() -> None:
    """Sections run oldest to newest; promotion assumes the tail."""
    text = RELEASED.replace(
        "## v5.1 - Previous release",
        "## Unreleased - Stray\n\nNote.\n\n## v5.1 - Previous release",
    )
    problems = check(text)
    assert len(problems) == 1
    assert "not the last section" in problems[0]


def test_check_passes_the_repository_s_own_file() -> None:
    """The invariant CI enforces, asserted against the real document."""
    real = (SCRIPT.parent.parent / "UPGRADING.md").read_text(encoding="utf-8")
    assert check(real) == []


@pytest.mark.parametrize("version", ["v5.2.0", "5.2.0", "v5.2.3"])
def test_version_is_read_as_a_minor_series(version: str) -> None:
    """Patch component and `v` prefix are both irrelevant to the heading."""
    text, _ = promote(UNRELEASED, version)
    assert "## v5.2 - New capability" in text
