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

## Unreleased

### fastmcp-pvl-core 7: FastMCP 4

The floor moves to `fastmcp-pvl-core>=7.0.0,<8`, which itself requires
FastMCP 4 (`fastmcp[tasks]>=4,<5`). pvl-core 7's
`configure_task_backend(mcp, env_prefix, config)` takes the server as its
first argument and registers the SEP-2663 tasks extension on it; the
`fastmcp.settings.docket` global the old form mutated no longer exists.
`copier update` re-renders the standard `server.py` call site (now after
`FastMCP(...)` construction) and `tests/test_task_backend.py`.

Do these steps after the update:

1. Run `uv lock` to resolve the two new majors.
2. Search project-owned code — a local `server.py` variant, DOMAIN-WIRING
   blocks, extra entry points — for two-argument
   `configure_task_backend(<PREFIX>, config)` calls. Move each after the
   `FastMCP(...)` construction of the server it configures and pass that
   server first: `configure_task_backend(mcp, <PREFIX>, config)`. Register
   on the server you `run()` — a mounted child's extensions do not
   propagate to the root.
3. Project code reading MCP SDK objects must use SDK v2 snake_case
   (`icon.mime_type`, `annotations.read_only_hint`); the camelCase
   attribute names emit deprecation warnings. Seeded-once files such as
   `tools.py` are not re-rendered: existing camelCase keys in
   `annotations={...}` dicts still validate, but prefer snake_case in new
   code (the wire format stays camelCase either way).
4. If any project tool uses `ctx.elicit()`, note it now raises on the
   modern sessionless protocol era that FastMCP 4 clients negotiate by
   default; see the FastMCP 3→4 upgrade guide for the return-and-resume
   replacement.

### `ProjectConfig` now owns `server_name`

`config.py` gains a template-owned `server_name` field, declared **outside**
the `CONFIG-FIELDS` sentinels, and `server.py` reads it instead of calling
`env(...)` itself. That is what makes the shaped instruction identity and the
live `FastMCP` name agree when a name is supplied programmatically; before
this, `make_server(config=ProjectConfig(server_name="x"))` produced a server
named `x` whose instructions still opened with the environment-derived
default.

Nothing to do if your project never declared a `server_name` of its own: the
`{PREFIX}_SERVER_NAME` operator override behaves exactly as before, because
the field's default is a factory that reads it.

**If your project did declare one, act on it — one of the two failures is
silent.**

1. **Delete your `server_name` field from the `CONFIG-FIELDS` block.** Python
   does not error on a repeated annotation in one class body; the later
   definition simply wins, so yours silently shadows the template's. If yours
   carried a plain literal default (`server_name: str = "my-service"`) rather
   than a factory, that shadowing **stops `{PREFIX}_SERVER_NAME` from being
   read at all** — a working operator override disappears with no message.
2. **Delete any `server_name=...` line from your `CONFIG-FROM-ENV` block.**
   The template's `from_env` deliberately does not pass the field, so yours
   will not collide there — but if it reads the literal suffix
   (`env(_ENV_PREFIX, "SERVER_NAME", ...)`), the config-surface generator's
   AST scan discovers `{PREFIX}_SERVER_NAME` as a *domain* var while
   `config-presentation.yml` already declares it with template provenance,
   and generation aborts with the duplicate-name error. That one is loud:
   `scripts/gen_config_surface.py` fails on the next update.
3. **Drop any `mcp._mcp_server.name = ...` override from your
   `DOMAIN-WIRING` block.** It runs after the identity snippet is composed,
   so it reintroduces exactly the mismatch this change removes. Pass the name
   through `ProjectConfig(server_name=...)` instead.

The rendered `tests/test_config_contract.py` asserts the field stays outside
the sentinels and that the env read stays out of `from_env`, so a project
that reintroduces either fails its own suite rather than drifting.

### compose.yml is now a working quick start, and no longer ships a reverse proxy

`compose.yml` is re-rendered on every update, so this arrives whether or not
you edited it. Four things move.

1. **The Traefik labels are gone from `compose.yml`.** They never worked as
   shipped: the file declared no `networks:` stanza, so the service sat on the
   compose project's default network and the proxy had no route to it. If your
   deployment relied on them, copy the overlay from
   `docs/deployment/docker.md` ("Behind a reverse proxy") into a
   `compose.override.yml`, which Compose loads automatically alongside
   `compose.yml`. Note the `ports: !reset []` line in it: an override file
   cannot unpublish a port by leaving it out, because Compose appends to
   sequences rather than replacing them, so without that line the service
   joins the proxy network *and* keeps publishing 8000. `!reset` needs
   Compose 2.24.4 or newer. Confirm with `docker compose config` before
   starting.

2. **Rename any public hostname you kept in `{PREFIX}_HOST`.** The old router
   rule read that variable as a public FQDN; the server reads it as the
   interface it binds to. Set your hostname directly in the overlay's
   `Host(...)` rule and set `{PREFIX}_BASE_URL` to the public URL. Then reset
   `{PREFIX}_HOST` to a bind address or remove the line — leaving an FQDN
   there is now only a bind address, and the server will fail to start if the
   name does not resolve to a local interface.

3. **`build: .` is gone; the file pulls the published image.** If you relied on
   `docker compose up -d` rebuilding from your checkout, build explicitly
   first: `docker build -t <registry>/<project>:dev .`, then point `image:` at
   that tag.

4. **Stop setting `{PREFIX}_PORT` for containers, and check any `-p` mapping
   that depended on it.** The image's `CMD` now pins `--port 8000` alongside
   `--host 0.0.0.0`, so neither variable reaches the server inside a
   container. A `docker run -e {PREFIX}_PORT=9000 -p 9000:9000 ...` that
   worked before now serves 8000 behind a mapping pointing at a closed port,
   and nothing reports an error — the container starts and the published port
   simply refuses connections. Change the mapping's **host** side instead
   (`-p 9000:8000`), and drop `{PREFIX}_PORT` from any `.env` a container
   reads. Outside a container — the systemd and `serve` paths — the variable
   is unchanged and still works.

5. **Move any out-of-seam edits into the new sentinel blocks.** The file now
   carries `DOMAIN-COMPOSE-VOLUMES`, `DOMAIN-COMPOSE-ENVIRONMENT`,
   `DOMAIN-COMPOSE-SERVICES` and `DOMAIN-COMPOSE-VOLUME-NAMES`. Volumes,
   environment and sidecars you added directly to the template-owned lines will
   conflict on this update; resolve by taking the template side and re-adding
   your content inside the matching block, where it survives from now on. A
   *named* volume needs two entries: the mount in `DOMAIN-COMPOSE-VOLUMES` and
   its declaration in `DOMAIN-COMPOSE-VOLUME-NAMES`.

Also changed, and absorbed with no action: the file publishes `8000:8000`,
declares a TCP liveness healthcheck, and marks its `env_file` entry
`required: false` so a checkout without a `.env` still starts (needs Compose
2.24.0 or newer).

### Author and maintainer are asked for; the license choice now persists

Two questions arrive on this update, and three lines in re-rendered files gain
marker blocks. The defaults reproduce exactly what the template rendered
before, so a project that does nothing sees its author fields unchanged.

1. **Answer the two new questions, or accept the defaults.** `author_name`
   defaults to your `github_org` answer and `author_email` to
   `<github_org>@users.noreply.github.com` — which is what `packaging/nfpm.yaml`
   already composed. The automated weekly update runs `copier update --defaults
   --skip-answered`, so it will take those defaults silently; to set a real
   name, either run `copier update` by hand and answer, or add the two keys to
   `.copier-answers.yml`:

   ```yaml
   author_name: Jane Doe
   author_email: jane@example.com
   ```

   They feed `[project] authors` in `pyproject.toml` and `maintainer` in
   `packaging/nfpm.yaml`. If you had hand-edited either to a real name, set the
   answers to that name and the hand edit becomes the rendered value.

2. **`pyproject.toml`'s `authors` gains an `email` key.** It rendered as
   `authors = [{ name = "..." }]` before and now carries `email` as well. This
   is a one-time change to that line for every project; resolve it in favour of
   the template side once your answers are right.

3. **Nothing to do for the license, and one thing to stop doing.** The
   `license` line and its trove classifier in `pyproject.toml`, and `license`
   in `packaging/nfpm.yaml`, now sit inside `PROJECT-LICENSE` /
   `PROJECT-LICENSE-CLASSIFIER` marker blocks. The template does not re-render
   inside them, so a license you picked is no longer overwritten. If you were
   carrying a hand-written marker such as `# project-owned — keep across copier
   updates` on those lines, it is now redundant and can go; keep the value, and
   keep the `PROJECT-LICENSE` markers themselves.

   `LICENSE` also told you, incorrectly, that `packaging/nfpm.yaml` was
   protected from re-rendering. It was not, which is why that line needed a
   marker too. The corrected text ships with this update.

Also changed, and absorbed with no action: `pyproject.toml` gains an empty
`[tool.uv]` section carrying a `PROJECT-UV` block, which is where a temporary
dependency bound belongs — `scripts/check_pins.py` already gated those entries
but the section had no home. Projects rendered with
`include_mcp_apps_scaffold` also stop shipping `static/app.src.html` inside the
wheel; it is the vendoring input, not a distributable.

### Package description and keywords become yours to write

Both arrive as sentinel blocks, so nothing is lost on a later update. Neither
step is required for the update to succeed.

1. **Write a real package description, if you want one.**
   `packaging/nfpm.yaml` now wraps its `description:` in
   `DOMAIN-NFPM-DESCRIPTION` markers and still starts as your
   `domain_description`. That answer is capped at 100 characters only because
   the MCP registry rejects longer in `server.json`; `apt show` and `dnf info`
   impose no limit, so a paragraph belongs here. If you had already rewritten
   that description by hand, the value survives — move nothing, the markers
   render around it.

2. **Add your domain keywords.** `pyproject.toml`'s `keywords` list is no
   longer empty: it renders `mcp`, `model-context-protocol`, `fastmcp` and
   your project and distribution names, and carries a `PROJECT-KEYWORDS` block
   for the terms only you know — what the server is *about*. If you had
   populated the list by hand, expect a conflict on this line; keep your terms
   by moving them inside the block, and take the template's entries above it.
