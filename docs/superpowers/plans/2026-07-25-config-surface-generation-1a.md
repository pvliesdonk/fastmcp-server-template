# Config-surface generation 1a: generator + whole-file artifacts

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate four whole-file config artifacts from `fastmcp_pvl_core.server_config_surface()` plus a declarative presentation config, and delete the hand-maintained Jinja sources and the drift test they needed.

**Architecture:** A template-owned Python script, `scripts/gen_config_surface.py`, ships **byte-identical** to every project (no `.jinja` suffix) and discovers everything it needs at runtime — the module name, the copier answers, and the core library's field surface. It merges four provenance sources into one ordered var list, then emits whole files as directed by `config-presentation.yml`. `--check` verifies the emitted files are current without writing, for CI.

**Tech Stack:** Python 3.11+ (the template's floor), stdlib + `fastmcp-pvl-core>=4.5.0` + `PyYAML` (already a docs dependency), copier 9.x, pytest.

**Upstream spec:** `docs/superpowers/specs/2026-07-25-config-generation-and-ownership-model-design.md`, Stage 1. This is plan **1a of three**: 1b adds region-splicing into authored files, 1c reclassifies `.pre-commit-config.yaml`.

**Closes:** #217, #254 (wizard half), #257, #260

## Global Constraints

- **The generator ships byte-identical.** No `.jinja` suffix, no Jinja tags in its body. It resolves the module name, `env_prefix`, `project_name`, `human_name`, `docker_registry`, and every boolean answer from `.copier-answers.yml` at runtime. This follows the existing `scripts/{% if include_mcp_apps_scaffold %}vendor_spa.py{% endif %}`, whose docstring states the same design: *"ships byte-identical to every project, so it discovers `src/<module>/static/app.src.html` at runtime rather than hard-coding a package name."*
- **`config-presentation.yml` also ships byte-identical.** Use the literal token `{PREFIX}` where the env prefix belongs; the generator substitutes it. No Jinja.
- **`_tasks` must never create a venv or write into the project tree beyond the generated artifacts.** `.github/workflows/template-ci.yml` renders the template twice and runs `diff -r /tmp/smoke /tmp/smoke2`, deliberately doing the second render before `uv sync` runs. A `.venv`, `uv.lock`, or `__pycache__` created during `_tasks` breaks that diff for every future PR. This is why the generator re-execs under `uv run --no-project` rather than relying on a synced project.
- **Generated output must be byte-deterministic.** Two renders must produce identical files or the `diff -r` check fails. Order every emitted list by `(provenance rank, declaration index)`; never iterate a `set` or `frozenset` to produce output. `server_config_surface()` returns a declaration-ordered `tuple` for exactly this reason — use it, not `server_config_env_suffixes()`, which is a `frozenset`.
- **Generated output must be render-hygiene clean.** `scripts/check_render_hygiene.py` runs over the render in template-CI and fails on trailing whitespace or a missing/extra trailing newline. Emit exactly one trailing newline and no trailing spaces on any line.
- **The generator is linted with the downstream ruleset, not the template's.** `template-ci.yml` runs `ruff check --select E,W,F,I,B,C4,UP,ARG,SIM,TC,PTH,RUF --ignore E501 --line-length 88` over the named scripts. `PTH` means use `pathlib`, never `os.path`; `ARG` means no unused arguments; `TC` means import-only-for-typing goes in a `TYPE_CHECKING` block. Write to that ruleset from the start rather than fixing it up at the end.
- **Core floor is `>=4.5.0`.** `server_config_surface()` and `ConfigField` do not exist before it.
- **`inferred` means "no wizard control", not "undocumented."** A field with `inferred=True` is omitted from the wizard spec but **must still appear** in `.env.example` and `packaging/env.example`. Getting this backwards silently drops `AUTH_MODE` from every downstream's env reference. See the spec's Stage 0 note.
- **Never restate a scalar default in emitted prose** when the value is already in the rendered default column; the help text from core already follows this rule.
- **Local gate:** render, then `python3 scripts/check_render_hygiene.py /tmp/smoke`, then inside the render `uv sync --all-extras --all-groups && uv run ruff check . && uv run ruff format --check . && uv run mypy src/ tests/ && uv run pytest -x -q`. Docs-touching changes also need `uv run mkdocs build --strict`.
- **Template repo edits require a commit before rendering.** Copier reads from the git index; use `--vcs-ref=HEAD` and commit (or amend) before each render. Rendering from the working tree is not supported.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `scripts/gen_config_surface.py` | merge four provenances → emit artifacts; `--check` | **Create** (byte-identical, no `.jinja`) |
| `config-presentation.yml` | non-core vars, section layout, destinations, wizard routing | **Create** (byte-identical, no `.jinja`) |
| `config-presentation.domain.yml` | the project's own questions and sections | **Create** (seeded) |
| `scripts/tests/test_gen_config_surface.py` | template-repo unit tests for the generator | **Create** |
| `copier.yml` | `_tasks` entry; ownership reclassification | Modify |
| `pyproject.toml.jinja` | core floor `>=4.3.0` → `>=4.5.0` | Modify |
| `.github/workflows/ci.yml.jinja` | add the `--check` step | Modify |
| `docs/guides/config-migration.md.jinja` | downstream migration guide | **Create** |
| `.env.example.jinja` | replaced by generated output | **Delete** |
| `packaging/env.example.jinja` | replaced by generated output | **Delete** |
| `examples/bearer-auth.env.jinja`, `examples/oidc.env.jinja` | replaced by generated output | **Delete** |
| `docs/javascripts/config-wizard/wizard-spec.json.jinja` | replaced by generated output | **Delete** |
| `tests/test_config_wizard_drift.py.jinja` | obsolete — drift is now impossible | **Delete** |

The generator lives in one file because its stages are a pipeline with one data shape flowing through; splitting loader/merge/emit across modules would spread one concern over three files. `scripts/tests/` is already `_exclude`d from renders and holds the template's own unit tests, so the generator's tests go there.

---

## Task 1: Presentation config, provenance merge, and the self-bootstrap

**Files:**
- Create: `scripts/gen_config_surface.py`
- Create: `config-presentation.yml`
- Create: `scripts/tests/test_gen_config_surface.py`

**Interfaces produced** (later tasks depend on these exact names):

```python
@dataclass(frozen=True)
class Var:
    name: str            # full env var name, e.g. "SCHOLAR_MCP_BASE_URL" or "FASTMCP_LOG_LEVEL"
    suffix: str | None   # part after "{PREFIX}_", or None for unprefixed vars
    provenance: str      # "core" | "template" | "external" | "domain"
    type_name: str
    default: object
    help: str
    tags: tuple[str, ...]
    inferred: bool
    wizard: Mapping[str, object]

def load_answers(project_root: Path) -> dict[str, object]: ...
def load_presentation(project_root: Path, env_prefix: str) -> dict[str, Any]: ...
def collect_vars(project_root: Path, answers: Mapping[str, object]) -> tuple[Var, ...]: ...
def ensure_core_available(project_root: Path) -> None: ...
def _core_floor(project_root: Path) -> str: ...   # private, but tested directly
```

Note the asymmetry in Task 3: `render_env_file` takes a single file's spec, while `render_wizard_spec` takes the whole presentation mapping. That is deliberate — the wizard needs `wizard_routing` and `wizard_guards` from the top level, which no single file spec carries.

`collect_vars` returns vars ordered by provenance rank — `core`, then `template`, then `external`, then `domain` — and within each, declaration order. `core` vars come from `server_config_surface()`; the rest come from the presentation configs.

- [ ] **Step 1: Write `config-presentation.yml`**

Ships byte-identical. `{PREFIX}` is substituted at runtime. The `vars` list declares every non-core var, with the same metadata shape core provides. `when_answer` gates a section or var on a copier boolean.

```yaml
# Presentation layer for generated config artifacts.  Template-owned.
#
# Ships byte-identical to every project: `{PREFIX}` is replaced with the
# project's env_prefix at generation time.  Core `ServerConfig` vars are NOT
# listed here — they come from fastmcp_pvl_core.server_config_surface(), which
# owns their help text and tags.  This file declares only the vars core does
# not know about, plus how every var is laid out in each artifact.

# Vars read outside ServerConfig.  Same metadata shape core uses.
vars:
  - name: "{PREFIX}_SERVER_NAME"
    provenance: template
    type_name: "str"
    default: null
    help: "Rename this server instance; defaults to the project name."
    tags: [server]
    wizard: {group: Server, when: server}

  - name: "{PREFIX}_INSTRUCTIONS"
    provenance: template
    type_name: "str"
    default: null
    help: "Replaces the default MCP instructions text sent to clients."
    tags: [server]
    wizard: {group: Server, when: server}

  - name: "{PREFIX}_HTTP_PATH"
    provenance: template
    type_name: "str"
    default: "/mcp"
    help: "Mount path for the MCP endpoint."
    tags: [server]
    wizard: {group: Server, when: server}

  - name: "{PREFIX}_DEBUG_PORT"
    provenance: template
    type_name: "int"
    default: 5678
    help: "debugpy listen port; the image must be built with --build-arg DEBUG=true."
    tags: [debug]
    wizard: {}

  - name: "{PREFIX}_DEBUG_WAIT"
    provenance: template
    type_name: "bool"
    default: false
    help: "Block startup until a debugger attaches."
    tags: [debug]
    wizard: {}

  - name: "FASTMCP_LOG_LEVEL"
    provenance: external
    type_name: "str"
    default: "INFO"
    help: "Log level for FastMCP internals and app loggers (DEBUG / INFO / WARNING / ERROR). The -v CLI flag overrides to DEBUG."
    tags: [observability, readme]
    wizard: {group: Logging}

  - name: "FASTMCP_ENABLE_RICH_LOGGING"
    provenance: external
    type_name: "bool"
    default: true
    help: "Set false for plain or structured JSON log output."
    tags: [observability, readme]
    wizard: {group: Logging}

  - name: "{PREFIX}_ACL_PATH"
    provenance: template
    when_answer: enable_authorization
    type_name: "Path"
    default: null
    help: "Subject-to-scope ACL file (TOML), for bearer and any auth mode."
    tags: [authz]
    wizard: {}

  - name: "{PREFIX}_AUTHZ_CLAIM"
    provenance: template
    when_answer: enable_authorization
    type_name: "str"
    default: null
    help: "OIDC claim to read scopes from, e.g. groups. Identity mapping when IdP group names already match scope names."
    tags: [authz]
    wizard: {}

  - name: "{PREFIX}_AUTHZ_GRANTS"
    provenance: template
    when_answer: enable_authorization
    type_name: "str"
    default: null
    help: "Inline-JSON translation map for when group names differ from scope names."
    tags: [authz]
    wizard: {}

# Wizard routing questions that emit a var rather than mapping 1:1 to one.
wizard_routing:
  - id: deployment
    label: "Where will the server run?"
    help: "Local stdio for Claude Desktop/Code, or an HTTP server for Docker/systemd."
    type: select
    options:
      - {value: local, label: "Local (Claude Desktop / Claude Code, stdio)", emit: {"{PREFIX}_TRANSPORT": stdio}}
      - {value: server, label: "Server (HTTP — Docker / Compose / systemd)", emit: {"{PREFIX}_TRANSPORT": http}}
  - id: auth
    label: "Authentication"
    type: select
    when: server
    options:
      - {value: none, label: "None"}
      - {value: bearer, label: "Bearer token"}
      - {value: oidc, label: "OIDC"}
      - {value: both, label: "Bearer + OIDC"}

wizard_guards:
  - when: {deployment: [server], auth: [oidc, both]}
    level: warning
    message: "OIDC needs BASE_URL set. Leaving OIDC_JWT_SIGNING_KEY unset derives the key from the client secret, so rotating that secret invalidates every issued token."

# Whole-file artifacts.  `tags: []` selects every var.
files:
  .env.example:
    kind: env
    header: "{HUMAN_NAME} environment variables (copy to .env and fill in)."
    commented: true
    sections:
      - {title: Server, tags: [server]}
      - {title: Authentication, tags: [auth]}
      - {title: Persistence, tags: [persistence]}
      - {title: "MCP Apps", tags: [apps]}
      - {title: Authorization, tags: [authz], when_answer: enable_authorization}
      - {title: Logging, tags: [observability]}
      - {title: "Remote debugger (development only)", tags: [debug]}
      - {title: Domain, tags: [domain], note: "Populated from your ProjectConfig CONFIG-FIELDS block."}

  packaging/env.example:
    kind: env
    header: |
      {HUMAN_NAME} environment configuration

      Installed to /etc/{PROJECT_NAME}/env.example.
      Copy to /etc/{PROJECT_NAME}/env and edit for your deployment; the systemd
      unit (/usr/lib/systemd/system/{PROJECT_NAME}.service) sources
      /etc/{PROJECT_NAME}/env via EnvironmentFile=.
    commented: false
    sections:
      - {title: Logging, tags: [observability]}
      - {title: Domain, tags: [domain], note: "All domain vars use the {PREFIX}_ prefix."}

  examples/bearer-auth.env:
    kind: env
    header: "Bearer token authentication example. Generate a token: openssl rand -hex 32"
    commented: false
    sections:
      - {title: null, tags: [bearer]}
      - {title: null, tags: [domain]}

  examples/oidc.env:
    kind: env
    header: "OIDC authentication example. See docs/guides/authentication.md for setup."
    commented: false
    sections:
      - {title: null, tags: [oidc]}
      - {title: null, tags: [domain]}

  docs/javascripts/config-wizard/wizard-spec.json:
    kind: wizard
```

- [ ] **Step 2: Write the failing tests**

Create `scripts/tests/test_gen_config_surface.py`. These tests define the contract; the implementation follows.

```python
"""Unit tests for the config-surface generator (template-repo only)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import gen_config_surface as g  # noqa: E402


@pytest.fixture
def fake_project(tmp_path):
    """A minimal rendered-project layout the generator can read."""
    (tmp_path / ".copier-answers.yml").write_text(
        "_commit: v2.11.2\n"
        "_src_path: gh:pvliesdonk/fastmcp-server-template\n"
        "project_name: demo-mcp\n"
        "python_module: demo_mcp\n"
        "env_prefix: DEMO_MCP\n"
        "human_name: Demo MCP\n"
        "docker_registry: ghcr.io/demo\n"
        "enable_authorization: false\n",
        encoding="utf-8",
    )
    src = tmp_path / "src" / "demo_mcp"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("", encoding="utf-8")
    return tmp_path


class TestLoadAnswers:
    def test_reads_the_copier_answers_file(self, fake_project):
        answers = g.load_answers(fake_project)
        assert answers["env_prefix"] == "DEMO_MCP"
        assert answers["python_module"] == "demo_mcp"

    def test_missing_answers_file_fails_with_a_clear_message(self, tmp_path):
        with pytest.raises(SystemExit, match="copier-answers"):
            g.load_answers(tmp_path)


class TestLoadPresentation:
    def test_substitutes_the_prefix_token(self, fake_project):
        pres = g.load_presentation(Path.cwd(), "DEMO_MCP")
        names = [v["name"] for v in pres["vars"]]
        assert "DEMO_MCP_HTTP_PATH" in names
        assert not any("{PREFIX}" in n for n in names)

    def test_unprefixed_external_vars_are_left_alone(self, fake_project):
        pres = g.load_presentation(Path.cwd(), "DEMO_MCP")
        names = [v["name"] for v in pres["vars"]]
        assert "FASTMCP_LOG_LEVEL" in names


class TestCollectVars:
    def test_includes_every_core_field(self, fake_project):
        from fastmcp_pvl_core import server_config_surface

        collected = {v.suffix for v in g.collect_vars(fake_project, g.load_answers(fake_project))}
        assert {f.suffix for f in server_config_surface()} <= collected

    def test_provenance_order_is_core_then_template_then_external(self, fake_project):
        vars_ = g.collect_vars(fake_project, g.load_answers(fake_project))
        ranks = [("core", "template", "external", "domain").index(v.provenance) for v in vars_]
        assert ranks == sorted(ranks)

    def test_core_ordering_matches_declaration_order(self, fake_project):
        from fastmcp_pvl_core import server_config_surface

        core = [v.suffix for v in g.collect_vars(fake_project, g.load_answers(fake_project))
                if v.provenance == "core"]
        assert core == [f.suffix for f in server_config_surface()]

    def test_authz_vars_absent_when_the_answer_is_false(self, fake_project):
        names = {v.name for v in g.collect_vars(fake_project, g.load_answers(fake_project))}
        assert "DEMO_MCP_ACL_PATH" not in names

    def test_authz_vars_present_when_the_answer_is_true(self, fake_project):
        p = fake_project / ".copier-answers.yml"
        p.write_text(p.read_text(encoding="utf-8").replace(
            "enable_authorization: false", "enable_authorization: true"), encoding="utf-8")
        names = {v.name for v in g.collect_vars(fake_project, g.load_answers(fake_project))}
        assert "DEMO_MCP_ACL_PATH" in names

    def test_prefixed_names_use_the_projects_prefix(self, fake_project):
        names = {v.name for v in g.collect_vars(fake_project, g.load_answers(fake_project))}
        assert "DEMO_MCP_BASE_URL" in names
        assert not any(n.startswith("SCHOLAR") for n in names)

    def test_every_var_carries_at_least_one_tag(self, fake_project):
        untagged = [v.name for v in g.collect_vars(fake_project, g.load_answers(fake_project))
                    if not v.tags]
        assert untagged == []

    def test_auth_mode_is_collected_despite_being_inferred(self, fake_project):
        """inferred means no wizard control, NOT undocumented — it must still be emitted."""
        vars_ = g.collect_vars(fake_project, g.load_answers(fake_project))
        auth_mode = next(v for v in vars_ if v.suffix == "AUTH_MODE")
        assert auth_mode.inferred is True

    def test_collection_is_deterministic_under_hash_randomisation(self, fake_project):
        """Two runs in separate processes must agree, or the render-twice CI diff fails."""
        import os
        import subprocess

        prog = (
            "import sys; sys.path.insert(0, %r);"
            "import gen_config_surface as g;"
            "a = g.load_answers(%r);"
            "print(','.join(v.name for v in g.collect_vars(%r, a)))"
            % (str(Path(g.__file__).parent), str(fake_project), str(fake_project))
        )
        outs = set()
        for seed in ("1", "2", "3"):
            r = subprocess.run([sys.executable, "-c", prog], capture_output=True,
                               text=True, check=True,
                               env={**os.environ, "PYTHONHASHSEED": seed})
            outs.add(r.stdout.strip())
        assert len(outs) == 1


class TestEnsureCoreAvailable:
    def test_parses_the_core_floor_from_pyproject(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            'dependencies = [\n  "fastmcp-pvl-core>=4.5.0,<5",\n]\n', encoding="utf-8")
        assert g._core_floor(tmp_path) == "4.5.0"

    def test_missing_floor_fails_loudly(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("dependencies = []\n", encoding="utf-8")
        with pytest.raises(SystemExit, match="fastmcp-pvl-core"):
            g._core_floor(tmp_path)
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run --no-project --with pyyaml --with 'fastmcp-pvl-core>=4.5.0' --with pytest pytest scripts/tests/test_gen_config_surface.py -v`

Expected: collection error — `ModuleNotFoundError: No module named 'gen_config_surface'`.

- [ ] **Step 4: Implement `scripts/gen_config_surface.py` up to `collect_vars`**

Write the minimum to pass Step 2's tests. Required behaviours, all pinned by those tests:

- Module docstring stating it ships byte-identical and discovers module/answers at runtime, mirroring `vendor_spa.py`'s framing.
- `_core_floor(project_root)` — parse `pyproject.toml` for `fastmcp-pvl-core>=X`; `SystemExit` with a message naming `fastmcp-pvl-core` if absent.
- `ensure_core_available(project_root)` — `import fastmcp_pvl_core`; on `ImportError`, re-exec via `os.execvp` under
  `uv run --no-project --with "fastmcp-pvl-core==<floor>" --with pyyaml python <this script> <original argv>`,
  guarded by an env var (e.g. `_GEN_CONFIG_BOOTSTRAPPED=1`) so a second failure raises instead of looping forever.
- `load_answers` / `load_presentation` / `collect_vars` per the interfaces above.
- `--check` accepted by the arg parser but not yet implemented (Task 4 wires it; Tasks 2–3 implement per-artifact comparison).

- [ ] **Step 5: Run the tests to verify they pass**

Run the Step 3 command. Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add scripts/gen_config_surface.py config-presentation.yml scripts/tests/test_gen_config_surface.py
git commit -m "feat(config): presentation config + provenance merge for generated artifacts

Adds the generator's front half: reads .copier-answers.yml, loads the
byte-identical presentation config, and merges four provenance sources
(core / template / external / domain) into one declaration-ordered var
list. Core vars come from fastmcp_pvl_core.server_config_surface(), so
their help text and tags have a single owner.

Ordering is contractual: template-ci renders twice and diffs, so emitted
output must be byte-identical across processes. A test pins that under
three PYTHONHASHSEED values.

The generator self-bootstraps under \`uv run --no-project\` when the core
library is not importable, because copier _tasks runs before any venv
exists and must not create one.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01As25PstUQeTR47J5SP5g7P"
```

---

## Task 2: Emit `.env.example` and `packaging/env.example`

**Files:**
- Modify: `scripts/gen_config_surface.py`
- Modify: `scripts/tests/test_gen_config_surface.py`
- Create: `config-presentation.domain.yml`

**Interfaces consumed:** `Var`, `collect_vars`, `load_presentation`, `load_answers` from Task 1.

**Interfaces produced:**

```python
def render_env_file(spec: Mapping[str, Any], vars_: Sequence[Var],
                    answers: Mapping[str, object]) -> str: ...
def write_artifacts(project_root: Path, *, check: bool) -> list[str]: ...
```

`render_env_file` returns the file's full text. `write_artifacts` writes each artifact (or, with `check=True`, compares without writing) and returns the list of paths that are stale or were written.

- [ ] **Step 1: Write `config-presentation.domain.yml`**

Seeded — downstream owns it. Ships with an empty `vars` list and a comment explaining the contract.

```yaml
# Domain presentation layer — YOURS to edit.  Preserved across copier update.
#
# Domain env vars are discovered automatically from your ProjectConfig's
# CONFIG-FIELDS block, using each field's `metadata={"help": ..., "tags": ...}`.
# Declare a var here only when it is read somewhere the scan cannot see it —
# for example a deprecated alias, or a var read outside ProjectConfig.from_env.
#
# Same shape as the template-owned config-presentation.yml.  `{PREFIX}` is
# substituted with your env_prefix.
vars: []

# Extra wizard questions specific to this project.
wizard_routing: []

# Extra wizard guards specific to this project.
wizard_guards: []
```

- [ ] **Step 2: Write the failing tests**

Append to `scripts/tests/test_gen_config_surface.py`:

```python
class TestRenderEnvFile:
    def _env_text(self, fake_project, path=".env.example"):
        answers = g.load_answers(fake_project)
        pres = g.load_presentation(Path.cwd(), str(answers["env_prefix"]))
        vars_ = g.collect_vars(fake_project, answers)
        return g.render_env_file(pres["files"][path], vars_, answers)

    def test_includes_all_eighteen_core_vars(self, fake_project):
        """The hand-written .env.example was missing six of them."""
        text = self._env_text(fake_project)
        for suffix in ("APP_DOMAIN", "AUTH_MODE", "BEARER_DEFAULT_SUBJECT",
                       "EVENT_STORE_URL", "KV_STORE_URL", "OIDC_VERIFY_ACCESS_TOKEN"):
            assert f"DEMO_MCP_{suffix}" in text

    def test_env_example_lines_are_commented_out(self, fake_project):
        text = self._env_text(fake_project)
        for line in text.splitlines():
            if "DEMO_MCP_" in line:
                assert line.lstrip().startswith("#")

    def test_packaging_env_lines_are_not_commented(self, fake_project):
        text = self._env_text(fake_project, "packaging/env.example")
        assert any(line.startswith("FASTMCP_LOG_LEVEL=") for line in text.splitlines())

    def test_section_titles_appear_in_declared_order(self, fake_project):
        text = self._env_text(fake_project)
        positions = [text.index(t) for t in ("--- Server ---", "--- Authentication ---",
                                             "--- Logging ---")]
        assert positions == sorted(positions)

    def test_authz_section_absent_when_answer_false(self, fake_project):
        assert "Authorization" not in self._env_text(fake_project)

    def test_help_text_appears_as_a_comment(self, fake_project):
        text = self._env_text(fake_project)
        assert "Interface the HTTP server binds to." in text

    def test_render_hygiene_no_trailing_whitespace_single_final_newline(self, fake_project):
        text = self._env_text(fake_project)
        assert not any(line != line.rstrip() for line in text.splitlines())
        assert text.endswith("\n") and not text.endswith("\n\n")

    def test_output_is_stable_across_calls(self, fake_project):
        assert self._env_text(fake_project) == self._env_text(fake_project)


class TestWriteArtifacts:
    def test_writes_then_reports_clean(self, fake_project):
        g.write_artifacts(fake_project, check=False)
        assert (fake_project / ".env.example").exists()
        assert g.write_artifacts(fake_project, check=True) == []

    def test_check_reports_a_stale_file_without_writing(self, fake_project):
        g.write_artifacts(fake_project, check=False)
        target = fake_project / ".env.example"
        target.write_text("tampered\n", encoding="utf-8")
        assert ".env.example" in g.write_artifacts(fake_project, check=True)
        assert target.read_text(encoding="utf-8") == "tampered\n"

    def test_check_reports_a_missing_file(self, fake_project):
        assert ".env.example" in g.write_artifacts(fake_project, check=True)
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run --no-project --with pyyaml --with 'fastmcp-pvl-core>=4.5.0' --with pytest pytest scripts/tests/test_gen_config_surface.py -v`

Expected: `AttributeError: module 'gen_config_surface' has no attribute 'render_env_file'`.

- [ ] **Step 4: Implement `render_env_file` and `write_artifacts`**

Write the minimum to pass. Section titles render as `# --- {title} ---`; a `null` title emits no header. Each var emits its help as a preceding `#` comment line, then the assignment — commented when the file spec sets `commented: true`. Domain vars come from `domain_env_suffixes(ProjectConfig)` when the project's module is importable, and are skipped without error when it is not (a fresh render has no domain fields yet).

- [ ] **Step 5: Run the tests to verify they pass**

Run the Step 3 command. Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add scripts/gen_config_surface.py scripts/tests/test_gen_config_surface.py config-presentation.domain.yml
git commit -m "feat(config): emit .env.example and packaging/env.example

Both files are now generated from the merged surface, so all 18 core vars
appear — the hand-written .env.example was missing six (APP_DOMAIN,
AUTH_MODE, BEARER_DEFAULT_SUBJECT, EVENT_STORE_URL, KV_STORE_URL,
OIDC_VERIFY_ACCESS_TOKEN). Section layout and gating are declarative in
config-presentation.yml; domain vars are discovered from the project's own
ProjectConfig field metadata.

Adds config-presentation.domain.yml as a seeded file for vars the scan
cannot see, such as deprecated aliases.

Emitted text is asserted whitespace-clean and stable across calls, because
template-ci renders twice and diffs, and check_render_hygiene runs over
the render.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01As25PstUQeTR47J5SP5g7P"
```

---

## Task 3: Emit `examples/*.env` and `wizard-spec.json`

**Files:**
- Modify: `scripts/gen_config_surface.py`
- Modify: `scripts/tests/test_gen_config_surface.py`

**Interfaces consumed:** everything from Tasks 1–2.

**Interfaces produced:**

```python
def render_wizard_spec(pres: Mapping[str, Any], vars_: Sequence[Var],
                       answers: Mapping[str, object]) -> str: ...
```

Returns the wizard spec as JSON text with a trailing newline, matching the schema `docs/javascripts/config-wizard/wizard-spec-schema.json` already validates.

- [ ] **Step 1: Write the failing tests**

Append to `scripts/tests/test_gen_config_surface.py`:

```python
class TestRenderWizardSpec:
    def _spec(self, fake_project):
        import json

        answers = g.load_answers(fake_project)
        pres = g.load_presentation(Path.cwd(), str(answers["env_prefix"]))
        vars_ = g.collect_vars(fake_project, answers)
        return json.loads(g.render_wizard_spec(pres, vars_, answers))

    def test_meta_comes_from_copier_answers(self, fake_project):
        meta = self._spec(fake_project)["meta"]
        assert meta["projectName"] == "demo-mcp"
        assert meta["envPrefix"] == "DEMO_MCP"
        assert meta["dockerImage"] == "ghcr.io/demo/demo-mcp:latest"

    def test_secret_keys_come_from_the_secret_hint(self, fake_project):
        assert set(self._spec(fake_project)["secretKeys"]) == {
            "DEMO_MCP_BEARER_TOKEN",
            "DEMO_MCP_OIDC_CLIENT_SECRET",
            "DEMO_MCP_OIDC_JWT_SIGNING_KEY",
        }

    def test_routing_questions_come_first(self, fake_project):
        ids = [q["id"] for q in self._spec(fake_project)["questions"]]
        assert ids[:1] == ["deployment"]
        assert "auth" in ids

    def test_inferred_vars_get_no_question(self, fake_project):
        """AUTH_MODE is documented in env files but offered no wizard control."""
        spec = self._spec(fake_project)
        emitted = {q.get("var") for q in spec["questions"]}
        assert "DEMO_MCP_AUTH_MODE" not in emitted

    def test_transport_is_emitted_by_the_routing_select_not_a_question(self, fake_project):
        spec = self._spec(fake_project)
        assert "DEMO_MCP_TRANSPORT" not in {q.get("var") for q in spec["questions"]}
        emits = [k for q in spec["questions"] for o in q.get("options", [])
                 for k in (o.get("emit") or {})]
        assert "DEMO_MCP_TRANSPORT" in emits

    def test_group_hint_becomes_advanced_group(self, fake_project):
        q = next(q for q in self._spec(fake_project)["questions"]
                 if q.get("var") == "DEMO_MCP_HOST")
        assert q["advancedGroup"] == "Server"

    def test_when_oidc_becomes_a_two_dimensional_show_if(self, fake_project):
        q = next(q for q in self._spec(fake_project)["questions"]
                 if q.get("var") == "DEMO_MCP_OIDC_CLIENT_ID")
        assert q["showIf"] == {"deployment": ["server"], "auth": ["oidc", "both"]}

    def test_guard_message_no_longer_claims_an_ephemeral_key(self, fake_project):
        """#260: the old wording was false — the key is derived deterministically."""
        text = " ".join(gd["message"] for gd in self._spec(fake_project)["guards"])
        assert "ephemeral" not in text.lower()

    def test_output_ends_with_exactly_one_newline(self, fake_project):
        answers = g.load_answers(fake_project)
        pres = g.load_presentation(Path.cwd(), str(answers["env_prefix"]))
        text = g.render_wizard_spec(pres, g.collect_vars(fake_project, answers), answers)
        assert text.endswith("\n") and not text.endswith("\n\n")


class TestExampleEnvFiles:
    def test_bearer_example_carries_only_bearer_tagged_vars(self, fake_project):
        g.write_artifacts(fake_project, check=False)
        text = (fake_project / "examples" / "bearer-auth.env").read_text(encoding="utf-8")
        assert "DEMO_MCP_BEARER_TOKEN" in text
        assert "DEMO_MCP_OIDC_CLIENT_ID" not in text

    def test_no_placeholder_read_only_var_survives(self, fake_project):
        """The hand-written examples shipped READ_ONLY, which exists nowhere."""
        g.write_artifacts(fake_project, check=False)
        for name in ("bearer-auth.env", "oidc.env"):
            text = (fake_project / "examples" / name).read_text(encoding="utf-8")
            assert "READ_ONLY" not in text
```

- [ ] **Step 2: Run the tests to verify they fail**

Run the Task 2 Step 3 command. Expected: `AttributeError: ... has no attribute 'render_wizard_spec'`.

- [ ] **Step 3: Implement `render_wizard_spec` and register the remaining artifacts**

Write the minimum to pass. Map hints to the existing spec schema: `group` → `advancedGroup`; `when: server` → `showIf: {deployment: ["server"]}`; `when: oidc` → `showIf: {deployment: ["server"], auth: ["oidc","both"]}`; `when: bearer` → `showIf: {deployment: ["server"], auth: ["bearer","both"]}`; `secret: true` → membership in `secretKeys`; `control: emit` → no question emitted. Skip vars with `inferred=True`. Emit JSON with `indent=2` and one trailing newline.

- [ ] **Step 4: Run the tests to verify they pass**

Expected: all pass.

- [ ] **Step 5: Add a schema-validation test for the generated spec**

The template ships `docs/javascripts/config-wizard/wizard-spec-schema.json`, and the rendered project's `tests/test_config_wizard_spec_schema.py` validates against it. Pin the same guarantee for generated output by appending this test to `scripts/tests/test_gen_config_surface.py`:

```python
class TestGeneratedSpecMatchesShippedSchema:
    def test_generated_spec_validates(self, fake_project):
        import json

        jsonschema = pytest.importorskip("jsonschema")
        schema_path = (
            Path.cwd() / "docs" / "javascripts" / "config-wizard" / "wizard-spec-schema.json"
        )
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        answers = g.load_answers(fake_project)
        pres = g.load_presentation(Path.cwd(), str(answers["env_prefix"]))
        spec = json.loads(
            g.render_wizard_spec(pres, g.collect_vars(fake_project, answers), answers)
        )
        jsonschema.validate(instance=spec, schema=schema)
```

Run: `uv run --no-project --with pyyaml --with 'fastmcp-pvl-core>=4.5.0' --with pytest --with jsonschema pytest scripts/tests/test_gen_config_surface.py -v`

If the generated spec violates the schema, fix the generator — not the schema.

- [ ] **Step 6: Commit**

```bash
git add scripts/gen_config_surface.py scripts/tests/test_gen_config_surface.py
git commit -m "feat(config): emit examples/*.env and the config-wizard spec

The wizard spec is now generated, so it can no longer go stale against the
core env surface — the defect that left every existing consumer's published
wizard missing every question added since their first render.

inferred vars (AUTH_MODE) are documented in the env files but offered no
wizard control, per the flag's contract. TRANSPORT is emitted by the
deployment routing select rather than a question of its own.

The OIDC guard message drops the false 'ephemeral key' claim (#260): the
key is derived deterministically from the client secret, so the real
caveat is secret rotation.

examples/*.env now carry the project's real domain vars instead of the
placeholder READ_ONLY, which existed nowhere in the codebase.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01As25PstUQeTR47J5SP5g7P"
```

---

## Task 4: Wire it up, delete the replaced files, document the migration

**Files:**
- Modify: `copier.yml`
- Modify: `pyproject.toml.jinja`
- Modify: `.github/workflows/ci.yml.jinja`
- Modify: `.github/workflows/template-ci.yml`
- Create: `docs/guides/config-migration.md.jinja`
- Modify: `mkdocs.yml.jinja` (nav entry for the new guide)
- Delete: `.env.example.jinja`, `packaging/env.example.jinja`, `examples/bearer-auth.env.jinja`, `examples/oidc.env.jinja`, `docs/javascripts/config-wizard/wizard-spec.json.jinja`, `tests/test_config_wizard_drift.py.jinja`

- [ ] **Step 1: Bump the core floor**

In `pyproject.toml.jinja` line 19, change `"fastmcp-pvl-core>=4.3.0,<5"` to `"fastmcp-pvl-core>=4.5.0,<5"`. `server_config_surface()` does not exist before 4.5.0.

- [ ] **Step 2: Add the `_tasks` entry**

In `copier.yml`, add a second task after the `vendor_spa.py` line. It must not create a venv in the project tree:

```yaml
_tasks:
  - "{% if include_mcp_apps_scaffold %}python scripts/vendor_spa.py{% endif %}"
  - "python scripts/gen_config_surface.py"
```

The script self-bootstraps under `uv run --no-project` when `fastmcp_pvl_core` is not importable, so plain `python` here is correct and keeps the task line free of a version pin that would drift from `pyproject.toml`.

- [ ] **Step 3: Reclassify ownership in `copier.yml`**

Remove these three from `_skip_if_exists` — they are now `generated`, produced by the task rather than rendered by copier:

```
  - ".env.example"
  - "packaging/env.example"
  - "docs/javascripts/config-wizard/wizard-spec.json"
```

Add `config-presentation.domain.yml` to `_skip_if_exists`, and replace each removed entry's justifying comment with one explaining the new ownership. Note in the comment that these files are regenerated on every `copier update`, so downstream customisation belongs in `config.py` field metadata or `config-presentation.domain.yml`.

- [ ] **Step 4: Delete the replaced files**

```bash
git rm .env.example.jinja packaging/env.example.jinja \
       examples/bearer-auth.env.jinja examples/oidc.env.jinja \
       docs/javascripts/config-wizard/wizard-spec.json.jinja \
       tests/test_config_wizard_drift.py.jinja
```

These are real removals. Do not leave any of them as a fallback, and do not add a shim. The drift test goes because generation makes the drift it guarded impossible — a regeneration check replaces it.

- [ ] **Step 5: Add the CI check step**

In `.github/workflows/ci.yml.jinja`, immediately before the existing "Run ruff check" step (which sits at line 39 today, after the `vendor_spa.py --check` block), add:

```yaml
      - name: Verify generated config artifacts are up-to-date
        run: uv run python scripts/gen_config_surface.py --check
```

Ungated — every project has config artifacts. Place it alongside the existing vendored-SPA check so both up-to-date verifications sit together.

- [ ] **Step 6: Write the migration guide**

Create `docs/guides/config-migration.md.jinja`. It must cover, for a project updating from a pre-generation template version:

1. **Before regenerating**, copy any hand-written help text out of `.env.example`, `packaging/env.example`, and `wizard-spec.json` — those three were downstream-owned and are now generated, so the first regeneration overwrites them.
2. For each domain env var, add its field to `ProjectConfig`'s `CONFIG-FIELDS` block with `metadata={"help": ..., "tags": (...)}`, moving the help text from the prose that documented it.
3. Declare in `config-presentation.domain.yml` only vars the AST scan cannot see — deprecated aliases, or vars read outside `ProjectConfig.from_env`.
4. Run the generator, then `git diff` to confirm every var reappears.
5. Delete the now-duplicated hand-written tables.

State plainly that step 2 needs a human or a capable agent: deciding which sentence in a paragraph *is* the help text is a judgment call, not a mechanical substitution.

Add a nav entry for it in `mkdocs.yml.jinja` next to the other guides.

- [ ] **Step 7: Add the generator to template-CI's script checks**

Three exact edits in `.github/workflows/template-ci.yml`.

The test step (line 648 today) gains the generator's two imports:

```yaml
      - name: Run aggregator tests
        run: uv run --with pytest --with pyyaml --with jsonschema --with 'fastmcp-pvl-core>=4.5.0' pytest scripts/tests/ -v
```

The ruff check step (line 660 today) and the format step (line 665 today) each name their files explicitly — add `scripts/gen_config_surface.py` to both lists, so they read:

```
            scripts/copier_update_aggregator.py scripts/check_render_hygiene.py scripts/gen_config_surface.py scripts/tests/
```

- [ ] **Step 8: Full local verification**

```bash
git add -A && git commit -m "wip: stage 1a wiring"   # copier reads the git index

rm -rf /tmp/smoke /tmp/smoke2
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke

# The four artifacts must exist and be hygiene-clean straight out of the render
ls -1 /tmp/smoke/.env.example /tmp/smoke/packaging/env.example \
      /tmp/smoke/examples/bearer-auth.env /tmp/smoke/examples/oidc.env \
      /tmp/smoke/docs/javascripts/config-wizard/wizard-spec.json
python3 scripts/check_render_hygiene.py /tmp/smoke

# Determinism: the render-twice diff template-CI runs
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke2
diff -r /tmp/smoke /tmp/smoke2 && echo "renders identical"

# The generated wizard spec must satisfy the shipped schema, and the gate must pass
cd /tmp/smoke
uv sync --all-extras --all-groups
uv run python scripts/gen_config_surface.py --check
uv run ruff check . && uv run ruff format --check .
uv run mypy src/ tests/ && uv run pytest -x -q
uv run mkdocs build --strict

# Confirm the removals actually happened
cd -
! test -f .env.example.jinja
! test -f packaging/env.example.jinja
! ls examples/*.env.jinja 2>/dev/null
! test -f docs/javascripts/config-wizard/wizard-spec.json.jinja
! test -f tests/test_config_wizard_drift.py.jinja
! grep -rn '_COVERED_BY_INFERENCE' --include='*.jinja' .
```

Every command must succeed. `diff -r` reporting differences means the generator is non-deterministic — fix that before proceeding, because it would break template-CI for every future PR.

- [ ] **Step 9: Squash the wip commit and commit properly**

```bash
git reset --soft HEAD~1
git add -A
git commit -m "feat(config)!: generate config artifacts, retire the drift test

Wires the generator into copier _tasks and project CI, bumps the core
floor to >=4.5.0 for server_config_surface(), and deletes the six files
generation replaces.

BREAKING for existing consumers: .env.example, packaging/env.example, and
wizard-spec.json move out of _skip_if_exists and become generated, so the
first regeneration overwrites local edits. docs/guides/config-migration.md
covers extracting that content into config.py field metadata first.

Closes #217 — _COVERED_BY_INFERENCE is gone; a var is covered because the
generator emitted it, so there is no divergence left to except.
Closes #254 (wizard half) — the spec is no longer frozen per-project.
Closes #257 — examples/*.env and the env examples are generated, not
re-rendered per-project files.
Closes #260 — the false ephemeral-signing-key claim is gone from the
generated guard message.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01As25PstUQeTR47J5SP5g7P"
```

---

## Wrap-up

- [ ] **Open the PR** against `main`, body ending with the agent-attribution signature line, closing #217, #254, #257, #260. Note in the body that #254 is only half-closed by this PR if 1c has not landed — if so, reference #254 without `Closes`.
- [ ] **Do not merge and do not release.** Both are human-only.

## What 1a deliberately leaves for 1b and 1c

- `server.json`'s env block, the `docs/*.md` env tables, and README's two tables — all region-splicing into authored files (1b).
- `.pre-commit-config.yaml` seeded → seamed with a `DOMAIN-HOOKS` seam, closing #254's structural-gate half (1c).
- `docs/deployment/oidc.md.jinja`'s copy of the false ephemeral-key claim — authored prose, fixed in 1b alongside the other docs tables. #260 stays open until then if this PR only fixes the generated guard message.
