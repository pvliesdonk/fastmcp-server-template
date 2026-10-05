#!/usr/bin/env python3
"""Require a recorded self-review of every commit a push sends.

The ``self-reviewing`` skill ends by recording its findings report for the
commit it reviewed (``--record``, report on stdin).  The ``self-review``
pre-push hook (``--hook``) then refuses a push whose commit has no record.
A record holds the report, so the check cannot be satisfied by an empty
file, and it is keyed by commit, so any commit after the review needs a new
one.  Records live in the git common directory, outside the work tree and
shared by every worktree of the clone.

Tag pushes pass: a release tag points at a commit already reviewed on its
way to the branch.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPORT_HEADING = "## Self-review"
SKIP_HINT = "SKIP=self-review git push"


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def record_dir() -> Path:
    common = Path(_git("rev-parse", "--git-common-dir"))
    return (common if common.is_absolute() else Path.cwd() / common) / "self-review"


def record_path(sha: str) -> Path:
    return record_dir() / f"{sha}.md"


def pushed_commit(environ: dict[str, str]) -> str | None:
    """The commit this push sends, or ``None`` when the push needs no review.

    pre-commit exports ``PRE_COMMIT_TO_REF`` for an incremental push and
    only the local branch for a push that includes the root commit.
    """
    if environ.get("PRE_COMMIT_REMOTE_BRANCH", "").startswith("refs/tags/"):
        return None
    ref = (
        environ.get("PRE_COMMIT_TO_REF")
        or environ.get("PRE_COMMIT_LOCAL_BRANCH")
        or "HEAD"
    )
    return _git("rev-parse", "--verify", f"{ref}^{{commit}}")


def record(report: str, rev: str) -> int:
    if REPORT_HEADING not in report:
        print(
            f"self-review: the report on stdin has no '{REPORT_HEADING}' "
            "heading; pipe in the findings block the self-reviewing skill "
            "produces.",
            file=sys.stderr,
        )
        return 1
    sha = _git("rev-parse", "--verify", f"{rev}^{{commit}}")
    path = record_path(sha)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report, encoding="utf-8")
    print(f"self-review: recorded the review of {sha[:12]}")
    return 0


def check(environ: dict[str, str]) -> int:
    sha = pushed_commit(environ)
    if sha is None or record_path(sha).is_file():
        return 0
    print(
        f"self-review: no recorded self-review of {sha[:12]}, the commit this "
        "push sends.\n"
        "Run the self-reviewing skill on the branch's cumulative diff. Once "
        "every finding is fixed or justified and committed, it records the "
        "review of that commit, and the push passes.\n"
        f"A person pushing without an agent: {SKIP_HINT}",
        file=sys.stderr,
    )
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Require a recorded self-review of every pushed commit."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--hook", action="store_true", help="pre-push check (pre-commit)")
    mode.add_argument(
        "--record",
        action="store_true",
        help="record the findings report on stdin for --rev",
    )
    parser.add_argument("--rev", default="HEAD", help="commit to record (HEAD)")
    args = parser.parse_args(argv)
    if args.record:
        return record(sys.stdin.read(), args.rev)
    return check(dict(os.environ))


if __name__ == "__main__":
    sys.exit(main())
