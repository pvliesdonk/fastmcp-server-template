# File Exchange upload scaffold + DOMAIN-FILE-EXCHANGE sentinel — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scaffold opt-in `register_file_exchange_upload(...)` wiring in `fastmcp-server-template`, after first wrapping the existing `register_file_exchange(...)` call in a downstream-owned `DOMAIN-FILE-EXCHANGE` sentinel block so opt-in customisations actually survive `copier update`.

**Architecture:** Six template files change. The meat is `server.py.jinja`, which gets a sentinel pair around `register_file_exchange(...)` (precursor #118) and a fully-commented `register_file_exchange_upload(...)` block inside the same sentinel (#117 main). Supporting changes: `pyproject.toml.jinja` pin bump to `>=2.1.0,<3`; four new env-var rows in `docs/configuration.md.jinja`; new "Uploading files" section in the file-exchange guide; brief `### File exchange` pointer in the README; CLAUDE.md.jinja inventory bullet update + new `## File Exchange` section.

**Tech Stack:** copier (Jinja2 templates), `fastmcp-pvl-core` 2.1.0 (newly required), uv (rendered project's package manager), mkdocs-material (rendered project's docs).

**Spec:** [`docs/superpowers/specs/2026-05-10-file-exchange-upload-scaffold-design.md`](../specs/2026-05-10-file-exchange-upload-scaffold-design.md)

**Closes:** #117, #118 — bundled in one PR per spec rationale.

**Branch:** `feat/file-exchange-upload-117` (already created, fresh from `origin/main`).

---

## Notes for the implementer

This is a copier template, not a runnable project. There are no unit tests *for the template itself* — the test surface is `template-ci.yml`, which renders the template against `tests/fixtures/smoke-answers.yml` and runs the *generated* project's full gate (lint, format, mypy, pytest, mkdocs build). Locally you must replicate this manually after each non-trivial commit.

The local render-and-gate sequence (referred to as **the gate** below):

```bash
rm -rf /tmp/smoke
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
cd /tmp/smoke
uv sync --all-extras --all-groups
uv run ruff check . && uv run ruff format --check .
uv run mypy src/ tests/
uv run pytest -x -q
uv run mkdocs build --strict
cd -
```

Critical: `copier copy --vcs-ref=HEAD` reads from the **last committed** tree, not the working tree. **Commit before rendering, every time.** If the gate fails, fix, create a new commit (don't amend across tasks — separate logical changes deserve separate commits), re-render, re-verify.

Each task below has its own minimal verification step. The final task (Task 8) is the cumulative gate + local review circus + PR open.

---

## Task 1: Wrap `register_file_exchange` in `DOMAIN-FILE-EXCHANGE` sentinel (#118 precursor)

**Files:**
- Modify: `src/{{python_module}}/server.py.jinja:141-151`

This is a pure structural refactor: the `register_file_exchange(...)` call body and surrounding producer-comment hint are unchanged; only their context shifts from template-owned territory to a downstream-owned sentinel block. The rendered `server.py` should be byte-identical except for two new sentinel comment lines plus updated wording of the producer-comment hint.

**Why before Task 2:** the sentinel block is the *home* for the upload scaffold added in Task 2. Doing the refactor first keeps Task 1's diff small and reviewable as a no-behavior-change change.

- [ ] **Step 1: Edit `src/{{python_module}}/server.py.jinja`**

Replace lines 141-151 (the existing producer-comment block + `register_file_exchange(...)` call). Before:

```python
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
```

After:

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
    # DOMAIN-FILE-EXCHANGE-END
```

The `register_file_exchange(...)` call is byte-identical. Only the surrounding two sentinel-comment lines are added. (The trailing `# DOMAIN-FILE-EXCHANGE-END` line will move down in Task 2 once the upload scaffold is inserted between it and the `register_file_exchange` call — that's fine; this task leaves it directly under the call for now.)

- [ ] **Step 2: Commit**

```bash
git add src/'{{python_module}}'/server.py.jinja
git -c commit.gpgsign=false commit -m "$(cat <<'EOF'
refactor(server): wrap register_file_exchange in DOMAIN-FILE-EXCHANGE sentinel (#118)

Move the existing register_file_exchange(...) call into a downstream-owned
sentinel block so opt-in kwargs (produces=, consumer_sink=) survive
subsequent copier updates. No behavior change in the rendered scaffold;
only the post-customisation lifecycle changes.

This is the precursor for #117 (upload scaffold), which needs the same
sentinel as the home for its commented-out register_file_exchange_upload
block.
EOF
)"
```

- [ ] **Step 3: Render and verify the gate is green**

Run **the gate** as described in "Notes for the implementer". Expected: all green (no behavior change).

- [ ] **Step 4: Spot-check the rendered server.py**

```bash
grep -nE 'DOMAIN-FILE-EXCHANGE-(START|END)|register_file_exchange\b' /tmp/smoke/src/*/server.py
```

Expected output (line numbers will vary):
```
NN:    # DOMAIN-FILE-EXCHANGE-START — file-exchange wiring (download direction
NN:    register_file_exchange(
NN:    # DOMAIN-FILE-EXCHANGE-END
```

Both sentinels appear exactly once; `register_file_exchange(` appears between them.

---

## Task 2: Add commented-out `register_file_exchange_upload` scaffold (#117 wiring)

**Files:**
- Modify: `src/{{python_module}}/server.py.jinja` — insert before `# DOMAIN-FILE-EXCHANGE-END`

- [ ] **Step 1: Edit `src/{{python_module}}/server.py.jinja`**

Find the block added in Task 1:

```python
    register_file_exchange(
        mcp,
        namespace="{{ project_name }}",
        env_prefix=_ENV_PREFIX,
        transport="auto",
        # produces=("application/octet-stream",),  # uncomment + customise per project
        # consumer_sink=_my_sink,                  # uncomment if this server consumes file_refs
    )
    # DOMAIN-FILE-EXCHANGE-END
```

Insert the commented-out upload scaffold between the closing `)` of `register_file_exchange(...)` and the `# DOMAIN-FILE-EXCHANGE-END` line. The result:

```python
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
```

Critical: every line of the new block must start with `#` (commented out). The comment includes the imports — a maintainer who uncomments needs `from typing import Any` and `from fastmcp_pvl_core import UploadRecord, register_file_exchange_upload`. Both are commented in.

- [ ] **Step 2: Commit**

```bash
git add src/'{{python_module}}'/server.py.jinja
git -c commit.gpgsign=false commit -m "$(cat <<'EOF'
feat(server): scaffold register_file_exchange_upload opt-in block (#117)

Add a fully-commented register_file_exchange_upload(...) block with
stub _upload_receiver / _validate_upload_target inside the new
DOMAIN-FILE-EXCHANGE sentinel. Stays commented by default; downstream
opts in by uncommenting and fleshing out the receiver/validator bodies.

Buffered receiver shape only; stream_receiver= is a power-user variant
documented in the upstream pvl-core README.
EOF
)"
```

- [ ] **Step 3: Render and verify the gate is green**

Run **the gate**. Expected: all green. The new lines are inert (comments only) — they cannot break lint, format, mypy, pytest, or mkdocs.

- [ ] **Step 4: Spot-check the rendered server.py**

```bash
grep -cE '^[[:space:]]+# register_file_exchange_upload' /tmp/smoke/src/*/server.py
```

Expected: `1` (the commented call).

```bash
grep -E 'register_file_exchange_upload' /tmp/smoke/src/*/server.py | grep -v '^[^#]*#'
```

Expected: empty output. (`register_file_exchange_upload` appears ONLY in commented lines.)

```bash
grep -nE 'DOMAIN-FILE-EXCHANGE-(START|END)' /tmp/smoke/src/*/server.py
```

Expected: each sentinel appears exactly once; END appears after START.

---

## Task 3: Bump `fastmcp-pvl-core` pin to `>=2.1.0,<3`

**Files:**
- Modify: `pyproject.toml.jinja:19`

- [ ] **Step 1: Edit `pyproject.toml.jinja`**

Change line 19 from:

```toml
    "fastmcp-pvl-core>=2.0.0,<3",
```

to:

```toml
    "fastmcp-pvl-core>=2.1.0,<3",
```

The `[debug]` extra at line 30 (`debug = ["fastmcp-pvl-core[debug]"]`) inherits this range — no edit needed there.

- [ ] **Step 2: Commit**

```bash
git add pyproject.toml.jinja
git -c commit.gpgsign=false commit -m "$(cat <<'EOF'
chore(deps): bump fastmcp-pvl-core minimum to 2.1.0 (#117)

Required for register_file_exchange_upload + UploadRecord, exported
from fastmcp_pvl_core in 2.1.0. Already published to PyPI.
EOF
)"
```

- [ ] **Step 3: Render and verify the gate is green**

Run **the gate**. Critical step: `uv sync --all-extras --all-groups` will fetch 2.1.0; the gate confirms there are no transitive resolution conflicts in the rendered project.

```bash
grep -E 'fastmcp-pvl-core' /tmp/smoke/pyproject.toml
```

Expected:
```
    "fastmcp-pvl-core>=2.1.0,<3",
debug = ["fastmcp-pvl-core[debug]"]
```

```bash
grep -E '^fastmcp-pvl-core==' /tmp/smoke/uv.lock | head -1
```

Expected: `fastmcp-pvl-core==2.1.0` (or the latest 2.x).

---

## Task 4: Add upload env-var rows to `docs/configuration.md.jinja`

**Files:**
- Modify: `docs/configuration.md.jinja:25-26` (in the **MCP File Exchange** table)

- [ ] **Step 1: Edit `docs/configuration.md.jinja`**

Find the row:

```markdown
| `{{ env_prefix }}_FILE_EXCHANGE_TTL` | `3600` | Lifetime in seconds for download links and exchange-volume records. |
```

After this row, insert four new rows. Then immediately below those four, replace the existing `BASE_URL` row.

Before (lines 25-26 of `docs/configuration.md.jinja`):

```markdown
| `{{ env_prefix }}_FILE_EXCHANGE_TTL` | `3600` | Lifetime in seconds for download links and exchange-volume records. |
| `{{ env_prefix }}_BASE_URL` | unset | Public base URL of this server. Required for the `http` transfer method (the `create_download_link` tool builds URLs against it). Also referenced by the OIDC guide and the universal-variables list above — set it once and every consumer picks it up. |
```

After:

```markdown
| `{{ env_prefix }}_FILE_EXCHANGE_TTL` | `3600` | Lifetime in seconds for download links and exchange-volume records. |
| `{{ env_prefix }}_UPLOAD_ENABLED` | `true` on HTTP/SSE, `false` on stdio | Master switch for the upload direction. **Only effective when `register_file_exchange_upload(...)` is uncommented in `server.py`** — without that call, no upload route is mounted regardless of this var. See [the guide](guides/file-exchange.md#uploading-files-receiver). |
| `{{ env_prefix }}_UPLOAD_MAX_BYTES` | `10485760` (10 MiB) | Maximum POST body size for the upload route. Bodies exceeding this return HTTP 413. |
| `{{ env_prefix }}_UPLOAD_TTL` | `300` | Default lifetime in seconds for upload links. Caller-requested TTL is clamped to `{{ env_prefix }}_UPLOAD_TTL_MAX`. |
| `{{ env_prefix }}_UPLOAD_TTL_MAX` | `3600` | Operator ceiling for caller-requested upload-link TTL. |
| `{{ env_prefix }}_BASE_URL` | unset | Public base URL of this server. Required for the `http` transfer method — the `create_download_link` tool and (when upload is wired) the `create_upload_link` tool both build URLs against it. Also referenced by the OIDC guide and the universal-variables list above — set it once and every consumer picks it up. |
```

The four upload rows go in the order listed (`UPLOAD_ENABLED`, `UPLOAD_MAX_BYTES`, `UPLOAD_TTL`, `UPLOAD_TTL_MAX`). The `BASE_URL` row is rewritten in place: only the second sentence of the description changes (mentions `create_upload_link` alongside `create_download_link`).

- [ ] **Step 2: Commit**

```bash
git add docs/configuration.md.jinja
git -c commit.gpgsign=false commit -m "$(cat <<'EOF'
docs(config): document upload env vars (#117)

Adds UPLOAD_ENABLED, UPLOAD_MAX_BYTES, UPLOAD_TTL, UPLOAD_TTL_MAX rows
to the MCP File Exchange table, and extends the BASE_URL row to mention
create_upload_link alongside create_download_link.
EOF
)"
```

- [ ] **Step 3: Verify mkdocs build is clean**

```bash
cd /tmp/smoke && uv run mkdocs build --strict 2>&1 | tail -20 ; cd -
```

Expected: `INFO    -  Documentation built in N.NNs` with no errors.

If the smoke render is stale (e.g. `--vcs-ref=HEAD` cached), re-run **the gate** in full from "Notes for the implementer".

- [ ] **Step 4: Spot-check the rendered configuration page**

```bash
grep -E 'UPLOAD_(ENABLED|MAX_BYTES|TTL|TTL_MAX)' /tmp/smoke/docs/configuration.md
```

Expected: 4 lines, one per env var, with the env-prefix substituted.

---

## Task 5: Add "Uploading files" section to `docs/guides/file-exchange.md.jinja`

**Files:**
- Modify: `docs/guides/file-exchange.md.jinja` — insert section between **Consuming files** and **Co-deploying two servers**

- [ ] **Step 1: Locate the insertion point**

The new section goes between the existing `## Consuming files (`consumer_sink`)` section (currently ending around line 150) and `## Co-deploying two servers (docker-compose)` (starting around line 152). Identify by:

```bash
grep -nE '^## ' docs/guides/file-exchange.md.jinja
```

Expected sections (in order):
- `## What's wired by default`
- `## The two patterns`
- `## Producing files (`handle.publish`)`
- `## Consuming files (`consumer_sink`)`
- `## Co-deploying two servers (docker-compose)`

Insert between **Consuming files** and **Co-deploying two servers**. The insertion is one blank line after the last paragraph of Consuming files.

- [ ] **Step 2: Edit `docs/guides/file-exchange.md.jinja`**

Insert the following section verbatim between Consuming files and Co-deploying two servers:

````markdown
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

````

The trailing four backticks above are markdown — the inserted section ends with the line `for the env-var matrix.` followed by one blank line (the section's natural end). Do **not** copy the four-backtick fence into the file; it only delimits the code block in this plan document.

- [ ] **Step 3: Commit**

```bash
git add docs/guides/file-exchange.md.jinja
git -c commit.gpgsign=false commit -m "$(cat <<'EOF'
docs(guide): add Uploading files section to file-exchange guide (#117)

Mirrors the Producing/Consuming sections' parallel structure. Covers
the receiver pattern, pre-link validator, receiver error contract,
one-time-token semantics, and a one-line stream_receiver= pointer.

The agent-side curl walkthrough is intentionally absent — it belongs
in docs/deployment/claude-desktop.md (#119, separate PR).
EOF
)"
```

- [ ] **Step 4: Verify mkdocs build is clean and the cross-link resolves**

Run **the gate** in full (the smoke tree may need a re-render after committing). Then:

```bash
grep -nE 'uploading-files-receiver|#mcp-file-exchange' /tmp/smoke/docs/guides/file-exchange.md /tmp/smoke/docs/configuration.md 2>&1
```

Expected: at least two lines — one in `configuration.md` referencing `#uploading-files-receiver`, and one in `file-exchange.md` referencing `#mcp-file-exchange` (the back-link to the configuration table).

If `mkdocs build --strict` complains about a broken anchor, the slug for `## Uploading files (`receiver=`)` may differ from `uploading-files-receiver`. Verify with:

```bash
grep -E '^<h2 id=' /tmp/smoke/site/guides/file-exchange/index.html
```

The expected `<h2 id="uploading-files-receiver">` confirms the slug. If it differs, update both the inserted section's anchor reference (in this task) and the `[the guide]` link in `docs/configuration.md.jinja` (Task 4) — they must match.

---

## Task 6: Add `### File exchange` subsection to `README.md.jinja`

**Files:**
- Modify: `README.md.jinja` — insert after `### Server info` (around line 96)

- [ ] **Step 1: Edit `README.md.jinja`**

Find the existing `### Server info` subsection (under `## Quick start`). It ends with the paragraph mentioning `register_server_info_tool` and links to `CLAUDE.md#server-info-tool-get_server_info`. Insert a new `### File exchange` subsection immediately after it, before `## Configuration`.

The inserted block:

```markdown
### File exchange

The server scaffolds [MCP File Exchange](docs/guides/file-exchange.md)
wiring — download direction is registered by default (active on
HTTP/SSE, transparent on stdio); an upload direction ships fully
commented-out for opt-in via `register_file_exchange_upload(...)`.
See the guide for producing / consuming / uploading patterns and the
env-var matrix.
```

Surround with one blank line above (separating it from the Server info subsection's last paragraph) and one blank line below (separating it from `## Configuration`).

- [ ] **Step 2: Commit**

```bash
git add README.md.jinja
git -c commit.gpgsign=false commit -m "$(cat <<'EOF'
docs(readme): add File exchange Quick-start subsection (#117)

Brief pointer to docs/guides/file-exchange.md so users discover both
the download-default and upload-opt-in flows from the README.
EOF
)"
```

- [ ] **Step 3: Spot-check the rendered README**

```bash
grep -nE '^### (Server info|File exchange)|^## Configuration' /tmp/smoke/README.md
```

Expected (line numbers vary, order is the requirement):
```
NN:### Server info
NN:### File exchange
NN:## Configuration
```

If `mkdocs build --strict` is sensitive to README structure (it's not by default but the smoke project's `mkdocs.yml.jinja` may reference it), re-run **the gate** in full. README changes do not normally affect mkdocs unless the README is included in the docs nav.

---

## Task 7: Update `CLAUDE.md.jinja` — inventory bullet + new File Exchange section

**Files:**
- Modify: `CLAUDE.md.jinja:135` (inventory bullet)
- Modify: `CLAUDE.md.jinja:130-131` (insert new `## File Exchange` section)

- [ ] **Step 1: Update the Shared Infrastructure inventory bullet**

Find line 135:

```markdown
- [`fastmcp-pvl-core`](https://github.com/pvliesdonk/fastmcp-pvl-core) — the Python library that provides `ServerConfig`, auth builders, middleware helpers, MCP File Exchange (`register_file_exchange`), and the `make_serve_parser` / `configure_logging_from_env` / `normalise_http_path` CLI helpers.
```

Replace with:

```markdown
- [`fastmcp-pvl-core`](https://github.com/pvliesdonk/fastmcp-pvl-core) — the Python library that provides `ServerConfig`, auth builders, middleware helpers, MCP File Exchange (`register_file_exchange` + `register_file_exchange_upload`), and the `make_serve_parser` / `configure_logging_from_env` / `normalise_http_path` CLI helpers.
```

Single change: `(`register_file_exchange`)` → `(`register_file_exchange` + `register_file_exchange_upload`)`.

- [ ] **Step 2: Insert new `## File Exchange` section between `## Server Info Tool` and `## Shared Infrastructure`**

The Server Info Tool section ends at line 129 (the paragraph about `DOMAIN-UPSTREAM-START / END`). The Shared Infrastructure section begins at line 131. Insert the new section between them, with one blank line above and one below:

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

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md.jinja
git -c commit.gpgsign=false commit -m "$(cat <<'EOF'
docs(claude-md): document DOMAIN-FILE-EXCHANGE sentinel + upload helper (#117, #118)

Adds a parallel section to ## Server Info Tool covering the new
DOMAIN-FILE-EXCHANGE sentinel and its opt-in customisation surface,
and extends the Shared Infrastructure inventory bullet to name the
upload helper alongside the download helper.
EOF
)"
```

- [ ] **Step 4: Spot-check the rendered CLAUDE.md**

```bash
grep -nE '^## (Server Info Tool|File Exchange|Shared Infrastructure)' /tmp/smoke/CLAUDE.md
```

Expected (order is the requirement):
```
NN:## Server Info Tool (`get_server_info`)
NN:## File Exchange (`register_file_exchange` + opt-in upload)
NN:## Shared Infrastructure
```

```bash
grep -E 'register_file_exchange.*register_file_exchange_upload' /tmp/smoke/CLAUDE.md
```

Expected: at least one line (the inventory bullet showing both helpers).

---

## Task 8: Final verification, local review circus, follow-up tracker, open PR

This is the longest task — it covers cumulative gate verification, the mandatory local-review circus per `~/.claude/CLAUDE.md`, filing the follow-up tracker for the deferred walkthrough, and opening the draft PR.

- [ ] **Step 1: Re-render against HEAD and run the full gate**

After all seven preceding commits are on the branch:

```bash
rm -rf /tmp/smoke
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
cd /tmp/smoke
uv sync --all-extras --all-groups
uv run ruff check . && uv run ruff format --check .
uv run mypy src/ tests/
uv run pytest -x -q
uv run mkdocs build --strict
cd -
```

Expected: every command exits 0. If any fails, fix in a new commit, re-render, re-run.

- [ ] **Step 2: Cumulative sentinel + dependency grep checks**

```bash
echo "=== Sentinel block ==="
grep -nE 'DOMAIN-FILE-EXCHANGE-(START|END)' /tmp/smoke/src/*/server.py
echo "=== Upload scaffold (commented only) ==="
grep -E 'register_file_exchange_upload' /tmp/smoke/src/*/server.py | head -5
grep -E '^[^#]*register_file_exchange_upload' /tmp/smoke/src/*/server.py
echo "=== pvl-core pin ==="
grep 'fastmcp-pvl-core' /tmp/smoke/pyproject.toml
echo "=== Configuration env-var rows ==="
grep -E 'UPLOAD_(ENABLED|MAX_BYTES|TTL|TTL_MAX)' /tmp/smoke/docs/configuration.md
echo "=== File-exchange guide section ==="
grep -nE '^## Uploading files' /tmp/smoke/docs/guides/file-exchange.md
echo "=== README subsection ==="
grep -nE '^### File exchange' /tmp/smoke/README.md
echo "=== CLAUDE.md section ==="
grep -nE '^## File Exchange' /tmp/smoke/CLAUDE.md
```

Expected (relative line numbers vary):
- Sentinel: two lines (one START, one END), END after START.
- Upload scaffold: every match is on a `#`-prefixed line; the second grep (lines NOT starting with `#`) returns nothing.
- pvl-core: `fastmcp-pvl-core>=2.1.0,<3` and `debug = ["fastmcp-pvl-core[debug]"]`.
- Configuration: 4 lines, one per env var.
- File-exchange guide: one line, `## Uploading files (\`receiver=\`)`.
- README: one line, `### File exchange`.
- CLAUDE.md: one line, `## File Exchange (\`register_file_exchange\` + opt-in upload)`.

- [ ] **Step 3: Local review circus — primary subagent**

Per `~/.claude/CLAUDE.md` PR workflow, **mandatory before opening any PR**. Dispatch the primary `pr-review-toolkit:code-reviewer` subagent on the cumulative diff. Use the Agent tool with `subagent_type: "pr-review-toolkit:code-reviewer"`. The prompt must instruct the subagent to load full file context (not just the diff hunks), since the change touches a sentinel-protection convention that's only meaningful in the context of the surrounding `*.jinja` files.

Sample dispatch prompt structure (adapt to actual diff):

> Review the cumulative diff on branch `feat/file-exchange-upload-117` against `origin/main`. The diff bundles two issues: #118 (sentinel-wrap `register_file_exchange` for opt-in-survives-update) and #117 (commented-out `register_file_exchange_upload` scaffold + dependency bump + docs). Spec at `docs/superpowers/specs/2026-05-10-file-exchange-upload-scaffold-design.md`. **Read full file context for every modified `.jinja` file** — the sentinel-block convention only makes sense in the context of how copier merges rendered output with downstream-owned regions on update. Specifically: confirm the new sentinel name doesn't collide with existing ones, verify the commented-out scaffold uncomments cleanly (every line either `#`-prefixed or part of a `# DOMAIN-` boundary), and check that the configuration-table cross-link anchor matches the file-exchange-guide section slug. Flag anything at any severity — bot-reviewer findings on first run after open count as discipline failures, so the bar is "nothing flagged", not "no blockers".

Address every finding (or defend in writing). If anything is unclear, surface to the user before pushing.

- [ ] **Step 4: Local review circus — second-opinion subagent**

After the primary subagent returns clean (or after addressing its findings), dispatch the `superpowers:code-reviewer` subagent on the same cumulative diff with a second-opinion prompt. Same "load full file context" instruction; same "nothing flagged" bar.

If the second-opinion reviewer flags anything the primary missed, address (or defend), then re-dispatch the primary on the new diff. Loop until both return clean. **Address findings in the *local* circus before pushing — soft-framed "low-priority follow-up" items get fixed now, not deferred.**

- [ ] **Step 5: Specialised reviewer — comment-analyzer (for the doc-heavy diff)**

The diff adds substantial doc content (file-exchange guide section, README subsection, CLAUDE.md section, configuration rows). Per `~/.claude/CLAUDE.md` rule about specialised reviewers triggering on diff content, dispatch `pr-review-toolkit:comment-analyzer` on the diff. The prompt asks specifically about: doc-comment accuracy against the rendered API (UploadRecord field names, BufferedReceiver signature, env-var defaults), internal cross-link integrity, and whether any commented-out code in the server.py scaffold names types/symbols that differ from the upstream pvl-core 2.1.0 surface.

Address findings; loop with the primary reviewer if the response materially changes any code or comment.

- [ ] **Step 6: File the follow-up tracker for the deferred walkthrough**

Before opening the PR, file a tracker issue for the agent-side `curl` walkthrough that this PR intentionally omits. Use `gh issue create` (or `mcp__plugin_github_github__issue_write`):

```bash
gh issue create \
  --repo pvliesdonk/fastmcp-server-template \
  --title "Add 'Local agent uploads' walkthrough to claude-desktop deployment guide" \
  --label enhancement,documentation,scaffold \
  --body "$(cat <<'EOF'
## Problem

#117 added the upload-direction scaffolding (`register_file_exchange_upload(...)` opt-in, env vars, `Uploading files` guide section) but intentionally omitted the agent-side walkthrough — the `curl` example showing how an agent calls `create_upload_link`, receives the one-time URL, and POSTs the bytes. That content belongs in `docs/deployment/claude-desktop.md.jinja`, which doesn't exist yet (#119 backports it from markdown-vault-mcp).

## Fix

After #119 lands, add a `## Local agent uploads` section to the new `docs/deployment/claude-desktop.md.jinja` covering:

- The two-step flow: agent calls `create_upload_link` → receives URL — agent POSTs bytes to that URL.
- A working `curl -X POST <url> --data-binary @file.pdf` example.
- The one-time-token contract (4xx burns the link; retry by calling `create_upload_link` again).
- Cross-link to `docs/guides/file-exchange.md#uploading-files-receiver` for the server-side wiring details.

## Blocked by

- #119 (claude-desktop deployment guide backport).

## Out of scope

- Re-architecting how the upload tool surfaces to clients (that's a #117 / pvl-core concern).
EOF
)"
```

Capture the resulting issue number — it will be referenced in the PR body.

- [ ] **Step 7: Push the branch and open the draft PR**

```bash
git push -u origin feat/file-exchange-upload-117
```

Then:

```bash
gh pr create --draft \
  --base main \
  --title "feat(file-exchange): scaffold register_file_exchange_upload + DOMAIN-FILE-EXCHANGE sentinel" \
  --body "$(cat <<'EOF'
## Summary

- Wraps the existing `register_file_exchange(...)` call in a downstream-owned `DOMAIN-FILE-EXCHANGE-START / END` sentinel block in `server.py.jinja` so opt-in kwargs (`produces=`, `consumer_sink=`) survive `copier update` (#118).
- Adds a fully-commented `register_file_exchange_upload(...)` scaffold inside the same sentinel, with stub `_upload_receiver` and `_validate_upload_target`. Stays commented by default; downstream opts in by uncommenting (#117).
- Bumps `fastmcp-pvl-core>=2.1.0,<3` for the new helper + `UploadRecord` exports.
- Documents 4 new env vars in `docs/configuration.md.jinja`, adds an "Uploading files" section to the file-exchange guide, brief pointer in `README.md.jinja`, and a `## File Exchange` section in `CLAUDE.md.jinja`.

Spec: `docs/superpowers/specs/2026-05-10-file-exchange-upload-scaffold-design.md`.

## Closes

- Closes #117 (upload scaffolding)
- Closes #118 (DOMAIN-FILE-EXCHANGE sentinel precursor)

## Deferred

- Agent-side `curl` walkthrough + one-time-token explanation: tracked as #<TRACKER_FROM_STEP_6>, blocked on #119 (claude-desktop deployment guide backport).

## Test plan

- [x] `uv run ruff check . && uv run ruff format --check .` — clean on rendered project.
- [x] `uv run mypy src/ tests/` — clean on rendered project.
- [x] `uv run pytest -x -q` — clean on rendered project.
- [x] `uv run mkdocs build --strict` — clean (covers the new cross-link).
- [x] Sentinel grep checks: `DOMAIN-FILE-EXCHANGE-START` / `-END` each appear once with `register_file_exchange(...)` between them; `register_file_exchange_upload` appears only on `#`-prefixed lines.
- [x] pvl-core pin grep: `fastmcp-pvl-core>=2.1.0,<3` in rendered `pyproject.toml`.
- [x] Local review circus: `pr-review-toolkit:code-reviewer` (primary), `superpowers:code-reviewer` (second opinion), `pr-review-toolkit:comment-analyzer` (doc-heavy diff) all returned clean before push.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Replace `<TRACKER_FROM_STEP_6>` with the actual issue number from Step 6.

- [ ] **Step 8: Schedule a wakeup to verify bot reviewers**

Per `~/.claude/CLAUDE.md` parallel-pipelining rule, after opening the draft PR you do **not** wait synchronously for bot reviews. Use `ScheduleWakeup` (or `CronCreate`) to verify the bot bodies (claude-review, gemini-code-assist) at the appropriate moment:

- claude-review runs on push and posts inline comments + a markdown body. The GH check turns green when the bot finished, **regardless of what it said** — read the body, not the check status.
- gemini-code-assist with the repo's `.gemini/config.yaml` (`include_drafts: false`) auto-runs on flip-to-ready, not on draft-open. So the gemini pass is deferred until step 9.

Schedule a 5-minute wakeup (cache stays warm) to read the claude-review body once it's done. Sample `ScheduleWakeup`:

```
delaySeconds: 270
prompt: "<original /implement #117 #118 prompt or equivalent>"
reason: "checking claude-review body on PR after draft-push for feat/file-exchange-upload-117"
```

- [ ] **Step 9: After bots LGTM and CI is green, flip the PR to ready**

Once the wakeup fires and you've read the claude-review body (NOT just the GH check), and CI checks are all green:

- If claude-review body says LGTM / no issues found → flip to ready.
- If claude-review flagged anything: this is a **discipline failure** per `~/.claude/CLAUDE.md` — local review missed something. Investigate. Address findings in a new commit (after re-running the local circus on the new diff per the "re-run local review BEFORE pushing fixes" rule). Push. Re-read claude-review. Cap at one round of bot iteration; surface to user if a second iteration is needed.

```bash
gh pr ready <PR_NUMBER>
```

This triggers gemini-code-assist's auto-review on the flip-to-ready event. Schedule another wakeup (10-15 min) to read gemini's verdict.

- [ ] **Step 10: After gemini LGTM, the PR is in human-merge state**

Per `~/.claude/CLAUDE.md`, **merging is human-only**. Don't run `gh pr merge`. Verify the merge state, then **return to the queue** — start the next item without waiting for the human merge. The user batch-merges ready PRs when they have time.

---

## Self-review (per the writing-plans skill checklist)

**Spec coverage** — every section/requirement in the spec maps to a task:

- Spec § Architecture — Task 1 (sentinel refactor) + Task 2 (upload scaffold).
- Spec § File-by-file changes / `server.py.jinja` — Tasks 1 + 2.
- Spec § File-by-file changes / `pyproject.toml.jinja` — Task 3.
- Spec § File-by-file changes / `docs/configuration.md.jinja` — Task 4.
- Spec § File-by-file changes / `docs/guides/file-exchange.md.jinja` — Task 5.
- Spec § File-by-file changes / `README.md.jinja` — Task 6.
- Spec § File-by-file changes / `CLAUDE.md.jinja` — Task 7.
- Spec § Verification — Task 8 Steps 1–2.
- Spec § Risks (anchor stability, sentinel collision, upstream API drift) — Task 8 Step 2 (sentinel grep) + Step 5 (comment-analyzer covering API drift) + Task 5 Step 4 (anchor verification).
- Spec § Open questions (none) — confirmed.
- Spec § Non-goals (`consumes=`, top-level type exports, `stream_receiver=`, advanced kwargs) — explicitly mentioned in Task 2's commit message and the file-exchange guide one-liner about streaming; not implemented.

**Placeholder scan** — searched for "TBD", "TODO", "implement later", "fill in details", "add appropriate", "Similar to Task N". The plan uses `<TRACKER_FROM_STEP_6>` and `<PR_NUMBER>` as runtime-resolved placeholders, both with explicit instructions for how to obtain them at execution time. No undefined references.

**Type / symbol consistency** — sentinel name `DOMAIN-FILE-EXCHANGE-START / END` appears identically in Tasks 1, 2, 5 (guide reference), 7 (CLAUDE.md), and Task 8 grep checks. Anchor slug `#uploading-files-receiver` matches between Task 4 (configuration table cross-link) and Task 5 (section heading). pvl-core version pin `>=2.1.0,<3` matches between Task 3 (edit) and Task 8 (verification grep).
