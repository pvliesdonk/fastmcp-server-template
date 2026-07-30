# PR E: generated README CORE + DOMAIN tables, and the MISSING required-ness fix

**Goal:** the README's core and domain env-var tables generate from a single source; a domain field's required-ness comes from whether it actually has a default (`field.default is MISSING`), fixing the bug that published `x: str | None = None` as Required: Yes; and `config-migration.md`'s AST-scan wording stops steering readers into the duplicate-name `SystemExit`.

**Closes:** #268 (AST-scan wording) — the anchor issue (#260, the domain arc's umbrella, was closed by PR D). The README-generation + MISSING-fix work is the spec's E row; if a reviewer wants the user-facing MISSING bug (optional fields shown Required: Yes) tracked in its own right, file that issue and add it to the close list before opening the PR.

**Spec:** `docs/superpowers/specs/2026-07-27-config-surface-1b-restructured-design.md` — PR E row, §4.3, §4.4, §5, §6. PR E of the strictly-sequential Stage 1b series; A #269, B #271, C #273, D #274 merged. Release gated on the whole series.

**Salvage source:** the README CORE/DOMAIN layout and `TestReadmeRegions` come from the abandoned spike `feat/config-surface-splicing`. The markdown-splice engine itself (`render_md_table`, `_md_required_cell`, `splice_region`, `render_splice_file`) already landed on `main` in PR D — E reuses it, it is not re-ported.

## Brainstormed decision (2026-07-30, user-approved)

**BD1 — full E now, documented migration (spec §6).** The domain env-var table converts from downstream-owned (hand-written inside `DOMAIN-START/END`) to fully generated from `ProjectConfig` field metadata. This is fleet-breaking: every downstream with a hand-written domain table hits a `copier update` conflict and migrates its rows into `field(metadata={"help": ...})`. CORE generation is not breaking — the `readme`-tagged set is exactly today's three Configuration rows (`FASTMCP_LOG_LEVEL`, `FASTMCP_ENABLE_RICH_LOGGING`, `{PREFIX}_KV_STORE_URL`), so the CORE table's rendered content is unchanged.

## The load-bearing change: the MISSING required-ness fix (§4.3)

This is the redecided-content half — the spike got it wrong and shipped the bug (§1.1). Today `_discover_domain_vars` sets `default = None` for a field with neither a `default` nor a `default_factory` (current `scripts/gen_config_surface.py`, the `field_info.default is MISSING` / `default_factory is MISSING` ladder), so a genuinely-defaultless required field and an `x: str | None = None` optional field are **indistinguishable** on the resulting `Var` — both carry `default=None`. `_is_required`'s domain rule then treats a null default as required, publishing every optional `… | None = None` as **Required: Yes**.

The fix, with the rule from §4.3:

| Field | Signal | Required |
|---|---|---|
| `vault_path: str = field(default="/data")` | has a default | No |
| `api_key: str \| None = None` | has a default (`None`) | **No** |
| `api_key: str = field(metadata={...})` | no default, no factory | **Yes** |

`_discover_domain_vars` must carry a distinct "no default declared" marker (a module sentinel or `dataclasses.MISSING`) rather than `None`, and `_is_required`'s domain branch must key required-ness on *that* marker, not on `default is None`.

**Design-failure-modes-first — the sentinel is consumed by every default path.** Changing "no default → `None`" to "no default → sentinel" ripples through every reader of `Var.default`. Enumerate and verify each before writing:
- `_is_empty_default` / `_documented_default` / `_md_default_cell` (markdown table) — the sentinel must render `(none)` (or a documented default), never the literal sentinel repr.
- `_format_value` (env file, `render_env_file`) — the sentinel must fall back to the var's `example`, exactly as `None` did, so `.env.example` output is unchanged.
- `_format_default` — must not print the sentinel.
- the wizard spec path (`render_wizard_spec`) — a domain field with no default must not emit a broken `default` value.
- `_json_default` is PR F's and not wired yet — out of scope, but note the sentinel will reach it later.

A test asserts each of the three §4.3 rows renders the right Required cell, AND that a no-default field's env-file / wizard output is unchanged from the pre-fix `None` behaviour (the sentinel is invisible outside the required signal).

## Scope

- `scripts/gen_config_surface.py` — the MISSING fix (`_discover_domain_vars` + `_is_required` domain branch + the default-consumer paths); the #268 docstring wording.
- `scripts/tests/test_gen_config_surface.py` — the MISSING-fix tests, `TestReadmeRegions` (ported), and the §5 downstream-help tests.
- `config-presentation.yml` — declare README's `CORE` (`tags:[readme]`) and `DOMAIN` (`tags:[domain]`) splice regions; any domain `documented_defaults` (expected: none — domain vars use their own field defaults).
- `README.md.jinja` — replace the hand-written Configuration table with `GENERATED-ENV-TABLE-CORE` markers; replace the `DOMAIN-START/END` config-table sentinel with template prose + `GENERATED-ENV-TABLE-DOMAIN` markers (the spike's layout). The title/overview `DOMAIN` sentinels are unrelated and stay.
- `docs/guides/config-migration.md.jinja` — the #268 wording correction + the DOMAIN-table rollout hazard.
- `.github/workflows/template-ci.yml` — assert the generated tables + `--check`.

**Out of scope:** `json-splice`/`server.json` arrays (PR F, #257). The markdown-splice engine (already on `main` from D).

## Decisions

**E1 — MISSING sentinel, verified through every consumer (§4.3).** As above. The sentinel is an implementation detail; the observable contract is the §4.3 table plus "no-default env-file/wizard output unchanged." Re-verify `_is_required`'s domain branch reads the sentinel, not `None`.

**E2 — CORE is the same var set, content-set (not positional) equality.** The `readme` tag on `kv_store_url` (core) and the two observability vars (config-presentation) yields exactly the current three vars. Revised during execution: the generated table asserts the same *set* of rows with correct defaults, NOT the old hand-written row order or descriptions. Row order follows `collect_vars`' deterministic provenance ordering (core → template → external — a load-bearing determinism contract the double-render diff check depends on; special-casing CORE order would fight it), so `KV_STORE_URL` sorts first. Descriptions come from core/presentation help, so they are fuller than the old hand-written ones. `KV_STORE_URL` needs a `documented_defaults` entry (`file:///data/state`) because its field default is `None` (core resolves it internally) — otherwise the cell shows `(none)`. A test pins the CORE content set + defaults so a future `collect_vars` change is caught. Consequence for downstreams: a one-time CORE reorder + richer descriptions on adopting E — diff noise, not a merge conflict (the whole table is template-owned/generated). Not the "positional equality" the first draft claimed.

**E3 — DOMAIN is fully generated from ProjectConfig metadata (BD1).** `## Domain configuration` loses its `DOMAIN-START/END` config-table sentinel; the env-var table becomes `GENERATED-ENV-TABLE-DOMAIN`, rendered from discovered `ProjectConfig` fields' `metadata` `help`/`tags`. A fresh scaffold has no domain fields, so it renders as a header-only empty table. Keep the surrounding template prose that tells a downstream author to add fields with `metadata` (the spike's trailing sentence: "Each field's metadata help and tags generate the table above directly").

**E4 — downstream-authored help is hostile input (§5).** The DOMAIN description column renders text a downstream wrote. `_clean_help_for_markdown_table` (on `main` from D) must neutralise a literal `|` (would break the table row), collapse multi-line help to one cell, and survive markup. Exercise all three with a fixture `ProjectConfig`, plus a field rendering Required each way.

**E5 — #268: state what the scan does.** The AST scan (`fastmcp_pvl_core.domain_env_suffixes`) returns **every** literal `env(prefix, "SUFFIX")` suffix read in `ProjectConfig.from_env`, field-matching or not — not only suffixes matching a dataclass field. Correct `config-migration.md.jinja`'s claim and the `_discover_domain_vars` docstring wherever they imply otherwise, and drop the guidance that steers a reader to declare a scan-visible alias (which raises the duplicate-name `SystemExit` the same section warns about). Grep the phrasing across the repo; fix every affected instance in the same commit.

**E6 — the DOMAIN flip is the §6 rollout hazard.** A downstream that hand-wrote its domain table 3-way-merges on the first `copier update`, and resolving it by keeping the hand-written table without the `GENERATED-ENV-TABLE-DOMAIN` markers gives a hard `--check` SystemExit (naming the file, per D). The migration guide names the marker pair, states that domain vars are now documented by adding `ProjectConfig` fields with `metadata`, and gives the recovery. Higher blast radius than D's OIDC tables — this one hits every downstream with domain fields.

## Tasks

Park `.vscode/` in `.git/info/exclude`; commit before rendering (`--vcs-ref=HEAD`); `--check` + Vale after content changes.

### Task 1 — the MISSING required-ness fix (behavioral, no README yet)

**Files:** `scripts/gen_config_surface.py` (`_discover_domain_vars`, `_is_required` domain branch, default-consumer paths); `scripts/tests/test_gen_config_surface.py`.

- [ ] Enumerate every reader of `Var.default` (E1 list). Introduce the no-default sentinel in `_discover_domain_vars` and make `_is_required`'s domain branch key on it.
- [ ] Make each default-consumer treat the sentinel exactly as it treated `None` for env-file/wizard output, and as `(none)`/documented-default for the markdown cell.
- [ ] Tests: the three §4.3 rows render the right Required cell; a no-default field's env-file line and wizard entry are unchanged from the pre-fix output; `x: str | None = None` renders Required **No**.
- [ ] Full suite green; `gen_config_surface.py --check` on a fresh render still exits 0 (no README region declared yet, so no output change); ruff/format to the aggregator config.
- [ ] Commit. `fix(config): domain required-ness from field default, not null (§4.3)`.

### Task 2 — README CORE + DOMAIN regions

**Files:** `README.md.jinja`; `config-presentation.yml`; `scripts/tests/test_gen_config_surface.py` (port `TestReadmeRegions` + the §5 downstream-help tests).

- [ ] `## Configuration`: replace the hand-written table with the `GENERATED-ENV-TABLE-CORE-START/END` pair (keep the intro line). `## Domain configuration`: replace the `DOMAIN-START/END` config-table sentinel with the spike's layout — intro prose, `GENERATED-ENV-TABLE-DOMAIN-START/END`, trailing "add fields with metadata" prose. Do not touch the title/overview `DOMAIN` sentinels.
- [ ] `config-presentation.yml`: declare README as `kind: splice` with regions `CORE` (`tags:[readme]`, cols `variable, default, description`) and `DOMAIN` (`tags:[domain]`, cols `variable, default, required, description`).
- [ ] Port `TestReadmeRegions` and add the §5 tests (a fixture `ProjectConfig` with a pipe in help, multi-line help, markup; a required field and an optional field).
- [ ] Generate + verify in `/tmp/smoke`: CORE table content equals today's three Configuration rows (E2); DOMAIN renders header-only empty on the fresh scaffold; a fixture domain field renders Required correctly both ways; every var `{{ env_prefix }}_`-prefixed; `--check` idempotent; a dropped marker SystemExits naming the file. Vale + render hygiene clean.
- [ ] Commit. `feat(config): generate the README core and domain env-var tables`.

### Task 3 — #268 AST-scan wording sweep

**Files:** `docs/guides/config-migration.md.jinja`; `scripts/gen_config_surface.py` (`_discover_domain_vars` docstring); any other file `grep` shows carrying the phrasing.

- [ ] `grep -rlnE 'suffix.*match.*field|no matching field|whose suffix matches' scripts/ docs/` (excluding `docs/superpowers`); fix every hit in this commit (fix the class). State the corrected fact: the scan returns every literal suffix read in `from_env`, field or no field; drop the "declare a scan-visible alias" guidance that triggers the duplicate-name `SystemExit`.
- [ ] Re-render; Vale clean over the render; the config-migration recovery for the duplicate-name `SystemExit` is still accurate.
- [ ] Commit. `docs(migration): correct the AST-scan wording (closes #268)`.

### Task 4 — template-ci assertions

**Files:** `.github/workflows/template-ci.yml`.

- [ ] Assert (matching the file's conventions, `set -euo pipefail`, `::error::`, `|| true` on zero-match greps): the README carries the `GENERATED-ENV-TABLE-CORE`/`-DOMAIN` markers; the CORE table has the three expected rows; the DOMAIN table renders (header present); `gen_config_surface.py --check` idempotence. Reuse the OIDC-table step's shape from D; do not duplicate the `--check` if one already covers splice output.
- [ ] Verify the step bites (sabotage a CORE row; break a marker); YAML valid.
- [ ] Commit. `ci(template): assert the generated README tables`.

### Task 5 — migration note (§6, E6)

**Files:** `docs/guides/config-migration.md.jinja`.

- [ ] Document the fleet-breaking DOMAIN-table flip: the domain env-var table is now generated from `ProjectConfig` field metadata; a hand-written table 3-way-merges on the first update; the resolution is to move rows into `field(metadata={"help": ...})` and keep the `GENERATED-ENV-TABLE-DOMAIN` marker pair; a dropped marker fails `--check` with a file-naming SystemExit. Quote the actual message. No forward references to other PRs (the reviewable-unit rule — a lesson from D's circus).
- [ ] Vale + hygiene clean.
- [ ] Commit. `docs(migration): record the README domain-table generation flip`.

## Verification contract (spec §5)

| Check | How | Expected |
|---|---|---|
| MISSING fix | the three §4.3 rows | Required No / No / Yes |
| No-default invisible elsewhere | env-file + wizard output for a no-default field | byte-identical to pre-fix |
| CORE non-breaking | diff generated CORE vs today's Configuration rows | identical content |
| DOMAIN from metadata | fixture ProjectConfig field | renders with help + correct Required |
| Hostile help | pipe / multi-line / markup in field help | table row intact, no broken cell |
| #268 | grep the phrasing repo-wide | corrected everywhere; recovery accurate |
| Idempotent + guard | `--check` twice; dropped marker | exit 0; SystemExit names the file |
| Vale + hygiene | B's gate + `check_render_hygiene.py` | 0 errors; clean |

## Traps (from B/C/D)

- Park `.vscode/`; render from the git index; `vale sync` after every fresh render.
- Bare env-var names: every generated row renders through `{{ env_prefix }}_` (the class C's circus caught).
- The MISSING sentinel must not leak into any rendered artifact — grep the render for its repr.
- Strip plan/spec/PR tokens from shipped comments and docstrings before invoking the circus — the class that hit D's cap. Do lens 1 on your own writing first.

## Out of scope

- `json-splice`/`server.json` (PR F, #257).
- G/H (independent; issues unfiled).
