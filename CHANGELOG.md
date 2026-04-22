# Changelog

## v1.1.0 (2026-04-22)

- #22 feat(ci): weekly copier update workflow


## v1.0.5 (2026-04-21)

- #21 chore(actions): bump setup-uv, deploy-pages, codeql-action
- #19 feat(gitignore): ship opinionated .gitignore starter + add to _skip_if_exists


## v1.0.4 (2026-04-21)

- #18 feat(cli): rewrite template CLI from argparse to typer


## v1.0.3 (2026-04-21)

- #17 fix(release): ship bump_manifests.py + wire PSR build_command
- #16 fix(ci): docs workflow triggers on v* tag pushes


## v1.0.2 (2026-04-21)

- #15 fix(mcpb): add [build-system] table to pyproject starter
- #14 fix(scaffold): default to proprietary, require explicit license choice
- #13 ci: Add claude GitHub actions 1776773149181
- #12 feat(packaging): add mcpb bundle scaffold


## v1.0.1 (2026-04-21)

- #11 fix(release): publish linux packages on prerelease too


## v1.0.0 (2026-04-20)

- #10 feat!: rewrite as copier template depending on fastmcp-pvl-core (v1.0.0)
- #5 feat(infra): sync non-domain infrastructure from evolved derived repos


All notable changes to this template are documented here.  Template
consumers see these in their `copier update` PRs.

## v1.0.0 (2026-04-20)

**Complete rewrite.**  The repo transitioned from a GitHub template
repo (with `scripts/rename.sh`) to a copier template that depends on
`fastmcp-pvl-core>=1.0,<2` for shared infrastructure rather than
re-hosting it inline.

### Migration

- Existing forks created via "Use this template" pre-v1.0.0 are NOT
  automatically upgraded.  To adopt the new shape, follow MV's
  7-PR migration (`refactor: adopt fastmcp-pvl-core ...` in
  `pvliesdonk/markdown-vault-mcp`) as a reference, then optionally
  run `copier copy gh:pvliesdonk/fastmcp-server-template ./sibling`
  into a sibling directory and diff against your hand-migrated repo.
- The "Use this template" button on GitHub is disabled — `copier copy`
  is the sole supported entry point.
- `scripts/rename.sh`, `src/fastmcp_server_template/`, `TEMPLATE.md`,
  and `SYNC.md` are removed.
