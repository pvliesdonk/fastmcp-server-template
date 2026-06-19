# Config-wizard: spec-owned domain knowledge, template-owned runtime

**Date:** 2026-06-19
**Status:** Design approved, pending implementation plan
**Issue:** [#169](https://github.com/pvliesdonk/fastmcp-server-template/issues/169) (scope expands — see §7)

## Problem

After the v2.2.1 adoption in `markdown-vault-mcp`, several config-wizard files
produce large conflicts on every `copier update` because domain knowledge has
leaked into template-owned runtime files. Downstream consumers were forced to
hand-edit JavaScript to express domain behavior, and those edits re-conflict on
every subsequent update.

Concretely, surveying the three live downstream specs and runtimes
(`markdown-vault-mcp`, `image-generation-mcp`, `scholar-mcp`) revealed:

1. **`wizard-spec.json`** — the template ships a 4-question skeleton; downstream
   replaces it entirely (markdown-vault-mcp: 64 questions). The skeleton and the
   domain spec diverge on first adoption and conflict on every update.

2. **`generators.js`** — markdown-vault-mcp diverged in *three* ways the existing
   `PROJECT-WIZARD-CONTAINER-PATHS` sentinel does **not** cover:
   - `CONTAINER_PATHS` populated with 5 domain entries (sentinel covers this one);
   - `generateDockerRun(map, hostVaultPath)` / `generateCompose(map, hostVaultPath)`
     gained an extra parameter to bind-mount the vault host path (a function-
     signature divergence the sentinel cannot express);
   - the vault host path is special-cased in `dockerEnvMap`.

3. **`wizard.js`** — markdown-vault-mcp added a line extracting
   `map["MARKDOWN_VAULT_MCP_SOURCE_DIR"]` and threading it into the docker
   generators (`hostVault`).

4. **Guard-level drift** — the wizard CSS (as of v2.2.1, after #168 renamed the
   classes and added `.cfg-error`) defines `.cfg-warning`, `.cfg-error`, and
   `.cfg-info`. `image-generation-mcp` correctly uses `level: "warning"`; any
   spec still using the pre-#168 `"warn"` renders **unstyled** (a latent, silent
   bug). With no schema and no canonical contract, each adoption agent guessed.

The root cause is not downstream misbehavior. The template gave domain knowledge
(vault paths, container path mappings, project identity) nowhere to live except
the runtime JS, so consumers edited the runtime — and now it conflicts forever.

## Principle

> The wizard **runtime** — `wizard.js`, `generators.js`, `config-wizard.css`,
> `wizard-spec-schema.json`, and the generic tests — is template-owned and
> **byte-identical across every consumer**. The **only** file that varies between
> consumers is `wizard-spec.json`, which holds 100% of the domain knowledge.
> Downstream never edits the runtime; new behavior is expressed as new *spec
> vocabulary*, which lives in the template.

To make this literally true, runtime files must carry **zero** per-project data —
including the copier variables (`{{ project_name }}`, `{{ docker_registry }}`,
`{{ env_prefix }}`) that `generators.js.jinja` bakes in today. Those move into the
spec's `meta` block. The runtime files stop being `.jinja` and become plain,
generic files that copier overwrites verbatim on every update — making conflict
structurally impossible.

## Design

### 1. Spec format (`wizard-spec.json`)

The spec gains a `meta` block and two new per-question Docker-path properties.
Full vocabulary:

```jsonc
{
  "version": 1,
  "meta": {
    "projectName": "markdown-vault-mcp",                       // CLI name + compose service + claude.json key
    "dockerImage": "ghcr.io/pvliesdonk/markdown-vault-mcp:latest",
    "envPrefix": "MARKDOWN_VAULT_MCP"                          // strip prefix for secret placeholders
  },
  "secretKeys": ["MARKDOWN_VAULT_MCP_BEARER_TOKEN"],          // vars never hydrated from URL; empty → placeholder
  "questions": [
    {
      "id": "source_dir",                  // required, unique
      "label": "Vault directory (host path)", // required
      "type": "text",                      // required: text | select | bool | number
      "var": "MARKDOWN_VAULT_MCP_SOURCE_DIR", // env var name (optional for pure-emit selects)
      "help": "Absolute path to your markdown vault on the host.", // optional
      "advancedGroup": "Persistence",      // optional; groups under the Advanced drawer
      "showIf": { "deployment": ["server"] }, // optional; visibility predicate (AND across keys)
      "dockerVolume": "/data/vault"        // NEW — see below
    },
    {
      "id": "index_path",
      "label": "FTS index path",
      "type": "text",
      "var": "MARKDOWN_VAULT_MCP_INDEX_PATH",
      "dockerPath": "/data/state/index.db" // NEW — see below
    },
    {
      "id": "read_only",
      "label": "Access mode",
      "type": "select",
      "options": [                         // for type=select; each has value+label, optional emit
        { "value": "true",  "label": "Read-only",  "emit": { "MARKDOWN_VAULT_MCP_READ_ONLY": "true" } },
        { "value": "false", "label": "Read-write", "emit": { "MARKDOWN_VAULT_MCP_READ_ONLY": "false" } }
      ]
    }
  ],
  "guards": [
    {
      "level": "warning",                  // warning | info | error (matches CSS classes)
      "message": "…",
      "when": { "openai_api_key": [""] }   // AND across keys; fires when all match
    }
  ]
}
```

#### New property: `dockerVolume`

A question whose **answer is a host path** that should be bind-mounted in
Docker/Compose output. When present and the question is visible, in Docker/Compose
mode:
- emit a bind mount `-v <answer>:<dockerVolume>` (compose: `- <answer>:<dockerVolume>`);
- rewrite the env var to the container path `<dockerVolume>` (not the host path).

When the answer is empty, the mount uses a `/path/to/<id>` placeholder so the
artifact still reads as "replace me". Local (stdio) and systemd output use the raw
host answer unchanged.

Replaces: the `hostVault` parameter threading in `generateDockerRun`/
`generateCompose`, the `wizard.js` extraction line, and the `SOURCE_DIR`
special-case in `dockerEnvMap`.

#### New property: `dockerPath`

A question whose value in Docker/Compose mode is a **fixed path inside the existing
named state volume** (`state-data:/data/state`). When present and visible, in
Docker/Compose mode the env var is rewritten to `<dockerPath>`; **no new mount** is
added. Local/systemd use the raw answer.

Replaces: the entire `CONTAINER_PATHS` map and its
`PROJECT-WIZARD-CONTAINER-PATHS-START/END` sentinel block, which are removed.

#### What stays hardcoded in the runtime

The named state volume `state-data:/data/state` and `FASTMCP_HOME=/data/state/fastmcp`
remain hardcoded in `generators.js` — these are template-owned fastmcp
infrastructure conventions, identical for every server, not domain knowledge.
`dockerPath` values point *into* that volume.

### 2. Runtime files become plain and generic

| File | Today | After |
|---|---|---|
| `docs/javascripts/config-wizard/generators.js.jinja` | `.jinja`, embeds `{{ project_name }}`, `{{ docker_registry }}`, `{{ env_prefix }}`, has `CONTAINER_PATHS` sentinel | **`generators.js`** — plain, generic; reads `meta`/`dockerVolume`/`dockerPath` off the spec; no jinja, no domain |
| `docs/javascripts/config-wizard/wizard.js` | plain, but had a domain-specific call pattern downstream | **`wizard.js`** — plain, generic; passes `(spec, answers, map)` to docker generators; no `hostVault` |
| `docs/stylesheets/config-wizard.css` | plain | **`config-wizard.css`** — unchanged, plain, generic |
| `docs/javascripts/config-wizard/wizard-spec-schema.json` | — | **NEW** — plain, generic JSON Schema for the spec |
| `docs/javascripts/config-wizard/wizard-spec.json.jinja` | `.jinja` skeleton | **stays `.jinja` as a one-time seed**; renders `meta` from copier vars; added to `_skip_if_exists` |

Generator signatures change so each reads what it needs off the spec instead of
copier vars. Precise per-function signatures:

| Generator | New signature | Needs |
|---|---|---|
| `generateDockerRun` | `(spec, answers, map)` | `meta.dockerImage` + `dockerVolume`/`dockerPath` walk |
| `generateCompose` | `(spec, answers, map)` | `meta.projectName` (service), `meta.dockerImage`, volumes |
| `generateSystemd` | `(meta, map)` | `meta.projectName` (`User=`, paths, `Description`) |
| `generateClaudeJson` | `(meta, map)` | `meta.projectName` (server key + command) |
| `generateDotenv` | `(map)` | nothing beyond the env map |

`generateSystemd` and `generateDotenv` operate on raw host answers (no Docker path
rewriting). Secret-placeholder stripping uses `meta.envPrefix` (`<YOUR_BEARER_TOKEN>`).
`wizard.js` updates all five call sites accordingly.

Project identity now comes from `spec.meta`:
- `meta.projectName` → CLI command, compose service name, `claude.json` server key,
  systemd `User=`/paths;
- `meta.dockerImage` → the `IMAGE` constant;
- `meta.envPrefix` → secret placeholder stripping (`<YOUR_BEARER_TOKEN>`).

### 3. Seed renders `meta` once

`wizard-spec.json.jinja` is the **seed**, rendered exactly once on first
`copier copy`, then protected by `_skip_if_exists`. Its `meta` block is the only
place copier variables appear:

```jsonc
"meta": {
  "projectName": "{{ project_name }}",
  "dockerImage": "{{ docker_registry }}/{{ project_name }}:latest",
  "envPrefix": "{{ env_prefix }}"
}
```

After first render this is plain domain-owned JSON. The tradeoff: a project
*rename* would not auto-propagate into a `_skip_if_exists` file — accepted, because
the seed renders correct values at copy time and renames are near-never.

### 4. File ownership (`copier.yml`)

Add to `_skip_if_exists`:
- `docs/javascripts/config-wizard/wizard-spec.json`
- `tests/test_config_wizard_domain.py`

Explicitly **not** in `_skip_if_exists` (template-owned, overwritten on update):
- `docs/javascripts/config-wizard/wizard.js`
- `docs/javascripts/config-wizard/generators.js`
- `docs/javascripts/config-wizard/wizard-spec-schema.json`
- `docs/stylesheets/config-wizard.css`
- `tests/test_config_wizard_smoke.py`
- `tests/test_config_wizard_spec_schema.py`

### 5. JSON Schema (`wizard-spec-schema.json`)

Template-owned, plain (non-`.jinja`), generic. Encodes the §1 vocabulary as the
canonical contract. Structural rules expressible directly in JSON Schema:
- required top-level: `version`, `meta`, `questions`; optional `secretKeys`, `guards`;
- `meta` requires `projectName`, `dockerImage`, `envPrefix` (all non-empty strings);
- question `type` ∈ `{text, select, bool, number}`; `id`/`label` required;
- `select` questions require `options` (each `value`+`label`, optional `emit`);
- guard `level` ∈ `{warning, info, error}` (matching the v2.2.1 CSS classes) —
  this alone catches the pre-#168 `"warn"` value, which renders unstyled;
- `dockerVolume`/`dockerPath` are absolute-path strings when present.

Cross-reference rules not expressible in pure JSON Schema (unique `id`s, every
`showIf`/`guard.when` key references an existing question id, every `secretKeys`
entry is some question's `var`) are asserted in the schema test (§6).

### 6. Tests

| File | Purpose | Ownership |
|---|---|---|
| `tests/test_config_wizard_smoke.py` | Browser smoke (existing `browser` marker): wizard renders; a `dockerVolume` question produces a `-v` mount + container-path env override; a `dockerPath` question rewrites env without a new mount. Uses the template's own seed spec. | Template-owned, generic |
| `tests/test_config_wizard_spec_schema.py` | **NEW.** Loads `wizard-spec.json`, validates against `wizard-spec-schema.json` (`jsonschema`), then asserts the cross-reference rules from §5. Pure Python + `jsonschema`, no browser. | Template-owned, generic |
| `tests/test_config_wizard_domain.py` | **NEW.** Empty placeholder (`pass`/skip) where downstream writes domain-specific browser assertions (field selectors, expected output strings, guard messages). | `_skip_if_exists` |

The schema test is the enforcement: an un-migrated spec (no `meta`), a bad guard
level (e.g. the pre-#168 `warn`), or a dangling `showIf` reference fails CI loudly
rather than breaking silently in the browser. `jsonschema` is added to the
generated project's test dependencies.

### 7. Issue scope

Issue #169 as written asks only for `_skip_if_exists` on two files. This design is
broader (schema, `meta` block, `dockerVolume`/`dockerPath` vocabulary, plain runtime
files, downstream migration). Per the project's issue-writing discipline, #169
should be expanded to reference this spec, or a short epic created with the spec as
its anchor. Addition (new vocabulary) and the implicit removal (`CONTAINER_PATHS`
sentinel, `hostVault` threading) are tracked together here because the removal is
small and inseparable from the addition.

## Downstream migration (rollout)

The three consumers that have adopted the config-wizard are the migration targets:
`markdown-vault-mcp`, `image-generation-mcp`, `scholar-mcp`. The other template
consumers (`paperless-mcp`, `reqeng-mcp`) have not adopted the wizard and are
unaffected.

Because the runtime is overwritten on update but `wizard-spec.json` is
`_skip_if_exists`, the per-repo order is:

1. Run `copier update` → runtime files (`generators.js`, `wizard.js`, css, schema,
   generic tests) are replaced with the canonical template versions. At this point
   the schema test **fails** because the existing spec has no `meta` — the desired
   loud signal.
2. Migrate `wizard-spec.json`:
   a. add the `meta` block (`projectName`, `dockerImage`, `envPrefix`);
   b. for each former `CONTAINER_PATHS` entry, add `dockerPath: "<container path>"`
      to the matching question;
   c. add `dockerVolume: "<container path>"` to the host-path bind-mount question
      (e.g. `source_dir` → `/data/vault` in markdown-vault-mcp);
   d. fix any guard `level` not in `{warning, info, error}` (e.g. a spec still on
      the pre-#168 `warn` → `warning`).
3. Re-run the gate; schema test + browser smoke pass.

Per-repo specifics:
- **markdown-vault-mcp** — `meta` (envPrefix `MARKDOWN_VAULT_MCP`); `dockerVolume`
  on `source_dir` → `/data/vault`; `dockerPath` on `index_path`, `embeddings_path`,
  `state_path`, `fastembed_cache_dir` (values from its current `CONTAINER_PATHS`);
  fix any guard `level: "warn"` → `"warning"` (its specs predate the #168 rename).
- **image-generation-mcp** — `meta` (envPrefix `IMAGE_GENERATION_MCP`); its guard
  already uses `level: "warning"` (now canonical); no docker volumes/paths needed
  unless its `scratch_dir` should bind-mount.
- **scholar-mcp** — `meta` (envPrefix `SCHOLAR_MCP`); consider `dockerPath` for
  `cache_dir` if it should live in the state volume.

Migration is the standard "point a coding agent at the latest release and update"
workflow; this spec section is its checklist.

## Testing strategy

- **Template gate** (`template-ci.yml`, the rendered smoke project): `ruff`, `mypy`,
  `pytest` including the new schema test against the seed spec; the browser smoke is
  `browser`-marked and skips when the site isn't built / Chromium absent.
- **`mkdocs build --strict`** must pass (the wizard is wired into the docs site);
  this is the downstream-workflow gate not covered by the local CLAUDE.md gate.
- **Schema self-consistency**: the seed `wizard-spec.json` (rendered) validates
  against `wizard-spec-schema.json` — the template dogfoods its own contract.

## Out of scope

- Adding new guard levels beyond `warning`/`info`/`error` (would require new CSS —
  a template change, not a downstream one).
- A runtime (browser) schema check — CI schema validation is the gate; the browser
  trusts a valid spec.
- Auto-migrating downstream specs programmatically — migration is the guided
  agent-update workflow.
