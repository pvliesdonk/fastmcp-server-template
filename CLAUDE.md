# fastmcp-server-template

Copier template repository.  This file is for claude-code agents
working on the **template itself** — NOT the generated projects.
Generated projects get their own `AGENTS.md` rendered from
`AGENTS.md.jinja` (plus a stub `CLAUDE.md` that imports it).

## Purpose

This repo is a [copier](https://copier.readthedocs.io/) template that
scaffolds FastMCP servers on top of `fastmcp-pvl-core`.  Users run
`copier copy gh:pvliesdonk/fastmcp-server-template my-service` to
create new projects.

## Layout

- `copier.yml` — variables, `_skip_if_exists`, `_exclude`.
- `tests/fixtures/smoke-answers.yml` — fixed answers for CI self-test.
- `.github/workflows/template-ci.yml` — renders the template with
  smoke-answers and runs the generated project's gate.
- `.github/workflows/template-release.yml` — manual `workflow_dispatch`
  bump for the template's own git tags; no PSR.
- `.github/workflows/*.yml.jinja` — generated project's workflows.
- `src/{{python_module}}/*.jinja` — generated project's Python module.
- `pyproject.toml.jinja`, `AGENTS.md.jinja`, `Dockerfile.jinja`, etc.
  — generated project's other files.
- `.github/ISSUE_TEMPLATE/*.yml`, `CONTRIBUTING.md`, and every skill under
  `.agents/skills/` (with its `.claude/skills/` symlink) are copied verbatim
  into generated projects and re-rendered on `copier update`.

## Making changes

1. Edit the relevant `.jinja` file(s).
2. Commit (copier reads from the git index — uncommitted changes are
   silently ignored without `--vcs-ref=HEAD`).
3. Render locally:
   ```bash
   rm -rf /tmp/smoke
   uv run --no-project --with copier copier copy --trust --defaults \
     --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
   ```
   `--vcs-ref=HEAD` tells copier to use the latest commit instead of the
   latest git tag (the default).  Without it, your edits render only
   after a release.  If you need to iterate, amend the commit or make
   follow-up commits — rendering from the working tree is not supported.
4. Check the render is hygiene-clean, **before anything writes into the
   tree**.  This is why it comes before steps 5 and 6 rather than after:
   both `vale sync` and `uv sync` leave files behind, and the guard
   reports those as violations the change never caused.  `template-ci`
   runs it in this same position, ahead of its own `uv sync`.
   ```bash
   python3 scripts/check_render_hygiene.py /tmp/smoke
   ```
   If you have already run step 5 or 6 in `/tmp/smoke`, re-render into a
   fresh directory and check that instead — do not "clean up" the tree.
5. Check the rendered prose is Vale-clean.  `template-ci` gates on this,
   and it is the only pre-push path: the template's own sources are
   `.md.jinja`, which Vale cannot usefully lint.
   ```bash
   cd /tmp/smoke
   vale sync    # writes style packs into the tree — after step 4, never before
   vale --glob='!docs/{superpowers,design,decisions}/**' docs README.md
   ```
   Match the Vale version pinned in the rendered `.github/workflows/ci.yml`;
   a different local binary can report differently.  The file set and glob
   above are a convenience copy — `template-ci` extracts the version, file
   set and glob from that rendered `ci.yml` rather than restating them, so
   those three cannot drift from what a downstream runs.  One divergence is
   deliberate: a downstream's `ci.yml` sets `filter_mode: added`, failing
   only on findings on lines its PR touched, while this gate lints the whole
   set — the template owns this prose, so all of it must stay clean.
6. Verify the generated project's own gate passes:
   ```bash
   cd /tmp/smoke
   uv sync --all-extras --all-groups
   uv run ruff check . && uv run ruff format --check .
   uv run mypy src/ tests/ && uv run pytest -x -q
   ```
7. Commit any fixes, push, open a PR.
8. `template-ci.yml` runs the gate on Python 3.11–3.14.  The Vale step
   runs on 3.11 alone: its result does not depend on the interpreter, and
   syncing style packs is a network fetch.

### Render hygiene

The template ships the `trailing-whitespace` and `end-of-file-fixer`
pre-commit hooks, and both *rewrite* files.  Anything they would touch in
a pristine render becomes a latent `copier update` conflict: the
downstream commits the fixed-up form, so copier's 3-way merge sees `ours`
differ from `base` in that region, and the first template version that
also changes that region conflicts for **every** downstream.

The classic trap (issue #251) is a Jinja block tag at EOF — Jinja has no
`trim_blocks` here, so the newline after `{% endif %}` survives and the
render ends with a blank line.  Use `{%- endif %}` or put real content
after it.  `scripts/check_render_hygiene.py` is the guard; in
`render-and-gate` it covers four renders — default, gate-off,
authorization-off, and the clean-tree opt-out render.  A variant is
only covered if it is rendered *above* the hygiene step and named in its
argument list, so a new render step belongs in both places.  The
idempotence render (`/tmp/smoke2`) is deliberately excluded: it is already
asserted byte-identical to the default render.

## Breaking changes

The canonical breaking-change policy ships in the generated project's
`AGENTS.md` — see "Breaking Changes and the `!` Marker" in
`AGENTS.md.jinja`.  In short: a change is breaking only if it breaks
the operator surface (env var, config file, CLI flag, deployment
layout, on-disk state) or the public library interface, assessed
against the last stable release; MCP tool-surface changes are not
breaking on their own.

The same test governs this repo, one level up: a template change is
breaking when it breaks a surface that generated projects' *users*
hold — renaming an env var in the config skeleton, moving a state
directory the Dockerfile ships, dropping a sentinel block projects
extend.  This repo's releases are cut manually via
`template-release.yml`'s `bump` input; apply the same test when
deciding whether that input must be `major`.  `CONTRIBUTING.md` and
`.github/PULL_REQUEST_TEMPLATE.md` point at "the breaking-change
policy in `AGENTS.md`" — in this repo that is this section; in a
generated project it is the rendered section from `AGENTS.md.jinja`.

## Repository protection

`.github/rulesets/*` ship to generated projects, where the rendered
`bootstrap.yml` applies them (posture documented in
`docs/deployment/repository-protection.md.jinja`).  The two branch rulesets
are `.json.jinja`: they require the generated `ci.yml`'s aggregate
`CI Success` check plus whatever the project listed in the
`extra_required_checks` answer, the seam that lets a domain check outside
`ci.yml` be merge-blocking without forking a template-owned file (#454).
`scripts/tests/test_ruleset_required_checks.py` guards both halves — an
empty answer must render the single-context form every existing downstream
already has, and a non-empty one must still render valid JSON.  The tag
ruleset has no status checks and stays plain JSON.

This template repo itself does NOT run bootstrap and has no aggregate
check — `template-ci.yml` exposes per-job contexts instead — so its own
protection is managed by hand: reuse the ruleset files as a starting point,
but swap the required check contexts for the template-ci job names.

## Release

Run `template-release.yml` via `workflow_dispatch` with `bump` input
(patch/minor/major).  It tags a new `vX.Y.Z`, updates CHANGELOG.md,
and creates a GitHub release.

`UPGRADING.md` (template-repo only, excluded from renders) carries the
one-time manual steps a `copier update` jump needs in generated projects
— reference the relevant section from the release notes when such a
release ships.

### Writing UPGRADING.md

**Any change that a downstream cannot absorb by running `copier update`
alone gets a note in `UPGRADING.md`, in the same PR that makes the
change.** The test is whether a human must *do* something: rename an env
var, move or delete a file the template no longer owns, rescue content
from a removed sentinel, add a secret, change a repository setting, or
re-run a generator. A change a downstream picks up silently needs no
note; a change that will fail, or quietly do the wrong thing, until
someone acts does. Write it as instructions to that person, not as a
description of the diff.

**Write it under `## Unreleased`, at the end of the file, and never
under a version heading.** The version is not knowable while the change
is being made — it is chosen later, by the `bump` input of the release
dispatch — so a hand-written `## v5.2` is a guess that is simply wrong
if the next release turns out to be a patch. `scripts/promote_upgrading.py`,
which `template-release.yml` runs, renames the section to the real
`## vX.Y` on a minor or major release, folds it into the existing
minor's section on a patch (the file is organised by minor, and its
preamble tells readers so), and leaves a fresh empty `## Unreleased`
behind. Add a `## Unreleased - <short title>` heading if the file has
none; the title carries through to the released heading.

`template-ci` asserts the invariants — at most one `## Unreleased`, and
it is the last section — and that the release workflow still both runs
the promotion and stages the result. Run `python3
scripts/promote_upgrading.py --check` locally to see what it sees.

The release *model* that generated projects follow — trunk releases from
a quiescent commit by default, short-lived `release/X.Y` branches as the
exception, the three channels — ships in `AGENTS.md.jinja`'s "Release
model" section.  `CONTRIBUTING.md` points at "the release model in
`AGENTS.md`": in a generated project that resolves to the rendered
section; in this repo, releases are the manual dispatch above and the
same trunk-first spirit applies, without the branch machinery.

## Spec

Full design: [`docs/superpowers/specs/2026-04-20-fastmcp-copier-scaffold-design.md`](https://github.com/pvliesdonk/markdown-vault-mcp/blob/main/docs/superpowers/specs/2026-04-20-fastmcp-copier-scaffold-design.md) (in the markdown-vault-mcp repo).
