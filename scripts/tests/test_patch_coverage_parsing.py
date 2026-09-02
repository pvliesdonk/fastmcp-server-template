"""Guard the `codecov/patch` description's coverage parse in `ci.yml` (#561).

The rendered `ci.yml` posts a `codecov/patch` commit status whose
description quotes the patch coverage diff-cover computed.  diff-cover's
summary carries two numbers, and the step used to read the wrong one::

    Total:   4 lines      <- coverable LINE COUNT
    Missing: 0 lines
    Coverage: 100%        <- the percentage the description means

A `Total:` parse posted the line count with a `%` suffix.  Harmless-looking
on the success branch (a small, fully covered diff read ``Patch coverage:
4%``), and actively misleading on the failure branch, which is the one a
reader acts on: an 80-line diff at 50% posted ``Patch coverage: 80%
(minimum 80%)`` on a *failing* status.

The pass/fail decision never came from this value — it is diff-cover's own
``--fail-under`` exit code — so nothing but the human-readable description
was ever wrong.  That is exactly why a test is worth having: no gate turns
red when this regresses.

The pattern is **extracted from `ci.yml.jinja` rather than restated here**,
so this test cannot pass against a workflow that has drifted back to
`Total:`.  It is exercised through the real ``grep -oP`` the step runs,
against captured diff-cover output, rather than a Python re-implementation
— `\\K` has no Python `re` equivalent, and a translated pattern would prove
nothing about the shell one.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_CI_WORKFLOW = _REPO / ".github" / "workflows" / "ci.yml.jinja"

# Real diff-cover console output.  Both fixtures were produced by running
# diff-cover 9.x against a two-commit fixture repo, not hand-written: the
# whole point is that the parse matches what the tool actually prints.
_PARTIAL = """\
-------------
Diff Coverage
Diff: main...HEAD, staged and unstaged changes
-------------
src/m.py (50.0%): Missing lines 7-8
-------------
Total:   4 lines
Missing: 2 lines
Coverage: 50%
-------------
"""

_FULL = """\
-------------
Diff Coverage
Diff: origin/main...HEAD, staged and unstaged changes
-------------
src/markdown_vault_mcp/managers/search.py (100%)
-------------
Total:   4 lines
Missing: 0 lines
Coverage: 100%
-------------
"""

_NO_COVERABLE_LINES = """\
-------------
Diff Coverage
Diff: main...HEAD, staged and unstaged changes
-------------
No lines with coverage information in this diff.
-------------
"""


def _step_pattern() -> str:
    """The PCRE the `Check patch coverage` step greps with, from the workflow."""
    text = _CI_WORKFLOW.read_text(encoding="utf-8")
    matches = re.findall(r"grep -oP '([^']+)'", text)
    assert matches, f"no `grep -oP '...'` found in {_CI_WORKFLOW}"
    assert len(matches) == 1, (
        f"{_CI_WORKFLOW} has {len(matches)} `grep -oP` patterns; this test "
        "assumes the patch-coverage parse is the only one — point it at the "
        "right one before adding another."
    )
    return matches[0]


def _grep(pattern: str, text: str) -> list[str]:
    proc = subprocess.run(
        ["grep", "-oP", pattern],
        input=text,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout.split()


pytestmark = pytest.mark.skipif(
    shutil.which("grep") is None
    or subprocess.run(
        ["grep", "-qP", "x"], input="x", capture_output=True, text=True, check=False
    ).returncode
    not in (0, 1),
    reason="grep without PCRE (-P) support; CI runs GNU grep on ubuntu-latest",
)


class TestPatchCoverageParse:
    def test_reads_the_percentage_not_the_line_count(self):
        """The regression itself: 4 coverable lines, all covered.

        `Total:` yields 4 and the status reads `Patch coverage: 4%` on a
        diff that was in fact fully covered — the shape observed on
        markdown-vault-mcp PR #1267.
        """
        assert _grep(_step_pattern(), _FULL) == ["100"]

    def test_the_failing_case_reports_the_coverage_that_failed(self):
        """The dangerous direction: a partially covered diff.

        Here `Total:` and the minimum coincide in the reader's eye — the
        old parse posted the line count beside `(minimum 80%)`, so the
        number a reader would act on was not the number that failed.
        """
        assert _grep(_step_pattern(), _PARTIAL) == ["50"]

    def test_matches_exactly_once(self):
        """`$(...)` captures every match, so a second one would splice two
        numbers into the description and break the `-z` branches."""
        for sample in (_FULL, _PARTIAL):
            assert len(_grep(_step_pattern(), sample)) == 1

    def test_no_coverable_lines_yields_nothing(self):
        """`Total:` and `Coverage:` live in the same `{% if src_stats %}`
        block, so both vanish together.  The step's two empty-value
        branches ("diff-cover failed" / "No coverable lines in diff")
        depend on that staying true."""
        assert _grep(_step_pattern(), _NO_COVERABLE_LINES) == []

    def test_workflow_does_not_parse_the_line_count(self):
        """Belt and braces: the whole failure mode was reading `Total:`."""
        assert "Total:" not in _step_pattern()
        assert "Coverage:" in _step_pattern()
