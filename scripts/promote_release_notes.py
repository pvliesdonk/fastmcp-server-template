#!/usr/bin/env python3
"""Promote reviewed staging notes into canonical release-note pages."""

from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path

VERSION_RE = re.compile(
    r"^v?(?P<major>0|[1-9][0-9]*)\."
    r"(?P<minor>0|[1-9][0-9]*)\."
    r"(?P<patch>0|[1-9][0-9]*)"
    r"(?:-rc\.(?P<rc>[1-9][0-9]*))?$"
)
WATERMARK_RE = re.compile(r"<!-- notes-range-end: ([0-9a-f]{40}) -->")
INDEX_START_RE = re.compile(r"<!-- RELEASE-PAGES-START:[\s\S]*?-->")
PATCH_HEADING_RE = re.compile(r"^## v([0-9]+)\.([0-9]+)\.([0-9]+)$", re.MULTILINE)


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
    title_count = sum(line == "# Next release" for line in lines)
    if title_count != 1:
        raise PromotionError(
            f"next.md title must occur exactly once; found {title_count}"
        )
    if len(WATERMARK_RE.findall(text)) != 1:
        raise PromotionError("next.md must contain exactly one 40-hex watermark")
    start = "<!-- RELEASE-SUMMARY NEXT START -->"
    end = "<!-- RELEASE-SUMMARY NEXT END -->"
    require_once(text, start, "NEXT summary start")
    require_once(text, end, "NEXT summary end")
    if text.index(start) > text.index(end):
        raise PromotionError("NEXT summary START must precede END")
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


def new_page_text(next_text: str, target: Target) -> str:
    body = next_text.replace("# Next release", f"# {target.minor}", 1)
    body = body.replace("RELEASE-SUMMARY NEXT", f"RELEASE-SUMMARY {target.tag}")
    return (
        body.rstrip()
        + "\n\n<!-- PATCH-RELEASES-START -->\n<!-- PATCH-RELEASES-END -->\n"
    )


def _new_index_text(index_text: str, target: Target) -> str:
    starts = list(INDEX_START_RE.finditer(index_text))
    if len(starts) != 1:
        raise PromotionError(
            f"release pages start must occur exactly once; found {len(starts)}"
        )
    end = "<!-- RELEASE-PAGES-END -->"
    require_once(index_text, end, "release pages end")
    if starts[0].end() > index_text.index(end):
        raise PromotionError("release pages START must precede END")
    if f"({target.minor}.md)" in index_text:
        raise PromotionError(f"release index already links to {target.minor}.md")

    placeholder = (
        "No release pages yet. The first entry appears with the first stable\n"
        "release cut after this project adopted release-notes pages.\n"
    )
    if index_text.count(placeholder) > 1:
        raise PromotionError("release pages placeholder must occur at most once")
    without_placeholder = index_text.replace(placeholder, "", 1)
    start = INDEX_START_RE.search(without_placeholder)
    if start is None:
        raise PromotionError("release pages START comment is malformed")
    suffix = without_placeholder[start.end() :]
    suffix = suffix.removeprefix("\n")
    entry = f"- [{target.minor}]({target.minor}.md)\n"
    return without_placeholder[: start.end()] + "\n" + entry + suffix


def promote_new_page(
    root: Path,
    target: Target,
    next_text: str,
    index_text: str,
) -> PromotionPlan:
    validate_next(next_text)
    page_text = new_page_text(next_text, target)
    promoted_index = _new_index_text(index_text, target)
    page_path = root / target.page
    index_relative = Path("docs/releases/index.md")
    next_relative = Path("docs/releases/next.md")
    return PromotionPlan(
        root,
        {page_path: page_text, root / index_relative: promoted_index},
        (root / next_relative,),
        (target.page, index_relative, next_relative),
    )


def shift_headings(text: str, levels: int = 1) -> str:
    shifted: list[str] = []
    fence_character = ""
    fence_length = 0
    for line in text.splitlines(keepends=True):
        stripped = line.rstrip("\r\n")
        if fence_character:
            shifted.append(line)
            if re.fullmatch(
                rf"{re.escape(fence_character)}{{{fence_length},}}[ \t]*", stripped
            ):
                fence_character = ""
                fence_length = 0
            continue

        fence = re.match(r"^(`{3,}|~{3,})", stripped)
        if fence:
            marker = fence.group(1)
            fence_character = marker[0]
            fence_length = len(marker)
            shifted.append(line)
            continue

        if re.match(r"^#{1,6}[ \t]", line):
            shifted.append("#" * levels + line)
        else:
            shifted.append(line)
    return "".join(shifted)


def _validate_canonical_page(
    page_text: str, target: Target
) -> list[tuple[int, int, int]]:
    lines = page_text.splitlines()
    title = f"# {target.minor}"
    title_count = sum(line == title for line in lines)
    if not lines or lines[0] != title or title_count != 1:
        raise PromotionError(
            f"canonical page title must be {title!r} exactly once; found {title_count}"
        )
    if len(WATERMARK_RE.findall(page_text)) != 1:
        raise PromotionError("canonical page must contain exactly one 40-hex watermark")

    start = "<!-- PATCH-RELEASES-START -->"
    end = "<!-- PATCH-RELEASES-END -->"
    require_once(page_text, start, "patch start sentinel")
    require_once(page_text, end, "patch end sentinel")
    start_at = page_text.index(start) + len(start)
    end_at = page_text.index(end)
    if start_at > end_at:
        raise PromotionError("patch START sentinel must precede END sentinel")

    patches = [
        (int(match[1]), int(match[2]), int(match[3]))
        for match in PATCH_HEADING_RE.finditer(page_text[start_at:end_at])
    ]
    if any(left >= right for left, right in pairwise(patches)):
        raise PromotionError(
            "existing patch sections must be in ascending version order"
        )
    target_minor = tuple(int(part) for part in target.minor.split("."))
    if any(patch[:2] != target_minor for patch in patches):
        raise PromotionError("patch headings must belong to the canonical minor series")
    return patches


def promote_patch_page(
    root: Path,
    target: Target,
    next_text: str,
    page_text: str,
) -> PromotionPlan:
    validate_next(next_text)
    patches = _validate_canonical_page(page_text, target)
    target_version = tuple(int(part) for part in target.version.split("."))
    if target_version[2] == 0:
        raise PromotionError(
            "an existing canonical page cannot accept a new .0 release"
        )
    if patches and target_version <= patches[-1]:
        raise PromotionError("target patch would violate ascending version order")

    staging_watermark = WATERMARK_RE.search(next_text)
    canonical_watermark = WATERMARK_RE.search(page_text)
    if staging_watermark is None or canonical_watermark is None:
        raise PromotionError("validated release notes lost their watermark")

    body = next_text.split("\n", 1)[1]
    body = WATERMARK_RE.sub("", body, count=1)
    body = body.replace("RELEASE-SUMMARY NEXT", f"RELEASE-SUMMARY {target.tag}")
    body = shift_headings(body).strip()
    section = f"## {target.tag}\n\n{body}"

    promoted = (
        page_text[: canonical_watermark.start()]
        + staging_watermark.group(0)
        + page_text[canonical_watermark.end() :]
    )
    end = "<!-- PATCH-RELEASES-END -->"
    insert_at = promoted.index(end)
    promoted = (
        promoted[:insert_at].rstrip() + "\n\n" + section + "\n\n" + promoted[insert_at:]
    )
    page_path = root / target.page
    next_relative = Path("docs/releases/next.md")
    return PromotionPlan(
        root,
        {page_path: promoted},
        (root / next_relative,),
        (target.page, next_relative),
    )


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
        return promote_patch_page(root, target, next_text, page_text)

    if not index_path.is_file():
        raise PromotionError(
            "docs/releases/index.md is required for a new release series"
        )
    index_text = index_path.read_text(encoding="utf-8")
    return promote_new_page(root, target, next_text, index_text)
