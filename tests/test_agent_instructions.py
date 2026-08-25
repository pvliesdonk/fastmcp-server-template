"""Agent-instruction surface contract (template-owned).

AGENTS.md is the single always-loaded instruction file every coding agent
reads; CLAUDE.md is a stub importing it; skills live under .agents/skills/
with .claude/skills/ symlinks for Claude Code.  Claude Code warns above
40 000 characters of always-loaded instructions, and the template owns
~20k of AGENTS.md, so the DOMAIN blocks are the lever when this fails.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENTS_LIMIT = 40_000
STUB = (
    "@AGENTS.md\n\nProject instructions live in `AGENTS.md` (domain content between its "
    "`DOMAIN-START` / `DOMAIN-END` markers). This file is template-owned; do not add content here.\n"
)


def test_agents_md_within_always_loaded_budget() -> None:
    size = len((REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8"))
    assert size <= AGENTS_LIMIT, (
        f"AGENTS.md is {size} chars; Claude Code degrades above {AGENTS_LIMIT}. "
        "Trim the DOMAIN blocks (move detail into docs/ or a project skill under "
        ".agents/skills/) — the template-owned sections are budgeted separately."
    )


def test_claude_md_is_the_stub() -> None:
    assert (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8") == STUB, (
        "CLAUDE.md is template-owned and must stay the @AGENTS.md stub; put content in AGENTS.md"
    )


def test_claude_skill_links_resolve_into_agents_skills() -> None:
    claude_skills = REPO_ROOT / ".claude" / "skills"
    agents_skills = (REPO_ROOT / ".agents" / "skills").resolve()
    for entry in claude_skills.iterdir():
        assert entry.is_symlink(), f"{entry} must be a symlink into .agents/skills/"
        assert entry.resolve().parent == agents_skills, entry
        assert (entry / "SKILL.md").is_file(), f"{entry} does not resolve to a SKILL.md"
