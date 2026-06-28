# Config-wizard ⇄ env Drift Guards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce bidirectional full coverage between the config-wizard spec and the env surface the server reads (core `ServerConfig` + domain `ProjectConfig`), as one template-owned test plus the seed enrichment that lets the scaffold pass it.

**Architecture:** A rendered, main-lane test reads the shipped `wizard-spec.json`, the core surface via `fastmcp_pvl_core.server_config_env_suffixes()` (pvl-core ≥ 4.2.0), and the domain surface via an AST scan of `ProjectConfig.from_env`. It fails on orphans (a wizard var/emit nothing reads) and on missing coverage (a core/domain setting with no wizard var/emit). The seed is enriched (deployment emits `TRANSPORT`; advanced questions for `HOST`/`PORT`/`BEARER_TOKENS_FILE`/`BEARER_DEFAULT_SUBJECT`/`EVENT_STORE_URL`/`APP_DOMAIN`) so the scaffold satisfies its own guard; `AUTH_MODE` is a documented inference-exception.

**Tech Stack:** Python (pytest, `ast`/`inspect`), copier/Jinja templates, JSON wizard spec.

## Global Constraints

- pvl-core floor: `fastmcp-pvl-core>=4.2.0,<5` (the version exposing `server_config_env_suffixes()`).
- "Covered" = a question `var` **or** a `select` option `emit` key equals `{PREFIX}_{SUFFIX}`. `advancedGroup` is UI-only and never affects coverage.
- Native `FASTMCP_*` vars are allowlisted: exempt from orphan, never required by coverage.
- New wizard `var`s match the schema pattern `^[A-Z][A-Z0-9_]*$`; none of the new ones are secrets (`secretKeys` unchanged); any question gating on `auth` must also gate on `deployment=server` (self-contained `showIf`, enforced by `test_showif_and_guard_gates_cascade`).
- Edits are to template (`.jinja`) / template-owned files; verify by rendering the smoke project with `--vcs-ref=HEAD` and running its gate (commit first — copier reads the git index).
- Render+gate command (run after each task that changes rendered output):
  ```bash
  rm -rf /tmp/smoke && uv run --no-project --with copier copier copy --trust --defaults \
    --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
  cd /tmp/smoke && uv sync --all-extras --all-groups
  uv run ruff check . && uv run ruff format --check . && uv run mypy src/ tests/ && uv run pytest -x -q
  ```

---

### Task 1: Floor bump + orphan guard

**Files:**
- Modify: `pyproject.toml.jinja` (the `fastmcp-pvl-core>=4.0.0,<5` dependency line)
- Create: `tests/test_config_wizard_drift.py.jinja`

**Interfaces:**
- Consumes: `fastmcp_pvl_core.server_config_env_suffixes() -> frozenset[str]`; the shipped `docs/javascripts/config-wizard/wizard-spec.json`; `{{ python_module }}.config.ProjectConfig`.
- Produces: helpers `_spec()`, `_wizard_emitted_vars(spec)`, `_suffix(var)`, `_suffixes_in_source(src)`, `_domain_suffixes()`, `_surface()`, and constant `_COVERED_BY_INFERENCE` used by Task 2/3.

- [ ] **Step 1: Bump the pvl-core floor**

In `pyproject.toml.jinja` change the dependency line:
```toml
    "fastmcp-pvl-core>=4.2.0,<5",
```

- [ ] **Step 2: Write the drift test module with the orphan guard (failing test first)**

Create `tests/test_config_wizard_drift.py.jinja`:
```python
"""Drift guards between the config-wizard spec and the env surface it mirrors.

Two directions, both fail CI:

* Orphan — a wizard ``var`` (or option ``emit`` key) that no read site consumes.
* Coverage — a core (``ServerConfig``) or domain (``ProjectConfig``) env setting
  with no wizard ``var``/``emit``.

Runs in the main lane. On the scaffold the domain surface is empty (every
``ProjectConfig.from_env`` domain read is a commented example), so this reduces
to "the seed covers core"; downstream it checks core + the project's domain.
"""

from __future__ import annotations

import ast
import inspect
import json
import textwrap
from pathlib import Path
from typing import Any

from fastmcp_pvl_core import server_config_env_suffixes

from {{ python_module }}.config import ProjectConfig

_ENV_PREFIX = "{{ env_prefix }}"
_WIZARD_SPEC = (
    Path(__file__).resolve().parent.parent
    / "docs"
    / "javascripts"
    / "config-wizard"
    / "wizard-spec.json"
)

# Core ServerConfig suffixes with no dedicated wizard control by design.
# AUTH_MODE: ServerConfig infers the auth mode from which auth vars are set (the
# ``auth`` select is a no-var routing key — see the Config wizard section of
# CLAUDE.md), so there is no AUTH_MODE control to offer.
_COVERED_BY_INFERENCE = frozenset({"AUTH_MODE"})


def _spec() -> dict[str, Any]:
    return json.loads(_WIZARD_SPEC.read_text(encoding="utf-8"))


def _wizard_emitted_vars(spec: dict[str, Any]) -> set[str]:
    """Every env var the wizard can emit: question ``var``s + option ``emit`` keys."""
    out: set[str] = set()
    for q in spec["questions"]:
        if q.get("var"):
            out.add(q["var"])
        for opt in q.get("options", []):
            out.update((opt.get("emit") or {}).keys())
    return out


def _suffix(var: str) -> str | None:
    """The part after ``{PREFIX}_``, or None if ``var`` is not prefixed."""
    prefix = _ENV_PREFIX + "_"
    return var[len(prefix) :] if var.startswith(prefix) else None


def _suffixes_in_source(src: str) -> set[str]:
    """Literal suffixes read by ``env``/``env_int``/``env_float`` calls in ``src``.

    Only string-literal second positional args are seen; a suffix built from a
    variable, passed by keyword, or read through a non-``env`` helper is
    invisible — keep reads in the ``env(_ENV_PREFIX, "LITERAL")`` form.
    """
    funcs = {"env", "env_int", "env_float"}
    found: set[str] = set()
    for node in ast.walk(ast.parse(textwrap.dedent(src))):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in funcs
            and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant)
            and isinstance(node.args[1].value, str)
        ):
            found.add(node.args[1].value)
    return found


def _domain_suffixes() -> set[str]:
    """Suffixes ``ProjectConfig.from_env`` reads beyond ``ServerConfig``.

    The ``server=ServerConfig.from_env(_ENV_PREFIX)`` call passes no suffix
    literal, so it contributes nothing. Vacuous on the scaffold (domain reads
    are commented examples), live downstream.
    """
    return _suffixes_in_source(inspect.getsource(ProjectConfig.from_env))


def _surface() -> set[str]:
    """The config surface the wizard must COVER: core (ServerConfig) + domain.

    This is the coverage target. The orphan check uses a broader read set (it
    also accepts scaffold-direct reads — see ``_src_text``), because the wizard
    may legitimately offer a var the scaffold reads outside ServerConfig (e.g.
    ``HTTP_PATH`` is read in ``cli.py``).
    """
    return set(server_config_env_suffixes()) | _domain_suffixes()


def _src_text() -> str:
    """Concatenated text of the project's ``src/**/*.py``.

    Used to accept wizard vars read directly in the scaffold (e.g. ``HTTP_PATH``
    in ``cli.py``, ``SERVER_NAME``/``INSTRUCTIONS`` in ``server.py``) that are
    not ``ServerConfig``/``ProjectConfig`` fields. Membership is a substring
    test — it errs toward NOT flagging, which is the safe direction for a guard.
    """
    src = Path(__file__).resolve().parent.parent / "src"
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted(src.rglob("*.py")))


def _orphan_vars(spec: dict[str, Any]) -> list[str]:
    """Wizard vars/emits that resolve to no read site (excluding FASTMCP_* natives)."""
    core_domain = _surface()
    src_text = _src_text()
    out: list[str] = []
    for var in sorted(_wizard_emitted_vars(spec)):
        if var.startswith("FASTMCP_"):
            continue  # native, read by FastMCP / configure_logging_from_env
        suffix = _suffix(var)
        if suffix is None:
            out.append(f"{var} (not {_ENV_PREFIX}_-prefixed and not FASTMCP_*)")
        elif suffix not in core_domain and suffix not in src_text:
            out.append(f"{var} (no read site consumes {suffix})")
    return out


def test_no_orphan_wizard_vars() -> None:
    """Every wizard var/emit resolves to a read site (or is a FASTMCP_* native)."""
    orphans = _orphan_vars(_spec())
    assert not orphans, "wizard offers vars nothing reads: " + "; ".join(orphans)
```

- [ ] **Step 3: Render and run the orphan test — verify it PASSES on the real seed**

Commit first (copier reads the index), then render+gate:
```bash
git add pyproject.toml.jinja tests/test_config_wizard_drift.py.jinja
git commit -m "wip(203): drift test orphan guard + floor bump"
rm -rf /tmp/smoke && uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
cd /tmp/smoke && uv sync --all-extras --all-groups
uv run pytest -q tests/test_config_wizard_drift.py::test_no_orphan_wizard_vars
```
Expected: PASS. Every wizard var is a `ServerConfig` suffix, a `FASTMCP_*` native, or read directly in `src/` (`HTTP_PATH` in `cli.py` — found via `_src_text`). This proves the orphan guard runs and the real seed is clean.

- [ ] **Step 4: Add a synthetic-orphan RED test proving the guard bites**

Append to `tests/test_config_wizard_drift.py.jinja`:
```python
def test_orphan_guard_flags_unread_var() -> None:
    """A wizard var whose suffix no read site consumes is reported."""
    spec: dict[str, Any] = {
        "questions": [{"id": "x", "var": f"{_ENV_PREFIX}_NONSENSE_XYZ"}]
    }
    orphans = _orphan_vars(spec)
    assert any("NONSENSE_XYZ" in o for o in orphans)
```

- [ ] **Step 5: Render and run both orphan tests**

```bash
cd /mnt/code/mcp-servers/fastmcp-server-template
git add tests/test_config_wizard_drift.py.jinja && git commit -m "wip(203): orphan guard RED proof"
rm -rf /tmp/smoke && uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
cd /tmp/smoke && uv sync --all-extras --all-groups
uv run pytest -q tests/test_config_wizard_drift.py -k orphan
```
Expected: both PASS.

---

### Task 2: Domain AST-scan unit test

**Files:**
- Modify: `tests/test_config_wizard_drift.py.jinja`

**Interfaces:**
- Consumes: `_suffixes_in_source(src)` from Task 1.
- Produces: confidence that domain enumeration ignores the `server=` line and picks literal `env*` reads.

- [ ] **Step 1: Write the domain-scan unit test**

Append to `tests/test_config_wizard_drift.py.jinja`:
```python
def test_domain_scan_extracts_literal_env_reads() -> None:
    """The domain scan picks literal env*-read suffixes and ignores the rest."""
    src = textwrap.dedent(
        '''
        @classmethod
        def from_env(cls):
            other = some_var
            return cls(
                server=ServerConfig.from_env(_ENV_PREFIX),
                vault_path=env(_ENV_PREFIX, "VAULT_PATH", "/data/vault"),
                max_n=env_int(_ENV_PREFIX, "MAX_N", 5),
                skip=env(_ENV_PREFIX, other),
            )
        '''
    )
    assert _suffixes_in_source(src) == {"VAULT_PATH", "MAX_N"}
```

- [ ] **Step 2: Render and run it**

```bash
cd /mnt/code/mcp-servers/fastmcp-server-template
git add tests/test_config_wizard_drift.py.jinja && git commit -m "wip(203): domain-scan unit test"
rm -rf /tmp/smoke && uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
cd /tmp/smoke && uv sync --all-extras --all-groups
uv run pytest -q tests/test_config_wizard_drift.py::test_domain_scan_extracts_literal_env_reads
```
Expected: PASS — `VAULT_PATH` + `MAX_N` extracted; the `server=` line and the non-literal `env(_ENV_PREFIX, other)` ignored.

---

### Task 3: Coverage guard + seed enrichment

**Files:**
- Modify: `tests/test_config_wizard_drift.py.jinja`
- Modify: `docs/javascripts/config-wizard/wizard-spec.json.jinja`

**Interfaces:**
- Consumes: `_surface()`, `_wizard_emitted_vars()`, `_suffix()`, `_COVERED_BY_INFERENCE` from Task 1.
- Produces: the coverage guard (the second drift direction) + a fully-core-covered seed.

- [ ] **Step 1: Write the coverage test (RED on the current seed)**

Append to `tests/test_config_wizard_drift.py.jinja`:
```python
def test_wizard_covers_full_env_surface() -> None:
    """Every core/domain setting is covered by a wizard var/emit (advanced ok).

    Hiding a setting is done with ``advancedGroup``, never by omission. A
    setting with no dedicated control by design goes in ``_COVERED_BY_INFERENCE``.
    """
    emitted_suffixes = {
        s
        for v in _wizard_emitted_vars(_spec())
        if (s := _suffix(v)) is not None
    }
    missing = sorted(
        s
        for s in _surface()
        if s not in emitted_suffixes and s not in _COVERED_BY_INFERENCE
    )
    assert not missing, (
        "env settings the server reads but the wizard does not offer "
        "(add a question/emit, or _COVERED_BY_INFERENCE if inferred by design): "
        + ", ".join(missing)
    )
```

- [ ] **Step 2: Render and run it — verify it FAILS (un-enriched seed)**

```bash
cd /mnt/code/mcp-servers/fastmcp-server-template
git add tests/test_config_wizard_drift.py.jinja && git commit -m "wip(203): coverage guard (RED pre-enrichment)"
rm -rf /tmp/smoke && uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
cd /tmp/smoke && uv sync --all-extras --all-groups
uv run pytest -q tests/test_config_wizard_drift.py::test_wizard_covers_full_env_surface
```
Expected: FAIL, listing the uncovered core suffixes: `APP_DOMAIN, BEARER_DEFAULT_SUBJECT, BEARER_TOKENS_FILE, EVENT_STORE_URL, HOST, PORT, TRANSPORT` (and **not** `AUTH_MODE`, which the inference set excuses).

- [ ] **Step 3: Enrich the seed — deployment emits TRANSPORT**

In `docs/javascripts/config-wizard/wizard-spec.json.jinja`, give the `deployment` select's options an `emit`:
```json
      "options": [
        { "value": "local", "label": "Local (Claude Desktop / Claude Code, stdio)", "emit": { "{{ env_prefix }}_TRANSPORT": "stdio" } },
        { "value": "server", "label": "Server (HTTP — Docker / Compose / systemd)", "emit": { "{{ env_prefix }}_TRANSPORT": "http" } }
      ]
```

- [ ] **Step 4: Enrich the seed — six advanced questions**

In `docs/javascripts/config-wizard/wizard-spec.json.jinja`, add these questions to the `questions` array (place the Server-group ones near `http_path`, the Auth ones near the OIDC block, Persistence near `kv_store_url`):
```json
    {
      "id": "host",
      "label": "Bind host",
      "help": "Interface the HTTP server binds to. Default 127.0.0.1.",
      "type": "text",
      "var": "{{ env_prefix }}_HOST",
      "showIf": { "deployment": ["server"] },
      "advancedGroup": "Server"
    },
    {
      "id": "port",
      "label": "Port",
      "help": "TCP port for the HTTP server. Default 8000.",
      "type": "text",
      "var": "{{ env_prefix }}_PORT",
      "showIf": { "deployment": ["server"] },
      "advancedGroup": "Server"
    },
    {
      "id": "bearer_tokens_file",
      "label": "Bearer tokens file (TOML)",
      "help": "Path to a TOML file of per-token subjects; overrides the single BEARER_TOKEN.",
      "type": "text",
      "var": "{{ env_prefix }}_BEARER_TOKENS_FILE",
      "showIf": { "deployment": ["server"], "auth": ["bearer", "both"] },
      "advancedGroup": "Auth"
    },
    {
      "id": "bearer_default_subject",
      "label": "Bearer default subject",
      "help": "Subject assigned to the single bearer token. Default bearer-anon.",
      "type": "text",
      "var": "{{ env_prefix }}_BEARER_DEFAULT_SUBJECT",
      "showIf": { "deployment": ["server"], "auth": ["bearer", "both"] },
      "advancedGroup": "Auth"
    },
    {
      "id": "event_store_url",
      "label": "Event store URL (HTTP resumability)",
      "help": "Legacy override; prefer KV_STORE_URL. See fastmcp-pvl-core.",
      "type": "text",
      "var": "{{ env_prefix }}_EVENT_STORE_URL",
      "showIf": { "deployment": ["server"] },
      "advancedGroup": "Persistence"
    },
    {
      "id": "app_domain",
      "label": "MCP Apps domain",
      "help": "Public domain that serves MCP Apps UI resources.",
      "type": "text",
      "var": "{{ env_prefix }}_APP_DOMAIN",
      "showIf": { "deployment": ["server"] },
      "advancedGroup": "MCP Apps"
    }
```

- [ ] **Step 5: Render and run the full wizard test suite — verify GREEN**

```bash
git add docs/javascripts/config-wizard/wizard-spec.json.jinja
git commit -m "wip(203): enrich seed to full core coverage"
rm -rf /tmp/smoke && uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
cd /tmp/smoke && uv sync --all-extras --all-groups
uv run pytest -q tests/test_config_wizard_drift.py tests/test_config_wizard_spec_schema.py
```
Expected: all PASS. The coverage test is green (TRANSPORT via emit; the six advanced questions; `AUTH_MODE` excused), and the schema/cascade tests still pass (the new auth-gated questions carry `deployment`).

- [ ] **Step 6: Run the JS-against-built-site smoke tests (the browser lane)**

The new `emit` and questions render into the built site; verify the wizard JS still passes:
```bash
cd /tmp/smoke && uv run mkdocs build >/dev/null && uv run playwright install chromium >/dev/null 2>&1
uv run pytest -q -m browser tests/test_config_wizard_smoke.py
```
Expected: PASS (framework tests assert universal invariants; emit/questions don't break them).

---

### Task 4: Squash, CLAUDE.md note, full gate, PR

**Files:**
- Modify: `CLAUDE.md.jinja` (the "Config wizard" subsection)

**Interfaces:** none (documentation + integration).

- [ ] **Step 1: Document the enforced coverage in CLAUDE.md.jinja**

In the "Config wizard" subsection of `CLAUDE.md.jinja`, after the "Cover the `ServerConfig` surface" rule, add:
```markdown
- **Coverage is CI-enforced.** `tests/test_config_wizard_drift.py` fails if the wizard offers a var no read site consumes (orphan) or omits a setting the server reads — both `ServerConfig` (via `server_config_env_suffixes()`) and your `ProjectConfig.from_env`. Offer every setting; hide niche ones with `advancedGroup`, never by omission. The only escape is `_COVERED_BY_INFERENCE` in that test, for settings with no control by design (e.g. `AUTH_MODE`, inferred from which auth vars are set).
```

- [ ] **Step 2: Squash the wip commits into one**

```bash
cd /mnt/code/mcp-servers/fastmcp-server-template
git add CLAUDE.md.jinja
git commit -m "wip(203): CLAUDE.md coverage note"
BASE=$(git merge-base HEAD origin/main)
git reset --soft "$BASE"
git commit -m "$(printf 'feat(scaffold): CI-enforced config-wizard env-surface coverage\n\nThe wizard had no guard against drifting from the env surface the server\nreads. tests/test_config_wizard_drift.py now fails on orphans (a wizard\nvar/emit nothing reads) and on missing coverage (a ServerConfig or\nProjectConfig setting with no wizard var/emit). It uses pvl-core 4.2.0''s\nserver_config_env_suffixes() for core and an AST scan of\nProjectConfig.from_env for domain, so it doubles as a scaffold-core guard\n(template CI) and a downstream wizard-env guard (rendered).\n\nThe seed is enriched to full core coverage: deployment emits TRANSPORT;\nadvanced questions for HOST, PORT, BEARER_TOKENS_FILE,\nBEARER_DEFAULT_SUBJECT, EVENT_STORE_URL, APP_DOMAIN. AUTH_MODE is a\ndocumented inference-exception. Floor bumped to fastmcp-pvl-core>=4.2.0.\n\nCloses #203\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```
(Keep the spec + this plan commit if present, or fold them in — confirm `git log --oneline origin/main..HEAD` shows one or two clean commits.)

- [ ] **Step 3: Full render + gate (all lanes that don't need external infra)**

```bash
rm -rf /tmp/smoke && uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
cd /tmp/smoke && uv sync --all-extras --all-groups
uv run ruff check . && uv run ruff format --check . && uv run mypy src/ tests/
uv run pytest -x -q && uv run mkdocs build --strict && vale docs/ || true
```
Expected: ruff/format/mypy/pytest/mkdocs all green; `vale docs/` introduces no new errors in files this PR touched (CLAUDE.md.jinja prose — avoid spaced em-dashes).

- [ ] **Step 4: Preflight circus, then PR**

Run the `preflight-circus` skill against `BASE..HEAD`; resolve any ≥80 finding; then:
```bash
git push -u origin feat/203-wizard-env-drift-guards
gh pr create --base main --head feat/203-wizard-env-drift-guards --title "feat(scaffold): CI-enforced config-wizard env-surface coverage" --body "<summary + Closes #203 + agent-attribution signature>"
```

## Notes for the implementer

- **Why a separate test file** (not `test_config_wizard_spec_schema.py`): that file validates the spec against the JSON Schema and cross-refs; drift-vs-the-env-surface is a different concern (needs pvl-core + `ProjectConfig`), so it lives on its own.
- **The domain scan is vacuous on the scaffold** because every `ProjectConfig.from_env` domain field is a commented example inside the `CONFIG-FROM-ENV` sentinels. That is intentional: the guard is inert until a downstream project adds a real domain read, at which point it requires a matching wizard question.
- **Do not** add `AUTH_MODE` as a question — it would reverse the #205 decision to make `auth` a no-`var` inferred routing key. It stays in `_COVERED_BY_INFERENCE`.
