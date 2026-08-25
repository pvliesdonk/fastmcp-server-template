# Upgrading generated projects

This guide is for maintainers updating a generated project with
`copier update`. It starts at template v1.0.0 and records the manual work that
Copier cannot do: preserving project-owned files, migrating removed extension
points, changing repository settings, and checking operational behavior.

Contributors: record migration steps under `## Unreleased` at the end of this
file, never under a version heading — the version is chosen at release time,
and `scripts/promote_upgrading.py` rewrites the heading then. See "Writing
UPGRADING.md" in `CLAUDE.md`.

Read the current minor's section when your target includes a newer patch in
that line, then read every later minor through the target. This matters for a
project on v1.2.0: v1.2.1 and v1.2.2 contain migration work recorded in the
v1.2 section. Unless you need to diagnose an intermediate change, update
straight to the newest patch of the newest minor rather than stopping on an
early patch.

## Before every upgrade

1. Read every applicable version section before running Copier. Complete all
   steps marked **before updating**, **rescue**, **copy**, **preserve**, or
   **inventory** first. For a v1.x-to-current jump, this includes File Exchange
   code, the old MCP Apps implementation, config-surface metadata, MCPB install
   objects, and release-manifest stamping logic. A single direct update can
   delete or regenerate all five. A pre-v3.2.2 manifest bumper has no extension
   markers, so preserve all project-specific logic from that script.
2. Commit or back up the project, including ignored and skip-listed files.
3. Read `.copier-answers.yml` and set new answers deliberately. Automated
   updates commonly use `--skip-answered`, which accepts new defaults.
4. Rescue custom content from any file or sentinel that a section says is
   removed. Copier deletes a removed template-owned file, including downstream
   content inside it.
5. Run the update with the project version of the normal Copier command. Trust
   the template when prompted: later versions run generation and vendoring
   tasks.
6. Resolve conflicts by ownership. Preserve domain content inside the current
   `DOMAIN-*` or `PROJECT-*` blocks and accept template changes outside them.
   The markers are conventions; Copier uses an ordinary three-way merge.
7. Review and commit intentional lockfile changes with `uv lock`, then search
   for unresolved conflicts and check the resulting tree:

   ```bash
   git diff --check
   git grep -nE '^(<<<<<<<|=======|>>>>>>>)'
   uv lock --check
   uv sync --all-extras --all-groups --locked
   uv run ruff check .
   uv run ruff format --check .
   uv run mypy src/ tests/
   uv run pytest -x -q
   uv run mkdocs build --strict
   uv run pre-commit run --all-files
   ```

   For a v3+ target, also run
   `python scripts/gen_config_surface.py --check`. For an MCP Apps project, run
   `python scripts/vendor_spa.py --check`. Run the Vale and browser checks when
   the relevant sections below introduce them.

Files in `_skip_if_exists` need special attention. Copier seeds them once and
then leaves them under project ownership. Later template corrections do not
reach an existing copy. Some newer config files are both skip-listed and
generator-owned; the generator, not Copier, rewrites those files.

Nothing surfaces that gap for you. A skip-listed file never appears in a
`copier update` diff, and the update pull request lists it among the regions
to leave alone, so a template improvement to one can sit unadopted for
releases without anything saying so. Check for it deliberately, by rendering
the target with your own answers and comparing the files Copier will not
touch:

```bash
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=<target> --data-file .copier-answers.yml \
  gh:pvliesdonk/fastmcp-server-template /tmp/target-render

diff -r /tmp/target-render/.vale/styles/config/vocabularies \
        .vale/styles/config/vocabularies
diff -r /tmp/target-render/.claude-plugin .claude-plugin
```

Then adopt what the template authored and keep what you wrote; this is a read
and a decision, not a wholesale copy.

`_skip_if_exists` in the template's `copier.yml` is the full list. Most of it
is yours by construction and will differ every time, which is why a blanket
diff of all of it is noise: `tools.py`, `resources.py`, `prompts.py`,
`domain.py`, the seeded tests, `CHANGELOG.md`, `docs/releases/`, `LICENSE`.
The entries worth reading a diff of are the ones the template still authors
content for, where a change is a correction rather than your own work:

- `.vale/styles/config/vocabularies/Base/accept.txt` — template prose that
  arrives in a later release can need vocabulary the seeded file lacks, and
  the missing terms fail your docs gate rather than the template's
  (template#366);
- `.claude-plugin/**` — the plugin scaffold and its README;
- `packaging/mcpb/` — `manifest.json.in`, `pyproject.toml.in`, `build.sh` and
  the entry shim, which track the mcpb CLI and manifest version;
- `.gitignore`, `.vale.ini`, `config-presentation.domain.yml`.

How much this matters depends on how far behind you are, and it is worth
knowing that it is often nothing. Between v5.0.0 and v5.6.1 no skip-listed
file changed at all; from v4.0.0 the set is two files. A v3.x jump is the one
that carries real content.

## v1.0 - Copier foundation and initial packaging

Template v1.0 replaced the old GitHub-template and `scripts/rename.sh` model
with Copier (template#10). A project created before v1.0 cannot use
`copier update` until it is manually moved into the Copier layout and given a
`.copier-answers.yml`. Remove the old `scripts/rename.sh`, `TEMPLATE.md`,
`SYNC.md`, and template package tree after preserving domain code.

For projects created on v1.0.x:

1. Choose the real license and align `LICENSE`, `pyproject.toml`,
   `packaging/mcpb/manifest.json.in`, and `packaging/nfpm.yaml`. Early v1.0
   releases changed the default from MIT to proprietary/`UNLICENSED`, but
   `LICENSE` and MCPB files are project-owned (template#14).
2. Reconcile custom CLI behavior with the argparse-to-Typer rewrite and run
   `uv lock` (template#18).
3. Customize the new MCPB starter before publishing it. Its build requires
   `mcpb` and `envsubst` (template#12).
4. Confirm `scripts/bump_manifests.py` exists and the semantic-release
   `build_command` invokes it. Otherwise `server.json` keeps the old version
   during MCP Registry publication (template#17).

MCPB files, `LICENSE`, `.gitignore`, and the original manifest bumper became
skip-listed during this line. Port later corrections into existing copies
manually.

## v1.1 - Automated Copier updates and extension sentinels

v1.1 added the weekly Copier update pull request and changed update conflicts
from `.rej` files to inline markers (template#22, template#23).

1. Configure `RELEASE_TOKEN` for contents and pull-request writes. Historical
   versions also needed permission to update workflow files.
2. Move Docker customizations into the new `DOCKERFILE-*` blocks: apt
   dependencies, `uv sync` flags, state-directory setup, and volumes
   (template#27, template#42).
3. If `scripts/bump_manifests.py` already exists, port template#27's type
   validation and null OCI-identifier handling into it. Copier cannot update
   the skip-listed copy.
4. If upgrading only within v1.1, replace stale `MCP_SERVER_*` examples in the
   deployment and authentication docs with the project's prefix. The later
   v1.4-v1.5 ownership migrations supersede this step.
5. Verify the Dockerfile copies `uv.lock` before its final frozen sync
   (template#39).

An update branch can intentionally contain committed conflict markers. Review
and resolve them before merge; the existence of the pull request is not proof
that the update succeeded.

## v1.2 - README ownership, pre-commit, and dependency groups

v1.2 moved the README from a frozen starter to a hybrid file and moved
development tooling from extras to PEP 735 dependency groups (template#65,
template#87).

1. On the first update, move project prose into the new
   `DOMAIN-START`/`DOMAIN-END` regions and accept the template-owned README
   sections.
2. Run `uv lock` and replace old setup commands. Use
   `uv sync --all-extras --all-groups` for development and
   `uv sync --no-default-groups --group docs --frozen` for docs-only jobs.
3. Reconcile an existing `.pre-commit-config.yaml` manually. It is skip-listed,
   so Copier does not seed the v1.2 hooks over an existing file.
4. Preserve and customize `packaging/env.example`, which is also project-owned.
5. If using File Exchange, check `{PREFIX}_BASE_URL`, `MCP_EXCHANGE_DIR`, and
   HTTP versus stdio behavior after adopting `register_file_exchange`
   (template#73).

From v1.2.2, prereleases no longer publish `.deb` or `.rpm` packages.

## v1.3 - Server wiring sentinels

v1.3 added automatic `get_server_info` registration and stable extension
points in server and build configuration (template#89, template#91).

1. Move custom `make_server()` wiring into `DOMAIN-WIRING` and remote-service
   version reporting into `DOMAIN-UPSTREAM`.
2. Keep custom Ruff ignores, MkDocs navigation, and llmstxt sections inside
   their `PROJECT-*` blocks.
3. Add the optional Lucide tool-icon wiring by hand if wanted. `tools.py` is
   skip-listed, so existing projects do not receive that example
   (template#100).

Call `get_server_info` after the update and verify the server, package, and core
versions it reports.

## v1.4 - Shared docs become template-owned

v1.4 converted the Docker, OIDC, and authentication guides from frozen files
to hybrid documents (template#108).

1. Accept the current shared text and move project additions into
   `DOMAIN-DOCKER-EXTRA`, `DOMAIN-OIDC-EXTRA`, and `DOMAIN-AUTH-EXTRA`.
2. Set `CLAUDE_CODE_OAUTH_TOKEN` if the Copier update workflow should run its
   agent-assisted conflict and changelog analysis (template#109).
3. Review agent commits as untrusted changes. The v1.4-v1.6.0 workflow lacked
   permissions required by some agent jobs; v1.6.1 fixes that path.

## v1.5 - pvl-core 2, docs ownership, authorization, and debugging

v1.5 raised `fastmcp-pvl-core` to 2.x, converted the remaining operator docs
to hybrid ownership, and added optional authorization and debugging scaffolds
(template#112, template#113, template#115).

1. Move project content in `docs/index.md`, `installation.md`,
   `configuration.md`, `tools/index.md`, and `prompts.md` into their new
   topic-specific blocks. Preserve real tool and prompt catalogs in
   `DOMAIN-TOOLS-LIST` and `DOMAIN-PROMPTS-LIST`.
2. Run `uv lock`. Invalid remote or multi-auth configuration now raises an
   error instead of silently disabling authentication.
3. If adopting authorization, add `{PREFIX}_BEARER_TOKENS_FILE` and
   `{PREFIX}_ACL_PATH` to the skip-listed `.env.example`, then configure the
   supplied config and middleware stubs.
4. If adopting remote debugging, add
   `debug = ["fastmcp-pvl-core[debug]"]` to the project extras block and
   reconcile both Docker sync commands. Bind debugpy only to localhost or a
   secure tunnel. `{PREFIX}_DEBUG_WAIT=true` blocks startup until attachment.

## v1.6 - File Exchange upload extension

v1.6 raised pvl-core to 2.1 and wrapped File Exchange customization in a
stable block (template#121).

1. Run `uv lock`.
2. Move existing `register_file_exchange(...)` customization into
   `DOMAIN-FILE-EXCHANGE`.
3. Upload support remains opt-in. Implement and enable the receiver and
   validator only when required, then test size, expiry, and one-time-token
   rejection paths.
4. Adopt v1.6.1 before relying on all Copier agent jobs; it adds the missing
   OIDC permission and output-write capability (template#123).

## v1.7 - Repeated release candidates

No file migration or new secret is required. The release workflow gains
`force: prerelease` so an existing release candidate can advance to the next
revision (template#136). Use it only with the prerelease option enabled.

## v1.8 - Vale prose linting

v1.8 added Vale to CI and local pre-commit checks (template#142,
template#145).

1. Reconcile an existing `.vale.ini` and Base vocabulary with the template.
   Both are skip-listed.
2. Port the `vale-sync` and Vale hooks into the skip-listed
   `.pre-commit-config.yaml`.
3. Add these rules to the skip-listed `.gitignore`:

   ```gitignore
   .vale/styles/*
   !.vale/styles/config/
   ```

4. Add project terminology to the Base vocabulary, then run:

   ```bash
   vale sync
   vale --glob='!docs/superpowers/**' docs README.md
   uv run pre-commit run --all-files
   ```

CI checks findings on changed lines, but the local command can expose existing
prose debt.

## v2.0 - pvl-core 3 and File Exchange removal

v2.0 removes the File Exchange subsystem and raises pvl-core to 3.x
(template#151, template#153).

1. Before updating, rescue downstream code from the removed
   `DOMAIN-FILE-EXCHANGE` block and `docs/guides/file-exchange.md`.
2. Remove or replace `register_file_exchange`,
   `register_file_exchange_upload`, `ArtifactStore`, `ExchangeURI`, and
   `UploadRecord`. pvl-core 3 no longer exports them.
3. Rename deployment configuration from `{PREFIX}_EVENT_STORE_URL` to
   `{PREFIX}_KV_STORE_URL`. Update secrets, Compose, systemd, and operator
   docs. The deprecated old name was temporarily accepted by core but should
   not remain in project configuration.
4. Review conflicts around the `DOMAIN-*-EXTRA` documentation markers, which
   became pure HTML-comment blocks.

Verify that no retired API or active `EVENT_STORE_URL` reference remains.

## v2.1 - MCP Apps choice and versioned documentation

Add an explicit Copier answer:

```yaml
include_mcp_apps_scaffold: false
```

Set it to `true` only for a server that ships a visual MCP App
(template#158).

A v1.x project already has an ungated `_server_apps.py` placeholder, and some
projects replaced it with a real app before the answer existed. Before
updating, inspect and preserve the whole implementation, not only marked
blocks. Set `include_mcp_apps_scaffold: true` when retaining an app, then port
its tools, resources, and UI into the current app seams.

The move to mike-based documentation requires repository setup outside Copier
(template#157):

1. Seed `gh-pages` before changing Pages settings:

   ```bash
   uv run mike deploy --push --update-aliases unstable \
     --title "unstable (<current-version>)"
   ```

2. Set GitHub Pages to deploy from `gh-pages` at `/ (root)`.
3. Verify the branch with `uv run mike list` and build the docs.

## v2.2 - Initial configuration wizard

No mandatory migration is required for an uncustomized project. The browser
configuration wizard is new and initially covers only a subset of settings
(template#166). Adopt at least v2.2.1, which fixes first-render, escaping,
sandboxed-iframe, and missing-spec defects (template#168).

If exposing the wizard, install Chromium and run its browser tests before
publishing the docs.

## v2.3 - Wizard ownership boundary

v2.3 makes `wizard-spec.json` the project-owned domain surface and keeps the
JavaScript runtime template-owned (template#170, template#174).

1. Add the required `meta` object to an existing v2.2 spec:

   ```json
   {
     "meta": {
       "projectName": "<project>",
       "dockerImage": "<registry>/<project>:latest",
       "envPrefix": "<PREFIX>"
     }
   }
   ```

2. Express host mounts with `dockerVolume` and paths in the state volume with
   `dockerPath`. Each requires `var`; they are mutually exclusive.
3. Move domain browser assertions into
   `tests/test_config_wizard_domain.py`.
4. Replace any early guard level named `warn` with `warning`.

Local changes in `generators.js` or `wizard.js` are not a supported extension
surface and can be overwritten. Move them into the spec where possible.

## v2.4 - Authorization becomes a Copier choice

Add an explicit answer before resolving the update:

```yaml
enable_authorization: false
```

Set it to `true` if the project uses the pre-v2.4 ACL stubs. The default false
omits config, middleware, docs, navigation, and `.env.example` entries, so
accepting it can remove customized authorization blocks (template#177,
template#179). Reconcile `{PREFIX}_ACL_PATH` manually in the skip-listed
`.env.example`.

## v2.5 - pvl-core 4 authorization and clean detach

v2.5 raises pvl-core to 4.x and replaces its old authorization API
(template#181).

1. Replace `AuthorizationMiddleware`, `make_acl_authorizer`,
   `check_authorization`, `AuthzDenied`, and `expose_subject_in_error` with
   one FastMCP `AuthMiddleware`.
2. Use `make_acl_check(...)`, `make_claims_check(...)`, or `any_check(...)`.
   Do not install separate ACL and claims middlewares; that creates accidental
   AND semantics.
3. For authorization-enabled projects, add `{PREFIX}_ACL_PATH`,
   `{PREFIX}_AUTHZ_CLAIM`, and `{PREFIX}_AUTHZ_GRANTS` to `.env.example`.
4. Check behavior on stdio and unauthenticated HTTP. Stdio bypasses authz;
   unauthenticated HTTP has no subject and cannot access gated components.
5. Merge the v2.5 `.gitignore` additions manually because the file is
   skip-listed: `docs/superpowers/`, `.claude/`, `.mcp.json`, and
   `.repowise/`. Later v4 instructions refine the `.claude/` rule.

`FORKING.md` documents the optional clean detach from Copier. Use the v2.5.4
or newer form if making a project standalone (template#183, template#198).

## v2.6 - Complete wizard coverage and HTTP bind default

The wizard spec is skip-listed, so reconcile it manually with all settings
read by `ProjectConfig`, including transport, HTTP, authentication, OIDC,
stores, app domain, logging, and domain variables (template#205,
template#207). The new drift test reports missing and orphaned settings.

Also add `{PREFIX}_SERVER_NAME` and `{PREFIX}_INSTRUCTIONS` to the skip-listed
`.env.example` if operators should use them (template#206).

Bare `serve --transport http` now follows `ServerConfig.host`, whose default
is `127.0.0.1` (template#207). A non-container deployment that relied on the
old implicit all-interface bind must set `{PREFIX}_HOST=0.0.0.0` or pass
`--host 0.0.0.0`. The generated container command already does so explicitly.

## v2.7 - Structural gate and real MCP Apps vendoring

Add an explicit answer:

```yaml
enable_structural_gate: true
```

For existing projects, keep the diff gate enabled and use the v2.10
`structural_gate_assert_clean_tree` answer to handle legacy debt.

The then-skip-listed `.pre-commit-config.yaml` needs manual reconciliation
(template#211):

1. Add `default_install_hook_types: [pre-commit, pre-push]` and the
   `structural-diff-gate` system hook at the pre-push stage.
2. Expand Vale to `docs/` and `README.md`, excluding
   `docs/{superpowers,design,decisions}/` (template#209).
3. Reinstall hooks with `uv run pre-commit install --install-hooks`.

For projects with `include_mcp_apps_scaffold: true`, v2.7 replaces the inline
placeholder with a vendored SPA (template#220):

1. Rescue content from the removed `DOMAIN-APP-HTML` block.
2. Move it to `src/<module>/static/app.src.html` and replace old
   `<module>___<tool>` literals with `app___<tool>`.
3. Treat `app.src.html` as project-owned and `app.html` as generated. Do not
   edit `app.html`.
4. Allow network access during the trusted Copier task, then run
   `python scripts/vendor_spa.py --check`.

## v2.8 - Recursive config discovery

No unconditional migration is required. The wizard drift gate now discovers
composed config sections through `domain_env_suffixes(ProjectConfig)`
(template#224). Run the drift test and add genuinely missing fields to the
skip-listed wizard spec rather than suppressing the findings.

## v2.9 - CLI command extension point

Move custom Typer commands in template-owned `cli.py` into the new
`DOMAIN-COMMANDS` block (template#226). v2.9.1 also permits non-prefixed
external variables in the wizard when project source actually reads them
(template#228).

## v2.10 - Brownfield gate choice and Apps SDK update

When the structural gate is enabled, add:

```yaml
structural_gate_assert_clean_tree: true
```

Set it to `false` for a brownfield project with existing structural debt. This
disables only the whole-tree assertion; changed code still passes through the
diff gate (template#231).

For MCP Apps projects, update the import in the skip-listed `app.src.html`
from ext-apps 1.3.1 to 1.7.4 before the new vendor script runs, then regenerate
`app.html` (template#238). A stale source import can make the Copier task fail.
Move custom resource-level `AppConfig` domain or CSP settings into
`DOMAIN-APP-RESOURCE`, added in v2.10.5 (template#248), and test the app in its
sandboxed host.

v2.10.4 disables the weekly Copier schedule. Decide whether to keep manual
`workflow_dispatch` updates or restore a project-owned schedule. Also review
the expanded write permissions for the `@claude` responder and confirm
`CLAUDE_CODE_OAUTH_TOKEN` is present (template#243). The obsolete
`.gemini/config.yaml` is deleted; rescue it first only if it contains unrelated
project configuration.

## v2.11 - Renovate and repository bootstrap

v2.11 replaces Dependabot with Renovate and adds the aggregate `CI Success`
job (template#250).

The classic branch-protection procedure below applies only when stopping on
v2.11-v3.x. For a v4+ target, preserve the token and Renovate changes but use
the v4 ruleset migration instead of dispatching this historical Bootstrap.

1. Give `RELEASE_TOKEN` contents, pull-request, and administration write
   permissions.
2. Inspect current branch protection before merging the update. In this
   version Bootstrap uses a declarative branch-protection `PUT`; it replaces
   rather than merges settings. Encode required reviews, extra checks,
   restrictions, or admin enforcement in the workflow before the update lands.
3. Merging the update triggers Bootstrap. Verify auto-merge plus the required
   `CI Success` context; dispatch it manually only if the automatic run fails.
4. Confirm `.github/dependabot.yml` is gone and `renovate.json` plus
   `.github/workflows/renovate.yml` are present.

The first adoption can conflict at the end of `ci.yml`: pre-commit removed an
extra final blank line downstream while the template added `ci-success` at the
same location (template#252). Keep the new aggregate job and the project's
existing jobs.

v2.11.2 adds `CONFIG-VALIDATE` (template#255). If `ProjectConfig` already has
a custom `__post_init__`, keep one method and move validation into the new
block.

## v3.0 - Generated configuration surfaces

v3.0 replaces hand-maintained environment examples, wizard fields, README and
OIDC tables, and `server.json` environment arrays with generated content
(template#264, template#274, template#275, template#276).

Do not stop at v3.0.0 or v3.0.1 for an adoption. v3.0.0 allowed Copier to
patch generated files and leave conflicts (template#283), while the final
update-order fix arrives in v3.1 (template#302).

1. Before updating, inventory domain variables, descriptions, examples,
   requiredness, and wizard behavior in all existing config surfaces.
2. Move variables read by `ProjectConfig.from_env()` into config field metadata,
   including `help` and `tags`. Keep literal `env`, `env_int`, or `env_float`
   reads discoverable.
3. Put variables the scanner cannot see into the new project-owned
   `config-presentation.domain.yml`. Do not duplicate scanned variables.
4. Preserve the project's current `server.json` version and OCI identifier.
   Conflict resolution must not reset a released project to the scaffold's
   `0.1.0` values.
5. Keep the new generated marker pairs in README and docs, then run:

   ```bash
   python scripts/gen_config_surface.py
   python scripts/gen_config_surface.py --check
   ```

6. Move custom pre-commit hooks into `DOMAIN-HOOKS`.
7. Add `dataclass` to the skip-listed Vale vocabulary.
8. In the skip-listed `.gitignore`, change `.mcp.json/` to `.mcp.json` and add
   `.vscode/` if wanted. Remove the dead `{PREFIX}_READ_ONLY` entry from the
   project-owned MCPB manifest.

Generated-but-skip-listed files are no longer hand-editable. Put customization
in `config.py` metadata or `config-presentation.domain.yml`; each update's
after-stage generator rewrites the outputs.

## v3.1 - Safe post-update generation and release lockfile

1. Use Copier 9.4 or newer. Config generation now runs as an after-stage
   migration, after Copier restores domain code (template#302).
2. Update to at least v3.1.1 so the generator re-execs with a sufficiently new
   core instead of failing after output deletion (template#307).
3. Run `uv lock`; the final v3.1 line requires pvl-core 4.8.
4. For config construction that needs domain environment values, add a
   `config_contract_env` fixture seam to the skip-listed `tests/conftest.py`.
5. Ensure semantic-release stamps the project's own version in `uv.lock`.
   Existing projects received the `pyproject.toml` asset change but not the
   matching implementation in the then-skip-listed bumper (template#298).
   v3.2.2 fixes that ownership design; if passing through v3.1, port the
   `_bump_lockfile(version)` call manually.

## v3.2 - Tool visibility and manifest bumper ownership

Update to v3.2.2 (template#322, template#324, template#327).

1. Add `allowlist` and `denylist` to the skip-listed Vale vocabulary.
2. Move local manifest helpers and calls into the new
   `DOMAIN-MANIFESTS-HELPERS` and `DOMAIN-MANIFESTS` blocks in
   `scripts/bump_manifests.py`.
3. Run and commit `uv lock`. CI now uses non-mutating locked/frozen installs.
4. Test `{PREFIX}_TOOLS_ALLOW` and `{PREFIX}_TOOLS_DENY`. They are mutually
   exclusive; hidden tools disappear from listing and invocation, while
   resources and prompts are unchanged.

## v3.3 - Background-task backend

v3.3 configures the pvl-core 4.11 task backend on every server
(template#329). It does not turn ordinary tools into background tasks.

Review persistence before deployment:

1. Explicit `{PREFIX}_TASKS_URL` wins.
2. Otherwise a Redis `{PREFIX}_KV_STORE_URL` is reused.
3. Otherwise the backend is `memory://` and tasks are lost on restart.

Set `{PREFIX}_TASKS_URL=memory://` or a separate Redis URL if an existing Redis
KV store must not become the task queue. Treat credential-bearing URLs as
secrets and check that derived queue names do not collide between servers.

## v3.4 - Generated MCPB install configuration

v3.4 makes the MCPB manifest's `user_config` and `server.mcp_config.env`
generator-owned while preserving the surrounding project-owned manifest
(template#337).

1. Copy both existing objects before updating.
2. Represent each retained field under the manifest's `files:` entry in
   `config-presentation.domain.yml`. Each field needs a collected environment
   variable and snake-case `id`.
3. Run the generator and inspect both objects. Fixed mappings not backed by a
   declared config field are removed.
4. Dispatch the new **Pre-release check**, download the `.mcpb`, and install it
   before the next release (template#338).

Marketplace catalog publication now pushes directly to the catalog repository
rather than opening a pull request (template#334). If a plugin artifact exists,
verify `RELEASE_TOKEN` can push to that repository under its protection rules.

## v3.5 - Claude Code plugin scaffold

The new plugin channel is opt-in and defaults off (template#339). Persist the
decision explicitly:

```yaml
include_claude_plugin: false
```

Set it to `true` only when adopting or preserving a Claude Code plugin channel.

The new `.claude-plugin/**` files are immediately skip-listed and
project-owned. Their seed version is `0.0.0`; the next stable release stamps
the real version before publication. For an existing hand-built plugin,
remove duplicate local stamping logic from `DOMAIN-MANIFESTS*` and ensure each
manifest appears once in semantic-release assets.

Verify the catalog-repository permissions described under v3.4 and check both
manifest versions and the `.mcp.json` `uvx --from` pin after the next release.

## v3.6 - Generated Claude plugin configuration

No new Copier answer or automatic config screen is introduced. To opt in,
declare paired entries in project-owned `config-presentation.domain.yml`
(template#340):

```yaml
files:
  .claude-plugin/plugin/.claude-plugin/plugin.json:
    kind: claude-plugin-user-config
    fields:
      PREFIX_SOURCE_DIR:
        id: source_dir
        type: directory
        required: true

  .claude-plugin/plugin/.mcp.json:
    kind: claude-plugin-env
    fields_from: .claude-plugin/plugin/.claude-plugin/plugin.json
```

Preserve existing `userConfig` and `env` objects first. Generation replaces
those objects but preserves identity, version, command, arguments, and release
pins. Keep the exec-form plugin command; shell-form cannot interpolate
`${user_config.*}`. Mark credentials `sensitive: true`.

## v4.0 - Release branches, rulesets, and release notes

v4.0 changes both repository protection and the release operating model
(template#360, template#361, template#365).

1. Replace the old blanket `.claude/` entry in the skip-listed `.gitignore`:

   ```gitignore
   .claude/*
   !.claude/skills/
   ```

   Otherwise the generated contributor skills remain ignored.

2. Initialize the new project-owned public-import snapshot:

   ```bash
   uv run python tests/test_import_surface.py --update
   git diff -- tests/public_import_surface.txt
   uv run pytest tests/test_import_surface.py -q
   ```

3. Add exactly one `<!-- version list -->` insertion line to the skip-listed
   `CHANGELOG.md`. Preserve existing release history; PSR writes no new
   sections without the marker (template#364).
4. Add `backports`, `hotfix`, `ruleset`, `rulesets`, `upsert`, and `upserts` to
   the skip-listed Vale vocabulary.
5. Ensure project-owned MkDocs blocks include the release notes navigation and
   llmstxt entry, and that `docs/releases/index.md` contains one
   `RELEASE-PAGES` marker pair.
6. Confirm `RELEASE_TOKEN` has contents, pull-request, and administration
   writes and belongs to an admin for the v4 PSR direct-push and merge-back
   flow. Confirm `CLAUDE_CODE_OAUTH_TOKEN` for release-note drafting.
7. Review and customize the rendered Bootstrap workflow and ruleset JSON before
   merging the update. The merge triggers Bootstrap automatically; it upserts
   `protect-main`, `protect-release-branches`, and `protect-release-tags`, then
   removes classic `main` protection. Dispatch it manually only if that run
   fails. Private repositories on GitHub Free may not support repository
   rulesets.

The following PSR controls apply only when stopping on v4.x. For a v5+ target,
complete the persistent migration above, including rulesets, snapshots, docs,
vocabulary, and secrets, then use the v5 Release Prepare process instead.

When operating on v4, adopt these release controls:

- A Release dispatch on `main` creates a stable release.
- Create exact `release/X.Y` branches for candidates. Dispatch there for
  `X.Y.Z-rc.N`; use `finalize: true` for stable promotion.
- Let every stable branch release complete its automated merge-back or later
  trunk releases can deadlock.
- Delete spent protected release branches with admin bypass.
- Replace the rolling Docker `:unstable` channel with `:edge`; use immutable
  candidate tags when testing an rc.

## v4.1 - Pull-request title gate and committed manifest checks

v4.1 makes the pull-request title gate part of `CI Success` (template#369).
Retitle open pull requests to one of `build`, `chore`, `ci`, `docs`, `feat`,
`fix`, `perf`, `refactor`, `revert`, `style`, or `test`, then rerun the failed
job. No new push is required.

Normalize committed release pins to the latest published stable and keep them
equal (template#378, template#382):

- `server.json` version, PyPI package versions, and OCI tag
- Claude plugin `plugin.json` version
- Claude plugin `.mcp.json` `--from ...==X.Y.Z` pin

Admin bypass remains necessary to delete spent `release/X.Y` branches and
disposable `v*-rc` smoke tags.

## v5.0 - PSR to knope release pull requests

v5 replaces python-semantic-release's compute-and-push flow with reviewed
knope release pull requests (template#408, template#409). Copier adds
`knope.toml`, `release-prepare.yml`, the new `release.yml`,
`scripts/stamp_manifests.py`, and release-flow tests. It deletes the PSR config,
`scripts/bump_manifests.py`, `scripts/merge_back.sh`, and old release tests.

Do these steps in order:

1. Before updating, preserve all project-specific logic from
   `scripts/bump_manifests.py`. For v3.2.2+ projects, this is normally the
   bodies of `DOMAIN-MANIFESTS-HELPERS` and `DOMAIN-MANIFESTS`. Older scripts
   have no markers, so inspect the whole file. Copier deletes the file and all
   downstream customization with it.
2. Adapt those bodies into the same markers in `scripts/stamp_manifests.py`.
   The new script receives the version as `argv[1]`, runs only for stable
   versions, raises `StampError` rather than warning, and appends every changed
   path to `stamped`. Remove local `pyproject.toml` and `uv.lock` handling;
   knope and the template-owned stamper own them.
3. Normalize the skip-listed changelog while retaining
   `<!-- version list -->`:

   ```bash
   python - <<'PY'
   import re
   from pathlib import Path

   path = Path("CHANGELOG.md")
   path.write_text(
       re.sub(r"^## v(?=\d)", "## ", path.read_text(), flags=re.MULTILINE)
   )
   PY
   ```

   Reword an intro that names PSR and add `knope` to the skip-listed Vale
   vocabulary.
4. Confirm `RELEASE_TOKEN` has contents, pull-request, and administration
   writes. Admin ownership is required for Bootstrap and protected cleanup,
   not for CI to run on the release pull request.
5. Remove local tests, prose, and automation that expect PSR behavior.
   `perf:` no longer releases by itself; use `fix:` for a real performance
   defect or set `override_version`. Reverts no longer enter `CHANGELOG.md`.

Use the final v5.0.2 behavior (template#411, template#413, template#416):

1. Dispatch **Release Prepare** only on the default branch or an exact
   `release/X.Y` branch. Deeper or dashed release branch names are rejected.
2. Review and merge the generated release pull request. Its merge is the
   release decision. Never use GitHub's **Update branch** button; redispatch
   Release Prepare to recreate an outdated prep branch.
3. A candidate creates no port pull request. A stable release from a release
   branch creates a bookkeeping port pull request to `main`; review and merge
   it separately.
4. Promotion after an rc must contain only release metadata. Prepare another
   rc if code or docs changed.
5. Use `override_version` for chore/perf-only ranges or when a computed version
   is already reserved or tagged elsewhere.

Open release pull requests reserve versions, prepare runs are globally
serialized, promotion is checked both before PR creation and before tagging,
and mutable publishing channels recheck ordering at publish time. Smoke-test
adoption with `knope prepare-release --dry-run`, then run the full gate.

## v5.1 - Release notes move into the release pull request

Release Prepare now drafts and commits the `docs/releases/` page onto every
release pull request, so every tag contains its own notes page (template#420).
The post-publication body-upgrade path and
`<!-- release-notes-pending -->` marker are gone.

1. Confirm `CLAUDE_CODE_OAUTH_TOKEN` is present.
2. Do not merge until the `draft-notes` job succeeds and the release pull
   request tree contains the intended page. Drafting normally adds a second
   commit, but a valid unchanged page needs no new commit. If the job fails or
   the page is absent, retry or redispatch.
3. Use `skip_notes: true` only as an explicit outage escape hatch or when a
   hand-written page is already present.
4. Redispatch Release Prepare for an open release pull request created under
   v5.0; do not update it manually.
5. A stable v5.0 release that still carries the invisible pending marker is no
   longer updated automatically. After merging a manually dispatched backfill
   notes pull request, update its GitHub release body with `gh release edit`.

No project-owned file changes shape in this line. Existing notes pages without
the new range watermark are upgraded by their next accepted draft.

## v5.2 - Rolling `rc` image tag and the marketplace manifest path

Two release-pipeline corrections. Neither changes a project-owned file, and
both take effect on the next release after the update.

**The marketplace publish moves to `.claude-plugin/marketplace.json`**
(template#383). Claude Code loads a marketplace from that path and no other,
so the previous root-level `marketplace.json` write produced a catalog nothing
could install. The catalog at `<org>/claude-plugins` must already carry the
manifest at the new path, with a top-level `name`, `owner`, and `plugins`
array; the publish job now fails with a named error instead of bumping a file
no one reads. Verify with `claude plugin validate .` in a clone of the catalog
before the first stable release after this update. Projects with
`include_claude_plugin: false` are unaffected.

The bump now also writes `description` and `homepage` into this project's
entry, taken from its own metadata, and rewrites them on every release rather
than only on the first. The catalog's README plugin list is generated from
those descriptions, so a blurb hand-edited in the catalog is replaced on the
next release — curate it here, in the `domain_description` copier answer.

If the catalog ships `scripts/gen_readme.py`, the bump runs it and stages the
regenerated `README.md` in the same commit, so the catalog's default branch
never describes a plugin set it no longer serves. A catalog without that
script is unaffected; the step is guarded on the file existing.

**Pre-releases regain a rolling image tag.** An rc now pushes
`ghcr.io/<org>/<project>:rc` alongside its immutable `vX.Y.Z-rc.N` tag. The
tag is ordering-gated like `latest`: it moves only while the candidate's
version is still ahead of the newest stable, so a candidate for an
already-released version, or one cut on an older `release/X.Y` branch, never
pulls it backwards. It is not cleared when its release ships, so keep pointing
production at `latest`.

This does not reinstate the v4.0 `:unstable` channel. `edge` remains the
newest merged commit, `rc` is the newest candidate, and each tag has exactly
one producing workflow. Update any deployment that has been chasing exact rc
numbers to follow `rc` instead.

`claude-code-review.yml` now decides draft eligibility itself, in the
workflow, and reviews each commit once. No action is needed on update; the
behaviour change is that a push to a draft pull request no longer starts a
review run at all, and marking the pull request ready starts exactly one.

## v5.3 - pvl-core 4.11.3 and advertised OIDC scopes

The `fastmcp-pvl-core` floor moves to 4.11.3. `copier update` brings the new
constraint in; run `uv lock` (or `uv sync`) afterwards so the project's
lockfile resolves a core that satisfies it.

The release changes what an OIDC-authenticated server tells its clients to
ask for. Protected-resource metadata now advertises `openid offline_access`
instead of a set derived from `{PREFIX}_OIDC_REQUIRED_SCOPES` — which is
empty in `multi` mode, so clients asked for no scopes, received no refresh
token, and lost the session at every access-token expiry.

Check the client registration at your authorization server before deploying:
a client that is not permitted `offline_access` may have the whole
authorization request rejected with `invalid_scope`. The server drops a
default scope the authorization server does not list in its own
`scopes_supported`, so a provider-level omission is handled for you (with a
WARNING naming the dropped scope), but a client-level restriction is not
visible in discovery and cannot be. Where that applies, set the new
`{PREFIX}_OIDC_ADVERTISED_SCOPES` to the set that client may request; it is
taken verbatim, with the required scopes added on top.

Deployments using bearer tokens, or no authentication, are unaffected.

## v5.6 - Release candidates publish to PyPI, an installable plugin zip, and stricter config-surface and manifest checks

Release candidates now publish their wheel to PyPI. Before this, the
`publish-pypi` job skipped pre-releases, which made every rc `.mcpb` bundle
uninstallable: the bundle carries no code, it pins
`<your-package>[all]==<version>` and has `uvx` fetch that from PyPI on first
launch. Claude Desktop therefore failed the install with *"there is no
version of `<your-package>[all]==X.Y.ZrcN`"*, and a candidate could not be
tested through the channel candidates exist to test.

Check your `pypi` deployment environment before cutting the next rc. Open
**Settings → Environments → pypi** in the project repository. If it has
required reviewers, a wait timer, or a deployment branch rule that admits
only `main`, every rc release will now block or fail at that job where it
previously skipped it. Either widen the rule to cover `release/*` branches
and the tags you release from, or accept that each rc needs the same
approval a stable does.

Confirm the PyPI trusted publisher matches too. It is keyed on workflow file
and environment name, neither of which changed, so an existing publisher
keeps working — but a project that scoped its publisher more narrowly should
re-check it.

Nothing changes for people installing your package. A PEP 440 resolver skips
pre-releases unless the requirement pins one or `--pre` is passed, so
`pip install <your-package>` and `uv add <your-package>` still resolve to the
newest stable. The rolling surfaces that would expose a candidate to everyone
— the marketplace and MCP registry entries, the Docker `latest` tag, the docs
deploy — stay stable-only, and `scripts/stamp_manifests.py` still leaves
`server.json` and the Claude plugin manifests at the last published stable on
an rc prepare.

One consequence is permanent: PyPI versions cannot be deleted and reused. Each
rc you cut occupies its version number on PyPI forever.

### The Claude Code plugin now ships as a release asset

Projects with `include_claude_plugin` on now attach
`<project>-plugin-<version>.zip` to every GitHub release, and publish the same
archive as the `plugin-zip-edge` workflow artifact on each merge to `main`.
The zip vendors the project's own wheel and launches it from
`${CLAUDE_PLUGIN_ROOT}`, so it installs at versions PyPI does not serve.

No action is needed on update. The marketplace entry is unchanged: it stays a
thin PyPI pointer that follows stable releases only, so nothing about
`/plugin install` changes for your users.

Two things to know before the next release:

The packing job runs `uv build --wheel`, so a project whose wheel build needs
credentials or a network service will now hit that in one more job. Every
project already builds the same wheel in the `release` job, so this is a
repeat of work that succeeds today rather than a new requirement.

A project without a `.claude-plugin/plugin` directory skips the whole thing
with a warning, exactly as the marketplace publish already does. Turning
`include_claude_plugin` on is still what enables the channel.

To try a candidate's plugin without installing it:

```bash
claude --plugin-url <the release asset URL>
```

That loads it for one session and leaves no install record. It is the only
marketplace-free way to load a plugin: `claude plugin install` resolves names
through marketplaces and accepts no path, URL, or archive.

### Install screens now inherit a field's required-ness

`scripts/gen_config_surface.py` resolves an install screen's `required` flag
through the same rule the README table and spliced regions use, instead of
hardcoding `false`.

This changes generated output in one case: a domain field declared with **no
default at all** (`api_key: str`, not `api_key: str | None = None`) now renders
`"required": true` on the mcpb and Claude Code plugin screens. Previously it
rendered `false`, and an installer could click past a value the server cannot
start without. Regenerate and review the diff:

```bash
python3 scripts/gen_config_surface.py
```

Fields declared with any default, including `None`, are unaffected, as are all
template-owned fields. If a field is genuinely optional despite having no
default, say so explicitly in its field spec — `required: false` still wins.

### A field removal naming a non-baseline field now fails generation

Dropping a template baseline field from a screen is spelled `{PREFIX}_VAR: null`
in `config-presentation.domain.yml`. Misspelling the var name used to be
silently discarded, leaving the field on the screen with nothing to say why.
The generator now exits naming the file, the var, and the baseline fields it
does have.

If you have a typo'd removal, the next generation run fails until you fix the
spelling or drop the line. A removal that names a field you already removed
counts as a typo too. This surfaces an existing mistake rather than creating a
new one — the screen it produced was already not what you asked for.

### `Path`-typed defaults reach install screens

A config field annotated `Path` with a default no longer crashes generation
with `TypeError: Object of type PosixPath is not JSON serializable`. The
default is written as its string form.

If you worked around this with an explicit `default:` or `default: null` in the
field spec, you can drop the workaround and let the field's own default show
through. Nothing forces you to.

### PyYAML is a declared dev dependency

`scripts/gen_config_surface.py` imports `yaml`, which previously arrived only
transitively through `mkdocs-material` in the `docs` group. It is now declared
in the `dev` group, so a plain `uv sync` gets it and the generator uses the
project environment instead of falling back to its network bootstrap.

Run `uv lock` (or `uv sync`) after updating so the lockfile records it.

### The manifest pin tests now catch a stale or half-stamped version

`tests/test_release_flow_contract.py` asserts the "Manifest version lockstep"
rule directly: `server.json` and, where the plugin channel is on,
`plugin.json` and its `.mcp.json` must all pin one version. Two states that
previously passed now fail.

**A manifest reseeded to its placeholder.** A `copier update` can reset a
manifest's version to the template seed. Previously the suite skipped the pin
assertions whenever `server.json`'s top-level version was a seed value, so a
tree with one placeholder and the rest at a real release went unexamined —
and `server.json` is the MCP registry manifest, so the registry was being
told a version that was never published. The skip now requires *every* pin to
be a seed value, which is the genuine before-first-release state.

**A half-stamped release PR.** The existing history-scoped assertion admits
two values during a release PR, the last stable and the version being
prepared, so a tree with some manifests moved and some not satisfied it. The
new lockstep assertion does not.

If your suite goes red on either after updating, the manifests are telling
your users something untrue and the test is right. Fix the pins to agree:

```bash
python3 scripts/stamp_manifests.py <the version they should all carry>
```

A project that has not cut its first release is unaffected: its pins are all
seeds and the assertions skip, as before.

### `postinstall.sh` has a sentinel for extras — move any hand-added ones into it

`packaging/scripts/postinstall.sh` now carries a
`DOMAIN-POSTINSTALL-EXTRAS-START/-END` block holding one `EXTRAS` variable,
interpolated into all three of its `pip install` invocations. It is the
counterpart of the `DOCKERFILE-UV-EXTRAS` block, so the Linux packages can
install the same dependency set as the container.

**If your project added extras to this file by hand, this update conflicts on
exactly those lines, and resolving it in the template's favour silently drops
them.** That produces a `.deb`/`.rpm` installing a different dependency set
than your image and your `.mcpb` bundle, failing only at runtime.

Resolve by taking the template's side, then setting the variable:

```bash
# DOMAIN-POSTINSTALL-EXTRAS-START
EXTRAS="[all]"
# DOMAIN-POSTINSTALL-EXTRAS-END
```

Match it to the `--extra` flags in your `Dockerfile`'s `DOCKERFILE-UV-EXTRAS`
block. From this release on the edit lives inside a sentinel, so later updates
preserve it.

Projects that never added extras need do nothing: the default `EXTRAS=""`
renders the same three install commands as before.

This does not apply to `packaging/mcpb/pyproject.toml.in`, the mcpb manifest,
or the Claude plugin's `.mcp.json`. Those are `_skip_if_exists`, so your copies
are already yours and `copier update` never rewrites them — their `[all]` is a
seed, not a template-owned line.

### Fork pull requests now always get a `codecov/patch` status

`coverage-status.yml`, the fallback that posts `codecov/patch` for pull
requests from forks, previously posted nothing when it could not download the
coverage artifact. It now posts an `error` status instead, matching the
invariant `ci.yml` already held for the own-branch path.

No action is needed. It matters most if you list `codecov/patch` in
`extra_required_checks`: a required context that never reported left a fork
pull request waiting forever on a status that was not coming, exitable only by
an admin bypass or a ruleset edit. An `error` is recoverable by re-running the
workflow.

The visible change is that a fork pull request whose coverage artifact is
missing now shows a failed `codecov/patch` where it previously showed nothing.

### Re-run any release that failed at `publish-pypi`

If a release cut before this update failed at the `Publish to PyPI` step with

```
ERROR InvalidDistribution: Invalid distribution metadata:
      '2.5' is not a valid metadata version
```

then that version was built, tagged and released everywhere except PyPI. Update
to this template version, then re-run the failed `Release` workflow run for the
same tag.

**No version was burned.** The error comes from `twine check`, which the
publisher runs before the upload begins, so nothing reached PyPI and the
version is still free. The "PyPI versions cannot be deleted and reused" hazard
in the v5.6 note does not apply: a re-run publishes that exact version.

Check whether the other release artifacts landed before re-running. In the
observed cases every other job succeeded, so a re-run needs only the PyPI leg;
a job that publishes to a rolling channel is safe to repeat.

### Why it broke, and what stops it recurring

Two template-owned pins encoded one invariant that nothing asserted: the
core-metadata version the build backend emits has to be one the publisher's
twine understands. `pyproject.toml` left `hatchling` unbounded while
`release.yml` pinned `gh-action-pypi-publish` at v1.14.0, so when hatchling
1.32 began emitting `Metadata-Version: 2.5`, that action's bundled twine 6.1.0
refused it. The break arrived on hatchling's release schedule rather than on
anyone's decision, and it hit every project at once.

Both halves move in this release. The publisher is now pinned to v1.14.2, the
first release bundling twine 7.0.0, and `hatchling` is bounded `>=1.32,<1.33`
so the next metadata bump cannot arrive unannounced. `template-ci` now builds
the rendered project and runs `twine check` against the twine that the pinned
publisher bundles, so the pair is proven to agree here rather than in your
release.

**If you pin `hatchling` yourself**, the new bound arrives through `copier
update` in `pyproject.toml`, which is template-owned; resolve the merge in
favour of a bounded requirement. An unbounded `hatchling` still builds and
still passes your CI. It fails only at release time.

### Apply the same bound by hand in `packaging/mcpb/pyproject.toml.in`

`copier update` will not do this one for you. That file is `_skip_if_exists`,
so your copy is yours and the template never rewrites it. Edit it yourself:

```diff
 [build-system]
-requires = ["hatchling"]
+requires = ["hatchling>=1.32,<1.33"]
 build-backend = "hatchling.build"
```

This is housekeeping, not a fix. That backend runs only on the bundle's
fallback launch path, where a host uses `server.type: "uv"` with
`entry_point` and uv builds the bundle's project on the user's machine. The
primary path fetches the published wheel and never touches it, and nothing
`twine check`s this project, so the release failure above cannot happen here.
The bound keeps an end user's build off whatever backend happens to be newest
that day, and keeps one story about the build backend rather than two.

Nothing fails if you skip it. No CI check covers this file: a required check
that a `copier update` cannot satisfy would go red in every project until
someone hand-edited it, which is a poor trade for a non-functional change.

This is the only `_skip_if_exists` file that declares a build backend, so
there is no second copy of this edit to hunt down. It is, though, a good
example of the general class: a template change that lands in a file copier
will not touch, with nothing in the update to tell you. The render-and-diff
recipe under "Before every upgrade" is how to find the others.

## Unreleased

### Automatic Claude review is now opt-in

Automatic Claude pull-request review now defaults to off. Explicit `@claude`
mentions remain available through the mention responder.

To keep automatic review enabled, add this answer to `.copier-answers.yml`
before running `copier update`:

```yaml
enable_automatic_claude_review: true
```

When automatic review is disabled, remove any independently configured required
Claude-review check from the repository rulesets or branch protection. The
deterministic CI checks remain the merge gate.

### Release notes are now human-owned staging

Add these rules to the project-owned `.gitignore` when they are absent, so the
provider-neutral release skill remains tracked:

```gitignore
.agents/*
!.agents/skills/
```

Stop dispatching the removed **Release Notes** workflow. Before preparing a new
release identity, invoke `.agents/skills/writing-release-notes/SKILL.md` and
merge its `docs/releases/next.md` pull request. Remove local runbooks and
repository settings that assume a draft hold, `skip_notes`, or `full_redraft`;
deterministic promotion now refuses when reviewed notes are missing.

Keep `CLAUDE_CODE_OAUTH_TOKEN` only for the explicit `@claude` responder or an
opted-in automatic Claude review. Existing canonical `docs/releases/X.Y.md`
pages need no conversion.

### `domain_description` is capped at 100 characters

The MCP registry rejects a `server.json` `description` longer than 100
characters, and `publish-registry` is the last job of a release, so a long
blurb used to fail only after PyPI, Docker and the plugin had already
published. The answer now has a copier validator, and the rendered
`tests/test_release_flow_contract.py` fails when the committed
`server.json` description exceeds the cap.

**Shorten the blurb before running `copier update`.** If the stored
`domain_description` in `.copier-answers.yml` is over 100 characters (or
blank), `copier update` refuses before rendering anything, and the error it
prints is copier's generic one, not the validator's message:

```
ValueError: Question "domain_description" is required
```

Edit the value in `.copier-answers.yml` to 100 characters or fewer, then run
`copier update` again; the renders of `server.json`, `README.md` and the
other consumers pick the new value up. A blurb that was edited by hand in
`server.json` alone is caught by the new contract test instead.

### CLAUDE.md is now a stub; AGENTS.md carries the instructions

Project instructions moved to `AGENTS.md`, which every AAIF-aware agent reads;
`CLAUDE.md` is a three-line stub importing it. Task-shaped guidance (release
model and machinery, config contract, logging standard, tool registration,
repository protection) moved into skills under `.agents/skills/`, each with a
`.claude/skills/<name>` symlink so Claude Code still finds it.

`copier update` migrates automatically: the DOMAIN blocks from your committed
`CLAUDE.md` are spliced into `AGENTS.md`, `CLAUDE.md` is rewritten as the stub,
and the old `.claude/skills/authoring-issues-prs/` directory becomes a symlink.
Review the update PR's `AGENTS.md` diff to confirm your three DOMAIN blocks
arrived.

Do by hand only if it applies:

- If you had edited template-owned prose in `CLAUDE.md` outside the DOMAIN
  blocks, re-apply it in `AGENTS.md` — the migration prints a pointer to
  `git show HEAD:CLAUDE.md`.
- If you had customised a template-owned skill under `.claude/skills/`
  (before this release: `authoring-issues-prs`), the update replaces that
  directory with a symlink into `.agents/skills/` and logs `copier
  migration: removing real directory …`. Recover your edits with `git show
  HEAD:.claude/skills/<name>/SKILL.md`. If the customisation lived inside a
  `DOMAIN-*` sentinel block (e.g. `DOMAIN-AUTHORING-START`/`-END` in
  `authoring-issues-prs`), paste it back into the same sentinel in
  `.agents/skills/<name>/SKILL.md` — that block is preserved by every later
  update. Only edits **outside** a sentinel need a separate project-owned
  skill under `.agents/skills/<other-name>/`, since template-owned skills
  are otherwise re-rendered on every update.
- If your `.gitignore` predates the `!.agents/skills/` or `!.claude/skills/`
  exceptions, add both (the file is seeded once), or git ignores the skills
  and their symlinks.
- If `AGENTS.md` exceeds 40 000 characters, `tests/test_agent_instructions.py`
  fails: shorten the DOMAIN blocks or move detail into a project skill.
- If `_commit` in `.copier-answers.yml` is a bare commit hash rather than a
  tag-derived version, copier skips **all** migrations — the before-stage
  guard and `scripts/migrate_agent_instructions.py` alike. Before running
  `copier update`, remove `.claude/skills/authoring-issues-prs/` by hand
  (`git rm -r`); after it, move your three DOMAIN blocks from the committed
  `CLAUDE.md` (`git show HEAD:CLAUDE.md`) into `AGENTS.md` yourself and
  replace `CLAUDE.md` with the rendered stub, since none of that happens
  automatically in this case.
