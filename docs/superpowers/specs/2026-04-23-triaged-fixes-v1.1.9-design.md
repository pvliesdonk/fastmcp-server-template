# Triaged fixes → template v1.1.9

**Date:** 2026-04-23
**Author:** Peter van Liesdonk (+ Claude Code)
**Status:** Approved; ready for implementation plan.

## Purpose

Resolve three open issues surfaced during the 2026-04-22 copier-sync and
post-sync triage, and ship them as a single template patch release.

| Issue | Priority | Summary |
|---|---|---|
| [#31](https://github.com/pvliesdonk/fastmcp-server-template/issues/31) | high | Shared docs hardcode `MCP_SERVER_` instead of `{{ env_prefix }}_`. |
| [#30](https://github.com/pvliesdonk/fastmcp-server-template/issues/30) | medium | `Dockerfile.jinja` state-dir `mkdir` + `VOLUME` are unprotected by sentinels. |
| [#37](https://github.com/pvliesdonk/fastmcp-server-template/issues/37) | medium | `CLAUDE.md.jinja` names upstream repos but doesn't tell an agent where to open a PR. |

## Delivery shape

Three focused PRs merged in sequence to `main`, then one
`template-release.yml` dispatch.

- **PR order:** #31 → #30 → #37.
  (#31 is the only user-visible bug; #30 and #37 are additive and low-risk.)
- **Release:** patch bump → **v1.1.9** once all three are on `main`.
- **Consumer rollout:** next weekly `copier-update.yml` cron, or manual
  dispatch.

## Scope

### PR 1 — #31 render shared docs with consumer env_prefix

**Files renamed (source → template):**
- `docs/deployment/docker.md` → `docs/deployment/docker.md.jinja`
- `docs/deployment/oidc.md` → `docs/deployment/oidc.md.jinja`
- `docs/guides/authentication.md` → `docs/guides/authentication.md.jinja`

**Edits within each renamed file:**
- Replace every literal `MCP_SERVER_` with `{{ env_prefix }}_`.
- Replace `ghcr.io/pvliesdonk/fastmcp-server-template:latest` (found at
  `oidc.md:97` on inspection) with
  `{{ docker_registry }}/{{ project_name }}:latest`.
- Re-grep each file after edits for `smoke-mcp`, `Smoke MCP`,
  `smoke_mcp`, and `fastmcp-server-template` to confirm no other stale
  literals were missed.  (Initial grep at spec-time found only the
  `oidc.md:97` case, but the audit step catches regressions if the
  three files acquire new literals before the PR lands.)

**`copier.yml`:**
- `_skip_if_exists` entries stay as `docs/deployment/docker.md`,
  `docs/deployment/oidc.md`, `docs/guides/authentication.md` — copier
  matches rendered paths, not source filenames. The comment already
  references the tracking follow-up (#29); no change needed.

**`template-ci.yml`:**
- In the existing rendered-project inspection step (after `copier copy`
  into the scratch directory), add:
  ```bash
  grep -q SMOKE_MCP_OIDC_ISSUER docs/deployment/oidc.md
  ! grep -F MCP_SERVER_ docs/deployment/docker.md docs/deployment/oidc.md docs/guides/authentication.md
  ! grep -F fastmcp-server-template docs/deployment/docker.md docs/deployment/oidc.md docs/guides/authentication.md
  ```
- Fails the CI gate on any regression.

**Behavior matrix:**

| Scenario | Result |
|---|---|
| Fresh `copier copy` into empty dir | Docs render with consumer's `env_prefix`. |
| `copier update`, consumer has customized docs | `_skip_if_exists` matches rendered path → file untouched, no conflict. |
| `copier update`, consumer deleted the docs | Fresh render with correct prefix. |

### PR 2 — #30 Dockerfile state-dir + VOLUME sentinels

**`Dockerfile.jinja` — two new sentinel pairs.**

Around the `mkdir` fragment (leave `chown` outside the block — it's
template-owned and shouldn't be customized by consumers):

```dockerfile
    # DOCKERFILE-STATE-DIRS-START — domain state subdirs; kept across copier update
    && mkdir -p /data/service /data/state/fastmcp \
    # DOCKERFILE-STATE-DIRS-END
    && chown -R appuser:appuser /app /data
```

Around the `VOLUME` line:

```dockerfile
# DOCKERFILE-VOLUMES-START — mounted volume list; kept across copier update
VOLUME ["/data/service", "/data/state"]
# DOCKERFILE-VOLUMES-END
```

**`template-ci.yml`:**
- Extend the existing sentinel-count assertion to require exactly one
  `DOCKERFILE-STATE-DIRS-START`, one `DOCKERFILE-STATE-DIRS-END`, one
  `DOCKERFILE-VOLUMES-START`, and one `DOCKERFILE-VOLUMES-END` in the
  rendered `Dockerfile`.

**Behavior matrix:**

| Scenario | Result |
|---|---|
| Fresh render | Sentinels + defaults. No semantic change to container. |
| `copier update`, consumer hasn't edited the block | Block matches exactly → no conflict. |
| `copier update`, consumer customized state dirs or volumes | `--conflict=inline` surfaces markers for operator to resolve (expected; this is the mechanism working). |

### PR 3 — #37 CLAUDE.md "Contributing fixes upstream"

**`CLAUDE.md.jinja`:** append a new top-level section immediately after
the existing Shared Infrastructure section, using the text drafted in
issue #37 body verbatim:

```markdown
## Contributing fixes upstream

- **Library-level fix** (anything you'd change in `fastmcp_pvl_core`):
  open a PR on `pvliesdonk/fastmcp-pvl-core`. After merge + release,
  bump `fastmcp-pvl-core` in this project's `pyproject.toml` (or wait
  for copier update).
- **Template-level fix** (anything template-owned in this file —
  `Dockerfile`, workflows, `server.py` skeleton, `CLAUDE.md` sections):
  open a PR on `pvliesdonk/fastmcp-server-template`. After merge +
  release, this project gets the fix on the next weekly `copier update`
  cron (or dispatch the workflow manually).
- **Domain-only fix** (anything inside `DOMAIN-START`/`DOMAIN-END`
  sentinels, `tools.py`, `resources.py`, `prompts.py`, `domain.py`,
  `tests/`): PR on this repo directly.

If a conflict marker appears in a copier-update bot PR, the conflict
itself often signals a template bug — investigate whether the template's
version needs fixing before resolving locally.
```

**`template-ci.yml`:** the existing CLAUDE.md sentinel-structure
assertion (3 `DOMAIN-START`, 3 `DOMAIN-END`) stays unchanged — the new
section lives outside every sentinel block.

## Release

After all three PRs are merged to `main`:

1. Dispatch `template-release.yml` with `bump=patch`.
2. Tag `v1.1.9` lands; GitHub release and updated `CHANGELOG.md` are
   produced by the workflow.

**CHANGELOG delta (produced by release workflow; content goal):**

```markdown
### Fixed
- docs/deployment/docker.md, docs/deployment/oidc.md, and
  docs/guides/authentication.md now render with the consumer's
  `env_prefix` instead of the hardcoded `MCP_SERVER_` placeholder (#31).

### Added
- Dockerfile.jinja sentinels `DOCKERFILE-STATE-DIRS-*` and
  `DOCKERFILE-VOLUMES-*` to protect consumer customization of state
  directories and volume list across copier updates (#30).
- CLAUDE.md "Contributing fixes upstream" section guiding agents to
  the correct upstream repo for library, template, and domain-only
  fixes (#37).
```

## Non-goals

- Issue #29 (sentinel-protect shared docs) — deferred per its own body;
  no consumer has customized these pages in a way that needs protection
  beyond `_skip_if_exists` yet.
- Issue #28 (PAT → GitHub App token) — separate workstream; requires
  creating the App outside this repo.
- Issue #36 (Claude Code auto-analyze conflicts) — ambitious, needs its
  own design.

## Risks & mitigations

- **Risk:** renaming the three docs to `.jinja` could inadvertently
  change rendering for a consumer that had modified them mid-update.
  **Mitigation:** `_skip_if_exists` protects existing consumer files;
  the rename affects only fresh renders or freshly-restored files.

- **Risk:** Jinja substitution inside the renamed docs could emit
  malformed content if a literal contains a lookalike of Jinja syntax
  (`{{ }}`, `{% %}`).
  **Status:** initial grep at spec time found zero `{{` / `{%` tokens in
  the three files, so this risk is theoretical for today's content.
  **Mitigation:** PR 1 re-greps immediately before the rename; the
  `copier copy` step in `template-ci.yml` fails loudly on any Jinja
  syntax error introduced later.

- **Risk:** new Dockerfile sentinels land but the assertion in
  `template-ci.yml` is forgotten, leaving them silently droppable on
  future convergence.
  **Mitigation:** PR 2 adds the count assertion in the same change; no
  split delivery.

## References

- Triage thread: this brainstorming session.
- Post-sync retrospective: #35 (closed 2026-04-23).
- Spec for the sync that created these follow-ups:
  `docs/superpowers/specs/2026-04-22-copier-sync-and-claude-md-parity-design.md`.
