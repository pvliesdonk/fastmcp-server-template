# Agent-Neutral Release Notes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace headless Claude release-note drafting with a human-invoked provider-neutral skill and deterministic promotion of a reviewed `docs/releases/next.md` artifact.

**Architecture:** A template-owned Python script validates and promotes `next.md` after knope computes the version and before it commits the release preparation. Release candidates normalize to their eventual stable identity, existing notes satisfy later candidates, and the knope pull request leaves freshness assessment to human review. The hosted drafting workflow, draft hold, and model-token release dependency are removed.

**Tech Stack:** Python 3.11+, pathlib, dataclasses, subprocess with fixed argv, Copier/Jinja, knope, GitHub Actions YAML, pytest, Vale, MkDocs.

**Spec:** `docs/superpowers/specs/2026-08-24-agent-neutral-review-and-release-notes-design.md`

## Global Constraints

- Implement `2026-08-24-optional-automatic-claude-review.md` first.
- Every target stable identity must have exactly one `RELEASE-SUMMARY vX.Y.Z` block; Release Prepare has no bypass.
- `vX.Y.Z-rc.N` and `vX.Y.Z` share the `vX.Y.Z` notes identity.
- Existing target notes plus absent `next.md` is a valid no-op; automation never gates on watermark freshness.
- Target notes plus `next.md`, or neither target notes nor `next.md`, must refuse preparation.
- Validate all release-note inputs and compute all output text before replacing or deleting any file.
- Patch release headings are undated.
- Agent-authored prose reaches the repository only through an ordinary pull request.
- Keep `.github/workflows/release-notes-publish.yml`; remove only the content-generating `.github/workflows/release-notes.yml.jinja`.
- Preserve `.claude/skills/authoring-issues-prs/` while moving only the release-notes skill to `.agents/skills/`.

---

### Task 1: Build The Pure Promotion State Machine

**Files:**
- Create: `scripts/promote_release_notes.py`
- Create: `tests/test_promote_release_notes.py`

**Interfaces:**
- Produces: `PromotionError(ValueError)` for deterministic refusals.
- Produces: `Target(version: str, tag: str, minor: str, page: Path)`.
- Produces: `PromotionPlan(root: Path, writes: dict[Path, str], deletes: tuple[Path, ...], stage_paths: tuple[Path, ...])`; writes/deletes are absolute beneath `root`, while stage paths are repository-relative.
- Produces: `normalize_target(version: str) -> Target`.
- Produces: `plan_promotion(root: Path, version: str) -> PromotionPlan`.
- Later tasks consume `apply_plan(plan: PromotionPlan) -> None` and `main(argv: Sequence[str] | None = None) -> int`.

- [ ] **Step 1: Write failing version and four-state tests**

Start `tests/test_promote_release_notes.py` by importing the copied script as a normal module and creating helpers with concrete valid content:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.promote_release_notes import PromotionError, normalize_target, plan_promotion

NEXT = """# Next release

<!-- notes-range-end: 0123456789abcdef0123456789abcdef01234567 -->

<!-- RELEASE-SUMMARY NEXT START -->
Operators can now rotate credentials without restarting the server.
<!-- RELEASE-SUMMARY NEXT END -->

## Credential rotation

The server reloads credentials after the configured interval ([#42](https://github.com/example/project/issues/42)).
"""

INDEX = """# Release Notes

<!-- RELEASE-PAGES-START: newest series first; one list entry per page.
     The first real entry replaces the placeholder line below. -->
No release pages yet. The first entry appears with the first stable
release cut after this project adopted release-notes pages.
<!-- RELEASE-PAGES-END -->
"""


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def canonical(tag: str = "v2.4.0") -> str:
    return f"""# 2.4

<!-- notes-range-end: 1111111111111111111111111111111111111111 -->

<!-- RELEASE-SUMMARY {tag} START -->
Existing reviewed summary.
<!-- RELEASE-SUMMARY {tag} END -->

## Existing theme

Existing evidence.

<!-- PATCH-RELEASES-START -->
<!-- PATCH-RELEASES-END -->
"""


@pytest.mark.parametrize(
    ("version", "tag", "minor"),
    [
        ("2.4.0", "v2.4.0", "2.4"),
        ("v2.4.0", "v2.4.0", "2.4"),
        ("2.4.0-rc.3", "v2.4.0", "2.4"),
    ],
)
def test_normalize_target(version: str, tag: str, minor: str) -> None:
    target = normalize_target(version)
    assert (target.tag, target.minor, target.page) == (
        tag,
        minor,
        Path("docs/releases/2.4.md"),
    )


def test_target_present_without_next_is_a_noop(tmp_path: Path) -> None:
    write(tmp_path / "docs/releases/2.4.md", canonical())
    plan = plan_promotion(tmp_path, "2.4.0-rc.2")
    assert plan.writes == {}
    assert plan.deletes == ()
    assert plan.stage_paths == ()


def test_missing_target_with_next_plans_promotion(tmp_path: Path) -> None:
    write(tmp_path / "docs/releases/next.md", NEXT)
    write(tmp_path / "docs/releases/index.md", INDEX)
    plan = plan_promotion(tmp_path, "2.4.0-rc.1")
    assert tmp_path / "docs/releases/2.4.md" in plan.writes
    assert plan.deletes == (tmp_path / "docs/releases/next.md",)


def test_missing_target_and_next_refuses(tmp_path: Path) -> None:
    with pytest.raises(PromotionError, match="no reviewed release notes"):
        plan_promotion(tmp_path, "2.4.0")


def test_target_and_next_together_refuse(tmp_path: Path) -> None:
    write(tmp_path / "docs/releases/2.4.md", canonical())
    write(tmp_path / "docs/releases/next.md", NEXT)
    with pytest.raises(PromotionError, match="ambiguous"):
        plan_promotion(tmp_path, "2.4.0-rc.2")
```

- [ ] **Step 2: Run the focused tests to verify the module is missing**

```bash
uv run --no-project --with pytest pytest tests/test_promote_release_notes.py -x -q
```

Expected: collection FAIL because `scripts.promote_release_notes` does not exist.

- [ ] **Step 3: Implement target normalization and immutable plans**

Create `scripts/promote_release_notes.py` with these exact public types and validation boundary:

```python
from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

VERSION_RE = re.compile(r"^v?(?P<major>0|[1-9][0-9]*)\.(?P<minor>0|[1-9][0-9]*)\.(?P<patch>0|[1-9][0-9]*)(?:-rc\.(?P<rc>[1-9][0-9]*))?$")
WATERMARK_RE = re.compile(r"<!-- notes-range-end: ([0-9a-f]{40}) -->")


class PromotionError(ValueError):
    """Release notes cannot be promoted without human correction."""


@dataclass(frozen=True)
class Target:
    version: str
    tag: str
    minor: str
    page: Path


@dataclass(frozen=True)
class PromotionPlan:
    root: Path
    writes: dict[Path, str]
    deletes: tuple[Path, ...]
    stage_paths: tuple[Path, ...]


def normalize_target(version: str) -> Target:
    match = VERSION_RE.fullmatch(version)
    if match is None:
        raise PromotionError(
            f"invalid release version {version!r}; expected X.Y.Z or X.Y.Z-rc.N"
        )
    stable = f"{match['major']}.{match['minor']}.{match['patch']}"
    minor = f"{match['major']}.{match['minor']}"
    return Target(stable, f"v{stable}", minor, Path(f"docs/releases/{minor}.md"))
```

Implement `plan_promotion` as a pure function: resolve all paths beneath `root`, count complete target START/END marker pairs, apply the four-state table before parsing staging, and return a no-op plan for the existing-target state. Do not write, delete, stage, or invoke git in this function.

- [ ] **Step 4: Implement strict staging parsing**

Use exact-count helpers rather than permissive `str.replace`:

```python
def require_once(text: str, token: str, label: str) -> None:
    count = text.count(token)
    if count != 1:
        raise PromotionError(f"{label} must occur exactly once; found {count}")


def validate_next(text: str) -> str:
    lines = text.splitlines()
    if not lines or lines[0] != "# Next release":
        raise PromotionError("next.md must start with '# Next release'")
    if len(WATERMARK_RE.findall(text)) != 1:
        raise PromotionError("next.md must contain exactly one 40-hex watermark")
    require_once(text, "<!-- RELEASE-SUMMARY NEXT START -->", "NEXT summary start")
    require_once(text, "<!-- RELEASE-SUMMARY NEXT END -->", "NEXT summary end")
    summary = text.split("<!-- RELEASE-SUMMARY NEXT START -->", 1)[1].split(
        "<!-- RELEASE-SUMMARY NEXT END -->", 1
    )[0].strip()
    if not summary:
        raise PromotionError("NEXT summary must not be empty")
    return text
```

- [ ] **Step 5: Run the state tests**

```bash
uv run --no-project --with pytest pytest tests/test_promote_release_notes.py -x -q
```

Expected: the seven normalization and state-machine cases shown in Step 1 pass. Task 2 adds the detailed content and formatting tests afterward.

- [ ] **Step 6: Commit the pure state machine**

```bash
git add scripts/promote_release_notes.py tests/test_promote_release_notes.py
git commit -m "feat(release): define release-notes promotion states"
```

### Task 2: Implement New-Page And Patch Promotion

**Files:**
- Modify: `scripts/promote_release_notes.py`
- Modify: `tests/test_promote_release_notes.py`

**Interfaces:**
- Consumes: `Target`, `PromotionPlan`, and strict staging parser from Task 1.
- Produces: `promote_new_page(root: Path, target: Target, next_text: str, index_text: str) -> PromotionPlan`.
- Produces: `promote_patch_page(root: Path, target: Target, next_text: str, page_text: str) -> PromotionPlan`.
- Produces: `shift_headings(text: str, levels: int = 1) -> str` with fenced-code awareness.

- [ ] **Step 1: Add failing new-series tests**

Add assertions covering the complete promoted page and index behavior:

```python
def test_new_minor_page_promotion(tmp_path: Path) -> None:
    write(tmp_path / "docs/releases/next.md", NEXT)
    write(tmp_path / "docs/releases/index.md", INDEX)
    plan = plan_promotion(tmp_path, "2.4.0-rc.1")
    page = plan.writes[tmp_path / "docs/releases/2.4.md"]
    assert page.startswith("# 2.4\n")
    assert "RELEASE-SUMMARY v2.4.0 START" in page
    assert "RELEASE-SUMMARY NEXT" not in page
    assert page.endswith(
        "<!-- PATCH-RELEASES-START -->\n<!-- PATCH-RELEASES-END -->\n"
    )
    index = plan.writes[tmp_path / "docs/releases/index.md"]
    assert "- [2.4](2.4.md)" in index
    assert "No release pages yet" not in index


def test_duplicate_target_summary_refuses(tmp_path: Path) -> None:
    duplicate = canonical() + canonical()
    write(tmp_path / "docs/releases/2.4.md", duplicate)
    with pytest.raises(PromotionError, match="target summary"):
        plan_promotion(tmp_path, "2.4.0")
```

Add a second index fixture with `- [2.3](2.3.md)` and assert the new `2.4` entry appears immediately after the multiline START comment and before `2.3`.

- [ ] **Step 2: Add failing patch and fenced-heading tests**

```python
def test_patch_section_is_inserted_before_patch_end(tmp_path: Path) -> None:
    write(tmp_path / "docs/releases/2.4.md", canonical("v2.4.0"))
    write(tmp_path / "docs/releases/next.md", NEXT)
    plan = plan_promotion(tmp_path, "2.4.1-rc.1")
    page = plan.writes[tmp_path / "docs/releases/2.4.md"]
    assert "## v2.4.1\n" in page
    assert "### Credential rotation\n" in page
    assert page.index("## v2.4.1") < page.index("<!-- PATCH-RELEASES-END -->")
    assert "notes-range-end: 0123456789abcdef0123456789abcdef01234567" in page
    assert "notes-range-end: 1111111111111111111111111111111111111111" not in page


@pytest.mark.parametrize("fence", ["```", "~~~"])
def test_heading_conversion_ignores_fenced_code(tmp_path: Path, fence: str) -> None:
    staged = NEXT + f"\n{fence}markdown\n## literal example\n{fence}\n"
    write(tmp_path / "docs/releases/2.4.md", canonical("v2.4.0"))
    write(tmp_path / "docs/releases/next.md", staged)
    page = plan_promotion(tmp_path, "2.4.1").writes[
        tmp_path / "docs/releases/2.4.md"
    ]
    assert "### Credential rotation" in page
    assert "## literal example" in page
    assert "### literal example" not in page
```

Add malformed tests for duplicate/missing title, watermark, NEXT summary markers, empty summary, canonical watermark, and patch sentinels. Snapshot all source bytes before each refusal and assert they remain identical afterward.

- [ ] **Step 3: Run tests to verify promotion output is missing**

```bash
uv run --no-project --with pytest pytest tests/test_promote_release_notes.py -x -q
```

Expected: FAIL on new-page or patch output assertions.

- [ ] **Step 4: Implement deterministic new-page conversion**

Implement these transformations only after every staging and index invariant passes:

```python
def new_page_text(next_text: str, target: Target) -> str:
    body = next_text.replace("# Next release", f"# {target.minor}", 1)
    body = body.replace("RELEASE-SUMMARY NEXT", f"RELEASE-SUMMARY {target.tag}")
    return body.rstrip() + "\n\n<!-- PATCH-RELEASES-START -->\n<!-- PATCH-RELEASES-END -->\n"
```

For index insertion, consume the complete multiline START comment through its terminating `-->`, replace the two-line seeded placeholder only when present, reject an existing `({minor}.md)` link, and insert exactly `- [{minor}]({minor}.md)\n` before older entries.

- [ ] **Step 5: Implement fenced-code-aware patch conversion**

`shift_headings` must toggle fences whose opening line begins with at least three backticks or tildes and only prefix headings outside fences. Remove the staging H1 and watermark from the appended section, replace NEXT markers, prefix the section with `## {target.tag}`, and replace the canonical page's single top watermark with the staging watermark.

Insert the section before `<!-- PATCH-RELEASES-END -->`. Parse existing `## vX.Y.Z` patch headings and refuse if the target would violate ascending version order rather than silently reordering hand-written prose.

- [ ] **Step 6: Run all promotion-content tests**

```bash
uv run --no-project --with pytest pytest tests/test_promote_release_notes.py -x -q
```

Expected: all pure planning tests pass.

- [ ] **Step 7: Commit promotion formatting**

```bash
git add scripts/promote_release_notes.py tests/test_promote_release_notes.py
git commit -m "feat(release): promote next notes into canonical pages"
```

### Task 3: Apply Plans Atomically And Stage Exact Paths

**Files:**
- Modify: `scripts/promote_release_notes.py`
- Modify: `tests/test_promote_release_notes.py`
- Modify: `pyproject.toml.jinja`
- Modify: `.github/workflows/template-ci.yml`

**Interfaces:**
- Consumes: complete in-memory `PromotionPlan` from Tasks 1-2.
- Produces: `apply_plan(plan: PromotionPlan) -> None`.
- Produces: CLI `python3 scripts/promote_release_notes.py VERSION`.

- [ ] **Step 1: Add failing real-filesystem and git-index tests**

Initialize a temporary git repository, commit the fixtures, run `main(["2.4.1-rc.1"])` from that root, then assert:

```python
status = subprocess.run(
    ["git", "diff", "--cached", "--name-status"],
    cwd=tmp_path,
    check=True,
    capture_output=True,
    text=True,
).stdout.splitlines()
assert status == ["M\tdocs/releases/2.4.md", "D\tdocs/releases/next.md"]
```

For a new series, expect `M docs/releases/index.md`, `A docs/releases/2.4.md`, and `D docs/releases/next.md`. For the no-op state, assert an empty cached diff. For every validation failure, compare a `{path: bytes}` snapshot before and after CLI execution.

- [ ] **Step 2: Run tests to verify plans are not applied**

```bash
uv run --no-project --with pytest pytest tests/test_promote_release_notes.py -x -q
```

Expected: FAIL because `apply_plan` and CLI staging are absent.

- [ ] **Step 3: Implement temporary writes, replacement, deletion, and staging**

Use sibling temporary files and fixed git argv:

```python
def apply_plan(plan: PromotionPlan) -> None:
    temporary: dict[Path, Path] = {}
    try:
        for path, text in plan.writes.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = path.with_name(f".{path.name}.tmp")
            temp.write_text(text, encoding="utf-8", newline="\n")
            temporary[path] = temp
        for path, temp in temporary.items():
            temp.replace(path)
        for path in plan.deletes:
            path.unlink()
    finally:
        for temp in temporary.values():
            temp.unlink(missing_ok=True)
    if plan.stage_paths:
        subprocess.run(
            ["git", "add", "-A", "--", *[str(path) for path in plan.stage_paths]],
            cwd=plan.root,
            check=True,
        )
```

`main` uses `Path.cwd()`, prints a concise no-op or promotion result, catches only `PromotionError` to print `promote_release_notes: REFUSING: ...` to stderr, and returns 1. Unexpected filesystem or git failures propagate.

- [ ] **Step 4: Add structural-security exceptions**

Add `scripts/promote_release_notes.py` beside `scripts/stamp_manifests.py` in the rendered Ruff `S603`/`S607` per-file ignores. The justification must state that `git add -A --` uses fixed argv and explicit repository paths. Include the new script in template CI's template-side Ruff/format and shipped-script structural checks.

- [ ] **Step 5: Run behavioral and static checks**

```bash
uv run --no-project --with pytest pytest tests/test_promote_release_notes.py -x -q
uv run --no-project --with ruff ruff check scripts/promote_release_notes.py tests/test_promote_release_notes.py
uv run --no-project --with ruff ruff format --check scripts/promote_release_notes.py tests/test_promote_release_notes.py
```

Expected: all tests and checks pass.

- [ ] **Step 6: Commit filesystem integration**

```bash
git add scripts/promote_release_notes.py tests/test_promote_release_notes.py pyproject.toml.jinja .github/workflows/template-ci.yml
git commit -m "feat(release): apply and stage promoted notes"
```

### Task 4: Integrate Promotion And Remove Hosted Drafting

**Files:**
- Modify: `knope.toml.jinja`
- Modify: `.github/workflows/release-prepare.yml.jinja`
- Modify: `.github/workflows/release.yml.jinja`
- Delete: `.github/workflows/release-notes.yml.jinja`
- Modify: `tests/test_release_flow_contract.py.jinja`

**Interfaces:**
- Consumes: CLI from Task 3.
- Produces: knope order `PrepareRelease -> stamp manifests -> promote notes -> commit -> promotion guard -> push -> PR`.
- Preserves: release-body RC normalization through `marker_tag="v${ver%%-*}"`.

- [ ] **Step 1: Replace hosted-drafting contract tests with deterministic tests**

Delete tests that require `NOTES_WORKFLOW`, notes concurrency, `full_redraft`, draft holds, lease retries, and reusable dispatch. Add these structural tests:

```python
def test_prepare_promotes_notes_before_release_commit() -> None:
    text = KNOPE_TOML.read_text(encoding="utf-8")
    prepare = text[text.index('name = "prepare-release"'):text.index('name = "tag-release"')]
    assert prepare.index("scripts/stamp_manifests.py $version") < prepare.index(
        "scripts/promote_release_notes.py $version"
    ) < prepare.index('git commit -m "chore: prepare release $version"')


def test_release_prepare_has_no_model_or_notes_bypass() -> None:
    text = PREPARE_WORKFLOW.read_text(encoding="utf-8")
    forbidden = (
        "CLAUDE_CODE_OAUTH_TOKEN",
        "anthropics/",
        "skip_notes",
        "full_redraft",
        "draft-notes",
        "gh pr ready --undo",
        "release-notes-draft",
    )
    assert not {token for token in forbidden if token in text}


def test_release_pr_body_assigns_freshness_to_reviewers() -> None:
    text = KNOPE_TOML.read_text(encoding="utf-8")
    assert "notes-range-end" in text
    assert "meaningful" in text
    assert "re-dispatch" in text
    assert "held as a DRAFT" not in text
```

Retain and rename the existing RC marker test so it explicitly asserts `marker_tag="v${ver%%-*}"` and the stable summary lookup.

- [ ] **Step 2: Commit and render the failing contract tests**

```bash
git add tests/test_release_flow_contract.py.jinja
git commit -m "test(release): require deterministic notes promotion"
rm -rf /tmp/smoke-release-contract
uv run --no-project --with copier copier copy --trust --defaults --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke-release-contract
uv sync --project /tmp/smoke-release-contract --all-extras --all-groups
uv run --project /tmp/smoke-release-contract pytest /tmp/smoke-release-contract/tests/test_release_flow_contract.py -x -q
```

Expected: FAIL on the new ordering and forbidden-token assertions.

- [ ] **Step 3: Insert the promotion command in knope**

After the manifest-stamping command and before the release commit, add:

```toml
[[workflows.steps]]
type = "Command"
command = "python3 scripts/promote_release_notes.py $version"
shell = true
```

Rewrite the PR body to state that notes presence was checked deterministically and to ask reviewers to compare `notes-range-end` with the release delta. Instruct them to merge a normal notes PR and re-dispatch when meaningful behavior is missing.

- [ ] **Step 4: Remove release drafting from Release Prepare**

Delete `skip_notes` and `full_redraft` inputs, contradictory-input validation, drafting-only outputs, prep-head recording, draft-state manipulation, and the entire `draft-notes` reusable job. Keep version reservation, prep-branch recreation, promotion guard, push, and PR creation unchanged.

Delete `.github/workflows/release-notes.yml.jinja` in full. Do not replace it with another workflow.

- [ ] **Step 5: Update release-body comments without changing behavior**

In `.github/workflows/release.yml.jinja`, remove references to the drafting job and `skip_notes`. Keep tagged-tree summary extraction, stable marker normalization, RC in-tag links, stable docs links, and branch-release bookkeeping.

- [ ] **Step 6: Commit deterministic preparation so Copier can render it**

```bash
git add knope.toml.jinja .github/workflows/release-prepare.yml.jinja .github/workflows/release.yml.jinja .github/workflows/release-notes.yml.jinja tests/test_release_flow_contract.py.jinja
git commit -m "refactor(release): remove hosted notes drafting"
```

The deleted workflow path remains in `git add` so its deletion is staged.

- [ ] **Step 7: Render and run the green contract tests**

```bash
rm -rf /tmp/smoke-release-contract
uv run --no-project --with copier copier copy --trust --defaults --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke-release-contract
uv sync --project /tmp/smoke-release-contract --all-extras --all-groups
uv run --project /tmp/smoke-release-contract pytest /tmp/smoke-release-contract/tests/test_release_flow_contract.py -x -q
uv run --no-project --with pyyaml python -c "import yaml; yaml.safe_load(open('/tmp/smoke-release-contract/.github/workflows/release-prepare.yml')); print('prepare YAML OK')"
```

Expected: contract tests pass and the rendered workflow parses. Fix failures in a new commit; do not amend either preceding commit.

### Task 5: Keep Staging Out Of Published Documentation

**Files:**
- Modify: `.github/workflows/release-notes-publish.yml.jinja`
- Modify: `mkdocs.yml.jinja`
- Modify: `docs/releases/index.md`
- Modify: `tests/test_release_flow_contract.py.jinja`

**Interfaces:**
- Consumes: `docs/releases/next.md` staging contract.
- Produces: canonical-only post-release publishing and LLM text output.

- [ ] **Step 1: Add failing publisher and MkDocs assertions**

```python
def test_notes_publish_ignores_next_only_changes() -> None:
    text = NOTES_PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    pages = text[text.index("Find changed release pages"):]
    assert "next\\.md" in pages


def test_next_notes_are_excluded_from_published_docs() -> None:
    text = (REPO_ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    assert "releases/next.md" in text
    assert "releases/*.md" not in text
    assert "releases/[0-9]*.[0-9]*.md" in text
```

Adapt constants to the rendered test module's existing `REPO_ROOT` pattern.

- [ ] **Step 2: Commit, render, and run the failing publication tests**

```bash
git add tests/test_release_flow_contract.py.jinja
git commit -m "test(docs): require next notes to stay unpublished"
rm -rf /tmp/smoke-release-publish
uv run --no-project --with copier copier copy --trust --defaults --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke-release-publish
uv sync --project /tmp/smoke-release-publish --all-extras --all-groups
uv run --project /tmp/smoke-release-publish pytest /tmp/smoke-release-publish/tests/test_release_flow_contract.py -x -q
```

Expected: FAIL because publish filtering excludes only `index.md` and llmstxt globs every release Markdown file.

- [ ] **Step 3: Exclude staging from every publication path**

In the publisher's changed-page pipeline, use:

```bash
grep -vE '/(index|next)\.md$'
```

Update the empty result message to say only index or staging files changed. Keep the broad trigger because GitHub Actions path filters cannot express the required canonical filename regex safely.

Add `releases/next.md` to `exclude_docs`. Replace the llmstxt release glob with `releases/[0-9]*.[0-9]*.md`; mkdocs-llmstxt supports glob patterns and this character-class prefix excludes `next.md`. Add a rendered strict-build assertion that `next.md` is absent from both `llms.txt` and `llms-full.txt`.

Change `docs/releases/index.md` from “dated section” to “versioned section”; keep `next.md` unlinked and preserve the insertion sentinel exactly.

- [ ] **Step 4: Commit publication exclusions so Copier can render them**

```bash
git add .github/workflows/release-notes-publish.yml.jinja mkdocs.yml.jinja docs/releases/index.md tests/test_release_flow_contract.py.jinja
git commit -m "fix(docs): keep next release notes unpublished"
```

- [ ] **Step 5: Render and verify publication behavior**

```bash
rm -rf /tmp/smoke-release-publish
uv run --no-project --with copier copier copy --trust --defaults --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke-release-publish
uv sync --project /tmp/smoke-release-publish --all-extras --all-groups
uv run --project /tmp/smoke-release-publish pytest /tmp/smoke-release-publish/tests/test_release_flow_contract.py -x -q
uv run --project /tmp/smoke-release-publish mkdocs build --strict
```

Expected: tests pass, the strict docs build succeeds, and generated LLM text contains no staging page. Fix failures in a new commit rather than amending.

### Task 6: Move And Rewrite The Provider-Neutral Skill

**Files:**
- Create: `.agents/skills/writing-release-notes/SKILL.md`
- Delete: `.claude/skills/writing-release-notes/SKILL.md`
- Modify: `.gitignore`
- Modify: `.gitignore.jinja`
- Modify: `copier.yml`
- Modify: `CLAUDE.md`
- Modify: `CLAUDE.md.jinja`

**Interfaces:**
- Produces: human-invoked skill modes `prepare-next`, `refresh-known-target`, and `backfill/redraft`.
- Preserves: `.claude/skills/authoring-issues-prs/SKILL.md` and all of its references.

- [ ] **Step 1: Add failing path and ownership assertions**

Extend an appropriate template structural test or create `scripts/tests/test_shared_skill_paths.py`:

```python
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
```

- [ ] **Step 2: Run the path tests to verify the old location remains**

```bash
uv run --no-project --with pytest pytest -q scripts/tests/test_shared_skill_paths.py
```

Expected: FAIL because `.agents/skills/writing-release-notes/` is absent.

- [ ] **Step 3: Move the skill and rewrite its inputs and outputs**

Move the file, retain the evidence and synthesis rules, and replace workflow context with this explicit opening contract:

```markdown
## Choose the mode

- `prepare-next`: research through the selected release branch head and write
  `docs/releases/next.md`.
- `refresh-known-target`: update an existing `docs/releases/X.Y.md` entry for
  the stable identity shared by an RC series.
- `backfill/redraft`: update a shipped canonical page.

Before research, record the repository, base branch, mode, stable target when
known, previous stable tag, and range-end commit SHA. Ask the human for any
value that cannot be derived unambiguously.
```

Replace the old artifact output with an ordinary PR sequence that checks status, refuses unrelated changes, creates `notes/<identity>`, commits only `docs/releases/`, any necessary Vale vocabulary additions, and the PR body, pushes, and runs `gh pr create --base "$BASE"`. The skill must never edit `CHANGELOG.md`.

For `prepare-next`, require the exact staging title and NEXT markers from the spec. For refresh and backfill, preserve exact `vX.Y.Z` markers and patch sentinels. Retain API-driven compare enumeration, commit-to-PR and PR-to-issue mapping, per-theme fan-out, attribution, first-party dependency research, net-delta synthesis, upgrade classification, docs-link checks, Vale, and strict MkDocs.

- [ ] **Step 4: Preserve both skill roots in ignore rules**

Add:

```gitignore
.agents/*
!.agents/skills/
```

to both ignore files without removing the existing `.claude` rules. Update `copier.yml` ownership comments and maintainer/generated `CLAUDE.md` layout text to distinguish the neutral release skill from the Claude-specific authoring skill.

- [ ] **Step 5: Run path and stale-reference checks**

```bash
uv run --no-project --with pytest pytest -q scripts/tests/test_shared_skill_paths.py
rg -n '\.claude/skills/writing-release-notes' . --glob '!docs/superpowers/**' --glob '!UPGRADING.md'
rg -n '\.agents/skills/writing-release-notes' . --glob '!docs/superpowers/**'
```

Expected: tests pass; the first `rg` has no live matches; the second finds the skill and current guidance. References to `.claude/skills/authoring-issues-prs` remain.

- [ ] **Step 6: Commit the neutral skill**

```bash
git add .agents/skills/writing-release-notes/SKILL.md .claude/skills/writing-release-notes/SKILL.md .gitignore .gitignore.jinja copier.yml CLAUDE.md CLAUDE.md.jinja scripts/tests/test_shared_skill_paths.py
git commit -m "refactor(skills): make release-note authoring provider-neutral"
```

### Task 7: Rewrite Release Documentation, Secrets, And Migration Guidance

**Files:**
- Modify: `docs/deployment/release-process.md.jinja`
- Modify: `CLAUDE.md.jinja`
- Modify: `README.md.jinja`
- Modify: `FORKING.md.jinja`
- Modify: `UPGRADING.md`
- Modify: `.github/workflows/template-ci.yml`

**Interfaces:**
- Consumes: optional-review answer from the prerequisite plan and neutral skill path from Task 6.
- Produces: one coherent operator process and one final `## Unreleased` migration section.

- [ ] **Step 1: Rewrite the release process around the human-owned sequence**

Document these exact steps:

```text
1. Invoke .agents/skills/writing-release-notes/SKILL.md and merge its next.md PR.
2. Dispatch Release Prepare.
3. Review deterministic promotion and compare notes-range-end with the release delta.
4. Merge the knope PR to tag and publish.
```

Explain first-RC consumption, later-RC/stable reuse, optional known-target refreshes, no dates on patch headings, and no notes bypass. Remove every reference to drafting jobs, draft holds, `skip_notes`, `full_redraft`, or manual Release Notes dispatch.

- [ ] **Step 2: Finalize generated instructions and secret tables**

In `CLAUDE.md.jinja`, replace headless drafting language with neutral skill and deterministic promotion rules. In `README.md.jinja`, remove `release-notes.yml` from both `RELEASE_TOKEN` and `CLAUDE_CODE_OAUTH_TOKEN` consumers. The Claude token row must now name only unconditional `claude.yml` and conditionally rendered `claude-code-review.yml`.

- [ ] **Step 3: Update forking and detach smoke in lockstep**

Remove `release-notes.yml` from `FORKING.md.jinja`'s deletion command and explanation because that workflow no longer exists. State that detached forks may retain or remove `.agents/skills/writing-release-notes/` independently and should keep deterministic `release-notes-publish.yml` when they retain release docs.

Update template CI's detach smoke deletion list, gone-file assertions, and kept-workflow assertions to match the new file set.

- [ ] **Step 4: Extend the existing Unreleased migration section**

Append instructions that downstreams must add these lines to their project-owned `.gitignore` when absent:

```gitignore
.agents/*
!.agents/skills/
```

Also state that operators must stop dispatching the removed workflow, merge `next.md` before preparing a new release identity, remove assumptions about draft holds and bypass inputs, and keep the Claude token only for `@claude` or opted-in automatic review. Existing canonical pages need no conversion.

- [ ] **Step 5: Commit documentation and render**

```bash
git add docs/deployment/release-process.md.jinja CLAUDE.md.jinja README.md.jinja FORKING.md.jinja UPGRADING.md .github/workflows/template-ci.yml
git commit -m "docs(release): document human-owned release notes"
rm -rf /tmp/smoke /tmp/smoke-claude-review-on
uv run --no-project --with copier copier copy --trust --defaults --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
uv run --no-project --with copier copier copy --trust --defaults --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml --data enable_automatic_claude_review=true . /tmp/smoke-claude-review-on
python3 scripts/check_render_hygiene.py /tmp/smoke /tmp/smoke-claude-review-on
python3 scripts/promote_upgrading.py --check
```

Expected: both renders are hygiene-clean and the migration checker accepts the final Unreleased section.

- [ ] **Step 6: Run prose and docs gates in both renders**

In each render, run:

```bash
vale sync
vale --glob='!docs/{superpowers,design,decisions}/**' docs README.md
uv run mkdocs build --strict
```

Expected: zero Vale findings and a successful strict build.

### Task 8: Run Full Template And Generated-Project Verification

**Files:**
- Verify only; modify failures in their owning task's files.

**Interfaces:**
- Verifies the integrated optional-review and release-notes plans.

- [ ] **Step 1: Run template-only tests**

```bash
uv run --with pytest --with pyyaml --with jsonschema --with jinja2 --with 'fastmcp-pvl-core>=4.6.1' pytest scripts/tests/ -v
```

Expected: all template-side tests pass.

- [ ] **Step 2: Run the default generated-project gate**

From `/tmp/smoke`:

```bash
uv sync --all-extras --all-groups
uv run ruff check .
uv run ruff format --check .
uv run mypy src/ tests/
uv run pytest -x -q
```

Expected: every command exits zero, including the new promotion tests.

- [ ] **Step 3: Validate enabled-review workflow and release workflow YAML**

```bash
uv run --no-project --with pyyaml python -c "from pathlib import Path; import yaml; roots=[Path('/tmp/smoke/.github/workflows'),Path('/tmp/smoke-claude-review-on/.github/workflows')]; [yaml.safe_load(p.read_text()) for root in roots for p in root.glob('*.yml')]; print('rendered workflows OK')"
```

Expected: all rendered workflows parse.

- [ ] **Step 4: Verify removed coupling and required files**

```bash
test ! -e /tmp/smoke/.github/workflows/release-notes.yml
test -e /tmp/smoke/.github/workflows/release-notes-publish.yml
test -e /tmp/smoke/.agents/skills/writing-release-notes/SKILL.md
test ! -e /tmp/smoke/.claude/skills/writing-release-notes/SKILL.md
test ! -e /tmp/smoke/.github/workflows/claude-code-review.yml
test -e /tmp/smoke-claude-review-on/.github/workflows/claude-code-review.yml
```

Expected: all assertions succeed.

- [ ] **Step 5: Review the cumulative diff and commit final fixes**

```bash
git status --short
git diff --check
git diff --stat
```

Expected: no whitespace errors and only files named by these two plans. Commit any verified fixes in a new commit; do not amend earlier commits.
