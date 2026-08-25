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


def test_release_skill_branches_from_fresh_remote_base_and_rechecks_it() -> None:
    text = (REPO / ".agents/skills/writing-release-notes/SKILL.md").read_text(
        encoding="utf-8"
    )
    output = text[text.index("## Output") :]

    fetch = 'git fetch origin "+refs/heads/${BASE}:refs/remotes/origin/${BASE}"'
    fetch_at = output.index(fetch)
    switch_at = output.index('git switch --create "$BRANCH" --no-track "origin/$BASE"')
    final_fetch_at = output.index(fetch, fetch_at + 1)
    ancestry_at = output.index(
        'git merge-base --is-ancestor "origin/$BASE" HEAD', final_fetch_at
    )
    push_at = output.index('git push --set-upstream origin "$BRANCH"')

    assert fetch_at < switch_at < final_fetch_at < ancestry_at < push_at
    assert 'git switch -c "$BRANCH"' not in output


def test_release_skill_reviews_staged_and_cumulative_diffs_before_push() -> None:
    text = (REPO / ".agents/skills/writing-release-notes/SKILL.md").read_text(
        encoding="utf-8"
    )
    output = text[text.index("## Output") :]
    commit_at = output.index(
        'git commit -m "docs: prepare release notes for ${IDENTITY}"'
    )
    push_at = output.index('git push --set-upstream origin "$BRANCH"')

    assert output.index("git diff --cached --check") < commit_at
    assert (
        output.index("git diff --cached", output.index("git diff --cached --check") + 1)
        < commit_at
    )
    assert output.index('git diff "origin/$BASE...HEAD" --check') < push_at
    assert output.index('git diff "origin/$BASE...HEAD"', commit_at) < push_at


def test_release_skill_treats_github_prose_as_untrusted_before_publication() -> None:
    text = (REPO / ".agents/skills/writing-release-notes/SKILL.md").read_text(
        encoding="utf-8"
    )
    prose = " ".join(text.split()).lower()

    for required in (
        "untrusted data",
        "issue and pull-request bodies and comments",
        "embedded instructions",
        "human confirmation",
        "credentialed publication",
    ):
        assert required in prose
