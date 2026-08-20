"""Guard the pvl-core floor against its own rationale comment going stale.

`pyproject.toml.jinja` records why each floor moved in the comment block
directly above the pin.  v5.3.0 moved the pin to 4.11.2 and left the comment
opening with `>=4.11.0` (#444), so every rendered project inherited a
rationale for a floor the file no longer pinned — silent, because nothing
mechanically couples the two.

The assertion here is deliberately narrow: the FIRST line of that comment
block must name the pinned floor.  It says nothing about the prose that
follows, so the block can be reworded, extended, or have older floors' notes
trimmed without touching this test; only dropping the convention that the
lead line opens with the floor in force will fail it.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_PYPROJECT = _REPO / "pyproject.toml.jinja"

_PIN_RE = re.compile(r'^\s*"fastmcp-pvl-core>=(?P<floor>[0-9][^,"]*),')


def _pin_line_index(lines: list[str]) -> int:
    for index, line in enumerate(lines):
        if _PIN_RE.match(line):
            return index
    raise AssertionError(
        "no 'fastmcp-pvl-core>=X.Y.Z,<N' dependency line in pyproject.toml.jinja"
    )


def test_rationale_comment_leads_with_the_pinned_floor() -> None:
    lines = _PYPROJECT.read_text(encoding="utf-8").splitlines()
    pin_index = _pin_line_index(lines)
    floor = _PIN_RE.match(lines[pin_index])["floor"]

    block_start = pin_index
    while block_start > 0 and lines[block_start - 1].lstrip().startswith("#"):
        block_start -= 1
    assert block_start < pin_index, (
        f"the fastmcp-pvl-core pin (>={floor}) has no comment block above it — "
        "that block is where each floor's rationale is recorded"
    )

    lead = lines[block_start].lstrip("# ").strip()
    assert lead.startswith(f">={floor}"), (
        f"the rationale comment above the fastmcp-pvl-core pin opens with "
        f"{lead!r}, but the pin is >={floor}. Lead the block with the floor "
        f"actually pinned and why it is required, keeping the earlier floors' "
        f"rationale below it (#444)."
    )
