# Config-wizard Spec-Ownership Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Reconciliation note (2026-06-19):** this plan was first written against the
> v2.1.2 base, then reconciled onto **v2.2.1** after discovering the branch was
> built on a stale base. Two corrections supersede the verbatim code blocks
> below: (1) PR #168 renamed the guard CSS to `.cfg-warning`/`.cfg-error`/`.cfg-info`,
> so the schema's guard `level` enum is **`{warning, info, error}`** (not the
> `{warn, info}` shown in Task 1), and the schema test's negative case rejects
> `"warn"` (not `"warning"`); (2) the v2.2.1 `generators.js` `dotenvQuote` includes
> `$` in its safe-char exclusion (the #168 fix), preserved in the shipped file.
> The shipped files are authoritative; see the design spec for the corrected
> narrative.

**Goal:** Make the config-wizard runtime (`generators.js`, `wizard.js`, css, schema, generic tests) plain, template-owned, byte-identical across consumers, and move 100% of per-project/domain knowledge into `wizard-spec.json` via a `meta` block and generic `dockerVolume`/`dockerPath` vocabulary, enforced by a JSON Schema validation test.

**Architecture:** The browser wizard reads a single JSON spec. Project identity (`meta.projectName`/`dockerImage`/`envPrefix`) and Docker path behavior (`dockerVolume` host bind-mount, `dockerPath` fixed state-volume path) become spec data the generic generators read at runtime. The runtime files stop being `.jinja` and are overwritten verbatim on `copier update`; only `wizard-spec.json` is `_skip_if_exists` (domain-owned). A `jsonschema`-based pytest validates the shipped spec against a canonical schema and catches drift (e.g. guard `level: "warning"` vs the CSS-defined `warn`/`info`).

**Tech Stack:** Copier (Jinja2 templating), vanilla ES modules (no build step), MkDocs Material, pytest + pytest-playwright (browser-marked), `jsonschema`.

This plan changes the **template repository only**. Downstream rollout (migrating the three adopting consumers) is described in the design spec's "Downstream migration" section and is out of scope here.

## Global Constraints

- **This is a copier template.** Edit `.jinja` / source files under the template root; verify by rendering with `--vcs-ref=HEAD` against `tests/fixtures/smoke-answers.yml`. Copier reads from the git index — commit before rendering, or edits are ignored.
- **Smoke-answers rendered values** (from `tests/fixtures/smoke-answers.yml`): `project_name=smoke-mcp`, `python_module=smoke_mcp`, `env_prefix=SMOKE_MCP`, `docker_registry=ghcr.io/pvliesdonk`. So the rendered seed `meta` is `projectName="smoke-mcp"`, `dockerImage="ghcr.io/pvliesdonk/smoke-mcp:latest"`, `envPrefix="SMOKE_MCP"`.
- **Runtime files carry zero per-project data.** `generators.js`, `wizard.js`, `config-wizard.css`, `wizard-spec-schema.json` must contain no Jinja tokens and no domain strings. The only file with copier variables is the seed `wizard-spec.json.jinja` (its `meta` block).
- **`mypy --strict`** is on; all new Python is fully typed. `jsonschema` 4.26 ships no `py.typed`, so a mypy override is required (Task 3).
- **Ownership:** `wizard-spec.json` and `tests/test_config_wizard_domain.py` go in `_skip_if_exists`. The runtime files and the two generic test files (`test_config_wizard_smoke.py`, `test_config_wizard_spec_schema.py`) are template-owned (NOT in `_skip_if_exists`).
- **Spec vocabulary (canonical):** top-level `version` (const 1), `meta` (required: `projectName`, `dockerImage`, `envPrefix`), optional `secretKeys` (string[]), `questions` (≥1), optional `guards`. Question: required `id`/`label`/`type` (`text|select|bool|number`); optional `var`, `help`, `advancedGroup`, `showIf`, `options`, and **mutually exclusive** `dockerVolume`/`dockerPath` (absolute container paths). `select` requires `options` (each `value`+`label`, optional `emit`). Guard: `level` ∈ `{warn, info}`, `message`, `when`.
- **`dockerVolume` semantics:** in Docker/Compose only — emit a `-v <answer>:<dockerVolume>` bind mount (empty answer → `/path/to/<id>` placeholder) and set the question's `var` to `<dockerVolume>` (the container path) **always**. `dockerPath` semantics: in Docker/Compose only — set `var` to `<dockerPath>` **only when the var is otherwise present** in the env map (i.e. the user supplied a value or it is a secret placeholder); never adds a mount. Local/systemd use raw answers.

---

### Task 1: Add the canonical JSON Schema

**Files:**
- Create: `docs/javascripts/config-wizard/wizard-spec-schema.json` (plain, no `.jinja`)

**Interfaces:**
- Produces: a JSON Schema (Draft 2020-12) file consumed by Task 3's validation test and by downstream spec authors. No code symbols.

- [ ] **Step 1: Write the schema file**

Create `docs/javascripts/config-wizard/wizard-spec-schema.json` with exactly this content:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://pvliesdonk.github.io/fastmcp-server-template/wizard-spec-schema.json",
  "title": "fastmcp config-wizard spec",
  "type": "object",
  "additionalProperties": false,
  "required": ["version", "meta", "questions"],
  "properties": {
    "version": { "const": 1 },
    "meta": {
      "type": "object",
      "additionalProperties": false,
      "required": ["projectName", "dockerImage", "envPrefix"],
      "properties": {
        "projectName": { "type": "string", "minLength": 1 },
        "dockerImage": { "type": "string", "minLength": 1 },
        "envPrefix": { "type": "string", "pattern": "^[A-Z][A-Z0-9_]*[A-Z0-9]$" }
      }
    },
    "secretKeys": {
      "type": "array",
      "items": { "type": "string", "minLength": 1 }
    },
    "questions": {
      "type": "array",
      "minItems": 1,
      "items": { "$ref": "#/$defs/question" }
    },
    "guards": {
      "type": "array",
      "items": { "$ref": "#/$defs/guard" }
    }
  },
  "$defs": {
    "question": {
      "type": "object",
      "additionalProperties": false,
      "required": ["id", "label", "type"],
      "properties": {
        "id": { "type": "string", "pattern": "^[a-z][a-z0-9_]*$" },
        "label": { "type": "string", "minLength": 1 },
        "help": { "type": "string", "minLength": 1 },
        "type": { "enum": ["text", "select", "bool", "number"] },
        "var": { "type": "string", "pattern": "^[A-Z][A-Z0-9_]*$" },
        "advancedGroup": { "type": "string", "minLength": 1 },
        "showIf": {
          "type": "object",
          "minProperties": 1,
          "additionalProperties": {
            "type": "array",
            "items": { "type": "string" }
          }
        },
        "options": {
          "type": "array",
          "minItems": 1,
          "items": { "$ref": "#/$defs/option" }
        },
        "dockerVolume": { "type": "string", "pattern": "^/" },
        "dockerPath": { "type": "string", "pattern": "^/" }
      },
      "allOf": [
        {
          "if": { "required": ["type"], "properties": { "type": { "const": "select" } } },
          "then": { "required": ["options"] }
        }
      ],
      "not": { "required": ["dockerVolume", "dockerPath"] }
    },
    "option": {
      "type": "object",
      "additionalProperties": false,
      "required": ["value", "label"],
      "properties": {
        "value": { "type": "string" },
        "label": { "type": "string", "minLength": 1 },
        "emit": {
          "type": "object",
          "minProperties": 1,
          "additionalProperties": { "type": "string" }
        }
      }
    },
    "guard": {
      "type": "object",
      "additionalProperties": false,
      "required": ["level", "message", "when"],
      "properties": {
        "level": { "enum": ["warn", "info"] },
        "message": { "type": "string", "minLength": 1 },
        "when": {
          "type": "object",
          "minProperties": 1,
          "additionalProperties": {
            "type": "array",
            "items": { "type": "string" }
          }
        }
      }
    }
  }
}
```

- [ ] **Step 2: Verify it is valid JSON and a valid schema**

Run: `python3 -c "import json,jsonschema; s=json.load(open('docs/javascripts/config-wizard/wizard-spec-schema.json')); jsonschema.Draft202012Validator.check_schema(s); print('schema OK')"`
Expected: `schema OK` (if `jsonschema` is not yet importable in the ambient interpreter, this is verified instead in Task 3 Step 4 after the dependency is added; in that case just run the `json.load` half to confirm valid JSON).

Fallback JSON-only check: `python3 -c "import json; json.load(open('docs/javascripts/config-wizard/wizard-spec-schema.json')); print('json OK')"`
Expected: `json OK`

- [ ] **Step 3: Commit**

```bash
git add docs/javascripts/config-wizard/wizard-spec-schema.json
git commit -m "feat(wizard): add canonical JSON Schema for wizard-spec.json"
```

---

### Task 2: Add `meta` to the seed spec; set ownership in copier.yml; add domain placeholder

**Files:**
- Modify: `docs/javascripts/config-wizard/wizard-spec.json.jinja` (add `meta` block)
- Create: `tests/test_config_wizard_domain.py.jinja` (downstream-owned placeholder)
- Modify: `copier.yml` (`_skip_if_exists`)

**Interfaces:**
- Produces: a rendered `wizard-spec.json` whose `meta` block supplies `projectName`/`dockerImage`/`envPrefix` to the runtime (Task 4). The `_skip_if_exists` entries make `wizard-spec.json` and `tests/test_config_wizard_domain.py` domain-owned.

- [ ] **Step 1: Add the `meta` block to the seed spec**

In `docs/javascripts/config-wizard/wizard-spec.json.jinja`, replace the opening:

```json
{
  "version": 1,
  "secretKeys": [
```

with:

```json
{
  "version": 1,
  "meta": {
    "projectName": "{{ project_name }}",
    "dockerImage": "{{ docker_registry }}/{{ project_name }}:latest",
    "envPrefix": "{{ env_prefix }}"
  },
  "secretKeys": [
```

Leave the rest of the file (questions, guards) unchanged.

- [ ] **Step 2: Create the downstream domain-test placeholder**

Create `tests/test_config_wizard_domain.py.jinja` with exactly this content:

```python
"""Domain-specific config-wizard tests for {{ human_name }}.

This file is owned by the generated project (kept across ``copier update`` via
``_skip_if_exists``). The template seeds it once with a single skipped
placeholder test; add browser assertions here that depend on *this project's*
``wizard-spec.json`` — e.g. that a specific field renders, that a chosen option
emits the expected env var, or that a guard message appears. The generic
framework tests live in ``test_config_wizard_smoke.py`` (template-owned) and
must not be edited here.

See ``test_config_wizard_smoke.py`` for the page/browser fixtures to import.
"""

from __future__ import annotations

import pytest


def test_domain_placeholder() -> None:
    # Placeholder: the template seeds this file with one skipped test so the
    # path exists and is kept across copier updates, while neither failing CI
    # on an empty file nor reporting a hollow "passing" test. Replace this skip
    # with real domain assertions (field renders, option emits the expected env
    # var, guard message appears).
    pytest.skip("No domain-specific wizard tests yet -- add them here.")
```

- [ ] **Step 3: Add both rendered paths to `_skip_if_exists` in copier.yml**

In `copier.yml`, inside the `_skip_if_exists:` list, add these two entries after the `.vale/styles/config/vocabularies/Base/accept.txt` line (keep alphabetical-ish grouping is not required; place them together with a comment):

```yaml
  # Config-wizard domain spec — the entire file is domain content (the project's
  # questions, secrets, guards, and meta identity).  The wizard *runtime*
  # (generators.js, wizard.js, config-wizard.css, wizard-spec-schema.json) is
  # template-owned and overwritten on update; only this spec is domain-owned.
  - "docs/javascripts/config-wizard/wizard-spec.json"
  # Domain-specific wizard browser tests — seeded empty, owned downstream.
  # Generic framework tests stay in test_config_wizard_smoke.py (template-owned).
  - "tests/test_config_wizard_domain.py"
```

- [ ] **Step 4: Verify the seed spec is still valid JSON after rendering**

Run:
```bash
git add -A && git commit -m "feat(wizard): add meta block to seed spec; own spec + domain test downstream" && \
rm -rf /tmp/smoke && \
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke && \
python3 -c "import json; m=json.load(open('/tmp/smoke/docs/javascripts/config-wizard/wizard-spec.json'))['meta']; print(m); assert m=={'projectName':'smoke-mcp','dockerImage':'ghcr.io/pvliesdonk/smoke-mcp:latest','envPrefix':'SMOKE_MCP'}"
```
Expected: prints the meta dict and exits 0 (the commit is folded into this step because copier renders from the committed index).

Note: the commit was performed in this step; Task 2 needs no separate commit step.

---

### Task 3: Schema-validation test + `jsonschema` dependency + mypy override

**Files:**
- Modify: `pyproject.toml.jinja` (add `jsonschema` to `dev` group; add mypy override)
- Create: `tests/test_config_wizard_spec_schema.py.jinja`

**Interfaces:**
- Consumes: `wizard-spec-schema.json` (Task 1), the rendered `wizard-spec.json` with `meta` (Task 2).
- Produces: an always-on (non-browser) pytest that validates the shipped spec and asserts cross-reference rules. This is the drift gate.

- [ ] **Step 1: Add `jsonschema` to the `dev` dependency group**

In `pyproject.toml.jinja`, change the `dev` group from:

```toml
dev = [
    "pytest>=8",
    "pytest-asyncio>=0.24",
    "pytest-cov>=5",
    "diff-cover>=9",
    "ruff>=0.6",
    "mypy>=1.11",
    "pre-commit>=3",
    "pip-audit>=2.7",
]
```

to (add the `jsonschema` line):

```toml
dev = [
    "pytest>=8",
    "pytest-asyncio>=0.24",
    "pytest-cov>=5",
    "diff-cover>=9",
    "ruff>=0.6",
    "mypy>=1.11",
    "pre-commit>=3",
    "pip-audit>=2.7",
    "jsonschema>=4.18",
]
```

- [ ] **Step 2: Add the mypy override for `jsonschema`**

In `pyproject.toml.jinja`, find the existing override block:

```toml
[[tool.mypy.overrides]]
module = ["fastmcp_pvl_core", "fastmcp_pvl_core.*"]
ignore_missing_imports = true
```

and add a second override block immediately after it:

```toml
[[tool.mypy.overrides]]
module = ["jsonschema", "jsonschema.*"]
ignore_missing_imports = true
```

- [ ] **Step 3: Write the schema-validation test**

Create `tests/test_config_wizard_spec_schema.py.jinja` with exactly this content:

```python
"""Validate the shipped wizard-spec.json against the canonical JSON Schema.

Template-owned and generic: loads whatever ``wizard-spec.json`` this project
ships and checks it against ``wizard-spec-schema.json`` plus the cross-reference
rules JSON Schema cannot express (unique ids, dangling references, secret keys
declared by a question). Runs in the main test lane (no browser required), so it
is the gate that catches spec drift — e.g. a guard ``level`` outside {warn,
info} or a ``meta`` block that a stale spec never added.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest

_WIZARD_DIR = (
    Path(__file__).resolve().parent.parent
    / "docs"
    / "javascripts"
    / "config-wizard"
)
_SPEC_PATH = _WIZARD_DIR / "wizard-spec.json"
_SCHEMA_PATH = _WIZARD_DIR / "wizard-spec-schema.json"


@pytest.fixture(scope="module")
def spec() -> dict[str, Any]:
    return json.loads(_SPEC_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def _minimal_valid_spec() -> dict[str, Any]:
    return {
        "version": 1,
        "meta": {
            "projectName": "demo",
            "dockerImage": "ghcr.io/acme/demo:latest",
            "envPrefix": "DEMO",
        },
        "secretKeys": [],
        "questions": [
            {
                "id": "deployment",
                "label": "Where?",
                "type": "select",
                "options": [
                    {"value": "local", "label": "Local"},
                    {"value": "server", "label": "Server"},
                ],
            }
        ],
        "guards": [],
    }


def test_schema_itself_is_valid(schema: dict[str, Any]) -> None:
    jsonschema.Draft202012Validator.check_schema(schema)


def test_shipped_spec_matches_schema(
    spec: dict[str, Any], schema: dict[str, Any]
) -> None:
    jsonschema.validate(spec, schema)


def test_question_ids_are_unique(spec: dict[str, Any]) -> None:
    ids = [q["id"] for q in spec["questions"]]
    assert len(ids) == len(set(ids)), f"duplicate question id(s): {ids}"


def test_showif_references_existing_ids(spec: dict[str, Any]) -> None:
    ids = {q["id"] for q in spec["questions"]}
    for q in spec["questions"]:
        for key in q.get("showIf") or {}:
            assert key in ids, f"showIf references unknown question id: {key}"


def test_guard_when_references_existing_ids(spec: dict[str, Any]) -> None:
    ids = {q["id"] for q in spec["questions"]}
    for guard in spec.get("guards", []):
        for key in guard["when"]:
            assert key in ids, f"guard.when references unknown question id: {key}"


def test_secret_keys_are_declared_vars(spec: dict[str, Any]) -> None:
    declared = {q.get("var") for q in spec["questions"]}
    for key in spec.get("secretKeys", []):
        assert key in declared, f"secretKey not declared by any question var: {key}"


def test_schema_rejects_unknown_guard_level(schema: dict[str, Any]) -> None:
    bad = _minimal_valid_spec()
    bad["guards"] = [
        {"level": "warning", "message": "x", "when": {"deployment": ["server"]}}
    ]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)


def test_schema_rejects_missing_meta(schema: dict[str, Any]) -> None:
    bad = _minimal_valid_spec()
    del bad["meta"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)


def test_schema_rejects_dockervolume_and_dockerpath_together(
    schema: dict[str, Any],
) -> None:
    bad = _minimal_valid_spec()
    bad["questions"].append(
        {
            "id": "data_dir",
            "label": "Data",
            "type": "text",
            "var": "DEMO_DATA_DIR",
            "dockerVolume": "/data/app",
            "dockerPath": "/data/state/app",
        }
    )
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)
```

- [ ] **Step 4: Render and run the schema test against the rendered project**

Run:
```bash
git add -A && git commit -m "test(wizard): validate wizard-spec.json against schema" && \
rm -rf /tmp/smoke && \
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke && \
cd /tmp/smoke && uv sync --all-extras --all-groups && \
uv run pytest tests/test_config_wizard_spec_schema.py -v
```
Expected: all tests PASS (10 tests). In particular `test_shipped_spec_matches_schema` passes (the rendered seed has `meta`), and the three `test_schema_rejects_*` cases pass (the schema has teeth).

- [ ] **Step 5: Confirm mypy is clean on the new test**

Run (still in `/tmp/smoke`): `uv run mypy tests/test_config_wizard_spec_schema.py`
Expected: `Success: no issues found in 1 source file`

The commit was performed in Step 4; Task 3 needs no separate commit step. Return to the template dir afterward: `cd /mnt/code/mcp-servers/fastmcp-server-template`.

---

### Task 4: Rewrite the wizard runtime (generators.js + wizard.js) and its browser tests

**Files:**
- Rename + rewrite: `docs/javascripts/config-wizard/generators.js.jinja` → `docs/javascripts/config-wizard/generators.js` (plain, no Jinja)
- Modify: `docs/javascripts/config-wizard/wizard.js` (render() call sites + one defensive default)
- Rewrite: `tests/test_config_wizard_smoke.py.jinja` (generic framework tests + synthetic-spec generator unit tests)

**Interfaces:**
- Consumes: `spec.meta` (Task 2), the schema vocabulary (Task 1).
- Produces (generators.js exports — these exact signatures are what wizard.js and the tests rely on):
  - `buildEnvMap(spec, answers) -> {VAR: value}`
  - `isVisible(q, answers) -> boolean`
  - `dockerVolumes(spec, answers) -> [[hostPath, containerPath], ...]`
  - `generateDotenv(map) -> string`
  - `generateClaudeJson(meta, map) -> string`
  - `generateDockerRun(spec, answers, map) -> string`
  - `generateCompose(spec, answers, map) -> string`
  - `generateSystemd(meta, map) -> string`

- [ ] **Step 1: Write the new browser test file (tests first)**

Overwrite `tests/test_config_wizard_smoke.py.jinja` with exactly this content. It keeps the server/HTTP fixtures, replaces the two old framework tests with spec-agnostic ones, and adds generator unit tests that import `generators.js` with synthetic specs (independent of whatever `wizard-spec.json` ships):

```python
"""Browser smoke tests for the built config-wizard page.

Marked ``browser``; requires the ``browser`` dependency group and
``playwright install chromium``. Runs against the built ``site/`` directory, so
``mkdocs build`` must have run first.

Two kinds of tests live here, both template-owned and spec-agnostic:

* Framework tests drive the actual rendered page and assert only on invariants
  every spec shares (the ``deployment`` question exists; output carries the
  project identity from ``meta``).
* Generator unit tests import ``generators.js`` directly and feed it synthetic
  specs, so they exercise ``dockerVolume`` / ``dockerPath`` behaviour without
  depending on this project's questions.

Domain-specific assertions belong in ``test_config_wizard_domain.py``.
"""

from __future__ import annotations

import functools
import http.server
import socketserver
import threading
import typing
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")

if typing.TYPE_CHECKING:
    from playwright.sync_api import Browser, Page

SITE = Path(__file__).resolve().parent.parent / "site"

pytestmark = pytest.mark.browser


@pytest.fixture(scope="module")
def site_url() -> typing.Iterator[str]:
    if not (SITE / "configuration-generator" / "index.html").exists():
        pytest.skip("site/ not built -- run `uv run mkdocs build` first")
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(SITE)
    )
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as httpd:
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{port}"
        finally:
            httpd.shutdown()


@pytest.fixture(scope="module")
def browser(site_url: str) -> typing.Iterator[Browser]:  # noqa: ARG001 — depended on only for fixture ordering
    # Depend on site_url so its "site not built" skip runs BEFORE we try to
    # launch Chromium. In the main CI test lane (no built site, no installed
    # browser) this makes the smoke tests skip cleanly instead of erroring.
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture
def page(browser: Browser, site_url: str) -> typing.Iterator[Page]:
    # Fresh page per test: the wizard keeps answer state in a module-level JS
    # object, so each test must start from a clean load to stay order-independent.
    pg = browser.new_page()
    pg.goto(f"{site_url}/configuration-generator/")
    pg.wait_for_selector("#cfg-wizard select")
    yield pg
    pg.close()


# --- Framework tests: drive the real page, assert only on universal invariants.


def test_local_emits_claude_config_with_project_name(page: Page) -> None:
    page.select_option('[data-qid="deployment"] select', "local")
    text = page.inner_text(".cfg-output")
    # meta.projectName renders into the Claude config server key + command.
    assert "{{ project_name }}" in text


def test_server_emits_docker_image_from_meta(page: Page) -> None:
    page.select_option('[data-qid="deployment"] select', "server")
    text = page.inner_text("#cfg-wizard")
    assert "{{ docker_registry }}/{{ project_name }}:latest" in text


# --- Generator unit tests: import generators.js with synthetic specs.

_GEN_IMPORT = "/javascripts/config-wizard/generators.js"


def _eval_generators(page: Page, body: str) -> typing.Any:
    """Run `body` (an arrow function source) with generators.js imported.

    `body` is JS source of the form `(g) => { ...; return ...; }`; it receives
    the imported generators module as `g`.
    """
    script = (
        "async () => { const g = await import('"
        + _GEN_IMPORT
        + "'); return ("
        + body
        + ")(g); }"
    )
    return page.evaluate(script)


def test_docker_volume_adds_mount_and_fixes_container_path(page: Page) -> None:
    result = _eval_generators(
        page,
        """(g) => {
          const spec = { version: 1,
            meta: { projectName: 'demo', dockerImage: 'img:latest', envPrefix: 'DEMO' },
            secretKeys: [],
            questions: [{ id: 'data_dir', label: 'D', type: 'text', var: 'DEMO_DATA_DIR', dockerVolume: '/data/app' }],
            guards: [] };
          const answers = { deployment: 'server', data_dir: '/host/data' };
          const map = g.buildEnvMap(spec, answers);
          return g.generateDockerRun(spec, answers, map);
        }""",
    )
    assert "-v /host/data:/data/app" in result
    # env var is fixed to the container path, NOT the host path.
    assert "DEMO_DATA_DIR=/data/app" in result
    assert "DEMO_DATA_DIR=/host/data" not in result


def test_docker_volume_empty_answer_uses_placeholder(page: Page) -> None:
    result = _eval_generators(
        page,
        """(g) => {
          const spec = { version: 1,
            meta: { projectName: 'demo', dockerImage: 'img:latest', envPrefix: 'DEMO' },
            secretKeys: [],
            questions: [{ id: 'data_dir', label: 'D', type: 'text', var: 'DEMO_DATA_DIR', dockerVolume: '/data/app' }],
            guards: [] };
          const answers = { deployment: 'server' };
          const map = g.buildEnvMap(spec, answers);
          return g.generateDockerRun(spec, answers, map);
        }""",
    )
    assert "-v /path/to/data_dir:/data/app" in result


def test_docker_path_fixes_present_var_without_mount(page: Page) -> None:
    result = _eval_generators(
        page,
        """(g) => {
          const spec = { version: 1,
            meta: { projectName: 'demo', dockerImage: 'img:latest', envPrefix: 'DEMO' },
            secretKeys: [],
            questions: [{ id: 'index_path', label: 'I', type: 'text', var: 'DEMO_INDEX_PATH', dockerPath: '/data/state/index.db' }],
            guards: [] };
          const answers = { deployment: 'server', index_path: '/host/index.db' };
          const map = g.buildEnvMap(spec, answers);
          return { docker: g.generateDockerRun(spec, answers, map) };
        }""",
    )
    assert "DEMO_INDEX_PATH=/data/state/index.db" in result["docker"]
    # dockerPath never adds a -v mount.
    assert "/data/state/index.db:" not in result["docker"]
    assert "-v /host/index.db" not in result["docker"]


def test_docker_path_absent_var_stays_absent(page: Page) -> None:
    result = _eval_generators(
        page,
        """(g) => {
          const spec = { version: 1,
            meta: { projectName: 'demo', dockerImage: 'img:latest', envPrefix: 'DEMO' },
            secretKeys: [],
            questions: [{ id: 'index_path', label: 'I', type: 'text', var: 'DEMO_INDEX_PATH', dockerPath: '/data/state/index.db' }],
            guards: [] };
          const answers = { deployment: 'server' };
          const map = g.buildEnvMap(spec, answers);
          return g.generateDockerRun(spec, answers, map);
        }""",
    )
    # User left it blank → dockerPath does not inject it (persistence not opted in).
    assert "DEMO_INDEX_PATH" not in result


def test_systemd_uses_raw_host_path_not_container(page: Page) -> None:
    result = _eval_generators(
        page,
        """(g) => {
          const spec = { version: 1,
            meta: { projectName: 'demo', dockerImage: 'img:latest', envPrefix: 'DEMO' },
            secretKeys: [],
            questions: [{ id: 'data_dir', label: 'D', type: 'text', var: 'DEMO_DATA_DIR', dockerVolume: '/data/app' }],
            guards: [] };
          const answers = { deployment: 'server', data_dir: '/host/data' };
          const map = g.buildEnvMap(spec, answers);
          return g.generateSystemd(spec.meta, map);
        }""",
    )
    # systemd is a host-path context: no container-path rewrite.
    assert "DEMO_DATA_DIR=/host/data" in result
    assert "/data/app" not in result
```

- [ ] **Step 2: Replace generators.js.jinja with a plain generators.js**

Remove the old Jinja file and create the plain one:

```bash
git rm docs/javascripts/config-wizard/generators.js.jinja
```

Create `docs/javascripts/config-wizard/generators.js` with exactly this content:

```javascript
// Pure config-output generators. No DOM. All per-project data comes from
// spec.meta; Docker path behaviour comes from per-question dockerVolume /
// dockerPath. This file is template-owned and identical across all consumers.

const FASTMCP_HOME = "/data/state/fastmcp";
// The named state volume, mounted in every Docker/Compose artifact.
const STATE_VOLUME = "state-data:/data/state";

const secretPlaceholder = (key, envPrefix) =>
  `<YOUR_${key.replace(new RegExp(`^${envPrefix}_`), "")}>`;

// Single-quote a value for a POSIX shell `-e KEY=value` argument, but only when
// it contains characters outside the shell-safe set (keeps clean output tidy).
const shellQuote = (v) => {
  const s = String(v);
  return /^[A-Za-z0-9_@%+=:,./-]+$/.test(s) ? s : `'${s.replace(/'/g, "'\\''")}'`;
};

// Quote a YAML scalar only when it contains characters that would otherwise
// break parsing (or has surrounding whitespace, or is empty).
const yamlScalar = (v) => {
  const s = String(v);
  return /[\n:#[\]{}&*?|<>=!%@,`"']|^\s|\s$|^$/.test(s) ? JSON.stringify(s) : s;
};

// A systemd `Environment=` line. systemd does NOT expand `$` in Environment=
// values (expansion only happens in ExecXYZ= directives), so `$` is left
// literal. It DOES resolve `%` specifiers (escaped as `%%`) and process
// C-style `\`/`"` escapes (systemd/systemd#36488), so those are escaped, and
// the assignment is wrapped in quotes when it contains whitespace, a quote, or
// a backslash.
const systemdLine = (k, v) => {
  const s = String(v).replace(/%/g, "%%");
  if (!/[\s"\\]/.test(s)) return `Environment=${k}=${s}`;
  const escaped = s.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
  return `Environment="${k}=${escaped}"`;
};

// Build {VAR: value} from the spec + answers. Empty non-secret answers are
// dropped; a visible secret left empty becomes a placeholder so the artifact is
// still complete and signals "replace me".
export function buildEnvMap(spec, answers) {
  const secrets = new Set(spec.secretKeys ?? []);
  const envPrefix = spec.meta.envPrefix;
  const map = {};
  for (const q of spec.questions) {
    if (!isVisible(q, answers)) continue;
    if (q.options) {
      const chosen = q.options.find((o) => o.value === answers[q.id]);
      if (chosen && chosen.emit) Object.assign(map, chosen.emit);
    }
    if (q.var) {
      const raw = answers[q.id];
      if (raw !== undefined && raw !== "") map[q.var] = raw;
      else if (secrets.has(q.var)) map[q.var] = secretPlaceholder(q.var, envPrefix);
    }
  }
  return map;
}

export function isVisible(q, answers) {
  if (!q.showIf) return true;
  return Object.entries(q.showIf).every(([k, allowed]) => allowed.includes(answers[k]));
}

// Bind mounts for visible dockerVolume questions: [[hostPath, containerPath]].
// An empty answer yields a `/path/to/<id>` placeholder so the artifact still
// reads as "replace me".
export function dockerVolumes(spec, answers) {
  const vols = [];
  for (const q of spec.questions) {
    if (!q.dockerVolume || !isVisible(q, answers)) continue;
    const host = answers[q.id] || `/path/to/${q.id}`;
    vols.push([host, q.dockerVolume]);
  }
  return vols;
}

// Rewrite the env map for Docker/Compose output. A dockerVolume question's var
// is always fixed to its container path (the bind mount makes that path real).
// A dockerPath question's var is fixed only when already present (the user
// opted into the value); dockerPath never adds a mount. FASTMCP_HOME is injected.
function dockerEnvMap(spec, answers, map) {
  const out = { ...map };
  for (const q of spec.questions) {
    if (!isVisible(q, answers) || !q.var) continue;
    if (q.dockerVolume) {
      out[q.var] = q.dockerVolume;
    } else if (q.dockerPath && q.var in out) {
      out[q.var] = q.dockerPath;
    }
  }
  out.FASTMCP_HOME = FASTMCP_HOME;
  return out;
}

// Quote a .env value when it contains characters that common dotenv parsers
// treat specially (notably `#`, which starts an inline comment in an unquoted
// value and would silently truncate the value on load, and `$`, which triggers
// variable expansion when the file is shell-sourced — the #168 fix).
const dotenvQuote = (v) => {
  const s = String(v);
  if (!/[#"'\\\s$]/.test(s)) return s;
  return `"${s.replace(/\\/g, "\\\\").replace(/"/g, '\\"').replace(/\$/g, '\\$')}"`;
};

export function generateDotenv(map) {
  return Object.entries(map).map(([k, v]) => `${k}=${dotenvQuote(v)}`).join("\n") + "\n";
}

export function generateClaudeJson(meta, map) {
  return JSON.stringify(
    { mcpServers: { [meta.projectName]: { command: meta.projectName, args: ["serve"], env: map } } },
    null, 2,
  );
}

export function generateDockerRun(spec, answers, map) {
  const env = dockerEnvMap(spec, answers, map);
  const lines = [
    `docker run -d --name ${spec.meta.projectName}`,
    "  -p 8000:8000",
    `  -v ${STATE_VOLUME}`,
  ];
  for (const [host, container] of dockerVolumes(spec, answers)) {
    lines.push(`  -v ${shellQuote(host)}:${container}`);
  }
  for (const [k, v] of Object.entries(env)) lines.push(`  -e ${k}=${shellQuote(v)}`);
  lines.push(`  ${spec.meta.dockerImage}`);
  return lines.join(" \\\n");
}

export function generateCompose(spec, answers, map) {
  const env = dockerEnvMap(spec, answers, map);
  const volLines = [`      - ${STATE_VOLUME}`];
  for (const [host, container] of dockerVolumes(spec, answers)) {
    volLines.push(`      - ${yamlScalar(`${host}:${container}`)}`);
  }
  const envLines = Object.entries(env).map(([k, v]) => `      ${k}: ${yamlScalar(v)}`).join("\n");
  return [
    "services:",
    `  ${spec.meta.projectName}:`,
    `    image: ${spec.meta.dockerImage}`,
    "    ports:",
    '      - "8000:8000"',
    "    volumes:",
    ...volLines,
    "    environment:",
    envLines,
    "volumes:",
    "  state-data:",
  ].join("\n");
}

export function generateSystemd(meta, map) {
  const name = meta.projectName;
  const envLines = Object.entries(map).map(([k, v]) => systemdLine(k, v)).join("\n");
  return [
    "[Unit]",
    `Description=${name}`,
    "After=network.target",
    "",
    "[Service]",
    "Type=simple",
    `# Create this user first: sudo useradd --system --no-create-home ${name}`,
    `User=${name}`,
    `ExecStart=/opt/${name}/venv/bin/${name} serve --transport http`,
    envLines,
    "Restart=on-failure",
    "",
    "[Install]",
    "WantedBy=multi-user.target",
  ].join("\n");
}
```

- [ ] **Step 3: Update wizard.js call sites and the guards default**

In `docs/javascripts/config-wizard/wizard.js`, replace the block at lines 122–131:

```javascript
  const map = buildEnvMap(spec, answers);
  const local = answers.deployment !== "server";
  const tabs = local
    ? [["Claude config", generateClaudeJson(map)], [".env", generateDotenv(map)]]
    : [
        ["docker run", generateDockerRun(map)],
        ["compose", generateCompose(map)],
        ["systemd", generateSystemd(map)],
        [".env", generateDotenv(map)],
      ];
```

with:

```javascript
  const meta = spec.meta;
  const map = buildEnvMap(spec, answers);
  const local = answers.deployment !== "server";
  const tabs = local
    ? [["Claude config", generateClaudeJson(meta, map)], [".env", generateDotenv(map)]]
    : [
        ["docker run", generateDockerRun(spec, answers, map)],
        ["compose", generateCompose(spec, answers, map)],
        ["systemd", generateSystemd(meta, map)],
        [".env", generateDotenv(map)],
      ];
```

Then make the guards loop defensive — replace the line:

```javascript
  for (const g of spec.guards) {
```

with:

```javascript
  for (const g of spec.guards ?? []) {
```

- [ ] **Step 4: Render, build the site, run the wizard browser tests**

Run:
```bash
git add -A && git commit -m "feat(wizard): spec-driven meta + dockerVolume/dockerPath; plain runtime" && \
rm -rf /tmp/smoke && \
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke && \
cd /tmp/smoke && uv sync --all-extras --all-groups && \
uv run playwright install chromium && \
uv run mkdocs build && \
uv run pytest tests/test_config_wizard_smoke.py -v
```
Expected: all browser tests PASS (2 framework + 6 generator-unit = 8 tests). If `playwright install chromium` is unavailable in the environment, this verification moves to Task 5's CI note — but attempt it here first.

The commit was performed in Step 4. Return to the template dir: `cd /mnt/code/mcp-servers/fastmcp-server-template`.

---

### Task 5: Full gate verification on the rendered project

**Files:**
- None (verification + final confirmation task)

**Interfaces:**
- Consumes: all prior tasks.
- Produces: confidence the rendered project passes the same gate CI runs.

- [ ] **Step 1: Clean render at HEAD**

Run:
```bash
rm -rf /tmp/smoke && \
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
```
Expected: render completes with no errors; `/tmp/smoke/docs/javascripts/config-wizard/` contains `generators.js` (plain), `wizard.js`, `wizard-spec.json`, `wizard-spec-schema.json`.

- [ ] **Step 2: Confirm the runtime files carry no Jinja tokens or domain strings**

Run:
```bash
cd /tmp/smoke && \
! grep -RnE '\{\{|\{%' docs/javascripts/config-wizard/generators.js docs/javascripts/config-wizard/wizard.js docs/javascripts/config-wizard/wizard-spec-schema.json docs/stylesheets/config-wizard.css && \
echo "runtime files are token-free"
```
Expected: prints `runtime files are token-free` (the `!` inverts grep, so a clean exit means no matches found).

- [ ] **Step 3: Run the full gate**

Run (in `/tmp/smoke`):
```bash
uv sync --all-extras --all-groups && \
uv run ruff check . && uv run ruff format --check . && \
uv run mypy src/ tests/ && \
uv run pytest -x -q && \
uv run mkdocs build --strict
```
Expected: ruff clean, mypy `Success`, pytest passes (the schema test runs in this lane; the browser tests skip unless chromium + built site are present), `mkdocs build --strict` succeeds.

- [ ] **Step 4: Run the browser lane explicitly (if not already green in Task 4)**

Run (in `/tmp/smoke`):
```bash
uv run playwright install chromium && \
uv run mkdocs build && \
uv run pytest -m browser -v
```
Expected: 8 browser tests pass.

- [ ] **Step 5: Confirm `_skip_if_exists` ownership by re-running copier update semantics**

Verify the two domain files are protected while the runtime is overwritten. Simulate by editing the rendered spec, then re-rendering over it:
```bash
cd /tmp/smoke && \
python3 -c "import json,io; p='docs/javascripts/config-wizard/wizard-spec.json'; d=json.load(open(p)); d['_sentinel']='domain-edit'; json.dump(d, open(p,'w'))" && \
echo '// domain edit' >> docs/javascripts/config-wizard/generators.js && \
cd /mnt/code/mcp-servers/fastmcp-server-template && \
uv run --no-project --with copier copier copy --trust --defaults --overwrite \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke && \
grep -q '_sentinel' /tmp/smoke/docs/javascripts/config-wizard/wizard-spec.json && echo "SPEC preserved (skip_if_exists OK)" && \
! grep -q 'domain edit' /tmp/smoke/docs/javascripts/config-wizard/generators.js && echo "RUNTIME overwritten (template-owned OK)"
```
Expected: prints both `SPEC preserved (skip_if_exists OK)` and `RUNTIME overwritten (template-owned OK)`.

Note: `copier copy --overwrite` re-applies the template over an existing dir, honoring `_skip_if_exists`, which is the relevant behavior here. (A true `copier update` requires the project to be a git repo with a `.copier-answers.yml`; the `--overwrite` re-render is sufficient to confirm the `_skip_if_exists` vs template-owned split.)

- [ ] **Step 6: Final confirmation (no commit needed — all work committed in prior tasks)**

Run (in template dir): `git status --short && git log --oneline -5`
Expected: clean working tree (all changes committed across Tasks 1–4); the recent commits show the schema, seed meta, schema test, and runtime rewrite.

---

## Self-Review

**1. Spec coverage** (design §1–§7 + migration):

- §1 spec format (`meta`, `dockerVolume`, `dockerPath`, vocabulary) → Task 1 (schema encodes it), Task 2 (seed `meta`), Task 4 (generators implement `dockerVolume`/`dockerPath`). ✅
- §1 "what stays hardcoded" (state volume, FASTMCP_HOME) → Task 4 generators.js `STATE_VOLUME`/`FASTMCP_HOME`. ✅
- §2 runtime files become plain/generic; signature table → Task 4 (generators.js rename + signatures; wizard.js call sites). Verified token-free in Task 5 Step 2. ✅
- §3 seed renders `meta` once → Task 2 Step 1. ✅
- §4 file ownership (copier.yml `_skip_if_exists`) → Task 2 Step 3; verified Task 5 Step 5. ✅
- §5 JSON Schema → Task 1; cross-ref rules not expressible in schema → Task 3 test (`test_*_references_existing_ids`, `test_question_ids_are_unique`, `test_secret_keys_are_declared_vars`). ✅
- §6 tests (smoke generic, schema validation, domain placeholder) → Task 4 (smoke), Task 3 (schema), Task 2 (domain placeholder); `jsonschema` dep → Task 3 Step 1. ✅
- §6 guard-level drift caught → Task 3 `test_schema_rejects_unknown_guard_level`. ✅
- §7 issue scope → documented in the design spec; no code task (noted in this plan's intro that rollout/issue-admin is out of scope). ✅
- Testing strategy (mkdocs --strict, schema self-consistency) → Task 5 Steps 3–4. ✅
- Migration (downstream) → explicitly out of scope for this template PR (stated in intro). ✅

**2. Placeholder scan:** No "TBD"/"add error handling"/"similar to Task N". Every code step shows complete content. The two conditional verification notes (chromium availability in Task 4 Step 4 / Task 5 Step 4) are environment fallbacks, not implementation ambiguity. ✅

**3. Type consistency:** generators.js export signatures in the Task 4 Interfaces block match the function definitions in Step 2 and the call sites in Step 3 (`generateClaudeJson(meta, map)`, `generateSystemd(meta, map)`, `generateDockerRun(spec, answers, map)`, `generateCompose(spec, answers, map)`, `generateDotenv(map)`, `dockerVolumes(spec, answers)`). The browser tests in Step 1 call these exact signatures. Python fixtures (`spec`, `schema`) and helper names (`_minimal_valid_spec`) are consistent within Task 3. ✅
