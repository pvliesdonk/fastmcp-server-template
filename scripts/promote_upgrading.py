#!/usr/bin/env python3
"""Promote UPGRADING.md's ``## Unreleased`` section at release time.

``UPGRADING.md`` records the one-time manual steps a ``copier update`` jump
needs in a generated project.  It is written while the change that needs it
is being made, which is before anyone knows the version that change will
ship in — the release version comes from ``template-release.yml``'s ``bump``
input, dispatched later.  Guessing it by hand is how the file drifts: a
section headed ``## v5.2`` written during development is simply wrong if the
next dispatch cuts a patch, and nothing catches that.

So contributors write under ``## Unreleased`` and never name a version.  This
script, run by the release workflow, turns that section into the real one:

* a **minor or major** release renames the heading to ``## vX.Y``, keeping
  whatever title follows it;
* a **patch** release appends the section's body to the existing ``## vX.Y``
  section, because the file is organised by minor and its own preamble tells
  readers a patch's migration work lives in its minor's section;
* either way an empty ``## Unreleased`` is left behind for the next change.

With ``--check`` it asserts the invariants instead: at most one
``## Unreleased``, and it is the last section.  That is what CI runs, so a
second one cannot accumulate unnoticed above an older section.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
UPGRADING = REPO_ROOT / "UPGRADING.md"

UNRELEASED_RE = re.compile(r"^## Unreleased(?P<title> - .*)?$", re.MULTILINE)
HEADING_RE = re.compile(r"^## .*$", re.MULTILINE)
PLACEHOLDER = "_Nothing yet._"
EMPTY_SECTION = f"## Unreleased\n\n{PLACEHOLDER}\n"


def _section_bounds(text: str, start: int) -> tuple[int, int]:
    """Body span of the section whose heading starts at ``start``."""
    heading_end = text.index("\n", start) + 1
    following = HEADING_RE.search(text, heading_end)
    return heading_end, following.start() if following else len(text)


def _is_empty(body: str) -> bool:
    """A section carrying nothing but whitespace or the placeholder."""
    return body.strip() in ("", PLACEHOLDER)


def check(text: str) -> list[str]:
    """Structural problems, as messages; empty when the file is sound."""
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
    return problems


def promote(text: str, version: str) -> tuple[str, str]:
    """Rewrite the Unreleased section for ``version``; return (text, note)."""
    match = UNRELEASED_RE.search(text)
    if not match:
        return text, "no '## Unreleased' section — nothing to promote"

    body_start, body_end = _section_bounds(text, match.start())
    body = text[body_start:body_end]
    if _is_empty(body):
        return text, "'## Unreleased' is empty — nothing to promote"

    minor = ".".join(version.lstrip("v").split(".")[:2])
    existing = re.search(rf"^## v{re.escape(minor)}(?: - .*)?$", text, re.MULTILINE)

    if existing:
        # Patch into a minor that already has a section: its body belongs at
        # the end of that section, per the file's own reading order.  The
        # whole Unreleased section is replaced, heading included — keeping
        # the old title would leave it describing content that has moved,
        # and the next minor release would then promote a stale title.
        text = text[: match.start()] + EMPTY_SECTION + text[body_end:]
        insert_at = _section_bounds(text, existing.start())[1]
        addition = body.strip("\n")
        text = f"{text[:insert_at]}{addition}\n\n{text[insert_at:]}"
        return text, f"appended the Unreleased notes to the v{minor} section"

    title = match.group("title") or ""
    text = f"{text[: match.start()]}## v{minor}{title}{text[match.end() :]}"
    text = text.rstrip("\n") + f"\n\n{EMPTY_SECTION}"
    return text, f"promoted '## Unreleased' to '## v{minor}'"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--version",
        help="Release version being cut, e.g. v5.2.0. Required unless --check.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify the Unreleased section's invariants without writing.",
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=UPGRADING,
        help="Path to UPGRADING.md (default: the repository's own).",
    )
    args = parser.parse_args()

    if not args.file.is_file():
        print(f"ERROR: {args.file} not found.", file=sys.stderr)
        return 1
    text = args.file.read_text(encoding="utf-8")

    problems = check(text)
    if problems:
        for problem in problems:
            print(f"ERROR: {args.file.name}: {problem}", file=sys.stderr)
        return 1
    if args.check:
        print(f"{args.file.name}: Unreleased section is well-formed.")
        return 0

    if not args.version:
        print("ERROR: --version is required unless --check is given.", file=sys.stderr)
        return 1

    promoted, note = promote(text, args.version)
    print(f"{args.file.name}: {note}.")
    if promoted != text:
        args.file.write_text(promoted, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
