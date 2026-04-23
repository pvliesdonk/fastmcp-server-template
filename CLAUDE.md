# fastmcp-server-template

Copier template repository.  This file is for claude-code agents
working on the **template itself** — NOT the generated projects.
Generated projects get their own `CLAUDE.md` rendered from
`CLAUDE.md.jinja`.

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
- `pyproject.toml.jinja`, `CLAUDE.md.jinja`, `Dockerfile.jinja`, etc.
  — generated project's other files.

## Making changes

1. Edit the relevant `.jinja` file(s).
2. Commit (copier reads from the git index — uncommitted changes are
   silently ignored without `--vcs-ref=HEAD`).
3. Render locally and verify the gate passes:
   ```bash
   rm -rf /tmp/smoke
   uv run --no-project --with copier copier copy --trust --defaults \
     --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
   cd /tmp/smoke
   uv sync --all-extras --dev
   uv run ruff check . && uv run ruff format --check .
   uv run mypy src/ tests/ && uv run pytest -x -q
   ```
   `--vcs-ref=HEAD` tells copier to use the latest commit instead of the
   latest git tag (the default).  Without it, your edits render only
   after a release.  If you need to iterate, amend the commit or make
   follow-up commits — rendering from the working tree is not supported.
4. Commit any fixes, push, open a PR.
5. `template-ci.yml` runs the same gate on Python 3.11–3.14.

## Release

Run `template-release.yml` via `workflow_dispatch` with `bump` input
(patch/minor/major).  It tags a new `vX.Y.Z`, updates CHANGELOG.md,
and creates a GitHub release.

## Spec

Full design: [`docs/superpowers/specs/2026-04-20-fastmcp-copier-scaffold-design.md`](https://github.com/pvliesdonk/markdown-vault-mcp/blob/main/docs/superpowers/specs/2026-04-20-fastmcp-copier-scaffold-design.md) (in the markdown-vault-mcp repo).
