from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_release_skill_uses_neutral_path() -> None:
    assert (REPO / ".agents/skills/writing-release-notes/SKILL.md").is_file()
    assert not (REPO / ".claude/skills/writing-release-notes/SKILL.md").exists()
    assert (REPO / ".claude/skills/authoring-issues-prs/SKILL.md").is_file()


def test_ignore_rules_preserve_both_skill_roots() -> None:
    for name in (".gitignore", ".gitignore.jinja"):
        text = (REPO / name).read_text(encoding="utf-8")
        assert ".agents/*" in text
        assert "!.agents/skills/" in text
        assert ".claude/*" in text
        assert "!.claude/skills/" in text
