# Config-surface generation + file-ownership model

**Date:** 2026-07-25
**Status:** design approved, implementation not started
**Closes (design-level):** #217, #254, #257, #258, #259, plus two issues still to be filed (§10)

## 1. Problem

Six issues, filed independently, are symptoms of one root cause.

| Issue | Reported symptom |
|---|---|
| #254 | `copier update` leaves a pristine downstream with 4 red tests |
| #257 | `examples/*.env` + `server.json` re-rendered but hold per-project content |
| #258 | `pyproject.toml`, `compose.yml`, `postinstall.sh`, `nfpm.yaml` hold per-project content with no seam |
| #259 | nothing verifies a template-owned file matches the render outside its sentinels |
| #217 | `_COVERED_BY_INFERENCE` is a designed extension point inside a template-owned file |
| *(to file)* | existing consumers **ship** a config wizard missing every question added since their first render |

`scripts/check_render_hygiene.py` already states the governing invariant, applied
narrowly to whitespace:

> Keeping a render byte-identical to its committed form is what makes copier's
> merge see `ours == base` and apply template changes cleanly.

Every issue above is another way `ours != base`.

### 1.1 Root cause A — ownership is prose, not data

`copier.yml` carries ~60 lines of comments explaining why each of 22 paths is
skip-listed, four unrelated sentinel prefixes (`DOMAIN-*`, `PROJECT-*`,
`CONFIG-*`, `DOCKERFILE-*`), and a hybrid-file convention documented in a
comment that concedes *"copier itself doesn't act on them."*

A rule that exists only in a comment cannot be mechanically checked. #257 (a
misclassification), #258 and #217 (missing seams), and #259 (no enforcement)
are all consequences.

### 1.2 Root cause B — the config surface is duplicated a dozen times

`fastmcp_pvl_core` already exports the env surface as data, and the current
drift test already consumes it:

```python
from fastmcp_pvl_core import domain_env_suffixes, server_config_env_suffixes
```

Yet that surface is hand-copied into many artifacts. A four-variable probe
(`OIDC_CONFIG_URL`, `KV_STORE_URL`, `BEARER_TOKEN`, `EVENT_STORE_URL`) found 11
template files restating it; `docs/configuration.md` surfaced separately via
`HTTP_PATH`, so **12 files is a lower bound**:

| File | Distinct core suffixes mentioned |
|---|---|
| `docs/javascripts/config-wizard/wizard-spec.json.jinja` | 17 / 18 |
| `.env.example.jinja` | 12 |
| `docs/guides/authentication.md.jinja` | 11 |
| `server.json.jinja` | 10 |
| `docs/deployment/oidc.md.jinja` | 8 |
| `examples/oidc.env.jinja` | 5 |
| `docs/deployment/docker.md.jinja` | 2 |
| `tests/test_config_wizard_smoke.py.jinja` | 2 |
| `examples/bearer-auth.env.jinja` | 1 |
| `README.md.jinja` | 1 |
| `docs/guides/authorization.md.jinja` | (gated file, not counted) |
| `docs/configuration.md.jinja` | (found via `HTTP_PATH`) |

A hand-maintained artifact whose source of truth is already available as data,
with a test guarding the gap, should be generated. `_COVERED_BY_INFERENCE`
(#217) is the tell: an escape hatch for a divergence that could not occur if
the artifact were generated.

### 1.3 The wizard regression (the unfiled issue)

`copier.yml` claims of `wizard-spec.json`: *"the entire file is domain
content."* This is false. `wizard-spec.json.jinja` ships **21 questions**, of
which 17 carry `{{ env_prefix }}_*` vars describing `ServerConfig` — verified by
reading the file.

Because the file is in `_skip_if_exists`, it is frozen at whatever template
version first rendered it. So every existing consumer publishes a config wizard
to its docs site that is **permanently missing every question added since**.
#254's four red tests are the symptom that surfaced this; the defect itself is
in shipped user-facing output.

## 2. Verified facts underpinning this design

Every claim below was checked, not assumed.

**Copier (9.17.0):**
- `_tasks` run on `copier copy` **and** `copier update`.
- `_copier_operation` (`'copy'` / `'update'`) is available in task context.
- `_copier_conf.src_path` exposes the template source — so a side-render needs
  no fresh network fetch.
- `--skip-tasks` / `-T` exists. This is the recursion escape for §5.

**`fastmcp-pvl-core`:**
- `origin/main` is `4cf1755`; latest tag `v4.4.0`.
- The local checkout sits on `chore/uv-lock-sync-4.3.0`, whose commit already
  merged as #228. **Stage 0 must branch from fresh `origin/main`, not this.**
- `ServerConfig` is a frozen stdlib dataclass with **18 fields**.
- Its 18 fields map **1:1** with the 18 env suffixes `from_env` reads — no gaps
  in either direction. So `field(metadata=…)` is a valid vehicle for all of them.
- 17 fields use plain defaults; one uses `field(default_factory=tuple)`. All
  defaults are immutable, so converting all 18 to `field(default=…, metadata=…)`
  is behaviour-preserving.
- Some help text already exists as code comments (on `event_store_url` and
  `bearer_default_subject`). The migration has a source to draw from.

**Template:**
- `HTTP_PATH` appears in the wizard but is **not** a `ServerConfig` field. It is
  read in `cli.py`, and `test_config_wizard_drift.py` explicitly asserts
  `"HTTP_PATH" not in _surface()` as a known special case.
- `config.py`'s `CONFIG-FIELDS` block is empty in the scaffold (commented
  examples only). All 18 core vars arrive via `ServerConfig.from_env(_ENV_PREFIX)`.

## 3. Solution shape: two layers

The layers are complementary, and **generation must come first** because it
changes the ownership class of ~9 files. Classifying them first would mean
authoring seams that the generation work then deletes.

- **Layer B — generate (drift becomes impossible).** Anything derivable from the
  config surface is generated. A generated file needs no seam, no conformance
  hash, and no `_skip_if_exists` decision; it drops out of the guarded set.
- **Layer A — guard (drift becomes detectable).** What remains is genuinely
  authored English — the 8 `docs/*.md` prose files, `CLAUDE.md`, `mkdocs.yml`,
  and the non-env regions of `pyproject.toml` / `compose.yml` / `nfpm.yaml`.
  These get an ownership manifest and a conformance digest.

## 4. Layer A: ownership model

### 4.1 Taxonomy

Five classes. Every rendered path gets exactly one.

| Class | Copier behaviour | Per-project content | Guarded how |
|---|---|---|---|
| `template` | re-rendered every update | none permitted | must equal render byte-for-byte |
| `seamed` | re-rendered every update | only inside declared seams | must equal render **outside** seams |
| `seeded` | `_skip_if_exists` | entire file | unguarded — downstream owns it |
| `generated` | produced by a generator or task | n/a | regenerated; never compared to a render |
| `excluded` | `_exclude` | n/a | never rendered |

### 4.2 Rules

- **R1** — a `template` / `seamed` file matches the pristine render outside its
  declared seams. *(#257, #258, #217, #259)*
- **R2** — template-owned code must not assert on downstream-owned **values**.
  It **may** assert relationships *between* downstream-owned regions. *(#254)*
- **R3** — every seam in the manifest appears in the render exactly once, with
  `START` before `END`, properly nested.
- **R4** — every rendered path appears in the manifest exactly once. New files
  cannot escape classification.
- **R5** — the render is whitespace-clean (existing `check_render_hygiene.py`,
  folded in as one rule among six).
- **R6** — `copier.yml`'s `_skip_if_exists` equals the manifest's `seeded` set,
  and its `_exclude` equals the `excluded` set. The two encodings can never
  silently disagree.

R2's precise wording is load-bearing. The naive form — *"no template-owned code
may read a `_skip_if_exists` file"* — would wrongly condemn the wizard coverage
check, whose legitimate job is comparing two downstream-owned regions. The
actual defect in #254 is that the check reads **template-owned** data out of a
**frozen** file.

### 4.3 Manifest

`ownership.yml` at template root, `_exclude`d from renders:

```yaml
files:
  pyproject.toml:
    class: seamed
    seams: [PROJECT-DEPS, PROJECT-EXTRAS, PROJECT-RUFF-IGNORES,
            PROJECT-META, PROJECT-TOOLING]
  .pre-commit-config.yaml:
    class: seamed          # was seeded — #254
    seams: [DOMAIN-HOOKS]
  docs/javascripts/config-wizard/wizard-spec.json:
    class: generated       # was seeded — the §1.3 regression
```

It stays **separate from** `copier.yml`: copier rejects unknown top-level keys,
and `copier.yml` should keep meaning only what copier means. R6 is the
template-CI check that keeps the two in agreement. `copier.yml` stays canonical
for copier; `ownership.yml` becomes canonical for the guards.

**Note on #257.** That issue proposes skip-listing `examples/*.env` and
`server.json`. This design supersedes that: `examples/*.env` become `generated`
(§6.5) and `server.json`'s env block is spliced, so neither needs
`_skip_if_exists`. Do not apply the issue's own suggested fix.

## 5. Layer A: the conformance digest

### 5.1 The chicken-and-egg

A masked hash of the *pristine* render cannot come from the working tree during
`copier update` — by then the tree already contains the drift, so hashing it
would enshrine the drift as canonical. It also cannot be precomputed in the
template repo, because rendered bytes embed the answers.

### 5.2 Bootstrap side-render

```
copier copy/update finishes
  └─ _tasks: scripts/write_ownership_digest.py
       ├─ read .copier-answers.yml → _src_path, _commit, answers
       ├─ render that ref + those answers → tmpdir, with --skip-tasks   ← breaks recursion
       ├─ per template/seamed path: mask seam interiors → sha256
       └─ write .template-ownership.json      (class: generated)

at commit time — fully offline, milliseconds:
  tests/test_template_ownership.py + a pre-commit hook
       mask working file → sha256 → compare → "move this into <PROJECT-META>"
```

The expensive render happens once per update, which already pays that cost. The
per-commit check is pure hashing. Because the side-render uses **this project's
own answers**, conditional files (`{% if enable_structural_gate %}`) and
answer-dependent content are handled automatically — no flag matrix, no
answer-normalisation.

### 5.3 What "masking" means, precisely

For each seam declared for the file, every byte **between** the `START` and
`END` marker lines is replaced by a single fixed placeholder line. The marker
lines themselves are retained and hashed. This yields the required two
behaviours: editing a seam's interior leaves the hash unchanged (F5), while
deleting or moving a marker changes it (F4). Both the digest writer and the
downstream checker use the same masking function, so it lives in one module
shared by both.

## 6. Layer B: the generation layer

### 6.0 Where generation runs

**Generation runs downstream, in the consumer project.** `fastmcp-pvl-core`
supplies deterministic input (field metadata); the template supplies
deterministic methodology (the generator and the presentation config); the
downstream supplies domain content and executes.

Three consequences:

- The template ships the **generator**, not pre-generated artifacts. So
  `wizard-spec.json.jinja`, `.env.example.jinja`, `packaging/env.example.jinja`
  and `examples/*.env.jinja` are **deleted** from the template — real removals,
  not fallbacks left in place (per this repo's removal discipline, verify with
  the §12 commands that they are gone).
- Generated files are produced at copy time by a `_tasks` hook and re-verified
  at pre-commit and CI by regenerate-and-`git diff --exit-code`.
- The digest side-render (§5.2) runs with `--skip-tasks`, so it does not run the
  generator and generated files are absent from it. This is consistent: class
  `generated` is excluded from the digest, which is F10's pattern generalised.

Because there is exactly one generator implementation and it runs in one place,
output ordering is an **internal property of that generator**, not a cross-repo
contract. It does not belong in Stage 0's metadata schema.

### 6.1 Four provenances

The generator merges four sources, not one:

| Provenance | Example | Metadata home |
|---|---|---|
| **core** | the 18 `ServerConfig` fields | `field(metadata=…)` in the library (Stage 0) |
| **template** | `HTTP_PATH`, read in `cli.py` | template-owned presentation config |
| **upstream-external** | `FASTMCP_LOG_LEVEL`, `FASTMCP_ENABLE_RICH_LOGGING` | template-owned presentation config |
| **domain** | downstream `CONFIG-FIELDS` additions | `field(metadata=…)` in the project's `config.py` |

### 6.2 Segmentation: tag sets

A config var can honestly belong in several places — `BASE_URL` is genuinely
server-relevant, OIDC-relevant, and Apps-relevant, and different docs pages
cover it from different angles. So vars carry a **tag set**, not one category,
and destinations select by tag intersection. Multiplicity is **intended**; the
design makes it visible and deterministic rather than preventing it.

Four orthogonal axes, layered so that no layer knows more than it should:

```
tags         {"auth","oidc"} / {"server","http"} / {"persistence"} / {"apps"}
             ↑ declared in metadata — SEMANTIC and layout-agnostic. The library
               must not know the template's file layout; downstream layouts differ.

destination  tag-intersection selector → which file + which section
             ↑ template-owned presentation config; downstream EXTENDS it

prominence   primary | advanced          (today: presence/absence of advancedGroup)

visibility   showIf conditionals         (template-owned presentation config)
```

Example:

```yaml
# config-presentation.yml  (template-owned)
destinations:
  docs/configuration.md#env:            {tags: []}            # empty = all vars
  docs/guides/authentication.md#env:    {tags: [auth]}
  docs/deployment/oidc.md#env:          {tags: [oidc]}
  docs/deployment/docker.md#env:        {tags: [server]}
  examples/oidc.env:                    {tags: [oidc]}
  examples/bearer-auth.env:             {tags: [bearer]}
```

`base_url` tagged `{"server","oidc","apps"}` therefore appears in
`configuration.md`, `oidc.md`, and `docker.md` — deliberately.

### 6.3 Determinism and visibility

Tags make two things mandatory that a single category would not:

- **Deterministic ordering — but only inside the generator (§6.0).** Any stable
  order works, provided it is a pure function of the generator's inputs.
  There is one concrete hazard, verified: `server_config_env_suffixes()` returns
  a **`frozenset`**, and CPython randomises string hashing by default
  (`PYTHONHASHSEED`), so frozenset iteration order varies *between processes*.
  Letting it drive output order would make regeneration produce different bytes
  on every run. **Rule: never iterate a frozenset to produce output.** Drive
  ordering from `dataclasses.fields()` — a tuple in declaration order — or sort
  explicitly. G4's test asserts two runs under different `PYTHONHASHSEED`
  values produce identical bytes.
- **Generated inventory.** `docs/config-inventory.md` (class `generated`) lists
  every var with its tags and every destination it landed in, so triple-listing
  is reviewable rather than silent.

### 6.4 Generator invariants

The deleted drift test's two checks were meant to survive as generator
invariants over tags, same two directions, unfalsifiable by construction.
**Correction, recorded during Stage 1 implementation:** only the coverage
direction actually does. Every var the generator collects is, by
construction, emitted into at least one destination — there is no code path
that produces a `Var` and then fails to place it — so coverage cannot regress
silently.

The **orphan** direction — a var declared in `config-presentation.yml` or
`config-presentation.domain.yml` that no read site actually consumes — is
**not** guarded by generation. Generation only transforms whatever the
presentation config declares; it has no way to know whether a declared var
corresponds to a real `env()`/`os.environ` read anywhere in the project, core
or domain. The deleted `tests/test_config_wizard_drift.py`'s
`test_no_orphan_wizard_vars` covered exactly this and has no replacement in
Stage 1. A stale or hand-added entry in either presentation file that nothing
reads will happily generate into `.env.example` and the wizard spec forever,
undetected. Building an orphan checker is out of scope for Stage 1; if this
gap is worth closing, it needs its own design and issue, not a checker
retrofitted here.

- **Coverage** — every var matches ≥1 destination. A var documented nowhere is
  an error. This applies to `inferred` fields too: no wizard control does not
  mean no documentation (see Stage 0's note on `auth_mode`).
- ~~**Orphan** — every tag used in a selector matches ≥1 var.~~ Not
  implemented in Stage 1; see the correction above.

Coverage fails at **generation time** (a `Var` is always placed) rather than
at template CI as originally envisioned; there is no separate orphan check to
run anywhere.

### 6.5 Outputs

`scripts/gen_config_surface.py` emits, from the merged surface:

- `docs/javascripts/config-wizard/wizard-spec.json` (whole file)
- `.env.example`, `packaging/env.example`, `examples/*.env` (whole files)
- `server.json` — **env block only**, spliced; the `version` line is
  PSR-owned via `bump_manifests.py` and must not be touched
- spliced env tables in `docs/configuration.md`, `docs/guides/authentication.md`,
  `docs/deployment/oidc.md`
- spliced env tables in `README.md` — **both** of them (§6.6)
- `docs/config-inventory.md`

### 6.6 The real boundary is tables vs prose, not docs vs README

README is not a harder case than the docs pages. It is already segmented exactly
the way generation needs, and its two tables have different characters:

- **The core table** (`README.md.jinja` lines 106–110) is **3 curated rows** —
  `FASTMCP_LOG_LEVEL`, `FASTMCP_ENABLE_RICH_LOGGING`,
  `{{ env_prefix }}_KV_STORE_URL` — deliberately 3 of ~20. The *selection* is
  editorial, and a tag expresses it natively: tag those three `readme`, give the
  destination the selector `{tags: [readme]}`. Nothing about a landing page
  requires a full table, and generating one would be a regression.
- **The domain table** (lines 204–209) is a **placeholder with two fake rows**
  (`EXAMPLE_VAR`, `ANOTHER_VAR`) plus the comment *"Replace with a table of
  domain-specific env vars."* This is the highest-value generation target in the
  batch: the template explicitly instructs every downstream to hand-maintain a
  duplicate. That instruction **is** the §8 migration, and generation deletes
  both the placeholder and the instruction.

What is genuinely not generable — in README and in the docs pages alike — is
**prose that names env vars inline**: `README.md.jinja` line 121 naming
`_ACL_PATH` and `_AUTHZ_CLAIM` mid-sentence, line 69 naming `.env.example`,
`authentication.md` line 158 naming `BASE_URL` and `HTTP_PATH` in a caveat.
Those sentences stay authored and are covered by Layer A's digest guard.

So the boundary is **tables (generated) vs prose (authored + guarded)**, and it
cuts through the middle of individual files rather than between them. Both
layers apply to `README.md` and to most `docs/*.md`.

Removed outright (real removals, not shims, per the repo's removal discipline):
`tests/test_config_wizard_drift.py` and `_COVERED_BY_INFERENCE`, replaced by a
regenerate-and-`git diff --exit-code` check.

## 7. Staging

Sequential, one PR at a time off `main`. No stacked branches.

This document is a **program spec spanning four stages and two repositories**;
it is deliberately not sized for a single implementation plan. Each stage gets
its own plan, written when the preceding stage has merged, so that the plan is
drafted against the code as it actually is.

### Stage 0 — `fastmcp-pvl-core` v4.5.0 · gates everything

Branch from fresh `origin/main` (`4cf1755`), **not** the stale local branch.

- Convert `ServerConfig`'s 18 fields to `field(default=…, metadata={…})`
  carrying `help`, `tags`, and wizard hints.
- Migrate the existing `event_store_url` / `bearer_default_subject` code
  comments into their `help` values.
- `auth_mode` gets `metadata={"wizard": "inferred"}` — this closes #217 at the
  source rather than adding a downstream seam.

  **`inferred` means "no wizard control", not "not operator-settable".**
  Corrected during Stage 0 implementation: `AUTH_MODE` **is** readable from the
  environment (`_config.py` reads `env(env_prefix, "AUTH_MODE")`) and acts as an
  explicit override accepting `remote` or `oidc-proxy`, short-circuiting
  auto-detection. It exists because having all four OIDC variables set is
  ambiguous between those two modes. The template's retired
  `_COVERED_BY_INFERENCE` comment described it as derived; that was wrong, and
  this design inherited the error.

  Consequence the Stage 1 generator **must** honour: an `inferred` field still
  requires a destination in env references and `.env.example`. Treating
  `inferred` as "omit from documentation" would silently drop a supported
  operator variable from every downstream — the opposite of this design's
  purpose.
- Add `server_config_surface()` returning suffix / name / type / default / help /
  tags / hints per field, complementing (not replacing)
  `server_config_env_suffixes()`.
- Release v4.5.0. **Release dispatch is manual and human-only — do not run it.**

Example:

```python
oidc_jwt_signing_key: str | None = field(default=None, metadata={
    "help": "Required on Linux/Docker — the default is ephemeral and "
            "invalidates tokens on restart. Generate: openssl rand -hex 32.",
    "tags": ("auth", "oidc"),
    "wizard": {"group": "Auth", "secret": True, "when": "oidc"}})

auth_mode: str | None = field(default=None, metadata={"wizard": "inferred"})
```

### Stage 1 — template: generation layer

Closes #217, the wizard half of #254, the env halves of #257/#258, and the §1.3
regression.

New: `scripts/gen_config_surface.py`, `config-presentation.yml`
(template-owned), `config-presentation.domain.yml` (**seeded**).
Also in this stage: `.pre-commit-config.yaml` moves seeded→seamed with a
`DOMAIN-HOOKS` seam, closing #254's structural-gate half.
Requires core ≥4.5.0, so it can be written before Stage 0 releases but cannot
merge until it does.

### Stage 2 — template: ownership manifest + digest guard

Closes #259 and the prose halves of #257/#258. Materially smaller than it would
have been, because Stage 1 turned ~9 config files into `generated`.

Not generable, and needing **new copier answers** rather than seams:
`license`, `author_name`, `author_email` (for `pyproject [project]` and
`nfpm.yaml`). These need defaults so `--skip-answered` does not re-prompt
existing consumers.

### Stage 3 — downstream convergence

Four consumers, strict guard (no warn phase, no grandfathering baseline). One
issue + PR each. `markdown-vault-mcp`'s ~14 diverged files are mostly domain
prose sitting adjacent to the empty `DOMAIN-*-EXTRA` block meant to hold it.

## 8. Downstream migration: "move from README into code"

Stage 3 is not "move prose into seams" — it is "move prose into field
metadata". Per domain env var:

1. Confirm a field exists in `ProjectConfig`'s `CONFIG-FIELDS` block. Many
   downstreams read env directly in `from_env` with no declared field; add one.
2. Move the README/docs sentence describing the var into
   `metadata={"help": "…"}`.
3. Assign `metadata={"tags": (…)}` — this picks its destinations.
4. Delete the hand-written table row / paragraph.
5. Regenerate; confirm the row reappears.
6. The regeneration check and digest guard confirm no drift.

This ships as `docs/guides/config-migration.md` in the template, not merely as
PR descriptions — four consumers do it now and every future project does it
once.

**Step 2 requires judgment** (which sentence in a paragraph *is* the help text
versus surrounding narrative). Per this repo's literal-execution-subagent
discipline, it must not be delegated to a Haiku-class executor. The mechanical
parts — grep commands and verification steps — are fully resolved in the guide;
the extraction itself needs a capable reader.

## 9. Failure modes → tests

Enumerated before implementation. Each becomes a test that fails first.

**Layer A — digest:**

| # | Mode | Handling |
|---|---|---|
| F1 | side-render re-triggers `_tasks` → infinite recursion | `--skip-tasks`; test asserts bounded completion |
| F2 | `_src_path` unreachable | fail loudly — never ship a silently stale digest |
| F3 | digest from an older template version validates a newer tree | digest records `_commit`; check fails on mismatch |
| F4 | downstream deletes a seam marker | masking finds no seam → hash differs → caught |
| F5 | downstream edits a seam **interior** | hash unchanged → passes (required behaviour) |
| F6 | new template file with no manifest entry | R4 fails at template CI |
| F7 | `copier.yml` skip/exclude lists drift from the manifest | cross-check fails |
| F8 | digest file missing | check fails with "run `scripts/write_ownership_digest.py`" |
| F9 | `copier-update.yml.jinja` passes `-T`, starving the digest | **audit the workflow's flags during implementation** |
| F10 | `vendor_spa.py` skipped in side-render → no `app.html` | `app.html` is `generated`, excluded from the digest — consistent |

**Layer B — generation:**

| # | Mode | Handling |
|---|---|---|
| G1 | core adds a var with no presentation entry | coverage invariant fails at **template** CI |
| G2 | selector tag matches no var (typo, or core dropped a var) | orphan invariant fails at template CI |
| G3 | downstream hand-edits a generated file | regeneration check fails; class `generated` documented as never-edit |
| G4 | generated output not byte-stable across runs | never iterate a `frozenset` (§6.3); test asserts identical bytes under two different `PYTHONHASHSEED` values |
| G5 | `server.json` version line is PSR-owned, adjacent to a generated block | splice env region only; PSR region untouched |
| G6 | template pinned to core <4.5.0 | generator fails with an explicit minimum-version message |
| G7 | a var has no introspectable field (`HTTP_PATH`, `FASTMCP_*`) | presentation config can declare non-introspectable vars with their own help/tags |

## 10. Issues to file before any PR

Per the one-PR-one-issue rule, two items in this batch have no issue yet:

1. **The wizard staleness regression** (§1.3) — structurally distinct from #254:
   consumers *ship* a wizard missing every question added since their first
   render. A defect in generated user-facing output, not a test problem.
   File in `fastmcp-server-template`.
2. **The core metadata API** — `field(metadata=…)` on `ServerConfig` plus
   `server_config_surface()`. File in `fastmcp-pvl-core`.

## 10a. Content defects found while implementing Stage 0

Stage 0's review pass verified each drafted help string against the code rather
than against the existing wizard spec. Two claims the fleet has been repeating
turned out to be false, which is worth recording because generation will
propagate whatever the metadata says:

1. **The "ephemeral JWT signing key" claim is false.** `wizard-spec.json.jinja`
   states that leaving `OIDC_JWT_SIGNING_KEY` unset means "the default is
   ephemeral and invalidates tokens on restart". Verified against fastmcp 3.3.1:
   `OAuthProxy.__init__` derives the key via
   `derive_jwt_key(high_entropy_material=upstream_client_secret, salt="fastmcp-jwt-signing-key")`
   — HKDF-SHA256 with a **fixed** salt, confirmed deterministic by running it.
   Tokens survive restart. The real caveat is that rotating the client secret
   invalidates every issued token. Core's own runtime warning carried the same
   falsehood and is corrected in Stage 0; the template's copy needs its own
   issue, and since `wizard-spec.json` becomes `generated` in Stage 1, the fix
   lands there.
2. **`AUTH_MODE` was described as derived.** See the Stage 0 note above.

The lesson for Stages 1–3: when migrating prose into metadata, verify each claim
against the implementation. Copying an existing doc string forward preserves its
errors, and generation then multiplies them across every downstream.

## 11. Out of scope

- Prose content of any docs page. Generation covers env **tables**; the
  surrounding narrative stays authored.
- `CLAUDE.md` guidance text — authored, covered by Layer A only.
- Whether the structural gate or wizard coverage checks are *desirable*
  (explicit scope boundary of #254).
- Fixing the specific downstream forks; that is Stage 3 per-repo work.
- Migrating `copier-update.yml` from PAT to GitHub App token (#28) and the
  file-exchange scaffold (#150) — unrelated open issues.

## 12. Verification

Each stage's plan carries its own commands. Program-level:

```bash
# Layer A: render, then assert hygiene + conformance on a pristine tree
rm -rf /tmp/smoke && uv run --no-project --with copier copier copy --trust \
  --defaults --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
python3 scripts/check_render_hygiene.py /tmp/smoke
python3 scripts/check_ownership_manifest.py        # R3, R4, R6

# Layer B: regeneration must be a no-op on a fresh render
cd /tmp/smoke && python3 scripts/gen_config_surface.py && git diff --exit-code

# R2: no template-owned code may assert on a seeded file's values
python3 scripts/check_ownership_manifest.py --rule=R2

# Confirm the removals actually happened (removal discipline)
! grep -rn '_COVERED_BY_INFERENCE' --include='*.jinja' .
! test -f tests/test_config_wizard_drift.py.jinja
! test -f docs/javascripts/config-wizard/wizard-spec.json.jinja
! test -f .env.example.jinja
! test -f packaging/env.example.jinja
! ls examples/*.env.jinja 2>/dev/null
! grep -n 'EXAMPLE_VAR\|ANOTHER_VAR' README.md.jinja   # domain placeholder gone

# G4: byte-stability under hash randomisation
cd /tmp/smoke
PYTHONHASHSEED=1 python3 scripts/gen_config_surface.py && git stash -u -q
PYTHONHASHSEED=2 python3 scripts/gen_config_surface.py && git stash pop -q
git diff --exit-code
```
