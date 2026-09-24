#!/usr/bin/env python3
"""Compare this project's template-owned files with a pristine template render.

Every file ``copier update`` re-renders (anything not under
``_skip_if_exists``, and not one of the generated config artefacts) is
owned by the template outside its sentinel blocks: the project's content
belongs inside a ``*-START`` / ``*-END`` block the template declares, or in
a file the template does not render.  This script renders the template at
one ref with this project's own answers and reports every template-owned
file whose content outside those blocks differs from the render.  A
difference is the project's drift: restore the template's lines and move
the project's content into a sentinel block, or open a Decay issue for it.

Usage::

    python scripts/check_template_conformance.py            # working tree vs _commit
    python scripts/check_template_conformance.py --ref v9.1.0
    python scripts/check_template_conformance.py --rev HEAD --output drift.md

Exit status: 0 when every template-owned file conforms, 1 when at least one
differs, 2 when the comparison could not be made (no answers file, the
render failed, copier unavailable).

The comparison ignores trailing whitespace and blank lines, compares a
sentinel block as a single token (its interior is the project's), and only
honours sentinel names the pristine render declares, so a block the project
invents does not shield its content.  In Python files, imports the project
adds are allowed — the template's skeletons ask for them, and ruff's import
sorting leaves no stable place for a sentinel — but every name the
template's render imports must still be imported.

``scripts/report_seeded_changes.py`` calls :func:`check` during
``copier update`` to write ``.copier-template-drift.md``.  Importing this
module has no side effects; the ``uv run`` fallback runs from ``main()``.
"""

from __future__ import annotations

import argparse
import ast
import difflib
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

ANSWERS = Path(".copier-answers.yml")
DRIFT_REPORT = Path(".copier-template-drift.md")

# Rendered, but written afterwards by tooling rather than by hand: copier
# owns the answers file; `gen_config_surface.py` splices server.json's
# environment arrays and `stamp_manifests.py` its versions on every release.
_NOT_COMPARED = (".copier-answers.yml", "server.json")

# Lines inside a compared file whose value release tooling writes: knope
# bumps pyproject.toml's `version`.  Compared by key, not by value.
_TOOL_WRITTEN_LINES = {"pyproject.toml": re.compile(r'^version = "')}

# A sentinel marker is a comment line: `# NAME-START`, `<!-- NAME-START -->`,
# `// NAME-START`.  Anchored at the start of the line so prose that quotes a
# marker in backticks is not mistaken for one.
_START = re.compile(r"^\s*(?:#|<!--|//)\s*([A-Z][A-Z0-9-]*)-START\b")
_END = re.compile(r"^\s*(?:#|<!--|//)\s*([A-Z][A-Z0-9-]*)-END\b")

_MAX_COMMITS = 5  # per file, in the order blame first meets them
_MAX_HUNK_LINES = 60  # per file; the rest is summarised, the command shows all
_FENCE = "````"  # four backticks: a drifted markdown file may itself contain ```


@dataclass(frozen=True)
class Line:
    """One compared unit: the project line number (1-based), the key the
    comparison uses, and the text a report shows."""

    number: int
    key: str
    text: str


@dataclass
class Drift:
    """A template-owned file that differs from the render outside its sentinels."""

    path: str
    hunks: list[str] = field(default_factory=list)
    ranges: list[tuple[int, int]] = field(default_factory=list)
    note: str = ""


# --------------------------------------------------------------------------- #
# Comparison
# --------------------------------------------------------------------------- #
def normalize(text: str) -> list[str]:
    return [line.rstrip() for line in text.replace("\r\n", "\n").split("\n")]


def sentinel_names(lines: list[str]) -> set[str]:
    """Names of the sentinel blocks *lines* opens and closes, in balance.

    Called on the pristine render: only blocks the template declares may hold
    project content.  An unbalanced block in the render is not a sentinel."""
    opened: set[str] = set()
    closed: set[str] = set()
    for line in lines:
        if m := _START.match(line):
            opened.add(m.group(1))
        elif m := _END.match(line):
            closed.add(m.group(1))
    return opened & closed


def collapse_sentinels(lines: list[str], legal: set[str]) -> list[Line]:
    """Number the lines and replace each legal ``NAME-START..NAME-END`` block
    with one unit, so the block's interior never takes part in the comparison."""
    out: list[Line] = []
    i = 0
    while i < len(lines):
        start = _START.match(lines[i])
        if start and start.group(1) in legal:
            name = start.group(1)
            end = next(
                (
                    j
                    for j in range(i + 1, len(lines))
                    if (m := _END.match(lines[j])) and m.group(1) == name
                ),
                None,
            )
            if end is not None:
                out.append(Line(i + 1, f"@@SENTINEL {name}@@", lines[i]))
                i = end + 1
                continue
        out.append(Line(i + 1, lines[i], lines[i]))
        i += 1
    return out


def python_imports(text: str) -> tuple[set[str], set[int]] | None:
    """(imported names, line numbers the import statements span); None when
    *text* is not valid Python (a conflict marker, for one)."""
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return None
    names: set[str] = set()
    spans: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(f"import {a.name} as {a.asname}" for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = "." * node.level + (node.module or "")
            names.update(
                f"from {module} import {a.name} as {a.asname}" for a in node.names
            )
        else:
            continue
        spans.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))
    return names, spans


def _significant(
    units: list[Line], skip: set[int], tool_written: re.Pattern[str] | None
) -> list[Line]:
    out = [u for u in units if u.key.strip() and u.number not in skip]
    if tool_written is None:
        return out
    return [
        Line(u.number, tool_written.pattern, u.text) if tool_written.match(u.key) else u
        for u in out
    ]


def _hunks(project: list[Line], pristine: list[Line]) -> Drift:
    drift = Drift(path="")
    matcher = difflib.SequenceMatcher(
        a=[u.key for u in pristine], b=[u.key for u in project], autojunk=False
    )
    for tag, a0, a1, b0, b1 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if b1 > b0:
            first, last = project[b0].number, project[b1 - 1].number
            where = (
                f"project lines {first}-{last}"
                if last > first
                else f"project line {first}"
            )
        else:
            first = last = (
                project[b0].number
                if b0 < len(project)
                else (project[-1].number if project else 1)
            )
            where = f"missing before project line {first}"
        body = [f"-{u.text}" for u in pristine[a0:a1]] + [
            f"+{u.text}" for u in project[b0:b1]
        ]
        drift.hunks.append(f"@@ {where} @@\n" + "\n".join(body))
        drift.ranges.append((first, last))
    return drift


def compare_text(
    project_text: str,
    pristine_text: str,
    *,
    python: bool,
    tool_written: re.Pattern[str] | None = None,
) -> Drift:
    """Differences outside the render's sentinel blocks; no hunks means conformant."""
    pristine_lines = normalize(pristine_text)
    project_lines = normalize(project_text)
    legal = sentinel_names(pristine_lines)
    pristine = collapse_sentinels(pristine_lines, legal)
    project = collapse_sentinels(project_lines, legal)
    skip_pristine: set[int] = set()
    skip_project: set[int] = set()
    missing_imports: list[str] = []
    if python:
        ours, theirs = python_imports(project_text), python_imports(pristine_text)
        if ours is not None and theirs is not None:
            skip_project, skip_pristine = ours[1], theirs[1]
            missing_imports = sorted(theirs[0] - ours[0])
    drift = _hunks(
        _significant(project, skip_project, tool_written),
        _significant(pristine, skip_pristine, tool_written),
    )
    if missing_imports:
        drift.hunks.insert(
            0,
            "@@ imports the template renders but this file does not @@\n"
            + "\n".join(
                f"-{name.removesuffix(' as None')}" for name in missing_imports
            ),
        )
    return drift


# --------------------------------------------------------------------------- #
# Walking the render
# --------------------------------------------------------------------------- #
ReadProject = Callable[[str], "bytes | str | None"]


def template_owned(render_root: Path, skip_patterns: list[str]) -> list[str]:
    """Every file and symlink the render holds that ``copier update`` re-renders."""
    from report_seeded_changes import _generated, matching_files

    skipped = matching_files(render_root, skip_patterns)
    owned: list[str] = []
    for p in render_root.rglob("*"):
        if (
            not (p.is_symlink() or p.is_file())
            or ".git" in p.relative_to(render_root).parts
        ):
            continue
        rel = p.relative_to(render_root).as_posix()
        if rel in skipped or rel in _NOT_COMPARED or _generated(rel):
            continue
        owned.append(rel)
    return sorted(owned)


def _compare_link(
    rel: str, pristine_path: Path, project: bytes | str | None
) -> Drift | None:
    target = str(pristine_path.readlink())
    if project == target:
        return None
    return Drift(rel, note=f"should be a symlink to `{target}`")


def compare_file(
    rel: str, render_root: Path, read_project: ReadProject
) -> Drift | None:
    """The drift of one template-owned file, or None when it conforms."""
    pristine_path = render_root / rel
    project = read_project(rel)
    if pristine_path.is_symlink():
        return _compare_link(rel, pristine_path, project)
    if project is None:
        return Drift(rel, note="deleted in the project; the template renders it")
    if isinstance(project, str):
        return Drift(rel, note=f"a symlink to `{project}`; the template renders a file")
    pristine = pristine_path.read_bytes()
    try:
        project_text, pristine_text = project.decode("utf-8"), pristine.decode("utf-8")
    except UnicodeDecodeError:
        return None if project == pristine else Drift(rel, note="binary file differs")
    drift = compare_text(
        project_text,
        pristine_text,
        python=rel.endswith(".py"),
        tool_written=_TOOL_WRITTEN_LINES.get(rel),
    )
    drift.path = rel
    return drift if drift.hunks else None


def check(
    render_root: Path, read_project: ReadProject, skip_patterns: list[str]
) -> list[Drift]:
    """Every template-owned file that differs from *render_root* outside its sentinels."""
    found = (
        compare_file(rel, render_root, read_project)
        for rel in template_owned(render_root, skip_patterns)
    )
    return [d for d in found if d is not None]


def read_worktree(root: Path) -> ReadProject:
    """File bytes, symlink target (str), or None, from the working tree."""

    def read(rel: str) -> bytes | str | None:
        p = root / rel
        if p.is_symlink():
            return str(p.readlink())
        return p.read_bytes() if p.is_file() else None

    return read


def read_revision(rev: str) -> ReadProject:
    """File bytes, symlink target (str), or None, from a git revision."""
    listing = subprocess.run(
        ["git", "ls-tree", "-r", "-z", "--full-tree", rev],
        capture_output=True,
        check=True,
    ).stdout.decode("utf-8")
    prefix = subprocess.run(
        ["git", "rev-parse", "--show-prefix"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    modes: dict[str, str] = {}
    for entry in filter(None, listing.split("\0")):
        meta, path = entry.split("\t", 1)
        if path.startswith(prefix):
            modes[path[len(prefix) :]] = meta.split()[0]

    def read(rel: str) -> bytes | str | None:
        if rel not in modes:
            return None
        blob = subprocess.run(
            ["git", "show", f"{rev}:./{rel}"], capture_output=True, check=True
        ).stdout
        return blob.decode("utf-8") if modes[rel] == "120000" else blob

    return read


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
def last_commits(rel: str, ranges: list[tuple[int, int]], rev: str | None) -> list[str]:
    """``sha subject`` of the commits that last touched the drifted lines."""
    commits: dict[str, str] = {}
    for first, last in ranges:
        args = ["git", "blame", "--porcelain", "-L", f"{first},{last}"]
        proc = subprocess.run(
            [*args, *([rev] if rev else []), "--", rel],
            capture_output=True,
            text=True,
            check=False,
        )
        sha = ""
        for line in proc.stdout.splitlines():
            if re.match(r"^[0-9a-f]{40} ", line):
                sha = line[:40]
            elif line.startswith("summary ") and sha not in commits:
                commits[sha] = line.removeprefix("summary ")
    return [
        "not committed yet" if set(sha) == {"0"} else f"`{sha[:10]}` {subject}"
        for sha, subject in commits.items()
    ]


def blame_note(drift: Drift, rev: str | None) -> str:
    commits = last_commits(drift.path, drift.ranges, rev) if drift.ranges else []
    if len(commits) > _MAX_COMMITS:
        rest = len(commits) - _MAX_COMMITS
        commits = [*commits[:_MAX_COMMITS], f"and {rest} more (`git blame` the lines)"]
    return (
        "Last commits to touch these lines: " + "; ".join(commits) + "."
        if commits
        else ""
    )


_HEADER = """# Template-owned files that differ from the template

<!-- Generated by scripts/check_template_conformance.py; do not edit.
     Re-run it to refresh. -->

Template `{src}` at `{ref}`, compared with {what}, outside the template's
sentinel blocks.
"""

_EXPLAIN = """
{count} template-owned file(s) differ from the pristine render outside their
sentinel blocks. None of these differences came from the template: each is
content this project wrote into lines the template owns. `copier update`
carries such a difference forward without a conflict marker whenever the
template did not change the same lines, so an update that shows no conflict
can still leave the project forked here. For each file, restore the
template's lines and move the project's content into a sentinel block the
render declares (or into a file the template does not render), or open a
Decay issue in this project that names the file. A `-` line is the
template's, a `+` line is the project's.
"""


def report_header(*, src: str, ref: str, what: str) -> str:
    return _HEADER.format(src=src, ref=ref, what=what)


def render_report(
    drifts: list[Drift],
    header: str,
    describe: Callable[[Drift], str] | None = None,
) -> str:
    """The markdown report; *describe* adds a paragraph per drifted file."""
    text = header
    if not drifts:
        text += "\nEvery template-owned file matches the render outside its sentinel blocks.\n"
        return text
    text += _EXPLAIN.format(count=len(drifts))
    for d in drifts:
        text += f"\n## `{d.path}`\n"
        about = " ".join(s for s in (d.note, describe(d) if describe else "") if s)
        if about:
            text += f"\n{about}\n"
        if d.hunks:
            body = "\n".join(d.hunks).split("\n")
            if len(body) > _MAX_HUNK_LINES:
                rest = len(body) - _MAX_HUNK_LINES
                body = [
                    *body[:_MAX_HUNK_LINES],
                    f"… {rest} more line(s); run the script for all",
                ]
            text += (
                f"\n{_FENCE}diff\n"
                + "\n".join(line.rstrip() for line in body)
                + f"\n{_FENCE}\n"
            )
    return text


# --------------------------------------------------------------------------- #
# Command line
# --------------------------------------------------------------------------- #
def _reexec_with_deps() -> bool:
    """Re-exec under `uv run --no-project` when copier is missing; True when
    the caller should give up instead."""
    try:
        import copier  # noqa: F401
    except ImportError:
        pass
    else:
        return False
    if os.environ.get("_CONFORMANCE_BOOTSTRAPPED") == "1":
        return True
    os.environ["_CONFORMANCE_BOOTSTRAPPED"] = "1"
    argv = [
        "uv",
        "run",
        "--no-project",
        "--with",
        "copier",
        "python",
        __file__,
        *sys.argv[1:],
    ]
    try:
        os.execvpe("uv", argv, os.environ)
    except OSError:
        return True
    return True  # pragma: no cover — execvpe does not return on success


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument(
        "--ref", help="template ref to render (default: _commit in the answers file)"
    )
    parser.add_argument(
        "--rev", help="compare this git revision instead of the working tree"
    )
    parser.add_argument(
        "--output", type=Path, help="write the markdown report here instead of stdout"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from report_seeded_changes import (
        _read_simple_answers,
        _render,
        _render_pattern,
        _skip_patterns,
    )

    if not ANSWERS.is_file():
        print(
            "check_template_conformance: no .copier-answers.yml here", file=sys.stderr
        )
        return 2
    answers = _read_simple_answers(ANSWERS.read_text(encoding="utf-8"))
    src, ref = (
        str(answers.get("_src_path", "")),
        args.ref or str(answers.get("_commit", "")),
    )
    if not (src and ref):
        print(
            "check_template_conformance: the answers file names no template",
            file=sys.stderr,
        )
        return 2
    if _reexec_with_deps():
        print(
            "check_template_conformance: copier is not importable and uv is unavailable",
            file=sys.stderr,
        )
        return 2
    try:
        read = read_revision(args.rev) if args.rev else read_worktree(Path.cwd())
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "render"
            _render(src, ref, answers, root)
            patterns = [_render_pattern(p, answers) for p in _skip_patterns(src, ref)]
            drifts = check(root, read, patterns)
    except Exception as exc:  # report, never a traceback
        print(
            f"check_template_conformance: could not render {src}@{ref}: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2
    what = f"commit `{args.rev}`" if args.rev else "the working tree"
    header = report_header(src=src, ref=ref, what=what)
    report = render_report(drifts, header, lambda d: blame_note(d, args.rev))
    if args.output:
        args.output.write_text(report, encoding="utf-8")
    else:
        print(report, end="")
    return 1 if drifts else 0


if __name__ == "__main__":
    sys.exit(main())
