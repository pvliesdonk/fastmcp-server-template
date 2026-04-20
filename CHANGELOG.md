# Changelog

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
