# Extend sentinel-protection to remaining `docs/` files

**Date:** 2026-05-07
**Tracks:** [#106](https://github.com/pvliesdonk/fastmcp-server-template/issues/106)
**Builds on:** [#29 / PR #108](https://github.com/pvliesdonk/fastmcp-server-template/issues/29) — sentinel-protected `docs/deployment/*` and `docs/guides/authentication.md`

## Goal

Move the remaining five `docs/` files out of `_skip_if_exists` and add per-file `<!-- DOMAIN-{TOPIC}-{KIND}-START/END -->` sentinel blocks so future template improvements (link updates, new framing paragraphs, new shared sections) flow to downstream consumers via `copier update` while their domain-specific content survives.

The five files:

- `docs/index.md` — landing page
- `docs/installation.md` — install instructions
- `docs/configuration.md` — env vars / config
- `docs/tools/index.md` — tool catalog
- `docs/prompts.md` — prompt catalog

After this change, `_skip_if_exists` no longer contains any `docs/*.md` entries — the docs tree becomes fully template-owned with sentinel-protected domain zones.

## Architecture

Two-part atomic change in a single PR:

1. **Drop five lines** from `copier.yml`'s `_skip_if_exists`:

   ```diff
   -  - "docs/index.md"
   -  - "docs/installation.md"
   -  - "docs/configuration.md"
   -  - "docs/tools/index.md"
   -  - "docs/prompts.md"
   ```

2. **Add `<!-- DOMAIN-{TOPIC}-{KIND}-START/END -->` sentinel blocks** to each of the five `.jinja` files at the natural per-file shape (see "Per-file designs" below).

Sentinel naming follows the topic-specific family established by #29 (`DOMAIN-DOCKER-EXTRA`, `DOMAIN-OIDC-EXTRA`, `DOMAIN-AUTH-EXTRA`). Bare anonymous `<!-- DOMAIN-START -->` (used in README.md.jinja and CLAUDE.md.jinja) is **not** used here — every block on every file is greppable by topic.

## Tech Stack

- `copier` (template renderer, reads `copier.yml`)
- `mkdocs-material` + `mkdocs-llmstxt` (docs site, validated via `mkdocs build --strict` in `template-ci.yml`'s `downstream-gate` job)
- HTML comments inside Markdown for sentinel markers (matches the pre-existing convention in CLAUDE.md.jinja, README.md.jinja, and the #29-introduced `docs/deployment/*` and `docs/guides/*`)

## Files to change

| File | Change | Result |
|------|--------|--------|
| `copier.yml` | Remove 5 lines from `_skip_if_exists` | Five docs files now flow through copier-update |
| `docs/index.md.jinja` | Add 2 DOMAIN blocks at end | Template owns title + description + Getting started; operator owns Features + Use cases below |
| `docs/installation.md.jinja` | Append 1 DOMAIN-INSTALL-EXTRA block | Template owns install instructions; operator appends notes |
| `docs/configuration.md.jinja` | Wrap existing `## Domain variables` in DOMAIN-CONFIG-VARS | Template owns common-vars + File Exchange table; operator owns domain vars |
| `docs/tools/index.md.jinja` | Replace placeholder body with framing + DOMAIN-TOOLS-LIST | Template owns intro + FastMCP-docs link; operator owns tool catalog |
| `docs/prompts.md.jinja` | Reorder: framing → Example → FastMCP link → DOMAIN-PROMPTS-LIST | Template owns framing + Example + FastMCP link; operator owns prompt catalog |

## Per-file designs

### 1. `docs/index.md.jinja`

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

The `{{ human_name }}` title and `{{ domain_description }}` introduction render from copier answers (re-rendered on every `copier update`, so they stay in sync if the operator changes their answer). The "Getting started" link list stays template-owned and sits immediately after the description — the template knows which docs ship and updates the list when docs are added or removed. The two operator-owned DOMAIN blocks (Features, Use cases) sit below the navigation, so a visitor landing on the page sees the install/config/tools links before the operator's pitch.

### 2. `docs/installation.md.jinja`

Append at end of file:

```markdown
<!-- DOMAIN-INSTALL-EXTRA-START -->

## Project-specific notes

_Add domain-specific install notes here, e.g. system dependencies, optional
extras, or custom configuration steps._

<!-- DOMAIN-INSTALL-EXTRA-END -->
```

Matches the #29 EXTRA pattern exactly: blank line before `<!-- DOMAIN-INSTALL-EXTRA-START -->` separates it from the preceding `## From source` section; the `## Project-specific notes` heading inside the block gives the rendered docs site a labeled section even when the operator hasn't customized.

### 3. `docs/configuration.md.jinja`

Wrap the existing `## Domain variables` placeholder section in sentinels:

```markdown
<!-- DOMAIN-CONFIG-VARS-START -->
## Domain variables

Document your project-specific variables here.
<!-- DOMAIN-CONFIG-VARS-END -->
```

The "Common variables" + "MCP File Exchange" sections above remain template-owned (they describe core `fastmcp-pvl-core` variables and the shared file-exchange contract — both update via the template). Sentinel name uses `VARS` for brevity, matching the section heading "variables".

### 4. `docs/tools/index.md.jinja`

Replace the current 7-line placeholder with framing + DOMAIN-TOOLS-LIST block:

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

The intro paragraph + FastMCP-docs link become template-owned (so they update if FastMCP's docs URL changes or the framing improves). The catalog body (currently the `ping` placeholder) becomes operator-owned. Operators replace the `ping` example with their actual tool catalog inside the sentinel block.

### 5. `docs/prompts.md.jinja`

Reorder so the Example block sits *before* the DOMAIN block (more natural reading order: framing → example → catalog), and wrap the "Built-in prompts" section in sentinels:

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

The framing + Example + FastMCP-docs link stay template-owned. The catalog (currently empty placeholder) is operator-owned.

## Sentinel naming convention

All sentinel blocks introduced by this PR use topic-specific names from the `DOMAIN-{TOPIC}-{KIND}` family. No bare `<!-- DOMAIN-START -->` blocks are introduced — every block is greppable.

| Sentinel | File | Purpose |
|----------|------|---------|
| `DOMAIN-INDEX-FEATURES-START/END` | `docs/index.md.jinja` | Operator-owned features bullets |
| `DOMAIN-INDEX-USE-CASES-START/END` | `docs/index.md.jinja` | Operator-owned usage examples |
| `DOMAIN-INSTALL-EXTRA-START/END` | `docs/installation.md.jinja` | Operator-appended install notes |
| `DOMAIN-CONFIG-VARS-START/END` | `docs/configuration.md.jinja` | Operator-owned env-var documentation |
| `DOMAIN-TOOLS-LIST-START/END` | `docs/tools/index.md.jinja` | Operator-owned tool catalog |
| `DOMAIN-PROMPTS-LIST-START/END` | `docs/prompts.md.jinja` | Operator-owned prompt catalog |

The existing pre-#106 sentinels (`DOMAIN-DOCKER-EXTRA`, `DOMAIN-OIDC-EXTRA`, `DOMAIN-AUTH-EXTRA` from #29; `DOMAIN-START`/`DOMAIN-END` in README and CLAUDE.md from earlier work) are unchanged.

## Migration story

**Same approach as #29 / PR #108.** After merge, downstream consumers receive the new sentinel structure on their next `copier update` — either via the weekly `copier-update.yml` cron or a manual run.

**Expected per-downstream conflict shape:**

- **`docs/index.md`, `docs/installation.md`, `docs/configuration.md`** — operators are unlikely to have customized these (they were placeholder content); copier-update should land cleanly. If an operator did customize, the conflict resolves by accepting the new template + moving their content into the appropriate DOMAIN block.
- **`docs/tools/index.md`** — operators almost certainly have a real tool catalog here. Conflict on first update; resolution: keep the operator's catalog, move it inside the new `DOMAIN-TOOLS-LIST` block, accept the new template framing above.
- **`docs/prompts.md`** — same as tools: operators may have a real prompt catalog. Same resolution pattern.

**Downstream consumers:**

1. `pvliesdonk/image-generation-mcp`
2. `pvliesdonk/markdown-vault-mcp`
3. `pvliesdonk/paperless-mcp`
4. `pvliesdonk/reqeng-mcp`

The PR description for the implementation PR will document the expected conflict shape so the user (or the agent doing copier-update review) knows what "good" looks like during conflict resolution.

## Verification

Run on the implementation branch (works pre-merge via `--vcs-ref=HEAD`):

```bash
# 1. _skip_if_exists no longer contains the 5 docs files
grep -E "docs/(index|installation|configuration|tools/index|prompts)\.md" copier.yml
# Expected: only matches outside the _skip_if_exists block (none in the dropped lines)

# 2. All 6 new sentinels present in rendered output
rm -rf /tmp/smoke-106
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke-106

grep "DOMAIN-INDEX-FEATURES-START" /tmp/smoke-106/docs/index.md
grep "DOMAIN-INDEX-USE-CASES-START" /tmp/smoke-106/docs/index.md
grep "DOMAIN-INSTALL-EXTRA-START" /tmp/smoke-106/docs/installation.md
grep "DOMAIN-CONFIG-VARS-START" /tmp/smoke-106/docs/configuration.md
grep "DOMAIN-TOOLS-LIST-START" /tmp/smoke-106/docs/tools/index.md
grep "DOMAIN-PROMPTS-LIST-START" /tmp/smoke-106/docs/prompts.md

# 3. mkdocs build still passes (downstream-gate)
cd /tmp/smoke-106
uv sync --all-extras --all-groups
uv run mkdocs build --strict
```

## Out of scope

- **Other docs files** beyond the five listed (e.g. `docs/design.md.jinja`, `docs/deployment/*` from #29, `docs/guides/*` from #29) — this PR does not touch them.
- **Sentinel-protection of non-docs files** (Python sources, workflows, etc.) — separate concerns, separate issues.
- **Adding new content** to the framing sections — this PR preserves the current framing as template-owned. Improvements to the framing land in follow-up PRs that flow through the new sentinel structure.
- **Downstream-side rebases** — the user dispatches `copier update` per the standard manual-release workflow; this PR does not auto-open downstream PRs.
- **Renaming pre-existing sentinels** — the bare `<!-- DOMAIN-START -->` blocks in README.md.jinja and CLAUDE.md.jinja stay as-is.
