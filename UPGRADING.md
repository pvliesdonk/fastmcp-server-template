# Upgrading generated projects

This guide is for maintainers updating a generated project with
`copier update`. It starts at template v1.0.0 and records the manual work that
Copier cannot do: preserving project-owned files, migrating removed extension
points, changing repository settings, and checking operational behavior.

Contributors (when a note is needed: "Writing UPGRADING.md" in `CLAUDE.md`):
write the note under `## Unreleased`, the last section, replacing the
`_Nothing yet._` placeholder, and title it `## Unreleased - <short title>`.
Never write under a version heading or into `upgrading/`;
`scripts/promote_upgrading.py` moves the section at release time. Run
`python3 scripts/promote_upgrading.py --check` before pushing.

This file is the index: each released minor's section below is a one-line
pointer to that minor's file under [`upgrading/`](upgrading/), which holds
its full steps. Read each applicable file whole, not by grep or tail. Start
with your current minor's file when your target includes a newer patch in
that line (a project on v1.2.0 needs the v1.2 file for v1.2.1 and v1.2.2),
then read every later minor's file through the target. Update straight to
the newest patch of the newest minor unless you are diagnosing an
intermediate change.

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

Copier seeds the files in `_skip_if_exists` once and never updates an
existing copy, so a later template correction to one reaches your project
only by hand. Some newer config files are both skip-listed and
generator-owned; the generator, not Copier, rewrites those files.

For a target of v6.0.0 or later, the update writes
`.copier-seeded-changes.md` with the template's changes to every
skip-listed file; read it. For an earlier target, or when that report says
it could not be computed, render the target with your own answers and
compare the files Copier will not touch:

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

`_skip_if_exists` in the template's `copier.yml` is the full list. Skip the
entries that are yours by construction (`tools.py`, `resources.py`,
`prompts.py`, `domain.py`, the seeded tests, `CHANGELOG.md`,
`docs/releases/`, `LICENSE`). Diff the ones the template still authors
content for, where a change is a correction rather than your own work:

- `.vale/styles/config/vocabularies/Base/accept.txt` — for targets before
  the template's own vocabulary moved to the re-rendered
  `vocabularies/Template/accept.txt` (template#366), template prose arriving
  in a release could need terms the seeded file lacks;
- `.claude-plugin/**` — the plugin scaffold and its README;
- `packaging/mcpb/` — `manifest.json.in`, `pyproject.toml.in`, `build.sh` and
  the entry shim, which track the mcpb CLI and manifest version;
- `.gitignore`, `.vale.ini`, `config-presentation.domain.yml`.

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

## v11.1 - documentation structure contract

Steps: [upgrading/v11.1.md](upgrading/v11.1.md).

## v11.2 - Pushes require a recorded self-review

Steps: [upgrading/v11.2.md](upgrading/v11.2.md).

## Unreleased - copier update leaves the generated reference pages alone

`copier update` no longer writes any page under `docs/reference/` that
`scripts/gen_reference.py` owns: the tool pages, `resources.md`,
`prompts.md` and `cli.md`.

- A project that removed the scaffold's `docs/reference/tools/tools.md` or
  `server_apps.md` after an earlier update has nothing to do; the update
  stops adding them back.
- A project updating from before v11.1 gets no reference pages from the
  update. Run `uv run python scripts/gen_reference.py` and commit
  `docs/reference/` and `mkdocs.yml`, as v11.1's steps say. The docs
  build fails until you do.
