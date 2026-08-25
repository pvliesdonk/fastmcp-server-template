"""The after-stage copier migration that moves a downstream from CLAUDE.md to
AGENTS.md without a human step (spec §4)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import migrate_agent_instructions as mig

REPO = Path(__file__).resolve().parents[2]

PLACEHOLDER = "<!-- DOMAIN-START -->\n<!-- Describe your service's design here. Kept across copier update. -->\n<!-- DOMAIN-END -->\n"
FILLED = "<!-- DOMAIN-START -->\nReal design prose.\n\n- bullet\n<!-- DOMAIN-END -->\n"
AGENTS_FRESH = (
    "# X\n\n## Design\n"
    + PLACEHOLDER
    + "\n## Project Structure\n"
    + PLACEHOLDER
    + "\n## Key Design Decisions\n"
    + PLACEHOLDER
)
HEAD_CLAUDE = (
    "# X\n\n## Design\n"
    + FILLED
    + "\n## Project Structure\n"
    + PLACEHOLDER
    + "\n## Key Design Decisions\n"
    + FILLED.replace("Real", "Decision")
)


def _project(
    tmp_path: Path,
    *,
    agents: str = AGENTS_FRESH,
    claude: str = "<<<<<<< before updating\nold\n=======\nnew\n>>>>>>> after updating\n",
) -> Path:
    (tmp_path / "AGENTS.md").write_text(agents, encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text(claude, encoding="utf-8")
    (tmp_path / ".agents" / "skills" / "releasing").mkdir(parents=True)
    (tmp_path / ".agents" / "skills" / "releasing" / "SKILL.md").write_text(
        "---\nname: releasing\n---\n"
    )
    (tmp_path / ".claude" / "skills").mkdir(parents=True)
    return tmp_path


def test_is_placeholder_recognises_the_seeded_comment() -> None:
    assert mig.is_placeholder(
        "<!-- Describe your service's design here. Kept across copier update. -->\n"
    )
    assert mig.is_placeholder("\n  \n")
    assert not mig.is_placeholder("Real prose\n")


def test_splice_moves_only_filled_blocks_into_empty_ones() -> None:
    out, moved = mig.splice(AGENTS_FRESH, HEAD_CLAUDE)
    assert moved == 2
    blocks = mig.domain_blocks(out)
    assert "Real design prose." in blocks[0]
    assert mig.is_placeholder(blocks[1])
    assert "Decision design prose." in blocks[2]


def test_splice_never_overwrites_a_filled_agents_block() -> None:
    already = AGENTS_FRESH.replace(PLACEHOLDER, FILLED.replace("Real", "Kept"), 1)
    out, moved = mig.splice(already, HEAD_CLAUDE)
    assert moved == 1  # only Key Design Decisions
    assert "Kept design prose." in mig.domain_blocks(out)[0]


def test_migrate_rewrites_stub_and_replaces_real_skill_dir(tmp_path: Path) -> None:
    root = _project(tmp_path)
    real = root / ".claude" / "skills" / "releasing"
    real.mkdir()
    (real / "SKILL.md").write_text("stale copy")
    actions = mig.migrate(root, head_claude=HEAD_CLAUDE)
    assert (root / "CLAUDE.md").read_text(encoding="utf-8") == mig.STUB
    assert "Real design prose." in (root / "AGENTS.md").read_text(encoding="utf-8")
    link = root / ".claude" / "skills" / "releasing"
    assert (
        link.is_symlink() and str(link.readlink()) == "../../.agents/skills/releasing"
    )
    assert any("git show HEAD:CLAUDE.md" in a for a in actions)


def test_migrate_is_idempotent(tmp_path: Path) -> None:
    root = _project(tmp_path)
    mig.migrate(root, head_claude=HEAD_CLAUDE)
    after_first = (root / "AGENTS.md").read_text(encoding="utf-8")
    actions = mig.migrate(root, head_claude=HEAD_CLAUDE)
    assert (root / "AGENTS.md").read_text(encoding="utf-8") == after_first
    assert not any("spliced" in a for a in actions)


def test_migrate_noop_without_head_claude_or_agents(tmp_path: Path) -> None:
    assert mig.migrate(tmp_path, head_claude=None) == []
    (tmp_path / "CLAUDE.md").write_text("x")
    assert mig.migrate(tmp_path, head_claude="no blocks here") == []


def test_stub_matches_the_template() -> None:
    # CLAUDE.md.jinja has no Jinja in it, so its bytes ARE the render.
    assert (REPO / "CLAUDE.md.jinja").read_text(encoding="utf-8") == mig.STUB
