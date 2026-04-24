# README.md.jinja Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite `README.md.jinja` into a structured template with DOMAIN sentinel blocks (preserved across `copier update`) and template-owned sections (re-rendered uniformly), absorbing issue #52 as a troubleshooting entry.

**Architecture:** Mirror `CLAUDE.md.jinja`'s sentinel pattern — DOMAIN blocks at top (Features, What you can do with it) and bottom (Domain configuration, Key design decisions) wrap a central template-owned region (Installation, Quick start, Configuration, Post-scaffold checklist, GitHub secrets, Local development, Troubleshooting, Links) delimited by `<!-- ===== TEMPLATE-OWNED SECTIONS ===== -->` banner comments. Remove `README.md` from `copier.yml` `_skip_if_exists` so the template-owned sections update on `copier update`.

**Tech Stack:** copier (template rendering), Jinja2 (variable substitution), Markdown.

**Spec:** [`docs/superpowers/specs/2026-04-24-readme-template-expansion-design.md`](../specs/2026-04-24-readme-template-expansion-design.md)

**Branch:** `feat/readme-template-expansion` (already exists; spec already committed)

---

## Working conventions

- **Every content-level task** ends with: render the smoke project against HEAD (`--vcs-ref=HEAD`), verify the expected content is in `/tmp/smoke/README.md`, commit.
- **Commit cadence:** one commit per task with a `docs(readme): ...` or `refactor(copier): ...` conventional-commit message.
- **Smoke-render command** (used repeatedly; run from `/mnt/code/fastmcp-server-template`):
  ```bash
  rm -rf /tmp/smoke && uv run --no-project --with copier copier copy --trust --defaults --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
  ```
  After each commit, this command must succeed and produce a valid `/tmp/smoke/README.md`.

---

## Task 1: Scaffold the new README.md.jinja skeleton

**Files:**
- Modify: `README.md.jinja` (full rewrite; current ~63 lines → skeleton ~50 lines with empty bodies)

**Rationale:** Get the overall structure in place first — all headings, both sentinel banners, all DOMAIN comment markers. Every later task fills in one section's body.

- [ ] **Step 1: Replace the entire file contents with the skeleton below**

```markdown
# {{ human_name }}

<!-- BADGES PLACEHOLDER -->

{{ domain_description }}

**[Documentation](https://{{ github_org }}.github.io/{{ project_name }}/)** | **[PyPI](https://pypi.org/project/{{ pypi_name }}/)** | **[Docker](https://github.com/{{ github_org }}/{{ project_name }}/pkgs/container/{{ project_name }})**

## Features

<!-- DOMAIN-START -->
<!-- FEATURES PLACEHOLDER -->
<!-- DOMAIN-END -->

## What you can do with it

<!-- DOMAIN-START -->
<!-- USAGE NARRATIVES PLACEHOLDER -->
<!-- DOMAIN-END -->

<!-- ===== TEMPLATE-OWNED SECTIONS BELOW — DO NOT EDIT; CHANGES WILL BE OVERWRITTEN ON COPIER UPDATE ===== -->

## Installation

<!-- INSTALLATION PLACEHOLDER -->

## Quick start

<!-- QUICK START PLACEHOLDER -->

## Configuration

<!-- CORE CONFIG PLACEHOLDER -->

## Post-scaffold checklist

<!-- CHECKLIST PLACEHOLDER -->

## GitHub secrets

<!-- GITHUB SECRETS PLACEHOLDER -->

## Local development

<!-- LOCAL DEV PLACEHOLDER -->

## Troubleshooting

<!-- TROUBLESHOOTING PLACEHOLDER -->

## Links

<!-- LINKS PLACEHOLDER -->

<!-- ===== TEMPLATE-OWNED SECTIONS END ===== -->

## Domain configuration

<!-- DOMAIN-START -->
<!-- DOMAIN CONFIG PLACEHOLDER -->
<!-- DOMAIN-END -->

## Key design decisions

<!-- DOMAIN-START -->
<!-- KEY DESIGN PLACEHOLDER -->
<!-- DOMAIN-END -->
```

- [ ] **Step 2: Smoke render and verify structure**

```bash
rm -rf /tmp/smoke && uv run --no-project --with copier copier copy --trust --defaults --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
```

Then verify all 11 expected section headings render and both sentinel banner comments are present:

```bash
grep -c '^## ' /tmp/smoke/README.md         # expect: 11
grep -c 'DOMAIN-START' /tmp/smoke/README.md # expect: 4
grep -c 'DOMAIN-END' /tmp/smoke/README.md   # expect: 4
grep 'TEMPLATE-OWNED SECTIONS BELOW' /tmp/smoke/README.md
grep 'TEMPLATE-OWNED SECTIONS END' /tmp/smoke/README.md
```

Expected: all greps succeed with the expected counts.

- [ ] **Step 3: Commit**

```bash
git add README.md.jinja
git commit -m "docs(readme): scaffold structured skeleton with sentinel markers (refs #57)

Replace the ~63-line README with a skeleton containing all target
section headings and both \`<!-- DOMAIN-START -->\`/\`<!-- DOMAIN-END -->\`
blocks plus the template-owned banner comments that mirror
CLAUDE.md.jinja's pattern. Bodies are placeholder comments — filled
in by subsequent commits on this branch."
```

---

## Task 2: Add the badge row

**Files:**
- Modify: `README.md.jinja` (replace `<!-- BADGES PLACEHOLDER -->` line)

- [ ] **Step 1: Replace the badge placeholder with eight parameterized badges**

Replace the single line `<!-- BADGES PLACEHOLDER -->` with:

```markdown
[![CI](https://github.com/{{ github_org }}/{{ project_name }}/actions/workflows/ci.yml/badge.svg)](https://github.com/{{ github_org }}/{{ project_name }}/actions/workflows/ci.yml) [![codecov](https://codecov.io/gh/{{ github_org }}/{{ project_name }}/graph/badge.svg)](https://codecov.io/gh/{{ github_org }}/{{ project_name }}) [![PyPI](https://img.shields.io/pypi/v/{{ pypi_name }})](https://pypi.org/project/{{ pypi_name }}/) [![Python](https://img.shields.io/pypi/pyversions/{{ pypi_name }})](https://pypi.org/project/{{ pypi_name }}/) [![License](https://img.shields.io/github/license/{{ github_org }}/{{ project_name }})](LICENSE) [![Docker](https://img.shields.io/github/v/release/{{ github_org }}/{{ project_name }}?label=ghcr.io&logo=docker)](https://github.com/{{ github_org }}/{{ project_name }}/pkgs/container/{{ project_name }}) [![Docs](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://{{ github_org }}.github.io/{{ project_name }}/) [![llms.txt](https://img.shields.io/badge/llms.txt-available-brightgreen)](https://{{ github_org }}.github.io/{{ project_name }}/llms.txt)
```

Single line (no hard wraps) — Markdown treats consecutive badge links as one paragraph.

- [ ] **Step 2: Smoke render and verify badge substitution**

Run the smoke-render command. Then:

```bash
grep -c 'img.shields.io' /tmp/smoke/README.md  # expect: 4 (PyPI, Python, License, Docker)
grep -c 'actions/workflows/ci.yml' /tmp/smoke/README.md  # expect: 2 (badge src + link)
grep 'codecov.io/gh/pvliesdonk/smoke-mcp/graph' /tmp/smoke/README.md
grep 'pypi.org/project/smoke-mcp' /tmp/smoke/README.md
grep 'pvliesdonk.github.io/smoke-mcp/llms.txt' /tmp/smoke/README.md
```

All greps must succeed. The smoke project slug is `smoke-mcp` (per `tests/fixtures/smoke-answers.yml`); if any badge shows unrendered `{{ project_name }}` or `{{ pypi_name }}`, fail.

- [ ] **Step 3: Commit**

```bash
git add README.md.jinja
git commit -m "docs(readme): add parameterized 8-badge header row (refs #57)

CI, codecov, PyPI version, Python versions, License, GHCR, Docs site,
llms.txt — all parameterized on github_org / project_name / pypi_name.
llms.txt is wired by the shipped docs workflow so it's always-on; DeepWiki
is excluded (opt-in only for some projects)."
```

---

## Task 3: Fill in the Features DOMAIN block

**Files:**
- Modify: `README.md.jinja` (replace `<!-- FEATURES PLACEHOLDER -->`)

- [ ] **Step 1: Replace the Features placeholder**

Replace the single line `<!-- FEATURES PLACEHOLDER -->` with:

```markdown
<!-- Replace with 3-7 bullets describing what this MCP server does. Kept across copier update. -->

- **[Capability 1]** — one-sentence description of a user-visible feature.
- **[Capability 2]** — one-sentence description of another capability.
- **MCP tools** — N LLM-visible tools exposed; see `src/{{ python_module }}/tools.py`.
- **MCP resources** — M resources exposing domain state; see `src/{{ python_module }}/resources.py`.
- **MCP prompts** — K prompt templates; see `src/{{ python_module }}/prompts.py`.
```

The `[Capability N]`, `N`, `M`, `K` tokens are intentional placeholders an implementer replaces.

- [ ] **Step 2: Smoke render and verify**

```bash
# After smoke render
grep -A1 '^## Features' /tmp/smoke/README.md | tail -1  # expect: the DOMAIN-START comment marker line
grep 'src/smoke_mcp/tools.py' /tmp/smoke/README.md  # expect: path renders with python_module substitution
grep 'src/smoke_mcp/resources.py' /tmp/smoke/README.md
grep 'src/smoke_mcp/prompts.py' /tmp/smoke/README.md
```

- [ ] **Step 3: Commit**

```bash
git add README.md.jinja
git commit -m "docs(readme): ship Features DOMAIN block with placeholder capability bullets (refs #57)

Ship short, specific-enough-to-be-useful placeholders (\"[Capability 1]\",
N/M/K counts) that coding agents replace with real content — matches the
decision to ship starter content, not empty blocks, so the structural
hints (bullet shape, path references) persist across fills."
```

---

## Task 4: Fill in the "What you can do with it" DOMAIN block

**Files:**
- Modify: `README.md.jinja` (replace `<!-- USAGE NARRATIVES PLACEHOLDER -->`)

- [ ] **Step 1: Replace the usage-narratives placeholder**

Replace `<!-- USAGE NARRATIVES PLACEHOLDER -->` with:

```markdown
<!-- Replace with 3-5 concrete "you can ask Claude to X" examples. Kept across copier update. -->

With this server mounted in an MCP client (Claude, etc.), you can:

- **[Task 1]** — "[example user request]." Composes tools `[tool_a]` + `[tool_b]`.
- **[Task 2]** — "[another example request]." Uses resource `[resource_x]`.
- **[Task 3]** — "[third example]."

Short, concrete prompts beat abstract feature lists — replace the
`[Task N]` placeholders with prompts that actually work against your
server's tool surface.
```

- [ ] **Step 2: Smoke render and verify**

```bash
grep '^## What you can do with it$' /tmp/smoke/README.md
grep 'mounted in an MCP client' /tmp/smoke/README.md
grep '\[Task 1\]' /tmp/smoke/README.md  # placeholder survives to the render
```

- [ ] **Step 3: Commit**

```bash
git add README.md.jinja
git commit -m "docs(readme): ship \"What you can do with it\" DOMAIN block with usage-narrative placeholders (refs #57)

Short, concrete \"ask Claude to X\" examples mapped to tool/resource
composition — the pattern markdown-vault-mcp uses to communicate the
actual shape of interaction, not just a feature list."
```

---

## Task 5: Fill in the Installation section (5 subsections)

**Files:**
- Modify: `README.md.jinja` (replace `<!-- INSTALLATION PLACEHOLDER -->`)

- [ ] **Step 1: Replace the installation placeholder**

Replace `<!-- INSTALLATION PLACEHOLDER -->` with:

````markdown
### From PyPI

```bash
pip install {{ pypi_name }}
```

If you add optional extras via the `PROJECT-EXTRAS-START` / `PROJECT-EXTRAS-END` sentinels in `pyproject.toml`, document them here.

### From source

```bash
git clone https://github.com/{{ github_org }}/{{ project_name }}.git
cd {{ project_name }}
uv sync --all-extras --dev
```

### Docker

```bash
docker pull ghcr.io/{{ github_org }}/{{ project_name }}:latest
```

A `compose.yml` ships at the repo root as a starting point — copy `.env.example` to `.env`, edit, and `docker compose up -d`.

### Linux packages (.deb / .rpm)

Download `.deb` or `.rpm` packages from the [GitHub Releases](https://github.com/{{ github_org }}/{{ project_name }}/releases) page. Both install a hardened systemd unit; env configuration is sourced from `/etc/{{ project_name }}/env` (copy from the shipped `/etc/{{ project_name }}/env.example`).

### Claude Desktop (.mcpb bundle)

Download the `.mcpb` bundle from the [GitHub Releases](https://github.com/{{ github_org }}/{{ project_name }}/releases) page and double-click to install, or run:

```bash
mcpb install {{ project_name }}-<version>.mcpb
```

Claude Desktop prompts for required env vars via a GUI wizard — no manual JSON editing needed.
````

- [ ] **Step 2: Smoke render and verify all five subsections**

```bash
grep -c '^### From PyPI$\|^### From source$\|^### Docker$\|^### Linux packages\|^### Claude Desktop' /tmp/smoke/README.md  # expect: 5
grep 'pip install smoke-mcp' /tmp/smoke/README.md
grep 'docker pull ghcr.io/pvliesdonk/smoke-mcp' /tmp/smoke/README.md
grep '/etc/smoke-mcp/env.example' /tmp/smoke/README.md
grep 'mcpb install smoke-mcp' /tmp/smoke/README.md
```

- [ ] **Step 3: Commit**

```bash
git add README.md.jinja
git commit -m "docs(readme): document five install methods (PyPI / source / Docker / deb-rpm / mcpb) (refs #57)

Template's release workflow already publishes all five artifacts; the
README now documents each so they don't bit-rot. Cross-references the
systemd env path from #59 and the PROJECT-EXTRAS sentinels in
pyproject.toml.jinja."
```

---

## Task 6: Fill in Quick start

**Files:**
- Modify: `README.md.jinja` (replace `<!-- QUICK START PLACEHOLDER -->`)

- [ ] **Step 1: Replace the quick-start placeholder**

Replace `<!-- QUICK START PLACEHOLDER -->` with:

````markdown
```bash
{{ project_name }} serve                                # stdio transport
{{ project_name }} serve --transport http --port 8000   # streamable HTTP
```

For library usage (embedding the domain logic without the MCP transport), import from the `{{ python_module }}` package directly — see `src/{{ python_module }}/domain.py` for the entry point scaffold.
````

- [ ] **Step 2: Smoke render and verify**

```bash
grep 'smoke-mcp serve' /tmp/smoke/README.md  # appears twice (stdio + http lines)
grep '^## Quick start$' /tmp/smoke/README.md
grep 'src/smoke_mcp/domain.py' /tmp/smoke/README.md
```

- [ ] **Step 3: Commit**

```bash
git add README.md.jinja
git commit -m "docs(readme): preserve serve quick-start snippet and add library-usage pointer (refs #57)

Keeps the current two-liner (stdio + HTTP) and adds a pointer at
domain.py so consumers know where the embedding entry point lives
without having to spelunk."
```

---

## Task 7: Fill in the Configuration section (core env vars)

**Files:**
- Modify: `README.md.jinja` (replace `<!-- CORE CONFIG PLACEHOLDER -->`)

- [ ] **Step 1: Replace the core-config placeholder**

Replace `<!-- CORE CONFIG PLACEHOLDER -->` with:

````markdown
Core environment variables shared across all `fastmcp-pvl-core`-based services:

| Variable | Default | Description |
|---|---|---|
| `FASTMCP_LOG_LEVEL` | `INFO` | Log level for FastMCP internals and app loggers (`DEBUG` / `INFO` / `WARNING` / `ERROR`). The `-v` CLI flag overrides to `DEBUG`. |
| `FASTMCP_ENABLE_RICH_LOGGING` | `true` | Set to `false` for plain / structured JSON log output. |
| `{{ env_prefix }}_EVENT_STORE_URL` | `memory://` | Event store backend for HTTP session persistence — `memory://` (dev), `file:///path` (survives restarts). |

Domain-specific variables go below under [Domain configuration](#domain-configuration).
````

- [ ] **Step 2: Smoke render and verify**

```bash
grep 'FASTMCP_LOG_LEVEL' /tmp/smoke/README.md
grep 'FASTMCP_ENABLE_RICH_LOGGING' /tmp/smoke/README.md
grep 'SMOKE_MCP_EVENT_STORE_URL' /tmp/smoke/README.md  # env_prefix substitutes
grep 'Domain configuration' /tmp/smoke/README.md
```

- [ ] **Step 3: Commit**

```bash
git add README.md.jinja
git commit -m "docs(readme): add Core environment variables table (refs #57)

Three core vars shared across all fastmcp-pvl-core-based services:
FASTMCP_LOG_LEVEL, FASTMCP_ENABLE_RICH_LOGGING, and
{env_prefix}_EVENT_STORE_URL. Domain-specific vars live in the
DOMAIN block further down to keep the template-owned table focused
on universal settings."
```

---

## Task 8: Fill in Post-scaffold checklist

**Files:**
- Modify: `README.md.jinja` (replace `<!-- CHECKLIST PLACEHOLDER -->`)

- [ ] **Step 1: Replace the checklist placeholder**

Replace `<!-- CHECKLIST PLACEHOLDER -->` with:

````markdown
After `copier copy` and `gh repo create --push`:

1. **Fill in the DOMAIN blocks** in this README (Features, What you can do with it, Domain configuration, Key design decisions) and in `CLAUDE.md`.
2. Configure GitHub secrets — see below.
3. Install dev dependencies: `uv sync --all-extras --dev`.
4. Install pre-commit hooks: `uv run pre-commit install`.
5. Run the gate locally: `uv run pytest -x -q && uv run ruff check --fix . && uv run ruff format . && uv run mypy src/ tests/`.
6. Push the first commit — CI should be green.
````

- [ ] **Step 2: Smoke render and verify**

```bash
grep 'Fill in the DOMAIN blocks' /tmp/smoke/README.md
grep 'pre-commit install' /tmp/smoke/README.md
grep 'pytest -x -q && uv run ruff check --fix' /tmp/smoke/README.md
```

- [ ] **Step 3: Commit**

```bash
git add README.md.jinja
git commit -m "docs(readme): expand post-scaffold checklist with DOMAIN-fill step (refs #57)

Six-step checklist now starts with 'fill in the DOMAIN blocks' so a
fresh scaffold's first action is to make the README/CLAUDE.md reflect
the actual service. Steps 3-6 preserve the existing deps/pre-commit/
gate/push flow (including the full ruff check --fix + format sequence
fixed in #63)."
```

---

## Task 9: Fill in GitHub secrets + Local development sections

**Files:**
- Modify: `README.md.jinja` (replace `<!-- GITHUB SECRETS PLACEHOLDER -->` and `<!-- LOCAL DEV PLACEHOLDER -->`)

- [ ] **Step 1: Replace the GitHub-secrets placeholder**

Replace `<!-- GITHUB SECRETS PLACEHOLDER -->` with:

````markdown
CI workflows reference three repository secrets. Configure them via **Settings → Secrets and variables → Actions** or with `gh secret set`:

| Secret | Used by | How to generate |
|---|---|---|
| `RELEASE_TOKEN` | `release.yml`, `copier-update.yml` | Fine-grained PAT at <https://github.com/settings/personal-access-tokens/new> with `contents: write` and `pull_requests: write` (the `copier-update` cron opens PRs). Scoped to this repo. |
| `CODECOV_TOKEN` | `ci.yml` | <https://codecov.io> — sign in with GitHub, add the repo, copy the upload token from the repo settings page. |
| `CLAUDE_CODE_OAUTH_TOKEN` | `claude.yml`, `claude-code-review.yml` | Run `claude setup-token` locally and paste the result. |

```bash
gh secret set RELEASE_TOKEN
gh secret set CODECOV_TOKEN
gh secret set CLAUDE_CODE_OAUTH_TOKEN
```

`GITHUB_TOKEN` is auto-provided — no action needed.
````

- [ ] **Step 2: Replace the local-dev placeholder**

Replace `<!-- LOCAL DEV PLACEHOLDER -->` with:

````markdown
The PR gate (matches CI):

```bash
uv run pytest -x -q                                  # tests
uv run ruff check --fix . && uv run ruff format .    # lint + format
uv run mypy src/ tests/                              # type-check
```

Pre-commit runs a subset of the gate on each commit; see `.pre-commit-config.yaml` or `CLAUDE.md` for details. See [`CLAUDE.md`](CLAUDE.md) for the full Hard PR Acceptance Gates.
````

- [ ] **Step 3: Smoke render and verify**

```bash
grep 'RELEASE_TOKEN' /tmp/smoke/README.md
grep 'CODECOV_TOKEN' /tmp/smoke/README.md
grep 'CLAUDE_CODE_OAUTH_TOKEN' /tmp/smoke/README.md
grep 'Pre-commit runs a subset' /tmp/smoke/README.md
grep 'Hard PR Acceptance Gates' /tmp/smoke/README.md
```

- [ ] **Step 4: Commit**

```bash
git add README.md.jinja
git commit -m "docs(readme): preserve GitHub secrets and Local development sections (refs #57)

Carries forward the existing three-secret table and the PR-gate snippet
verbatim from the pre-expansion README — both are generic and don't
need domain editing. Local development section gains a one-liner
pointing at .pre-commit-config.yaml and the Hard PR Acceptance Gates
cross-reference."
```

---

## Task 10: Fill in Troubleshooting section (absorbs #52)

**Files:**
- Modify: `README.md.jinja` (replace `<!-- TROUBLESHOOTING PLACEHOLDER -->`)

- [ ] **Step 1: Replace the troubleshooting placeholder**

Replace `<!-- TROUBLESHOOTING PLACEHOLDER -->` with:

````markdown
### Moving a scaffolded project

`uv sync` creates `.venv/bin/*` scripts with absolute shebangs pointing at the venv Python. If you move the repo after scaffolding (`mv /old/path /new/path`), `uv run pytest` fails with `ModuleNotFoundError: No module named 'fastmcp'` because the stale shebang resolves to a different interpreter than the venv's site-packages.

**Fix:**

```bash
rm -rf .venv
uv sync --all-extras --dev
```

`uv run python -m pytest` also works as a one-shot workaround (bypasses the stale entry-script shim).

### `uv.lock` refresh after `copier update`

When `copier update` introduces new dependencies (e.g. a new extra added to `pyproject.toml.jinja`), CI runs `uv sync --frozen` which fails against a stale lockfile. Run `uv lock` locally and commit the refreshed `uv.lock` alongside accepting the copier-update PR.
````

- [ ] **Step 2: Smoke render and verify**

```bash
grep '^### Moving a scaffolded project$' /tmp/smoke/README.md
grep 'rm -rf .venv' /tmp/smoke/README.md
grep '^### `uv.lock` refresh' /tmp/smoke/README.md
grep 'uv sync --frozen' /tmp/smoke/README.md
```

- [ ] **Step 3: Commit**

```bash
git add README.md.jinja
git commit -m "docs(readme): add Troubleshooting section, absorbing #52 (closes #52, refs #57)

Two initial entries:
- 'Moving a scaffolded project' — absorbs #52; documents the rm -rf .venv
  recovery path plus the 'uv run python -m pytest' one-shot workaround.
- 'uv.lock refresh after copier update' — covers the downstream rollout
  footgun surfaced while rolling #62 (new docs extra vs uv sync --frozen)."
```

---

## Task 11: Fill in Links section

**Files:**
- Modify: `README.md.jinja` (replace `<!-- LINKS PLACEHOLDER -->`)

- [ ] **Step 1: Replace the links placeholder**

Replace `<!-- LINKS PLACEHOLDER -->` with:

```markdown
- [Documentation](https://{{ github_org }}.github.io/{{ project_name }}/)
- [llms.txt](https://{{ github_org }}.github.io/{{ project_name }}/llms.txt)
- [FastMCP](https://gofastmcp.com)
- [fastmcp-pvl-core](https://pypi.org/project/fastmcp-pvl-core/)
```

- [ ] **Step 2: Smoke render and verify**

```bash
grep 'gofastmcp.com' /tmp/smoke/README.md
grep 'pvliesdonk.github.io/smoke-mcp/llms.txt' /tmp/smoke/README.md
grep 'pypi.org/project/fastmcp-pvl-core' /tmp/smoke/README.md
```

- [ ] **Step 3: Commit**

```bash
git add README.md.jinja
git commit -m "docs(readme): preserve Links section + add llms.txt link (refs #57)

Existing three links (docs site, FastMCP, fastmcp-pvl-core) plus a new
llms.txt link matching the badge in the header row — the docs workflow
already publishes this file, so linking it here exposes the LLM-facing
documentation entry point."
```

---

## Task 12: Fill in Domain configuration DOMAIN block

**Files:**
- Modify: `README.md.jinja` (replace `<!-- DOMAIN CONFIG PLACEHOLDER -->`)

- [ ] **Step 1: Replace the domain-config placeholder**

Replace `<!-- DOMAIN CONFIG PLACEHOLDER -->` with:

````markdown
<!-- Replace with a table of domain-specific env vars. Kept across copier update. -->

Domain environment variables use the `{{ env_prefix }}_` prefix:

| Variable | Default | Required | Description |
|---|---|---|---|
| `{{ env_prefix }}_EXAMPLE_VAR` | — | **Yes** | Replace this row with your first required setting. |
| `{{ env_prefix }}_ANOTHER_VAR` | `default` | No | Replace with an optional setting. |

Domain-config fields are composed inside `src/{{ python_module }}/config.py` between the `CONFIG-FIELDS-START` / `CONFIG-FIELDS-END` sentinels; env reads go through `fastmcp_pvl_core.env(_ENV_PREFIX, "SUFFIX", default)` so naming stays consistent.
````

- [ ] **Step 2: Smoke render and verify**

```bash
grep 'SMOKE_MCP_EXAMPLE_VAR' /tmp/smoke/README.md  # env_prefix substitutes
grep 'src/smoke_mcp/config.py' /tmp/smoke/README.md
grep 'CONFIG-FIELDS-START' /tmp/smoke/README.md
```

- [ ] **Step 3: Commit**

```bash
git add README.md.jinja
git commit -m "docs(readme): ship Domain configuration DOMAIN block with env-var table stub (refs #57)

Placeholder table with two example rows (\"[EXAMPLE_VAR]\", \"[ANOTHER_VAR]\"),
plus a pointer at the CONFIG-FIELDS sentinels in config.py so implementers
know where to add fields. Mirrors the split in markdown-vault-mcp's README
(core vars table template-owned, domain vars table domain-owned)."
```

---

## Task 13: Fill in Key design decisions DOMAIN block

**Files:**
- Modify: `README.md.jinja` (replace `<!-- KEY DESIGN PLACEHOLDER -->`)

- [ ] **Step 1: Replace the key-design placeholder**

Replace `<!-- KEY DESIGN PLACEHOLDER -->` with:

```markdown
<!-- Document architectural decisions specific to this service. Kept across copier update. -->

_Replace this placeholder with a short list of the non-obvious design calls this service makes — e.g. "writes are append-only", "embeddings cached in SQLite", "auth uses OIDC bearer tokens". Three to six bullets is typically enough; link out to longer ADRs under `docs/decisions/` if you maintain any._
```

- [ ] **Step 2: Smoke render and verify**

```bash
grep '^## Key design decisions$' /tmp/smoke/README.md
grep 'non-obvious design calls' /tmp/smoke/README.md
```

- [ ] **Step 3: Commit**

```bash
git add README.md.jinja
git commit -m "docs(readme): ship Key design decisions DOMAIN block (refs #57)

Short placeholder prose explaining what belongs in this block ('non-obvious
design calls'), matching the Key Design Decisions DOMAIN block in
CLAUDE.md.jinja for consistency. Cross-references an optional
docs/decisions/ ADR folder."
```

---

## Task 14: Remove README.md from copier.yml _skip_if_exists

**Files:**
- Modify: `copier.yml` (remove the `"README.md"` line from `_skip_if_exists`)

**Rationale:** With sentinel blocks in place, the README now behaves like `CLAUDE.md.jinja` — template-owned sections re-render on `copier update`, DOMAIN blocks are preserved by the three-way merge. Staying in `_skip_if_exists` would defeat the whole point of the sentinel structure.

- [ ] **Step 1: Read copier.yml to locate the entry**

```bash
grep -n '"README.md"' copier.yml
```

Expected: one line in the `_skip_if_exists` block (currently line 33 per spec).

- [ ] **Step 2: Remove the `"README.md"` entry and add a note to nearby comment**

Delete the single `- "README.md"` line from `_skip_if_exists`. Update the adjacent explanatory comment (the block that lists files protected from update) to mention that `README.md` is deliberately NOT here — same rationale as the existing CLAUDE.md note a few lines below.

Find the existing comment block that ends with `# Note: CLAUDE.md is deliberately NOT in _skip_if_exists...`. Extend that note to also mention README.md:

```yaml
# Note: CLAUDE.md and README.md are deliberately NOT in _skip_if_exists —
# both are hybrid files with template-owned and domain-owned sections
# marked by sentinel blocks, and copier's 3-way merge needs to re-render
# the template-owned sections on update.
```

- [ ] **Step 3: Smoke render and verify README still renders**

Run the smoke-render command, then:

```bash
ls /tmp/smoke/README.md  # still exists
grep -c 'DOMAIN-START' /tmp/smoke/README.md  # still 4 (unchanged from before)
```

- [ ] **Step 4: Commit**

```bash
git add copier.yml
git commit -m "refactor(copier): remove README.md from _skip_if_exists now that sentinels are in place (refs #57)

With README.md.jinja carrying <!-- DOMAIN-START -->/<!-- DOMAIN-END -->
blocks wrapping template-owned sections (banner-delimited), copier's
three-way merge can now preserve domain edits while re-rendering
template-owned content on update — same contract CLAUDE.md.jinja
already uses.

Extend the adjacent comment so future readers see both files grouped
under the same rationale."
```

---

## Task 15: Round-trip verification — sentinels preserve and update correctly

**Files:** none (verification only)

**Rationale:** This is the critical behavioral test: confirm that `copier update` preserves DOMAIN-block edits while re-rendering template-owned sections.

- [ ] **Step 1: Seed a temp project from HEAD**

```bash
rm -rf /tmp/readme-roundtrip
uv run --no-project --with copier copier copy --trust --defaults --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/readme-roundtrip
cd /tmp/readme-roundtrip
git init -q
git add -A
git -c user.email=test@test -c user.name=test commit -q -m "initial seed"
```

- [ ] **Step 2: Simulate a domain edit inside a DOMAIN block**

Edit `/tmp/readme-roundtrip/README.md`: in the `## Features` section, replace the first placeholder bullet (`- **[Capability 1]** — one-sentence description of a user-visible feature.`) with:

```markdown
- **Domain edit** — this bullet should survive the next copier update.
```

Commit the edit:

```bash
cd /tmp/readme-roundtrip
git add README.md
git -c user.email=test@test -c user.name=test commit -q -m "domain: customise first feature bullet"
```

- [ ] **Step 3: Simulate a template-owned edit and commit on the template branch**

Back in `/mnt/code/fastmcp-server-template` (branch `feat/readme-template-expansion`), add a small extra entry to the Troubleshooting section:

```bash
cd /mnt/code/fastmcp-server-template
```

Edit `README.md.jinja` — under `## Troubleshooting`, after the second entry, add:

````markdown
### Round-trip sentinel test entry

This entry exists only to verify `copier update` re-renders the
template-owned troubleshooting section when running the plan's
round-trip step. Remove after verification.
````

Commit:

```bash
git add README.md.jinja
git commit -m "chore: temporary round-trip marker (will be reverted)"
```

- [ ] **Step 4: Run copier update against the seeded project**

```bash
cd /tmp/readme-roundtrip
uv run --no-project --with copier copier update --trust --defaults --vcs-ref=HEAD /mnt/code/fastmcp-server-template
```

Accept any merge prompts by keeping copier defaults (no overrides).

- [ ] **Step 5: Verify both outcomes**

```bash
# DOMAIN edit preserved:
grep 'Domain edit.*should survive' /tmp/readme-roundtrip/README.md && echo "DOMAIN preserved OK"

# Template-owned update applied:
grep 'Round-trip sentinel test entry' /tmp/readme-roundtrip/README.md && echo "TEMPLATE updated OK"
```

Both echoes must print. If either fails, investigate and fix before continuing.

- [ ] **Step 6: Revert the temporary round-trip marker commit**

Back in the template repo:

```bash
cd /mnt/code/fastmcp-server-template
git reset --hard HEAD~1   # drop the "chore: temporary round-trip marker" commit
```

Verify:

```bash
git log --oneline -5  # HEAD should be the Task 14 commit
```

- [ ] **Step 7: Clean up the temp project**

```bash
rm -rf /tmp/readme-roundtrip
```

- [ ] **Step 8: No commit for this task** — it's verification only; the temporary commit was reverted in step 6.

---

## Task 16: Full gate on the rendered project

**Files:** none (verification only)

- [ ] **Step 1: Smoke render at HEAD and run the full downstream gate**

```bash
rm -rf /tmp/smoke && uv run --no-project --with copier copier copy --trust --defaults --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
cd /tmp/smoke
uv sync --all-extras --dev
```

- [ ] **Step 2: Run each gate step**

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src/ tests/
uv run pytest -x -q
uv run mkdocs build --strict
```

Expected: all green.

- [ ] **Step 3: Spot-check the rendered README**

```bash
wc -l /tmp/smoke/README.md  # expect: substantially more than the 63-line original, around 200-250 lines
grep -c '{{' /tmp/smoke/README.md  # expect: 0 (no unrendered Jinja braces)
grep -c '{%' /tmp/smoke/README.md  # expect: 0
```

If any unrendered Jinja braces show, find and fix.

- [ ] **Step 4: No commit** — verification only.

---

## Self-review checklist

After all tasks pass:

- **Spec coverage:** every section in the spec's "Section list" table (14 items) → has a task. Badge row (Task 2), Features (3), What-you-can-do (4), Installation (5), Quick start (6), Configuration (7), Post-scaffold checklist (8), GitHub secrets + Local dev (9), Troubleshooting (10), Links (11), Domain configuration (12), Key design decisions (13), copier.yml (14). ✓
- **#52 absorption:** Task 10 explicitly `closes #52`. ✓
- **Placeholder check:** all `[Capability N]`, `[Task N]`, `[EXAMPLE_VAR]`, `[ANOTHER_VAR]` tokens in the README are intentional DOMAIN placeholders for downstream users; they are not plan TODOs. No actual plan-level placeholders.
- **Consistency:** Jinja variables used across tasks (`{{ github_org }}`, `{{ project_name }}`, `{{ pypi_name }}`, `{{ python_module }}`, `{{ env_prefix }}`, `{{ human_name }}`, `{{ domain_description }}`) match the names in `copier.yml`.

---

## Post-plan: PR flow

After Task 16 passes:

1. Push the branch: `git -C /mnt/code/fastmcp-server-template push -u origin feat/readme-template-expansion`.
2. Open draft PR with `Closes #57, closes #52` in the body.
3. Run `/pr-review-toolkit:review-pr` on the draft (per the personal CLAUDE.md rule updated in this session).
4. Address findings. Push fixes.
5. Mark ready. Wait for CI + bot reviewer. Iterate per auto-mode rule until green.
6. Human merges.
