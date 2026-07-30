# PR F — Generate server.json env-var arrays (json-splice) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate `server.json`'s two `environmentVariables` arrays from the single config-surface source instead of hand-maintaining them, closing the last drift surface (`Closes #257`).

**Architecture:** Salvage the spike's `json-splice` engine into `scripts/gen_config_surface.py`. JSON has no comment syntax for `GENERATED-*` markers, so this splices *structurally*: the generator replaces each declared array path (`[packages, N, environmentVariables]`) wholesale and leaves every other key (`version`, OCI `identifier`) untouched. Membership per package comes from a `packaging:` map in `config-presentation.yml`. `server.json.jinja`'s committed arrays are regenerated so a fresh render is `--check`-clean, exactly as D/E pre-spliced the docs tables.

**Tech Stack:** Python 3.11+, `jsonschema` (already a dep, used by wizard-spec tests), copier/Jinja2, the existing config-surface generator.

## Global Constraints

- Dependency lock: `fastmcp 3.4.5`, `fastmcp-pvl-core 4.5.0`. Cite signatures against the installed package, never memory.
- **Reviewable-unit hygiene:** no spec/plan tokens (`§N`, PR-letter like `F2`, `Stage N`, "the plan"/"the spec", "Task N reviewer") in ANY file in the diff — **including test docstrings** (the class the circus caught on PR E). The plan doc under `docs/superpowers/` is the only legitimate carrier of its own section tokens.
- `isRequired` is **NEVER** emitted into `server.json` (a package manifest has no conditional scoping; the flag would assert something false). Pin it absent with a test, paired with a test that the markdown `Required` column still marks the same vars — the two destinations stay pinned apart.
- Byte-format parity with `scripts/bump_manifests.py.jinja`: `json.dumps(data, indent=2, ensure_ascii=False)` + a single trailing `"\n"`. `bump_manifests` rewrites only `version`/package `identifier` with identical formatting, so the two tools never collide — a byte round-trip test guards this.
- `--check` is read-only: it reports staleness, never writes.
- Determinism: no set iteration feeding ordered output.
- Every env-var name in rendered `.md.jinja`/docs prose carries `{{ env_prefix }}_`. `server.json.jinja` env-var `name` values carry `{{ env_prefix }}_` too (they render to concrete names the generator reproduces).
- Render from the git index with `--vcs-ref=HEAD` (copier ignores the working tree); commit before rendering.
- Salvage source: spike branch `feat/config-surface-splicing` (tip `283811e`). Read it with `git show feat/config-surface-splicing:<path>`. Everything below is spike-only — main has the markdown splice, not the json splice.

---

## File Structure

- `scripts/gen_config_surface.py` — gains the json-splice engine (13 symbols) + the presentation-key validators. Modify only; large file.
- `scripts/tests/test_gen_config_surface.py` — gains the salvaged json tests + a real schema-validation test + the key-validator tests.
- `config-presentation.yml` — gains a `packaging:` map, a `choices:` map, and the `server.json` `json-splice` file-spec.
- `server.json.jinja` — its two `environmentVariables` arrays are regenerated to match generator output (post-render, `--check`-clean).
- `schemas/server.schema.json` (new, vendored) — the `2025-12-11` MCP server schema the `$schema` URL already names, for `jsonschema.validate`.
- `.github/workflows/template-ci.yml` — a step asserting the generated server.json arrays + schema validity (idempotence rides the existing generator `--check`).
- `docs/guides/config-migration.md.jinja` — a migration note for the server.json array generation + its rollout hazard.

---

### Task 1: Salvage the json-splice engine

**Files:**
- Modify: `scripts/gen_config_surface.py`
- Test: `scripts/tests/test_gen_config_surface.py`

**Interfaces:**
- Produces (all salvaged verbatim-where-possible from `feat/config-surface-splicing:scripts/gen_config_surface.py`, adapted to main's current surrounding code):
  - `_ALL_PACKAGING_IDS = frozenset({"pypi", "oci"})`
  - `_JSON_INPUT_FORMATS: dict[str, str]` (type_name → schema `Input.format`: `bool→boolean`, `int/float→number`, `path→filepath`; plain `str` omits the key)
  - `_json_input_format(var) -> str | None`
  - `_packaging_ids(var, packaging) -> frozenset[str]` — 3-step resolution mirroring `_is_required`: explicit `packaging:` entry wins → `domain`-provenance var → all packagings → else empty
  - `_json_default(var, documented_defaults) -> str | None` — empty/`None`/empty-container default falls to `documented_defaults` then omits; non-empty → `_format_default(var.default)`; never emits `var.example`
  - `_render_json_env_entry(var, *, sub, choices, documented_defaults) -> dict` — one schema `Input`: `name`, `description` (raw `var.help`, **not** Vale-normalised), `format`, `default` **xor** `placeholder`, `choices` (from presentation map), `isSecret` (from `var.wizard.get("secret")`); **never** `isRequired`
  - `_json_array_container(data, path, rel_path)` and `_assert_packaging_matches_container(...)` — path walk + `registryType`↔`packaging` cross-check, both raising `SystemExit` naming the file
  - `render_json_splice_file(project_root, rel_path, file_spec, vars_, presentation, answers) -> str`
  - `_JSON_SPLICE_KIND = "json-splice"`, added to `_KNOWN_FILE_KINDS`, dispatched in `write_artifacts`

- [ ] **Step 1: Read the salvage source.** `git show feat/config-surface-splicing:scripts/gen_config_surface.py` — locate every symbol above (the explorer mapped them to spike lines 1413-2020). Read each in full.

- [ ] **Step 2: Port the pure helpers first.** Add `_ALL_PACKAGING_IDS`, `_JSON_INPUT_FORMATS`, `_json_input_format`, `_packaging_ids`, `_json_default` near the existing `_is_required`/`_documented_default`/`_format_default` (they share those). Reuse main's existing `_is_empty_default`, `_documented_default`, `_format_default` — do NOT re-port them.

- [ ] **Step 3: Port the entry + array builders.** Add `_render_json_env_entry`, `_json_array_container`, `_assert_packaging_matches_container`, `render_json_splice_file`. Add `_JSON_SPLICE_KIND`, extend `_KNOWN_FILE_KINDS`, and add the `elif kind == _JSON_SPLICE_KIND:` dispatch branch in `write_artifacts`.

- [ ] **Step 4: Port the pure-function unit tests.** From the spike test file, salvage `TestPackagingIds` (explicit-wins / domain-fallback-to-all / unlisted-non-domain-is-nowhere) and `TestServerJsonEntryShape` (default-always-string; example→placeholder-not-default; empty-default omission; documented-default fill; format-from-type + enum membership; choices-from-presentation; description NOT Vale-normalised, pinned against the markdown path; `{PROJECT_NAME}` placeholder substitution). Strip any spec/plan tokens from their docstrings.

- [ ] **Step 5: Run tests.** `uv run --with pytest --with pyyaml --with jsonschema --with 'fastmcp-pvl-core>=4.5.0' pytest scripts/tests/test_gen_config_surface.py -q` → all pass. Authoritative ruff: `uv run --with ruff ruff check --select E,W,F,I,B,C4,UP,ARG,SIM,TC,PTH,RUF --ignore E501 --line-length 88 scripts/gen_config_surface.py scripts/tests/` and `ruff format --check --line-length 88 …` → clean.

- [ ] **Step 6: Commit.** `feat(config): salvage the json-splice engine for server.json`

---

### Task 2: Presentation-key validation

**Files:**
- Modify: `scripts/gen_config_surface.py`
- Test: `scripts/tests/test_gen_config_surface.py`

**Interfaces:**
- Produces:
  - `_VAR_KEYED_MAPS` / `_VAR_KEYED_LISTS` — the presentation keys whose entries name a var (`packaging`, `choices`, `documented_defaults`, `examples`, `required_vars`)
  - `validate_presentation_keys(presentation, vars_) -> None` — raises `SystemExit` naming any entry that references a var not in `vars_` (typo guard; main has none today)
  - `_validate_packaging_map(packaging) -> None` — raises `SystemExit` naming any non-list or unknown-token `packaging:` value

- [ ] **Step 1: Read the salvage source.** Spike lines 1460-1551 for `_VAR_KEYED_MAPS`/`_VAR_KEYED_LISTS`/`validate_presentation_keys`/`_validate_packaging_map`, and its `TestPackagingMapValidation`.

- [ ] **Step 2: Port the validators.** Add both functions. Wire `validate_presentation_keys` into the generation entry path (where `presentation` and `vars_` are both available — near `write_artifacts`/`load_presentation`) so it runs before rendering. Wire `_validate_packaging_map` where the `packaging:` map is first read. Both must run under `--check` too (they are read-only assertions).

- [ ] **Step 3: Tests.** Salvage `TestPackagingMapValidation` (unknown token / non-list value raise, naming the offending var). Add tests for `validate_presentation_keys`: an entry in each of the five maps naming a nonexistent var raises `SystemExit` naming the map and the bad key; a clean presentation passes. Strip spec/plan tokens from docstrings.

- [ ] **Step 4: Run tests + ruff (as Task 1 Step 5).**

- [ ] **Step 5: Commit.** `feat(config): reject presentation-map entries naming unknown vars`

---

### Task 3: Wire server.json + regenerate the committed arrays

**Files:**
- Modify: `config-presentation.yml`, `server.json.jinja`
- Test: `scripts/tests/test_gen_config_surface.py`
- Modify: `.github/workflows/template-ci.yml`

**Interfaces:**
- Consumes: everything from Tasks 1-2.

- [ ] **Step 1: Read the salvage source.** Spike `config-presentation.yml` (the `packaging:` map ~lines 201-232, the `choices:` map, the `server.json` file-spec ~lines 455-467) and its `TestServerJsonSplice`.

- [ ] **Step 2: Declare the maps + file-spec.** In `config-presentation.yml` add:
  - a `packaging:` map keyed by full var name → `[pypi, oci]` subset. Every var currently in `server.json.jinja`'s arrays gets an entry: `FASTMCP_LOG_LEVEL: [pypi, oci]`; the OIDC/auth vars per the current pypi array; the oci-only extras `{PREFIX}_KV_STORE_URL: [pypi, oci]`, `PUID: [oci]`, `PGID: [oci]`, `{PREFIX}_BASE_URL: [oci]` etc. Cross-check every entry against the two current arrays in `server.json.jinja` so membership is preserved exactly. Domain-provenance vars need no entry (rule 2). Deliberately-absent vars (transport/port/host/debug, `EVENT_STORE_URL`) get an explanatory comment.
  - a `choices:` map: `FASTMCP_LOG_LEVEL: [DEBUG, INFO, WARNING, ERROR, CRITICAL]` (redecided content — verify against the current arrays' `choices`).
  - the `server.json` file-spec: `kind: json-splice`, `arrays: [{path: [packages, 0, environmentVariables], packaging: pypi}, {path: [packages, 1, environmentVariables], packaging: oci}]`.

- [ ] **Step 3: Regenerate `server.json.jinja`'s arrays.** Render smoke (`--vcs-ref=HEAD` after committing Steps 1-2), run the generator in write mode against `/tmp/smoke`, and author `server.json.jinja`'s two `environmentVariables` arrays to byte-match the generator output with concrete smoke tokens (`SMOKE_MCP_`, project name, etc.) back-substituted to their Jinja expressions (`{{ env_prefix }}_`, `{{ project_name }}`, …). `template-ci`'s `--check` is the exactness guarantee — iterate until a fresh render's `gen_config_surface.py --check` is clean.

- [ ] **Step 4: Integration tests.** Salvage `TestServerJsonSplice`: both arrays replaced (not just `packages[0]`); `version` + OCI `identifier` survive untouched; **byte round-trip vs `bump_manifests`** (`test_matches_bump_manifests_byte_for_byte_after_a_round_trip`); packaging membership differs pypi vs oci; `isSecret` set is exactly the three secrets; `isRequired` absent from every entry, paired with the markdown-`Required`-still-marks-them test; `--check` reports stale without rewriting; missing file / malformed JSON / missing array path all fail loudly naming the file; deterministic re-run. Adapt fixtures (`_seed_server_json`, `_server_json`, `_env_names`, `_env_entry`) to main. Strip spec/plan tokens.

- [ ] **Step 5: template-ci step.** Add a step (after the OIDC-tables step, `working-directory: /tmp/smoke`) asserting `server.json`'s two arrays carry the expected `SMOKE_MCP_*`/`FASTMCP_*` names per package, `version`/`identifier` are intact, and `isRequired` appears nowhere. Idempotence rides the existing `gen_config_surface.py --check` (do not add a second `--check`).

- [ ] **Step 6: Verify.** Render + `check_render_hygiene.py` clean; full test suite green; ruff/format clean; `gen_config_surface.py --check` idempotent; the generated `/tmp/smoke/server.json` diff vs the pre-F render is only the array reformat (no `version`/`identifier` change).

- [ ] **Step 7: Commit.** `feat(config): generate the server.json env-var arrays`

---

### Task 4: Schema validity

**Files:**
- Create: `schemas/server.schema.json` (vendored)
- Test: `scripts/tests/test_gen_config_surface.py`
- Modify: `.github/workflows/template-ci.yml`

- [ ] **Step 1: Vendor the schema.** Fetch the `2025-12-11` MCP server schema named by `server.json.jinja`'s `$schema` (`https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json`) and commit it to `schemas/server.schema.json`. Record the source URL + version in a top-of-repo note or the test's docstring (self-contained, no external-plan reference). If the fetch is unavailable in-sandbox, ask the controller to supply it rather than hand-authoring a schema.

- [ ] **Step 2: Schema-validation test.** Add a test that renders/generates `server.json` and runs `jsonschema.validate(generated, vendored_schema)` — mirroring the existing wizard-spec schema test. It must FAIL if a generated entry violates the schema (spot-check by asserting a deliberately-broken entry raises `ValidationError` in a sub-test, or trust `validate`'s coverage).

- [ ] **Step 3: template-ci schema gate.** Add (or fold into Task 3's step) a `jsonschema` validation of the rendered `/tmp/smoke/server.json` against the vendored schema, so a downstream-affecting schema regression fails template-ci.

- [ ] **Step 4: Verify + Commit.** Tests green, ruff clean. `test(config): validate the generated server.json against the vendored schema`

---

### Task 5: Migration note + close #257

**Files:**
- Modify: `docs/guides/config-migration.md.jinja`

- [ ] **Step 1: Document the flip.** In `config-migration.md.jinja`, add a section: `server.json`'s two `environmentVariables` arrays are now generated from `ProjectConfig` field metadata + `config-presentation.yml`'s `packaging:` map, spliced structurally (the generator replaces each `packages[].environmentVariables` array wholesale; `version` and the OCI `identifier` are left untouched for `bump_manifests`). **Rollout hazard:** a downstream that hand-edited entries inside those arrays will have them overwritten on the next `gen_config_surface.py --check`/generation — domain env-var customization must move into `ProjectConfig` field `metadata` (so the generator emits it) or a `config-presentation.domain.yml` entry. Quote the real `SystemExit` a broken array path raises (verify the exact text from `render_json_splice_file`/`_json_array_container`).

- [ ] **Step 2: Vale + hygiene.** `config-migration.md.jinja` renders to Vale-gated prose — no em dash, no "e.g."/"i.e."/"etc."; every env var carries `{{ env_prefix }}_`; quote the `SystemExit` in a fenced block so Vale ignores any punctuation inside it. Re-render, `vale sync`, `vale … docs README.md` → 0/0/0; `check_render_hygiene.py` clean.

- [ ] **Step 3: Commit.** `docs(migration): record the server.json array generation (closes #257)`

---

## Self-Review

- **Spec coverage:** json-splice engine (T1), packaging/choices/key validation (T2+T3), server.json arrays (T3), schema-valid (T4), bump_manifests round-trip byte-identical (T3 test), every guard bites (T2/T3 `SystemExit` tests). All spec-line-96 items mapped.
- **#257:** the two `examples/*.env` were removed in #264 and the env peers are now generated, so server.json is the whole live remainder — `Closes #257` is carried by T3+T5.
- **No placeholders:** each task names the exact salvage source (spike line ranges), the exact maps/values to add, and the verification command.
- **Type consistency:** `_json_default`/`_render_json_env_entry`/`_packaging_ids` signatures match the explorer's verified spike signatures; `_is_empty_default`/`_documented_default`/`_format_default` are reused from main, not re-ported.
