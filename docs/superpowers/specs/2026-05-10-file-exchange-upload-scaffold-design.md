# File Exchange upload scaffold + DOMAIN-FILE-EXCHANGE sentinel

**Date:** 2026-05-10
**Scope:** `pvliesdonk/fastmcp-server-template`
**Closes:** #117 (upload scaffold), #118 (precursor sentinel refactor)
**Companion:** #119 (claude-desktop deployment guide backport — separate PR; the upload-direction `curl` walkthrough deferred there)

## Background

`fastmcp-pvl-core` 2.1.0 ships `register_file_exchange_upload` — the symmetric inbound mirror of the existing `register_file_exchange` (download direction). The template wires the download direction in `src/{{python_module}}/server.py.jinja` but has no upload-direction equivalent. Downstream servers that want inbound file uploads (markdown-vault-mcp, paperless inbox, scholar-mcp PDF intake) currently have to write the wiring from scratch.

A second, smaller problem must be fixed first to make the upload scaffold actually work: the existing `register_file_exchange(...)` call lives in template-owned territory, with inline-commented opt-in kwargs (`# produces=...`, `# consumer_sink=...`). Because the surrounding lines regenerate on `copier update`, any maintainer's "uncomment to opt in" edits silently revert. The same problem would bite a commented-out `register_file_exchange_upload(...)` block placed in template-owned territory. A downstream-owned sentinel block (preserved across `copier update`) is the only shape where uncomment-to-opt-in survives.

This spec bundles the precursor (#118) and the upload scaffold (#117) into one PR because (1) the precursor blocks the scaffold from being usable, and (2) CLAUDE.md's PR discipline permits one PR closing multiple issues when they're tightly coupled.

## Non-goals

- The agent-side `curl` walkthrough + one-time-token explanation. Belongs in `docs/deployment/claude-desktop.md.jinja`, which doesn't exist yet (#119 backports it from markdown-vault-mcp). The walkthrough is added in a follow-up after #119 lands.
- `consumes=` parameter for the upload helper. Tracked upstream as `pvliesdonk/fastmcp-pvl-core#66`.
- Top-level export of `BufferedReceiver` / `StreamReceiver` / `PreLinkValidator` aliases. Tracked upstream as `pvliesdonk/fastmcp-pvl-core#67`.
- `stream_receiver=` (streaming variant). The scaffold ships buffered only; streaming gets a one-line pointer in the guide.
- `accepts=` / `tool_tags=` / `upload_tool_name=` advanced kwargs. Defaults are correct for the common case; upstream docstring covers them when downstream needs them.

## Architecture

The change is concentrated in `src/{{python_module}}/server.py.jinja`: introduce a downstream-owned sentinel block, move the existing `register_file_exchange(...)` call inside it, and add a fully-commented `register_file_exchange_upload(...)` opt-in scaffold inside the same block. Everything else (configuration table, file-exchange guide, README pointer, CLAUDE.md.jinja inventory) reflects this in documentation.

The sentinel pair is named `DOMAIN-FILE-EXCHANGE-START` / `DOMAIN-FILE-EXCHANGE-END` — single block wrapping both directions. Rationale: download and upload are aspects of the same capability and already share the configuration-table heading (`MCP File Exchange`); a single block matches that grouping and avoids a fourth sentinel pair in `server.py`.

The receiver shape scaffolded is the buffered one (`receiver: BufferedReceiver`, `(UploadRecord, bytes) -> dict[str, Any] | Awaitable[dict[str, Any]]`). The streaming shape is mentioned only as a one-line pointer in the guide.

## File-by-file changes

### `src/{{python_module}}/server.py.jinja`

Replace lines 141–151 (the existing producer-comment + `register_file_exchange(...)` call) with a single `DOMAIN-FILE-EXCHANGE-START / END` sentinel block. The download call's body is byte-identical; only the surrounding sentinel + the new fully-commented upload block are added.

Final shape (excerpt):

```python
    # DOMAIN-FILE-EXCHANGE-START — file-exchange wiring (download direction
    # always; upload direction opt-in by uncommenting). Kept across copier
    # update so opt-in customisations (consumer_sink=, produces=, upload
    # receiver) survive subsequent template updates.
    #
    # To publish files from a tool body, capture the returned handle
    # — see docs/guides/file-exchange.md for the module-level singleton
    # pattern (e.g. ``_file_exchange = register_file_exchange(...)``).
    register_file_exchange(
        mcp,
        namespace="{{ project_name }}",
        env_prefix=_ENV_PREFIX,
        transport="auto",
        # produces=("application/octet-stream",),  # uncomment + customise per project
        # consumer_sink=_my_sink,                  # uncomment if this server consumes file_refs
    )

    # Optional upload direction — uncomment + flesh out the helpers below
    # to accept agent-pushed files via POST /<namespace>/uploads/{token}.
    # The route mounts only when transport is HTTP/SSE AND
    # {{ env_prefix }}_BASE_URL is set; sync receivers run in a thread.
    # See docs/guides/file-exchange.md for the full pattern.
    #
    # from typing import Any
    # from fastmcp_pvl_core import (
    #     UploadRecord,
    #     register_file_exchange_upload,
    # )
    #
    # def _validate_upload_target(target_id: str, extra: dict[str, Any] | None) -> None:
    #     """Pre-link validator: reject obviously bad target_ids in-band.
    #
    #     Runs inside create_upload_link before the token is minted, so an
    #     LLM gets a clean tool error rather than a wasted upload.
    #     """
    #     # Example: reject anything outside the domain's allowlist.
    #     # raise ValueError(f"target_id not allowed: {target_id}")
    #     pass
    #
    # def _upload_receiver(record: UploadRecord, body: bytes) -> dict[str, Any]:
    #     """Commit the uploaded bytes. Raise ValueError → 400, FileExistsError → 409,
    #     anything else → 500 (with traceback logged)."""
    #     ...
    #     return {"path": record.target_id, "size_bytes": len(body)}
    #
    # register_file_exchange_upload(
    #     mcp,
    #     namespace="{{ project_name }}",
    #     env_prefix=_ENV_PREFIX,
    #     receiver=_upload_receiver,
    #     pre_link_validator=_validate_upload_target,
    # )
    # DOMAIN-FILE-EXCHANGE-END

    return mcp
```

Notes:
- `from typing import Any` is in the commented import block because the file doesn't currently import `Any`. A maintainer who uncomments needs it.
- Buffered receiver only; `stream_receiver=` is documented in the guide as a power-user pointer.
- The `# To publish files from a tool body...` producer-pattern hint moves inside the sentinel (now downstream-owned). Same words; only relocated.

### `pyproject.toml.jinja`

Single-line bump on line 19:

```diff
-    "fastmcp-pvl-core>=2.0.0,<3",
+    "fastmcp-pvl-core>=2.1.0,<3",
```

The `[debug]` extra at line 30 inherits this range — no change needed there.

### `docs/configuration.md.jinja`

Insert four new rows in the existing **MCP File Exchange** table between `FILE_EXCHANGE_TTL` and `BASE_URL`, and tweak the `BASE_URL` row to mention the upload-tool dependency:

```diff
 | `{{ env_prefix }}_FILE_EXCHANGE_TTL` | `3600` | Lifetime in seconds for download links and exchange-volume records. |
+| `{{ env_prefix }}_UPLOAD_ENABLED` | `true` on HTTP/SSE, `false` on stdio | Master switch for the upload direction. **Only effective when `register_file_exchange_upload(...)` is uncommented in `server.py`** — without that call, no upload route is mounted regardless of this var. See [the guide](guides/file-exchange.md#uploading-files-receiver). |
+| `{{ env_prefix }}_UPLOAD_MAX_BYTES` | `10485760` (10 MiB) | Maximum POST body size for the upload route. Bodies exceeding this return HTTP 413. |
+| `{{ env_prefix }}_UPLOAD_TTL` | `300` | Default lifetime in seconds for upload links. Caller-requested TTL is clamped to `{{ env_prefix }}_UPLOAD_TTL_MAX`. |
+| `{{ env_prefix }}_UPLOAD_TTL_MAX` | `3600` | Operator ceiling for caller-requested upload-link TTL. |
-| `{{ env_prefix }}_BASE_URL` | unset | Public base URL of this server. Required for the `http` transfer method (the `create_download_link` tool builds URLs against it). Also referenced by the OIDC guide and the universal-variables list above — set it once and every consumer picks it up. |
+| `{{ env_prefix }}_BASE_URL` | unset | Public base URL of this server. Required for the `http` transfer method — the `create_download_link` tool and (when upload is wired) the `create_upload_link` tool both build URLs against it. Also referenced by the OIDC guide and the universal-variables list above — set it once and every consumer picks it up. |
```

`UPLOAD_ENABLED` description mirrors the existing `FILE_EXCHANGE_CONSUME` row's "**Only effective when X is wired**" callout — symmetric framing makes the opt-in dependency obvious. "true on HTTP/SSE, false on stdio" is the net-effect description (the upstream env-var default is `"true"` always; stdio + missing `BASE_URL` are separate gates inside the helper) — same wording as the download-side row keeps the table consistent.

### `docs/guides/file-exchange.md.jinja`

New section inserted between **Consuming files** and **Co-deploying two servers**. Mirrors the parallel structure of the two existing direction sections.

```markdown
## Uploading files (`receiver=`)

The download direction is producer-driven: this server `publish()`es
a file, and a peer (or LLM tool) fetches it. The **upload direction**
is the inverse — an agent or peer pushes bytes into this server, and
a **receiver** in your code commits them.

Wire it by uncommenting the `register_file_exchange_upload(...)`
block in `src/{{ python_module }}/server.py` (inside the
`DOMAIN-FILE-EXCHANGE-START / END` sentinel) and supplying a
`receiver`:

```python
from typing import Any
from fastmcp_pvl_core import UploadRecord, register_file_exchange_upload

def _upload_receiver(record: UploadRecord, body: bytes) -> dict[str, Any]:
    # record.target_id, record.extra, record.max_bytes available.
    path = _vault.write(record.target_id, body)
    return {"path": str(path), "size_bytes": len(body)}

register_file_exchange_upload(
    mcp,
    namespace="{{ project_name }}",
    env_prefix=_ENV_PREFIX,
    receiver=_upload_receiver,
)
```

Once registered, an LLM-visible `create_upload_link` tool appears.
The agent calls it with a `target_id` (and optional `extra`,
`ttl_seconds`, `max_bytes`); the helper mints a one-time HTTPS
`POST /<namespace>/uploads/{token}` URL and returns it. The agent
POSTs the bytes; the route hands them to your receiver.

### Pre-link validation

To reject bad `target_id`s **before** the token is minted — so an LLM
sees a clean tool error rather than wastes a round-trip — supply
`pre_link_validator`:

```python
def _validate_upload_target(target_id: str, extra: dict[str, Any] | None) -> None:
    if not target_id.startswith("inbox/"):
        raise ValueError(f"target_id must begin with 'inbox/': {target_id}")

register_file_exchange_upload(
    mcp,
    namespace="{{ project_name }}",
    env_prefix=_ENV_PREFIX,
    receiver=_upload_receiver,
    pre_link_validator=_validate_upload_target,
)
```

Raising `ValueError` surfaces the message verbatim to the caller.
Other exceptions also propagate but are logged at ERROR with a
`non-ValueError` marker so operators distinguish bugs from
caller-input errors. Sync validators run in `asyncio.to_thread`
automatically; `async def` validators run on the loop.

### Receiver error contract

| Exception | Response | When to use |
|-----------|----------|-------------|
| `ValueError` | `400` Bad Request | Request body fails domain validation. |
| `FileExistsError` | `409` Conflict | `target_id` collides with existing data. |
| Anything else | `500` Internal Server Error | Server-side bug. Traceback is logged. |

A returned `dict[str, Any]` produces `200` and is JSON-encoded into
the response. Sync receivers run in `asyncio.to_thread` (blocking I/O
does not stall the loop); `async def` receivers run on the loop.

Tokens are **one-time** — every non-2xx response burns the link;
retries call `create_upload_link` again. For uploads too large to
buffer, use `stream_receiver=` (`AsyncIterator[bytes]` shape;
documented in the upstream `fastmcp-pvl-core` README — the template
scaffolds the buffered shape only).

See [Configuration → MCP File Exchange](../configuration.md#mcp-file-exchange)
for the env-var matrix.
```

Section anchor `#uploading-files-receiver` is what the configuration table links to.

### `README.md.jinja`

New `### File exchange` subsection after the existing `### Server info` (under `## Quick start`):

```markdown
### File exchange

The server scaffolds [MCP File Exchange](docs/guides/file-exchange.md)
wiring — download direction is registered by default (active on
HTTP/SSE, transparent on stdio); an upload direction ships fully
commented-out for opt-in via `register_file_exchange_upload(...)`.
See the guide for producing / consuming / uploading patterns and the
env-var matrix.
```

### `CLAUDE.md.jinja`

Two edits:

1. Update the Shared Infrastructure inventory bullet (line 135) so the upload helper is named alongside the download one:

```diff
-- [`fastmcp-pvl-core`](https://github.com/pvliesdonk/fastmcp-pvl-core) — the Python library that provides `ServerConfig`, auth builders, middleware helpers, MCP File Exchange (`register_file_exchange`), and the `make_serve_parser` / `configure_logging_from_env` / `normalise_http_path` CLI helpers.
+- [`fastmcp-pvl-core`](https://github.com/pvliesdonk/fastmcp-pvl-core) — the Python library that provides `ServerConfig`, auth builders, middleware helpers, MCP File Exchange (`register_file_exchange` + `register_file_exchange_upload`), and the `make_serve_parser` / `configure_logging_from_env` / `normalise_http_path` CLI helpers.
```

2. New `## File Exchange` section between `## Server Info Tool` and `## Shared Infrastructure`:

```markdown
## File Exchange (`register_file_exchange` + opt-in upload)

`make_server()` calls `register_file_exchange(...)` inside the
`DOMAIN-FILE-EXCHANGE-START` / `DOMAIN-FILE-EXCHANGE-END` sentinel in
`src/{{ python_module }}/server.py`. The block is preserved across
`copier update`, so opt-in customisations (`produces=`, `consumer_sink=`,
or uncommenting the `register_file_exchange_upload(...)` block for the
inbound direction) survive subsequent template updates. Download direction
is wired unconditionally; upload direction is opt-in by uncommenting
the fully commented `register_file_exchange_upload(...)` call and
fleshing out `_upload_receiver` / `_validate_upload_target`. See
[`docs/guides/file-exchange.md`](docs/guides/file-exchange.md) for the
full pattern.
```

## Verification

- `template-ci.yml` renders `tests/fixtures/smoke-answers.yml` against HEAD on Python 3.11–3.14 and runs the generated project's gate (lint, format, mypy, pytest). The gate must remain green.
- Local render-and-gate sequence per `CLAUDE.md`:
  ```bash
  rm -rf /tmp/smoke
  uv run --no-project --with copier copier copy --trust --defaults \
    --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
  cd /tmp/smoke
  uv sync --all-extras --all-groups
  uv run ruff check . && uv run ruff format --check .
  uv run mypy src/ tests/ && uv run pytest -x -q
  ```
- Per CLAUDE.md "local gate misses the downstream-workflow-gate CI job" — also run `uv run mkdocs build --strict` from `/tmp/smoke` after `uv sync` since this PR adds doc content. Broken intra-doc anchors in the configuration → file-exchange-guide cross-link would be caught here.
- Manual sentinel-shape verification on the rendered `server.py`:
  - `grep -c 'DOMAIN-FILE-EXCHANGE-START' /tmp/smoke/src/<module>/server.py` returns `1`.
  - `grep -c 'DOMAIN-FILE-EXCHANGE-END' /tmp/smoke/src/<module>/server.py` returns `1`.
  - The `register_file_exchange(...)` call is between them.
  - `register_file_exchange_upload` appears only inside comments, never as an executed call.
- pvl-core version pin: `grep 'fastmcp-pvl-core>=' /tmp/smoke/pyproject.toml` shows `>=2.1.0,<3`.

## Risks

- **Anchor stability for `#uploading-files-receiver`**: mkdocs-material's slugger strips parentheses and special chars, so `## Uploading files (`receiver=`)` becomes `#uploading-files-receiver`. Verified against existing pattern: `## Producing files (`handle.publish`)` slugs to `#producing-files-handlepublish` (already linked from elsewhere in the same guide). The slug semantics are stable.
- **Sentinel name collision**: existing sentinels in `server.py.jinja` are `DOMAIN-WIRING`, `DOMAIN-UPSTREAM`. `DOMAIN-FILE-EXCHANGE` is new and unique. Confirmed by grep across `*.jinja` files in the template root.
- **Upstream API drift**: the buffered-receiver / pre-link-validator signatures are pinned to fastmcp-pvl-core 2.1.0 (verified by reading upstream source at `src/fastmcp_pvl_core/file_exchange.py`, `_file_exchange_runtime.py`, `_token_store.py` against tag `v2.1.0`). The `>=2.1.0,<3` SemVer pin in `pyproject.toml.jinja` is the contract; signature changes would arrive in 3.x and be addressed then.
- **`_my_sink` / `_vault` placeholder identifiers**: existing scaffold pattern (the `_my_sink` placeholder already lives in template-owned territory in the current file, just commented inline). The new scaffold reuses the same convention. Maintainers fill these in as part of opt-in.

## Open questions

None — placement, sentinel shape, scope split (#117 + #118 bundled, #119 separate), and walkthrough deferral all decided in brainstorming.
