# Changelog

## v2.1.0 (2026-06-18)

- #158 feat(scaffold): add include_mcp_apps_scaffold flag with full SPA hash-routing scaffold
- #157 feat(docs): mike versioned-docs publishing (#148)
- #156 feat(docs): add Claude Desktop deployment guide (#119)
- #155 feat(ci): surface MCPB_VERSION as env var and add bundle smoke-test


## v2.0.0 (2026-06-17)

- #153 feat(deps): bump fastmcp-pvl-core to >=3.2.0,<4 and expose build_kv_store
- #152 fix: convert DOMAIN-*-EXTRA sentinels to pure HTML-comment blocks
- #151 feat: remove file-exchange scaffolding for the pvl-core 3.x line


## v1.8.0 (2026-05-26)

- #145 docs: clean up rendered docs/** to pass Vale (closes #141)
- #142 feat(docs): add Vale prose linter for downstream docs/**
- #140 ci(claude-review): skip on fork PRs to avoid auth-failing checks


## v1.7.0 (2026-05-17)

- #136 ci(release): expose `prerelease` as a force option so a second rc can be cut


## v1.6.1 (2026-05-11)

- #123 fix(copier-update): OIDC permission + bare Write for Jobs B/C


## v1.6.0 (2026-05-10)

- #121 feat(file-exchange): scaffold register_file_exchange_upload + DOMAIN-FILE-EXCHANGE sentinel


## v1.5.1 (2026-05-07)

- #115 feat(docker): optional debug extra + remote-debugger wiring (#105)
- #114 fix(aggregator): three follow-ups from #109 review (#110)


## v1.5.0 (2026-05-07)

- #113 feat(scaffold): commented opt-in authorization stubs + pin pvl-core 2.0
- #112 feat(docs): extend sentinel-protection to remaining docs/ files (#106)
- #111 docs(claude-md): add bot-reviewer-as-gate paragraph (#107)


## v1.4.0 (2026-05-07)

- #109 feat(workflow): wire claude-code agent into copier-update.yml
- #108 feat(template): sentinel-protect shared deployment + auth docs


## v1.3.0 (2026-05-03)

- #104 feat(readme): add template-version badge sourced from .copier-answers.yml
- #102 fix(release): bump mcp-publisher to v1.7.6 for new OIDC audience
- #100 feat(scaffold): commented Lucide-icon registration in tools.py + static/icons/
- #99 fix(release): use pypi_name in publish-pypi environment URL
- #98 feat(template-ci): add docker build smoke step
- #97 docs(claude-md): include PROJECT-* in domain-only-fix enumeration
- #93 docs(claude-md): enumerate Dockerfile sentinels as extension points
- #91 feat(template): sentinel-protect recurring copier-update conflict zones
- #89 feat(template): wire register_server_info_tool with upstream sentinel


## v1.2.2 (2026-05-01)

- #88 feat(release): gate publish-linux-packages on !inputs.prerelease
- #87 refactor(pyproject): migrate dev/docs to PEP 735 dependency-groups
- #86 fix(readme): genericise Quick start library-usage pointer
- #85 chore(deps): bump mkdocs-material floor + add mkdocs-llmstxt
- #84 feat(template): ship .gemini/config.yaml for review-scope control


## v1.2.1 (2026-04-29)

- #79 fix(ci): exclude dev/docs extras from pip-audit input
- #73 feat(template): adopt register_file_exchange in server skeleton


## v1.2.0 (2026-04-24)

- #66 chore: mop-up — Gate #3 mypy scope + template-ci hardening
- #65 feat(readme): expand README.md.jinja into structured template with DOMAIN sentinels
- #63 feat: pre-commit gate + PR-issue discipline in template CLAUDE.md
- #62 fix: three scaffolding-time bugs blocking downstream CI and releases
- #54 Scaffold coverage + README post-setup (closes #50, #51)


## v1.1.11 (2026-04-23)

- #49 feat(copier-update): enrich weekly PR body with delta, notes, diff, conflicts (#40)
- #48 fix(ci): surface CLAUDE.md sentinel count errors under bash -e (#43)


## v1.1.10 (2026-04-23)

- #45 fix(release): upsert marketplace.json when plugin is absent (#38)
- #44 docs(claude-md): add 'Contributing fixes upstream' section (#37)
- #42 feat(dockerfile): sentinel-protect state-dir mkdir + VOLUME (#30)
- #41 fix(docs): render shared docs with consumer env_prefix (#31)


## v1.1.9 (2026-04-23)

- #39 fix(dockerfile): COPY uv.lock so final uv sync sees the lockfile


## v1.1.8 (2026-04-22)

- #34 fix(copier-update): stage conflict markers before git checkout -B


## v1.1.7 (2026-04-22)

- #33 fix(claude-md): replace RST :class: with Markdown backticks


## v1.1.6 (2026-04-22)

- #32 fix(copier): add shared deployment+auth docs to _skip_if_exists


## v1.1.5 (2026-04-22)

- #27 feat: template v1.1.5 — CLAUDE.md Shared Infrastructure + Dockerfile sentinels + bump_manifests hardening


## v1.1.4 (2026-04-22)

- #26 fix(copier-update): pass REF through env: + top-level import in test_smoke.py


## v1.1.3 (2026-04-22)

- #25 fix(copier): exclude scaffold files instead of `_skip_if_exists`


## v1.1.2 (2026-04-22)

- #24 fix(copier-update): add dependencies label guard + drop unused step id


## v1.1.1 (2026-04-22)

- #23 fix(copier-update): use --conflict=inline instead of --conflict=rej


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
