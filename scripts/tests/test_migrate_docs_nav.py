"""Tests for scripts/migrate_docs_nav.py (#713).

The fixtures are a real ``copier update`` from v11.0.2 onto the goal-shaped nav
frame: ``head_mkdocs.yml.txt`` is the customised project's committed file and
``updated_mkdocs.yml.txt`` is what copier left in the working tree, diff3 conflict
markers included (hence ``.txt``: the file is deliberately not valid YAML).
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from migrate_docs_nav import park

FIX = Path(__file__).parent / "fixtures" / "nav_migration"
HEAD = (FIX / "head_mkdocs.yml.txt").read_text(encoding="utf-8")
UPDATED = (FIX / "updated_mkdocs.yml.txt").read_text(encoding="utf-8")
PROJECT_PAGES = ["api/vault.md", "extra.md", "guides/deep.md", "guides/para.md"]


def _leaves(node: object, out: list[str] | None = None) -> list[str]:
    out = [] if out is None else out
    if isinstance(node, list):
        for item in node:
            _leaves(item, out)
    elif isinstance(node, dict):
        for value in node.values():
            _leaves(value, out)
    elif isinstance(node, str):
        out.append(node)
    return out


def _nav(text: str) -> list[object]:
    return yaml.safe_load(text)["nav"]


def _unsorted(text: str) -> str:
    return text.split("PROJECT-NAV-UNSORTED-START", 1)[1].split(
        "PROJECT-NAV-UNSORTED-END", 1
    )[0]


def test_resolves_the_conflict_and_parks_every_project_entry() -> None:
    text, parked = park(UPDATED, HEAD)
    assert "<<<<<<<" not in text
    assert "|||||||" not in text
    assert ">>>>>>>" not in text
    assert sorted(parked) == PROJECT_PAGES
    for path in PROJECT_PAGES:
        assert path in _unsorted(text)


def test_keeps_old_section_titles_and_nesting() -> None:
    text, _ = park(UPDATED, HEAD)
    unsorted = yaml.safe_load(
        "\n".join(line[2:] for line in _unsorted(text).splitlines()[1:] if line.strip())
    )
    assert {
        "Guides": [
            {"PARA": "guides/para.md"},
            {"Advanced": [{"Deep dive": "guides/deep.md"}]},
        ]
    } in unsorted
    assert {"Python API": [{"Vault": "api/vault.md"}]} in unsorted
    assert "extra.md" in unsorted


def test_template_pages_stay_in_the_frame_and_are_not_parked() -> None:
    text, _ = park(UPDATED, HEAD)
    unsorted = _unsorted(text)
    for path in (
        "index.md",
        "guides/security-model.md",
        "deployment/docker.md",
        "guides/authorization.md",
        "releases/index.md",
    ):
        assert path not in unsorted
    leaves = _leaves(_nav(text))
    for path in (
        "index.md",
        "guides/security-model.md",
        "use/index.md",
        "contribute/docs-structure.md",
        *PROJECT_PAGES,
    ):
        assert path in leaves


def test_everything_outside_nav_is_untouched() -> None:
    text, _ = park(UPDATED, HEAD)
    before_nav = UPDATED.split("\nnav:\n", 1)[0]
    assert text.split("\nnav:\n", 1)[0] == before_nav


def test_second_run_changes_nothing() -> None:
    once, _ = park(UPDATED, HEAD)
    twice, parked = park(once, HEAD)
    assert twice == once
    assert parked == []


def test_already_migrated_head_is_a_no_op() -> None:
    once, _ = park(UPDATED, HEAD)
    again, parked = park(once, once)
    assert again == once
    assert parked == []


def test_file_without_nav_is_left_alone() -> None:
    text = "site_name: x\nplugins:\n  - search\n"
    assert park(text, HEAD) == (text, [])


def test_head_without_closing_marker_is_left_alone() -> None:
    broken_head = HEAD.replace("# PROJECT-NAV-END", "# (marker removed)")
    assert park(UPDATED, broken_head) == (UPDATED, [])


def test_frame_without_unsorted_block_is_left_alone() -> None:
    customised = UPDATED.replace("PROJECT-NAV-UNSORTED-START", "X").replace(
        "PROJECT-NAV-UNSORTED-END", "Y"
    )
    assert park(customised, HEAD) == (customised, [])
