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


def test_release_skill_creates_pr_from_temporary_body_file() -> None:
    text = (REPO / ".agents/skills/writing-release-notes/SKILL.md").read_text(
        encoding="utf-8"
    )
    assert 'BODY_FILE=".release-notes-pr-body.md"' in text
    assert '--title "docs: prepare release notes for ${IDENTITY}"' in text
    assert '--head "notes/${IDENTITY}"' in text
    assert '--base "$BASE"' in text
    assert '--body-file "$BODY_FILE"' in text
    assert text.index("gh pr create \\") < text.index('rm -f "$BODY_FILE"')
    for required in (
        "claim-by-claim evidence summary",
        "breaking-change classification",
        "docs-staleness candidates",
        "anything you could not source",
    ):
        assert required in text


def test_release_skill_never_stages_temporary_body_file() -> None:
    text = (REPO / ".agents/skills/writing-release-notes/SKILL.md").read_text(
        encoding="utf-8"
    )
    output = text[text.index("## Output") :]
    assert "git add docs/releases/" in output
    assert 'git add "$BODY_FILE"' not in output
    assert "git add -A" not in output
    assert "git add .\n" not in output
    assert "Do not stage `$BODY_FILE`" in output
