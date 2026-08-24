#!/usr/bin/env python3
"""Promote reviewed staging notes into canonical release-note pages."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

VERSION_RE = re.compile(
    r"^v?(?P<major>0|[1-9][0-9]*)\."
    r"(?P<minor>0|[1-9][0-9]*)\."
    r"(?P<patch>0|[1-9][0-9]*)"
    r"(?:-rc\.(?P<rc>[1-9][0-9]*))?$"
)
WATERMARK_RE = re.compile(r"<!-- notes-range-end: ([0-9a-f]{40}) -->")


class PromotionError(ValueError):
    """Release notes cannot be promoted without human correction."""


@dataclass(frozen=True)
class Target:
    version: str
    tag: str
    minor: str
    page: Path


@dataclass(frozen=True)
class PromotionPlan:
    root: Path
    writes: dict[Path, str]
    deletes: tuple[Path, ...]
    stage_paths: tuple[Path, ...]


def normalize_target(version: str) -> Target:
    match = VERSION_RE.fullmatch(version)
    if match is None:
        raise PromotionError(
            f"invalid release version {version!r}; expected X.Y.Z or X.Y.Z-rc.N"
        )
    stable = f"{match['major']}.{match['minor']}.{match['patch']}"
    minor = f"{match['major']}.{match['minor']}"
    return Target(stable, f"v{stable}", minor, Path(f"docs/releases/{minor}.md"))


def require_once(text: str, token: str, label: str) -> None:
    count = text.count(token)
    if count != 1:
        raise PromotionError(f"{label} must occur exactly once; found {count}")


def validate_next(text: str) -> str:
    lines = text.splitlines()
    if not lines or lines[0] != "# Next release":
        raise PromotionError("next.md must start with '# Next release'")
    if len(WATERMARK_RE.findall(text)) != 1:
        raise PromotionError("next.md must contain exactly one 40-hex watermark")
    start = "<!-- RELEASE-SUMMARY NEXT START -->"
    end = "<!-- RELEASE-SUMMARY NEXT END -->"
    require_once(text, start, "NEXT summary start")
    require_once(text, end, "NEXT summary end")
    summary = text.split(start, 1)[1].split(end, 1)[0].strip()
    if not summary:
        raise PromotionError("NEXT summary must not be empty")
    return text


def _target_summary_count(text: str, tag: str) -> int:
    start = f"<!-- RELEASE-SUMMARY {tag} START -->"
    end = f"<!-- RELEASE-SUMMARY {tag} END -->"
    starts = text.count(start)
    ends = text.count(end)
    if starts != ends or starts > 1:
        raise PromotionError(
            "target summary must contain zero or one complete START/END pair"
        )
    return starts


def plan_promotion(root: Path, version: str) -> PromotionPlan:
    root = root.resolve()
    target = normalize_target(version)
    page_path = root / target.page
    next_relative = Path("docs/releases/next.md")
    next_path = root / next_relative
    index_relative = Path("docs/releases/index.md")
    index_path = root / index_relative

    page_text = page_path.read_text(encoding="utf-8") if page_path.is_file() else ""
    target_present = _target_summary_count(page_text, target.tag) == 1
    next_present = next_path.is_file()

    if target_present and next_present:
        raise PromotionError("ambiguous release notes: target and next.md both exist")
    if target_present:
        return PromotionPlan(root, {}, (), ())
    if not next_present:
        raise PromotionError("no reviewed release notes found for target")

    next_text = validate_next(next_path.read_text(encoding="utf-8"))
    if page_path.is_file():
        return PromotionPlan(
            root,
            {page_path: next_text},
            (next_path,),
            (target.page, next_relative),
        )

    if not index_path.is_file():
        raise PromotionError(
            "docs/releases/index.md is required for a new release series"
        )
    index_text = index_path.read_text(encoding="utf-8")
    require_once(index_text, "<!-- RELEASE-PAGES-START:", "release pages start")
    require_once(index_text, "<!-- RELEASE-PAGES-END -->", "release pages end")
    return PromotionPlan(
        root,
        {page_path: next_text, index_path: index_text},
        (next_path,),
        (target.page, index_relative, next_relative),
    )
