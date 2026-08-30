"""Tests for scripts/promote_upgrading.py (the per-minor split layout)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "promote_upgrading.py"
_spec = importlib.util.spec_from_file_location("promote_upgrading", SCRIPT)
assert _spec and _spec.loader
promote_upgrading = importlib.util.module_from_spec(_spec)
# Registered before exec: the script's frozen dataclass resolves its
# stringified annotations through sys.modules[cls.__module__] at class
# creation, which is None for an unregistered spec-loaded module.
sys.modules["promote_upgrading"] = promote_upgrading
_spec.loader.exec_module(promote_upgrading)

check = promote_upgrading.check
promote = promote_upgrading.promote
PLACEHOLDER = promote_upgrading.PLACEHOLDER

INDEX = """# Upgrading generated projects

Intro prose.

## v5.0 - Older release

Steps: [upgrading/v5.0.md](upgrading/v5.0.md).

## v5.1 - Previous release

Steps: [upgrading/v5.1.md](upgrading/v5.1.md).
"""

UNRELEASED = (
    INDEX
    + """
## Unreleased - New capability

Rename the env var.
"""
)


@pytest.fixture
def sections_dir(tmp_path: Path) -> Path:
    sections = tmp_path / "upgrading"
    sections.mkdir()
    (sections / "v5.0.md").write_text(
        "## v5.0 - Older release\n\nStep one.\n", encoding="utf-8"
    )
    (sections / "v5.1.md").write_text(
        "## v5.1 - Previous release\n\nStep two.\n", encoding="utf-8"
    )
    return sections


def test_minor_release_writes_the_per_minor_file_and_index_pointer() -> None:
    """The whole point: the version is chosen at release time, not before —
    and the content lands in the minor's own file, never in the index."""
    result = promote(UNRELEASED, "v5.2.0", existing_section=None)
    assert result.minor == "5.2"
    assert result.section_text is not None
    assert result.section_text.startswith("## v5.2 - New capability")
    assert "Rename the env var." in result.section_text
    assert "## v5.2 - New capability" in result.index_text
    assert "[upgrading/v5.2.md](upgrading/v5.2.md)" in result.index_text
    assert "Rename the env var." not in result.index_text
    assert "v5.2" in result.note


def test_promotion_leaves_a_fresh_unreleased_section_behind(
    sections_dir: Path,
) -> None:
    """The next contributor must not have to know to re-create the heading.

    An absent heading is how the file drifted in the first place: with no
    obvious place to write, migration notes either land under a hand-guessed
    version heading or are not written at all.
    """
    result = promote(UNRELEASED, "v5.2.0", existing_section=None)
    assert result.index_text.rstrip().endswith(PLACEHOLDER)
    assert result.section_text is not None
    (sections_dir / "v5.2.md").write_text(result.section_text, encoding="utf-8")
    assert not check(result.index_text, sections_dir), (
        "the promoted layout must satisfy its own invariants"
    )


def test_new_pointer_lands_between_released_sections_and_unreleased() -> None:
    """Sections run oldest to newest with Unreleased last."""
    text = promote(UNRELEASED, "v5.2.0", existing_section=None).index_text
    assert text.index("## v5.1") < text.index("## v5.2") < text.index("## Unreleased")


def test_patch_release_appends_into_the_existing_minor_file(
    sections_dir: Path,
) -> None:
    """A patch has no file of its own — the layout is organised by minor.

    The index's preamble tells readers a patch's migration work lives in
    its minor's file, so writing a second v5.1 file or index section would
    contradict the document and split one minor across two places.
    """
    existing = (sections_dir / "v5.1.md").read_text(encoding="utf-8")
    result = promote(UNRELEASED, "v5.1.1", existing_section=existing)
    assert result.minor == "5.1"
    assert result.section_text is not None
    assert result.section_text.startswith("## v5.1 - Previous release")
    body = result.section_text
    assert "Step two." in body
    assert "Rename the env var." in body
    assert body.index("Step two.") < body.index("Rename the env var.")
    assert result.index_text.count("## v5.1") == 1
    # The heading resets to a bare `## Unreleased`: its title described the
    # notes that just moved into v5.1, so leaving it would hand a stale title
    # to whatever the next minor release promotes.
    assert "## Unreleased - New capability" not in result.index_text
    assert result.index_text.rstrip().endswith(PLACEHOLDER)
    (sections_dir / "v5.1.md").write_text(result.section_text, encoding="utf-8")
    assert not check(result.index_text, sections_dir)


def test_an_empty_unreleased_section_is_not_promoted() -> None:
    """Most releases carry no migration steps; they must not gain a file."""
    text = INDEX + f"\n## Unreleased\n\n{PLACEHOLDER}\n"
    result = promote(text, "v5.2.0", existing_section=None)
    assert result.index_text == text
    assert result.section_text is None
    assert "nothing to promote" in result.note


def test_a_missing_unreleased_section_is_not_an_error() -> None:
    """Releasing straight after a release, before any new notes are written."""
    result = promote(INDEX, "v5.2.0", existing_section=None)
    assert result.index_text == INDEX
    assert result.section_text is None
    assert "nothing to promote" in result.note


def test_check_rejects_a_second_unreleased_section(sections_dir: Path) -> None:
    """Two would strand one of them above already-released sections."""
    text = UNRELEASED + "\n## Unreleased - Another\n\nMore.\n"
    problems = check(text, sections_dir)
    assert len(problems) == 1
    assert "exactly one is allowed" in problems[0]


def test_check_rejects_an_unreleased_section_that_is_not_last(
    sections_dir: Path,
) -> None:
    """Sections run oldest to newest; promotion assumes the tail."""
    text = INDEX.replace(
        "## v5.1 - Previous release",
        "## Unreleased - Stray\n\nNote.\n\n## v5.1 - Previous release",
    )
    problems = check(text, sections_dir)
    assert len(problems) == 1
    assert "not the last section" in problems[0]


def test_check_rejects_an_index_section_without_its_file(tmp_path: Path) -> None:
    sections = tmp_path / "upgrading"
    sections.mkdir()
    (sections / "v5.0.md").write_text(
        "## v5.0 - Older release\n\nStep one.\n", encoding="utf-8"
    )
    problems = check(INDEX, sections)
    assert any("upgrading/v5.1.md does not exist" in p for p in problems)


def test_check_rejects_full_content_creeping_back_into_the_index(
    sections_dir: Path,
) -> None:
    """The pointer-shape invariant is what keeps the index short: content
    quietly re-accumulating there recreates the 1400-line file the split
    removed."""
    text = INDEX.replace(
        "Steps: [upgrading/v5.1.md](upgrading/v5.1.md).",
        "Steps: [upgrading/v5.1.md](upgrading/v5.1.md).\n\nRename this.\nAnd this.\nAlso this.",
    )
    problems = check(text, sections_dir)
    assert any("more than" in p for p in problems)


def test_check_rejects_an_index_section_that_never_links_its_file(
    sections_dir: Path,
) -> None:
    text = INDEX.replace(
        "Steps: [upgrading/v5.1.md](upgrading/v5.1.md).", "All the steps inline."
    )
    problems = check(text, sections_dir)
    assert any("does not link upgrading/v5.1.md" in p for p in problems)


def test_check_rejects_an_unindexed_per_minor_file(sections_dir: Path) -> None:
    (sections_dir / "v5.3.md").write_text(
        "## v5.3 - Orphan\n\nInvisible steps.\n", encoding="utf-8"
    )
    problems = check(INDEX, sections_dir)
    assert any("v5.3.md has no" in p for p in problems)


def test_check_rejects_a_file_missing_its_own_heading(sections_dir: Path) -> None:
    """The notes pipeline concatenates these files and selects on the
    heading; a file without one silently drops out of every embed."""
    (sections_dir / "v5.1.md").write_text("Step two, headless.\n", encoding="utf-8")
    problems = check(INDEX, sections_dir)
    assert any("does not open with its own '## v5.1' heading" in p for p in problems)


def test_check_passes_the_repository_s_own_layout() -> None:
    """The invariant CI enforces, asserted against the real document."""
    repo_root = SCRIPT.parent.parent
    real = (repo_root / "UPGRADING.md").read_text(encoding="utf-8")
    assert check(real, repo_root / "upgrading") == []


@pytest.mark.parametrize("version", ["v5.2.0", "5.2.0", "v5.2.3"])
def test_version_is_read_as_a_minor_series(version: str) -> None:
    """Patch component and `v` prefix are both irrelevant to the minor."""
    result = promote(UNRELEASED, version, existing_section=None)
    assert result.minor == "5.2"
    assert "## v5.2 - New capability" in result.index_text
