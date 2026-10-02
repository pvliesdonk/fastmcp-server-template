# Upgrading generated projects

This guide is for maintainers updating a generated project with
`copier update`. It starts at template v1.0.0 and records the manual work that
Copier cannot do: preserving project-owned files, migrating removed extension
points, changing repository settings, and checking operational behavior.

Contributors: record migration steps under `## Unreleased` at the end of this
file, never under a version heading — the version is chosen at release time,
and `scripts/promote_upgrading.py` moves the section into its minor's file
then. See "Writing UPGRADING.md" in `CLAUDE.md`.

This file is the index: each released minor's section below is a one-line
pointer, and the full migration steps live in that minor's own file under
[`upgrading/`](upgrading/). Read the files whole — each one is complete for
its minor, and a partial read (a grep, a tail) of a combined document is how
migration steps get missed. Read the current minor's file when your target
includes a newer patch in that line, then every later minor's file through
the target. This matters for a project on v1.2.0: v1.2.1 and v1.2.2 contain
migration work recorded in the v1.2 file. Unless you need to diagnose an
intermediate change, update straight to the newest patch of the newest minor
rather than stopping on an early patch.

## Before every upgrade

1. Read every applicable minor's file under `upgrading/` before running
   Copier. Complete all
   steps marked **before updating**, **rescue**, **copy**, **preserve**, or
   **inventory** first. For a v1.x-to-current jump, this includes File Exchange
   code, the old MCP Apps implementation, config-surface metadata, MCPB install
   objects, and release-manifest stamping logic. A single direct update can
   delete or regenerate all five. A pre-v3.2.2 manifest bumper has no extension
   markers, so preserve all project-specific logic from that script.
2. Commit or back up the project, including ignored and skip-listed files.
3. Read `.copier-answers.yml` and set new answers deliberately. Automated
   updates commonly use `--skip-answered`, which accepts new defaults.
4. Rescue custom content from any file or sentinel that a section says is
   removed. Copier deletes a removed template-owned file, including downstream
   content inside it.
5. Run the update with the project version of the normal Copier command. Trust
   the template when prompted: later versions run generation and vendoring
   tasks.
6. Resolve conflicts by ownership. Preserve domain content inside the current
   `DOMAIN-*` or `PROJECT-*` blocks and accept template changes outside them.
   The markers are conventions; Copier uses an ordinary three-way merge.
7. Review and commit intentional lockfile changes with `uv lock`, then search
   for unresolved conflicts and check the resulting tree:

   ```bash
   git diff --check
   git grep -nE '^(<<<<<<<|=======|>>>>>>>)'
   uv lock --check
   uv sync --all-extras --all-groups --locked
   uv run ruff check .
   uv run ruff format --check .
   uv run mypy src/ tests/
   uv run pytest -x -q
   uv run mkdocs build --strict
   uv run pre-commit run --all-files
   ```

   For a v3+ target, also run
   `python scripts/gen_config_surface.py --check`. For an MCP Apps project, run
   `python scripts/vendor_spa.py --check`. Run the Vale and browser checks when
   the relevant sections below introduce them.

Files in `_skip_if_exists` need special attention. Copier seeds them once and
then leaves them under project ownership. Later template corrections do not
reach an existing copy. Some newer config files are both skip-listed and
generator-owned; the generator, not Copier, rewrites those files.

Nothing surfaces that gap for you. A skip-listed file never appears in a
`copier update` diff, and the update pull request lists it among the regions
to leave alone, so a template improvement to one can sit unadopted for
releases without anything saying so. Check for it deliberately, by rendering
the target with your own answers and comparing the files Copier will not
touch:

```bash
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=<target> --data-file .copier-answers.yml \
  gh:pvliesdonk/fastmcp-server-template /tmp/target-render

diff -r /tmp/target-render/.vale/styles/config/vocabularies \
        .vale/styles/config/vocabularies
diff -r /tmp/target-render/.claude-plugin .claude-plugin
```

Then adopt what the template authored and keep what you wrote; this is a read
and a decision, not a wholesale copy.

`_skip_if_exists` in the template's `copier.yml` is the full list. Most of it
is yours by construction and will differ every time, which is why a blanket
diff of all of it is noise: `tools.py`, `resources.py`, `prompts.py`,
`domain.py`, the seeded tests, `CHANGELOG.md`, `docs/releases/`, `LICENSE`.
The entries worth reading a diff of are the ones the template still authors
content for, where a change is a correction rather than your own work:

- `.vale/styles/config/vocabularies/Base/accept.txt` — for targets before
  the template's own vocabulary moved to the re-rendered
  `vocabularies/Template/accept.txt` (template#366), template prose arriving
  in a release could need terms the seeded file lacks;
- `.claude-plugin/**` — the plugin scaffold and its README;
- `packaging/mcpb/` — `manifest.json.in`, `pyproject.toml.in`, `build.sh` and
  the entry shim, which track the mcpb CLI and manifest version;
- `.gitignore`, `.vale.ini`, `config-presentation.domain.yml`.

How much this matters depends on how far behind you are, and it is worth
knowing that it is often nothing. Between v5.0.0 and v5.6.1 no skip-listed
file changed at all; from v4.0.0 the set is two files. A v3.x jump is the one
that carries real content.

## v1.0 - Copier foundation and initial packaging

Steps: [upgrading/v1.0.md](upgrading/v1.0.md).

## v1.1 - Automated Copier updates and extension sentinels

Steps: [upgrading/v1.1.md](upgrading/v1.1.md).

## v1.2 - README ownership, pre-commit, and dependency groups

Steps: [upgrading/v1.2.md](upgrading/v1.2.md).

## v1.3 - Server wiring sentinels

Steps: [upgrading/v1.3.md](upgrading/v1.3.md).

## v1.4 - Shared docs become template-owned

Steps: [upgrading/v1.4.md](upgrading/v1.4.md).

## v1.5 - pvl-core 2, docs ownership, authorization, and debugging

Steps: [upgrading/v1.5.md](upgrading/v1.5.md).

## v1.6 - File Exchange upload extension

Steps: [upgrading/v1.6.md](upgrading/v1.6.md).

## v1.7 - Repeated release candidates

Steps: [upgrading/v1.7.md](upgrading/v1.7.md).

## v1.8 - Vale prose linting

Steps: [upgrading/v1.8.md](upgrading/v1.8.md).

## v2.0 - pvl-core 3 and File Exchange removal

Steps: [upgrading/v2.0.md](upgrading/v2.0.md).

## v2.1 - MCP Apps choice and versioned documentation

Steps: [upgrading/v2.1.md](upgrading/v2.1.md).

## v2.2 - Initial configuration wizard

Steps: [upgrading/v2.2.md](upgrading/v2.2.md).

## v2.3 - Wizard ownership boundary

Steps: [upgrading/v2.3.md](upgrading/v2.3.md).

## v2.4 - Authorization becomes a Copier choice

Steps: [upgrading/v2.4.md](upgrading/v2.4.md).

## v2.5 - pvl-core 4 authorization and clean detach

Steps: [upgrading/v2.5.md](upgrading/v2.5.md).

## v2.6 - Complete wizard coverage and HTTP bind default

Steps: [upgrading/v2.6.md](upgrading/v2.6.md).

## v2.7 - Structural gate and real MCP Apps vendoring

Steps: [upgrading/v2.7.md](upgrading/v2.7.md).

## v2.8 - Recursive config discovery

Steps: [upgrading/v2.8.md](upgrading/v2.8.md).

## v2.9 - CLI command extension point

Steps: [upgrading/v2.9.md](upgrading/v2.9.md).

## v2.10 - Brownfield gate choice and Apps SDK update

Steps: [upgrading/v2.10.md](upgrading/v2.10.md).

## v2.11 - Renovate and repository bootstrap

Steps: [upgrading/v2.11.md](upgrading/v2.11.md).

## v3.0 - Generated configuration surfaces

Steps: [upgrading/v3.0.md](upgrading/v3.0.md).

## v3.1 - Safe post-update generation and release lockfile

Steps: [upgrading/v3.1.md](upgrading/v3.1.md).

## v3.2 - Tool visibility and manifest bumper ownership

Steps: [upgrading/v3.2.md](upgrading/v3.2.md).

## v3.3 - Background-task backend

Steps: [upgrading/v3.3.md](upgrading/v3.3.md).

## v3.4 - Generated MCPB install configuration

Steps: [upgrading/v3.4.md](upgrading/v3.4.md).

## v3.5 - Claude Code plugin scaffold

Steps: [upgrading/v3.5.md](upgrading/v3.5.md).

## v3.6 - Generated Claude plugin configuration

Steps: [upgrading/v3.6.md](upgrading/v3.6.md).

## v4.0 - Release branches, rulesets, and release notes

Steps: [upgrading/v4.0.md](upgrading/v4.0.md).

## v4.1 - Pull-request title gate and committed manifest checks

Steps: [upgrading/v4.1.md](upgrading/v4.1.md).

## v5.0 - PSR to knope release pull requests

Steps: [upgrading/v5.0.md](upgrading/v5.0.md).

## v5.1 - Release notes move into the release pull request

Steps: [upgrading/v5.1.md](upgrading/v5.1.md).

## v5.2 - Rolling `rc` image tag and the marketplace manifest path

Steps: [upgrading/v5.2.md](upgrading/v5.2.md).

## v5.3 - pvl-core 4.11.3 and advertised OIDC scopes

Steps: [upgrading/v5.3.md](upgrading/v5.3.md).

## v5.6 - Release candidates publish to PyPI, an installable plugin zip, and stricter config-surface and manifest checks

Steps: [upgrading/v5.6.md](upgrading/v5.6.md).

## v6.0 - fastmcp-pvl-core 5 and composed instructions

Steps: [upgrading/v6.0.md](upgrading/v6.0.md).

## v6.1 - Generated configuration reference, curated README tables

Steps: [upgrading/v6.1.md](upgrading/v6.1.md).

## v7.0

Steps: [upgrading/v7.0.md](upgrading/v7.0.md).

## v8.0

Steps: [upgrading/v8.0.md](upgrading/v8.0.md).

## v8.1 - Health routes, the compose probe, and merge-commit port PRs

Steps: [upgrading/v8.1.md](upgrading/v8.1.md).

## v8.2 - Container logs and roadmapping convention

Steps: [upgrading/v8.2.md](upgrading/v8.2.md).

## v9.0 - pvl-core v8 and v9, security policy and enforced log-call grammar

Steps: [upgrading/v9.0.md](upgrading/v9.0.md).

## v9.1 - The `code-review` skill is now `self-reviewing`

Steps: [upgrading/v9.1.md](upgrading/v9.1.md).

## v9.2 - Project classifiers seam, Python 3.14 classifier, pre-push conformance hook

Steps: [upgrading/v9.2.md](upgrading/v9.2.md).

## v9.3 - Repository About block from pyproject, compose publishes on loopback, security-model page

Steps: [upgrading/v9.3.md](upgrading/v9.3.md).

## v10.0 - pvl-core v10 and the tool boundary

Steps: [upgrading/v10.0.md](upgrading/v10.0.md).

## v10.3 - Required config variables and `ConfigurationError` validation

Steps: [upgrading/v10.3.md](upgrading/v10.3.md).

## v11.0 - SonarQube Cloud takes over coverage from Codecov

Steps: [upgrading/v11.0.md](upgrading/v11.0.md).

## Unreleased - documentation structure contract

### Documentation structure contract and `writing-documentation` skill

`copier update` adds `docs/contribute/docs-structure.md` and the `writing-documentation` skill. Your `nav:` and `llmstxt` sections are project-owned, so the new page isn't linked until you add it:

1. In `mkdocs.yml`, inside `PROJECT-NAV-START/END`, add a last section:
   `- Contribute:` with `- Documentation structure: contribute/docs-structure.md`.
2. Inside `PROJECT-LLMSTXT-SECTIONS-START/END`, add `Contribute:` with `- contribute/*.md`.

The page states which documentation belongs to your project and which to the template. Pages it classifies as misplaced aren't moved by this update.

### Sections in the docs navigation

The template now owns the frame of `nav:` in `mkdocs.yml`: eight sections by what the reader is trying to do (Overview, Security model, Get started, Deploy, Use, Reference, Upgrade, Contribute), with a slot in each for your own pages. Template pages keep their file paths, so no URL changes.

`copier update` rebuilds `nav:` on the new frame. Every entry you had added to your old navigation is moved under **Unsorted** at the end of `nav:`, keeping its section title; entries for template pages are dropped, because the frame lists them, and so is any title you had given a template page (the frame titles its own pages). When the migration can't do this safely, it leaves copier's conflict in place and prints why. Then:

1. Move each entry under Unsorted into the `PROJECT-NAV-<SECTION>-START/END` block of the section whose reader it serves. `docs/contribute/docs-structure.md` lists the sections and what goes where; your own how-to and feature pages belong in Use (`docs/use/`).
2. Delete the emptied `Guides:`-style headings left under Unsorted, and run `uv run mkdocs build --strict`.
3. `git add mkdocs.yml`: the update leaves it marked as conflicted even though its content is resolved.

`mkdocs-redirects` joins the docs dependency group. Run `uv lock` and commit `uv.lock`: the docs workflow installs from the lock (`uv sync --frozen`), so the docs build fails until the lock has it. If you move one of your own pages while sorting, add an `old.md: new.md` entry to the new `redirects` block in `mkdocs.yml` so its published URL keeps working.

### llms.txt built from the navigation

`llms.txt` is now generated from `nav:` when the site builds, by `scripts/llmstxt_sections_hook.py`. The `PROJECT-LLMSTXT-SECTIONS` block in `mkdocs.yml` is gone: `copier update` resolves the conflict it leaves to the template side, and the entries and descriptions you kept there are dropped.

The hook is registered under a new top-level `hooks:` key in `mkdocs.yml`. If you already have a `hooks:` list, copier leaves a conflict there: keep your entries and add `scripts/llmstxt_sections_hook.py` to them.

Each page's line in `llms.txt` now comes from its own front matter. Add to every page you own:

```yaml
---
description: "One sentence on what the page is for."
kind: how-to
---
```

`kind` is `tutorial`, `how-to`, `reference` or `explanation`; `docs/contribute/docs-structure.md` says which fits each section. A page without `description:` is listed without one.

### Documentation structure check

`scripts/check_docs_structure.py` now runs in pre-commit and in the docs workflow. Errors fail from the first run: links to pages the site doesn't serve (`exclude_docs` drops them, or they sit outside `docs/`), published pages neither the nav nor `llms.txt` reaches, and a template entry page without its security-model link. Fix those before merging the update. Warnings (pages outside the designated places, missing `description:`/`kind:` front matter, entries under Unsorted) print without failing. Once they're gone, set `strict = true` under `[tool.docs-structure]` in `pyproject.toml` so new debt fails too.

### Reference generated from the code

The Reference section moved under `docs/reference/`, and its tool, resource, prompt and command-line pages are now written by `scripts/gen_reference.py` from what the server registers; the template's redirects keep the old URLs working. The update deletes `docs/configuration.md`, `docs/configuration-generator.md`, `docs/tools/index.md` and `docs/prompts.md`; `scripts/migrate_docs_reference.py` carries the `DOMAIN-CONFIG-VARS` block of the old configuration page into `docs/reference/configuration.md`, and restores a tools or prompts page that held this project's own text as a parked page. The update is finished only when these steps are done:

1. Run `uv run python scripts/gen_reference.py`. It writes `docs/reference/` from the code and fills the `GENERATED-NAV-TOOLS` region of `nav:`. Pre-commit and CI fail while a page is stale.
2. Tools group by the module that registers them. Where that is not the right page, add a `group:<slug>` tag (`tags={"group:reading"}`) to the tool and regenerate.
3. Move every example from the parked `docs/tools/index.md` and `docs/prompts.md` into the `DOMAIN-EXAMPLE-<name>` slot of its tool or prompt, and every piece of task guidance into a page under `docs/use/`; then delete the parked page. `scripts/check_docs_structure.py` reports E2 on a parked page until it is gone, and its old URL shows the parked page instead of the redirect.
4. `Returns:` and `Raises:` sections of tool docstrings are published now, so Vale lints them; fix the docstring, never the page. Identifiers in docstring prose render as code.
5. A project whose `from_env` requires variables the scaffold does not sets them under `[tool.docs-reference] env` in `pyproject.toml` (the `PROJECT-DOCS-CHECKS` block), so the generator can build the server.

### Published examples are tested

`tests/test_published_examples.py` (template-owned) checks the fenced blocks on every published page and `README.md`. From the first run it fails a shell block with an unquoted package extra (`pip install pkg[extra]`): quote it, `"pkg[extra]"`. Then tag the examples that make a claim: ```` ```python { .run data-expect="results" } ```` for a block a reader runs (add a `docs_example_substitutions` fixture to `tests/conftest.py` that maps placeholder paths to fixtures), ```` ```json { .config data-expect="read_only=True" } ```` for a configuration that claims something (a dotenv-shaped shell block takes the same tag), ```` ```python { .fragment } ```` for a snippet. A Python block with neither tag is W4 in the structure check: debt, failing only in strict mode. The tags render as CSS classes and attributes, invisible to readers.
