# Adopt register_file_exchange() in template Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace direct `ArtifactStore` wiring in the generated server skeleton with the spec-compliant `register_file_exchange()` facade from `fastmcp-pvl-core` 1.2.0, and ship the supporting docs / tests / config updates so every newly generated project participates in MCP File Exchange v0.2.5 by default.

**Architecture:** `server.py.jinja` drops the `ArtifactStore` import and the `if transport != "stdio"` block, and instead calls `register_file_exchange(mcp, namespace=..., env_prefix=..., transport=...)` once. The facade resolves transport-gating, builds (or skips) the artifact store, mounts the `/artifacts/{token}` route, advertises the `experimental.file_exchange` capability, and registers the `create_download_link` / `fetch_file` MCP tools as appropriate. The template captures the returned handle as a discarded value (downstream projects that need to publish will capture it and stash it per the new doc page). Documentation, env-var lists, smoke tests, and the dependency floor follow.

**Tech Stack:** Python 3.11+, FastMCP, `fastmcp-pvl-core` ≥ 1.2.0 (which adds `register_file_exchange`, `FileRef`, `FileRefPreview`, `FileExchangeHandle`, `FILE_EXCHANGE_SPEC_VERSION`), copier, mkdocs-material, pytest.

**Reference (read before starting any code task):**

- Issue: `gh issue view 72`
- pvl-core PR: `pvliesdonk/fastmcp-pvl-core#33`
- Spec: `https://github.com/pvliesdonk/fastmcp-pvl-core/blob/main/docs/specs/file-exchange.md`
- Local pvl-core checkout (this machine): `/mnt/code/fastmcp-pvl-core` — read `src/fastmcp_pvl_core/file_exchange.py` for the facade source-of-truth, since PyPI 1.2.0 may not be live yet.
- Template render+gate workflow: `CLAUDE.md` "Making changes" section.

---

## Pre-flight: Prerequisites

Before any task in this plan, confirm:

1. **`fastmcp-pvl-core==1.2.0` is on PyPI.** ✅ Confirmed at plan-write time (2026-04-27): release `v1.2.0` was tagged at commit `48f7301a` on 2026-04-27 16:49 UTC and the wheel is live on PyPI. Re-verify before starting if a long delay has elapsed: `python3 -c "import urllib.request, json; print(json.load(urllib.request.urlopen('https://pypi.org/pypi/fastmcp-pvl-core/json'))['info']['version'])"`.

2. **The downstream consumers list is unchanged from auto-memory** — `markdown-vault-mcp`, `image-generator-mcp`, `paperless-mcp`. Per the issue's "Out of scope" section, this PR does **not** migrate those repos; that's three separate follow-up issues filed after this lands. Do not touch those repos as part of this work.

3. **Branch hygiene:** create a feature branch off `main` (e.g. `feat/adopt-register-file-exchange`). The current working branch (`chore/mop-up-ci-and-gate3`) is unrelated; do not stack this on top of it.

---

## File Structure

Files modified / created by this plan:

| Path | Action | Responsibility |
|---|---|---|
| `src/{{python_module}}/server.py.jinja` | modify | Swap `ArtifactStore` direct wiring for `register_file_exchange` facade. |
| `pyproject.toml.jinja` | modify | Bump `fastmcp-pvl-core` floor to `>=1.2.0,<2`. |
| `CLAUDE.md.jinja` | modify (line 114) | Mention "MCP File Exchange (`register_file_exchange`)" alongside artifact store. |
| `docs/configuration.md.jinja` | modify | Add `_FILE_EXCHANGE_*` env vars to the variable list. |
| `docs/guides/file-exchange.md.jinja` | **create** | Full guide: spec link, two patterns, env vars, publish/consume snippets, docker-compose example. Template-owned (per #29 deferral). |
| `mkdocs.yml.jinja` | modify | Add `Guides → File Exchange: guides/file-exchange.md` to nav. |
| `tests/test_smoke.py.jinja` | modify | Two new tests: stdio default → no file-exchange tools/capability; http transport → capability advertised when an exchange dir is provided. |
| `docs/superpowers/plans/2026-04-27-adopt-register-file-exchange.md` | (this plan) | Tracked as part of the PR. |

**Files explicitly NOT modified:**

- `src/{{python_module}}/_server_deps.py.jinja` — the handle is not stashed in `lifespan_context` because the scaffold has no producer tools that call `publish()`. The doc page explains the pattern for downstream projects.
- `src/{{python_module}}/tools.py.jinja` — adding a publishing example would change the example tool's contract; leave domain code alone.
- `examples/`, `compose.yml.jinja` — no example needs file-exchange today; the doc's docker-compose snippet is illustrative.

---

## Task 1: Verify the pvl-core API surface against the local checkout

Before editing anything, confirm the API names and signatures the plan assumes match the actual code in `/mnt/code/fastmcp-pvl-core`. This guards against drift between the issue body (written from memory) and the merged PR.

**Files:**
- Read-only: `/mnt/code/fastmcp-pvl-core/src/fastmcp_pvl_core/__init__.py`
- Read-only: `/mnt/code/fastmcp-pvl-core/src/fastmcp_pvl_core/file_exchange.py`

- [ ] **Step 1: Confirm `register_file_exchange` is exported.**

```bash
grep -E '^\s*"register_file_exchange"' /mnt/code/fastmcp-pvl-core/src/fastmcp_pvl_core/__init__.py
```

Expected: one match (in `__all__`).

- [ ] **Step 2: Confirm the signature matches the issue's snippet.**

```bash
sed -n '473,485p' /mnt/code/fastmcp-pvl-core/src/fastmcp_pvl_core/file_exchange.py
```

Expected: `def register_file_exchange(mcp, *, namespace, env_prefix, produces=(), consumes=(), consumer_sink=None, artifact_store=None, transport="auto", download_tool_name=..., fetch_tool_name=...) -> FileExchangeHandle:`. If any kwarg name has changed, update Tasks 2 and 5 below to match.

- [ ] **Step 3: Confirm transport literal type.**

```bash
grep -n 'transport: Literal' /mnt/code/fastmcp-pvl-core/src/fastmcp_pvl_core/file_exchange.py | head
```

Expected: `transport: Literal["http", "stdio", "auto"] = "auto"`. **This matters:** `make_server`'s own `transport` parameter is a plain `str` and accepts `"sse"`. Passing `"sse"` straight through would mypy-fail under `--strict`. The plan handles this in Task 2 by passing `"auto"` and letting the facade resolve from `{PREFIX}_TRANSPORT` / `FASTMCP_TRANSPORT`.

- [ ] **Step 4: Confirm `FILE_EXCHANGE_SPEC_VERSION` is exported (used in the doc page).**

```bash
grep -n 'FILE_EXCHANGE_SPEC_VERSION' /mnt/code/fastmcp-pvl-core/src/fastmcp_pvl_core/__init__.py
```

Expected: a re-export under that name.

- [ ] **Step 5: No commit for this task** (read-only verification).

---

## Task 2: Update `server.py.jinja` to call `register_file_exchange`

**Files:**
- Modify: `src/{{python_module}}/server.py.jinja`

- [ ] **Step 1: Replace the `fastmcp_pvl_core` import block (current lines 16-25).**

Current:

```python
from fastmcp_pvl_core import (
    ArtifactStore,
    ServerConfig,  # noqa: F401  — re-exported for downstream projects' convenience
    build_auth,
    build_event_store,  # noqa: F401  — re-exported for downstream projects' convenience
    build_instructions,
    configure_logging_from_env,
    resolve_auth_mode,
    wire_middleware_stack,
)
```

Replace with:

```python
from fastmcp_pvl_core import (
    ServerConfig,  # noqa: F401  — re-exported for downstream projects' convenience
    build_auth,
    build_event_store,  # noqa: F401  — re-exported for downstream projects' convenience
    build_instructions,
    configure_logging_from_env,
    register_file_exchange,
    resolve_auth_mode,
    wire_middleware_stack,
)
```

(Drops `ArtifactStore`, adds `register_file_exchange`. Alphabetical order preserved per ruff isort config.)

- [ ] **Step 2: Replace the artifact-store wiring (current lines 96-98).**

Current:

```python
    if transport != "stdio":
        artifact_store = ArtifactStore(ttl_seconds=3600)
        ArtifactStore.register_route(mcp, artifact_store)

    return mcp
```

Replace with:

```python
    register_file_exchange(
        mcp,
        namespace="{{ project_name }}",
        env_prefix=_ENV_PREFIX,
        transport="auto",
        # produces=("application/octet-stream",),  # uncomment + customise per project
        # consumer_sink=_my_sink,                  # uncomment if this server consumes file_refs
    )

    return mcp
```

**Why `transport="auto"` and not the function arg:** `make_server`'s `transport` parameter is `str` accepting `"stdio"|"http"|"sse"`, but the facade's `transport` is `Literal["http", "stdio", "auto"]`. Forwarding the value would either drop `"sse"` support or require a coercion expression. Letting the facade read `{PREFIX}_TRANSPORT` / `FASTMCP_TRANSPORT` matches how the rest of `fastmcp-pvl-core` resolves transport and avoids a mypy fight. CLI invocation (`cli.py`) sets the env var path consistently, so behaviour is identical.

- [ ] **Step 3: Update the docstring `transport` parameter description (current lines 47-49).**

Current:

```python
        transport: ``"stdio"`` / ``"http"`` / ``"sse"``.  HTTP-only
            features (artifact downloads) are wired only when transport
            != ``"stdio"``.
```

Replace with:

```python
        transport: ``"stdio"`` / ``"http"`` / ``"sse"``.  Used here for
            logging only; MCP File Exchange wiring is gated by
            ``register_file_exchange`` reading
            ``{{ env_prefix }}_TRANSPORT`` / ``FASTMCP_TRANSPORT`` and
            ``{{ env_prefix }}_FILE_EXCHANGE_ENABLED`` (default true on
            HTTP/SSE, false on stdio).
```

- [ ] **Step 4: Render the template locally and confirm the rendered file imports cleanly.**

```bash
rm -rf /tmp/smoke
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
grep -n 'register_file_exchange\|ArtifactStore' /tmp/smoke/src/*/server.py
```

Expected: one `register_file_exchange` import line, one `register_file_exchange(` call, **no** `ArtifactStore` references.

- [ ] **Step 5: Commit.**

```bash
git add src/{{python_module}}/server.py.jinja
git commit -m "feat(server-skeleton): adopt register_file_exchange facade

Replace direct ArtifactStore wiring with the spec-compliant facade
from fastmcp-pvl-core 1.2.0. The facade handles transport gating,
mounts the /artifacts/{token} route, advertises the experimental.
file_exchange capability, and registers create_download_link /
fetch_file MCP tools as appropriate.

Refs #72"
```

---

## Task 3: Bump `fastmcp-pvl-core` dependency floor

**Files:**
- Modify: `pyproject.toml.jinja:19`

- [ ] **Step 1: Replace the dependency line.**

Current (line 19):

```toml
    "fastmcp-pvl-core>=1.0,<2",
```

Replace with:

```toml
    "fastmcp-pvl-core>=1.2.0,<2",
```

- [ ] **Step 2: Render and verify.**

```bash
rm -rf /tmp/smoke
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
grep 'fastmcp-pvl-core' /tmp/smoke/pyproject.toml
```

Expected: `"fastmcp-pvl-core>=1.2.0,<2",`.

- [ ] **Step 3: Commit.**

```bash
git add pyproject.toml.jinja
git commit -m "feat(deps): require fastmcp-pvl-core>=1.2.0 for register_file_exchange

The 1.2.0 release adds register_file_exchange, FileRef, FileRefPreview,
and FileExchangeHandle, which the server skeleton now depends on.

Refs #72"
```

---

## Task 4: Update `CLAUDE.md.jinja:114`

**Files:**
- Modify: `CLAUDE.md.jinja:114`

- [ ] **Step 1: Replace the artifact-store mention.**

Current (line 114):

```markdown
- [`fastmcp-pvl-core`](https://github.com/pvliesdonk/fastmcp-pvl-core) — the Python library that provides `ServerConfig`, auth builders, middleware helpers, artifact store, and the `make_serve_parser` / `configure_logging_from_env` / `normalise_http_path` CLI helpers.
```

Replace with:

```markdown
- [`fastmcp-pvl-core`](https://github.com/pvliesdonk/fastmcp-pvl-core) — the Python library that provides `ServerConfig`, auth builders, middleware helpers, MCP File Exchange (`register_file_exchange`), and the `make_serve_parser` / `configure_logging_from_env` / `normalise_http_path` CLI helpers.
```

- [ ] **Step 2: Commit.**

```bash
git add CLAUDE.md.jinja
git commit -m "docs(claude-md): mention register_file_exchange in shared-infra list

Refs #72"
```

---

## Task 5: Update `docs/configuration.md.jinja`

**Files:**
- Modify: `docs/configuration.md.jinja`

- [ ] **Step 1: Replace the file's body** (it's only 16 lines today; rewriting beats trying to splice).

Replace the entire file with:

```markdown
# Configuration

{{ human_name }} is configured via environment variables with the
``{{ env_prefix }}_`` prefix.

## Common variables

See `fastmcp-pvl-core`'s README for the full list of universal
variables (`{{ env_prefix }}_TRANSPORT`, `{{ env_prefix }}_HOST`,
`{{ env_prefix }}_PORT`, `{{ env_prefix }}_HTTP_PATH`,
`{{ env_prefix }}_BASE_URL`, auth vars, etc.).

## MCP File Exchange

These variables control [MCP File Exchange](guides/file-exchange.md)
participation — pass-by-reference file transfer between co-deployed
servers (and HTTP fallback for remote clients). All are optional; the
defaults are sensible for both stdio and HTTP deployments.

| Variable | Default | Description |
|----------|---------|-------------|
| `{{ env_prefix }}_FILE_EXCHANGE_ENABLED` | `true` on HTTP/SSE, `false` on stdio | Master switch. Set `false` to opt out entirely. |
| `{{ env_prefix }}_FILE_EXCHANGE_PRODUCE` | `true` | Allow this server to mint `FileRef` objects via `handle.publish(...)`. |
| `{{ env_prefix }}_FILE_EXCHANGE_CONSUME` | `true` | Allow this server to fetch files via the `fetch_file` tool (requires a `consumer_sink=` argument to `register_file_exchange`). |
| `{{ env_prefix }}_FILE_EXCHANGE_TTL` | `3600` | Lifetime in seconds for download links and exchange-volume records. |
| `{{ env_prefix }}_BASE_URL` | unset | Public base URL of this server. Required for the `http` transfer method (the `create_download_link` tool builds URLs against it). |

The deployer also controls three **unprefixed** environment variables
shared by every co-deployed server:

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_EXCHANGE_DIR` | unset | Path to a directory shared between co-deployed MCP servers. When set, the `exchange://` transfer method activates; when unset, only the HTTP method is available. |
| `MCP_EXCHANGE_ID` | persisted in `.exchange-id` | Optional explicit exchange-group identifier; first server to start writes a UUID into `${MCP_EXCHANGE_DIR}/.exchange-id`, subsequent starts must agree. |
| `MCP_EXCHANGE_NAMESPACE` | the server's `namespace=` argument | Override the namespace used in `exchange://` URIs for this process. |

## Domain variables

Document your project-specific variables here.
```

- [ ] **Step 2: Render and verify.**

```bash
rm -rf /tmp/smoke
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
grep -c 'FILE_EXCHANGE' /tmp/smoke/docs/configuration.md
```

Expected: `4` (one per row in the prefixed table).

- [ ] **Step 3: Commit.**

```bash
git add docs/configuration.md.jinja
git commit -m "docs(configuration): document MCP File Exchange env vars

Add the prefixed FILE_EXCHANGE_* table and the unprefixed
MCP_EXCHANGE_* table the deployer controls.

Refs #72"
```

---

## Task 6: Create `docs/guides/file-exchange.md.jinja`

**Files:**
- Create: `docs/guides/file-exchange.md.jinja`

- [ ] **Step 1: Write the new file with this exact content.**

```markdown
# MCP File Exchange

{{ human_name }} participates in the **MCP File Exchange** convention
— a lightweight, spec-defined way for co-deployed MCP servers to pass
files to each other by reference instead of by base64-in-context.

The full specification lives in `fastmcp-pvl-core`'s docs:
[`docs/specs/file-exchange.md`](https://github.com/pvliesdonk/fastmcp-pvl-core/blob/main/docs/specs/file-exchange.md).
This page is the project-side guide: **what's wired by default, which
env vars to set, and how to publish or consume `FileRef` objects from
your tool bodies.**

## What's wired by default

`make_server()` calls `register_file_exchange()` once during startup.
That single call:

1. Mounts an `/artifacts/{token}` HTTP route (HTTP transport only).
2. Advertises the `experimental.file_exchange` capability on the MCP
   `initialize` response.
3. Registers two MCP tools when the surrounding env permits:
   - `create_download_link` — producer-side; mints time-limited HTTP
     URLs for `FileRef`s this server has published.
   - `fetch_file` — consumer-side; resolves a `FileRef` (via
     `exchange://` or `https://`) and hands the bytes to your sink.

By default the feature is **on** for HTTP/SSE deployments and **off**
for stdio. See [Configuration → MCP File Exchange](../configuration.md#mcp-file-exchange)
for the env-var matrix.

## The two patterns

### Augmented response (recommended)

The tool returns its normal output plus a `file_ref` field. Existing
clients ignore the field and keep working; file-exchange-aware
clients can use it.

```python
from fastmcp_pvl_core import FileRefPreview

result = await handle.publish(
    source=image_bytes,
    mime_type="image/png",
    preview=FileRefPreview(description=prompt, dimensions=(width, height)),
)
return {
    "image_id": image_id,
    "prompt": prompt,
    "dimensions": {"width": width, "height": height},
    "file_ref": result.to_dict(),
}
```

### Reference-only

The tool returns just the `FileRef` — appropriate when the file is
large and you do not want to spend tokens on inline data:

```python
file_ref = await handle.publish(source=pdf_path, mime_type="application/pdf")
return file_ref.to_dict()
```

## Producing files (`handle.publish`)

`register_file_exchange` returns a `FileExchangeHandle`. Capture it
in `make_server()` and stash it where your tool bodies can reach it
— most projects attach it to the lifespan state:

```python
# server.py
handle = register_file_exchange(
    mcp,
    namespace="{{ project_name }}",
    env_prefix=_ENV_PREFIX,
    transport="auto",
    produces=("image/png", "image/webp"),
)
mcp.file_exchange = handle  # any attribute name works; pick one and stick to it
```

Then in a tool body:

```python
from fastmcp_pvl_core import FileRefPreview

@mcp.tool
async def render(prompt: str, ctx: Context) -> dict[str, Any]:
    image_bytes = await _render(prompt)
    file_ref = await ctx.fastmcp.file_exchange.publish(
        source=image_bytes,
        mime_type="image/png",
        preview=FileRefPreview(description=prompt),
    )
    return {"prompt": prompt, "file_ref": file_ref.to_dict()}
```

`publish()` returns a `FileRef`. Call `.to_dict()` (or let your
return type adapter serialise it) before sending it back through MCP.

## Consuming files (`consumer_sink`)

Pass a `consumer_sink` to enable the `fetch_file` tool. The sink
receives the resolved bytes and a `FetchContext`, and returns a
`FetchResult`:

```python
from fastmcp_pvl_core import FetchContext, FetchResult

async def _store_in_vault(data: bytes, ctx: FetchContext) -> FetchResult:
    path = await _vault.write(data, mime_type=ctx.mime_type, name=ctx.suggested_filename)
    return FetchResult(stored_at=str(path), bytes_written=len(data))

handle = register_file_exchange(
    mcp,
    namespace="{{ project_name }}",
    env_prefix=_ENV_PREFIX,
    transport="auto",
    consumes=("image/*", "application/pdf"),
    consumer_sink=_store_in_vault,
)
```

`consumes=` is advertised in the capability declaration; the LLM and
peer servers use it to pick a destination for `fetch_file` calls.

## Co-deploying two servers (docker-compose)

The `exchange://` transfer method requires both servers to share a
volume mounted at `MCP_EXCHANGE_DIR`. Example:

```yaml
services:
  image-mcp:
    image: ghcr.io/example/image-mcp:latest
    environment:
      IMAGE_MCP_TRANSPORT: http
      IMAGE_MCP_BASE_URL: https://mcp.example.com/image
      MCP_EXCHANGE_DIR: /var/lib/mcp-exchange
    volumes:
      - mcp-exchange:/var/lib/mcp-exchange

  vault-mcp:
    image: ghcr.io/example/vault-mcp:latest
    environment:
      VAULT_MCP_TRANSPORT: http
      VAULT_MCP_BASE_URL: https://mcp.example.com/vault
      MCP_EXCHANGE_DIR: /var/lib/mcp-exchange
    volumes:
      - mcp-exchange:/var/lib/mcp-exchange

volumes:
  mcp-exchange:
```

Both containers see the same `.exchange-id` file, so they agree on
the exchange group automatically. When `image-mcp` publishes a file,
`vault-mcp` can fetch it via the `exchange://` URI without an HTTP
round-trip — the bytes never leave the shared volume.

When the servers are deployed apart (no shared volume), the spec's
`http` transfer method handles it: peers call `create_download_link`
on the producer, get a time-limited HTTPS URL, and pull the bytes
across the network.
```

- [ ] **Step 2: Render and confirm the file is generated.**

```bash
rm -rf /tmp/smoke
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
test -f /tmp/smoke/docs/guides/file-exchange.md && echo "exists" || echo "MISSING"
```

Expected: `exists`.

- [ ] **Step 3: Commit.**

```bash
git add docs/guides/file-exchange.md.jinja
git commit -m "docs(guides): add MCP File Exchange guide

Cover the two usage patterns (augmented response vs reference-only),
the publish/consume APIs, env vars, and a docker-compose snippet for
co-deployed servers sharing MCP_EXCHANGE_DIR.

Refs #72"
```

---

## Task 7: Add the new doc page to the mkdocs nav

**Files:**
- Modify: `mkdocs.yml.jinja`

- [ ] **Step 1: Insert the new nav entry.**

Locate the Guides block (currently lines 75-76):

```yaml
  - Guides:
      - Authentication: guides/authentication.md
```

Replace with:

```yaml
  - Guides:
      - Authentication: guides/authentication.md
      - File Exchange: guides/file-exchange.md
```

- [ ] **Step 2: Render and confirm the nav entry exists.**

```bash
rm -rf /tmp/smoke
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
grep 'guides/file-exchange.md' /tmp/smoke/mkdocs.yml
```

Expected: one match.

- [ ] **Step 3: Build the docs to confirm the link resolves.**

```bash
cd /tmp/smoke
uv sync --extra docs
uv run mkdocs build --strict 2>&1 | tail -20
cd /mnt/code/fastmcp-server-template
```

Expected: `INFO     -  Documentation built in ...s` with no `WARNING` lines about missing files. `--strict` makes any warning a build failure, so this catches a typo in the nav path.

- [ ] **Step 4: Commit.**

```bash
git add mkdocs.yml.jinja
git commit -m "docs(mkdocs): add File Exchange to Guides nav

Refs #72"
```

---

## Task 8: Update smoke tests

**Files:**
- Modify: `tests/test_smoke.py.jinja`

The existing `test_make_server_constructs` test asserts construction works in the default (stdio) configuration. We add two specific assertions: stdio omits the file-exchange tools, and an HTTP boot with an exchange dir advertises the capability.

- [ ] **Step 1: Replace the import block at the top of `tests/test_smoke.py.jinja` (current lines 1-12).**

Current imports include `Client`, `register_apps`, `make_server`. Add the test-helper import for tool listing — but FastMCP's `Client.list_tools()` is async and we already have an async `client` fixture, so no new imports are needed for that path. We do need `pathlib.Path` and `pytest.MonkeyPatch` for the new tests.

Replace the imports section:

```python
"""Smoke tests for {{ human_name }}."""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastmcp import Client

from {{ python_module }}._server_apps import register_apps
from {{ python_module }}.server import make_server
```

with:

```python
"""Smoke tests for {{ human_name }}."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastmcp import Client

from {{ python_module }}._server_apps import register_apps
from {{ python_module }}.server import make_server
```

- [ ] **Step 2: Add the stdio-default test (append at end of file).**

```python
async def test_file_exchange_disabled_on_stdio_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stdio default omits file-exchange tools and capability.

    Asserts the facade's transport-gating contract: with no
    ``{{ env_prefix }}_FILE_EXCHANGE_ENABLED`` override and stdio
    transport, neither ``create_download_link`` nor ``fetch_file`` is
    registered, and ``MCP_EXCHANGE_DIR`` (deployer-controlled) is also
    unset so the exchange-volume runtime stays disabled.
    """
    for var in (
        "{{ env_prefix }}_FILE_EXCHANGE_ENABLED",
        "{{ env_prefix }}_TRANSPORT",
        "FASTMCP_TRANSPORT",
        "MCP_EXCHANGE_DIR",
    ):
        monkeypatch.delenv(var, raising=False)

    server = make_server()
    async with Client(server) as client:
        tools = {t.name for t in await client.list_tools()}
    assert "create_download_link" not in tools
    assert "fetch_file" not in tools
```

- [ ] **Step 3: Add the http-with-exchange-dir test.**

```python
async def test_file_exchange_capability_when_http_and_exchange_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """HTTP transport + MCP_EXCHANGE_DIR registers the producer tool.

    With ``transport=http`` resolved (via the env var) and an
    exchange directory provided, ``register_file_exchange`` advertises
    the producer side: ``create_download_link`` is registered when
    ``{{ env_prefix }}_BASE_URL`` is set, and the exchange transfer
    method activates because ``MCP_EXCHANGE_DIR`` resolves.
    """
    monkeypatch.setenv("{{ env_prefix }}_TRANSPORT", "http")
    monkeypatch.setenv("{{ env_prefix }}_BASE_URL", "https://test.example.com")
    monkeypatch.setenv("MCP_EXCHANGE_DIR", str(tmp_path))
    monkeypatch.delenv("{{ env_prefix }}_FILE_EXCHANGE_ENABLED", raising=False)

    server = make_server(transport="http")
    async with Client(server) as client:
        tools = {t.name for t in await client.list_tools()}
    assert "create_download_link" in tools
```

- [ ] **Step 4: Render the smoke template into a temp project and run pytest.**

```bash
rm -rf /tmp/smoke
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
cd /tmp/smoke
uv sync --all-extras --dev
uv run pytest tests/test_smoke.py -x -v 2>&1 | tail -30
cd /mnt/code/fastmcp-server-template
```

Expected: 4 tests total (2 existing + 2 new), all passing. If the http test fails because `register_file_exchange` rejects an HTTPS BASE_URL with a non-resolvable host in CI, swap to `http://127.0.0.1:8000`.

- [ ] **Step 5: Commit.**

```bash
git add tests/test_smoke.py.jinja
git commit -m "test(smoke): assert file-exchange wiring respects transport gating

- stdio default: no create_download_link / fetch_file tools.
- http + MCP_EXCHANGE_DIR + BASE_URL: create_download_link is registered.

Refs #72"
```

---

## Task 9: Full local gate run on the rendered project

**Files:** none (verification step).

- [ ] **Step 1: Render fresh and run the full template gate.**

```bash
rm -rf /tmp/smoke
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
cd /tmp/smoke
uv sync --all-extras --dev
uv run ruff check .
uv run ruff format --check .
uv run mypy src/ tests/
uv run pytest -x -q
cd /mnt/code/fastmcp-server-template
```

Expected: all four commands exit 0. If `ruff format --check` complains, run `ruff format .` inside the rendered project to see the diff, then mirror the change in the corresponding `.jinja` source file (do **not** edit `/tmp/smoke` in place — the change won't survive). If `mypy` flags `register_file_exchange`, re-check Task 1 step 3.

- [ ] **Step 2: No commit for this task** (gate was already enforced per-task; this is the integrated re-run).

---

## Task 10: Open the PR

**Files:** none (PR machinery).

- [ ] **Step 1: Push the feature branch and open a draft PR.**

```bash
git push -u origin feat/adopt-register-file-exchange
gh pr create --draft --title "feat(template): adopt register_file_exchange in server skeleton" \
  --body "$(cat <<'EOF'
## Summary

- Replace `ArtifactStore` direct wiring in `server.py.jinja` with the spec-compliant `register_file_exchange()` facade from `fastmcp-pvl-core` 1.2.0.
- Bump the dep floor to `fastmcp-pvl-core>=1.2.0,<2`.
- Add `docs/guides/file-exchange.md.jinja` (template-owned per #29) and link it from the mkdocs nav.
- Document the new prefixed `_FILE_EXCHANGE_*` env vars and the unprefixed `MCP_EXCHANGE_*` deployer vars in `docs/configuration.md.jinja`.
- Update `CLAUDE.md.jinja` shared-infra blurb to mention the facade.
- Add two smoke-test assertions: stdio default omits file-exchange tools, http-with-exchange-dir advertises `create_download_link`.

## Out of scope

- Downstream project migrations (`markdown-vault-mcp`, `image-generator-mcp`, `paperless-mcp`) — separate issues per repo.
- Sentinel-block markers on the new doc page — deferred per the same call as #29; revisit if a downstream needs to extend it.

## Test plan

- [ ] `template-ci.yml` green on Python 3.11–3.14 (the CI renders the template with `tests/fixtures/smoke-answers.yml` and runs the generated project's gate).
- [ ] Manually verify `mkdocs build --strict` on the rendered project (covered in plan Task 7 step 3).
- [ ] Confirm `fastmcp-pvl-core==1.2.0` is on PyPI (otherwise CI fails at `uv sync`).

Closes #72
EOF
)"
```

- [ ] **Step 2: Address any bot-review findings.**

Per global agent instructions:

1. Wait for `claude-code-review.yml` and `gemini-code-assist` to post their reviews (Gemini auto-runs on PR open; if you push more commits, post a `/gemini review` comment to re-trigger).
2. **Read each bot's full review body**, not just the green check status. Search for "Still Open", "needs to be fixed", "Recommendation: fix items".
3. Treat "low-priority follow-up" / "non-blocking" / "nice to have" items as do-now-in-this-PR — there is no "later" in an agent loop.
4. Push fixes; iterate; re-trigger Gemini before flipping ready.

- [ ] **Step 3: Flip to ready when CI is green and both bots have come back clean on the latest commit.**

```bash
gh pr ready <N>
```

- [ ] **Step 4: Stop. Merge is human-only.** Per global agent instructions, never run `gh pr merge` autonomously, and never use `--admin` to bypass branch protection.

---

## Self-review

**Spec coverage** (against the issue's Acceptance section):

- ✅ `server.py.jinja` calls `register_file_exchange(...)` — Task 2.
- ✅ `pyproject.toml.jinja`: `fastmcp-pvl-core>=1.2.0,<2` — Task 3.
- ✅ `docs/guides/file-exchange.md.jinja` exists; linked from `mkdocs.yml.jinja` nav — Tasks 6, 7.
- ✅ `docs/configuration.md.jinja` lists the new env vars — Task 5.
- ✅ `CLAUDE.md.jinja` mentions the file-exchange facade — Task 4.
- ✅ Generated project (via `copier copy`) passes `pytest`, `ruff check`, `mypy --strict` — Task 9 (and per-task render+gate steps).

**Risks / open questions surfaced for the user:**

1. **pvl-core 1.2.0 prerequisite is satisfied** — release `v1.2.0` is live on PyPI as of 2026-04-27 16:49 UTC (commit `48f7301a`). No release-dispatch is needed before starting this plan.
2. The plan passes `transport="auto"` rather than forwarding `make_server`'s `transport` arg, because the facade types are stricter (`Literal["http", "stdio", "auto"]`) than `make_server`'s permissive `str` (which accepts `"sse"`). This is a deliberate deviation from the issue's literal snippet (`transport=transport`) — flagged in Task 2 step 2 commentary so the user can override if they prefer a coercion expression.
3. The plan does not stash the returned `FileExchangeHandle` in the template's `make_server()` (the scaffold has no producer tools). The doc page demonstrates `mcp.file_exchange = handle` for downstream projects. If you'd rather have the scaffold pre-stash the handle on a known attribute, add a one-line edit to Task 2 step 2 (`mcp.file_exchange = register_file_exchange(...)`) and a corresponding type annotation if mypy complains.
4. Smoke-test http path uses `MCP_EXCHANGE_DIR=tmp_path` — works because `FileExchange.from_env` accepts any existing directory and creates the `.exchange-id` file on first run. If CI's filesystem is read-only or the test ordering causes leftover state, swap to `monkeypatch.setenv` per-test plus a `tmp_path / "exchange"` subdir created by the test.
