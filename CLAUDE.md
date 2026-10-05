# fastmcp-server-template

This repo is a [copier](https://copier.readthedocs.io/) template that
scaffolds FastMCP servers on top of `fastmcp-pvl-core`; users run
`copier copy gh:pvliesdonk/fastmcp-server-template my-service`.  This file
guides work on the template itself.  Guidance for agents in a generated
project goes in `AGENTS.md.jinja`, which renders to that project's
`AGENTS.md`; `CLAUDE.md.jinja` stays the three-line `@AGENTS.md` stub that
`tests/test_agent_instructions.py` checks.

## What renders where

- Edit `X.jinja` to change the generated project's `X`.  A plain file beside
  a `.jinja` of the same name (`CLAUDE.md`, `SECURITY.md`, `pyproject.toml`,
  `sonar-project.properties`) is this repo's own and never renders.
- Every other plain file outside `copier.yml`'s `_exclude` and
  `_skip_if_exists` ships verbatim and is re-rendered on `copier update`,
  including `CONTRIBUTING.md`, `.github/ISSUE_TEMPLATE/*.yml`, the skills
  under `.agents/skills/`, the shipped `scripts/` and
  `tests/test_agent_instructions.py`.  Write those for the downstream
  reader, not for this repo.  A `_skip_if_exists` file is seeded once and
  never reaches an existing project again.
- Run this repo's tools with `uv run --locked`.  Bump the
  `fastmcp-pvl-core` pin in `pyproject.toml` and `pyproject.toml.jinja`
  together, then run `uv lock`.
- `ruff.toml` lints `scripts/`; change it together with the `[tool.ruff]`
  block in `pyproject.toml.jinja` (`scripts/tests/test_ruff_config_mirror.py`).
- When you add, rename or remove a template skill, update `TEMPLATE_SKILLS`
  in `scripts/migrate_agent_instructions.py`, the same tuple in
  `scripts/tests/test_shared_skill_paths.py` and in
  `tests/test_agent_instructions.py`, and the directory list in `copier.yml`'s
  before-stage guard, and add the relative symlink
  `.claude/skills/<name>` → `../../.agents/skills/<name>`.
  `scripts/tests/test_shared_skill_paths.py` checks all five.

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
7. Commit any fixes, push, open a PR.

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
- To add a render variant to template-ci's `render-and-gate`, render it
  above the `check_render_hygiene.py` step and add its directory to that
  step's arguments.  Leave the idempotence render `/tmp/smoke2` out; it is
  asserted byte-identical to the default render.

### Always-loaded budget

`template-ci` fails when the smoke render's `AGENTS.md` exceeds 24 000
characters of template-owned prose, and `tests/test_agent_instructions.py`
fails a rendered project whose whole `AGENTS.md` exceeds 40 000.  Put
guidance that only some tasks need in a skill under `.agents/skills/`, not
in `AGENTS.md.jinja`.

## Breaking changes

The breaking-change policy is "Breaking Changes and the `!` Marker" in
`AGENTS.md.jinja`: a change is breaking only if it breaks the operator
surface (env var, config file, CLI flag, deployment layout, on-disk state)
or the public library interface, assessed against the last stable release.
MCP-surface changes (tools, resources, prompts) are not breaking on their
own.  In this repo, "the breaking-change policy in `AGENTS.md`" in
`CONTRIBUTING.md` and `.github/PULL_REQUEST_TEMPLATE.md` means this section.

A template change is breaking when it breaks a surface that generated
projects' *users* hold: renaming an env var in the config skeleton, moving
a state directory the Dockerfile ships, dropping a sentinel block projects
extend.  Recommend `major` for `template-release.yml`'s `bump` input when a
release carries one.

## Repository protection

`.github/rulesets/*` ship to generated projects, where the rendered
`bootstrap.yml` applies them; the posture is in
`docs/contribute/repository-protection.md.jinja`.

- Keep an empty `extra_required_checks` answer rendering the `main` and
  `release/*` rulesets with the single `CI Success` context, and a
  non-empty one rendering valid JSON.
- Keep the tag ruleset and `protect-integration-branches.json` plain JSON;
  the latter requires `CI Success` alone, because a domain check may not
  run on `integration/*` and a required check that never reports blocks
  every child PR.
- Keep all three branch rulesets non-strict.
  `scripts/tests/test_ruleset_required_checks.py` checks these three rules.
- Before changing `bootstrap.yml.jinja`'s `security` job or
  `SECURITY.md.jinja`, read
  `docs/design/reference/github-repository-security-settings.md`;
  `scripts/tests/test_bootstrap_security.py` checks both.

This repo runs no bootstrap and has no aggregate check.  Manage its own
protection by hand from the ruleset files, with the required contexts
swapped for `template-ci.yml`'s job names.

## Release

Releases are cut by running `template-release.yml` via `workflow_dispatch`
with the `bump` input (patch/minor/major); it tags `vX.Y.Z`, updates
`CHANGELOG.md` and creates the GitHub release.  When a release carries
manual downstream steps, reference their `UPGRADING.md` section from the
release notes.

In this repo, `CONTRIBUTING.md`'s "release model in the `releasing` skill"
means this manual dispatch; the trunk-first model in
`.agents/skills/releasing/SKILL.md.jinja` applies without release branches.

### Writing UPGRADING.md

**Any change that a downstream cannot absorb by running `copier update`
alone gets a note in `UPGRADING.md`, in the same PR that makes the
change.**  A note is needed when a human must act: rename an env var, move
or delete a file the template no longer owns, rescue content from a removed
sentinel, add a secret, change a repository setting, or re-run a generator.
A change a downstream picks up silently needs none.  Write the note as
instructions to that person, not as a description of the diff.

- Write it under `## Unreleased`, the last section of `UPGRADING.md`,
  replacing the `_Nothing yet._` placeholder.  Never write it under a
  version heading: the release dispatch chooses the version later.
- Title the heading `## Unreleased - <short title>`; the title carries into
  the released heading.
- Leave the released `## vX.Y` index sections as one-line pointers and add
  no steps to `upgrading/vX.Y.md` by hand; `scripts/promote_upgrading.py`
  moves the Unreleased section there at release time.
- Run `python3 scripts/promote_upgrading.py --check` before pushing;
  `template-ci` runs the same check.

## Spec

Full design: [`docs/superpowers/specs/2026-04-20-fastmcp-copier-scaffold-design.md`](https://github.com/pvliesdonk/markdown-vault-mcp/blob/main/docs/superpowers/specs/2026-04-20-fastmcp-copier-scaffold-design.md) (in the markdown-vault-mcp repo).
