# Agent-neutral instruction surface design

**Date:** 2026-08-25
**Closes:** #484 (rendered CLAUDE.md exceeds Claude Code's 40k-char limit),
#485 (no AGENTS.md for other agents), #486 (skills are Claude-only)
**Does not cover:** #496 (provider-neutral code-review skill), prose rewrites
beyond trimming, Windows symlink support.

## Problem

The template renders one always-loaded instruction file, `CLAUDE.md`, and it
is too large and too Claude-specific:

- Template-owned prose alone is ~48.6k characters (smoke render), over
  Claude Code's 40k warning threshold before any domain content. The largest
  downstream (markdown-vault-mcp) renders at 59k. No downstream can fix this
  locally because copier re-renders everything outside the DOMAIN blocks.
- Only Claude Code reads `CLAUDE.md`. Agents that read the AAIF `AGENTS.md`
  standard (Cursor, Codex, Aider, goose, opencode, Zed, VS Code, ...) get no
  project instructions.
- The template's contributor skill `authoring-issues-prs` lives under
  `.claude/skills/`, which only Claude Code scans. `writing-release-notes`
  already moved to `.agents/skills/` (#498) but Claude Code cannot see it
  there.

## Verified facts the design rests on

| Fact | How verified |
|---|---|
| Claude Code expands `@path` imports in full at launch; an import-based split saves no context. | code.claude.com/docs/en/memory ("imported files are expanded and loaded into context at launch") |
| Claude Code 2.1.245 does **not** scan `.agents/skills/` natively. | Probe: a skill placed only in `.agents/skills/` was not listed by `claude -p`. |
| Claude Code follows a `.claude/skills/<name>` symlink whose target is a directory under `.agents/skills/`. | Same probe: the symlinked skill was listed. |
| Skills load lazily: name/description at launch, body on invocation. | code.claude.com/docs/en/context-window |
| copier 9.17.2 with `_preserve_symlinks: true` keeps relative symlinks through `copier copy` **and** `copier update`. | Probe: two-tag mini template, update with a deliberate local conflict; link intact. |
| The template already runs a `_migrations` entry at the end of every `copier update`, after the old-render → project diff has restored project content. | `copier.yml` (`_migrations: python scripts/gen_config_surface.py`). |
| Downstream `copier-update.yml` runs `--conflict=inline`; the pre-update `CLAUDE.md` is at the project's git `HEAD` while the migration runs. | `.github/workflows/copier-update.yml.jinja` |
| `scripts/check_render_hygiene.py` skips symlinks. | `check_render_hygiene.py:151` |

## Design

### 1. `AGENTS.md` is the canonical always-loaded file

`AGENTS.md.jinja` replaces `CLAUDE.md.jinja` as the file carrying project
instructions. It keeps CLAUDE.md's exact structure so every existing
mechanism keeps working with a path change only:

- both `<!-- DOMAIN-START/END -->` blocks;
- the three `<!-- TEMPLATE-TRACKING-START/END -->` blocks;
- the `TEMPLATE-OWNED SECTIONS BELOW / END` fences.

Sections that must be present on every turn stay: Design, Project Structure,
Conventions (verbatim prose asserted by `tests/test_commit_conventions.py`),
Breaking Changes and the `!` marker, Hard PR Acceptance Gates, Pre-commit
Hooks, Structural health (grepped by the structural-gate test and the detach
scrub), PR Discipline merged with GitHub Review Types, Documentation
Discipline merged with Documentation Conventions, Shared Infrastructure
merged with Contributing fixes upstream, Key Design Decisions.

A new **Skills** section lists every template-owned skill with one line on
when to invoke it explicitly — e.g. "before any release work, invoke
`releasing`". Skills load only on invocation, so this section is the
discoverability contract; it replaces the prose that used to be inline.

Budget: the smoke render's `AGENTS.md` must stay ≤ 24 000 characters. That
leaves ≥ 16k for domain content under the 40k warning; the largest current
downstream uses ~10k.

### 2. `CLAUDE.md` becomes a template-owned stub

```markdown
@AGENTS.md

Project instructions live in `AGENTS.md` (domain content between its
`DOMAIN-START` / `DOMAIN-END` markers). This file is template-owned; do not
add content here.
```

No sentinels, no domain content. Claude Code loads exactly what other agents
read, and its 40k warning measures the same bytes.

### 3. Task-shaped sections become portable skills

Each skill is `.agents/skills/<name>/SKILL.md.jinja` (template-owned,
re-rendered on every update — **not** `_skip_if_exists`), with frontmatter
`name: <name>` (equal to the directory) and a `description` that states when
to use it. For each, `.claude/skills/<name>` is a relative symlink to
`../../.agents/skills/<name>` so Claude Code discovers it. `copier.yml` gains
`_preserve_symlinks: true`.

| Skill | Sections moved from CLAUDE.md | ≈ chars |
|---|---|---|
| `releasing` | Release model; Unstable channel; Release machinery (prepare, release PRs, promotion); Release notes pages; Pre-release artifact smoke test; Claude Code plugin channel | 15k |
| `config-contract` | Config & Customization Contract, incl. Config wizard, mcpb install screen, Dockerfile extension points, Release manifest extension points | 7k |
| `logging-standard` | Logging Standard | 2.8k |
| `tool-registration` | Tool Registration Checklist; Server Info Tool; Tool icons; Public import surface guard | 4k |
| `repository-protection` | Repository protection (rulesets) | 1.7k |

Existing skills: `authoring-issues-prs` moves from `.claude/skills/` to
`.agents/skills/` and gets a symlink; `writing-release-notes` (already under
`.agents/`) gets a symlink. `.claude/skills/` then contains symlinks only —
project-owned skills follow the same shape.

Content moves **verbatim** in one commit and is trimmed in a separate
commit, so the move is reviewable as a pure relocation.

References inside moved prose (`CONTRIBUTING.md`, issue forms, `CLAUDE.md`
mentions in tests and workflows) are repointed in the same change.

### 4. Migration on `copier update`

`scripts/migrate_agent_instructions.py`, run from `_migrations` (after-stage,
every update, alongside `gen_config_surface.py`), makes the common case
hands-off:

1. If `AGENTS.md` exists with **empty** DOMAIN blocks and
   `git show HEAD:CLAUDE.md` contains **populated** DOMAIN blocks, splice
   that content into `AGENTS.md`'s corresponding blocks (by ordinal: first
   block to first block, second to second).
2. Overwrite `CLAUDE.md` with the rendered stub. Copier's inline conflict
   markers in `CLAUDE.md` are discarded deliberately — the stub is the whole
   file, and the domain content was already rescued from `HEAD` in step 1.
3. If `.claude/skills/<name>` exists as a real directory where the template
   ships a symlink, remove the directory so the symlink can land (copier
   writes the symlink in the render stage; the migration reconciles the
   leftover).
4. Print one line per action taken, and, if `HEAD:CLAUDE.md` differs from the
   template's previous render **outside** the DOMAIN blocks, print a pointer
   to `git diff HEAD -- CLAUDE.md` so a maintainer can re-apply hand edits
   to `AGENTS.md` — this is the only case that needs a human.

The script is idempotent (re-running after migration is a no-op) and does
nothing on a fresh `copier copy` (no `HEAD:CLAUDE.md`).

`UPGRADING.md` ("Unreleased") documents: what the migration does, the
hand-edit exception, and that `.gitignore` already needs the `!.agents/skills/`
and `!.claude/skills/` exceptions (seeded-once file; both notes already exist
from earlier releases).

**Addendum (post-implementation).** Step 3's after-stage migration alone was
not enough: copier 9.17 crashes with an `IsADirectoryError` out of
`Worker._render_allowed` when a rendered symlink lands on a real directory,
non-atomically and *before* `_migrations` ever runs. The fix is a
**before-stage** `_migrations` shell guard in `copier.yml` that removes the
seven template-owned real directories first, so the render can lay the
symlink down; the after-stage symlink reconciliation above stays as
belt-and-braces. Copier also skips *all* migrations, both stages, when
either the destination's or the template's recorded commit fails to resolve
to a version (a bare-hash `_commit`) — `UPGRADING.md` covers that case with
a manual step. The before-stage guard carries no `version:` window
deliberately: the release is chosen at dispatch time, and once every
downstream has migrated once it is a steady-state no-op anyway.

### 5. Guards

Template side (`template-ci`, `scripts/tests/`):

- smoke render `AGENTS.md` ≤ 24 000 characters;
- every template-owned `.agents/skills/<name>` has `.claude/skills/<name>` as
  a symlink resolving to it, and every other entry under `.claude/skills/` is
  a symlink into `.agents/skills/` (no real directories);
- every `SKILL.md` frontmatter parses, `name` equals its directory,
  `description` is non-empty;
- `CLAUDE.md` render equals the stub;
- the existing sentinel-structure, detach-scrub anchor, and Vale checks are
  repointed from `CLAUDE.md` to `AGENTS.md`;
- the migration script has unit tests against a fixture that mimics a real
  downstream (populated DOMAIN blocks, a real `.claude/skills/` directory, a
  hand-edited line outside sentinels).

Rendered side (`tests/test_agent_instructions.py.jinja`, template-owned):

- `AGENTS.md` ≤ 40 000 characters, failure message names the DOMAIN block as
  the lever;
- `CLAUDE.md` is the stub;
- each `.claude/skills/*` symlink resolves into `.agents/skills/`.

Existing tests keep their assertions and change only the path they read:
`test_commit_conventions.py.jinja`, `test_structural_gate.py.jinja`,
`test_release_flow_contract.py.jinja` docstrings, `scripts/tests/test_claude_review_gating.py`,
`scripts/tests/test_shared_skill_paths.py`.

## Ownership summary

| Path | Owner | On `copier update` |
|---|---|---|
| `AGENTS.md` | template outside DOMAIN blocks; project inside | re-rendered; DOMAIN content restored by copier's diff |
| `CLAUDE.md` | template | re-rendered (stub) |
| `.agents/skills/<template skill>/` | template | re-rendered |
| `.claude/skills/<name>` (symlink) | template | re-rendered |
| `.agents/skills/<project skill>/` | project | untouched (not in template) |

Projects add their own skills under `.agents/skills/` with their own
symlinks; template guards only inspect template-owned names.

## Risks and mitigations

- **Migration corrupts a downstream.** Mitigated by fixture tests, idempotence,
  `HEAD`-based recovery (never the conflict-marked file), and the diff pointer
  for the hand-edit case.
- **Lazy skills are not read when needed.** Mitigated by the explicit Skills
  section in `AGENTS.md`; this is the documented Claude Code recommendation
  for large instruction sets.
- **Symlinks on Windows checkouts.** Out of scope; the fleet runs Linux CI and
  Linux/macOS developer machines. Noted in `AGENTS.md`'s Skills section.
- **Detach scrub drift.** Anchor counts are re-derived once and the existing
  drift check keeps them coupled.

## Sequencing

1. Add `AGENTS.md.jinja` as a verbatim copy of `CLAUDE.md.jinja`; stub
   `CLAUDE.md.jinja`; repoint every reader. Gate green.
2. Move sections into skills verbatim; add symlinks and
   `_preserve_symlinks`; move `authoring-issues-prs`. Gate green.
3. Add guards (template + rendered) and the migration script with tests.
4. Trim prose in `AGENTS.md` to the 24k budget; write the Skills section.
5. `UPGRADING.md` note; release notes.

One PR, commits in this order, so each step is reviewable.
