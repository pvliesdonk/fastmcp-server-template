"""Template-owned contributor skills live under .agents/skills/ (portable) and
are reachable by Claude Code through .claude/skills/<name> symlinks (#486)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import migrate_agent_instructions as mig

REPO = Path(__file__).resolve().parents[2]
AGENTS_SKILLS = REPO / ".agents" / "skills"
CLAUDE_SKILLS = REPO / ".claude" / "skills"
TEMPLATE_SKILLS = (
    "authoring-issues-prs",
    "config-contract",
    "logging-standard",
    "releasing",
    "repository-protection",
    "tool-registration",
    "writing-release-notes",
)
_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def _skill_file(name: str) -> Path:
    d = AGENTS_SKILLS / name
    for candidate in (d / "SKILL.md.jinja", d / "SKILL.md"):
        if candidate.is_file():
            return candidate
    raise AssertionError(f"{name}: no SKILL.md(.jinja) under .agents/skills/")


@pytest.mark.parametrize("name", TEMPLATE_SKILLS)
def test_skill_is_portable_and_symlinked(name: str) -> None:
    _skill_file(name)
    link = CLAUDE_SKILLS / name
    assert link.is_symlink(), f".claude/skills/{name} must be a symlink"
    assert link.readlink() == Path(f"../../.agents/skills/{name}"), link.readlink()
    assert link.resolve() == (AGENTS_SKILLS / name).resolve()


@pytest.mark.parametrize("name", TEMPLATE_SKILLS)
def test_skill_frontmatter(name: str) -> None:
    text = _skill_file(name).read_text(encoding="utf-8")
    m = _FRONTMATTER.match(text)
    assert m, f"{name}: SKILL.md lacks YAML frontmatter"
    fm = m.group(1)
    assert re.search(rf"^name: {re.escape(name)}$", fm, re.MULTILINE), (
        f"{name}: name must equal dir"
    )
    assert re.search(r"^description: \S", fm, re.MULTILINE), (
        f"{name}: description missing"
    )


def test_no_real_directories_under_claude_skills() -> None:
    real = [
        p.name for p in CLAUDE_SKILLS.iterdir() if p.is_dir() and not p.is_symlink()
    ]
    assert not real, (
        f"real directories under .claude/skills/ (must be symlinks): {real}"
    )


def test_every_agents_skill_has_a_symlink() -> None:
    missing = [
        p.name
        for p in AGENTS_SKILLS.iterdir()
        if p.is_dir() and not (CLAUDE_SKILLS / p.name).is_symlink()
    ]
    assert not missing, f"skills without a .claude/skills symlink: {missing}"


def test_gitignore_keeps_both_skill_roots() -> None:
    for path in (REPO / ".gitignore", REPO / ".gitignore.jinja"):
        text = path.read_text(encoding="utf-8")
        assert "!.agents/skills/" in text, path
        assert "!.claude/skills/" in text, path


def test_release_skill_uses_neutral_path() -> None:
    assert (REPO / ".agents/skills/writing-release-notes/SKILL.md").is_file()
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
    assert '--head "$BRANCH"' in text
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


def test_release_skill_uses_a_fresh_branch_name_for_each_pr() -> None:
    text = (REPO / ".agents/skills/writing-release-notes/SKILL.md").read_text(
        encoding="utf-8"
    )
    output = text[text.index("## Output") :]

    assert 'BRANCH_STEM="notes/${IDENTITY}-$(date -u +%Y%m%d%H%M%S)"' in output
    assert 'git show-ref --verify --quiet "refs/heads/$BRANCH"' in output
    assert 'git ls-remote --exit-code --heads origin "$BRANCH"' in output
    assert 'BRANCH="${BRANCH_STEM}-${suffix}"' in output
    assert '--head "$BRANCH"' in output
    assert 'BRANCH="notes/${IDENTITY}"' not in output


def test_next_notes_are_an_explicit_mkdocs_only_exclusion() -> None:
    workflow = (REPO / ".github/workflows/template-ci.yml").read_text(encoding="utf-8")
    mkdocs = (REPO / "mkdocs.yml.jinja").read_text(encoding="utf-8")

    assert "releases/next.md" in mkdocs
    assert 'MK_VALE_EXCEPTIONS="releases/next.md"' in workflow
    assert 'grep -vFx "$MK_VALE_EXCEPTIONS"' in workflow
    assert "next.md is intentionally Vale-linted" in workflow


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


def test_template_skills_list_matches_migration_script() -> None:
    assert mig.TEMPLATE_SKILLS == TEMPLATE_SKILLS, (
        "TEMPLATE_SKILLS drifted between scripts/migrate_agent_instructions.py "
        f"{mig.TEMPLATE_SKILLS} and scripts/tests/test_shared_skill_paths.py "
        f"{TEMPLATE_SKILLS} -- keep the two tuples identical"
    )


def test_template_skills_list_matches_rendered_test_file() -> None:
    text = (REPO / "tests" / "test_agent_instructions.py").read_text(encoding="utf-8")
    match = re.search(
        r"TEMPLATE_SKILLS: tuple\[str, \.\.\.\] = \((.*?)\)", text, re.DOTALL
    )
    assert match, (
        "could not find a 'TEMPLATE_SKILLS: tuple[str, ...] = (...)' literal in "
        "tests/test_agent_instructions.py"
    )
    names = tuple(re.findall(r'"([^"]+)"', match.group(1)))
    assert names == TEMPLATE_SKILLS, (
        "TEMPLATE_SKILLS drifted between scripts/tests/test_shared_skill_paths.py "
        f"{TEMPLATE_SKILLS} and tests/test_agent_instructions.py {names} -- keep the "
        "skill-name list identical in both places"
    )


def test_template_skills_list_matches_copier_before_stage_migration() -> None:
    config = yaml.safe_load((REPO / "copier.yml").read_text(encoding="utf-8"))
    before_stage = [
        m
        for m in config["_migrations"]
        if isinstance(m, dict) and "before" in m.get("when", "")
    ]
    assert len(before_stage) == 1, (
        "expected exactly one before-stage _migrations entry in copier.yml, "
        f"found {len(before_stage)}"
    )
    command = before_stage[0]["command"]
    match = re.search(r"for \w+ in (.+?);\s*do", command)
    assert match, (
        "could not find a 'for X in ...; do' clause in copier.yml's before-stage "
        f"migration command: {command!r}"
    )
    names = frozenset(match.group(1).split())
    assert names == frozenset(TEMPLATE_SKILLS), (
        "TEMPLATE_SKILLS drifted between scripts/tests/test_shared_skill_paths.py "
        f"{sorted(TEMPLATE_SKILLS)} and copier.yml's before-stage migration command "
        f"{sorted(names)} -- keep the skill-name list identical in both places"
    )
