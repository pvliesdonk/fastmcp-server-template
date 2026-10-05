# fastmcp-server-template

This repo is the [copier](https://copier.readthedocs.io/) template for
FastMCP servers on `fastmcp-pvl-core`; this file covers work on the template
itself.  Put guidance for a generated project's agents in `AGENTS.md.jinja`,
and keep `CLAUDE.md.jinja` the three-line `@AGENTS.md` stub.

## What renders where

- Edit `X.jinja` to change the generated project's `X`.  A plain file beside
  a `.jinja` of the same name (`CLAUDE.md`, `SECURITY.md`, `pyproject.toml`,
  `sonar-project.properties`) is this repo's own and never renders.
- Every other plain file outside `copier.yml`'s `_exclude` and
  `_skip_if_exists` (`CONTRIBUTING.md`, the skills, the shipped scripts and
  tests) ships verbatim and is re-rendered on `copier update`; write it for
  the downstream reader.  A `_skip_if_exists` file is seeded once and
  never reaches an existing project again.
- Run this repo's tools with `uv run --locked`.
- Change `ruff.toml`, which lints `scripts/`, together with the
  `[tool.ruff]` block in `pyproject.toml.jinja`.
- Adding, renaming or removing a template skill touches four name lists and
  a symlink; `scripts/tests/test_shared_skill_paths.py` names each.

## Making changes

1. Edit the relevant `.jinja` file(s).
2. Commit.  Copier renders from the git index, so it ignores uncommitted
   changes.
3. Render locally:
   ```bash
   rm -rf /tmp/smoke
   uv run --locked copier copy --trust --defaults \
     --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
   ```
   Keep `--vcs-ref=HEAD`; without it copier renders the latest tag.  To
   iterate, amend the commit or add commits; copier cannot render the
   working tree.
4. Check render hygiene before anything writes into the tree, because the
   guard reports files that `vale sync`, `uv sync` or any other command
   leaves behind:
   ```bash
   python3 scripts/check_render_hygiene.py /tmp/smoke
   ```
   If you already ran step 5 or 6 in `/tmp/smoke`, re-render into a fresh
   directory and check that; do not delete files from the tree.
5. Check the rendered prose with the Vale version pinned in the rendered
   `.github/workflows/ci.yml`:
   ```bash
   cd /tmp/smoke
   vale sync    # writes style packs into the tree — after step 4, never before
   vale --glob='!docs/{superpowers,design,decisions}/**' docs README.md
   ```
   Fix every finding in that set, not only those on lines you touched:
   `template-ci` lints the whole set, unlike a downstream's
   `filter_mode: added`.
6. Run the generated project's gate:
   ```bash
   cd /tmp/smoke
   uv sync --all-extras --all-groups
   uv run ruff check . && uv run ruff format --check .
   uv run mypy src/ tests/ && uv run pytest -x -q
   ```
7. Commit any fixes, run the `self-reviewing` skill on the cumulative diff,
   and fix or justify each finding; then push and open a PR.  Run it again
   before every later push to the branch.

### Render hygiene

Leave a pristine render with nothing for the shipped `trailing-whitespace`,
`end-of-file-fixer` and `ruff format` hooks to rewrite: a downstream commits
the rewritten form, and the next template change to that region conflicts
for every downstream.

- Do not end a `.jinja` file on a block tag.  Jinja keeps the newline after
  `{% endif %}` here, so the render ends with a blank line; write
  `{%- endif %}` or put content after the tag.
- Write any Python call or import whose length depends on
  `{{ project_name }}`, `{{ python_module }}`, `{{ env_prefix }}` or
  `{{ domain_description }}` with the value hoisted into a variable, or one
  argument per line with a trailing comma.  The smoke answers are too short
  to show the rewrap; template-ci's long-identifiers render catches it.

### Always-loaded budget

Put guidance that only some tasks need in a skill under `.agents/skills/`,
not in `AGENTS.md.jinja`; template-ci's size step and
`tests/test_agent_instructions.py` cap the rendered `AGENTS.md`.

## Breaking changes

The policy is "Breaking Changes and the `!` Marker" in `AGENTS.md.jinja`;
in this repo, "the breaking-change policy in `AGENTS.md`" means this
section.  A template change is breaking when it breaks a surface that
generated projects' *users* hold: renaming an env var in the config
skeleton, moving a state directory the Dockerfile ships, dropping a
sentinel block projects extend.  Recommend `major` for the release that
carries one.

## Repository protection

Change `.github/rulesets/*` within what
`scripts/tests/test_ruleset_required_checks.py` asserts; the posture is in
`docs/contribute/repository-protection.md.jinja`.  This repo runs no
bootstrap: manage its own protection by hand from those files, with the
required contexts swapped for `template-ci.yml`'s job names.

## Release

Releases are cut by dispatching `template-release.yml` with its `bump`
input.  `CONTRIBUTING.md`'s pointer to the `releasing` skill means this
dispatch here; the skill's trunk-first model applies without release
branches.

### Writing UPGRADING.md

**Any change that a downstream cannot absorb by running `copier update`
alone gets a note in `UPGRADING.md`, in the same PR that makes the
change.**  A note is needed when a human must act: rename an env var, move
or delete a file the template no longer owns, rescue content from a removed
sentinel, add a secret, change a repository setting, or re-run a generator.
Write it as instructions to that person; where it goes is in
`UPGRADING.md`'s Contributors paragraph.

## Spec

Full design: [`docs/superpowers/specs/2026-04-20-fastmcp-copier-scaffold-design.md`](https://github.com/pvliesdonk/markdown-vault-mcp/blob/main/docs/superpowers/specs/2026-04-20-fastmcp-copier-scaffold-design.md) (in the markdown-vault-mcp repo).
