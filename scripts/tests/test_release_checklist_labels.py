"""The release page's three fixed lines are named identically in the two places that promise them.

`docs/upgrade/index.md` tells readers which labels a release page's Upgrading
section carries; the `writing-release-notes` skill tells the author to write
them. A label that drifts in one place sends readers looking for text the
other place never produces.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LABELS = ("**Clients:**", "**State:**", "**Security posture:**")
PLACES = (
    ROOT / "docs" / "upgrade" / "index.md.jinja",
    ROOT / ".agents" / "skills" / "writing-release-notes" / "SKILL.md",
)


def test_every_label_appears_in_both_places() -> None:
    for place in PLACES:
        text = place.read_text(encoding="utf-8")
        missing = [label for label in LABELS if label not in text]
        assert not missing, f"{place.relative_to(ROOT)} lacks {missing}"
