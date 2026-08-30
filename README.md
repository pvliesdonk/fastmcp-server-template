# fastmcp-server-template

[![repowise](https://api.repowise.dev/badge/wiki/pvliesdonk/fastmcp-server-template.svg)](https://repowise.dev/repo/pvliesdonk/fastmcp-server-template) [![Code health](https://api.repowise.dev/badge/health/pvliesdonk/fastmcp-server-template.svg)](https://repowise.dev/repo/pvliesdonk/fastmcp-server-template)

Copier template that scaffolds a production-ready FastMCP server on top of
[`fastmcp-pvl-core`](https://pypi.org/project/fastmcp-pvl-core/): auth,
middleware, logging, config surface, packaging channels (PyPI, Docker,
Linux packages, mcpb, Claude Code plugin), CI, release automation and
documentation site. The pvliesdonk MCP servers are generated from it, and the
template is the mechanism that keeps them aligned, so it ships complete,
opinionated functionality rather than placeholders.

## Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv)
- [copier](https://copier.readthedocs.io/) 9.4+

## Generate a project

```bash
uv run --no-project --with copier \
  copier copy gh:pvliesdonk/fastmcp-server-template my-new-service

cd my-new-service
uv sync --all-extras --all-groups
uv run pytest
uv run my-new-service serve
```

The generated project's `README.md` carries the post-scaffold checklist
(DOMAIN blocks to fill, GitHub secrets, repository protection). Its
`AGENTS.md` (imported by a stub `CLAUDE.md`) carries the conventions every
contributor and coding agent follows, and its skills under
`.agents/skills/` carry the task-shaped guidance.

## Layout of this repository

| Path | What it is |
|---|---|
| `copier.yml` | Questions, `_skip_if_exists` (seeded once), `_exclude`, tasks and migrations |
| `*.jinja` | Files rendered into a generated project; the plain twin (`README.md`, `CLAUDE.md`) is this repository's own |
| `.github/workflows/*.yml.jinja` | The generated project's workflows; `template-*.yml` are this repository's own |
| `.agents/skills/` | Skills copied verbatim into generated projects, reachable by Claude Code through `.claude/skills/` symlinks |
| `scripts/` | Generators and checks that ship downstream; `scripts/tests/` and the `check_*` guards stay here |
| `UPGRADING.md` | Per-release manual steps for generated projects, written under `## Unreleased` as changes land |
| `docs/superpowers/` | Design specs and implementation plans (not rendered) |

`CLAUDE.md` is the maintainer routine: how to change a template, render it,
check hygiene and Vale, run the generated project's gate, and what counts
as a breaking change.

## Releasing the template

Releases are cut by hand: dispatch `template-release.yml` with a `bump` of
`patch`, `minor` or `major`. It tags `vX.Y.Z`, updates `CHANGELOG.md`,
promotes the `## Unreleased` section of `UPGRADING.md` to the released
version, and creates the GitHub release. Pick the bump with the
breaking-change test in `CLAUDE.md`: a change is major when it breaks a
surface that generated projects' users hold (an env var, a state
directory, a sentinel block), not when it changes a generated file.

Before dispatching, read `UPGRADING.md`'s `## Unreleased` section: every
change a downstream cannot absorb by `copier update` alone must already be
described there, in the same pull request that made the change.

## How generated projects update

Each generated project runs `copier-update.yml` weekly. It runs `copier
update --trust` (the template declares tasks and migrations, so `--trust` is
required by hand as well), advancing one major at a time, and opens a pull
request whose body carries the version delta, the
template's release notes, the applicable `UPGRADING.md` sections and the
resolution policy. Working through that pull request, by hand or with a
coding agent, is documented in the generated project's
`docs/deployment/template-updates.md` and in the `applying-template-updates`
skill it ships. The one trap worth knowing before reading either: files
under `_skip_if_exists` in `copier.yml` are seeded once and never
re-rendered, so a template change to one of them has to be applied by hand.

## Contributing

`CONTRIBUTING.md` holds the rules: issues record observations rather than
work orders, one issue per problem, and every pull request closes an issue.
Fixes are routed by which file they change: `fastmcp-pvl-core` for library
code, this repository for template-owned files, the generated project for
anything inside its `DOMAIN-*` / `CONFIG-*` / `PROJECT-*` blocks.

## Forking

A generated project can detach from the template; `FORKING.md` in the
project walks the scrub, and this repository's `template-ci.yml` smoke-tests
that procedure on every change.

## Spec

The original design: [copier scaffold design spec](https://github.com/pvliesdonk/markdown-vault-mcp/blob/main/docs/superpowers/specs/2026-04-20-fastmcp-copier-scaffold-design.md)
(in the markdown-vault-mcp repository). Later designs live under
`docs/superpowers/specs/` here.
