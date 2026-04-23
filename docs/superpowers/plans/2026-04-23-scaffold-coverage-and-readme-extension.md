# Scaffold Coverage + README Post-Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a pristine scaffold pass its own 80% coverage gate (issue #50) and add a README post-setup section documenting required GitHub secrets (issue #51).

**Architecture:** Five small template-file edits + one `copier.yml` entry. No new abstractions. Validated by rendering `tests/fixtures/smoke-answers.yml` into `/tmp/smoke` after each change and running the generated project's gate (`uv sync` → `pytest` → `ruff` → `mypy`).

**Tech Stack:** copier (template rendering), pytest with `--cov`, `typer.testing.CliRunner`, FastMCP `Client` for in-memory resource/prompt round-trips.

**Spec:** [`docs/superpowers/specs/2026-04-23-scaffold-coverage-and-readme-extension-design.md`](../specs/2026-04-23-scaffold-coverage-and-readme-extension-design.md)

---

## File Structure

| File | Change | Why |
|---|---|---|
| `tests/test_smoke.py.jinja` | extend (+3 tests) | `register_apps` env-var branch, `status` resource, `summarize` prompt |
| `tests/test_cli.py.jinja` | **create** | Cover `cli.py` (~26% of codebase, currently 0% covered) |
| `tests/conftest.py.jinja` | edit | `Client[Any]` annotation so strict mypy on `tests/` passes |
| `copier.yml` | edit (+1 entry in `_skip_if_exists`) | Preserve downstream `test_cli.py` if present |
| `pyproject.toml.jinja` | edit (+1 ruff per-file ignore) | Silence TC002 on the new annotation-only imports in `tests/test_smoke.py` |
| `README.md.jinja` | extend (+3 sections) | Post-scaffold checklist, GitHub secrets table, local dev gate |
| `CLAUDE.md` | edit | Document `--vcs-ref=HEAD` for local iteration (template-maintainer gate) |

No new files in `src/`.

---

## Conventions for the implementer

- This is a **template repo**. Files ending in `.jinja` are rendered by copier into a generated project. Variables like `{{ python_module }}` are substituted at render time using `tests/fixtures/smoke-answers.yml`.
- The validation loop is: edit `.jinja` → re-render to `/tmp/smoke` → `cd /tmp/smoke` → run the generated project's gate. Never run `pytest` from the template repo root — the template repo has no Python project of its own.
- Each task ends with a commit using conventional commit format. Use `feat(scaffold-tests):` for test additions, `feat(readme):` for README changes, `chore(copier):` for `copier.yml`. Sign with `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>`.
- The full render+gate command (used in many tasks) is wrapped in a helper alias for brevity in this doc — substitute the actual commands when running.

**Render+gate one-liner (referenced as RENDER_GATE in this plan):**

```bash
rm -rf /tmp/smoke && \
uv run --no-project --with copier copier copy --trust --defaults \
  --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke && \
cd /tmp/smoke && \
uv sync --all-extras --dev && \
uv run ruff check . && uv run ruff format --check . && \
uv run mypy src/ && \
uv run pytest -x -q
```

---

## Task 0: Baseline render + record coverage

**Files:** none (read-only sanity check)

**Why:** Capture the starting coverage number so subsequent tasks can confirm forward motion.

- [ ] **Step 1: Render and run gate, capture coverage**

```bash
cd /mnt/code/fastmcp-server-template
rm -rf /tmp/smoke
uv run --no-project --with copier copier copy --trust --defaults \
  --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
cd /tmp/smoke
uv sync --all-extras --dev
uv run pytest --cov=src/smoke_mcp --cov-report=term-missing 2>&1 | tail -40
```

Expected: tests pass, coverage report shows total ~59% (or close), `FAIL Required test coverage of 80.0% not reached.`

- [ ] **Step 2: Note baseline**

Record the baseline coverage % and which lines are uncovered (look for `cli.py`, `_server_apps.py`, `domain.py:status`, `resources.py`, `prompts.py` in the missing-lines report). No commit — this is informational.

---

## Task 1+2 (merged): Extend `tests/test_smoke.py.jinja` with all new test coverage

**Plan revision (2026-04-23):** Original Task 1 targeted `tests/test_tools.py.jinja`, but that file is in `copier.yml`'s `_exclude` block (not `_skip_if_exists`), so it never renders into greenfield scaffolds. Folding the resource + prompt tests into `tests/test_smoke.py.jinja` (which IS in `_skip_if_exists`) lands them where issue #50 needs them, without touching `_exclude`'s deliberate "downstream brings their own" semantics.

**Files:**
- Modify: `tests/test_smoke.py.jinja`

- [ ] **Step 1: Read the current file**

```bash
cat /mnt/code/fastmcp-server-template/tests/test_smoke.py.jinja
```

Confirm it currently has just `test_make_server_constructs` and imports only `make_server`.

- [ ] **Step 2: Replace with extended version**

Overwrite `/mnt/code/fastmcp-server-template/tests/test_smoke.py.jinja` with:

```jinja
"""Smoke tests for {{ human_name }}."""

from __future__ import annotations

import pytest
from fastmcp import Client

from {{ python_module }}._server_apps import register_apps
from {{ python_module }}.server import make_server


def test_make_server_constructs() -> None:
    """make_server() returns a FastMCP instance without raising."""
    server = make_server()
    assert server is not None


def test_register_apps_logs_when_app_domain_set(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """register_apps logs the configured app domain when the env var is set.

    Covers the ``if app_domain:`` branch of ``_server_apps.register_apps``,
    which the default smoke tests miss because no ``{{ env_prefix }}_APP_DOMAIN``
    is set in the test env.
    """
    monkeypatch.setenv("{{ env_prefix }}_APP_DOMAIN", "example.com")
    with caplog.at_level("INFO", logger="{{ python_module }}._server_apps"):
        # Pass None for the FastMCP instance — register_apps doesn't touch it
        # in the scaffold's no-op branch.
        register_apps(None)  # type: ignore[arg-type]
    assert any("example.com" in r.message for r in caplog.records)


async def test_status_resource_reports_ready(client: Client) -> None:
    """The example ``status://`` resource returns the running service's state."""
    result = await client.read_resource("status://{{ project_name }}")
    text = result[0].text if hasattr(result[0], "text") else str(result[0])
    assert "ready" in text


async def test_summarize_prompt_includes_context(client: Client) -> None:
    """The example ``summarize`` prompt round-trips its ``context`` argument."""
    result = await client.get_prompt("summarize", {"context": "hello world"})
    assert "hello world" in result.messages[0].content.text
```

Notes:
- The `client` fixture comes from `tests/conftest.py.jinja` (also in `_skip_if_exists`, also rendered into greenfield scaffolds). It wraps `make_server()` in an in-memory FastMCP `Client`.
- The `# type: ignore[arg-type]` is needed because `register_apps` is typed to take a `FastMCP`, but the scaffold body never dereferences it — simplest way to test the env-var branch without spinning up a server.
- `tests/test_tools.py.jinja` is **deliberately not modified** — it's in `_exclude` so changes there never reach scaffolds.

- [ ] **Step 3: Render and run the new tests**

```bash
cd /mnt/code/fastmcp-server-template
rm -rf /tmp/smoke
uv run --no-project --with copier copier copy --trust --defaults \
  --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
cd /tmp/smoke
uv sync --all-extras --dev
uv run pytest tests/test_smoke.py -v
```

Expected: 4 tests pass (`test_make_server_constructs`, `test_register_apps_logs_when_app_domain_set`, `test_status_resource_reports_ready`, `test_summarize_prompt_includes_context`).

If `test_status_resource_reports_ready` fails with an attribute error on `result[0]`, the FastMCP client API may have shifted — inspect with `python -c "from fastmcp import Client; help(Client.read_resource)"` and adjust the access pattern. The `hasattr(...)` guard is defensive against minor API shifts.

- [ ] **Step 4: Run mypy + coverage check**

```bash
cd /tmp/smoke
uv run mypy src/ tests/
uv run pytest --cov=src/smoke_mcp --cov-report=term 2>&1 | tail -15
```

Expected: mypy clean (the `# type: ignore[arg-type]` silences the intentional misuse). Coverage > Task 0 baseline (gain from `resources.py`, `prompts.py`, `domain.py:status`, and `_server_apps.py` if-branch). Likely still under 80% — Task 3 (CLI tests) closes the remaining gap.

- [ ] **Step 5: Commit**

```bash
cd /mnt/code/fastmcp-server-template
git add tests/test_smoke.py.jinja
git commit -m "$(cat <<'EOF'
feat(scaffold-tests): cover register_apps branch + status resource + summarize prompt

The pristine scaffold's smoke test only exercised make_server() and
register_apps's inactive branch; the status resource handler, summarize
prompt handler, and register_apps's env-var branch were all uncovered,
contributing to the 59% coverage that fails the project's own
--fail-under=80 gate. Add three round-trip tests via the existing
in-memory Client fixture (already shipped in conftest.py.jinja).

Folded into test_smoke.py.jinja rather than test_tools.py.jinja
because the latter is in copier.yml's _exclude block and never
renders into greenfield scaffolds.

Refs #50

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Create `tests/test_cli.py.jinja` and update `copier.yml`

**Files:**
- Create: `tests/test_cli.py.jinja`
- Modify: `copier.yml` (`_skip_if_exists` block)

- [ ] **Step 1: Create the new test file**

Write `/mnt/code/fastmcp-server-template/tests/test_cli.py.jinja`:

```jinja
"""CLI tests for {{ human_name }}.

Borrowed from scholar-mcp's ``test_cli.py`` typer pattern. ``--help``
exits via typer before any command body runs, so these tests don't
import ``server.py`` or start uvicorn — keeping them fast and free
of side effects.
"""

from __future__ import annotations

from typer.testing import CliRunner

from {{ python_module }}.cli import app


def test_help_exits_zero() -> None:
    """`{{ project_name }} --help` lists the serve command."""
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "serve" in result.output


def test_serve_help_exits_zero() -> None:
    """`{{ project_name }} serve --help` documents the transport flag."""
    result = CliRunner().invoke(app, ["serve", "--help"])
    assert result.exit_code == 0
    assert "stdio" in result.output


def test_no_args_shows_help() -> None:
    """Bare invocation exits 0 with help text via ``no_args_is_help=True``."""
    result = CliRunner().invoke(app, [])
    assert result.exit_code == 0
    assert "serve" in result.output
```

- [ ] **Step 2: Add `tests/test_cli.py` to `copier.yml`'s `_skip_if_exists`**

Open `/mnt/code/fastmcp-server-template/copier.yml` and locate the `_skip_if_exists` block (starts at line 27). Insert `tests/test_cli.py` directly after `tests/test_smoke.py`, so the relevant lines read:

```yaml
  - "tests/conftest.py"
  - "tests/test_smoke.py"
  - "tests/test_cli.py"
  - "README.md"
```

This protects downstream projects (scholar-mcp, image-gen-mcp, markdown-vault-mcp) from having their existing `test_cli.py` overwritten by `copier update`.

- [ ] **Step 3: Render and run the new tests**

```bash
cd /mnt/code/fastmcp-server-template
rm -rf /tmp/smoke
uv run --no-project --with copier copier copy --trust --defaults \
  --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
cd /tmp/smoke
uv sync --all-extras --dev
uv run pytest tests/test_cli.py -v
```

Expected: 3 tests pass.

- [ ] **Step 4: Run the full gate and verify coverage clears 80%**

```bash
cd /tmp/smoke
uv run ruff check . && uv run ruff format --check .
uv run mypy src/ tests/
uv run pytest -x -q
```

Expected: all four commands succeed. The pytest line should NOT show `FAIL Required test coverage of 80.0% not reached`. If it does, capture the `--cov-report=term-missing` output and inspect which lines remain uncovered — most likely candidates are CLI option-default fallbacks (`--http-path` env fallback) or the `transport != "stdio"` branch in `server.py`. If a small additional test would close the gap, add it under Task 1 or Task 3 rather than introducing a new task; otherwise, lower-priority uncovered lines can be left for downstream tests.

- [ ] **Step 5: Commit**

```bash
cd /mnt/code/fastmcp-server-template
git add tests/test_cli.py.jinja copier.yml
git commit -m "$(cat <<'EOF'
feat(scaffold-tests): add CLI smoke tests so pristine scaffold clears 80% coverage

cli.py was ~26% of the rendered codebase and 0% covered, so a fresh
copier copy + uv run pytest failed the project's own --fail-under=80
gate. Add three CliRunner tests (--help, serve --help, bare invocation)
borrowed from scholar-mcp's typer pattern, and protect existing
downstream test_cli.py files via _skip_if_exists.

Closes #50

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Extend `README.md.jinja` with post-scaffold sections

**Files:**
- Modify: `README.md.jinja`

- [ ] **Step 1: Read the current README**

```bash
cat /mnt/code/fastmcp-server-template/README.md.jinja
```

Confirm it has `# {{ human_name }}`, `## Quick start`, `## Configuration`, `## Links` (in that order).

- [ ] **Step 2: Replace with the extended version**

Overwrite `/mnt/code/fastmcp-server-template/README.md.jinja` with:

```jinja
# {{ human_name }}

{{ domain_description }}

## Quick start

```bash
pip install {{ pypi_name }}
{{ project_name }} serve                                # stdio
{{ project_name }} serve --transport http --port 8000   # HTTP
```

## Configuration

All configuration goes via `{{ env_prefix }}_*` env vars.  See
[docs/configuration.md](docs/configuration.md).

## Post-scaffold checklist

After `copier copy` and `gh repo create --push`:

1. Configure GitHub secrets (see below).
2. Install dev dependencies: `uv sync --all-extras --dev`.
3. Run the gate locally: `uv run pytest -x -q && uv run ruff check . && uv run mypy src/`.
4. Push the first commit — CI should be green.

## GitHub secrets

CI workflows reference three repository secrets. Configure them via
**Settings → Secrets and variables → Actions** or with `gh secret set`:

| Secret | Used by | How to generate |
|---|---|---|
| `RELEASE_TOKEN` | `release.yml` | Fine-grained PAT at <https://github.com/settings/personal-access-tokens/new> with `contents: write` (and `pull_requests: write` if release PRs are enabled). Scoped to this repo. |
| `CODECOV_TOKEN` | `ci.yml`, `coverage-status.yml` | <https://codecov.io> — sign in with GitHub, add the repo, copy the upload token from the repo settings page. |
| `CLAUDE_CODE_OAUTH_TOKEN` | `claude.yml`, `claude-code-review.yml` | Run `claude setup-token` locally and paste the result. |

```bash
gh secret set RELEASE_TOKEN
gh secret set CODECOV_TOKEN
gh secret set CLAUDE_CODE_OAUTH_TOKEN
```

`GITHUB_TOKEN` is auto-provided — no action needed.

## Local development

The PR gate (matches CI):

```bash
uv run pytest -x -q                                  # tests
uv run ruff check --fix . && uv run ruff format .    # lint + format
uv run mypy src/                                     # type-check
```

See [`CLAUDE.md`](CLAUDE.md) for the full PR acceptance gates.

## Links

- [Documentation](https://{{ github_org }}.github.io/{{ project_name }}/)
- [FastMCP](https://gofastmcp.com)
- [fastmcp-pvl-core](https://pypi.org/project/fastmcp-pvl-core/)
```

Note: keep the `{{ project_name }}`, `{{ env_prefix }}`, `{{ github_org }}` jinja
substitutions exactly as written — copier will fill them in at render time.

- [ ] **Step 3: Render and verify content**

```bash
cd /mnt/code/fastmcp-server-template
rm -rf /tmp/smoke
uv run --no-project --with copier copier copy --trust --defaults \
  --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
cat /tmp/smoke/README.md
```

Expected output verifies:
- `## Post-scaffold checklist`, `## GitHub secrets`, `## Local development` sections present
- `{{ … }}` placeholders are all rendered (no literal `{{` in output)
- Secret table shows `RELEASE_TOKEN`, `CODECOV_TOKEN`, `CLAUDE_CODE_OAUTH_TOKEN`
- `gh secret set` snippet shows three commands

- [ ] **Step 4: Commit**

```bash
cd /mnt/code/fastmcp-server-template
git add README.md.jinja
git commit -m "$(cat <<'EOF'
feat(readme): add post-scaffold checklist, GitHub secrets table, local dev gate

A fresh copier copy + gh repo create --push leaves CI failing until
three secrets are set, but the rendered README didn't mention any of
them. Add a post-scaffold checklist, a secrets table with one-line
generation steps and a gh secret set snippet, and the local PR gate
commands so new downstream maintainers don't have to grep workflow
files.

Closes #51

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Final end-to-end validation

**Files:** none (verification only)

- [ ] **Step 1: Re-render and run the full gate**

```bash
cd /mnt/code/fastmcp-server-template
rm -rf /tmp/smoke
uv run --no-project --with copier copier copy --trust --defaults \
  --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
cd /tmp/smoke
uv sync --all-extras --dev
uv run ruff check . && uv run ruff format --check .
uv run mypy src/ tests/
uv run pytest -x -q
```

Expected: every command exits 0. Pytest output should show 8 tests passing (was 2) and NO `FAIL Required test coverage` line.

- [ ] **Step 2: Verify coverage is comfortably above the threshold**

```bash
cd /tmp/smoke
uv run pytest --cov=src/smoke_mcp --cov-report=term 2>&1 | tail -5
```

Expected: total ≥ 85% (per spec's design target). If between 80-85%, that's still passing — the spec calls out 85% as a comfort margin, not a hard requirement.

- [ ] **Step 3: Spot-check the rendered README**

```bash
grep -E "^##|RELEASE_TOKEN|CODECOV_TOKEN|CLAUDE_CODE_OAUTH_TOKEN" /tmp/smoke/README.md
```

Expected: shows all three secrets and the new section headings (`## Post-scaffold checklist`, `## GitHub secrets`, `## Local development`).

- [ ] **Step 4: Push the branch (no PR yet — let user decide)**

```bash
cd /mnt/code/fastmcp-server-template
git log --oneline -5
git push origin HEAD
```

Stop here. Do NOT open a PR or trigger a release — both are user decisions per project conventions (see memory: release dispatch is manual). Surface the branch name and let the user open the PR themselves with `gh pr create` or via the `/commit-push-pr` skill.

---

## Self-review checklist (already completed by plan author)

- ✅ Spec coverage: every spec section maps to a task (Task 1 → tests §2, Task 2 → tests §3, Task 3 → tests §1 + copier §1, Task 4 → README §4, Task 5 → spec's Validation section).
- ✅ No placeholders: every code block is complete; no "TODO", "TBD", "implement later".
- ✅ Type consistency: `register_apps`, `make_server`, `app`, `Client.read_resource`, `Client.get_prompt` signatures match between tasks and the actual scaffold source files.
- ✅ Render+gate command repeated in each task (intentional — the "DRY" rule yields to "engineer may read tasks out of order" when the command is the validation gate).
