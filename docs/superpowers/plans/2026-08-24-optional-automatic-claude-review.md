# Optional Automatic Claude Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make automatic Claude pull-request review an opt-in Copier feature disabled by default while retaining the explicit `@claude` responder everywhere.

**Architecture:** Gate the generated automatic-review workflow through a boolean Copier answer and a conditional template path. Delete the template repository's active automatic reviewer, add disabled/enabled render coverage, and make generated guidance accurately distinguish explicit mentions from optional automation.

**Tech Stack:** Copier, Jinja, GitHub Actions YAML, pytest, PyYAML, repository render-hygiene scripts.

**Spec:** `docs/superpowers/specs/2026-08-24-agent-neutral-review-and-release-notes-design.md`

## Global Constraints

- `enable_automatic_claude_review` defaults to `false`.
- `.github/workflows/claude.yml` remains unconditional and continues to respond only to explicit `@claude` mentions.
- The template repository must not run `.github/workflows/claude-code-review.yml` automatically.
- No branch ruleset may require an agent-review check; `CI Success` remains the deterministic required check.
- Do not create a provider-neutral code-review skill in this plan; track that as a follow-up issue.
- Preserve `.claude/skills/authoring-issues-prs/`; the release-notes skill move belongs to the subsequent release-notes plan.
- Implement this plan before `2026-08-24-agent-neutral-release-notes.md` so the later plan can finalize shared secrets and release documentation.

---

### Task 1: Add The Disabled-By-Default Copier Contract

**Files:**
- Create: `scripts/tests/test_claude_review_gating.py`
- Modify: `copier.yml`
- Modify: `tests/fixtures/smoke-answers.yml`
- Rename: `.github/workflows/claude-code-review.yml.jinja` to `.github/workflows/{% if enable_automatic_claude_review %}claude-code-review.yml{% endif %}.jinja`
- Delete: `.github/workflows/claude-code-review.yml`

**Interfaces:**
- Produces: Copier answer `enable_automatic_claude_review: bool`.
- Produces: disabled render with `claude.yml` only and enabled render with both Claude workflows.
- Consumes: existing `--vcs-ref=HEAD` Copier render convention.

- [ ] **Step 1: Write the failing gating test**

Create `scripts/tests/test_claude_review_gating.py` using the existing render pattern from `scripts/tests/test_plugin_gating.py`:

```python
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
ANSWERS = REPO / "tests" / "fixtures" / "smoke-answers.yml"


def render(tmp_path: Path, enabled: bool) -> Path:
    answers = tmp_path / "answers.yml"
    text = ANSWERS.read_text(encoding="utf-8").replace(
        "enable_automatic_claude_review: false",
        f"enable_automatic_claude_review: {'true' if enabled else 'false'}",
    )
    answers.write_text(text, encoding="utf-8")
    output = tmp_path / "rendered"
    subprocess.run(
        [
            "uv", "run", "--no-project", "--with", "copier", "copier",
            "copy", "--trust", "--defaults", "--vcs-ref=HEAD",
            "--data-file", str(answers), str(REPO), str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return output


@pytest.fixture(scope="module")
def review_off(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return render(tmp_path_factory.mktemp("review-off"), enabled=False)


@pytest.fixture(scope="module")
def review_on(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return render(tmp_path_factory.mktemp("review-on"), enabled=True)


def test_answer_defaults_to_false() -> None:
    answers = yaml.safe_load((REPO / "copier.yml").read_text(encoding="utf-8"))
    assert answers["enable_automatic_claude_review"]["default"] is False


@pytest.mark.parametrize("fixture_name", ["review_off", "review_on"])
def test_explicit_claude_responder_is_always_present(
    fixture_name: str, request: pytest.FixtureRequest
) -> None:
    rendered = request.getfixturevalue(fixture_name)
    assert (rendered / ".github/workflows/claude.yml").is_file()


def test_automatic_review_is_absent_by_default(review_off: Path) -> None:
    workflows = review_off / ".github/workflows"
    assert not (workflows / "claude-code-review.yml").exists()
    assert not (workflows / ".jinja").exists()


def test_automatic_review_renders_when_enabled(review_on: Path) -> None:
    workflow = review_on / ".github/workflows/claude-code-review.yml"
    parsed = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    assert set(parsed["jobs"]) == {"wait-for-ci", "claude-review"}
    text = workflow.read_text(encoding="utf-8")
    assert "github.event.pull_request.draft == false" in text
    assert "cancel-in-progress: true" in text


def test_template_repo_has_no_active_automatic_reviewer() -> None:
    assert not (REPO / ".github/workflows/claude-code-review.yml").exists()
```

- [ ] **Step 2: Run the test to verify the option is absent**

Run:

```bash
uv run --no-project --with pytest --with pyyaml --with copier pytest -q scripts/tests/test_claude_review_gating.py
```

Expected: FAIL because `enable_automatic_claude_review` is absent and the automatic workflow is unconditional.

- [ ] **Step 3: Add the answer and conditional path**

Add beside the other feature toggles in `copier.yml`:

```yaml
enable_automatic_claude_review:
  type: bool
  default: false
  help: "Include automatic Claude pull-request review after CI passes. Leave off to keep agent review human-triggered through @claude only."
```

Add the explicit smoke answer:

```yaml
enable_automatic_claude_review: false
```

Rename the Jinja workflow to the complete conditional destination path and delete the plain active `.github/workflows/claude-code-review.yml`. Do not alter either `.github/workflows/claude.yml` file.

- [ ] **Step 4: Commit the template-path change before rendering**

Copier reads the git index for `--vcs-ref=HEAD`, so make the task's implementation commit before rerunning render tests:

```bash
git add copier.yml tests/fixtures/smoke-answers.yml scripts/tests/test_claude_review_gating.py .github/workflows
git commit -m "feat(review): make automatic Claude review opt-in"
```

- [ ] **Step 5: Run the gating test to verify both variants**

Run:

```bash
uv run --no-project --with pytest --with pyyaml --with copier pytest -q scripts/tests/test_claude_review_gating.py
```

Expected: PASS with six test cases and no stray `.jinja` output.

### Task 2: Cover Both Variants In Template CI

**Files:**
- Modify: `.github/workflows/template-ci.yml`

**Interfaces:**
- Consumes: `enable_automatic_claude_review` from Task 1.
- Produces: `/tmp/smoke-claude-review-on` render before hygiene checking.
- Produces: structural assertions against the enabled workflow only.

- [ ] **Step 1: Add the enabled render before the hygiene step**

Use the same render command as the default smoke project, adding only:

```yaml
- name: Render automatic-review variant
  run: |
    rm -rf /tmp/smoke-claude-review-on
    uv run --no-project --with copier copier copy --trust --defaults \
      --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml \
      --data enable_automatic_claude_review=true \
      . /tmp/smoke-claude-review-on
```

Add `/tmp/smoke-claude-review-on` to the existing `scripts/check_render_hygiene.py` argument list.

- [ ] **Step 2: Add the presence matrix and retarget review assertions**

Add one shell step with these exact checks:

```bash
test -f /tmp/smoke/.github/workflows/claude.yml
test ! -e /tmp/smoke/.github/workflows/claude-code-review.yml
test ! -e /tmp/smoke/.github/workflows/.jinja
test -f /tmp/smoke-claude-review-on/.github/workflows/claude.yml
test -f /tmp/smoke-claude-review-on/.github/workflows/claude-code-review.yml
test ! -e /tmp/smoke-claude-review-on/.github/workflows/.jinja
```

Retarget the existing draft-gate and per-commit concurrency greps around the `claude-code-review draft gate and per-commit concurrency` step from `/tmp/smoke` to `/tmp/smoke-claude-review-on`.

- [ ] **Step 3: Update detach-smoke wording without weakening cleanup**

Keep `claude-code-review.yml` in detach smoke's idempotent `rm -f` list so an opted-in downstream removes it. Change assertions and comments that call it unconditional to call it optional.

- [ ] **Step 4: Parse template CI and run its focused static checks**

Run:

```bash
uv run --no-project --with pyyaml python -c "import yaml; yaml.safe_load(open('.github/workflows/template-ci.yml')); print('template-ci YAML OK')"
uv run --no-project --with pytest --with pyyaml --with copier pytest -q scripts/tests/test_claude_review_gating.py
```

Expected: YAML parse succeeds and the gating tests pass.

- [ ] **Step 5: Commit the CI variant**

```bash
git add .github/workflows/template-ci.yml
git commit -m "test(review): cover automatic review render variants"
```

### Task 3: Make Generated Guidance Conditional And Migration-Safe

**Files:**
- Modify: `CLAUDE.md.jinja`
- Modify: `README.md.jinja`
- Modify: `FORKING.md.jinja`
- Modify: `UPGRADING.md`
- Modify: `copier.yml`

**Interfaces:**
- Consumes: `enable_automatic_claude_review` from Task 1.
- Produces: truthful guidance in both renders.
- Preserves: release-notes workflow/token wording until the subsequent release-notes plan removes that workflow.

- [ ] **Step 1: Make automatic-review prose conditional**

In `CLAUDE.md.jinja`, always document explicit `@claude` mentions. Wrap only the automatic-review paragraph in:

```jinja
{% if enable_automatic_claude_review %}
Automatic Claude review runs after deterministic CI passes. It is advisory and
is not a required ruleset check.
{% else %}
Automatic agent review is disabled. Request Claude selectively with an
`@claude` mention; deterministic CI remains the merge gate.
{% endif %}
```

Keep the existing `TEMPLATE-TRACKING` marker pair in both variants so detach marker counts do not change.

- [ ] **Step 2: Correct secrets and forking prose for the transitional state**

In `README.md.jinja`, mark `claude-code-review.yml` optional but retain `release-notes.yml` as a `CLAUDE_CODE_OAUTH_TOKEN` consumer until the next plan deletes it. In `FORKING.md.jinja`, distinguish the explicit mention responder from the optional automatic reviewer while retaining both in the idempotent detach command.

- [ ] **Step 3: Add the upgrade instructions under the existing Unreleased section**

Replace `_Nothing yet._` under `## Unreleased` with instructions containing this exact answer:

```yaml
enable_automatic_claude_review: true
```

State that the default is now off, `@claude` remains available, and any independently configured required Claude-review check must be removed when automatic review is disabled. Do not add a guessed version heading.

- [ ] **Step 4: Update Copier ownership commentary**

Document that the conditional review workflow remains template-owned and that disabling it removes the generated file. Do not move or reclassify either skill tree in this task.

- [ ] **Step 5: Commit and render both prose variants**

```bash
git add CLAUDE.md.jinja README.md.jinja FORKING.md.jinja UPGRADING.md copier.yml
git commit -m "docs(review): explain optional automatic review"
rm -rf /tmp/smoke /tmp/smoke-claude-review-on
uv run --no-project --with copier copier copy --trust --defaults --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
uv run --no-project --with copier copier copy --trust --defaults --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml --data enable_automatic_claude_review=true . /tmp/smoke-claude-review-on
python3 scripts/check_render_hygiene.py /tmp/smoke /tmp/smoke-claude-review-on
python3 scripts/promote_upgrading.py --check
```

Expected: both renders are hygiene-clean and the upgrading check reports a single final `## Unreleased` section.

- [ ] **Step 6: Run Vale against both generated prose variants**

Run `vale sync` once in each fresh render, then:

```bash
vale --glob='!docs/{superpowers,design,decisions}/**' docs README.md
```

Expected: zero Vale findings in both renders.

### Task 4: Verify Rulesets, Update Behavior, And The Generated Gate

**Files:**
- Modify: `scripts/check_update_regression.py`
- Test: `scripts/tests/test_ruleset_required_checks.py`

**Interfaces:**
- Verifies: older downstreams lose automatic review by default and preserve it when the answer is true.
- Verifies: branch protection requires deterministic CI, not an agent check.

- [ ] **Step 1: Extend the existing old-render update regression**

Add this helper to `scripts/check_update_regression.py` and call it immediately after the real `copier update` at line 135:

```python
def _assert_review_workflow_default(project: Path) -> None:
    workflows = project / ".github" / "workflows"
    if (workflows / "claude-code-review.yml").exists():
        raise SystemExit(
            "ERROR: copier update retained automatic Claude review despite "
            "enable_automatic_claude_review defaulting to false"
        )
    if not (workflows / "claude.yml").is_file():
        raise SystemExit("ERROR: copier update removed the explicit @claude responder")
```

The existing v3.0.2 fixture predates the answer and contains the formerly unconditional workflow, so this proves the migration's default removal path. Task 1's enabled fresh-render test proves the opt-in path.

- [ ] **Step 2: Run update and ruleset checks**

```bash
python3 scripts/check_update_regression.py
uv run --no-project --with pytest --with pyyaml --with jinja2 pytest -q scripts/tests/test_ruleset_required_checks.py scripts/tests/test_claude_review_gating.py
```

Expected: the old unconditional workflow is removed on update, `claude.yml` remains, and default rulesets contain only `CI Success` unless `extra_required_checks` adds project-owned contexts.

- [ ] **Step 3: Run the generated project gate**

From `/tmp/smoke`:

```bash
uv sync --all-extras --all-groups
uv run ruff check .
uv run ruff format --check .
uv run mypy src/ tests/
uv run pytest -x -q
uv run mkdocs build --strict
```

Expected: all commands exit zero.

- [ ] **Step 4: Commit any update-regression changes**

```bash
git add scripts/check_update_regression.py scripts/tests/test_ruleset_required_checks.py
git commit -m "test(review): verify Copier update behavior"
```

Skip this commit when neither file needed a change.

### Task 5: Track The Provider-Neutral Review Skill Separately

**Files:**
- No repository files; creates one GitHub issue.

**Interfaces:**
- Consumes: the completed optional-review implementation and approved design spec.
- Produces: one follow-up issue; does not add `.agents/skills/code-review/` in this change.

- [ ] **Step 1: Load the repository's issue-authoring skill**

Invoke `.claude/skills/authoring-issues-prs/SKILL.md` and follow its repository routing, issue-form, labeling, and duplicate-search rules before posting.

- [ ] **Step 2: Search for an existing equivalent issue**

```bash
gh issue list --state all --search 'provider-neutral code review skill in:title' --json number,title,state,url
```

Expected: either one existing issue to reuse, or no equivalent issue.

- [ ] **Step 3: Create the follow-up when none exists**

Use the issue form selected by the authoring skill with title:

```text
design(review): provider-neutral local code-review skill
```

The body must define this scope:

```markdown
## Goal

Ship a human-invoked code-review skill that works with a coding agent chosen by
the contributor and has no dependency on Claude, a hosted model workflow, or
model credits.

## Contract to design

- Select the cumulative pull-request diff and relevant repository guidance.
- Require source-backed findings with file and line references.
- Define severity and confidence conventions.
- Permit targeted verification without rerunning deterministic CI wholesale.
- Refuse to overwrite unrelated working-tree changes.
- Produce review findings suitable for a pull-request review or comment.

## Out of scope

- Reintroducing a required hosted-agent check.
- Choosing one model provider.
- Changing deterministic CI or branch-protection requirements.
```

- [ ] **Step 4: Verify and record the issue URL**

```bash
gh issue list --state open --search 'provider-neutral local code-review skill in:title' --json number,title,url
```

Expected: exactly one open tracking issue. Include its URL in the implementation handoff.
