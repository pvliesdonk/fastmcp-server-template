# Scaffold coverage + README post-setup extension

**Date:** 2026-04-23
**Issues:** [#50](https://github.com/pvliesdonk/fastmcp-server-template/issues/50), [#51](https://github.com/pvliesdonk/fastmcp-server-template/issues/51)

> **Revision 2026-04-23 (post-implementation):** Section 2 originally extended `tests/test_tools.py.jinja`, but that file is in `copier.yml`'s `_exclude` block — copier **never renders it**, on copy or update. The resource + prompt tests were folded into `tests/test_smoke.py.jinja` (which IS in `_skip_if_exists`) so they reach greenfield scaffolds as intended. Sections 2 + 3 below are kept as the original design record; the File changes table (§ "File changes") and the implementation plan reflect the corrected landing place.

## Problem

Two papercuts surface on the first greenfield use of the template
(`paperless-mcp`):

1. **Pristine scaffold fails its own coverage gate.** The shipped
   `tests/test_smoke.py` + `tests/test_tools.py` exercise ~59% of the
   generated code, well below `pyproject.toml`'s `fail_under = 80`.
   A new downstream maintainer sees red CI on commit 1.

2. **Required GitHub secrets are undocumented.** After
   `gh repo create --push`, three secrets must be configured before CI
   stops failing — `RELEASE_TOKEN`, `CODECOV_TOKEN`,
   `CLAUDE_CODE_OAUTH_TOKEN`. None of them are mentioned anywhere in
   the rendered README; users grep workflow files to discover each.

Issue #52 (stale venv shebangs after moving a scaffolded project) is
out of scope — that's a `uv` behaviour question, not a template fix.

## Goals

- A pristine scaffold's `uv run pytest` passes the 80% threshold
  without any downstream test-writing.
- A new downstream maintainer can find every required GitHub secret
  in the rendered README, with copy-pasteable commands to set them.
- Maintenance footprint stays small: borrow the existing typer test
  pattern from `scholar-mcp`, don't invent a new one.

## Non-goals

- Fixing or documenting the stale-shebang issue (#52).
- Adding a `scripts/setup-secrets.sh` interactive helper (the README
  table closes the loop for most users; defer the script).
- Moving deployment docs into the README (`docs/deployment/*.md.jinja`
  already covers Docker / OIDC).

## Coverage gap analysis

Source files in the rendered scaffold (executable line estimates):

| File | ~LOC | Covered by current tests? |
|---|---|---|
| `cli.py` | ~70 | **No** — no CLI tests exist |
| `server.py` | ~50 | Mostly (transport!=stdio branch uncovered) |
| `_server_apps.py` | ~20 | Else-branch only (no env-var branch covered) |
| `_server_deps.py` | ~30 | Yes (via `client` fixture lifespan) |
| `config.py` | ~25 | Yes |
| `domain.py` | ~25 | `start/stop/ping` covered, `status` not |
| `tools.py` | ~25 | Yes (`ping` tested) |
| `resources.py` | ~15 | `register_*` only — `status` handler not invoked |
| `prompts.py` | ~10 | `register_*` only — `summarize` handler not invoked |

`cli.py` alone is ~70 of ~270 executable lines (~26% of the codebase),
which is the dominant gap. Covering it lifts coverage to ~75-80% —
marginal. Adding handler-invocation tests for the `status` resource,
the `summarize` prompt, and the `_server_apps` env-var branch comfortably
clears 80% with headroom for downstream branch additions.

## Design

### 1. New file: `tests/test_cli.py.jinja`

Borrowed pattern: `scholar-mcp/tests/test_cli.py` (the only downstream
that uses typer; markdown-vault-mcp and image-gen-mcp are argparse-based).

```python
"""CLI tests for {{ human_name }}."""

from __future__ import annotations

from typer.testing import CliRunner

from {{ python_module }}.cli import app


def test_help_exits_zero() -> None:
    """`{{ project_name }} --help` lists the serve command."""
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "serve" in result.output


def test_serve_help_exits_zero() -> None:
    """`{{ project_name }} serve --help` documents transport flags."""
    result = CliRunner().invoke(app, ["serve", "--help"])
    assert result.exit_code == 0
    assert "stdio" in result.output


def test_no_args_shows_help() -> None:
    """`no_args_is_help=True` makes bare invocation exit 0 with help text."""
    result = CliRunner().invoke(app, [])
    assert result.exit_code == 0
    assert "serve" in result.output
```

`--help` exits via typer before any command body runs, so no
`make_server()` / uvicorn imports execute. No mocks needed.

**Copier placement:** Add `tests/test_cli.py` to `_skip_if_exists` in
`copier.yml` — same treatment as `tests/test_smoke.py`. Greenfield
scaffolds get the file; downstreams that already have their own
`test_cli.py` (scholar-mcp, image-gen-mcp, markdown-vault-mcp) keep
theirs.

### 2. Extend `tests/test_tools.py.jinja`

Add two handler-invocation tests using the existing `client` fixture:

```python
async def test_status_resource_returns_ready(client: Client) -> None:
    """The `status://{{ project_name }}` resource reports the running service."""
    result = await client.read_resource("status://{{ project_name }}")
    payload = result[0].text
    assert "ready" in payload


async def test_summarize_prompt_includes_context(client: Client) -> None:
    """The `summarize` prompt round-trips the context argument."""
    result = await client.get_prompt("summarize", {"context": "hello world"})
    assert "hello world" in result.messages[0].content.text
```

`test_tools.py` is in `_exclude` — copier never renders it (on copy
or on update), so the plan landed these tests in
`tests/test_smoke.py.jinja` instead. See the revision banner at the
top of this document.

### 3. Extend `tests/test_smoke.py.jinja`

Add one branch test for `_server_apps.register_apps`:

```python
def test_register_apps_logs_when_app_domain_set(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`register_apps` logs an info message when the app-domain env var is set."""
    monkeypatch.setenv("{{ env_prefix }}_APP_DOMAIN", "example.com")
    with caplog.at_level("INFO", logger="{{ python_module }}._server_apps"):
        make_server()
    assert any("example.com" in r.message for r in caplog.records)
```

`test_smoke.py` is in `_skip_if_exists` — greenfield scaffolds get
the new tests; existing downstreams keep their version.

### 4. Extend `README.md.jinja`

`README.md` is in `_skip_if_exists` — extensions land on greenfield
scaffolds only, which is exactly the issue audience (someone who just
ran `copier copy` and `gh repo create`).

New sections appended after the existing `## Configuration` block,
before `## Links`:

```markdown
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
| `RELEASE_TOKEN` | `release.yml` | Fine-grained PAT at https://github.com/settings/personal-access-tokens/new with `contents: write` (and `pull_requests: write` if release PRs are enabled). Scoped to this repo. |
| `CODECOV_TOKEN` | `ci.yml`, `coverage-status.yml` | https://codecov.io → sign in with GitHub → add the repo → copy the upload token from repo settings. |
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
uv run pytest -x -q                      # tests
uv run ruff check --fix . && uv run ruff format .   # lint + format
uv run mypy src/                         # type-check
```

See [`CLAUDE.md`](CLAUDE.md) for the full PR acceptance gates.
```

The existing `## Quick start`, `## Configuration`, and `## Links`
sections stay unchanged.

## File changes

| File | Change | Notes |
|---|---|---|
| `tests/test_cli.py.jinja` | **new** | CliRunner tests; covers `cli.py` |
| `tests/test_smoke.py.jinja` | extend | +3 tests: `register_apps` env-var branch, `status` resource, `summarize` prompt |
| `tests/conftest.py.jinja` | edit | `Client[Any]` on the `client` fixture (strict mypy) |
| `copier.yml` | edit | Add `tests/test_cli.py` to `_skip_if_exists` |
| `pyproject.toml.jinja` | edit | Add `tests/test_smoke.py` to ruff TC002 per-file ignores |
| `README.md.jinja` | extend | +3 sections (post-scaffold checklist, GitHub secrets, local dev) |
| `CLAUDE.md` | edit | Document `--vcs-ref=HEAD` for local iteration |

## Validation

Local render + gate (per project CLAUDE.md):

```bash
rm -rf /tmp/smoke
uv run --no-project --with copier copier copy --trust --defaults \
  --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
cd /tmp/smoke
uv sync --all-extras --dev
uv run ruff check . && uv run ruff format --check .
uv run mypy src/
uv run pytest -x -q   # must pass with --fail-under=80
```

Then push and wait for `template-ci.yml` to run the same gate on
Python 3.11–3.14.

## Rollout

- Template release: standard `template-release.yml` `workflow_dispatch`
  with `bump=patch` (no breaking change). **Manual trigger only** —
  not run autonomously per project conventions.
- Downstream pickup: weekly `copier-update.yml` cron picks up the
  template change. Existing downstreams (markdown-vault-mcp,
  image-gen-mcp, scholar-mcp) are unaffected because their copies of
  `test_smoke.py`, `test_cli.py`, and `README.md` already exist
  (`_skip_if_exists` preserves them).
