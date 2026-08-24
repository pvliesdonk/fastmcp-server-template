from __future__ import annotations

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
