# Config-wizard ⇄ env drift guards

**Issue:** [#203](https://github.com/pvliesdonk/fastmcp-server-template/issues/203)
**Date:** 2026-06-27
**Status:** Draft — pending review

## Problem

Nothing keeps a project's config-wizard spec in sync with the env surface the
server actually reads. Two drift directions were both seen in the wild:

- **Orphan** — the wizard offers `{PREFIX}_{SUFFIX}` vars no code reads
  (`server_name`/`instructions` before [#202]; caught only by manual review).
- **Missing** — the wizard omits settings the server *does* read (`logodev-mcp`
  shipped no auth/OIDC/base-url questions).

There was no programmatic way to enumerate the `ServerConfig` surface, so such a
test could not be written. That prerequisite now exists:
`fastmcp_pvl_core.server_config_env_suffixes()` (pvl-core ≥ 4.2.0, issue
[pvl-core #200]) returns the frozenset of suffixes `ServerConfig.from_env` reads.

## Goal

A single template-owned test that enforces **bidirectional full coverage**
between the wizard and the env surface, serving two obligations from two
contexts:

- **Guard 1 — scaffold ↔ core** (template maintainer's obligation): when
  pvl-core adds a `ServerConfig` setting, the **seed** `wizard-spec.json.jinja`
  must offer it. Runs in *template* CI against the rendered smoke project, where
  the domain surface is empty, so it reduces to "seed covers core".
- **Guard 2 — downstream wizard ↔ downstream env** (project author's
  obligation): each generated project's wizard must cover **its** surface =
  core + its own `ProjectConfig`. Ships rendered; runs in the project's CI.

These are the **same coverage logic in two contexts** — one rendered test does
both, because the domain scan is vacuous on the scaffold and live downstream.

## Definitions

- **Surface** = the set of `{PREFIX}_{SUFFIX}` env vars the server reads:
  - **Core**: `server_config_env_suffixes()` (the 18 `ServerConfig` suffixes).
  - **Domain**: the suffixes `ProjectConfig.from_env` reads, discovered by
    AST-scanning that method's source for `env`/`env_int`/`env_float` calls
    whose suffix is a string literal (the same technique the pvl-core helper's
    anti-drift test uses). The `server=ServerConfig.from_env(_ENV_PREFIX)` line
    is *not* a suffix read, so it contributes nothing. **Vacuous in the
    scaffold** (all domain reads are commented examples), live downstream.
- **Covered** = a setting `{PREFIX}_{SUFFIX}` is covered by the wizard when some
  question has `var == "{PREFIX}_{SUFFIX}"` **or** some `select` option's `emit`
  map sets that var. `advancedGroup` is irrelevant to coverage — it is UI
  grouping only. Hiding a setting from the default view is done with
  `advancedGroup`, **never** by omission.
- **Native** = non-prefixed vars (`FASTMCP_*`). Read by FastMCP /
  `configure_logging_from_env`, not enumerable here, so they are allowlisted:
  exempt from the orphan check and never required by the coverage check.

## The test — `tests/test_config_wizard_drift.py.jinja`

Template-owned, generic, main test lane (no browser). Reads the shipped
`wizard-spec.json`, calls `server_config_env_suffixes()`, and AST-scans the
project's `ProjectConfig.from_env`.

1. **Orphan check (fails CI).** For every wizard `var` (and every option
   `emit` key): if it does not start with `{PREFIX}_`, it must be a `FASTMCP_*`
   native var (else fail — an unknown non-prefixed var is a typo). Otherwise its
   suffix must be in `core ∪ domain`. A var matching neither is an orphan →
   fail, naming it.
2. **Coverage check (fails CI).** Every suffix in `core ∪ domain` must be
   *covered* (var-or-emit), except suffixes in the documented
   `_COVERED_BY_INFERENCE` exception set (see below). A surface suffix that is
   neither covered nor excepted → fail, naming it.

Both directions hard-fail. There is no per-project skip-set (which the
template-owned, re-rendered test could not carry anyway); the only escape hatch
is the universal, documented inference-exception set.

### `_COVERED_BY_INFERENCE` exception set

A small template-owned frozenset of core suffixes that have **no dedicated
wizard control by design**, each with a one-line rationale comment:

- `AUTH_MODE` — auth mode is *inferred* by `ServerConfig` from which auth vars
  are set (the `auth` select is a no-`var` routing key, per [#205]); exposing
  `AUTH_MODE` as a control would reverse that decision.

> **Decision point for review:** is `AUTH_MODE` the only inference-exception, or
> should it too get an emitted control? Default in this spec: documented
> exception (no control).

## Seed enrichment (required so the scaffold passes Guard 1)

The current seed covers 10 of 18 core suffixes. To reach full coverage:

- `deployment` select options gain an `emit`: `local` → `{PREFIX}_TRANSPORT=stdio`,
  `server` → `{PREFIX}_TRANSPORT=http`. Covers `TRANSPORT`.
- New **advanced** questions (gated `deployment=server` where applicable):
  - `HOST` (advancedGroup "Server")
  - `PORT` (advancedGroup "Server")
  - `BEARER_TOKENS_FILE` (advancedGroup "Auth"; alternative to `BEARER_TOKEN`)
  - `BEARER_DEFAULT_SUBJECT` (advancedGroup "Auth")
  - `EVENT_STORE_URL` (advancedGroup "Persistence"; alongside `KV_STORE_URL`)
  - `APP_DOMAIN` (advancedGroup "MCP Apps")
- `AUTH_MODE` — documented inference-exception, no question.

After enrichment, `core` is fully covered on the scaffold (TRANSPORT via emit,
the six advanced questions, `AUTH_MODE` excepted, the rest already present), so
the rendered smoke project passes Guard 1.

The new questions must satisfy the existing wizard invariants
(`test_config_wizard_spec_schema.py`): every `var` matches the schema pattern;
secret-bearing vars (none of the new ones are secrets) go in `secretKeys`;
self-contained `showIf` cascade (advanced server questions gate on
`deployment=server`).

## TDD plan

1. **Orphan RED:** a synthetic spec fixture with a deliberately-orphaned
   `{PREFIX}_NONSENSE` var → the orphan check fails. Then the real spec passes.
2. **Coverage RED:** assert the *un-enriched* seed fails the coverage check
   (missing `TRANSPORT` etc.); then enrich the seed → passes.
3. **Domain RED:** a synthetic `ProjectConfig.from_env` reading a suffix not in
   the wizard → coverage fails; a covered one → passes. (Unit-level, via a
   hand-built source string fed to the AST scanner, so it does not depend on the
   scaffold's empty domain.)
4. The `_COVERED_BY_INFERENCE` set is exercised: `AUTH_MODE` in the surface but
   not in the wizard does **not** fail.

## Scope

- **In:** floor bump `fastmcp-pvl-core>=4.2.0,<5`; the drift test; the seed
  enrichment above; doc note in CLAUDE.md's "Config wizard" section that
  coverage is now CI-enforced (offer settings via `advancedGroup`, never omit;
  the inference-exception set is the only escape).
- **Out:** changing the wizard runtime (`generators.js`/`wizard.js`); any
  pvl-core change (the helper already shipped in 4.2.0); MCP-Apps-conditional
  subtleties beyond gating the `APP_DOMAIN` question.

## Risks

- **AST domain scan fragility:** only literal-suffix `env*(_ENV_PREFIX, "X")`
  reads are seen; a downstream `ProjectConfig.from_env` using a non-literal or
  non-`env` read would be invisible (same documented limitation as the pvl-core
  helper). Acceptable: the scaffold convention is literal `env(...)` reads, and
  the test comment will state the limitation.
- **`APP_DOMAIN` conditionality:** relevant mainly to MCP-Apps projects. The
  seed question is gated/grouped accordingly; coverage still requires it because
  `ServerConfig` reads it unconditionally.
