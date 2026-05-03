# Sentinel-protect shared deployment + auth docs

**Issue:** [#29](https://github.com/pvliesdonk/fastmcp-server-template/issues/29)
**Date:** 2026-05-03
**Status:** Approved (awaiting implementation plan)

## Problem

Three template-owned markdown files live under `docs/deployment/` and `docs/guides/`:

- `docs/deployment/docker.md.jinja` (32 lines, 4 sections)
- `docs/deployment/oidc.md.jinja` (202 lines, 6 sections)
- `docs/guides/authentication.md.jinja` (216 lines, 5 sections)

They document shared infrastructure shipped by `fastmcp-pvl-core` (auth providers, OIDC patterns, container deployment). All three are listed in `copier.yml`'s `_skip_if_exists`, which means once a downstream renders the project, copier never touches the files again on update — even when the template ships material improvements (new env vars, OIDC quirks discovered post-release, container-deployment best-practice updates).

Symmetrically, downstream consumers can never extend these docs with project-specific caveats without losing the template's future updates, because there's no machinery to merge.

## Design

Two-part change in a single PR. Both parts must ship together — neither alone solves the problem.

### Part 1 — Drop the three files from `_skip_if_exists`

Edit `copier.yml`, remove three lines from the `_skip_if_exists` list:

```yaml
- "docs/deployment/docker.md"
- "docs/deployment/oidc.md"
- "docs/guides/authentication.md"
```

Other entries in `_skip_if_exists` stay (they serve different purposes — `docs/index.md` etc. are project-narrative pages, tracked separately in #106).

After this part alone: future template updates to the three files would flow through to downstream on `copier update` via copier's standard 3-way merge — but downstream's existing customisations (if any, applied as direct file edits since the file was project-owned) would conflict-mark.

### Part 2 — Add `DOMAIN-{TOPIC}-EXTRA` sentinel block at end of each file

Append a sentinel-bracketed `## Project-specific notes` block to each `.jinja` file:

```markdown
... (last template-owned section content)

<!-- DOMAIN-{TOPIC}-EXTRA-START -->
<!-- Project-specific notes for {topic}; kept across copier update. -->

## Project-specific notes

<!-- Add domain-specific caveats here (e.g. "Keycloak requires X", "the
     /data/uploads volume must be writable by UID Y", "paperless-mcp tokens
     expire every 60 min"). Use sub-headings to organize if needed. -->

<!-- DOMAIN-{TOPIC}-EXTRA-END -->
```

Concrete sentinel names per file:

| File | Sentinel pair |
|---|---|
| `docs/deployment/docker.md.jinja` | `DOMAIN-DOCKER-EXTRA-START` / `DOMAIN-DOCKER-EXTRA-END` |
| `docs/deployment/oidc.md.jinja` | `DOMAIN-OIDC-EXTRA-START` / `DOMAIN-OIDC-EXTRA-END` |
| `docs/guides/authentication.md.jinja` | `DOMAIN-AUTH-EXTRA-START` / `DOMAIN-AUTH-EXTRA-END` |

The `-EXTRA` suffix communicates intent: this is for downstream's *additions* on top of template-owned content, not a wholesale rewrite.

### Why this naming

Three pre-existing sentinel families:

| Family | Used for | Examples |
|---|---|---|
| `PROJECT-*` | Config-extensibility (TOML/YAML lists) | `PROJECT-DEPS`, `PROJECT-RUFF-IGNORES`, `PROJECT-NAV` |
| `DOMAIN-*` | Prose-or-code customisation | `DOMAIN-START` in CLAUDE.md/README, `DOMAIN-WIRING`/`DOMAIN-UPSTREAM` in server.py |
| `CONFIG-*` | The `config.py` special case | `CONFIG-FIELDS`, `CONFIG-FROM-ENV` |

Issue #29 was filed before PR #91 unified the `DOMAIN-*` family for prose-customisation in template-owned markdown. The issue's original `DOCS-*` naming proposal predates that convention; we use `DOMAIN-*` to keep the mental model consistent and match what the post-#97 `CLAUDE.md.jinja` "Domain-only fix" enumeration already documents (`DOMAIN-*`, `CONFIG-*`, `PROJECT-*`).

### Why end-of-file with a labeled heading

- **Simple to find / reason about** — one sentinel pair per file, downstream knows exactly where to add notes.
- **Survives template restructure** — if we later rename or split a section in `oidc.md`, downstream's notes stay intact (they're after all template sections).
- **Renders as a clean separate section** — the `## Project-specific notes` heading gives downstream's content a visible home in the published docs site, not buried inside the template's narrative.

Per-section sentinels were considered and rejected: would multiply the maintenance surface (3 files × ~5 sections = 15 sentinel pairs) and most domain-specific caveats don't fit cleanly inside a single template section anyway.

Tradeoff: notes are physically separated from the template section they relate to. Downstream uses sub-headings inside the block (e.g. `### Authelia: token-cache quirk`) to keep relevance clear.

## Migration story

On the next `copier update` after this lands, each of the four downstream consumers (`image-generation-mcp`, `markdown-vault-mcp`, `scholar-mcp`, `paperless-mcp`) sees three changed files. Per-file 3-way merge:

| Downstream's current state | Outcome |
|---|---|
| Unchanged from template | Clean merge — picks up new template content + new empty `DOMAIN-{TOPIC}-EXTRA` block at end |
| Customised inside what becomes the EXTRA zone (end-of-file additions) | Clean — additions land inside the new sentinel markers via standard 3-way merge |
| Customised by replacing/editing template content (mid-file edits) | Conflict markers — one-time fix-up to relocate the customisation into the new `## Project-specific notes` block |

The third case is the only manual-work scenario. Per-downstream resolution: read the conflict, decide if the customisation is "still relevant on top of the new template content", paste into the EXTRA zone. Cost is small per downstream and one-time.

The PR body and commit message body will both call out the case-3 migration scenario explicitly so consumers' first `copier update` after the release isn't a surprise.

## Testing

- `template-ci.yml`'s `downstream-gate` already runs `mkdocs build --strict` against the rendered smoke project. HTML comments inside markdown are compatible with `mkdocs --strict`, so the new sentinels won't break the build.
- Manual verification before merging: spot-check each downstream's actual current `docker.md` / `oidc.md` / `authentication.md` against the template's content to predict how many will hit case-3 conflicts. If any are heavily customised, document that in the PR body so the user knows to budget reconciliation time on the next update.

## No documentation changes elsewhere

The `CLAUDE.md.jinja` "Contributing fixes upstream" enumeration (post-#97) already says "anything inside a `DOMAIN-*`, `CONFIG-*`, or `PROJECT-*` sentinel block" — captures the new `DOMAIN-{TOPIC}-EXTRA` family without further edits.

## Out of scope (tracked separately)

- The remaining `_skip_if_exists` docs (`docs/index.md`, `docs/installation.md`, `docs/configuration.md`, `docs/tools/index.md`, `docs/prompts.md`) — different design space per file, tracked in [#106](https://github.com/pvliesdonk/fastmcp-server-template/issues/106).
- A CHANGELOG callout for the migration scenario — the template's CHANGELOG is auto-generated from PR titles by python-semantic-release with no body content, so the callout lives in the PR body + commit message body instead.
