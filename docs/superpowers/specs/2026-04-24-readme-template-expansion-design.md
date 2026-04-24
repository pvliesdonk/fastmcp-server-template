# README.md.jinja expansion — design

**Status:** draft
**Closes:** #57 (README expansion), #52 (venv shebangs — absorbed as troubleshooting)
**Related:** PR #62 (scaffolding fixes), PR #63 (CLAUDE.md.jinja PR discipline). The sentinel conventions adopted here mirror `CLAUDE.md.jinja`.

## Purpose

Replace the minimal 63-line `README.md.jinja` with a structured template split into template-owned sections (uniformly updated across all downstreams via `copier update`) and `DOMAIN`-sentinel blocks (preserved across updates). Give freshly-scaffolded projects a useful, publishable README without hand-writing the scaffold — and give coding agents filling in the domain content a clear, narrow set of slots to target.

## Scope

- Rewrite `README.md.jinja` to include a badge row, features list, usage narratives, five install methods, configuration tables, the existing post-scaffold checklist (expanded), GitHub secrets, local development, troubleshooting, links, and domain-design notes.
- Move `README.md` from `_skip_if_exists` to the template-owned pool so template-owned sections update across all downstreams on `copier update`, while `<!-- DOMAIN-START --> / <!-- DOMAIN-END -->` blocks preserve domain edits.
- Fold #52 (stale venv shebangs after a scaffolded project is moved) into a `## Troubleshooting` subsection.

## Out of scope

- Claude Code plugin marketplace reference — specific to `pvliesdonk/claude-plugins` and not something every downstream ships.
- DeepWiki badge — opt-in only for some projects.
- Backfilling existing downstream READMEs. The weekly `copier-update` cron will pick this up; downstream owners reconcile conflicts per the existing process.
- Changes to `mkdocs` / docs-site content — this is README only.

## Current state

`README.md.jinja` (63 lines) contains: title, one-line description, quick-start (`serve` stdio/http), pointer to `docs/configuration.md`, 4-step post-scaffold checklist, GitHub secrets table, local dev gate snippet, links. `README.md` is in `copier.yml` `_skip_if_exists` — rendered once on first copy, never touched on update.

## Target state

### Sentinel convention

Follow `CLAUDE.md.jinja`'s layout (DOMAIN blocks top/bottom; template-owned sections wrapped in banner comments in the middle):

```
# header + badges + description + hook
## [DOMAIN sections — features, usage narratives]
<!-- ===== TEMPLATE-OWNED SECTIONS BELOW — DO NOT EDIT ===== -->
## [template-owned sections — install, config, checklist, secrets, dev, troubleshooting, links]
<!-- ===== TEMPLATE-OWNED SECTIONS END ===== -->
## [DOMAIN sections — domain config, key design decisions]
```

Remove `README.md` from `copier.yml:_skip_if_exists`. Downstream edits inside DOMAIN blocks are preserved by `copier update`'s three-way merge (same mechanism `CLAUDE.md.jinja` already relies on); edits outside DOMAIN blocks are expected to be re-rendered.

### Section list

| # | Section | Ownership | Notes |
|---|---|---|---|
| 1 | Title (`# {{ human_name }}`) | template | auto-rendered |
| 2 | Badge row | template | CI, codecov, PyPI, Python versions, license, GHCR, docs site, llms.txt — all parameterized on `{{ github_org }}`, `{{ project_name }}`, `{{ pypi_name }}` |
| 3 | `{{ domain_description }}` + quick-links hook (`Documentation \| PyPI \| Docker`) | template | |
| 4 | `## Features` | **DOMAIN** | Placeholder bullet list with a short comment explaining coding agents should replace with real feature bullets |
| 5 | `## What you can do with it` | **DOMAIN** | Placeholder usage narratives in the "you can ask Claude to X" style. Comment explains this is the "demo prompts" section |
| 6 | `## Installation` | template | Five subsections: PyPI, from source, Docker, Linux packages (.deb/.rpm), Claude Desktop (.mcpb) — all already published by the template's release workflow |
| 7 | `## Quick start` | template | Preserves current `serve` snippet; adds library-usage stub |
| 8 | `## Configuration` | template | Core env vars table: `FASTMCP_LOG_LEVEL`, `FASTMCP_ENABLE_RICH_LOGGING`, transport vars if applicable. Points at `## Domain configuration` below for domain vars |
| 9 | `## Post-scaffold checklist` | template | Current 5-step checklist + step 0 "fill in DOMAIN blocks" at the top |
| 10 | `## GitHub secrets` | template | Preserved verbatim |
| 11 | `## Local development` | template | Preserved verbatim |
| 12 | `## Troubleshooting` | template | Two initial entries: "Moving a scaffolded project" (absorbs #52) and "`uv.lock` refresh after template update" (covers the #62 rollout footgun) |
| 13 | `## Links` | template | Docs site, FastMCP, `fastmcp-pvl-core` — preserved from current |
| 14 | `## Domain configuration` | **DOMAIN** | Placeholder env var table for domain-specific vars. Comment explains the format expected |
| 15 | `## Key design decisions` | **DOMAIN** | Placeholder for domain architectural decisions. Mirrors the same section in `CLAUDE.md.jinja` |

### DOMAIN block placeholder convention

Per the decision to ship concrete starter content (not empty blocks), each DOMAIN block contains:

1. A top HTML comment explaining what goes in the block and that it's preserved across `copier update`.
2. Short, useful placeholder content a coding agent can replace — specific enough to be illustrative, generic enough not to mislead.

Example for `## Features`:

```markdown
## Features

<!-- DOMAIN-START -->
<!-- Replace with 3-7 bullets describing what this MCP server does. Preserved across copier update. -->

- **[Feature 1]** — one-sentence description of a user-visible capability.
- **[Feature 2]** — one-sentence description of another capability.
- **MCP tools** — N LLM-visible tools exposed; see `src/{{ python_module }}/tools.py`.
- **MCP resources** — M resources exposing domain state.
- **MCP prompts** — K prompt templates.
<!-- DOMAIN-END -->
```

Agents and humans replace the `[Feature N]` bullets and update the tool/resource/prompt counts; the structural hints persist.

### Badge row

Eight badges (in order), all parameterized:

| Badge | Target |
|---|---|
| CI | `https://github.com/{{ github_org }}/{{ project_name }}/actions/workflows/ci.yml/badge.svg` |
| codecov | `https://codecov.io/gh/{{ github_org }}/{{ project_name }}/graph/badge.svg` |
| PyPI version | `https://img.shields.io/pypi/v/{{ pypi_name }}` |
| Python versions | `https://img.shields.io/pypi/pyversions/{{ pypi_name }}` |
| License | `https://img.shields.io/github/license/{{ github_org }}/{{ project_name }}` |
| GHCR | `https://img.shields.io/github/v/release/{{ github_org }}/{{ project_name }}?label=ghcr.io&logo=docker` |
| Docs site | `https://img.shields.io/badge/docs-GitHub%20Pages-blue` linking to `https://{{ github_org }}.github.io/{{ project_name }}/` |
| llms.txt | `https://img.shields.io/badge/llms.txt-available-brightgreen` linking to `https://{{ github_org }}.github.io/{{ project_name }}/llms.txt` (wired in by the existing docs workflow) |

### Install section

Five subsections. For each, specify exact commands and a one-liner of context:

1. **From PyPI** — `pip install {{ pypi_name }}`; also `pip install {{ pypi_name }}[mcp]` when the FastMCP extra becomes domain-relevant (template-owned comment says "add optional extras between the `PROJECT-EXTRAS` sentinels in `pyproject.toml`").
2. **From source** — clone + `pip install -e ".[dev]"`.
3. **Docker** — `docker pull ghcr.io/{{ github_org }}/{{ project_name }}:latest` + pointer at `compose.yml`.
4. **Linux packages (.deb / .rpm)** — pointer at GitHub Releases; note systemd unit installs to `/usr/lib/systemd/system/{{ project_name }}.service` and env file at `/etc/{{ project_name }}/env.example` (references #59).
5. **Claude Desktop (.mcpb bundle)** — pointer at GitHub Releases; note `mcpb install {{ project_name }}-<version>.mcpb` and the GUI prompt for env vars.

### Troubleshooting section

Initial entries (both pre-existing reports from our triage):

- **"Moving a scaffolded project" (#52)** — after `mv /old/path /new/path`, `uv run pytest` fails with stale venv shebangs. Fix: `rm -rf .venv && uv sync --all-extras --dev`. Reference the issue and mention `uv run python -m pytest` also bypasses the stale shim.
- **"`uv.lock` refresh after template update"** — when `copier update` brings in new dependencies (e.g. the `docs` extra added in #62), `uv sync --frozen` in CI fails. Fix: run `uv lock` locally, commit the refreshed lockfile.

## Files touched

- `README.md.jinja` — full rewrite (grows from ~63 lines to ~200–250).
- `copier.yml` — remove `"README.md"` from `_skip_if_exists`. Add brief comment noting the README uses the same sentinel pattern as `CLAUDE.md.jinja`.
- `docs/superpowers/specs/2026-04-24-readme-template-expansion-design.md` — this file.

No other files change. No new dependencies.

## Verification

On the feature branch, after committing:

1. **Smoke render:** `rm -rf /tmp/smoke && uv run --no-project --with copier copier copy --trust --defaults --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke`. Inspect `/tmp/smoke/README.md` — all badges resolve to the smoke project's slugs; all placeholder DOMAIN content renders.
2. **Markdown validity:** `cd /tmp/smoke && uv run mkdocs build --strict` still passes (README isn't in the nav, but we confirm no broken cross-references sneak in).
3. **Sentinel round-trip:** simulate a `copier update`:
   - Run copier copy once against a temp dir to seed.
   - Edit a `## Features` DOMAIN bullet in the generated `README.md`.
   - Edit the template's title line.
   - Commit the template change, run `copier update` against the seeded dir.
   - Confirm: title updated (template-owned), Features bullet preserved (DOMAIN).
4. **Existing gate:** `uv run ruff check .`, `ruff format --check .`, `mypy src/ tests/`, `pytest -x -q` on the rendered smoke project — all green.
5. **#52 absorption:** verify the troubleshooting entry reproduces the user-flow described in #52 (move-then-pytest → fix command).

## Rollout notes

- Removing `README.md` from `_skip_if_exists` means the weekly `copier-update` cron will rewrite the README on downstream projects. Each consumer will see a large-but-structured diff, with any edits they made inside DOMAIN blocks preserved and any edits outside those blocks overwritten.
- Downstream rollout plan (per ~/.claude/CLAUDE.md conventions, the three known consumers from memory):
  - Preview the diff locally against each consumer before merging this template change.
  - Flag in the PR body that the change is intentionally broad and that conflicts in existing downstream READMEs are expected and reconcilable.

## Open questions resolved

- **All five install methods ship unconditionally** — template workflows already publish all of them; documenting costs nothing and discourages drift. (Answered.)
- **Badges include llms.txt; DeepWiki excluded** — llms.txt is wired by the docs workflow so always-on is free. (Answered.)
- **DOMAIN blocks ship placeholder content** — coding agents use the structure as an example; empty blocks would lose the structural hint. Each placeholder block starts with a `<!-- -->` comment explaining the replacement target. (Answered.)

## Follow-ups not in scope

- #55 (PR-per-phase plan workflow) — rethink after this wave lands.
- #61 (template-ci docs/nfpm smoke steps) — still open.
- #64 (CLAUDE.md.jinja Gate #3 mypy scope) — trivial doc patch, pick up anytime.
