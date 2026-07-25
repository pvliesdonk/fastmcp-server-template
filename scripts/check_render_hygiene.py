#!/usr/bin/env python3
"""Assert a pristine copier render is already whitespace-clean.

The template ships the ``trailing-whitespace`` and ``end-of-file-fixer``
pre-commit hooks (see ``.pre-commit-config.yaml.jinja``).  Both *rewrite*
files.  So any render artifact those hooks would touch is a latent
``copier update`` conflict: the downstream commits the fixed-up form,
copier's 3-way merge sees ``base`` (the pristine render) differ from
``ours`` (the committed file) in that exact region, and the moment a
template version also changes that region -- ``theirs`` -- the merge
conflicts for **every** downstream, even ones that never touched the file.

Issue #251 is the real instance: ``ci.yml.jinja`` used to end with the
``{% endif %}`` closing the ``enable_structural_gate`` block.  Jinja (no
``trim_blocks``) keeps the newline after a block tag, so the render ended
``\\n\\n``; ``end-of-file-fixer`` stripped the blank on every downstream's
first commit.  Latent for months -- until v2.11.0 appended the
``ci-success`` job to the same tail and every downstream's update
conflicted on ci.yml alone.

This checker is the regression guard: run it over a freshly rendered
project and it fails if either hook would have anything to do.  Keeping a
render byte-identical to its committed form is what makes copier's merge
see ``ours == base`` and apply template changes cleanly.

Usage::

    python scripts/check_render_hygiene.py /tmp/smoke [/tmp/smoke-gate-off ...]

Exits 0 when every checked file is clean, 1 otherwise (violations are
printed as ``path:line: message``, plus GitHub Actions ``::error::``
annotations when ``GITHUB_ACTIONS`` is set).

Template-repo only -- listed in ``copier.yml``'s ``_exclude``, so it never
renders into generated projects.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Directories never present in a pristine render, but cheap to guard against:
# a caller may point this at a tree that has since been installed or linted.
_SKIP_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        "node_modules",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
    }
)

# pre-commit resolves `types: [text]` via identify, which reads a leading
# chunk and calls the file binary if it contains a NUL byte.  Mirror that
# so we skip exactly the files the hooks skip (the vendored SPA and the
# rendered docs are text and ARE checked; images are not).
_BINARY_SNIFF_BYTES = 1024


class Violation:
    """One hook finding: a file (and optionally line) a hook would rewrite."""

    def __init__(self, path: Path, line: int | None, message: str) -> None:
        self.path = path
        self.line = line
        self.message = message

    def format(self, root: Path) -> str:
        try:
            rel = self.path.relative_to(root)
        except ValueError:  # pragma: no cover - path always under root in practice
            rel = self.path
        where = f"{rel}:{self.line}" if self.line is not None else str(rel)
        return f"{where}: {self.message}"


def _is_binary(data: bytes) -> bool:
    return b"\x00" in data[:_BINARY_SNIFF_BYTES]


def check_file(path: Path) -> list[Violation]:
    """Return the violations `trailing-whitespace` / `end-of-file-fixer` would fix."""
    data = path.read_bytes()
    # Both hooks leave an empty file untouched.
    if not data or _is_binary(data):
        return []

    violations: list[Violation] = []

    # end-of-file-fixer: exactly one trailing newline.
    if not data.endswith(b"\n"):
        violations.append(
            Violation(path, None, "missing final newline (end-of-file-fixer would add)")
        )
    elif data.endswith(b"\n\n"):
        violations.append(
            Violation(
                path,
                None,
                "blank line(s) at EOF (end-of-file-fixer would strip) — "
                "a Jinja block tag at EOF is the usual cause; "
                "use {%- endif %} or drop the trailing newline",
            )
        )

    # trailing-whitespace: no space/tab before the line terminator.  The
    # template passes no --markdown-linebreak-ext, so .md files are not
    # exempt: a two-space hard break would be stripped too.
    for lineno, raw in enumerate(data.split(b"\n"), start=1):
        line = raw.removesuffix(b"\r")
        if line != line.rstrip(b" \t"):
            violations.append(
                Violation(
                    path,
                    lineno,
                    "trailing whitespace (trailing-whitespace would strip)",
                )
            )

    return violations


def check_tree(root: Path) -> list[Violation]:
    """Check every text file under `root`, skipping build/VCS directories."""
    violations: list[Violation] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        if _SKIP_DIRS.intersection(path.relative_to(root).parts):
            continue
        violations.extend(check_file(path))
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "roots",
        nargs="+",
        type=Path,
        help="rendered project directories to check",
    )
    args = parser.parse_args(argv)

    in_actions = bool(os.environ.get("GITHUB_ACTIONS"))
    failed = False

    for root in args.roots:
        if not root.is_dir():
            print(f"not a directory: {root}", file=sys.stderr)
            failed = True
            continue
        violations = check_tree(root)
        if not violations:
            print(f"render hygiene OK: {root}")
            continue
        failed = True
        print(f"render hygiene FAILED: {root} ({len(violations)} violation(s))")
        for violation in violations:
            line = violation.format(root)
            print(f"  {line}")
            if in_actions:
                print(f"::error::{root}: {line}")

    if failed:
        print(
            "\nA pristine render must already satisfy the pre-commit hooks the "
            "template ships; otherwise every downstream's committed file differs "
            "from the render at that spot and copier update conflicts there (#251).",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
