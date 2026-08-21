# Changelog

## v5.4.0 (2026-08-21)

- #456 feat: versioned llms.txt links, a shared CI setup composite, and a required-check seam


## v5.3.2 (2026-08-21)

- #451 feat(notes): net-delta and upstream-bump rules, full_redraft override, Vale-safe heading, call-mode lock


## v5.3.1 (2026-08-20)

- #446 fix(deps): raise the pvl-core floor to 4.11.3, and document subpath routing on a shared hostname


## v5.3.0 (2026-08-19)

- #443 fix: drop read_only= from the build_instructions call site


## v5.2.1 (2026-08-19)

- #441 fix(ci): keep Renovate PRs out of review, and land README-only catalog repairs


## v5.2.0 (2026-08-19)

- #439 fix(ci): decide review eligibility in the workflow, and review each commit once
- #437 docs: write UPGRADING.md under `## Unreleased`, and promote it at release time
- #433 fix(release): bump the catalog where Claude Code reads it, and give rcs a rolling image tag
- #431 ci: cache Playwright browsers and stop a font install gating the docs job
- #429 chore(deps): update python docker tag to v3.14
- #428 chore(deps): update ghcr.io/astral-sh/uv docker tag to v0.12
- #427 docs: add cumulative template upgrade guide
- #425 ci: bound the docs workflow's Chromium install so it cannot wedge a runner
- #422 fix(release): draft-hold until notes land, watermark-verified already-current, publish skips release merges
- #384 chore(deps): update dependency astral-sh/uv to 0.12


## v5.1.0 (2026-08-18)

- #420 feat(release): release notes become part of the release PR — every tag carries its own page


## v5.0.2 (2026-08-18)

- #416 fix(release): injective releasable refs, atomic version reservation, convergent rolling channels, rename-aware promotion guard


## v5.0.1 (2026-08-18)

- #413 fix(release): gate promotions at prepare time and overlay notes pages into release docs
- #411 fix(release): repair v5.0.0 flow defects surfaced by the MVM adoption


## v5.0.0 (2026-08-18)

- #409 feat(release)!: swap PSR for the knope release-PR flow (Phase 2)
- #408 feat(release): add interlocked knope release-PR core (Phase 1)
- #382 fix(release): correct ships-atomically warn gating and add manifest-lockstep test


## v4.1.0 (2026-08-16)

- #378 fix(release): close release-machinery disclosure gaps
- #369 feat(ci): gate pull-request titles on the commit types PSR can parse


## v4.0.0 (2026-08-16)

- #365 feat(release-notes): agent-written release-notes workflow (per-minor pages, PR-gated)
- #364 feat(release): compose release bodies as summary + docs pointers; repair PSR changelog writing
- #363 docs(release): document the release model — channels, cut criterion, branch-on-demand
- #361 feat(workflows): ship branch/tag rulesets under the branch-aware release model
- #360 feat(release)!: release from short-lived stabilisation branches; branch-derived rc identity
- #358 feat(workflows): ship a rolling unstable channel (edge image + mcpb artifact) per merge to main
- #357 feat: guard the package root's public import surface with a snapshot test
- #356 feat: ship an Epic issue form and a contributor-facing authoring skill
- #355 fix: stop bump_manifests pinning pre-release versions never published to PyPI
- #354 docs: define the breaking-change policy (operator/library surface, not MCP tool surface)


## v3.6.0 (2026-08-15)

- #340 feat(gen-config): generate the Claude Code plugin userConfig screen as a split-file pair


## v3.5.0 (2026-08-14)

- #339 feat(plugin): scaffold the Claude Code plugin channel behind include_claude_plugin


## v3.4.0 (2026-08-14)

- #338 feat(ci): pre-release workflow_dispatch smoke test for the mcpb bundle
- #337 feat(gen-config): generate the mcpb user_config install screen from the config surface
- #336 fix(gen-config): bootstrap with the project's full core constraint, not ==floor
- #334 feat(release): publish marketplace catalog entry by direct push, not an unmerged PR


## v3.3.0 (2026-08-13)

- #329 feat(tasks): wire pvl-core 4.11.0's background-task backend


## v3.2.2 (2026-08-13)

- #327 fix(release): template-own bump_manifests.py; stop CI syncs mutating uv.lock


## v3.2.1 (2026-08-12)

- #324 fix(wizard): surface TOOLS_ALLOW/TOOLS_DENY as wizard questions and server.json env vars


## v3.2.0 (2026-08-11)

- #322 feat(server): wire operator tool visibility (TOOLS_ALLOW/TOOLS_DENY)


## v3.1.4 (2026-08-11)

- #320 fix(review): pin CLA 2.1.197 to run the full /code-review skill (fixes silent no-op reviews)
- #316 chore(deps): update dependency renovatebot/github-action to v46.2.2
- #315 Add issue/PR templates + contributing guide for downstream (dogfooded here)


## v3.1.3 (2026-08-09)

- #313 fix(workflows): grant Task so Claude reviews can fan out into subagents
- #310 experiment(claude): grant Task + show_full_output to test fan-out


## v3.1.2 (2026-08-09)

- #309 feat(server): add transfer subsystem wiring examples to DOMAIN-WIRING block


## v3.1.1 (2026-08-07)

- #307 fix(config): re-exec on too-old core (#306); adopt core 4.6.1's local-read resolution (#305)
- #304 fix(config): decompose _unscanned_from_env_reads under C901; gate shipped scripts structurally


## v3.1.0 (2026-08-07)

- #302 fix(update): regenerate the config surface AFTER the update diff, not against the mid-update skeleton
- #301 feat(config): document composed sub-config vars with their own field metadata (core 4.6.0)
- #300 fix(renovate): exact-pin the unresolvable @v46 + implement the four decided adoption-findings fixes
- #298 fix: address v3.0.x adoption findings — release lockfile bump, gate/doc corrections


## v3.0.2 (2026-07-31)

- #288 docs: move config-migration out of the operator site; scrub implementer prose from operator pages


## v3.0.1 (2026-07-31)

- #285 docs(authz): drop the implementer-facing enablement instructions from the operator guide
- #283 fix(update): unblock v3 adoption — gate-clean shipped scripts, no conflict markers in generated files, seamed pre-commit config


## v3.0.0 (2026-07-30)

- #280 ci(claude): grant GitHub MCP tools to the claude workflows; make @claude read-only
- #278 chore: rendered-project hygiene — .gitignore fixes + drop dead READ_ONLY manifest knob
- #276 feat(config): generate the server.json env-var arrays (json-splice)
- #275 feat(config): generate the README env-var tables + fix domain required-ness
- #274 feat(config): generate the OIDC env-var tables, dropping the ephemeral claim
- #273 docs(oidc): correct the false ephemeral signing-key claim
- #271 ci(template): run Vale over the render, and enforce the lockstep it claimed
- #269 fix(docs): clear every Vale error from the rendered docs
- #264 feat(config)!: generate the config surface, retire the drift test


## v2.11.2 (2026-07-25)

- #256 ci: make detach-smoke fail loudly when CLAUDE.md drifts from the scrub
- #255 feat(config): add CONFIG-VALIDATE seam for domain field validation
- #253 fix: transport docstring accuracy + seven template-owned tidies


## v2.11.1 (2026-07-25)

- #252 ci: guard that a pristine render already satisfies the shipped pre-commit hooks


## v2.11.0 (2026-07-24)

- #250 feat(deps): switch fleet dependency automation from Dependabot to Renovate


## v2.10.5 (2026-07-15)

- #248 feat(apps): DOMAIN-APP-RESOURCE seam for the app-shell resource's AppConfig


## v2.10.4 (2026-07-13)

- (no PRs merged since v2.10.3)


## v2.10.3 (2026-07-08)

- #243 fix: harden Claude review workflows (inline comments, write perms, REVIEW.md scoping, CI-gated review)
- #240 fix(docs): remove dead env vars and mcp-server hardcodes from shared deployment docs


## v2.10.2 (2026-07-03)

- #238 fix: bump vendored ext-apps SDK 1.3.1 → 1.7.4


## v2.10.1 (2026-07-03)

- #236 fix(release): gate detect-rc on the latest stable release
- #233 chore: purge dead gemini-code-assist wiring


## v2.10.0 (2026-06-30)

- #231 feat(scaffold): brownfield opt-out for the structural gate's whole-tree clean assertion


## v2.9.1 (2026-06-30)

- #228 fix(config-wizard): orphan check accepts non-prefixed vars read in src


## v2.9.0 (2026-06-29)

- #226 feat(scaffold): DOMAIN-COMMANDS sentinel in cli.py for domain subcommands


## v2.8.0 (2026-06-29)

- #224 feat: drift gate measures decomposed configs via domain_env_suffixes
- #222 fix(scaffold): point pre-commit mypy at scripts/, not unrendered Jinja src/


## v2.7.0 (2026-06-29)

- #220 feat(scaffold): real SPA SDK vendoring pipeline (closes #216, #218, #219)
- #215 fix(scaffold): make vendor_spa.py starter self-contained
- #213 fix(scaffold): drop inert git.py CodeQL filter; ship benign config seam
- #211 feat(scaffold): diff-scoped structural-health gate (Spec 1)
- #209 feat(docs): lint user-facing docs + README; exclude internal dev-doc subtrees (#208)


## v2.6.0 (2026-06-28)

- #207 feat(scaffold): CI-enforced config-wizard env-surface coverage
- #206 feat(scaffold): honor {PREFIX}_SERVER_NAME and {PREFIX}_INSTRUCTIONS
- #205 feat(wizard): seed the upstream ServerConfig questions; document coverage
- #204 docs(claude-md): add Tool Registration Checklist section


## v2.5.4 (2026-06-27)

- #198 fix(scaffold): neutralize copier-update wording in CLAUDE.md on detach
- #197 docs(scaffold): add MCP Registry mcp-name marker to README header
- #196 test(scaffold): assert app_domain log by arg equality, not URL substring
- #195 ci(scaffold): bump pinned actions and seed dependencies label


## v2.5.3 (2026-06-22)

- #189 ci: bump pinned GitHub Actions (checkout v7, cache v5, setup-uv v8.2)
- #187 fix(docs): replace spaced em-dash in authentication guide to satisfy Vale


## v2.5.2 (2026-06-22)

- #186 fix(config-wizard): skip smoke tests on a stale site/ instead of false-failing


## v2.5.1 (2026-06-20)

- #183 feat(scaffold): document and enable clean detach from the template (closes #182)


## v2.5.0 (2026-06-20)

- #181 feat(scaffold): migrate authorization to pvl-core v4 native AuthChecks


## v2.4.0 (2026-06-19)

- #179 feat(scaffold): co-locate authentication + authorization (closes #178)
- #177 feat(scaffold): gate Authorization scaffold behind enable_authorization (closes #176)
- #174 fix(config-wizard): deep meta validation + dockerVolume/dockerPath var constraint (closes #172, #173)


## v2.3.0 (2026-06-19)

- #170 feat(wizard): spec-owned domain via meta + dockerVolume/dockerPath (closes #169)


## v2.2.1 (2026-06-19)

- #168 fix(config-wizard): five correctness bugs found during v2.2.0 adoption


## v2.2.0 (2026-06-18)

- #166 feat(template): port in-browser configuration generator


## v2.1.2 (2026-06-18)

- #165 fix(release): auto-advance rc revision; remove force=prerelease workaround
- #164 fix(workflow): restore github-actions[bot] identity on copier-update commits
- #162 fix(aggregator): surface silent failures at operator boundary
- #161 docs(claude-md): add Logging Standard Scope subsection
- #160 fix(ci): CVE-2026-42561 ignore, test timeout, interpreter cache, stale #49 ref


## v2.1.1 (2026-06-18)

- #159 fix(vale): Milestone C — cache clobber, exclusion-scope lockstep, ai-tells URL ownership


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
