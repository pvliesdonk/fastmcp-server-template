# PR D: markdown splice engine + the generated OIDC doc tables

**Goal:** the OIDC env-var tables in `docs/deployment/oidc.md` and `docs/guides/authentication.md` are generated from one source, removing the `ephemeral` falsehood the tables still carry (the surface PR C deferred), on top of the markdown-splice engine salvaged from the abandoned spike.

**Closes:** #260 (its last surface — the two table rows). Use `Closes #260` only after confirming no other #260 surface survives at merge (C left exactly the table rows; the wizard-spec and core-runtime surfaces are already correct). Verify the squash keyword against `git grep -niE 'ephemeral|invalidates.*restart'` before merge — a stale `Closes` auto-closed three issues in Stage 1a.

**Spec:** `docs/superpowers/specs/2026-07-27-config-surface-1b-restructured-design.md` — PR D row, §4.3, §4.4, §4.5, §5, §6. PR D of the strictly-sequential Stage 1b series; A #269, B #271, C #273 merged. Release is gated on the whole series.

**Salvage source:** the markdown-splice engine and its tests were verified by execution across three review rounds on the abandoned spike `feat/config-surface-splicing` (tip `283811e`). §4.5 carries the *mechanism* forward; the *content* (which vars, `required_vars`, `documented_defaults`, every value) is redecided and re-verified here, because judgement produced the content and judgement was wrong in the spike.

This plan states decisions and the verification method. It does not transcribe the ported code line-by-line — the salvage source is a named git ref, and PR A's 420-line recipe produced ~20 review findings against one in the prose it described.

## Brainstormed decisions (2026-07-29, user-approved)

**BD1 — homogenize.** Both files' OIDC tables are generated from the same `tags:[oidc]` source, so `authentication.md`'s currently-terser tables become identical to `oidc.md`'s — it gains `OIDC_VERIFY_ACCESS_TOKEN` and the fuller descriptions. The hand-written terseness was under-maintained drift (it omitted a real var); single-source generation is the spec's thesis.

**BD2 — the signing-key Default cell shows `derived`.** `OIDC_JWT_SIGNING_KEY` has no literal default; `_md_default_cell` would otherwise render bare `(none)`. Add a `documented_defaults` entry so the Default column states the behaviour directly: `` `derived` ``. Diverges from the spike's `(none)`. Vale-safe (code span). The Description column still carries the full "derived from the client secret; set explicitly to keep tokens valid across a secret rotation" text from core help.

## Scope

- `scripts/gen_config_surface.py` — port the markdown-splice engine (below).
- `scripts/tests/test_gen_config_surface.py` — port the engine's unit tests.
- `config-presentation.yml` — OIDC `tags`, `required_vars`, `documented_defaults`, and the two `kind: splice` file declarations.
- `docs/deployment/oidc.md.jinja`, `docs/guides/authentication.md.jinja` — replace the four hand-written tables with `GENERATED-ENV-TABLE-*` marker pairs.
- `.github/workflows/template-ci.yml` — assert the spliced output.
- Release/migration note for the marker rollout hazard.

**Out of scope (do not port from the spike):** `render_json_splice_file` and the `_json_*` helpers + `TestServerJsonSplice` (PR F); the README `CORE`/`DOMAIN` regions + `TestReadmeRegions` + `documented_defaults`/`required`-ness for domain vars (PR E). D establishes the shared markdown-splice engine; E and F build on it.

## Salvage boundary — the exact functions D ports

From `feat/config-surface-splicing:scripts/gen_config_surface.py`, port and re-read each rather than trust it:

- `_is_required`, `_is_empty_default`, `_documented_default`
- `_md_variable_cell`, `_dedash_for_markdown_table`, `_clean_help_for_markdown_table`, `_md_description_cell`, `_md_default_cell`, `_md_required_cell`
- `render_md_table`, `splice_region`, `_select_region_vars`, `render_splice_file`

These have **no** dependency on the json-splice or README/domain helpers (confirmed: their bodies reference `DOMAIN-*`/json only in comments). `_discover_domain_vars` is already on `main` from Stage 1a — do not re-port it.

Tests to port (the markdown-splice subset only): `TestRenderMdTable`, `TestSpliceRegion`, `TestSelectRegionVars`, `TestSelectRegionVarsWithRequiredNames`, `TestRenderSpliceFileMultiRegion`, `TestCleanHelpForMarkdownTable`, the em-dash / `e.g.`-in-a-table-cell tests, the determinism test, and `test_jwts_does_not_reach_a_spliced_docs_table`. **Not** `TestReadmeRegions`, **not** `TestServerJsonSplice`.

## Decisions

**D1 — mechanism salvaged, content redecided (§4.5).** The engine is ported verbatim (it survived three adversarial rounds); every content value is re-verified. A ported test that asserts a content value must be checked against source, not accepted because it passed on the spike.

**D2 — every table value cites a source.** Descriptions come from core help via `server_config_surface()` (the same corrected help C verified). `required_vars`, `documented_defaults`, and the `oidc` tag set are template-owned choices in `config-presentation.yml`; each is verified against `fastmcp_pvl_core` source (which vars the oidc-proxy path reads) and the review record (§5), at the resolved lock (`fastmcp 3.4.5`, `pvl-core 4.5.0`), not the spike's stale citations.

**D3 — `required_vars` = the four OIDC connection vars.** `{PREFIX}_BASE_URL`, `{PREFIX}_OIDC_CONFIG_URL`, `{PREFIX}_OIDC_CLIENT_ID`, `{PREFIX}_OIDC_CLIENT_SECRET` → the `OIDC-REQUIRED` region. The rest (`SIGNING_KEY`, `AUDIENCE`, `REQUIRED_SCOPES`, `VERIFY_ACCESS_TOKEN`) → `OIDC-OPTIONAL`. Verify each: a var is "required" only if the oidc-proxy path cannot start without it. `OIDC_JWT_SIGNING_KEY` is NOT required (it derives), so it is optional — the exact distinction #260 turned on.

**D4 — `documented_defaults`.** `{PREFIX}_OIDC_REQUIRED_SCOPES` = `openid` (the field default `()` means "no restriction" in remote mode, but oidc-proxy gets `openid`; the description carries the condition). `{PREFIX}_OIDC_JWT_SIGNING_KEY` = `derived` (BD2). Verify both against source before writing.

**D5 — both files, identical regions (BD1).** Each of the two files declares `OIDC-REQUIRED` (cols `variable, description`) and `OIDC-OPTIONAL` (cols `variable, default, description`), both `tags:[oidc]`, filtered by `required`. The marker id is shared across files; `render_splice_file` operates per file, so the same id in two files is two independent regions.

**D6 — `kind: splice` never creates a file.** `render_splice_file` raises `SystemExit` naming the file if it does not exist or a marker is missing. The generator only rewrites the marked region inside authored prose. `write_artifacts` must dispatch `kind: splice` to it, alongside the existing `kind: env`/`kind: wizard`.

**D7 — markers are the copier-update conflict surface (§6).** Adding `GENERATED-ENV-TABLE-*` to a file every downstream already has means the first `copier update` 3-way-merges the generated table over the downstream's hand-written one. A downstream that customized its OIDC table and drops a marker gets a hard `--check` failure (SystemExit), not a silent skip. Lower blast radius than E's README domain table (OIDC tables are rarely customized), but it must reach the release note and the migration guide with the recovery for a missing-marker error mid-update.

## Tasks

Park `.vscode/` in `.git/info/exclude` before any render. Commit `.jinja`/generator edits before rendering (`--vcs-ref=HEAD`). Run `gen_config_surface.py --check` and B's Vale gate after content changes.

### Task 1 — port the markdown-splice engine (mechanism only, no wiring)

**Files:** Modify `scripts/gen_config_surface.py` (add the salvaged functions); `scripts/tests/test_gen_config_surface.py` (add the salvaged tests).

- [ ] Port the 13 functions listed under **Salvage boundary** from `feat/config-surface-splicing:scripts/gen_config_surface.py`. Read each ported function against the current file's conventions (imports, `Var` shape) — the spike diverged from `main`; reconcile.
- [ ] Port the listed test classes. Run them: `uv run --with pytest --with pyyaml --with jsonschema --with 'fastmcp-pvl-core>=4.5.0' pytest scripts/tests/test_gen_config_surface.py -q`. Expected: the ported md-splice tests pass; no existing test regresses.
- [ ] Confirm no `kind: splice` file is declared yet, so `write_artifacts` behaviour is unchanged — this task adds the engine, not its use. `gen_config_surface.py --check` still passes on a fresh render.
- [ ] Lint/format to the aggregator config: `uv run --with ruff ruff check --select E,W,F,I,B,C4,UP,ARG,SIM,TC,PTH,RUF --ignore E501 --line-length 88 scripts/gen_config_surface.py scripts/tests/` and `ruff format --check`.
- [ ] Commit. `feat(config): port the markdown-splice engine from the 1b spike`.

### Task 2 — OIDC content in config-presentation.yml (verified against source)

**Files:** Modify `config-presentation.yml`.

- [ ] Add the `oidc` tag to the OIDC vars, `required_vars` (D3), and `documented_defaults` (D4). For each value, record in the commit body the source symbol / review-record citation that backs it (`fastmcp_pvl_core._auth.build_oidc_proxy_auth` for which vars the proxy path reads; `_config.py` for defaults).
- [ ] Verify `OIDC_JWT_SIGNING_KEY` is tagged `oidc`, is NOT in `required_vars`, and has `documented_defaults` = `derived`. Verify `OIDC_VERIFY_ACCESS_TOKEN` is `oidc`-tagged (so homogenization adds it to `authentication.md` per BD1).
- [ ] `gen_config_surface.py --check` still passes (no splice files declared yet, so no output changes). Commit. `feat(config): tag OIDC vars, set required_vars + documented_defaults`.

### Task 3 — markers in both docs + wire the two splice files

**Files:** Modify `docs/deployment/oidc.md.jinja`, `docs/guides/authentication.md.jinja` (replace the four hand tables with `GENERATED-ENV-TABLE-OIDC-REQUIRED/-OPTIONAL` marker pairs); `config-presentation.yml` (declare both `kind: splice` files + regions per D5); `scripts/gen_config_surface.py` if `write_artifacts` needs the `kind: splice` dispatch (D6).

- [ ] Replace each hand-written table with its marker pair (keep the `## Required Variables` / `## Optional Variables` headings; the markers sit under them). Delete the hand rows — the generator fills the region.
- [ ] Declare the two files in `config-presentation.yml` as `kind: splice` with the `OIDC-REQUIRED`/`OIDC-OPTIONAL` regions (D5).
- [ ] Render and generate: `gen_config_surface.py` writes the tables. Verify in `/tmp/smoke`:
  - `ephemeral`/`invalidates.*restart`/`Required on Linux` gone from both rendered tables.
  - `OIDC_JWT_SIGNING_KEY` row: Default cell = `` `derived` ``, Description = the derivation text.
  - Both files' tables are byte-identical in var set (BD1); `authentication.md` now shows `OIDC_VERIFY_ACCESS_TOKEN`.
  - `required` split correct: the four connection vars in REQUIRED, the rest in OPTIONAL.
- [ ] `gen_config_surface.py --check` is idempotent (a second run reports no change). Break a marker in a scratch copy and confirm `--check` SystemExits naming the file (D6).
- [ ] B's Vale gate clean over the render; render hygiene clean on the marker'd files (the generated table must not introduce trailing whitespace / EOF drift — check `check_render_hygiene.py`).
- [ ] Commit. `feat(config): generate the OIDC env-var tables (closes #260)`.

### Task 4 — template-ci assertions

**Files:** Modify `.github/workflows/template-ci.yml`.

- [ ] Add assertions to the render-and-gate job: after generation, the two files' OIDC tables contain the generated markers and the correct rows; `gen_config_surface.py --check` passes on the pristine render (idempotence, mirroring the existing `--check` step); no `ephemeral` survives in the rendered `docs/`. Reuse the existing generated-artifact `--check` step if it already covers splice output.
- [ ] Confirm the render-hygiene step covers the marker'd files (they render in every variant).
- [ ] Commit. `ci(template): assert the generated OIDC tables and their idempotence`.

### Task 5 — rollout note (§6, D7)

**Files:** the release-note / migration surface the series uses (confirm where A/B/C recorded rollout hazards — likely the PR body + a migration section in `docs/guides/config-migration.md` if that is where SystemExit recoveries live per §5).

- [ ] Document: the OIDC tables become generated; a downstream that customized either table 3-way-merges on first `copier update`, and a dropped `GENERATED-ENV-TABLE-*` marker fails `--check` with a SystemExit naming the file. Give the recovery (restore the marker pair around the region). Note this is lower-risk than E's README table.
- [ ] Commit. `docs(migration): record the OIDC-table generation rollout hazard`.

## Verification contract (spec §5)

| Check | How | Expected |
|---|---|---|
| Engine ported cleanly | md-splice unit tests | pass; no existing test regresses |
| Content cited | commit bodies name a source per value | no uncited `required_vars`/`documented_defaults`/tag |
| `ephemeral` gone | grep rendered `docs/` | zero hits (the last #260 surface) |
| Signing-key cell | grep rendered table | Default `` `derived` ``, Description = derivation text |
| Homogenized | diff the two files' rendered OIDC tables | identical var set; `authentication.md` gained `VERIFY_ACCESS_TOKEN` |
| Idempotent | `gen_config_surface.py --check` twice | no change on second run |
| Marker guard bites | drop a marker, `--check` | SystemExit naming the file |
| Existing downstream | `config-presentation.yml` + generator overwrite on update; the marker'd doc files are the conflict surface | migration note covers the recovery |
| Vale + hygiene | B's gate + `check_render_hygiene.py` | 0 errors; hygiene clean |

## Traps (from A/B/C)

- Park `.vscode/` before any render; render from the git index.
- `vale sync` after every fresh render.
- The spike diverged from `main`; a ported function may reference a helper signature that changed — reconcile against the current `Var`/`collect_vars`, don't paste blind.
- Bare env-var names: every var in the generated table renders through `{{ env_prefix }}_`; confirm the render shows the prefixed form (the class the C circus caught).

## Out of scope

- json-splice / `server.json` arrays (PR F, #257).
- README `CORE`/`DOMAIN` tables + domain-var required-ness + the `MISSING` fix (PR E, #268/#260-domain).
- Making the gate strict. The Vale advisory stays as B left it.
