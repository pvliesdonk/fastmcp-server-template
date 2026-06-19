# Co-locate authentication + authorization across the template

**Date:** 2026-06-19
**Status:** Design — approved, pending spec review
**Repo:** fastmcp-server-template (the template itself)
**Related:** PR #177 (added `enable_authorization` gating), issue #176

## Problem

Authentication (who the caller is) and authorization (what the caller may
do) are tightly related — authz consumes the subject that authn mints — but
the template documents them in structurally inconsistent places:

- **Authentication** lives only in docs: `docs/guides/authentication.md`
  (bearer, mapped multi-subject, OIDC explanation, troubleshooting). It is
  absent from the README.
- **Authorization** lives mostly in the README (`## Authorization (opt-in)`,
  gated by `enable_authorization`) plus the `config.py`/`server.py` stubs and
  the `.env.example` ACL block. It has **no docs page** — only a cross-link
  *from* the authn guide *to* the README section.

The result: the core feature (authn) is a deep docs guide, the optional
feature (authz) is documented in the README, and they are stitched together
by a README-pointing cross-link. A reader cannot find the two auth concerns
next to each other anywhere.

Authn/authz are template-owned and have little domain dependence, so this is
a template-structure issue, not a per-project one. The one domain-dependent
part is *which of a project's tools require which scope* — that needs a
seeded, customizable home.

## Goal

Make authn and authz travel together on every surface — README, `.env`, and
docs — with authz template-owned and gated by `enable_authorization`, and the
depth living in two adjacent, cross-linked guides. Give the downstream a
seeded place to document its own tool→scope mapping.

## Non-goals (explicitly out of scope)

- **OIDC de-duplication.** The authn guide's OIDC *explanation* and
  `docs/deployment/oidc.md`'s *deployment recipe* serve different audiences
  (in-depth reference vs. "what it takes to run in a normal environment").
  They are intentionally distinct and stay as-is.
- Any change to the authn content itself beyond repointing one cross-link.
- Any change to the runtime auth/authz code (`fastmcp-pvl-core`) — this is a
  template docs/scaffold restructuring only.

## Design

### Surface 1 — Docs: two adjacent guides

- `docs/guides/authentication.md.jinja` stays the in-depth authn reference.
  Its one change: the existing cross-link (currently
  `→ README.md#authorization-opt-in`, gated by `enable_authorization`) is
  **repointed** to the new authorization guide, staying gated.
- **NEW** `docs/guides/authorization.md.jinja` — the in-depth authz content
  **moved out of the README**: ACL TOML schema, subjects & scopes,
  subject↔bearer alignment, load semantics, privacy default, and the
  `fastmcp-pvl-core` "see also" links. It also contains:
  - A back cross-link to the authentication guide at the subject boundary
    ("subjects are minted by the auth layer — see the Authentication guide").
    Always safe to render (the authz guide only exists when authz is on; the
    authn guide is always present), so this link is **not** gated.
  - A `DOMAIN-AUTHZ-SCOPES` sentinel block giving the downstream room to
    document which of *its* tools require which scope, seeded with a
    commented example table the project replaces (kept across copier update
    via the same 3-way-merge mechanism as `DOMAIN-AUTH-EXTRA`):

    ```markdown
    <!-- DOMAIN-AUTHZ-SCOPES-START — list THIS server's gated tools; kept across copier update -->
    <!-- Replace with your tool→scope mapping. Example: -->
    | Tool | Required scope |
    |------|----------------|
    | `delete_entry` | `write` |
    | `search`       | `read`  |
    <!-- DOMAIN-AUTHZ-SCOPES-END -->
    ```

#### Conditional file creation

The authorization guide must be **absent** when `enable_authorization` is
false, not merely empty — an orphaned page (present on disk, missing from
nav) fails `mkdocs build --strict` ("page exists but not in nav"). Use
copier's conditional-filename idiom:

```
docs/guides/{% if enable_authorization %}authorization.md{% endif %}.jinja
```

When the flag is false the rendered filename is empty and copier skips the
file. The nav entry is gated to match (below).

#### Nav

`mkdocs.yml.jinja` gains an Authorization entry immediately after
Authentication, wrapped in `{% if enable_authorization %}`:

```yaml
      - Authentication: guides/authentication.md
{% if enable_authorization %}      - Authorization: guides/authorization.md
{% endif %}
```

(The `llms.txt` section globs `guides/*.md`, so the new page is picked up
automatically when present and absent when not — no separate change there.)

### Surface 2 — README: brief side-by-side pointers

Immediately after `## Configuration`, two short adjacent sections replace the
current fuller `## Authorization (opt-in)` section:

- `## Authentication` (always rendered) — 2–3 lines: bearer token or OIDC,
  pick one; link to the Authentication guide.
- `## Authorization (opt-in)` (gated by `enable_authorization`) — 2–3 lines:
  off by default, point `*_ACL_PATH` at an ACL file to gate tools by scope;
  link to the Authorization guide.

All ACL schema / subject-alignment / load / privacy detail currently in the
README moves into the authorization guide. The README authz block keeps its
`{% if enable_authorization %}` gate.

### Surface 3 — `.env.example`: naming symmetry

The authn (`# --- Auth (pick one flavor) ---`) and gated authz
(`# --- Authorization (optional opt-in) ---`) blocks are already adjacent
(lines 10–24). Only change: rename the authn header to
`# --- Authentication (pick one flavor) ---` for naming symmetry with the
docs/README. The authz block stays gated.

### Gating summary

`enable_authorization` continues to gate every authz surface, now including
the new guide:

| Surface | Gated? | Mechanism |
|---|---|---|
| README `## Authorization` pointer | yes | `{% if %}` block |
| README `## Authentication` pointer | no (authn is core) | always rendered |
| `.env.example` ACL block | yes | `{% if %}` block (existing) |
| `config.py`/`server.py` stubs | yes | `{% if %}` block (existing) |
| `guides/authorization.md` | yes | conditional filename |
| nav Authorization entry | yes | `{% if %}` in `mkdocs.yml.jinja` |
| authn→authz cross-link | yes | `{% if %}` (existing, repointed) |
| authz→authn back-link | no (target always present) | always rendered |

## Cross-reference integrity

The two guides cross-reference at the subject boundary. The gating asymmetry
(authn always present, authz present only when enabled) means:

- authn→authz link is gated (no dead link when authz off).
- authz→authn link is ungated (target always present; the link only renders
  at all when the authz guide itself is present).

This is the same dead-anchor class fixed in PR #177; the design preserves it
by construction.

## Testing / verification

Render and gate **both** branches (`enable_authorization` true and false)
from HEAD with smoke-answers:

- **ON:** `guides/authorization.md` present and in nav; authn→authz and
  authz→authn links resolve; README has both pointer sections; `.env` has
  both blocks. `mkdocs build --strict` passes; full render gate
  (ruff/format/mypy/pytest) passes.
- **OFF:** `guides/authorization.md` **absent** (no file, no nav entry, no
  orphan-page warning); README has only `## Authentication`; `.env` has only
  the authn block; no dead authn→authz link. `mkdocs build --strict` passes.

`smoke-answers.yml` already sets `enable_authorization: true`, so CI exercises
the ON branch; the OFF branch is verified locally (the established
convention).

## Downstream migration

Consumers on the current template will, on `copier update`:

- Gain `guides/authorization.md` (if they have `enable_authorization: true`).
- See the README authz detail collapse to a pointer; the moved content now
  lives in the guide.
- Need to populate the `DOMAIN-AUTHZ-SCOPES` table with their real tool→scope
  mapping (seeded example otherwise renders).

No code changes are required downstream; this is docs/scaffold only.
