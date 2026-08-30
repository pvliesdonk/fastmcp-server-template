#!/usr/bin/env python3
"""Promote UPGRADING.md's ``## Unreleased`` section at release time.

``UPGRADING.md`` records the one-time manual steps a ``copier update`` jump
needs in a generated project.  It is written while the change that needs it
is being made, which is before anyone knows the version that change will
ship in — the release version comes from ``template-release.yml``'s ``bump``
input, dispatched later.  Guessing it by hand is how the file drifts: a
section headed ``## v5.2`` written during development is simply wrong if the
next dispatch cuts a patch, and nothing catches that.

So contributors write under ``## Unreleased`` and never name a version.

Since the per-minor split, ``UPGRADING.md`` itself is an *index*: its
released ``## vX.Y`` sections are one-line pointers, and each minor's full
migration steps live in ``upgrading/vX.Y.md``.  A 1400-line single file made
partial reads (a grep, a tail) look complete while missing whole minors;
the index enumerates every minor in one screen, and each per-minor file is
complete for its jump.  This script, run by the release workflow, moves the
Unreleased section into that layout:

* a **minor or major** release writes the section body to a new
  ``upgrading/vX.Y.md`` (under a ``## vX.Y`` heading that keeps whatever
  title followed ``## Unreleased``) and adds the pointer section to the
  index, just above ``## Unreleased``;
* a **patch** release appends the body to the existing ``upgrading/vX.Y.md``,
  because the layout is organised by minor and the index's preamble tells
  readers a patch's migration work lives in its minor's file — or creates
  file and pointer when the minor released without notes;
* either way an empty ``## Unreleased`` is left behind for the next change.

With ``--check`` it asserts the invariants instead: at most one
``## Unreleased`` and it is the last section (that is what CI runs, so a
second one cannot accumulate unnoticed above an older section), every
released index section is a short pointer whose ``upgrading/vX.Y.md``
exists, and every per-minor file has an index pointer and opens with its
own ``## vX.Y`` heading.  The pointer-shape check is what keeps full
migration content from quietly creeping back into the index.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
UPGRADING = REPO_ROOT / "UPGRADING.md"
SECTIONS_DIRNAME = "upgrading"

UNRELEASED_RE = re.compile(r"^## Unreleased(?P<title> - .*)?$", re.MULTILINE)
HEADING_RE = re.compile(r"^## .*$", re.MULTILINE)
MINOR_HEADING_RE = re.compile(r"^## v(?P<minor>\d+\.\d+)(?P<title> - .*)?$")
SECTION_FILE_RE = re.compile(r"^v(?P<minor>\d+\.\d+)\.md$")
PLACEHOLDER = "_Nothing yet._"
EMPTY_SECTION = f"## Unreleased\n\n{PLACEHOLDER}\n"
# An index section is a pointer, not content: at most this many non-blank
# body lines. One for the link line, one spare for a single-sentence gist.
_MAX_POINTER_LINES = 2


def _pointer_body(minor: str) -> str:
    return f"Steps: [{SECTIONS_DIRNAME}/v{minor}.md]({SECTIONS_DIRNAME}/v{minor}.md).\n"


def _section_bounds(text: str, start: int) -> tuple[int, int]:
    """Body span of the section whose heading starts at ``start``."""
    heading_end = text.index("\n", start) + 1
    following = HEADING_RE.search(text, heading_end)
    return heading_end, following.start() if following else len(text)


def _is_empty(body: str) -> bool:
    """A section carrying nothing but whitespace or the placeholder."""
    return body.strip() in ("", PLACEHOLDER)


def _index_minors(text: str) -> dict[str, tuple[int, int, int]]:
    """``{minor: (heading_start, body_start, body_end)}`` for every ``## vX.Y``."""
    minors: dict[str, tuple[int, int, int]] = {}
    for match in HEADING_RE.finditer(text):
        minor_match = MINOR_HEADING_RE.match(match.group(0))
        if minor_match is None:
            continue
        body_start, body_end = _section_bounds(text, match.start())
        minors[minor_match.group("minor")] = (match.start(), body_start, body_end)
    return minors


def check(text: str, sections_dir: Path) -> list[str]:
    """Structural problems, as messages; empty when the layout is sound."""
    problems: list[str] = []
    matches = list(UNRELEASED_RE.finditer(text))
    if len(matches) > 1:
        problems.append(
            f"{len(matches)} '## Unreleased' sections; exactly one is allowed. "
            "Merge them — the release promotes one section, and the others "
            "would be stranded above released ones."
        )
    if matches:
        headings = list(HEADING_RE.finditer(text))
        if headings and headings[-1].start() != matches[-1].start():
            problems.append(
                "'## Unreleased' is not the last section. Sections run oldest "
                "to newest, so unreleased work belongs at the end of the file."
            )

    indexed = _index_minors(text)
    for minor, (_, body_start, body_end) in indexed.items():
        problems.extend(
            _check_indexed_minor(minor, text[body_start:body_end], sections_dir)
        )

    if sections_dir.is_dir():
        for path in sorted(sections_dir.iterdir()):
            file_match = SECTION_FILE_RE.match(path.name)
            if file_match is not None and file_match.group("minor") not in indexed:
                problems.append(
                    f"{SECTIONS_DIRNAME}/{path.name} has no '## v"
                    f"{file_match.group('minor')}' index section in "
                    "UPGRADING.md — unindexed steps are invisible to readers "
                    "and to the copier-update notes pipeline."
                )
    return problems


def _check_indexed_minor(minor: str, body: str, sections_dir: Path) -> list[str]:
    """One indexed minor's invariants: pointer-shaped body, existing file
    that opens with its own heading."""
    problems: list[str] = []
    link = f"{SECTIONS_DIRNAME}/v{minor}.md"
    if link not in body:
        problems.append(
            f"the '## v{minor}' index section does not link {link}. "
            "Released sections are pointers; the full steps live in "
            "that per-minor file."
        )
    elif len([line for line in body.splitlines() if line.strip()]) > (
        _MAX_POINTER_LINES
    ):
        problems.append(
            f"the '## v{minor}' index section carries more than "
            f"{_MAX_POINTER_LINES} non-blank lines. Keep the index a "
            f"pointer and put the steps in {link}."
        )
    section_path = sections_dir / f"v{minor}.md"
    if not section_path.is_file():
        problems.append(f"'## v{minor}' is indexed but {link} does not exist.")
    elif not section_path.read_text(encoding="utf-8").startswith(f"## v{minor}"):
        problems.append(
            f"{link} does not open with its own '## v{minor}' heading — "
            "the update-notes pipeline concatenates these files and "
            "selects on that heading."
        )
    return problems


@dataclass(frozen=True)
class Promotion:
    """One promotion's outcome: the rewritten index, the per-minor file, a note."""

    index_text: str
    note: str
    # None when nothing was promoted; otherwise the full new content of
    # ``upgrading/v<minor>.md`` and the minor it belongs to.
    minor: str | None = None
    section_text: str | None = None


def promote(text: str, version: str, existing_section: str | None) -> Promotion:
    """Move the Unreleased body into ``version``'s minor.

    Pure: *text* is the index content, *existing_section* is the current
    ``upgrading/vX.Y.md`` content (``None`` when the file does not exist),
    and the caller owns all file I/O on the returned result.
    """
    match = UNRELEASED_RE.search(text)
    if not match:
        return Promotion(text, "no '## Unreleased' section — nothing to promote")

    body_start, body_end = _section_bounds(text, match.start())
    body = text[body_start:body_end]
    if _is_empty(body):
        return Promotion(text, "'## Unreleased' is empty — nothing to promote")

    minor = ".".join(version.lstrip("v").split(".")[:2])
    addition = body.strip("\n")
    text = text[: match.start()] + EMPTY_SECTION + text[body_end:]

    if existing_section is not None:
        # Patch into a minor whose file already exists: the notes belong at
        # the end of that file, per the layout's own reading order.  The
        # Unreleased heading resets to bare either way — keeping the old
        # title would leave it describing content that has moved, and the
        # next minor release would then promote a stale title.
        section_text = f"{existing_section.rstrip()}\n\n{addition}\n"
        return Promotion(
            text,
            f"appended the Unreleased notes to {SECTIONS_DIRNAME}/v{minor}.md",
            minor=minor,
            section_text=section_text,
        )

    title = match.group("title") or ""
    section_text = f"## v{minor}{title}\n\n{addition}\n"
    pointer = f"## v{minor}{title}\n\n{_pointer_body(minor)}"
    # The pointer joins the released sections directly above the fresh
    # Unreleased tail (sections run oldest to newest).
    unreleased_at = text.rindex(EMPTY_SECTION)
    text = f"{text[:unreleased_at].rstrip()}\n\n{pointer}\n{EMPTY_SECTION}"
    return Promotion(
        text,
        f"promoted '## Unreleased' to {SECTIONS_DIRNAME}/v{minor}.md",
        minor=minor,
        section_text=section_text,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--version",
        help="Release version being cut, e.g. v5.2.0. Required unless --check.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify the index/per-minor-file invariants without writing.",
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=UPGRADING,
        help="Path to UPGRADING.md (default: the repository's own). The "
        "per-minor files live in the 'upgrading' directory beside it.",
    )
    args = parser.parse_args()

    if not args.file.is_file():
        print(f"ERROR: {args.file} not found.", file=sys.stderr)
        return 1
    text = args.file.read_text(encoding="utf-8")
    sections_dir = args.file.parent / SECTIONS_DIRNAME

    problems = check(text, sections_dir)
    if problems:
        for problem in problems:
            print(f"ERROR: {args.file.name}: {problem}", file=sys.stderr)
        return 1
    if args.check:
        print(f"{args.file.name}: index and per-minor files are well-formed.")
        return 0

    if not args.version:
        print("ERROR: --version is required unless --check is given.", file=sys.stderr)
        return 1

    minor = ".".join(args.version.lstrip("v").split(".")[:2])
    section_path = sections_dir / f"v{minor}.md"
    existing_section = (
        section_path.read_text(encoding="utf-8") if section_path.is_file() else None
    )
    result = promote(text, args.version, existing_section)
    print(f"{args.file.name}: {result.note}.")
    if result.index_text != text:
        args.file.write_text(result.index_text, encoding="utf-8")
    if result.section_text is not None:
        sections_dir.mkdir(parents=True, exist_ok=True)
        section_path.write_text(result.section_text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
