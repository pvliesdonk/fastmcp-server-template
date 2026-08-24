from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from scripts.promote_release_notes import (
    PromotionError,
    normalize_target,
    plan_promotion,
)

NEXT = """# Next release

<!-- notes-range-end: 0123456789abcdef0123456789abcdef01234567 -->

<!-- RELEASE-SUMMARY NEXT START -->
Operators can now rotate credentials without restarting the server.
<!-- RELEASE-SUMMARY NEXT END -->

## Credential rotation

The server reloads credentials after the configured interval ([#42](https://github.com/example/project/issues/42)).
"""

INDEX = """# Release Notes

<!-- RELEASE-PAGES-START: newest series first; one list entry per page.
     The first real entry replaces the placeholder line below. -->
No release pages yet. The first entry appears with the first stable
release cut after this project adopted release-notes pages.
<!-- RELEASE-PAGES-END -->
"""

INDEX_WITH_EXISTING = """# Release Notes

<!-- RELEASE-PAGES-START: newest series first; one list entry per page.
     The first real entry replaces the placeholder line below. -->
- [2.3](2.3.md)
<!-- RELEASE-PAGES-END -->
"""


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def canonical(tag: str = "v2.4.0") -> str:
    return f"""# 2.4

<!-- notes-range-end: 1111111111111111111111111111111111111111 -->

<!-- RELEASE-SUMMARY {tag} START -->
Existing reviewed summary.
<!-- RELEASE-SUMMARY {tag} END -->

## Existing theme

Existing evidence.

<!-- PATCH-RELEASES-START -->
<!-- PATCH-RELEASES-END -->
"""


def with_patch(tag: str) -> str:
    section = f"""## {tag}

<!-- RELEASE-SUMMARY {tag} START -->
Earlier patch summary.
<!-- RELEASE-SUMMARY {tag} END -->

### Earlier patch theme

Earlier patch evidence.

"""
    return canonical().replace(
        "<!-- PATCH-RELEASES-END -->", section + "<!-- PATCH-RELEASES-END -->"
    )


def snapshot(root: Path) -> dict[Path, bytes]:
    return {
        path.relative_to(root): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


@pytest.mark.parametrize(
    ("version", "tag", "minor"),
    [
        ("2.4.0", "v2.4.0", "2.4"),
        ("v2.4.0", "v2.4.0", "2.4"),
        ("2.4.0-rc.3", "v2.4.0", "2.4"),
    ],
)
def test_normalize_target(version: str, tag: str, minor: str) -> None:
    target = normalize_target(version)
    assert (target.tag, target.minor, target.page) == (
        tag,
        minor,
        Path("docs/releases/2.4.md"),
    )


def test_target_present_without_next_is_a_noop(tmp_path: Path) -> None:
    write(tmp_path / "docs/releases/2.4.md", canonical())
    plan = plan_promotion(tmp_path, "2.4.0-rc.2")
    assert plan.writes == {}
    assert plan.deletes == ()
    assert plan.stage_paths == ()


def test_missing_target_with_next_plans_promotion(tmp_path: Path) -> None:
    write(tmp_path / "docs/releases/next.md", NEXT)
    write(tmp_path / "docs/releases/index.md", INDEX)
    plan = plan_promotion(tmp_path, "2.4.0-rc.1")
    assert tmp_path / "docs/releases/2.4.md" in plan.writes
    assert plan.deletes == (tmp_path / "docs/releases/next.md",)


def test_missing_target_and_next_refuses(tmp_path: Path) -> None:
    with pytest.raises(PromotionError, match="no reviewed release notes"):
        plan_promotion(tmp_path, "2.4.0")


def test_target_and_next_together_refuse(tmp_path: Path) -> None:
    write(tmp_path / "docs/releases/2.4.md", canonical())
    write(tmp_path / "docs/releases/next.md", NEXT)
    with pytest.raises(PromotionError, match="ambiguous"):
        plan_promotion(tmp_path, "2.4.0-rc.2")


@pytest.mark.parametrize(
    "version",
    ["", "2.4", "02.4.0", "2.04.0", "2.4.00", "2.4.0-rc.0", "2.4.0-beta.1"],
)
def test_invalid_release_version_refuses(version: str) -> None:
    with pytest.raises(PromotionError, match="invalid release version"):
        normalize_target(version)


def test_new_minor_page_promotion(tmp_path: Path) -> None:
    write(tmp_path / "docs/releases/next.md", NEXT)
    write(tmp_path / "docs/releases/index.md", INDEX)

    plan = plan_promotion(tmp_path, "2.4.0-rc.1")

    assert (
        plan.writes[tmp_path / "docs/releases/2.4.md"]
        == """# 2.4

<!-- notes-range-end: 0123456789abcdef0123456789abcdef01234567 -->

<!-- RELEASE-SUMMARY v2.4.0 START -->
Operators can now rotate credentials without restarting the server.
<!-- RELEASE-SUMMARY v2.4.0 END -->

## Credential rotation

The server reloads credentials after the configured interval ([#42](https://github.com/example/project/issues/42)).

<!-- PATCH-RELEASES-START -->
<!-- PATCH-RELEASES-END -->
"""
    )
    assert (
        plan.writes[tmp_path / "docs/releases/index.md"]
        == """# Release Notes

<!-- RELEASE-PAGES-START: newest series first; one list entry per page.
     The first real entry replaces the placeholder line below. -->
- [2.4](2.4.md)
<!-- RELEASE-PAGES-END -->
"""
    )


def test_new_minor_index_entry_precedes_existing_series(tmp_path: Path) -> None:
    write(tmp_path / "docs/releases/next.md", NEXT)
    write(tmp_path / "docs/releases/index.md", INDEX_WITH_EXISTING)

    index = plan_promotion(tmp_path, "2.4.0").writes[
        tmp_path / "docs/releases/index.md"
    ]

    assert index.index("-->\n- [2.4](2.4.md)") < index.index("- [2.3](2.3.md)")


def test_existing_minor_index_link_refuses(tmp_path: Path) -> None:
    write(tmp_path / "docs/releases/next.md", NEXT)
    write(
        tmp_path / "docs/releases/index.md",
        INDEX_WITH_EXISTING.replace("2.3", "2.4"),
    )
    before = snapshot(tmp_path)

    with pytest.raises(PromotionError, match="already links"):
        plan_promotion(tmp_path, "2.4.0")

    assert snapshot(tmp_path) == before


def test_duplicate_target_summary_refuses(tmp_path: Path) -> None:
    write(tmp_path / "docs/releases/2.4.md", canonical() + canonical())
    before = snapshot(tmp_path)

    with pytest.raises(PromotionError, match="target summary"):
        plan_promotion(tmp_path, "2.4.0")

    assert snapshot(tmp_path) == before


def test_patch_section_is_inserted_before_patch_end(tmp_path: Path) -> None:
    write(tmp_path / "docs/releases/2.4.md", canonical("v2.4.0"))
    write(tmp_path / "docs/releases/next.md", NEXT)

    page = plan_promotion(tmp_path, "2.4.1-rc.1").writes[
        tmp_path / "docs/releases/2.4.md"
    ]

    assert "## v2.4.1\n" in page
    assert "### Credential rotation\n" in page
    assert page.index("## v2.4.1") < page.index("<!-- PATCH-RELEASES-END -->")
    assert "notes-range-end: 0123456789abcdef0123456789abcdef01234567" in page
    assert "notes-range-end: 1111111111111111111111111111111111111111" not in page


@pytest.mark.parametrize("fence", ["```", "~~~"])
def test_heading_conversion_ignores_fenced_code(tmp_path: Path, fence: str) -> None:
    staged = NEXT + f"\n{fence}markdown\n## literal example\n{fence}\n"
    write(tmp_path / "docs/releases/2.4.md", canonical("v2.4.0"))
    write(tmp_path / "docs/releases/next.md", staged)

    page = plan_promotion(tmp_path, "2.4.1").writes[tmp_path / "docs/releases/2.4.md"]

    assert "### Credential rotation" in page
    assert "## literal example" in page
    assert "### literal example" not in page


def test_patch_sections_remain_ascending_and_undated(tmp_path: Path) -> None:
    write(tmp_path / "docs/releases/2.4.md", with_patch("v2.4.1"))
    write(tmp_path / "docs/releases/next.md", NEXT)

    page = plan_promotion(tmp_path, "2.4.2").writes[tmp_path / "docs/releases/2.4.md"]

    assert page.index("## v2.4.1") < page.index("## v2.4.2")
    assert "## v2.4.2 (" not in page


def test_out_of_order_patch_refuses(tmp_path: Path) -> None:
    write(tmp_path / "docs/releases/2.4.md", with_patch("v2.4.2"))
    write(tmp_path / "docs/releases/next.md", NEXT)
    before = snapshot(tmp_path)

    with pytest.raises(PromotionError, match="ascending"):
        plan_promotion(tmp_path, "2.4.1")

    assert snapshot(tmp_path) == before


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda text: text.replace("# Next release", "# Upcoming release", 1), "start"),
        (lambda text: text + "\n# Next release\n", "exactly once"),
        (
            lambda text: text.replace(
                "<!-- notes-range-end: 0123456789abcdef0123456789abcdef01234567 -->",
                "",
                1,
            ),
            "watermark",
        ),
        (
            lambda text: (
                text
                + "\n<!-- notes-range-end: 2222222222222222222222222222222222222222 -->\n"
            ),
            "watermark",
        ),
        (
            lambda text: text.replace("<!-- RELEASE-SUMMARY NEXT START -->", "", 1),
            "summary start",
        ),
        (
            lambda text: text + "\n<!-- RELEASE-SUMMARY NEXT START -->\n",
            "summary start",
        ),
        (
            lambda text: text.replace("<!-- RELEASE-SUMMARY NEXT END -->", "", 1),
            "summary end",
        ),
        (lambda text: text + "\n<!-- RELEASE-SUMMARY NEXT END -->\n", "summary end"),
        (
            lambda text: text.replace(
                "Operators can now rotate credentials without restarting the server.",
                "",
            ),
            "must not be empty",
        ),
    ],
)
def test_malformed_next_refuses_without_changes(
    tmp_path: Path,
    mutate: Callable[[str], str],
    message: str,
) -> None:
    write(tmp_path / "docs/releases/2.4.md", canonical())
    write(tmp_path / "docs/releases/next.md", mutate(NEXT))
    before = snapshot(tmp_path)

    with pytest.raises(PromotionError, match=message):
        plan_promotion(tmp_path, "2.4.1")

    assert snapshot(tmp_path) == before


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda text: text.replace("# 2.4", "# 2.4 release", 1), "canonical page"),
        (lambda text: text + "\n# 2.4\n", "canonical page"),
        (
            lambda text: text.replace(
                "<!-- notes-range-end: 1111111111111111111111111111111111111111 -->",
                "",
                1,
            ),
            "watermark",
        ),
        (
            lambda text: (
                text
                + "\n<!-- notes-range-end: 2222222222222222222222222222222222222222 -->\n"
            ),
            "watermark",
        ),
        (
            lambda text: text.replace("<!-- PATCH-RELEASES-START -->", "", 1),
            "patch start",
        ),
        (lambda text: text + "\n<!-- PATCH-RELEASES-START -->\n", "patch start"),
        (lambda text: text.replace("<!-- PATCH-RELEASES-END -->", "", 1), "patch end"),
        (lambda text: text + "\n<!-- PATCH-RELEASES-END -->\n", "patch end"),
    ],
)
def test_malformed_canonical_page_refuses_without_changes(
    tmp_path: Path,
    mutate: Callable[[str], str],
    message: str,
) -> None:
    write(tmp_path / "docs/releases/2.4.md", mutate(canonical()))
    write(tmp_path / "docs/releases/next.md", NEXT)
    before = snapshot(tmp_path)

    with pytest.raises(PromotionError, match=message):
        plan_promotion(tmp_path, "2.4.1")

    assert snapshot(tmp_path) == before
