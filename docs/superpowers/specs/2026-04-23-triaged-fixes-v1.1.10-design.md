# Triaged fixes → template v1.1.10

**Date:** 2026-04-23
**Author:** Peter van Liesdonk (+ Claude Code)
**Status:** Approved; ready for implementation plan.

> **Note on versioning.**  This spec was originally drafted targeting
> v1.1.9, but v1.1.9 was cut independently as a hotfix for a separate
> `uv.lock` / `Dockerfile` issue (#39).  The scope here is now targeting
> **v1.1.10**, unchanged in substance.

## Purpose

Resolve four open issues surfaced during the 2026-04-22 copier-sync and
post-sync triage (plus one catalog-publication bug spotted on the
2026-04-23 release of v1.1.9), and ship them as a single template patch
release.

| Issue | Priority | Summary |
|---|---|---|
| [#31](https://github.com/pvliesdonk/fastmcp-server-template/issues/31) | high | Shared docs hardcode `MCP_SERVER_` instead of `{{ env_prefix }}_`. |
| [#30](https://github.com/pvliesdonk/fastmcp-server-template/issues/30) | medium | `Dockerfile.jinja` state-dir `mkdir` + `VOLUME` are unprotected by sentinels. |
| [#37](https://github.com/pvliesdonk/fastmcp-server-template/issues/37) | medium | `CLAUDE.md.jinja` names upstream repos but doesn't tell an agent where to open a PR. |
| [#38](https://github.com/pvliesdonk/fastmcp-server-template/issues/38) | medium | `publish-claude-plugin-pr` silently no-ops when the plugin is absent from the catalog. |

## Delivery shape

Four focused PRs merged in sequence to `main`, then one
`template-release.yml` dispatch.

- **PR order:** #31 → #30 → #37 → #38.
  (#31 is the only user-visible bug in rendered output; #30 and #37 are
  additive and low-risk; #38 touches the release workflow itself and is
  the most sensitive, so it lands last so we can dispatch the release
  right after and watch it run end-to-end.)
- **Release:** patch bump → **v1.1.10** once all four are on `main`.
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

### PR 4 — #38 upsert marketplace.json in publish-claude-plugin-pr

**Problem.** The `publish-claude-plugin-pr` job in
`.github/workflows/release.yml.jinja` (lines 334–369) uses a `jq` `map`
that only *updates* an entry whose `.name` matches `{{ project_name }}`.
When the plugin isn't yet in the shared `pvliesdonk/claude-plugins`
catalog, the `map` is a no-op, `peter-evans/create-pull-request@v8`
short-circuits on no-diff, and the job reports green without publishing
anything.  First-time plugin publication is silently broken for
`scholar-mcp` and `image-generation-mcp` today.

**Catalog entry shape (current `markdown-vault-mcp`):**

```json
{
  "name": "markdown-vault-mcp",
  "source": {
    "source": "git-subdir",
    "url": "https://github.com/pvliesdonk/markdown-vault-mcp.git",
    "path": ".claude-plugin/plugin",
    "ref": "v1.23.0"
  },
  "version": "1.23.0"
}
```

**Change in `release.yml.jinja` (`Bump marketplace.json entry` step).**
Replace the single `jq` invocation with an upsert sequence: build a
prospective new entry, then branch on whether the name already exists:

```yaml
      - name: Bump marketplace.json entry
        env:
          VERSION: {% raw %}${{ needs.release.outputs.version }}{% endraw %}
        run: |
          cd catalog
          NEW_ENTRY=$(jq -n \
            --arg name   "{{ project_name }}" \
            --arg url    "https://github.com/{{ github_org }}/{{ project_name }}.git" \
            --arg ref    "v$VERSION" \
            --arg version "$VERSION" \
            '{
              name: $name,
              source: {
                source: "git-subdir",
                url: $url,
                path: ".claude-plugin/plugin",
                ref: $ref
              },
              version: $version
            }')
          jq --arg name "{{ project_name }}" \
             --arg v    "$VERSION" \
             --arg ref  "v$VERSION" \
             --argjson new "$NEW_ENTRY" '
            .plugins |= (
              if any(.[]; .name == $name)
              then map(if .name == $name then .version = $v | .source.ref = $ref else . end)
              else . + [$new]
              end
            )
          ' marketplace.json > marketplace.json.tmp
          mv marketplace.json.tmp marketplace.json
```

- When the entry exists: identical behaviour to today (update `version`
  + `source.ref` in place).
- When absent: append the prospective entry, which `peter-evans`
  surfaces as a non-empty diff → catalog PR is opened.

**Safety.** The rest of `source` (`source: "git-subdir"`, `path`,
`url`) is hardcoded to match the existing catalog schema. Any consumer
whose plugin shape differs (e.g. non-GitHub source) falls outside the
v1.1.10 scope — when that comes up, promote these values to
`copier.yml` variables (deferred; not in scope here).

**`template-ci.yml`:** the template self-test renders the workflow but
doesn't execute it.  Add a `grep` assertion on the rendered
`.github/workflows/release.yml` to prove the upsert block is present
(`"git-subdir"` and `".claude-plugin/plugin"` should both appear
verbatim; `any(.[]; .name == $name)` should also be present).  Do not
attempt to simulate the catalog API — that's an end-to-end concern
caught on the first real release.

**Verification at release time.** The first v1.1.10 dispatch will run
the updated workflow against the real catalog. Because the template
repo itself isn't listed in `pvliesdonk/claude-plugins`, the release
will exercise the *append* path and prove the fix end-to-end.

**Behavior matrix:**

| Scenario | Result |
|---|---|
| Consumer plugin already in catalog | `version` + `source.ref` updated; catalog PR opened (same as today). |
| Consumer plugin absent from catalog | New entry appended with the `git-subdir` shape; catalog PR opened (fixes the silent no-op). |
| Non-GitHub source (hypothetical) | Out of scope for v1.1.10; entry values are hardcoded to GitHub. |

## Release

After all four PRs are merged to `main`:

1. Dispatch `template-release.yml` with `bump=patch`.
2. Tag `v1.1.10` lands; GitHub release and updated `CHANGELOG.md` are
   produced by the workflow.
3. Watch the `publish-claude-plugin-pr` job run — this release is the
   live exercise of the #38 fix.  Template isn't in the catalog today,
   so the append path fires; a PR should appear in
   `pvliesdonk/claude-plugins` adding a `fastmcp-server-template`
   entry.

**CHANGELOG delta (produced by release workflow; content goal):**

```markdown
### Fixed
- docs/deployment/docker.md, docs/deployment/oidc.md, and
  docs/guides/authentication.md now render with the consumer's
  `env_prefix` instead of the hardcoded `MCP_SERVER_` placeholder (#31).
- release.yml.jinja publish-claude-plugin-pr job upserts the catalog
  entry instead of silently no-op'ing when the plugin is missing (#38).

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

- **Risk:** the new marketplace.json upsert path could append a
  malformed entry if the hardcoded `source.*` shape drifts from what
  the catalog schema expects.
  **Mitigation:** entry shape is copied from the live
  `markdown-vault-mcp` entry in `pvliesdonk/claude-plugins` on
  2026-04-23; v1.1.10's own release dispatches the workflow against
  the real catalog and exercises the append path, catching schema
  drift before any downstream consumer relies on it.

## References

- Triage thread: this brainstorming session.
- Post-sync retrospective: #35 (closed 2026-04-23).
- Spec for the sync that created these follow-ups:
  `docs/superpowers/specs/2026-04-22-copier-sync-and-claude-md-parity-design.md`.
