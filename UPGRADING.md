# Upgrading generated projects

This guide is for maintainers updating a generated project with
`copier update`. It starts at template v1.0.0 and records the manual work that
Copier cannot do: preserving project-owned files, migrating removed extension
points, changing repository settings, and checking operational behavior.

Contributors: record migration steps under `## Unreleased` at the end of this
file, never under a version heading — the version is chosen at release time,
and `scripts/promote_upgrading.py` moves the section into its minor's file
then. See "Writing UPGRADING.md" in `CLAUDE.md`.

This file is the index: each released minor's section below is a one-line
pointer, and the full migration steps live in that minor's own file under
[`upgrading/`](upgrading/). Read the files whole — each one is complete for
its minor, and a partial read (a grep, a tail) of a combined document is how
migration steps get missed. Read the current minor's file when your target
includes a newer patch in that line, then every later minor's file through
the target. This matters for a project on v1.2.0: v1.2.1 and v1.2.2 contain
migration work recorded in the v1.2 file. Unless you need to diagnose an
intermediate change, update straight to the newest patch of the newest minor
rather than stopping on an early patch.

## Before every upgrade

1. Read every applicable minor's file under `upgrading/` before running
   Copier. Complete all
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

- `.vale/styles/config/vocabularies/Base/accept.txt` — for targets before
  the template's own vocabulary moved to the re-rendered
  `vocabularies/Template/accept.txt` (template#366), template prose arriving
  in a release could need terms the seeded file lacks;
- `.claude-plugin/**` — the plugin scaffold and its README;
- `packaging/mcpb/` — `manifest.json.in`, `pyproject.toml.in`, `build.sh` and
  the entry shim, which track the mcpb CLI and manifest version;
- `.gitignore`, `.vale.ini`, `config-presentation.domain.yml`.

How much this matters depends on how far behind you are, and it is worth
knowing that it is often nothing. Between v5.0.0 and v5.6.1 no skip-listed
file changed at all; from v4.0.0 the set is two files. A v3.x jump is the one
that carries real content.

## v1.0 - Copier foundation and initial packaging

Steps: [upgrading/v1.0.md](upgrading/v1.0.md).

## v1.1 - Automated Copier updates and extension sentinels

Steps: [upgrading/v1.1.md](upgrading/v1.1.md).

## v1.2 - README ownership, pre-commit, and dependency groups

Steps: [upgrading/v1.2.md](upgrading/v1.2.md).

## v1.3 - Server wiring sentinels

Steps: [upgrading/v1.3.md](upgrading/v1.3.md).

## v1.4 - Shared docs become template-owned

Steps: [upgrading/v1.4.md](upgrading/v1.4.md).

## v1.5 - pvl-core 2, docs ownership, authorization, and debugging

Steps: [upgrading/v1.5.md](upgrading/v1.5.md).

## v1.6 - File Exchange upload extension

Steps: [upgrading/v1.6.md](upgrading/v1.6.md).

## v1.7 - Repeated release candidates

Steps: [upgrading/v1.7.md](upgrading/v1.7.md).

## v1.8 - Vale prose linting

Steps: [upgrading/v1.8.md](upgrading/v1.8.md).

## v2.0 - pvl-core 3 and File Exchange removal

Steps: [upgrading/v2.0.md](upgrading/v2.0.md).

## v2.1 - MCP Apps choice and versioned documentation

Steps: [upgrading/v2.1.md](upgrading/v2.1.md).

## v2.2 - Initial configuration wizard

Steps: [upgrading/v2.2.md](upgrading/v2.2.md).

## v2.3 - Wizard ownership boundary

Steps: [upgrading/v2.3.md](upgrading/v2.3.md).

## v2.4 - Authorization becomes a Copier choice

Steps: [upgrading/v2.4.md](upgrading/v2.4.md).

## v2.5 - pvl-core 4 authorization and clean detach

Steps: [upgrading/v2.5.md](upgrading/v2.5.md).

## v2.6 - Complete wizard coverage and HTTP bind default

Steps: [upgrading/v2.6.md](upgrading/v2.6.md).

## v2.7 - Structural gate and real MCP Apps vendoring

Steps: [upgrading/v2.7.md](upgrading/v2.7.md).

## v2.8 - Recursive config discovery

Steps: [upgrading/v2.8.md](upgrading/v2.8.md).

## v2.9 - CLI command extension point

Steps: [upgrading/v2.9.md](upgrading/v2.9.md).

## v2.10 - Brownfield gate choice and Apps SDK update

Steps: [upgrading/v2.10.md](upgrading/v2.10.md).

## v2.11 - Renovate and repository bootstrap

Steps: [upgrading/v2.11.md](upgrading/v2.11.md).

## v3.0 - Generated configuration surfaces

Steps: [upgrading/v3.0.md](upgrading/v3.0.md).

## v3.1 - Safe post-update generation and release lockfile

Steps: [upgrading/v3.1.md](upgrading/v3.1.md).

## v3.2 - Tool visibility and manifest bumper ownership

Steps: [upgrading/v3.2.md](upgrading/v3.2.md).

## v3.3 - Background-task backend

Steps: [upgrading/v3.3.md](upgrading/v3.3.md).

## v3.4 - Generated MCPB install configuration

Steps: [upgrading/v3.4.md](upgrading/v3.4.md).

## v3.5 - Claude Code plugin scaffold

Steps: [upgrading/v3.5.md](upgrading/v3.5.md).

## v3.6 - Generated Claude plugin configuration

Steps: [upgrading/v3.6.md](upgrading/v3.6.md).

## v4.0 - Release branches, rulesets, and release notes

Steps: [upgrading/v4.0.md](upgrading/v4.0.md).

## v4.1 - Pull-request title gate and committed manifest checks

Steps: [upgrading/v4.1.md](upgrading/v4.1.md).

## v5.0 - PSR to knope release pull requests

Steps: [upgrading/v5.0.md](upgrading/v5.0.md).

## v5.1 - Release notes move into the release pull request

Steps: [upgrading/v5.1.md](upgrading/v5.1.md).

## v5.2 - Rolling `rc` image tag and the marketplace manifest path

Steps: [upgrading/v5.2.md](upgrading/v5.2.md).

## v5.3 - pvl-core 4.11.3 and advertised OIDC scopes

Steps: [upgrading/v5.3.md](upgrading/v5.3.md).

## v5.6 - Release candidates publish to PyPI, an installable plugin zip, and stricter config-surface and manifest checks

Steps: [upgrading/v5.6.md](upgrading/v5.6.md).

## v6.0 - fastmcp-pvl-core 5 and composed instructions

Steps: [upgrading/v6.0.md](upgrading/v6.0.md).

## v6.1 - Generated configuration reference, curated README tables

Steps: [upgrading/v6.1.md](upgrading/v6.1.md).

## v7.0

Steps: [upgrading/v7.0.md](upgrading/v7.0.md).

## v8.0

Steps: [upgrading/v8.0.md](upgrading/v8.0.md).

## v8.1 - Health routes, the compose probe, and merge-commit port PRs

Steps: [upgrading/v8.1.md](upgrading/v8.1.md).

## v8.2 - Container logs and roadmapping convention

Steps: [upgrading/v8.2.md](upgrading/v8.2.md).

## Unreleased - pvl-core v8 and v9, security policy and enforced log-call grammar

`SECURITY.md` is now a template-owned file at the repository root, and
`bootstrap.yml` gained a `security` job that enables private vulnerability
reporting, Dependabot alerts and secret scanning push protection. After
`copier update`:

1. **If your project already had a `SECURITY.md`**, copier reports a
   conflict, because the template's version knows nothing of yours. Keep the
   template-owned sections and move your own scope, contacts and response
   targets into the `DOMAIN-SECURITY` block; that block survives later
   updates.
2. **Merging the update pull request re-runs Bootstrap**, since the
   workflow's own file changed. Check the run. The new job needs
   `RELEASE_TOKEN` with `administration: write`, which the rulesets already
   required. On a private repository it skips private vulnerability
   reporting, which GitHub offers on public repositories only, and it warns
   instead of failing when push protection is not available on your plan.
3. **Confirm the Security tab** now shows **Report a vulnerability** and the
   policy. Adjust the defaults in the `DOMAIN-SECURITY` block (acknowledge
   within 7 days, assess within 30, disclose within 90) if they do not fit
   your project.

### Make first-party log calls parseable

The `logging-standard` skill's message format is now a grammar rather than
two lines of prose, and `tests/test_logging_standard.py` (template-owned,
shipped verbatim) fails the build on every call under `src/` that breaks
it. Across the family only 37% of first-party calls conformed when the
check was written (template #611), so expect the test to fail on your
first run after `copier update`. The dependency floor moved to
`fastmcp-pvl-core>=7.2.0` for the checker; 7.2.0 is additive and changes no
logging behaviour.

1. **List the offenders.** `uv sync` to pick up the new floor, then
   `uv run pytest tests/test_logging_standard.py -q`. Each violation prints
   its file, line, reason and template.
2. **Rewrite each call** using the skill's "Message Format" table: event
   name first (`snake_case`, no prose), then `name=value` fields, one
   positional argument per placeholder. Split compound values
   (`attempt=%d/%d` becomes `attempt=%d max_attempts=%d`), move units and
   percent signs into the field name (`waiting_s=%.1f`, `ratio_pct=%d`),
   turn a parenthesised reason into a fixed-token value
   (`reason=no_app_domain`), and replace f-strings with `%s` arguments.
3. **Re-key anything that matched the old text.** A Loki or Grafana query,
   an alert or a test that asserted on the skeleton's own lines needs the
   new event names: `service_started` / `service_stopped`,
   `auth_enabled mode=…` / `auth_disabled mode=none`,
   `server_configured version=… name=… transport=… auth=…`, and
   `apps_scaffold_not_wired app_domain=…` / `apps_scaffold_inactive`.
   Tests that already assert on `record.args` rather than on the message
   keep passing.
4. **Do not route around the check.** It sees only level calls on a
   module-level `logging.getLogger(...)` name; `self.logger`, a logger
   imported from another module and `logger.log(level, ...)` are invisible
   to it, and the skill forbids them for that reason.

### Adopt fastmcp-pvl-core v8: prefixed logging variables, pvl-core-run uvicorn

The dependency floor moved to `fastmcp-pvl-core>=8.0.0,<9`. v8 owns the
root logger and runs uvicorn for the HTTP transport, and the template stopped
attaching its own handler and calling `uvicorn.run`. This renames two
operator variables and removes one, so the template release carrying it is
a major. Work through these in order:

1. **Refresh the lockfile.** `uv lock`, then commit `uv.lock` with the update
   pull request; CI installs with `--locked` and fails on the stale file.
2. **Rename the log-level variable.** `FASTMCP_LOG_LEVEL` is now
   `<PREFIX>_LOG_LEVEL`, in `.env`, a compose `environment:` block,
   `/etc/<name>/env`, an orchestrator manifest, and the Claude Desktop
   `.mcpb` user config (the regenerated manifest already reads the new
   name). The old name keeps working for one major and logs
   `log_level_env_deprecated` once at startup, so a missed one is loud, not
   silent.
3. **Remove `FASTMCP_ENABLE_RICH_LOGGING`** wherever you set it; the
   variable is gone. Its replacement, `<PREFIX>_LOG_FORMAT`, takes `rich` or
   `json`, and unset picks `rich` on a terminal and `json` everywhere else,
   which is what the image and the unit bought with `false` before. Neither
   the image, the packaged unit nor the wizard's unit sets anything now. A
   `COLUMNS` entry you added to get Rich output in a container is no longer
   needed either: `LOG_FORMAT=rich` renders one line per record without it.
4. **Re-key anything that parses the container or journal log.** Every
   record now renders through pvl-core's formatter. In JSON mode that is
   `{"ts": …, "level": …, "logger": …, "event": …, <fields>}` for a
   conforming call, a `"message"` key for anything else, and
   `client`/`method`/`path`/`status` for an access line. The
   `INFO: {"event": …}` and `LEVEL: message` shapes the v7 container log
   carried are gone.
5. **Tests that read stderr.** pytest's stderr is not a terminal, so the
   server logs JSON under test. A test that asserted on Rich-shaped output
   sets `<PREFIX>_LOG_FORMAT=rich` through `monkeypatch` before the code
   under test calls `configure_logging_from_env`, or asserts on
   `caplog.records` instead.
6. **`<PREFIX>_SHUTDOWN_GRACE_S`** now sets the SIGTERM drain window that
   `serve --transport http` hard-coded at 3 seconds. The default is 3, so
   nothing changes unless you set it.
7. **If your `cli.py` diverged from the template** in `_root` or in the
   HTTP branch of `serve`, resolve the update conflict toward the template:
   `configure_logging_from_env` takes the env prefix as its first argument,
   the root `StreamHandler` and the `httpx`/`httpcore` quieting are
   pvl-core's now (keeping yours renders every line twice), and
   `run_http(app, config=config.server, host=host, port=port)` replaces
   `uvicorn.run(...)`. `make_server()` passes the prefix too.
8. **Re-read the `logging-standard` skill.** Six of its statements were
   wrong against v8 (the level variable, the removed Rich switch, what
   happens to `uvicorn.access`, who governs `httpx`, whose function
   `configure_logging_from_env` is, and why access lines are rewritten);
   the rewrite also adds the renderer's rules for reserved field names,
   quoting and malformed calls.

### The package version attribute and the app-tool hash key

`<module>.__version__` now reports the installed distribution's version
(`importlib.metadata`) instead of the `0.1.0` literal the skeleton shipped,
so it matches `pyproject.toml` after every release; an import from an
uninstalled checkout reads `0.0.0+unknown`. Nothing to do unless a test of
yours asserted the literal.

`_server_apps._app_tool_meta` writes the deterministic app-tool hash under
fastmcp's public `tool_hash` key. The previous `_tool_hash` key was stripped
from the protocol-visible metadata by FastMCP 4, so app-tool addressing never
saw it (#614). A project that worked around this with its own
sentinel-safe helper can delete that helper after `copier update`.

### Startup log lines that moved to pvl-core

`make_server` no longer logs `auth_enabled mode=…` / `auth_disabled mode=none`;
pvl-core's own `auth_mode_resolved mode=… source=…` line (pvl-core#310) is the
announcement, and the `server_configured … auth=…` field still carries the
mode. Re-key anything that matched the two removed events. On the stdio
transport with an auth provider configured, a new WARNING,
`auth_configured_but_stdio_skips_enforcement mode=…`, says that FastMCP does
not enforce it there. `serve` now prints a malformed configuration value as
one `ERROR: configuration error: …` line on stderr with exit code 1 instead
of a Rich traceback; a wrapper that parsed the traceback has nothing to
parse. The `pip-audit` step no longer carries `--ignore-vuln CVE-2026-42561`;
a project that removed it by hand converges on the render again.

### Remove the local exemption for `scripts/migrate_agent_instructions.py`

`pyproject.toml`'s template-owned `per-file-ignores` now carry
`"scripts/migrate_agent_instructions.py" = ["S603", "S607"]`, like the
sibling scripts that make the same fixed-argv `git` call (#524). If your
project added that same key inside its `PROJECT-RUFF-IGNORES` block as a
workaround, delete your copy before merging the update: TOML rejects a
duplicate key in one table, so `uv sync`, `ruff` and every CI job fail on
`pyproject.toml` until it is gone.

### Read the resolved config from registrars through `config_for(mcp)`

`make_server` now binds the `ProjectConfig` it resolved to the server before
`register_tools`, `register_resources`, `register_prompts` and
`register_apps` run. A registrar reads it with `config_for(mcp)` from
`<module>._server_deps`; a handler takes
`config: ProjectConfig = Depends(get_config)` (#534). Nothing changes for a
project whose registrars need no configuration. Two cases need a hand:

1. **You edited the template-owned `register_tools(mcp)` line in
   `server.py`** to pass a config. `copier update` reverts that line and
   your registrar's environment fallback takes over silently. Restore the
   scaffold's signature, read `config_for(mcp)` inside the registrar, and
   drop the fallback.
2. **Your registrars build a subsystem from environment variables** (a jobs
   backend, an upstream client, a parameter default). Switch them to
   `config_for(mcp)` so a config passed to `make_server` reaches them. A
   test that calls such a registrar on a bare `FastMCP()` must then call
   `bind_config(mcp, config)` first, or build the server through
   `make_server`.

### Adopt fastmcp-pvl-core v9: one configuration error, auth that refuses to start

The dependency floor moved to `fastmcp-pvl-core>=9.0.0,<10`. Two of the
changes below break code a project may have written against v8, and one
changes whether a misconfigured server starts at all. v9 also closes several
paths that published operator-URL credentials into logs and into a response
header, so prioritise the upgrade if any of your operator URLs carry a
`user:pass@`.

1. **Catch `ConfigurationError`, not `ValueError` or `ImportError`.** An
   unusable `<PREFIX>_KV_STORE_URL` (unrecognised scheme, malformed
   `file://`, `dynamodb://` with no table name) and a backend extra that is
   not installed both raise `ConfigurationError` now (pvl-core #337). It
   reaches five public entry points, not only the two that name the store:
   `build_kv_store`, `build_event_store`, `build_jobs`,
   `register_health_routes`, and the `transfer` namespace's
   `register_transfer_routes` / `build_transfer_links`. `ConfigurationError`
   is exported from `fastmcp_pvl_core`, and the template's own `serve`
   already catches it, so the generated CLI needs no change; a project that
   added handling of its own around any of those calls must swap the type.
   One `ValueError` survives: an empty `namespace=` argument to
   `build_kv_store`, which is your literal rather than an operator's value.
2. **Stop wrapping what `jobs.start` and `jobs.defer` return.** Inside a
   native SEP-2663 task both verbs now await the work and return its own
   result, the way `run_with_deadline` always has, and their annotations
   widen to `Any` (pvl-core #324). pvl-core's own docs taught
   `return dict(await jobs.defer(...))` until this release, and that line
   raises `TypeError` under a task-negotiating client as soon as the work
   returns anything that is not a mapping. Drop the `dict(...)`:

   ```python
   # before: TypeError under a task-negotiating client as soon as the
   # work returns something that is not a mapping
   return dict(await jobs.start(work(), tool="rebuild_index"))

   # after
   return await jobs.start(work(), tool="rebuild_index")
   ```

   A tool that reads `handle["job_id"]` out of the return value has to
   branch on the mode or stop needing the id. FastMCP 4's default client
   negotiates the tasks extension, so this path is reached in ordinary use.
3. **A configured auth mode that builds no provider now refuses to start.**
   Where v8 logged `auth_mode_resolved ... server accepts unauthenticated
   connections` and carried on, v9 raises `ConfigurationError` naming the
   unset variables (pvl-core #316), and `serve` turns that into one line on
   stderr and exit 1. Auto-detection cannot produce this, since a mode is
   only detected when its variables are present; what reaches it is an
   explicit `<PREFIX>_AUTH_MODE=remote` or `=oidc-proxy` whose variables are
   not all set. If a deployment starts failing here, read the missing names
   off the error before assuming the release broke it: the server it refuses
   to start is one that was already serving without the authentication its
   configuration asked for. `AUTH_MODE` unset with nothing else configured
   still resolves to `none` and still serves unauthenticated.
4. **Credentials no longer travel in the MCP Apps origin.**
   `compute_app_domain` returned `urlparse(base_url).netloc`, which includes
   any `user:pass@`, and that value becomes the MCP Apps iframe and CSP
   origin; it now returns host and port only (pvl-core #343). Nothing to do
   for a `<PREFIX>_BASE_URL` without userinfo, which should be every one of
   them. The same change covers the wider leak behind it: `urlparse` echoes
   the raw netloc in one of its error messages, so several operator-URL
   paths were publishing credentials into logs. If an operator URL of yours
   does carry embedded credentials, treat them as exposed in whatever sink
   collected those logs and rotate them.
5. **Re-key anything matching pvl-core's own log lines.** v9 finishes moving
   core's messages to the `event_name key=value` grammar the
   `logging-standard` skill states, so a query or alert written against v8's
   text needs the new names: `tool_allowlist_active` /
   `tool_denylist_active` / `tool_allowlist_zero_match` (was `Tool allowlist
   active: ...`), `kv_store_legacy_fallback`, `kv_store_default_fallback`,
   `tasks_url_env_conflict`, `tasks_url_dropped`,
   `tasks_extension_not_registered`, `env_value_rejected`, and the
   `debugpy_*` family. Lines that already had an event name kept it and
   moved their trailing prose into `consequence=` and `action=` fields,
   `auth_mode_resolved` among them.
6. **Refresh the lockfile.** `uv lock`, then commit `uv.lock` with the update
   pull request; CI installs with `--locked` and fails on a stale file.
