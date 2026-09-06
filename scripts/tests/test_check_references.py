"""``scripts/check_references.py`` enforces the reference contract (#593, #595, #597).

A reference under ``docs/design/reference/`` is an OKF v0.2 concept: dated,
sourced, and pinned; the ``researching-references`` skill says why.  These
tests exercise the checker on synthetic pages so the shipped
``tests/test_reference_docs.py`` can trust it.
"""

from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_references as cr

TODAY = dt.date(2026, 9, 6)

GOOD = """\
---
type: Reference
title: Example subject
description: How example behaves
subject_version: "1.x"
valid_for: "Example 1.x"
generated:
  by: process:researching-references
  at: 2026-09-06
stale_after: 2027-03-06
status: stable
sources:
  - id: spec
    title: Example spec
    resource: https://example.invalid/spec
    accessed: 2026-09-06
---

# Example subject

- A claim. [source: spec] [pins: tests/test_example.py::test_claim]
- Another. [observed: ran `example --dump`]
- A guess. [unverified]
"""

INDEX = '---\nokf_version: "0.2"\ntitle: References\n---\n\n# References\n\n- [Example](/example.md)\n'


def _repo(
    tmp_path: Path, text: str = GOOD, name: str = "example.md"
) -> tuple[Path, Path]:
    root = tmp_path / "docs" / "design" / "reference"
    root.mkdir(parents=True, exist_ok=True)
    (root / name).write_text(text, encoding="utf-8")
    (root / "index.md").write_text(INDEX, encoding="utf-8")
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
    _, root = _repo(tmp_path)
    assert cr.bundle_findings(root) == []


def test_marker_counts_and_derived_fields(tmp_path: Path) -> None:
    _, root = _repo(tmp_path)
    ref = cr.parse_reference(root / "example.md", GOOD)
    assert (
        ref.count("source"),
        ref.count("observed"),
        ref.count("unverified"),
        ref.count("pins"),
    ) == (1, 1, 1, 1)
    assert ref.status == "stable"
    assert ref.trust_tier == "unverified"
    machine = cr.parse_reference(
        root / "example.md",
        GOOD.replace(
            "status: stable",
            "verified:\n  - by: process:refute-pass\n    at: 2026-09-06",
        ),
    )
    assert machine.trust_tier == "machine-confirmed"
    human = cr.parse_reference(
        root / "example.md",
        GOOD.replace(
            "status: stable",
            "verified:\n  by: human:pvliesdonk\n  at: 2026-09-07T10:00:00",
        ),
    )
    assert human.trust_tier == "human-reviewed"
    absent = cr.parse_reference(
        root / "example.md", GOOD.replace("status: stable\n", "")
    )
    assert absent.status == "stable"


def test_missing_frontmatter_is_a_parse_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no YAML frontmatter"):
        cr.parse_reference(tmp_path / "x.md", "# no frontmatter\n")


@pytest.mark.parametrize("key", cr.REQUIRED_KEYS)
def test_every_required_key_is_enforced(tmp_path: Path, key: str) -> None:
    text = re.sub(rf"^{key}:.*\n(?:  .*\n)*", "", GOOD, flags=re.MULTILINE)
    problems = _findings(tmp_path, text)
    assert any(f"missing frontmatter key `{key}`" in p for p in problems), (
        key,
        problems,
    )


def test_null_required_keys_are_missing(tmp_path: Path) -> None:
    text = GOOD
    for key in ("title", "description", "subject_version", "valid_for"):
        text = re.sub(rf"^{key}:.*$", f"{key}:", text, flags=re.MULTILINE)
    text = re.sub(r"^sources:\n(?:  .*\n)+", "sources:\n", text, flags=re.MULTILINE)
    text = re.sub(r"^generated:\n(?:  .*\n)+", "generated:\n", text, flags=re.MULTILINE)
    problems = _findings(tmp_path, text)
    for key in (
        "title",
        "description",
        "subject_version",
        "valid_for",
        "sources",
        "generated",
    ):
        assert any(f"missing frontmatter key `{key}`" in p for p in problems), (
            key,
            problems,
        )
    assert any("`sources` must be a non-empty list" in p for p in problems), problems


def test_type_must_be_reference(tmp_path: Path) -> None:
    problems = _findings(tmp_path, GOOD.replace("type: Reference", "type: Playbook"))
    assert any("`type` must be 'Reference'" in p for p in problems), problems


def test_dates_must_be_iso(tmp_path: Path) -> None:
    problems = _findings(
        tmp_path, GOOD.replace("stale_after: 2027-03-06", "stale_after: next spring")
    )
    assert any("`stale_after` must be an ISO date" in p for p in problems), problems
    problems = _findings(tmp_path, GOOD.replace("  at: 2026-09-06", "  at: yesterday"))
    assert any("`generated.at` must be an ISO date" in p for p in problems), problems


def test_actor_convention(tmp_path: Path) -> None:
    for bad in ("Peter", '"human: pvliesdonk"', "claude code"):
        problems = _findings(
            tmp_path,
            GOOD.replace("  by: process:researching-references", f"  by: {bad}"),
        )
        assert any(
            "`generated.by` must follow the OKF actor convention" in p for p in problems
        ), (bad, problems)
    for good in ("human:pvliesdonk", "process:nightly", "reference_agent/1.2"):
        assert (
            _findings(
                tmp_path,
                GOOD.replace("  by: process:researching-references", f"  by: {good}"),
            )
            == []
        )
    problems = _findings(
        tmp_path,
        GOOD.replace("status: stable", "verified:\n  - by: nobody\n    at: 2026-09-06"),
    )
    assert any("`verified[0].by` must follow" in p for p in problems), problems
    problems = _findings(tmp_path, GOOD.replace("status: stable", "verified: yes"))
    assert any("`verified` must be a" in p for p in problems), problems


def test_status_is_okf_vocabulary(tmp_path: Path) -> None:
    problems = _findings(tmp_path, GOOD.replace("status: stable", "status: current"))
    assert any("`status` must be one of" in p for p in problems), problems
    assert _findings(tmp_path, GOOD.replace("status: stable", "status: draft")) == []


def test_superseded_by_needs_deprecated_and_an_existing_file_under_root(
    tmp_path: Path,
) -> None:
    repo, root = _repo(tmp_path)
    text = GOOD.replace("status: stable", "status: deprecated\nsuperseded_by: newer.md")
    problems = _findings(tmp_path, text)
    assert any("does not exist under" in p for p in problems), problems
    (root / "newer.md").write_text(GOOD, encoding="utf-8")
    ref = cr.parse_reference(root / "example.md", text)
    assert cr.findings(ref, repo_root=repo, root=root) == []
    text2 = GOOD.replace("status: stable", "status: stable\nsuperseded_by: newer.md")
    ref = cr.parse_reference(root / "example.md", text2)
    problems = cr.findings(ref, repo_root=repo, root=root)
    assert any("only meaningful with `status: deprecated`" in p for p in problems), (
        problems
    )
    (repo / "docs" / "design" / "outside.md").write_text(GOOD, encoding="utf-8")
    for escape in ("../outside.md", str(repo / "docs" / "design" / "outside.md")):
        text3 = GOOD.replace(
            "status: stable", f"status: deprecated\nsuperseded_by: {escape}"
        )
        ref = cr.parse_reference(root / "example.md", text3)
        problems = cr.findings(ref, repo_root=repo, root=root)
        assert any("is outside" in p for p in problems), (escape, problems)


def test_dangling_source_id(tmp_path: Path) -> None:
    problems = _findings(tmp_path, GOOD.replace("[source: spec]", "[source: nope]"))
    assert problems == [
        f"{tmp_path / 'docs/design/reference/example.md'}: `[source: nope]` names no declared source"
    ]


def test_sources_entries_are_validated(tmp_path: Path) -> None:
    text = GOOD.replace("    resource: https://example.invalid/spec\n", "").replace(
        "    accessed: 2026-09-06\n", ""
    )
    problems = _findings(tmp_path, text)
    assert any("has no `resource`" in p for p in problems), problems
    assert any("needs an ISO `accessed` date" in p for p in problems), problems
    problems = _findings(
        tmp_path,
        GOOD.replace(
            "sources:\n  - id: spec",
            "sources:\n  - id: spec\n  - id: spec\n    resource: u\n    accessed: 2026-09-06",
        ),
    )
    assert any("duplicates id 'spec'" in p for p in problems), problems


def test_dangling_pin_forms(tmp_path: Path) -> None:
    for bad, fragment in (
        ("tests/test_example.py::test_missing", "is not defined in"),
        ("tests/test_nope.py::test_claim", "does not exist"),
        ("not-a-pin", "is not of the form"),
        ("scripts/check_references.py::_defined", "is not of the form"),
        ("tests/test_example.py::helper", "is not of the form"),
        ("tests/test_example.py::Helper::test_claim", "is not of the form"),
        ("src/pkg/tests/test_x.py::test_claim", "is not of the form"),
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


def test_class_qualified_pin_must_match_its_class(tmp_path: Path) -> None:
    repo, root = _repo(tmp_path)
    (repo / "tests" / "test_example.py").write_text(
        "class TestX:\n    def test_m(self) -> None:\n        pass\n\n\ndef test_claim() -> None:\n    pass\n",
        encoding="utf-8",
    )
    for bad in (
        "tests/test_example.py::TestY::test_m",
        "tests/test_example.py::test_m",
    ):
        text = GOOD.replace("tests/test_example.py::test_claim", bad)
        ref = cr.parse_reference(root / "example.md", text)
        problems = cr.findings(ref, repo_root=repo, root=root)
        assert any("is not defined in" in p for p in problems), (bad, problems)


def test_markers_inside_html_comments_are_ignored(tmp_path: Path) -> None:
    text = GOOD.replace(
        "# Example subject\n",
        "# Example subject\n\n<!-- guidance: [source: nope] [pins: tests/none.py::test_x]\nspanning lines [unverified] -->\n",
    )
    assert _findings(tmp_path, text) == []
    _, root = _repo(tmp_path)
    assert cr.parse_reference(root / "example.md", text).count("unverified") == 1


def test_observed_marker_needs_its_evidence(tmp_path: Path) -> None:
    text = GOOD.replace("[observed: ran `example --dump`]", "[observed]")
    problems = _findings(tmp_path, text)
    assert any("`[observed]` marker without its evidence" in p for p in problems), (
        problems
    )


def test_a_reference_with_only_memory_is_rejected(tmp_path: Path) -> None:
    text = GOOD.replace("[source: spec] ", "").replace(
        "[observed: ran `example --dump`]", "[unverified]"
    )
    problems = _findings(tmp_path, text)
    assert any("this is memory, not a reference" in p for p in problems), problems


def test_expiry_follows_okf_staleness(tmp_path: Path) -> None:
    _, root = _repo(tmp_path)
    ref = cr.parse_reference(root / "example.md", GOOD)
    assert cr.expiry(ref, TODAY) is None
    assert cr.expiry(ref, dt.date(2027, 3, 5)) is None
    assert (
        cr.expiry(ref, dt.date(2027, 3, 6)) == "stale since 2027-03-06 (`stale_after`)"
    )
    deprecated = cr.parse_reference(
        root / "example.md", GOOD.replace("status: stable", "status: deprecated")
    )
    assert cr.expiry(deprecated, dt.date(2030, 1, 1)) is None
    assert "RE-RESEARCH" in cr.summary_line(ref, dt.date(2027, 3, 6))
    assert "RE-RESEARCH" not in cr.summary_line(ref, TODAY)
    assert "trust=unverified" in cr.summary_line(ref, TODAY)


def test_bundle_marker_and_log_headings(tmp_path: Path) -> None:
    _, root = _repo(tmp_path)
    (root / "index.md").unlink()
    assert any("missing; an OKF bundle root" in p for p in cr.bundle_findings(root))
    (root / "index.md").write_text("---\ntitle: x\n---\n", encoding="utf-8")
    assert any("must declare `okf_version" in p for p in cr.bundle_findings(root))
    (root / "index.md").write_text(INDEX, encoding="utf-8")
    (root / "log.md").write_text(
        "# Log\n\n## 2026-09-06\n\n- added\n\n## last week\n\n- x\n", encoding="utf-8"
    )
    problems = cr.bundle_findings(root)
    assert problems == [
        f"{root / 'log.md'}: heading `## last week` is not a `## YYYY-MM-DD` date"
    ]
    (root / "example.md").unlink()
    assert cr.bundle_findings(root) == []  # no pages, no bundle expected


def test_discover_skips_reserved_files_and_missing_root(tmp_path: Path) -> None:
    assert cr.discover(tmp_path / "absent") == []
    _, root = _repo(tmp_path)
    (root / "README.md").write_text("index\n", encoding="utf-8")
    (root / "log.md").write_text("# Log\n", encoding="utf-8")
    assert [p.name for p in cr.discover(root)] == ["example.md"]


def test_cli_exit_codes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, root = _repo(tmp_path)
    monkeypatch.chdir(repo)
    assert cr.main([]) == 0
    assert "example.md: status=stable" in capsys.readouterr().out
    (root / "bad.md").write_text(
        GOOD.replace("[source: spec]", "[source: nope]"), encoding="utf-8"
    )
    assert cr.main(["--quiet"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "names no declared source" in captured.err
    (root / "bad.md").unlink()
    (root / "old.md").write_text(
        GOOD.replace("stale_after: 2027-03-06", "stale_after: 2020-01-01"),
        encoding="utf-8",
    )
    assert cr.main([]) == 0
    assert cr.main(["--strict"]) == 1
    (root / "broken.md").write_text("no frontmatter\n", encoding="utf-8")
    assert cr.main([]) == 1
    assert "no YAML frontmatter" in capsys.readouterr().err
    (root / "index.md").unlink()
    assert cr.main(["--quiet"]) == 1
    assert "an OKF bundle root" in capsys.readouterr().err
