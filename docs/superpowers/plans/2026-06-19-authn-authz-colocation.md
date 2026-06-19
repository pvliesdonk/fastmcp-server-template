# Authn/Authz Co-location Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make authentication and authorization travel together across the template's README, `.env.example`, and docs — promoting authorization into its own gated docs guide adjacent to the authentication guide, with brief README pointers and a seeded domain home for the project's tool→scope mapping.

**Architecture:** Pure copier-template docs/scaffold change. A new `docs/guides/authorization.md.jinja` (created only when `enable_authorization` is true, via a conditional filename) holds the in-depth authz content moved out of the README. The two guides cross-reference at the subject boundary. The README keeps brief side-by-side pointers. No runtime code changes.

**Tech Stack:** copier (Jinja2 templates), mkdocs + mkdocs-material + mkdocstrings + mike + llmstxt plugin, the project's render-and-gate (`ruff`, `mypy`, `pytest`, `mkdocs build --strict`).

## Global Constraints

- This is the **template repo**. Edit `.jinja` files; copier renders them. Copier reads from the git index/HEAD — **commit before rendering**, and render with `--vcs-ref=HEAD`.
- `enable_authorization` (copier bool, default `false`) gates every authorization surface. Authentication is core and always renders.
- The authorization guide must be **absent** (not empty) when `enable_authorization` is false — use the conditional-filename idiom so `mkdocs build --strict` never sees an orphan page.
- README links to guides use **relative repo paths** (`docs/guides/<x>.md`) — they render on GitHub where the README is read, and the authz pointer + authz guide are co-gated so the link never dangles.
- Cross-link gating asymmetry: **authn→authz link is gated** (target absent when off); **authz→authn link is ungated** (authn guide always present; the link only renders when the authz guide itself exists).
- Verify **both** branches every task: `enable_authorization: true` (via `tests/fixtures/smoke-answers.yml`, already set) and `=false` (via `--data enable_authorization=false`).
- Do NOT touch `docs/deployment/oidc.md.jinja` or the authn guide's OIDC section — the explanation-vs-recipe split is intentional and out of scope.

## Render commands (used in every task's verification)

```bash
# ON branch (smoke-answers sets enable_authorization: true)
rm -rf /tmp/aa-on && uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/aa-on

# OFF branch
rm -rf /tmp/aa-off && uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml --data enable_authorization=false . /tmp/aa-off
```

(Rendered project name is `smoke-mcp`, module `smoke_mcp`, env prefix `SMOKE_MCP`, github_org `pvliesdonk`.)

---

### Task 1: Authorization guide + nav entry + authn cross-link repoint

**Files:**
- Create: a conditional-filename template — literal name `docs/guides/{% if enable_authorization %}authorization.md{% endif %}.jinja` (see Step 1)
- Modify: `mkdocs.yml.jinja` (nav, ~line 114)
- Modify: `docs/guides/authentication.md.jinja` (cross-link, ~line 74)

**Interfaces:**
- Produces: a rendered `docs/guides/authorization.md` page (when authz on) at mkdocs URL slug `guides/authorization/`, reachable from the Authentication guide and the README. Contains a `DOMAIN-AUTHZ-SCOPES-START/END` sentinel pair for downstream tool→scope tables.
- Consumes: nothing from other tasks.

- [ ] **Step 1: Create the authorization guide with a conditional filename**

Create a file whose **literal name on disk** is:

```
docs/guides/{% if enable_authorization %}authorization.md{% endif %}.jinja
```

(When `enable_authorization` is false the rendered filename is empty and copier skips the file entirely.) Its contents:

~~~markdown
# Authorization

This server supports opt-in **per-subject authorization** from
`fastmcp-pvl-core`. It is **off by default** — every authenticated caller can
use every tool, resource, and prompt. Turn it on by pointing
`{{ env_prefix }}_ACL_PATH` at a TOML ACL file; the middleware is installed
only when the path is set, and individual tools opt in by declaring
`meta={"required_scope": "<scope>"}` at registration. A tool without
`required_scope` is unrestricted regardless of caller.

The wiring ships as commented stubs in `src/{{ python_module }}/config.py`
and `src/{{ python_module }}/server.py` — uncomment them to enable the
`acl_path` config field and the `AuthorizationMiddleware` registration.

## ACL TOML schema

```toml
[subjects]
"user:alice@example.com" = ["read", "write"]
"user:admin@example.com" = ["*"]              # wildcard — any required scope passes
"service:ci-bot"         = ["read"]
"local"                  = ["*"]              # stdio mode subject
```

- **Subject strings are opaque.** The `<kind>:<id>` convention is
  documentation only; the library treats each subject as a literal string.
- **`*` is the only library-treated special scope** — it grants every
  required scope. Subject-side wildcards (`*` as an ACL key) are rejected at
  load time.
- **Scope vocabulary is domain-defined.** Per-project or per-folder gating is
  encoded into the scope string itself (e.g. `read:project-foo`,
  `write:vault/personal`).

## Subjects and bearer alignment

Subjects are minted by the authentication layer — see the
[Authentication guide](authentication.md) for how bearer tokens and OIDC map
callers to subject strings. The subject keyed in the ACL TOML is the same
string used as a *value* in the bearer-tokens TOML
(`{{ env_prefix }}_BEARER_TOKENS_FILE`) — keep the two consistent. In
single-token mode every caller shares one subject (the library default,
currently `"bearer-anon"`, overridable via
`{{ env_prefix }}_BEARER_DEFAULT_SUBJECT`); in stdio mode the subject is
`"local"`.

## Load semantics and privacy

The ACL file loads **once at startup** and `load_acl` fails fast with
`ConfigurationError` on any malformed entry (a typo aborts startup rather
than silently denying). Denied requests are logged at WARNING with the
subject; the wire-side error omits the subject by default — pass
`AuthorizationMiddleware(..., expose_subject_in_error=True)` to surface it on
internal-only servers.

## Gated tools

<!-- DOMAIN-AUTHZ-SCOPES-START — list THIS server's gated tools; kept across copier update -->
<!-- Replace with this server's tool→scope mapping. Example: -->
| Tool | Required scope |
|------|----------------|
| `delete_entry` | `write` |
| `search`       | `read`  |
<!-- DOMAIN-AUTHZ-SCOPES-END -->

## See also

- [fastmcp-pvl-core README — Authorization](https://github.com/pvliesdonk/fastmcp-pvl-core#authorization-opt-in--authorizationmiddleware) — full design, the `check_authorization` per-call helper, and per-token subject mapping.
- [Authorization submodule spec](https://github.com/pvliesdonk/fastmcp-pvl-core/blob/main/docs/specs/authorization-submodule.md) — design rationale and deviations table.
~~~

- [ ] **Step 2: Add the gated nav entry**

In `mkdocs.yml.jinja`, find (inside the `PROJECT-NAV-START`/`END` block):

```yaml
      - Authentication: guides/authentication.md
  - MCP Interface:
```

Replace with (note: `{% if %}`/`{% endif %}` abut the surrounding lines so both branches render clean YAML — on → both entries, off → only Authentication, no blank line):

```yaml
      - Authentication: guides/authentication.md
{% if enable_authorization %}      - Authorization: guides/authorization.md
{% endif %}  - MCP Interface:
```

- [ ] **Step 3: Repoint the authentication guide's cross-link to the new guide**

In `docs/guides/authentication.md.jinja`, the cross-link currently reads (inside its existing `{% if enable_authorization %}` block):

```
For the per-tool authorization that consumes these subjects, see [Authorization (opt-in)](https://github.com/{{ github_org }}/{{ project_name }}/blob/main/README.md#authorization-opt-in) in the project README.
```

Replace that one line with:

```
For the per-tool authorization that consumes these subjects, see the [Authorization guide](authorization.md).
```

(Leave the surrounding `{% if enable_authorization %}` / `{% endif %}` gate untouched — the link stays gated so it never points at an absent page.)

- [ ] **Step 4: Commit**

```bash
git add "docs/guides/{% if enable_authorization %}authorization.md{% endif %}.jinja" mkdocs.yml.jinja docs/guides/authentication.md.jinja
git commit -m "feat(scaffold): add gated Authorization guide adjacent to Authentication"
```

- [ ] **Step 5: Render both branches and verify presence/absence**

Run the ON and OFF render commands (top of plan). Then:

```bash
echo "ON: guide present?";  ls /tmp/aa-on/docs/guides/authorization.md && echo OK
echo "ON: nav has Authorization?"; grep -c "Authorization: guides/authorization.md" /tmp/aa-on/mkdocs.yml
echo "ON: authn->authz link repointed?"; grep -c "\[Authorization guide\](authorization.md)" /tmp/aa-on/docs/guides/authentication.md
echo "ON: authz->authn back-link?"; grep -c "\[Authentication guide\](authentication.md)" /tmp/aa-on/docs/guides/authorization.md
echo "ON: sentinel present?"; grep -c "DOMAIN-AUTHZ-SCOPES-START" /tmp/aa-on/docs/guides/authorization.md

echo "OFF: guide absent?"; test ! -e /tmp/aa-off/docs/guides/authorization.md && echo "absent OK"
echo "OFF: nav has no Authorization entry?"; grep -c "Authorization: guides/authorization.md" /tmp/aa-off/mkdocs.yml || echo "0 OK"
echo "OFF: authn guide has no authz link?"; grep -c "authorization.md" /tmp/aa-off/docs/guides/authentication.md || echo "0 OK"
```

Expected: ON → all `1`/OK; OFF → guide absent, `0` nav/link matches.

- [ ] **Step 6: mkdocs --strict on both branches**

```bash
for d in /tmp/aa-on /tmp/aa-off; do
  (cd "$d" && uv sync --no-default-groups --group docs --frozen >/dev/null 2>&1 && uv run mkdocs build --strict 2>&1 | tail -2)
done
```

Expected: both "Documentation built" with no `WARNING`/`ERROR` (no orphan-page warning on OFF, no broken-link warning on ON).

---

### Task 2: README brief pointers + `.env.example` header rename

**Files:**
- Modify: `README.md.jinja` (replace the `## Authorization (opt-in)` section block, ~lines 112–140; add `## Authentication` before it)
- Modify: `.env.example.jinja` (line 10 header)

**Interfaces:**
- Consumes: the `docs/guides/authentication.md` and `docs/guides/authorization.md` pages from Task 1 (the README pointers link to them).
- Produces: nothing other tasks consume.

- [ ] **Step 1: Replace the README authorization section with brief side-by-side pointers**

In `README.md.jinja`, the current block is:

```
{% if enable_authorization -%}
## Authorization (opt-in)
... (full ACL schema, subjects, load/privacy, see-also) ...
{% endif -%}
## Post-scaffold checklist
```

Replace the entire `{% if enable_authorization -%}` … `{% endif -%}` block (the Authorization section, from the `{% if enable_authorization -%}` line through the `{% endif -%}` line, inclusive) with:

```
## Authentication

Callers authenticate via a bearer token or OIDC (mutually exclusive). See the [Authentication guide](docs/guides/authentication.md) for setup, mapped multi-subject tokens, OIDC, and troubleshooting.

{% if enable_authorization -%}
## Authorization (opt-in)

Per-subject authorization is **off by default** — every authenticated caller can use every tool. Point `{{ env_prefix }}_ACL_PATH` at a TOML ACL file to gate tools by scope (tools opt in via `meta={"required_scope": "<scope>"}`). See the [Authorization guide](docs/guides/authorization.md).

{% endif -%}
```

(The `## Post-scaffold checklist` heading that followed the old block stays exactly where it was, immediately after the `{% endif -%}`.)

- [ ] **Step 2: Rename the `.env.example` auth header for naming symmetry**

In `.env.example.jinja`, change line 10 from:

```
# --- Auth (pick one flavor) ---
```

to:

```
# --- Authentication (pick one flavor) ---
```

(Leave the `{% if enable_authorization %}# --- Authorization (optional opt-in) ---` block below it unchanged — the two headers now read "Authentication" / "Authorization".)

- [ ] **Step 3: Commit**

```bash
git add README.md.jinja .env.example.jinja
git commit -m "feat(scaffold): brief README authn+authz pointers; .env header symmetry"
```

- [ ] **Step 4: Render both branches and verify**

Re-run the ON and OFF render commands, then:

```bash
echo "ON: README has Authentication section?"; grep -c "^## Authentication$" /tmp/aa-on/README.md
echo "ON: README has Authorization section?"; grep -c "^## Authorization (opt-in)$" /tmp/aa-on/README.md
echo "ON: README authz links to guide (not anchor)?"; grep -c "docs/guides/authorization.md" /tmp/aa-on/README.md
echo "ON: README no longer carries the full ACL TOML schema heading?"; grep -c "^### ACL TOML schema$" /tmp/aa-on/README.md || echo "0 OK"

echo "OFF: README has Authentication only?"; grep -c "^## Authentication$" /tmp/aa-off/README.md
echo "OFF: README has NO Authorization section?"; grep -c "^## Authorization (opt-in)$" /tmp/aa-off/README.md || echo "0 OK"

echo "BOTH: .env header renamed?"; grep -c "Authentication (pick one flavor)" /tmp/aa-on/.env.example /tmp/aa-off/.env.example
```

Expected: ON → Authentication `1`, Authorization `1`, guide link `1`, no `### ACL TOML schema` (`0`); OFF → Authentication `1`, Authorization `0`; both `.env` headers renamed (`1` each).

---

### Task 3: Full both-branch gate + spec status

**Files:**
- Modify: `docs/superpowers/specs/2026-06-19-authn-authz-colocation-design.md` (status line)

- [ ] **Step 1: Run the full render-and-gate on both branches**

Re-render ON and OFF, then for each run the project's gate:

```bash
for d in /tmp/aa-on /tmp/aa-off; do
  echo "===== $d ====="
  (cd "$d" \
    && uv sync --all-extras --all-groups >/dev/null 2>&1 \
    && uv run ruff check . \
    && uv run ruff format --check . \
    && uv run mypy src/ tests/ 2>&1 | tail -1 \
    && uv run pytest -x -q 2>&1 | tail -1 \
    && uv run mkdocs build --strict 2>&1 | tail -1)
done
```

Expected: both branches — ruff "All checks passed!", format "already formatted", mypy "Success", pytest passing, mkdocs "Documentation built". (`pytest`'s browser/config-wizard tests skip without a built site/Chromium — that is pre-existing and unrelated.)

- [ ] **Step 2: Mark the spec implemented**

In `docs/superpowers/specs/2026-06-19-authn-authz-colocation-design.md`, change the `**Status:**` line from `Design — approved, pending spec review` to `Implemented`.

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-06-19-authn-authz-colocation-design.md
git commit -m "docs(spec): mark authn/authz co-location implemented"
```

---

## Self-Review

**Spec coverage:**
- Two adjacent guides → Task 1 (new authz guide + nav). ✓
- Authz content moved out of README → Task 1 (guide content) + Task 2 (README pointer replaces it). ✓
- authn→authz repoint (gated) → Task 1 Step 3. ✓
- authz→authn back-link (ungated) → Task 1 Step 1 ("Subjects and bearer alignment"). ✓
- README brief side-by-side pointers → Task 2 Step 1. ✓
- `.env` naming symmetry → Task 2 Step 2. ✓
- Conditional filename (no orphan page) → Task 1 Step 1 + Step 6 verify. ✓
- `DOMAIN-AUTHZ-SCOPES` seeded sentinel → Task 1 Step 1. ✓
- Gating across all surfaces → Tasks 1–2 + Task 3 OFF-branch gate. ✓
- OIDC out of scope → no task touches it. ✓

**Placeholder scan:** No TBD/TODO; every file's full content is inline; the seeded ACL/scope examples are intentional template content, not placeholders.

**Type/name consistency:** Slugs and paths are consistent — guide file `authorization.md`, nav `guides/authorization.md`, README link `docs/guides/authorization.md`, intra-docs links `authorization.md`/`authentication.md`, sentinel `DOMAIN-AUTHZ-SCOPES-START/END`.
