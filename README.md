# fastmcp-server-template

Copier template that scaffolds a production-ready FastMCP server
depending on [`fastmcp-pvl-core`](https://pypi.org/project/fastmcp-pvl-core/)
for shared infrastructure (auth, middleware, logging, server factory,
artifact store, CLI helpers).

## Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- [copier](https://copier.readthedocs.io/) 9+

## Usage

```bash
uv run --no-project --with copier \
  copier copy gh:pvliesdonk/fastmcp-server-template my-new-service

# Answer the prompts, then:
cd my-new-service
uv sync --all-extras --all-groups
uv run pytest
uv run my-new-service serve
```

## Update flow

Downstreams updated via `copier update --trust` when a new template
tag lands.  `.copier-answers.yml` in your repo records the template
version; conflicts are surfaced as `<<<<<<< HEAD` markers in the
hybrid files (`pyproject.toml`, `CLAUDE.md`) on the rare occasion a
template-owned section and a domain edit collide.

## Spec

See [the copier scaffold design spec](https://github.com/pvliesdonk/markdown-vault-mcp/blob/main/docs/superpowers/specs/2026-04-20-fastmcp-copier-scaffold-design.md)
for the full rationale.
