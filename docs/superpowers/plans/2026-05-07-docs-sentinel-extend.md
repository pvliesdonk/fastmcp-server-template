# Docs sentinel-extend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the 5 remaining `docs/` files out of `_skip_if_exists` and add per-file `<!-- DOMAIN-{TOPIC}-{KIND}-START/END -->` sentinel blocks so future template improvements flow to downstream consumers via `copier update` while their domain-specific content survives.

**Architecture:** Six independent edits in a single PR — five `.jinja` files each get a sentinel block (mid-file for `index.md.jinja`, end-of-file for the others), and `copier.yml` loses the five `_skip_if_exists` entries. Tasks 1-5 can be done in any order; Task 6 must be last because dropping `_skip_if_exists` is meaningless until the sentinels are in place to receive operator content.

**Tech Stack:** `copier` (template renderer), `mkdocs-material` + `mkdocs-llmstxt` (docs site, validated via `mkdocs build --strict`), HTML comments inside Markdown for sentinel markers (matches established convention in `CLAUDE.md.jinja`, `README.md.jinja`, and #29's `docs/deployment/*` and `docs/guides/*`).

**Spec:** `docs/superpowers/specs/2026-05-07-docs-sentinel-extend-design.md`

**Branch:** `feat/docs-sentinel-extend` (already created and tracking `origin/main`; spec already committed).

---

## File Map

| File | Created/Modified | Responsibility |
|------|-----------------|---------------|
| `copier.yml` | Modified | Drop 5 lines from `_skip_if_exists` (Task 6) |
| `docs/index.md.jinja` | Modified | Add 2 DOMAIN blocks for Features + Use cases (Task 1) |
| `docs/installation.md.jinja` | Modified | Append `DOMAIN-INSTALL-EXTRA` block (Task 2) |
| `docs/configuration.md.jinja` | Modified | Wrap existing `## Domain variables` in `DOMAIN-CONFIG-VARS` (Task 3) |
| `docs/tools/index.md.jinja` | Modified | Replace placeholder with framing + `DOMAIN-TOOLS-LIST` block (Task 4) |
| `docs/prompts.md.jinja` | Modified | Reorder Example before catalog + wrap "Built-in prompts" in `DOMAIN-PROMPTS-LIST` (Task 5) |

No new files. All changes are within the template repo; downstream consumers receive the changes via `copier update`.

---

## Verification Pattern (used in every task)

Each task follows the same verification pattern: render the template, grep for the new sentinel, spot-check the rendered output. The smoke-render command is:

```bash
rm -rf /tmp/smoke-106
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke-106
```

The `--vcs-ref=HEAD` flag is required so copier renders from the latest commit (default is the latest tag, which doesn't include the unreleased changes). All edits must be committed before the smoke render reflects them.

---

## Task 1: Add DOMAIN blocks to `docs/index.md.jinja`

**Files:**
- Modify: `docs/index.md.jinja`

- [ ] **Step 1: Verify the sentinels are NOT yet in the rendered file**

```bash
rm -rf /tmp/smoke-106
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke-106
grep -c "DOMAIN-INDEX-FEATURES" /tmp/smoke-106/docs/index.md || true
```
Expected: `0` (sentinel does not yet exist).

- [ ] **Step 2: Replace the file content**

Replace the entire content of `docs/index.md.jinja` with:

```markdown
# {{ human_name }}

{{ domain_description }}

## Getting started

- [Installation](installation.md)
- [Configuration](configuration.md)
- [Tools](tools/index.md)

<!-- DOMAIN-INDEX-FEATURES-START -->
## Features

- _Add features specific to your server here._
<!-- DOMAIN-INDEX-FEATURES-END -->

<!-- DOMAIN-INDEX-USE-CASES-START -->
## What you can do

- _Add usage examples here._
<!-- DOMAIN-INDEX-USE-CASES-END -->
```

- [ ] **Step 3: Commit so smoke render picks up the change**

```bash
git add docs/index.md.jinja
git commit -m "feat(docs): add DOMAIN-INDEX blocks to index.md.jinja (#106)"
```

- [ ] **Step 4: Re-render and verify both sentinels appear**

```bash
rm -rf /tmp/smoke-106
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke-106
grep -c "DOMAIN-INDEX-FEATURES-START" /tmp/smoke-106/docs/index.md
grep -c "DOMAIN-INDEX-FEATURES-END" /tmp/smoke-106/docs/index.md
grep -c "DOMAIN-INDEX-USE-CASES-START" /tmp/smoke-106/docs/index.md
grep -c "DOMAIN-INDEX-USE-CASES-END" /tmp/smoke-106/docs/index.md
```
Expected: each grep returns `1`.

- [ ] **Step 5: Spot-check rendered output**

```bash
cat /tmp/smoke-106/docs/index.md
```
Expected: title from `human_name` answer, description from `domain_description` answer, then `## Getting started` link list, then the two DOMAIN blocks each containing the placeholder bullet.

---

## Task 2: Add `DOMAIN-INSTALL-EXTRA` block to `docs/installation.md.jinja`

**Files:**
- Modify: `docs/installation.md.jinja`

- [ ] **Step 1: Verify the sentinel is NOT yet in the rendered file**

```bash
rm -rf /tmp/smoke-106
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke-106
grep -c "DOMAIN-INSTALL-EXTRA" /tmp/smoke-106/docs/installation.md || true
```
Expected: `0`.

- [ ] **Step 2: Append the block to the existing file**

Append the following to `docs/installation.md.jinja` (preserve the existing content; add a blank line first to separate from the preceding `## From source` section):

```markdown

<!-- DOMAIN-INSTALL-EXTRA-START -->

## Project-specific notes

_Add domain-specific install notes here, e.g. system dependencies, optional
extras, or custom configuration steps._

<!-- DOMAIN-INSTALL-EXTRA-END -->
```

The blank line BEFORE `<!-- DOMAIN-INSTALL-EXTRA-START -->` is required to separate it from the preceding section. The blank lines INSIDE the block (above and below the heading and paragraph) make the rendered output read cleanly.

- [ ] **Step 3: Commit**

```bash
git add docs/installation.md.jinja
git commit -m "feat(docs): add DOMAIN-INSTALL-EXTRA block to installation.md.jinja (#106)"
```

- [ ] **Step 4: Re-render and verify the sentinel appears**

```bash
rm -rf /tmp/smoke-106
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke-106
grep -c "DOMAIN-INSTALL-EXTRA-START" /tmp/smoke-106/docs/installation.md
grep -c "DOMAIN-INSTALL-EXTRA-END" /tmp/smoke-106/docs/installation.md
```
Expected: each grep returns `1`.

- [ ] **Step 5: Spot-check rendered output**

```bash
tail -15 /tmp/smoke-106/docs/installation.md
```
Expected: ends with the DOMAIN-INSTALL-EXTRA block, with the `## Project-specific notes` heading visible inside.

---

## Task 3: Wrap `## Domain variables` in `DOMAIN-CONFIG-VARS` in `docs/configuration.md.jinja`

**Files:**
- Modify: `docs/configuration.md.jinja:37-39` (the existing `## Domain variables` section at end of file)

- [ ] **Step 1: Verify the sentinel is NOT yet in the rendered file**

```bash
rm -rf /tmp/smoke-106
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke-106
grep -c "DOMAIN-CONFIG-VARS" /tmp/smoke-106/docs/configuration.md || true
```
Expected: `0`.

- [ ] **Step 2: Wrap the existing `## Domain variables` section**

Replace the last 3 lines of `docs/configuration.md.jinja`:

```markdown
## Domain variables

Document your project-specific variables here.
```

With:

```markdown
<!-- DOMAIN-CONFIG-VARS-START -->
## Domain variables

Document your project-specific variables here.
<!-- DOMAIN-CONFIG-VARS-END -->
```

- [ ] **Step 3: Commit**

```bash
git add docs/configuration.md.jinja
git commit -m "feat(docs): wrap Domain variables section in DOMAIN-CONFIG-VARS sentinels (#106)"
```

- [ ] **Step 4: Re-render and verify the sentinel appears**

```bash
rm -rf /tmp/smoke-106
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke-106
grep -c "DOMAIN-CONFIG-VARS-START" /tmp/smoke-106/docs/configuration.md
grep -c "DOMAIN-CONFIG-VARS-END" /tmp/smoke-106/docs/configuration.md
```
Expected: each grep returns `1`.

- [ ] **Step 5: Spot-check rendered output**

```bash
tail -10 /tmp/smoke-106/docs/configuration.md
```
Expected: ends with the wrapped `## Domain variables` section inside the sentinels, preceded by the unchanged "MCP File Exchange" table.

---

## Task 4: Replace placeholder body in `docs/tools/index.md.jinja` with framing + `DOMAIN-TOOLS-LIST` block

**Files:**
- Modify: `docs/tools/index.md.jinja`

- [ ] **Step 1: Verify the sentinel is NOT yet in the rendered file**

```bash
rm -rf /tmp/smoke-106
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke-106
grep -c "DOMAIN-TOOLS-LIST" /tmp/smoke-106/docs/tools/index.md || true
```
Expected: `0`.

- [ ] **Step 2: Replace the entire file content**

Replace the content of `docs/tools/index.md.jinja` with:

```markdown
# Tools

The tools registered in this server are listed below. See the
[FastMCP tools documentation](https://gofastmcp.com/servers/tools)
for the full tool API.

<!-- DOMAIN-TOOLS-LIST-START -->
## ping

Health-check tool — returns `"pong"` if the service is alive.
Replace with real tools per the scaffold in
`src/{{ python_module }}/tools.py`.
<!-- DOMAIN-TOOLS-LIST-END -->
```

- [ ] **Step 3: Commit**

```bash
git add docs/tools/index.md.jinja
git commit -m "feat(docs): add framing + DOMAIN-TOOLS-LIST to tools/index.md.jinja (#106)"
```

- [ ] **Step 4: Re-render and verify the sentinel appears**

```bash
rm -rf /tmp/smoke-106
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke-106
grep -c "DOMAIN-TOOLS-LIST-START" /tmp/smoke-106/docs/tools/index.md
grep -c "DOMAIN-TOOLS-LIST-END" /tmp/smoke-106/docs/tools/index.md
```
Expected: each grep returns `1`.

- [ ] **Step 5: Spot-check rendered output**

```bash
cat /tmp/smoke-106/docs/tools/index.md
```
Expected: `# Tools` header, intro paragraph with FastMCP-docs link, then the DOMAIN-TOOLS-LIST block containing the `ping` example with `{{ python_module }}` resolved to the smoke fixture's value.

---

## Task 5: Reorder + add `DOMAIN-PROMPTS-LIST` block to `docs/prompts.md.jinja`

**Files:**
- Modify: `docs/prompts.md.jinja`

- [ ] **Step 1: Verify the sentinel is NOT yet in the rendered file**

```bash
rm -rf /tmp/smoke-106
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke-106
grep -c "DOMAIN-PROMPTS-LIST" /tmp/smoke-106/docs/prompts.md || true
```
Expected: `0`.

- [ ] **Step 2: Replace the entire file content**

Replace the content of `docs/prompts.md.jinja` with (note the reorder: framing → Example → FastMCP link → DOMAIN-PROMPTS-LIST block, where the catalog moves to the end):

```markdown
# Prompts

MCP prompts are reusable prompt templates exposed to clients. The scaffold
ships a minimal set defined in `src/{{ python_module }}/prompts.py`; add
domain-specific prompts there and document them in this page.

## Example

```python
@mcp.prompt()
def summarize(topic: str) -> str:
    """Summarize the given topic in three sentences."""
    return f"Write a three-sentence summary of: {topic}"
```

See the [FastMCP prompts documentation](https://gofastmcp.com/servers/prompts)
for the full prompt API.

<!-- DOMAIN-PROMPTS-LIST-START -->
## Built-in prompts

_None in the scaffold._ Define prompts with `@mcp.prompt(...)` decorators in
`src/{{ python_module }}/prompts.py` and list them here with their arguments,
usage, and example output.
<!-- DOMAIN-PROMPTS-LIST-END -->
```

- [ ] **Step 3: Commit**

```bash
git add docs/prompts.md.jinja
git commit -m "feat(docs): reorder + add DOMAIN-PROMPTS-LIST to prompts.md.jinja (#106)"
```

- [ ] **Step 4: Re-render and verify the sentinel appears**

```bash
rm -rf /tmp/smoke-106
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke-106
grep -c "DOMAIN-PROMPTS-LIST-START" /tmp/smoke-106/docs/prompts.md
grep -c "DOMAIN-PROMPTS-LIST-END" /tmp/smoke-106/docs/prompts.md
```
Expected: each grep returns `1`.

- [ ] **Step 5: Spot-check rendered output**

```bash
cat /tmp/smoke-106/docs/prompts.md
```
Expected: `# Prompts` header, framing paragraph, `## Example` with the Python code block, FastMCP-docs link line, then the DOMAIN-PROMPTS-LIST block containing `## Built-in prompts`. Verify the Example block sits BEFORE the catalog (reorder applied correctly).

---

## Task 6: Drop the 5 `docs/*.md` entries from `copier.yml`'s `_skip_if_exists` and run the full gate

**Files:**
- Modify: `copier.yml:49-53` (the 5 `docs/*.md` entries inside `_skip_if_exists`)

- [ ] **Step 1: Confirm the 5 lines are present in the current `_skip_if_exists`**

```bash
sed -n '27,60p' copier.yml | grep -E '"docs/(index|installation|configuration|tools/index|prompts)\.md"'
```
Expected: 5 matching lines listed in this order:

```
  - "docs/index.md"
  - "docs/installation.md"
  - "docs/configuration.md"
  - "docs/tools/index.md"
  - "docs/prompts.md"
```

- [ ] **Step 2: Remove the 5 lines from `_skip_if_exists`**

Apply this exact diff to `copier.yml` (the surrounding context is the existing `_skip_if_exists` list):

```diff
@@ around line 49 @@
   - "docs/superpowers"
-  - "docs/index.md"
-  - "docs/installation.md"
-  - "docs/configuration.md"
-  - "docs/tools/index.md"
-  - "docs/prompts.md"
   - "docs/design.md"
```

(The exact line numbers and surrounding context may differ slightly — what matters is that the 5 `docs/*.md` lines listed above are deleted and no other lines in `_skip_if_exists` are touched.)

- [ ] **Step 3: Verify the 5 lines are gone**

```bash
grep -E '"docs/(index|installation|configuration|tools/index|prompts)\.md"' copier.yml
```
Expected: no output (the 5 lines no longer appear anywhere in `copier.yml`).

- [ ] **Step 4: Commit**

```bash
git add copier.yml
git commit -m "feat(template): drop docs/*.md entries from _skip_if_exists (#106)"
```

- [ ] **Step 5: Final smoke render and verify all 6 new sentinels are present**

```bash
rm -rf /tmp/smoke-106
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke-106

# All 6 new sentinels must be present:
grep -c "DOMAIN-INDEX-FEATURES-START" /tmp/smoke-106/docs/index.md
grep -c "DOMAIN-INDEX-USE-CASES-START" /tmp/smoke-106/docs/index.md
grep -c "DOMAIN-INSTALL-EXTRA-START" /tmp/smoke-106/docs/installation.md
grep -c "DOMAIN-CONFIG-VARS-START" /tmp/smoke-106/docs/configuration.md
grep -c "DOMAIN-TOOLS-LIST-START" /tmp/smoke-106/docs/tools/index.md
grep -c "DOMAIN-PROMPTS-LIST-START" /tmp/smoke-106/docs/prompts.md
```
Expected: each grep returns `1`.

- [ ] **Step 6: Run the full generated-project gate inside the smoke render**

```bash
cd /tmp/smoke-106
uv sync --all-extras --all-groups
uv run ruff check .
uv run ruff format --check .
uv run mypy src/ tests/
uv run pytest -x -q
uv run mkdocs build --strict
cd -
```
Expected: all six commands exit `0`. The mkdocs build is the one that exercises the new docs files; if any of the new sentinel comments break Markdown parsing or break a link, `mkdocs build --strict` will fail.

- [ ] **Step 7: Verify the rendered docs site renders the new domain sections cleanly**

```bash
ls /tmp/smoke-106/site/docs/
ls /tmp/smoke-106/site/installation/
ls /tmp/smoke-106/site/configuration/
ls /tmp/smoke-106/site/tools/
ls /tmp/smoke-106/site/prompts/
```
Expected: each directory contains an `index.html`. Optionally open one of them and verify the operator-owned sections render as expected (HTML comments are stripped from the output but the contained content appears).

---

## After Task 6

The branch is ready for the local code-review circus and PR open. Per the global PR Discipline rules:

1. **Run two local code-reviewer subagents** in parallel on the cumulative diff (one with `pr-review-toolkit:code-reviewer`, one with `feature-dev:code-reviewer` for the second-opinion pass). Pass them the diff `git diff origin/main...HEAD` and instruct them to read full file context, not just the hunks.
2. **Address every flagged finding** at any severity (or defend in writing if the reviewer is wrong) before pushing.
3. **Push as draft**: `git push -u origin feat/docs-sentinel-extend` then `gh pr create --draft --title "feat(docs): extend sentinel-protection to remaining docs/ files (#106)" --body "<from spec>"`.
4. Wait for `claude-review` (always runs) to LGTM. If anything found, address → re-run BOTH local subagents → push.
5. `gh pr ready <N>` to flip to ready, which triggers `gemini-code-assist`.
6. Wait for `gemini-code-assist` LGTM (HIGH severity threshold per `.gemini/config.yaml`).
7. Surface the merged-PR link to the user; do NOT run `gh pr merge` autonomously.

The PR description should include the expected per-downstream conflict shape from the spec's Migration story so the user (or the agent doing copier-update review) knows what "good" looks like during the next downstream `copier update`.

---

## Self-Review Notes

**Spec coverage:**
- Goal (5 files out of `_skip_if_exists` + sentinel blocks added) — covered by Tasks 1-6.
- Per-file designs (5 files, exact content) — covered by Tasks 1-5; each task includes the verbatim file content from the spec.
- Sentinel naming convention table — sentinel names in tasks match the spec's table exactly: `DOMAIN-INDEX-FEATURES`, `DOMAIN-INDEX-USE-CASES`, `DOMAIN-INSTALL-EXTRA`, `DOMAIN-CONFIG-VARS`, `DOMAIN-TOOLS-LIST`, `DOMAIN-PROMPTS-LIST`.
- Migration story — referenced in "After Task 6" for inclusion in PR description; the implementation itself doesn't touch downstreams.
- Verification commands (spec section "Verification") — Tasks 1-5 cover per-file grep verification; Task 6 covers the full-suite verification + mkdocs build.

**Placeholder scan:** No "TBD"/"TODO"/"implement later" strings in the plan. The `_Add features here_` markers in Task 1's Step 2 file content are intentional — they ship as placeholder content in the rendered template, not plan placeholders.

**Type/name consistency:** Sentinel names used identically across all task references (verified by re-reading each task's grep + edit steps). The branch name `feat/docs-sentinel-extend` is consistent with what's already created. The smoke-render directory `/tmp/smoke-106` is consistent across tasks.
