"""``scripts/check_references.py`` enforces the reference contract (#593).

A reference under ``docs/design/reference/`` is dated, sourced, and pinned;
the ``researching-references`` skill says why.  These tests exercise the
checker on synthetic pages so the shipped ``tests/test_reference_docs.py``
can trust it.
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_references as cr

TODAY = dt.date(2026, 9, 6)

GOOD = """\
---
title: Example subject
subject: How example behaves
subject_version: "1.x"
valid_for: "Example 1.x"
researched: 2026-09-06
review_by: 2027-03-06
status: current
sources:
  - id: spec
    title: Example spec
    url: https://example.invalid/spec
    accessed: 2026-09-06
---

# Example subject

- A claim. [source: spec] [pins: tests/test_example.py::test_claim]
- Another. [observed: ran `example --dump`]
- A guess. [unverified]
"""


def _repo(
    tmp_path: Path, text: str = GOOD, name: str = "example.md"
) -> tuple[Path, Path]:
    root = tmp_path / "docs" / "design" / "reference"
    root.mkdir(parents=True, exist_ok=True)
    (root / name).write_text(text, encoding="utf-8")
    tests = tmp_path / "tests"
    tests.mkdir(exist_ok=True)
    (tests / "test_example.py").write_text(
        "def test_claim() -> None:\n    assert True\n", encoding="utf-8"
    )
    return tmp_path, root


def _findings(tmp_path: Path, text: str = GOOD) -> list[str]:
    repo, root = _repo(tmp_path, text)
    ref = cr.parse_reference(root / "example.md", text)
    return cr.findings(ref, repo_root=repo, root=root)


def test_good_reference_is_clean(tmp_path: Path) -> None:
    assert _findings(tmp_path) == []


def test_marker_counts(tmp_path: Path) -> None:
    _, root = _repo(tmp_path)
    ref = cr.parse_reference(root / "example.md", GOOD)
    assert (
        ref.count("source"),
        ref.count("observed"),
        ref.count("unverified"),
        ref.count("pins"),
    ) == (1, 1, 1, 1)


def test_missing_frontmatter_is_a_parse_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no YAML frontmatter"):
        cr.parse_reference(tmp_path / "x.md", "# no frontmatter\n")


@pytest.mark.parametrize("key", cr.REQUIRED_KEYS)
def test_every_required_key_is_enforced(tmp_path: Path, key: str) -> None:
    lines = [
        ln for ln in GOOD.splitlines(keepends=True) if not ln.startswith(f"{key}:")
    ]
    if key == "sources":
        lines = [
            ln
            for ln in lines
            if not ln.startswith("  - ") and not ln.startswith("    ")
        ]
    problems = _findings(tmp_path, "".join(lines))
    assert any(f"missing frontmatter key `{key}`" in p for p in problems), problems


def test_dates_must_be_iso(tmp_path: Path) -> None:
    problems = _findings(
        tmp_path, GOOD.replace("review_by: 2027-03-06", "review_by: next spring")
    )
    assert any("`review_by` must be an ISO date" in p for p in problems), problems


def test_status_is_an_enum(tmp_path: Path) -> None:
    problems = _findings(tmp_path, GOOD.replace("status: current", "status: fresh"))
    assert any("`status` must be one of" in p for p in problems), problems


def test_superseded_needs_an_existing_replacement(tmp_path: Path) -> None:
    text = GOOD.replace("status: current", "status: superseded")
    problems = _findings(tmp_path, text)
    assert any("requires `superseded_by" in p for p in problems), problems
    text2 = text.replace(
        "status: superseded", "status: superseded\nsuperseded_by: newer.md"
    )
    problems = _findings(tmp_path, text2)
    assert any("does not exist under" in p for p in problems), problems
    root = tmp_path / "docs" / "design" / "reference"
    (root / "newer.md").write_text("---\ntitle: x\n---\n", encoding="utf-8")
    ref = cr.parse_reference(root / "example.md", text2)
    assert cr.findings(ref, repo_root=tmp_path, root=root) == []


def test_dangling_source_id(tmp_path: Path) -> None:
    problems = _findings(tmp_path, GOOD.replace("[source: spec]", "[source: nope]"))
    assert problems == [
        f"{tmp_path / 'docs/design/reference/example.md'}: `[source: nope]` names no declared source"
    ]


def test_sources_entries_are_validated(tmp_path: Path) -> None:
    text = GOOD.replace("    url: https://example.invalid/spec\n", "").replace(
        "    accessed: 2026-09-06\n", ""
    )
    problems = _findings(tmp_path, text)
    assert any("has no `url`" in p for p in problems), problems
    assert any("needs an ISO `accessed` date" in p for p in problems), problems
    problems = _findings(
        tmp_path,
        GOOD.replace(
            "sources:\n  - id: spec",
            "sources:\n  - id: spec\n  - id: spec\n    url: u\n    accessed: 2026-09-06",
        ),
    )
    assert any("duplicates id 'spec'" in p for p in problems), problems


def test_dangling_pin_forms(tmp_path: Path) -> None:
    for bad, fragment in (
        ("tests/test_example.py::test_missing", "is not defined in"),
        ("tests/test_nope.py::test_claim", "does not exist"),
        ("not-a-pin", "is not of the form"),
    ):
        problems = _findings(
            tmp_path, GOOD.replace("tests/test_example.py::test_claim", bad)
        )
        assert any(fragment in p for p in problems), (bad, problems)


def test_pins_accept_class_methods_and_lists(tmp_path: Path) -> None:
    repo, root = _repo(tmp_path)
    (repo / "tests" / "test_example.py").write_text(
        "class TestX:\n    async def test_m(self) -> None:\n        pass\n\n\ndef test_claim() -> None:\n    pass\n",
        encoding="utf-8",
    )
    text = GOOD.replace(
        "[pins: tests/test_example.py::test_claim]",
        "[pins: tests/test_example.py::test_claim, tests/test_example.py::TestX::test_m]",
    )
    ref = cr.parse_reference(root / "example.md", text)
    assert cr.findings(ref, repo_root=repo, root=root) == []


def test_a_reference_with_only_memory_is_rejected(tmp_path: Path) -> None:
    text = GOOD.replace("[source: spec] ", "").replace(
        "[observed: ran `example --dump`]", "[unverified]"
    )
    problems = _findings(tmp_path, text)
    assert any("this is memory, not a reference" in p for p in problems), problems


def test_expiry_is_reported_not_failed(tmp_path: Path) -> None:
    _, root = _repo(tmp_path)
    ref = cr.parse_reference(root / "example.md", GOOD)
    assert cr.expiry(ref, TODAY) is None
    assert cr.expiry(ref, dt.date(2027, 3, 7)) == "`review_by` 2027-03-06 has passed"
    expired = cr.parse_reference(
        root / "example.md", GOOD.replace("status: current", "status: expired")
    )
    assert cr.expiry(expired, TODAY) == "marked `status: expired`"
    assert "RE-RESEARCH" in cr.summary_line(expired, TODAY)
    assert "RE-RESEARCH" not in cr.summary_line(ref, TODAY)


def test_discover_skips_indexes_and_missing_root(tmp_path: Path) -> None:
    assert cr.discover(tmp_path / "absent") == []
    _, root = _repo(tmp_path)
    (root / "README.md").write_text("index\n", encoding="utf-8")
    (root / "index.md").write_text("index\n", encoding="utf-8")
    assert [p.name for p in cr.discover(root)] == ["example.md"]


def test_cli_exit_codes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, root = _repo(tmp_path)
    monkeypatch.chdir(repo)
    assert cr.main([]) == 0
    assert "example.md: status=current" in capsys.readouterr().out
    (root / "bad.md").write_text(
        GOOD.replace("[source: spec]", "[source: nope]"), encoding="utf-8"
    )
    assert cr.main(["--quiet"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "names no declared source" in captured.err
    (root / "bad.md").unlink()
    (root / "old.md").write_text(
        GOOD.replace("review_by: 2027-03-06", "review_by: 2020-01-01"), encoding="utf-8"
    )
    assert cr.main([]) == 0
    assert cr.main(["--strict"]) == 1
    (root / "broken.md").write_text("no frontmatter\n", encoding="utf-8")
    assert cr.main([]) == 1
    assert "no YAML frontmatter" in capsys.readouterr().err
