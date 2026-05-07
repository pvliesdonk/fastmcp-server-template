# Claude Code agent for copier-update PRs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the downstream `copier-update.yml` workflow with three Claude Code agent steps (conflict resolution, changelog triage, excluded-file evolution) plus a body-aggregator script that composes their structured JSON outputs into the existing #49-shaped PR body — failure-tolerant, with graceful fallback when the OAuth token is missing or the API is rate-limited.

**Architecture:** Five new workflow steps in `.github/workflows/copier-update.yml.jinja` (clone template, check token, three parallel `anthropics/claude-code-action@v1` invocations, aggregate). Three agent prompt files at `scripts/copier_update_prompts/job_{a,b,c}.md` (template-owned, updates flow to downstream). One Python aggregator script at `scripts/copier_update_aggregator.py` (template-owned). Aggregator unit tests at `scripts/tests/test_copier_update_aggregator.py` (excluded from rendering, runs in `template-ci.yml` only).

**Tech Stack:** GitHub Actions YAML, `anthropics/claude-code-action@v1`, Python 3.11+ stdlib (no new deps — `json`, `pathlib`, `argparse`), `pytest` (already a dev dependency in the template repo).

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `scripts/copier_update_aggregator.py` | NEW (template-owned, NOT in `_skip_if_exists`) | Reads three job JSONs + existing #49 body data, composes final PR body with stratification + overflow safety net |
| `scripts/copier_update_prompts/job_a.md` | NEW (template-owned) | Job A prompt: conflict resolution with auto-commit |
| `scripts/copier_update_prompts/job_b.md` | NEW (template-owned) | Job B prompt: changelog triage |
| `scripts/copier_update_prompts/job_c.md` | NEW (template-owned) | Job C prompt: excluded-file evolution |
| `scripts/tests/test_copier_update_aggregator.py` | NEW (template-only, in `_exclude`) | Pytest unit tests for the aggregator |
| `scripts/tests/conftest.py` | NEW (template-only, in `_exclude`) | pytest fixtures (synthetic JSON inputs) |
| `.github/workflows/copier-update.yml.jinja` | MODIFY | Add clone + token-check + 3 claude-code steps + aggregator invocation; modify PR open step to use composed body |
| `.github/workflows/template-ci.yml` | MODIFY | Add new job that runs `pytest scripts/tests/` |
| `copier.yml` | MODIFY | Add `scripts/tests/` to `_exclude` |

The aggregator and prompt files are intentionally **template-owned** (not in `_skip_if_exists`) so updates flow to downstream consumers automatically on each cron run. This is a deliberate departure from the pre-existing convention that all `scripts/` files are "starter content" — these specific scripts are workflow plumbing, not user-facing utilities.

The aggregator avoids any third-party Python deps (uses only stdlib). This keeps it portable and avoids forcing downstream projects to install pytest-related dev dependencies just to run the cron.

---

## Task 1: Create aggregator skeleton + happy-path test (all-skipped jobs)

**Files:**
- Create: `scripts/copier_update_aggregator.py`
- Create: `scripts/tests/conftest.py`
- Create: `scripts/tests/test_copier_update_aggregator.py`

- [ ] **Step 1: Write the failing test**

```python
# scripts/tests/test_copier_update_aggregator.py
"""Tests for scripts/copier_update_aggregator.py."""
from __future__ import annotations

import sys
from pathlib import Path

# Make the script importable as a module (pytest runs from repo root).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import copier_update_aggregator as agg  # noqa: E402


def test_compose_body_all_jobs_skipped(tmp_path: Path) -> None:
    """When agent_enabled=False, body has only #49 sections + skip notices."""
    inputs = agg.AggregatorInputs(
        existing_body="## Template update: v1.0.0 → v1.1.0\n\n### Release notes\n\n- #1 feat: foo\n",
        agent_enabled=False,
        job_a_path=None,
        job_b_path=None,
        job_c_path=None,
        conflict_count=0,
        pr_number=42,
    )
    body = agg.compose_body(inputs)
    assert "## Template update: v1.0.0 → v1.1.0" in body
    assert "### Release notes" in body
    assert "#1 feat: foo" in body
    assert "🔒 Agent disabled" in body
    assert "CLAUDE_CODE_OAUTH_TOKEN" in body
```

- [ ] **Step 2: Create conftest.py for synthetic fixtures (used in later tasks)**

```python
# scripts/tests/conftest.py
"""Fixtures for aggregator tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def write_job_json(tmp_path: Path):
    """Helper: write a JSON object to tmp_path/<name>.json and return the path."""

    def _write(name: str, payload: dict) -> Path:
        p = tmp_path / f"{name}.json"
        p.write_text(json.dumps(payload), encoding="utf-8")
        return p

    return _write
```

- [ ] **Step 3: Run test to verify it fails (script doesn't exist yet)**

Run: `cd /mnt/code/fastmcp-server-template && uv run --with pytest pytest scripts/tests/test_copier_update_aggregator.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'copier_update_aggregator'`.

- [ ] **Step 4: Write minimal implementation**

```python
# scripts/copier_update_aggregator.py
"""Compose the copier-update PR body from three claude-code agent JSON outputs.

Reads /tmp/agent-job-{a,b,c}.json (or paths passed via CLI), validates each
against an inline schema, and composes a markdown PR body that extends the
existing #49-shaped body (delta/notes/diff/conflicts) with three new sections
(conflict resolutions, changelog triage, excluded-file evolution).

Failure-tolerant: missing/skipped/rate-limited/errored agent outputs render
as state-specific placeholders without affecting other sections. The existing
#49 sections always render regardless of agent state.

Exit codes:
- 0: composed body written successfully (even if some sections are placeholders)
- 1: catastrophic failure (e.g. existing body file missing, output path unwritable)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class AggregatorInputs:
    existing_body: str
    agent_enabled: bool
    job_a_path: Path | None
    job_b_path: Path | None
    job_c_path: Path | None
    conflict_count: int
    pr_number: int


def compose_body(inputs: AggregatorInputs) -> str:
    """Compose the full PR body from existing #49 content + agent JSON outputs."""
    parts = [inputs.existing_body.rstrip(), "", "---", "", "## Agent analysis", ""]

    if not inputs.agent_enabled:
        skip_msg = (
            "🔒 Agent disabled — `CLAUDE_CODE_OAUTH_TOKEN` not configured "
            "in this repository. To enable, set the secret in repo settings."
        )
        parts.extend([skip_msg, ""])
        return "\n".join(parts) + "\n"

    # TODO: full job rendering in subsequent tasks
    return "\n".join(parts) + "\n"
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run --with pytest pytest scripts/tests/test_copier_update_aggregator.py -v`

Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add scripts/copier_update_aggregator.py scripts/tests/conftest.py scripts/tests/test_copier_update_aggregator.py
git commit -m "feat(scripts): aggregator skeleton + all-skipped test (refs #36)"
```

---

## Task 2: Add Job A success rendering

**Files:**
- Modify: `scripts/copier_update_aggregator.py`
- Modify: `scripts/tests/test_copier_update_aggregator.py`

- [ ] **Step 1: Write the failing test**

Append to `scripts/tests/test_copier_update_aggregator.py`:

```python
def test_compose_body_job_a_success_with_auto_and_review(write_job_json) -> None:
    """Job A success: auto-committed entries + needs-review entries render correctly."""
    job_a = write_job_json(
        "agent-job-a",
        {
            "status": "ok",
            "auto_resolved": [
                {
                    "file": "docs/deployment/oidc.md",
                    "region": "L42-L78",
                    "articulation": "Moved 12 lines of remote OIDC mode customisation into the new DOMAIN-OIDC-EXTRA block.",
                    "commit_sha": "abc1234",
                }
            ],
            "needs_review": [
                {
                    "file": "docs/guides/authentication.md",
                    "region": "L120-L145",
                    "recommended_resolution": "Lift downstream's renamed anchor into the EXTRA block.",
                    "reasoning": "Conflict between template's new section and downstream's anchor rename.",
                }
            ],
        },
    )
    inputs = agg.AggregatorInputs(
        existing_body="## Template update: v1.0.0 → v1.1.0\n",
        agent_enabled=True,
        job_a_path=job_a,
        job_b_path=None,
        job_c_path=None,
        conflict_count=2,
        pr_number=42,
    )
    body = agg.compose_body(inputs)
    assert "🔧 Conflict resolutions" in body
    assert "**Auto-committed by claude-code** — VERIFY before merging:" in body
    assert "docs/deployment/oidc.md" in body
    assert "abc1234" in body
    assert "Moved 12 lines of remote OIDC mode customisation" in body
    assert "**Needs review**" in body
    assert "docs/guides/authentication.md" in body
    assert "Lift downstream's renamed anchor" in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --with pytest pytest scripts/tests/test_copier_update_aggregator.py::test_compose_body_job_a_success_with_auto_and_review -v`

Expected: FAIL — assertion error on `"🔧 Conflict resolutions" in body` (not yet rendered).

- [ ] **Step 3: Add Job A rendering**

In `scripts/copier_update_aggregator.py`, add the Job A renderer and integrate into `compose_body`:

```python
import json


def _read_job_json(path: Path | None) -> dict | None:
    """Read and JSON-parse an agent output file. Returns None if missing or unreadable."""
    if path is None or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _render_job_a(data: dict | None, conflict_count: int) -> str:
    """Render the 🔧 Conflict resolutions section."""
    if conflict_count == 0:
        return ""  # Job A is gated; no section if no conflicts
    if data is None:
        return "### 🔧 Conflict resolutions\n\n⚠️ Agent failed — see workflow log.\n"
    if data.get("status") != "ok":
        return "### 🔧 Conflict resolutions\n\n⚠️ Agent failed — see workflow log.\n"

    lines = ["### 🔧 Conflict resolutions", ""]
    auto = data.get("auto_resolved", [])
    if auto:
        lines.append("**Auto-committed by claude-code** — VERIFY before merging:")
        lines.append("")
        for item in auto:
            lines.append(
                f"- `{item['file']}` (commit {item['commit_sha']}): "
                f"_{item['articulation']}_"
            )
        lines.append("")
    review = data.get("needs_review", [])
    if review:
        lines.append("**Needs review** — conflict markers remain, operator must resolve:")
        lines.append("")
        for item in review:
            lines.append(f"- `{item['file']}`: {item['reasoning']}")
            lines.append(f"  Recommended approach: {item['recommended_resolution']}")
        lines.append("")
    return "\n".join(lines)


# Update compose_body to call _render_job_a:
def compose_body(inputs: AggregatorInputs) -> str:
    parts = [inputs.existing_body.rstrip(), "", "---", "", "## Agent analysis", ""]

    if not inputs.agent_enabled:
        skip_msg = (
            "🔒 Agent disabled — `CLAUDE_CODE_OAUTH_TOKEN` not configured "
            "in this repository. To enable, set the secret in repo settings."
        )
        parts.extend([skip_msg, ""])
        return "\n".join(parts) + "\n"

    job_a_data = _read_job_json(inputs.job_a_path)
    section_a = _render_job_a(job_a_data, inputs.conflict_count)
    if section_a:
        parts.append(section_a)

    return "\n".join(parts) + "\n"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --with pytest pytest scripts/tests/test_copier_update_aggregator.py -v`

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/copier_update_aggregator.py scripts/tests/test_copier_update_aggregator.py
git commit -m "feat(scripts): Job A success rendering in aggregator (refs #36)"
```

---

## Task 3: Add Job B success rendering with stratification

**Files:**
- Modify: `scripts/copier_update_aggregator.py`
- Modify: `scripts/tests/test_copier_update_aggregator.py`

- [ ] **Step 1: Write the failing test**

Append to test file:

```python
def test_compose_body_job_b_with_three_strata(write_job_json) -> None:
    """Job B: needs-opt-in (action), ships-automatically (informational), informational (rollup)."""
    job_b = write_job_json(
        "agent-job-b",
        {
            "status": "ok",
            "entries": [
                {
                    "pr_number": 89,
                    "title": "wire register_server_info_tool",
                    "classification": "needs-opt-in",
                    "summary": "The template now wires get_server_info but downstream's _server_deps.py is in _skip_if_exists. To enable: ...",
                },
                {
                    "pr_number": 84,
                    "title": "ship .gemini/config.yaml",
                    "classification": "ships-automatically",
                    "summary": "Applied this run.",
                },
                {
                    "pr_number": 87,
                    "title": "PEP 735 dependency-groups",
                    "classification": "informational",
                    "summary": "Internal pyproject restructure.",
                },
            ],
        },
    )
    inputs = agg.AggregatorInputs(
        existing_body="## Template update: v1.0.0 → v1.1.0\n",
        agent_enabled=True,
        job_a_path=None,
        job_b_path=job_b,
        job_c_path=None,
        conflict_count=0,
        pr_number=42,
    )
    body = agg.compose_body(inputs)
    # Action-required: full prose
    assert "**Needs your attention**" in body
    assert "#89 wire register_server_info_tool" in body
    assert "needs opt-in" in body or "_server_deps.py" in body
    # Informational: one-liner
    assert "**Ships through automatically**" in body
    assert "#84 ship .gemini/config.yaml — applied this run" in body
    # Rollup: count + ID list
    assert "**Internal / no downstream effect**" in body
    assert "#87" in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --with pytest pytest scripts/tests/test_copier_update_aggregator.py::test_compose_body_job_b_with_three_strata -v`

Expected: FAIL — assertion error on `"**Needs your attention**" in body`.

- [ ] **Step 3: Add Job B rendering**

Append to `scripts/copier_update_aggregator.py`:

```python
def _render_job_b(data: dict | None) -> str:
    """Render the ✨ New features in this update section."""
    if data is None:
        return "### ✨ New features in this update\n\n⚠️ Agent failed — see workflow log.\n"
    if data.get("status") != "ok":
        return "### ✨ New features in this update\n\n⚠️ Agent failed — see workflow log.\n"

    entries = data.get("entries", [])
    if not entries:
        return ""  # No features = no section (rare — refs differed but changelog empty)

    by_class = {"needs-opt-in": [], "ships-automatically": [], "informational": []}
    for e in entries:
        by_class.setdefault(e.get("classification", "informational"), []).append(e)

    lines = ["### ✨ New features in this update", ""]
    if by_class["needs-opt-in"]:
        lines.append("**Needs your attention** (action-required):")
        lines.append("")
        for e in by_class["needs-opt-in"]:
            lines.append(f"- #{e['pr_number']} {e['title']} — needs opt-in.")
            lines.append(f"  {e['summary']}")
        lines.append("")
    if by_class["ships-automatically"]:
        lines.append("**Ships through automatically** (informational):")
        lines.append("")
        for e in by_class["ships-automatically"]:
            lines.append(f"- #{e['pr_number']} {e['title']} — applied this run")
        lines.append("")
    if by_class["informational"]:
        ids = ", ".join(f"#{e['pr_number']}" for e in by_class["informational"])
        n = len(by_class["informational"])
        lines.append(f"**Internal / no downstream effect** ({n} {'entry' if n == 1 else 'entries'}): {ids}")
        lines.append("")
    return "\n".join(lines)


# In compose_body, after _render_job_a:
    job_b_data = _read_job_json(inputs.job_b_path)
    section_b = _render_job_b(job_b_data)
    if section_b:
        parts.append(section_b)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --with pytest pytest scripts/tests/test_copier_update_aggregator.py -v`

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/copier_update_aggregator.py scripts/tests/test_copier_update_aggregator.py
git commit -m "feat(scripts): Job B rendering with three-strata stratification (refs #36)"
```

---

## Task 4: Add Job C success rendering

**Files:**
- Modify: `scripts/copier_update_aggregator.py`
- Modify: `scripts/tests/test_copier_update_aggregator.py`

- [ ] **Step 1: Write the failing test**

```python
def test_compose_body_job_c_with_three_strata(write_job_json) -> None:
    """Job C: recommend-port (action), informational (one-line), skip (rollup)."""
    job_c = write_job_json(
        "agent-job-c",
        {
            "status": "ok",
            "files": [
                {
                    "file": "tests/test_tools.py",
                    "classification": "recommend-port",
                    "summary": "Template added a smoke test for the new register_server_info_tool helper.",
                    "diff_summary": "+15 lines test fixture for get_server_info",
                },
                {
                    "file": "docs/design.md",
                    "classification": "informational",
                    "summary": "Section renamed from 'Architecture' to 'System overview'.",
                    "diff_summary": "1 heading change",
                },
                {
                    "file": ".github/workflows/template-ci.yml",
                    "classification": "skip",
                    "summary": "Template-CI plumbing only.",
                    "diff_summary": "+2 lines on a self-test job",
                },
            ],
        },
    )
    inputs = agg.AggregatorInputs(
        existing_body="## Template update: v1.0.0 → v1.1.0\n",
        agent_enabled=True,
        job_a_path=None,
        job_b_path=None,
        job_c_path=job_c,
        conflict_count=0,
        pr_number=42,
    )
    body = agg.compose_body(inputs)
    assert "📦 Excluded-file upstream changes" in body
    assert "**Recommended to port**" in body
    assert "tests/test_tools.py" in body
    assert "**Informational**" in body
    assert "docs/design.md" in body
    assert "**Skipped (template-internal)**" in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --with pytest pytest scripts/tests/test_copier_update_aggregator.py::test_compose_body_job_c_with_three_strata -v`

Expected: FAIL — `"📦 Excluded-file upstream changes" in body` not found.

- [ ] **Step 3: Add Job C rendering**

Append to `scripts/copier_update_aggregator.py`:

```python
def _render_job_c(data: dict | None) -> str:
    """Render the 📦 Excluded-file upstream changes section."""
    if data is None:
        return "### 📦 Excluded-file upstream changes\n\n⚠️ Agent failed — see workflow log.\n"
    if data.get("status") != "ok":
        return "### 📦 Excluded-file upstream changes\n\n⚠️ Agent failed — see workflow log.\n"

    files = data.get("files", [])
    if not files:
        return ""

    by_class = {"recommend-port": [], "informational": [], "skip": []}
    for f in files:
        by_class.setdefault(f.get("classification", "informational"), []).append(f)

    lines = ["### 📦 Excluded-file upstream changes", ""]
    if by_class["recommend-port"]:
        lines.append("**Recommended to port** (action-required):")
        lines.append("")
        for f in by_class["recommend-port"]:
            lines.append(f"- `{f['file']}`: {f['summary']}")
            lines.append(f"  Diff: {f['diff_summary']}")
        lines.append("")
    if by_class["informational"]:
        lines.append("**Informational**:")
        lines.append("")
        for f in by_class["informational"]:
            lines.append(f"- `{f['file']}`: {f['summary']}")
        lines.append("")
    if by_class["skip"]:
        names = ", ".join(f"`{f['file']}`" for f in by_class["skip"])
        n = len(by_class["skip"])
        lines.append(f"**Skipped (template-internal)** ({n} {'file' if n == 1 else 'files'}): {names}")
        lines.append("")
    return "\n".join(lines)


# In compose_body, after _render_job_b:
    job_c_data = _read_job_json(inputs.job_c_path)
    section_c = _render_job_c(job_c_data)
    if section_c:
        parts.append(section_c)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --with pytest pytest scripts/tests/test_copier_update_aggregator.py -v`

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/copier_update_aggregator.py scripts/tests/test_copier_update_aggregator.py
git commit -m "feat(scripts): Job C rendering with three-strata stratification (refs #36)"
```

---

## Task 5: Add four-state per-section placeholder logic

**Files:**
- Modify: `scripts/copier_update_aggregator.py`
- Modify: `scripts/tests/test_copier_update_aggregator.py`

- [ ] **Step 1: Write failing tests for skipped + rate-limited + errored states**

```python
def test_compose_body_job_a_rate_limited(write_job_json) -> None:
    """Job A rate-limited: shows transient-failure placeholder."""
    job_a = write_job_json(
        "agent-job-a",
        {"status": "rate_limited", "message": "429 from anthropic API"},
    )
    inputs = agg.AggregatorInputs(
        existing_body="## Template update: v1.0.0 → v1.1.0\n",
        agent_enabled=True,
        job_a_path=job_a,
        job_b_path=None,
        job_c_path=None,
        conflict_count=2,
        pr_number=42,
    )
    body = agg.compose_body(inputs)
    assert "🔧 Conflict resolutions" in body
    assert "⏳" in body
    assert "rate-limited" in body or "rate_limited" in body
    assert "next cron" in body


def test_compose_body_job_a_errored(write_job_json) -> None:
    """Job A errored: shows generic-failure placeholder with workflow-log hint."""
    job_a = write_job_json(
        "agent-job-a",
        {"status": "error", "message": "tool call failed"},
    )
    inputs = agg.AggregatorInputs(
        existing_body="## Template update: v1.0.0 → v1.1.0\n",
        agent_enabled=True,
        job_a_path=job_a,
        job_b_path=None,
        job_c_path=None,
        conflict_count=2,
        pr_number=42,
    )
    body = agg.compose_body(inputs)
    assert "🔧 Conflict resolutions" in body
    assert "⚠️" in body
    assert "Agent failed" in body
    assert "workflow log" in body
```

- [ ] **Step 2: Run tests to verify they fail (rate_limited isn't distinguished yet)**

Run: `uv run --with pytest pytest scripts/tests/test_copier_update_aggregator.py::test_compose_body_job_a_rate_limited -v`

Expected: FAIL — body says "Agent failed" not "rate-limited".

- [ ] **Step 3: Refactor _render_job_a (and _render_job_b, _render_job_c) to handle the four states**

In `scripts/copier_update_aggregator.py`, replace the three `_render_job_*` functions with versions that share a common four-state placeholder helper:

```python
def _placeholder(section_title: str, status: str) -> str:
    """Render a state-specific placeholder for a section."""
    if status == "rate_limited":
        msg = "⏳ Agent rate-limited — full analysis will retry on next cron."
    else:  # generic error or missing-but-expected
        msg = "⚠️ Agent failed — see workflow log."
    return f"### {section_title}\n\n{msg}\n"


def _render_job_a(data: dict | None, conflict_count: int) -> str:
    if conflict_count == 0:
        return ""
    if data is None:
        return _placeholder("🔧 Conflict resolutions", "error")
    status = data.get("status", "error")
    if status == "rate_limited":
        return _placeholder("🔧 Conflict resolutions", "rate_limited")
    if status != "ok":
        return _placeholder("🔧 Conflict resolutions", "error")

    # ... existing success-rendering code (auto_resolved + needs_review) ...
```

Apply the same `if data is None / status == "rate_limited" / status != "ok"` pattern to `_render_job_b` and `_render_job_c`.

- [ ] **Step 4: Run tests to verify all pass**

Run: `uv run --with pytest pytest scripts/tests/test_copier_update_aggregator.py -v`

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/copier_update_aggregator.py scripts/tests/test_copier_update_aggregator.py
git commit -m "feat(scripts): four-state per-section placeholder rendering (refs #36)"
```

---

## Task 6: Add overflow safety net (>60k → spill longest section to comment)

**Files:**
- Modify: `scripts/copier_update_aggregator.py`
- Modify: `scripts/tests/test_copier_update_aggregator.py`

- [ ] **Step 1: Write the failing test**

```python
def test_overflow_spills_longest_section(write_job_json, tmp_path: Path) -> None:
    """When body > 60k, longest action-required section spills to overflow comment file."""
    # Build a Job B that will produce a very long body
    long_summary = "x" * 5000  # 5k chars per entry
    big_entries = [
        {
            "pr_number": 1000 + i,
            "title": f"feature {i}",
            "classification": "needs-opt-in",
            "summary": long_summary,
        }
        for i in range(15)  # 15 * 5k = 75k chars in this section alone
    ]
    job_b = write_job_json("agent-job-b", {"status": "ok", "entries": big_entries})

    overflow_dir = tmp_path / "overflow"
    inputs = agg.AggregatorInputs(
        existing_body="## Template update: v1.0.0 → v1.1.0\n",
        agent_enabled=True,
        job_a_path=None,
        job_b_path=job_b,
        job_c_path=None,
        conflict_count=0,
        pr_number=42,
    )
    body, overflow = agg.compose_body_with_overflow(inputs, overflow_dir=overflow_dir)
    assert len(body) <= 60_000
    # Body has spill marker
    assert "full" in body.lower()
    assert "comment" in body.lower()
    # Overflow file written
    assert len(overflow) >= 1
    assert overflow[0].exists()
    # Overflow file contains the displaced content
    overflow_content = overflow[0].read_text(encoding="utf-8")
    assert "feature 0" in overflow_content or "feature 14" in overflow_content


def test_no_overflow_when_body_under_60k(write_job_json, tmp_path: Path) -> None:
    """When body fits under 60k, no overflow spill happens."""
    job_b = write_job_json(
        "agent-job-b",
        {
            "status": "ok",
            "entries": [
                {"pr_number": 1, "title": "small feature", "classification": "ships-automatically", "summary": "applied"}
            ],
        },
    )
    inputs = agg.AggregatorInputs(
        existing_body="## Template update: v1.0.0 → v1.1.0\n",
        agent_enabled=True,
        job_a_path=None,
        job_b_path=job_b,
        job_c_path=None,
        conflict_count=0,
        pr_number=42,
    )
    body, overflow = agg.compose_body_with_overflow(inputs, overflow_dir=tmp_path / "overflow")
    assert len(body) < 60_000
    assert overflow == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --with pytest pytest scripts/tests/test_copier_update_aggregator.py::test_overflow_spills_longest_section scripts/tests/test_copier_update_aggregator.py::test_no_overflow_when_body_under_60k -v`

Expected: FAIL — `compose_body_with_overflow` not defined.

- [ ] **Step 3: Add overflow logic**

Append to `scripts/copier_update_aggregator.py`:

```python
BODY_LIMIT = 60_000
SECTION_MARKERS = ["### 🔧 ", "### ✨ ", "### 📦 "]


def compose_body_with_overflow(
    inputs: AggregatorInputs, overflow_dir: Path
) -> tuple[str, list[Path]]:
    """Compose body; if > BODY_LIMIT chars, spill longest section(s) to overflow files.

    Returns (body, overflow_paths). overflow_paths is empty if no spill occurred.
    Each overflow path holds the displaced section content (caller posts as comments).
    """
    body = compose_body(inputs)
    if len(body) <= BODY_LIMIT:
        return body, []

    overflow_dir.mkdir(parents=True, exist_ok=True)
    overflow_paths: list[Path] = []
    spill_index = 0

    while len(body) > BODY_LIMIT:
        # Find each section's start + length
        sections: list[tuple[str, int, int]] = []  # (header, start, end)
        for marker in SECTION_MARKERS:
            start = body.find(marker)
            if start == -1:
                continue
            # Section ends at the next "### " marker or EOF
            after = body.find("\n### ", start + len(marker))
            end = after if after != -1 else len(body)
            sections.append((marker.strip(), start, end))

        if not sections:
            # No sections to spill (only existing-body content); we can't reduce further
            break

        sections.sort(key=lambda s: s[2] - s[1], reverse=True)
        marker, start, end = sections[0]
        spill_index += 1
        overflow_path = overflow_dir / f"overflow-{spill_index}.md"
        overflow_path.write_text(body[start:end], encoding="utf-8")
        overflow_paths.append(overflow_path)

        replacement = (
            f"{marker}\n\n"
            f"📎 Section is long; full analysis posted as a follow-up comment "
            f"(see overflow #{spill_index}).\n\n"
        )
        body = body[:start] + replacement + body[end:]

    return body, overflow_paths
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --with pytest pytest scripts/tests/test_copier_update_aggregator.py -v`

Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/copier_update_aggregator.py scripts/tests/test_copier_update_aggregator.py
git commit -m "feat(scripts): aggregator overflow safety net for >60k bodies (refs #36)"
```

---

## Task 7: Add deterministic-ordering test + JSON schema validation

**Files:**
- Modify: `scripts/copier_update_aggregator.py`
- Modify: `scripts/tests/test_copier_update_aggregator.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_deterministic_ordering(write_job_json) -> None:
    """Same inputs across two runs produce byte-identical body."""
    payload = {
        "status": "ok",
        "entries": [
            {"pr_number": 100, "title": "a", "classification": "ships-automatically", "summary": "x"},
            {"pr_number": 200, "title": "b", "classification": "needs-opt-in", "summary": "y"},
            {"pr_number": 50, "title": "c", "classification": "ships-automatically", "summary": "z"},
        ],
    }
    job_b1 = write_job_json("agent-job-b-1", payload)
    job_b2 = write_job_json("agent-job-b-2", payload)
    inputs1 = agg.AggregatorInputs(
        existing_body="## Template update: v1.0.0 → v1.1.0\n",
        agent_enabled=True,
        job_a_path=None,
        job_b_path=job_b1,
        job_c_path=None,
        conflict_count=0,
        pr_number=42,
    )
    inputs2 = agg.AggregatorInputs(
        existing_body="## Template update: v1.0.0 → v1.1.0\n",
        agent_enabled=True,
        job_a_path=None,
        job_b_path=job_b2,
        job_c_path=None,
        conflict_count=0,
        pr_number=42,
    )
    assert agg.compose_body(inputs1) == agg.compose_body(inputs2)


def test_malformed_json_renders_errored_placeholder(tmp_path: Path) -> None:
    """A JSON file with a syntax error renders the errored placeholder."""
    bad = tmp_path / "agent-job-a.json"
    bad.write_text("not valid json {", encoding="utf-8")
    inputs = agg.AggregatorInputs(
        existing_body="## Template update: v1.0.0 → v1.1.0\n",
        agent_enabled=True,
        job_a_path=bad,
        job_b_path=None,
        job_c_path=None,
        conflict_count=2,
        pr_number=42,
    )
    body = agg.compose_body(inputs)
    assert "🔧 Conflict resolutions" in body
    assert "⚠️" in body and "failed" in body.lower()


def test_missing_required_field_renders_errored_placeholder(write_job_json) -> None:
    """Missing 'status' field is treated as malformed."""
    job_a = write_job_json("agent-job-a", {"auto_resolved": []})  # no status
    inputs = agg.AggregatorInputs(
        existing_body="## Template update: v1.0.0 → v1.1.0\n",
        agent_enabled=True,
        job_a_path=job_a,
        job_b_path=None,
        job_c_path=None,
        conflict_count=2,
        pr_number=42,
    )
    body = agg.compose_body(inputs)
    assert "⚠️" in body and "failed" in body.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --with pytest pytest scripts/tests/test_copier_update_aggregator.py::test_deterministic_ordering scripts/tests/test_copier_update_aggregator.py::test_malformed_json_renders_errored_placeholder scripts/tests/test_copier_update_aggregator.py::test_missing_required_field_renders_errored_placeholder -v`

Expected: deterministic test passes already (json doesn't reorder), malformed test fails (current code returns None for unparseable JSON which becomes "Agent failed" — actually maybe passes), missing-field test fails (status missing → defaults to "error" → renders placeholder — actually passes).

If all pass already (because the existing code is conservative), great — the test suite documents the contract. Otherwise, tighten the rendering to validate explicitly.

- [ ] **Step 3: If any test fails, add explicit validation**

Add to `scripts/copier_update_aggregator.py`:

```python
def _validate_job_a(data: dict | None) -> dict | None:
    """Return data if it has the expected schema, else None (treated as errored)."""
    if data is None:
        return None
    if not isinstance(data.get("status"), str):
        return None
    if data["status"] == "ok":
        if not isinstance(data.get("auto_resolved", []), list):
            return None
        if not isinstance(data.get("needs_review", []), list):
            return None
    return data
```

Use in `_render_job_a`. Apply analogous validators for Job B (`entries: list`) and Job C (`files: list`).

- [ ] **Step 4: Run tests to verify all pass**

Run: `uv run --with pytest pytest scripts/tests/test_copier_update_aggregator.py -v`

Expected: 11 passed (8 from before + 3 new).

- [ ] **Step 5: Commit**

```bash
git add scripts/copier_update_aggregator.py scripts/tests/test_copier_update_aggregator.py
git commit -m "feat(scripts): JSON schema validation + determinism test (refs #36)"
```

---

## Task 8: Add CLI entry point + integration test

**Files:**
- Modify: `scripts/copier_update_aggregator.py`
- Modify: `scripts/tests/test_copier_update_aggregator.py`

- [ ] **Step 1: Write the failing test**

```python
def test_cli_entry_point_writes_body_file(tmp_path: Path, write_job_json) -> None:
    """Invoking the script via subprocess writes a composed body to --output."""
    import subprocess

    job_a = write_job_json(
        "agent-job-a",
        {"status": "ok", "auto_resolved": [], "needs_review": []},
    )
    existing = tmp_path / "existing.md"
    existing.write_text("## Template update: v1.0.0 → v1.1.0\n", encoding="utf-8")
    output = tmp_path / "out.md"
    overflow_dir = tmp_path / "overflow"

    script = Path(__file__).resolve().parent.parent / "copier_update_aggregator.py"
    result = subprocess.run(
        [
            sys.executable, str(script),
            "--existing-body", str(existing),
            "--agent-enabled", "true",
            "--job-a", str(job_a),
            "--conflict-count", "2",
            "--pr-number", "42",
            "--output-body", str(output),
            "--overflow-dir", str(overflow_dir),
        ],
        capture_output=True, text=True, check=True,
    )
    assert output.exists()
    body = output.read_text(encoding="utf-8")
    assert "## Template update: v1.0.0 → v1.1.0" in body
    assert "🔧 Conflict resolutions" in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --with pytest pytest scripts/tests/test_copier_update_aggregator.py::test_cli_entry_point_writes_body_file -v`

Expected: FAIL — script has no CLI entry point.

- [ ] **Step 3: Add CLI entry point**

Append to `scripts/copier_update_aggregator.py`:

```python
import argparse


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Compose copier-update PR body from agent JSON outputs.")
    p.add_argument("--existing-body", type=Path, required=True, help="Path to the existing #49-shaped body markdown.")
    p.add_argument("--agent-enabled", choices=["true", "false"], required=True)
    p.add_argument("--job-a", type=Path, default=None, help="Path to /tmp/agent-job-a.json (or absent).")
    p.add_argument("--job-b", type=Path, default=None)
    p.add_argument("--job-c", type=Path, default=None)
    p.add_argument("--conflict-count", type=int, required=True)
    p.add_argument("--pr-number", type=int, required=True)
    p.add_argument("--output-body", type=Path, required=True, help="Where to write composed body.")
    p.add_argument("--overflow-dir", type=Path, required=True, help="Directory for overflow comment files.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    inputs = AggregatorInputs(
        existing_body=args.existing_body.read_text(encoding="utf-8"),
        agent_enabled=(args.agent_enabled == "true"),
        job_a_path=args.job_a,
        job_b_path=args.job_b,
        job_c_path=args.job_c,
        conflict_count=args.conflict_count,
        pr_number=args.pr_number,
    )
    body, overflow_paths = compose_body_with_overflow(inputs, overflow_dir=args.overflow_dir)
    args.output_body.write_text(body, encoding="utf-8")
    if overflow_paths:
        for p in overflow_paths:
            print(f"OVERFLOW: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --with pytest pytest scripts/tests/test_copier_update_aggregator.py -v`

Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/copier_update_aggregator.py scripts/tests/test_copier_update_aggregator.py
git commit -m "feat(scripts): aggregator CLI entry point + integration test (refs #36)"
```

---

## Task 9: Write Job A prompt file

**Files:**
- Create: `scripts/copier_update_prompts/job_a.md`

- [ ] **Step 1: Create the prompt file**

```markdown
<!-- scripts/copier_update_prompts/job_a.md -->
# Job A: copier-update conflict resolution

You are an agent helping an operator review a `copier-update` PR for the
`{{ project_name }}` downstream consumer of the `pvliesdonk/fastmcp-server-template`.

## Context

The template was advanced from `${PREVIOUS_COMMIT}` to `${NEW_REF}`. `copier
update --conflict=inline` ran and left conflict markers in some files because
copier's 3-way merge could not auto-resolve them. Your job is to triage these
conflicts: auto-commit the trivial mechanical ones, and write analysis comments
for the rest.

You have access to:
- The downstream working tree at the current branch state (with conflict markers).
- A clone of the template repo at `/tmp/template`. Use `git -C /tmp/template
  checkout ${PREVIOUS_COMMIT}` and `git -C /tmp/template checkout ${NEW_REF}`
  to inspect the template's state at either ref.

## Conflict files

The following files contain `<<<<<<< before updating ... >>>>>>>` markers:

${CONFLICT_FILES_LIST}

## Per-conflict task

For each `<<<<<<<` / `>>>>>>>` region in each conflict file, decide one of:

### Auto-resolvable

A conflict is **auto-resolvable** if and only if you can articulate the precise
transformation that resolves it in **one sentence** with **no ambiguity** about
which downstream lines belong where. Examples of articulations that pass this
bar:

- "Moved 12 lines of `remote OIDC mode` customisation from a mid-file location
  into the new `DOMAIN-OIDC-EXTRA` block at end-of-file; template body accepted
  unchanged."
- "Renamed sentinel marker `DOMAIN-DOCKER-START` to `DOMAIN-DOCKER-EXTRA-START`
  to match the template's new naming convention; downstream content unchanged."

If you cannot articulate the transformation in one sentence — or if there is any
ambiguity about which downstream lines should go where — the conflict is NOT
auto-resolvable.

For auto-resolvable conflicts: write the resolved file to disk (replacing the
conflict markers and surrounding region with the final content). Do NOT commit
yet — accumulate auto-resolutions and commit once at the end.

### Needs review

For non-auto-resolvable conflicts: leave the markers in place. Write a
`recommended_resolution` (one paragraph, concrete) and `reasoning` (one
paragraph, explains why it can't be auto-resolved).

## Final commit

If you applied any auto-resolutions, run **once** at the end:

```bash
git add <files-you-modified>
git commit -m "auto-resolve N trivial conflicts (claude-code)" --author="claude-code <claude-code@anthropic.com>"
```

Capture the commit SHA via `git rev-parse HEAD`.

## Output

Write the following JSON to `/tmp/agent-job-a.json` (NOT to stdout — write the file):

```json
{
  "status": "ok",
  "auto_resolved": [
    {
      "file": "docs/deployment/oidc.md",
      "region": "L42-L78",
      "articulation": "Moved 12 lines of remote OIDC mode customisation into the new DOMAIN-OIDC-EXTRA block; template body accepted unchanged.",
      "commit_sha": "abc1234"
    }
  ],
  "needs_review": [
    {
      "file": "docs/guides/authentication.md",
      "region": "L120-L145",
      "recommended_resolution": "Lift the renamed anchor `#known-limitations-oidc-session-lifetime` into the EXTRA block while accepting the template's anchor in the body.",
      "reasoning": "Conflict is between template's new MCP OAuth refresh section content and downstream's renamed cross-reference anchor. The rename affects three internal links so resolving requires choosing between (a) preserving the rename and updating template-body links to match, or (b) reverting to template anchor and dropping the rename. Operator preference."
    }
  ]
}
```

If you encounter an unrecoverable error (e.g. file unreadable, git commit
failed), write `{"status": "error", "message": "<one-line description>"}`
instead and exit. If you receive a 429 / rate-limit response from any tool,
write `{"status": "rate_limited", "message": "<details>"}`.

The aggregator that consumes this JSON validates schema strictly. Any
deviation from the shapes above will cause the section to render as
"Agent failed" in the PR body.

## Constraints

- Tool access: file read/write on the working tree, file read on `/tmp/template`,
  `git -C /tmp/template <subcommand>`, `git status`, `git diff`, `git add <path>`,
  `git commit -m '<msg>'`. NO `git push`, NO branch operations, NO network calls.
- Do not modify files outside the conflict files listed above.
- Sentinel-block awareness: lines inside `<!-- DOMAIN-*-START -->` ... `<!-- DOMAIN-*-END -->`,
  `<!-- PROJECT-*-START -->` ... `<!-- PROJECT-*-END -->`, `# CONFIG-*-START` ...
  `# CONFIG-*-END`, `# PROJECT-*-START` ... `# PROJECT-*-END` are downstream-owned by
  contract. When resolving conflicts inside these blocks, take the downstream side
  unless there is a clear template-side correction (e.g. the marker name itself
  was renamed by the template).

If the auto-resolved list is empty (no trivial cases found), do NOT make any
git commit; the `auto_resolved` array in the JSON is `[]`.
```

- [ ] **Step 2: Verify the file is well-formed**

Run: `cat scripts/copier_update_prompts/job_a.md | head -5 && wc -l scripts/copier_update_prompts/job_a.md`

Expected: file exists with the markdown header visible; ~120 lines.

- [ ] **Step 3: Commit**

```bash
git add scripts/copier_update_prompts/job_a.md
git commit -m "feat(prompts): Job A conflict-resolution prompt (refs #36)"
```

---

## Task 10: Write Job B prompt file

**Files:**
- Create: `scripts/copier_update_prompts/job_b.md`

- [ ] **Step 1: Create the prompt file**

```markdown
<!-- scripts/copier_update_prompts/job_b.md -->
# Job B: copier-update changelog triage

You are an agent helping an operator review a `copier-update` PR for the
`{{ project_name }}` downstream consumer of `pvliesdonk/fastmcp-server-template`.

## Context

The template was advanced from `${PREVIOUS_COMMIT}` to `${NEW_REF}`. The
template's `CHANGELOG.md` between these two refs has new entries the operator
hasn't seen before. Your job is to triage each entry: classify it by
operator-relevance and write a one-paragraph summary.

You have read-only access to:
- A clone of the template repo at `/tmp/template`. Read
  `/tmp/template/CHANGELOG.md` at the new ref.
- The downstream working tree (read-only — do not modify).

## Per-entry task

For each entry in the CHANGELOG between `${PREVIOUS_COMMIT}` (exclusive) and
`${NEW_REF}` (inclusive), classify as one of three:

- **`ships-automatically`** — the change is in a template-owned file (NOT in
  `_skip_if_exists`). Downstream gets it via this `copier update` with no
  further action. Examples: new env var documented in `docs/configuration.md`
  (template-owned), workflow change in `release.yml.jinja`.

- **`needs-opt-in`** — downstream must wire something to benefit. Examples:
  template wires a new helper in a `_skip_if_exists` file (`_server_deps.py`,
  `tools.py`, etc.); template adds a new copier variable that defaults to a
  conservative value but downstream may want to override; template adds a new
  scaffold file that downstream may want to populate.

- **`informational`** — internal template-side change with no downstream-facing
  effect. Examples: changes to `template-ci.yml`, release-pipeline plumbing,
  repo-internal docs (`docs/superpowers/`), CHANGELOG-only edits.

## Reading copier.yml to disambiguate

To decide between `ships-automatically` and `needs-opt-in`, read
`/tmp/template/copier.yml` at `${NEW_REF}` and check `_skip_if_exists` and
`_exclude`. Files listed in `_skip_if_exists` are downstream-owned starter
files — changes in those files do NOT flow to downstream automatically.

## Output

Write the following JSON to `/tmp/agent-job-b.json`:

```json
{
  "status": "ok",
  "entries": [
    {
      "pr_number": 89,
      "title": "wire register_server_info_tool",
      "classification": "needs-opt-in",
      "summary": "The template now wires `get_server_info` (via `register_server_info_tool`) by default in `make_server()`. This change ships through automatically since `server.py.jinja` is template-owned. To wire upstream version reporting, populate the DOMAIN-UPSTREAM sentinel inside the call. See template's CLAUDE.md `## Server Info Tool` section."
    }
  ]
}
```

If the CHANGELOG between the two refs is empty (template advanced without
publishing CHANGELOG entries — unusual), write `{"status": "ok", "entries": []}`.

If you encounter an unrecoverable error, write
`{"status": "error", "message": "<details>"}`. If rate-limited, write
`{"status": "rate_limited", "message": "<details>"}`.

## Constraints

- Tool access: file read on `/tmp/template`, `git -C /tmp/template log` and
  `git -C /tmp/template show`, `git -C /tmp/template checkout <ref>`. NO file
  writes (other than the output JSON), NO git commits, NO network calls.
- Use the CHANGELOG.md content directly. Do not infer entries from `git log`
  alone — if a PR isn't in the CHANGELOG, it's not in scope (the CHANGELOG is
  managed by python-semantic-release and is the canonical operator-facing
  feed).
- Per-entry summaries should be operator-actionable: tell the operator what
  they got, why it matters, and what (if anything) they should do.
```

- [ ] **Step 2: Commit**

```bash
git add scripts/copier_update_prompts/job_b.md
git commit -m "feat(prompts): Job B changelog-triage prompt (refs #36)"
```

---

## Task 11: Write Job C prompt file

**Files:**
- Create: `scripts/copier_update_prompts/job_c.md`

- [ ] **Step 1: Create the prompt file**

```markdown
<!-- scripts/copier_update_prompts/job_c.md -->
# Job C: copier-update excluded-file evolution

You are an agent helping an operator review a `copier-update` PR for the
`{{ project_name }}` downstream consumer of `pvliesdonk/fastmcp-server-template`.

## Context

Some files in the template are listed under `_exclude` in `copier.yml` — they
exist as `.jinja` source in the template repo for maintainer reference but are
NEVER rendered to downstream. Examples: `tests/test_tools.py`, `docs/design.md`.

Downstream often has its own version of these files (created at scaffold time,
or hand-written later). Because the template doesn't render these to
downstream, the upstream `.jinja` source can evolve without any changes
flowing through. This job triages whether downstream's local copy of any such
file would benefit from porting the upstream evolution.

You have read-only access to:
- A clone of the template repo at `/tmp/template`. Use `git -C /tmp/template
  diff ${PREVIOUS_COMMIT}..${NEW_REF} -- <path>` to see what changed.
- The downstream working tree at the current state (read-only — to inspect
  the local copy).

## Per-file task

Read `/tmp/template/copier.yml` at `${NEW_REF}` to get the `_exclude` list.
For each entry that is a `.jinja`-suffixed FILE (skip directory globs like
`docs/superpowers`, stock excludes like `.git` / `*.pyc` / `~*`, and
non-`.jinja` files like `uv.lock`):

1. Run: `git -C /tmp/template diff ${PREVIOUS_COMMIT}..${NEW_REF} -- <path>`
2. If the diff is empty → skip (not in output).
3. If non-empty, classify the diff:
   - **`recommend-port`** — the change adds operator-relevant value (new
     test case, doc improvement, bug fix in a script). Downstream's local
     copy of this file would benefit from porting the change manually.
   - **`skip`** — template-maintainer concern only. Downstream doesn't need
     to do anything (e.g. internal refactor, comment cleanup, change to a
     test that downstream doesn't have).
   - **`informational`** — small change with mixed value; downstream might
     find it interesting but no clear action recommended.

For each non-skipped file, also write `summary` (one sentence on what
changed) and `diff_summary` (terse — line counts, function names changed,
etc.; max ~80 chars).

## Output

Write to `/tmp/agent-job-c.json`:

```json
{
  "status": "ok",
  "files": [
    {
      "file": "tests/test_tools.py",
      "classification": "recommend-port",
      "summary": "Template added a smoke test for the new register_server_info_tool helper that downstream's local test_tools.py doesn't have.",
      "diff_summary": "+15 lines test fixture for get_server_info"
    }
  ]
}
```

If no excluded files evolved between the two refs, write
`{"status": "ok", "files": []}`.

If unrecoverable error: `{"status": "error", "message": "..."}`.
If rate-limited: `{"status": "rate_limited", "message": "..."}`.

## Constraints

- Tool access: file read, `git -C /tmp/template log` / `diff` / `show` /
  `checkout`. NO file writes (other than the output JSON), NO git commits,
  NO network calls.
- Skip directory globs in `_exclude`. Only process individual file paths
  ending in `.jinja`.
- The downstream working tree may not contain the same paths the template's
  `_exclude` references (e.g. downstream may have deleted their `tests/test_tools.py`).
  When that's the case, still report the upstream evolution but note in the
  summary that downstream doesn't currently have a local copy.
```

- [ ] **Step 2: Commit**

```bash
git add scripts/copier_update_prompts/job_c.md
git commit -m "feat(prompts): Job C excluded-file-evolution prompt (refs #36)"
```

---

## Task 12: Add `pytest scripts/tests/` to template-ci.yml + exclude tests dir from rendering

**Files:**
- Modify: `.github/workflows/template-ci.yml`
- Modify: `copier.yml`

- [ ] **Step 1: Add `scripts/tests/` to `_exclude` in copier.yml**

In `/mnt/code/fastmcp-server-template/copier.yml`, find the `_exclude:` block (around lines 85-108). Add this entry to the "Template-repo-specific excludes" section:

```yaml
  - "scripts/tests"                            # aggregator unit tests — template-only
```

- [ ] **Step 2: Add aggregator-test job to template-ci.yml**

In `/mnt/code/fastmcp-server-template/.github/workflows/template-ci.yml`, append a new job after the existing `downstream-gate` job:

```yaml

  aggregator-tests:
    name: Aggregator script unit tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6

      - name: Install uv
        uses: astral-sh/setup-uv@v8.1.0
        with:
          version: "0.6"

      - name: Set up Python 3.12
        run: uv python install 3.12

      - name: Run aggregator tests
        run: uv run --with pytest pytest scripts/tests/ -v
```

- [ ] **Step 3: Run the test job locally to confirm it would pass in CI**

Run: `cd /mnt/code/fastmcp-server-template && uv run --with pytest pytest scripts/tests/ -v`

Expected: 12 passed.

- [ ] **Step 4: Verify scripts/tests/ stays out of rendered project**

```bash
git add copier.yml .github/workflows/template-ci.yml
git commit -m "feat(ci): aggregator unit-test job; exclude tests from render (refs #36)"
rm -rf /tmp/smoke
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke 2>&1 | tail -2
ls /tmp/smoke/scripts/
```

Expected: `/tmp/smoke/scripts/` contains `copier_update_aggregator.py`, `copier_update_prompts/`, `bump_manifests.py` — but NOT `tests/`.

---

## Task 13: Modify copier-update.yml.jinja — add clone + token-check steps

**Files:**
- Modify: `.github/workflows/copier-update.yml.jinja`

- [ ] **Step 1: Read the existing workflow shape**

Run: `grep -n "^      - name:\|^  [a-z].*:" /mnt/code/fastmcp-server-template/.github/workflows/copier-update.yml.jinja | head -30`

Note the current step ordering. The new clone + token-check steps go BETWEEN the existing "Read template ref + collect conflict files" step and the existing "Open or update PR" step.

- [ ] **Step 2: Insert the clone step**

Find the existing step that reads `conflict_count` (around line 84). After that step (after its closing — typically a step boundary marked by an empty line), insert:

```yaml
      - name: Clone template at both refs (for agent context)
        id: clone-template
        # Provides /tmp/template at both old (downstream's previous _commit)
        # and new (just-applied) refs so the three claude-code agent steps can
        # read template-side history (CHANGELOG, conflict files at the old
        # ref, excluded-file evolution diffs).
        # Failure-tolerant: if clone fails, agent steps see the missing dir
        # and write error placeholders; PR still opens.
        if: steps.meta.outputs.conflict_count != '' || steps.meta.outputs.template_advanced == 'true'
        continue-on-error: true
        env:
          PREVIOUS_COMMIT: {% raw %}${{ steps.meta.outputs.previous_commit }}{% endraw %}
        run: |
          set -euo pipefail
          rm -rf /tmp/template
          git clone --filter=blob:none \
            https://github.com/pvliesdonk/fastmcp-server-template.git \
            /tmp/template
          # Verify both refs are reachable
          git -C /tmp/template fetch --tags
          git -C /tmp/template rev-parse "${PREVIOUS_COMMIT}^{commit}" >/dev/null
          echo "template_clone_ok=true" >> "$GITHUB_OUTPUT"
```

Note: the conditional `steps.meta.outputs.template_advanced == 'true'` references an output we'll add in Step 4. The existing workflow already detects whether copier produced any changes (`steps.meta.outputs.conflict_count` is one signal); we'll add `template_advanced` as a stronger gate for agent steps that should fire even when no conflicts.

- [ ] **Step 3: Insert the token-check step**

After the clone step, insert:

```yaml
      - name: Check claude-code token availability
        id: agent-prereq
        # Detect whether the downstream repo has CLAUDE_CODE_OAUTH_TOKEN
        # configured. Without it, the three agent steps skip and the
        # aggregator renders "agent disabled" placeholders.
        env:
          CLAUDE_CODE_OAUTH_TOKEN: {% raw %}${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}{% endraw %}
        run: |
          if [ -n "${CLAUDE_CODE_OAUTH_TOKEN}" ]; then
            echo "agent_enabled=true"  >> "$GITHUB_OUTPUT"
          else
            echo "agent_enabled=false" >> "$GITHUB_OUTPUT"
            echo "::notice::CLAUDE_CODE_OAUTH_TOKEN not set; skipping agent analysis. Set in repo secrets to enable."
          fi
```

- [ ] **Step 4: Add `template_advanced` output to the existing `meta` step**

Find the existing step with `id: meta` (around line 84). Inside that step's `run:` block, before the `echo "conflict_count=..."` line, add:

```bash
          # Detect whether the template ref actually changed (agent jobs B/C
          # should fire even when no conflicts but the template advanced).
          if [ "${PREVIOUS_COMMIT}" != "${NEW_REF}" ]; then
            template_advanced=true
          else
            template_advanced=false
          fi
          echo "template_advanced=${template_advanced}" >> "$GITHUB_OUTPUT"
```

- [ ] **Step 5: Render and verify**

```bash
rm -rf /tmp/smoke
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke 2>&1 | tail -2
grep -n "Clone template\|Check claude-code\|template_advanced" \
  /tmp/smoke/.github/workflows/copier-update.yml | head -10
```

Expected: rendered workflow contains the new steps.

- [ ] **Step 6: Don't commit yet**

The workflow modifications continue in Tasks 14-16; all commit together at the end of Task 16.

---

## Task 14: Add three claude-code parallel steps to copier-update.yml.jinja

**Files:**
- Modify: `.github/workflows/copier-update.yml.jinja`

- [ ] **Step 1: Insert Job A step**

After the token-check step (from Task 13), insert:

```yaml
      - name: Agent Job A — Conflict resolution
        if: |
          steps.agent-prereq.outputs.agent_enabled == 'true' &&
          steps.meta.outputs.conflict_count > 0 &&
          steps.clone-template.outputs.template_clone_ok == 'true'
        continue-on-error: true
        uses: anthropics/claude-code-action@v1
        with:
          claude_code_oauth_token: {% raw %}${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}{% endraw %}
          prompt_file: scripts/copier_update_prompts/job_a.md
          claude_args: |
            --append-system-prompt "PREVIOUS_COMMIT=${{ steps.meta.outputs.previous_commit }}"
            --append-system-prompt "NEW_REF=${{ steps.meta.outputs.new_ref }}"
            --append-system-prompt "CONFLICT_FILES_LIST=${{ steps.meta.outputs.conflict_files }}"
```

- [ ] **Step 2: Insert Job B step**

```yaml
      - name: Agent Job B — Changelog triage
        if: |
          steps.agent-prereq.outputs.agent_enabled == 'true' &&
          steps.meta.outputs.template_advanced == 'true' &&
          steps.clone-template.outputs.template_clone_ok == 'true'
        continue-on-error: true
        uses: anthropics/claude-code-action@v1
        with:
          claude_code_oauth_token: {% raw %}${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}{% endraw %}
          prompt_file: scripts/copier_update_prompts/job_b.md
          claude_args: |
            --append-system-prompt "PREVIOUS_COMMIT=${{ steps.meta.outputs.previous_commit }}"
            --append-system-prompt "NEW_REF=${{ steps.meta.outputs.new_ref }}"
```

- [ ] **Step 3: Insert Job C step**

```yaml
      - name: Agent Job C — Excluded-file evolution
        if: |
          steps.agent-prereq.outputs.agent_enabled == 'true' &&
          steps.meta.outputs.template_advanced == 'true' &&
          steps.clone-template.outputs.template_clone_ok == 'true'
        continue-on-error: true
        uses: anthropics/claude-code-action@v1
        with:
          claude_code_oauth_token: {% raw %}${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}{% endraw %}
          prompt_file: scripts/copier_update_prompts/job_c.md
          claude_args: |
            --append-system-prompt "PREVIOUS_COMMIT=${{ steps.meta.outputs.previous_commit }}"
            --append-system-prompt "NEW_REF=${{ steps.meta.outputs.new_ref }}"
```

- [ ] **Step 4: Commit nothing yet — continues in Task 15**

---

## Task 15: Add aggregator invocation step to copier-update.yml.jinja

**Files:**
- Modify: `.github/workflows/copier-update.yml.jinja`

- [ ] **Step 1: Insert aggregator step after the three agent steps**

```yaml
      - name: Compose PR body via aggregator
        id: compose
        # Reads the existing #49-shaped body data + three /tmp/agent-job-*.json
        # files (any may be missing/errored) and writes the composed PR body.
        # Failure-tolerant: if aggregator crashes, PR still opens with the
        # existing #49 body (no agent sections).
        continue-on-error: true
        env:
          AGENT_ENABLED: {% raw %}${{ steps.agent-prereq.outputs.agent_enabled }}{% endraw %}
          CONFLICT_COUNT: {% raw %}${{ steps.meta.outputs.conflict_count }}{% endraw %}
          PR_NUMBER: {% raw %}${{ steps.meta.outputs.pr_number || '0' }}{% endraw %}
        run: |
          set -euo pipefail
          # The existing workflow writes the #49-shaped body content to a
          # variable consumed by the "Open or update PR" step. We capture
          # that same content into a file the aggregator reads.
          mkdir -p /tmp/aggregator
          # NOTE: the existing #49 logic builds $body in shell. To wire the
          # aggregator in, the workflow needs to:
          #   1. Write the existing $body to /tmp/aggregator/existing-body.md
          #   2. Run the aggregator with --existing-body pointing at that file
          #   3. Read the aggregator's output as the new $body
          # This step assumes Task 16 will have updated the body-construction
          # step to write to /tmp/aggregator/existing-body.md.

          python3 scripts/copier_update_aggregator.py \
            --existing-body /tmp/aggregator/existing-body.md \
            --agent-enabled "${AGENT_ENABLED}" \
            $( [ -f /tmp/agent-job-a.json ] && echo "--job-a /tmp/agent-job-a.json" ) \
            $( [ -f /tmp/agent-job-b.json ] && echo "--job-b /tmp/agent-job-b.json" ) \
            $( [ -f /tmp/agent-job-c.json ] && echo "--job-c /tmp/agent-job-c.json" ) \
            --conflict-count "${CONFLICT_COUNT}" \
            --pr-number "${PR_NUMBER}" \
            --output-body /tmp/aggregator/composed-body.md \
            --overflow-dir /tmp/aggregator/overflow

          echo "composed_body_path=/tmp/aggregator/composed-body.md" >> "$GITHUB_OUTPUT"

          # Post overflow comments if any
          for overflow_file in /tmp/aggregator/overflow/overflow-*.md 2>/dev/null; do
            [ -f "$overflow_file" ] || continue
            gh pr comment "${PR_NUMBER}" --body-file "$overflow_file" || true
          done
        env:
          GH_TOKEN: {% raw %}${{ secrets.RELEASE_TOKEN }}{% endraw %}
```

- [ ] **Step 2: No commit yet — continues in Task 16**

---

## Task 16: Modify "Open or update PR" step to use composed body + render + smoke verify

**Files:**
- Modify: `.github/workflows/copier-update.yml.jinja`

- [ ] **Step 1: Locate the existing body-composition logic (#49)**

Run: `grep -n 'body=\|body+=' /mnt/code/fastmcp-server-template/.github/workflows/copier-update.yml.jinja | head -10`

Find where the existing workflow builds `$body` (the PR body) — typically as a shell variable inside the "Open or update PR" step.

- [ ] **Step 2: Refactor body construction to write to /tmp/aggregator/existing-body.md**

Modify the existing body-construction logic to write to a file BEFORE the aggregator step (Task 15) runs:

The existing step likely has something like:
```bash
body="## Template update: ..."$'\n'
body+="..."
gh pr edit ... --body "$body"
```

Restructure: split the body-construction into TWO steps:
1. A new step "Build #49 body content" that writes the existing body to `/tmp/aggregator/existing-body.md` (runs BEFORE the aggregator step from Task 15).
2. The existing "Open or update PR" step now reads from `/tmp/aggregator/composed-body.md` (the aggregator's output) instead of building `$body` inline.

If the aggregator step succeeded, the open-pr step uses the composed body. If aggregator failed (`steps.compose.outcome == 'failure'`), the open-pr step falls back to the original `/tmp/aggregator/existing-body.md`:

```yaml
      - name: Open or update PR
        env:
          # Existing env vars unchanged
          ...
        run: |
          set -euo pipefail
          if [ -f /tmp/aggregator/composed-body.md ]; then
            body_file=/tmp/aggregator/composed-body.md
          else
            body_file=/tmp/aggregator/existing-body.md
          fi
          gh pr edit ... --body-file "${body_file}" || gh pr create ... --body-file "${body_file}"
```

- [ ] **Step 3: Render the template + verify the workflow YAML is valid**

```bash
rm -rf /tmp/smoke
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke 2>&1 | tail -3

# Sanity check the rendered workflow file
python3 -c "
import yaml
with open('/tmp/smoke/.github/workflows/copier-update.yml') as f:
    content = f.read()
# Strip GitHub Actions placeholders for YAML parsing
import re
content = re.sub(r'\\\${{[^}]*}}', 'PLACEHOLDER', content)
yaml.safe_load(content)
print('YAML valid')
"
```

Expected: `YAML valid`.

- [ ] **Step 4: Run full template gate**

```bash
cd /tmp/smoke
uv sync --all-extras --all-groups 2>&1 | tail -2
uv run ruff check .
uv run ruff format --check .
uv run mypy src/ tests/ 2>&1 | tail -2
uv run pytest -x -q 2>&1 | tail -3
```

Expected: all green.

- [ ] **Step 5: Run the new aggregator-test job locally (template-side, not in /tmp/smoke)**

```bash
cd /mnt/code/fastmcp-server-template
uv run --with pytest pytest scripts/tests/ -v
```

Expected: 12 passed.

- [ ] **Step 6: Commit all the workflow changes from Tasks 13-16 atomically**

```bash
cd /mnt/code/fastmcp-server-template
git add .github/workflows/copier-update.yml.jinja
git commit -m "$(cat <<'EOF'
feat(workflow): wire claude-code agent into copier-update.yml (closes #36)

Extends copier-update.yml.jinja with five new failure-tolerant steps:

1. Clone fastmcp-server-template into /tmp/template (continue-on-error,
   provides agent context for both refs).
2. Check CLAUDE_CODE_OAUTH_TOKEN availability (gates agent steps; skips
   gracefully if missing).
3. Three parallel anthropics/claude-code-action@v1 invocations, one per
   job (A: conflict resolution with auto-commit; B: changelog triage;
   C: excluded-file evolution). Each continue-on-error: true.
4. Aggregator step (scripts/copier_update_aggregator.py) composes the
   final PR body from existing #49 sections + three agent JSONs;
   spills sections > 60k to follow-up comments.
5. PR open/update step uses the composed body when available, falls
   back to the existing #49 body when the aggregator failed.

A PR is always opened as long as the existing copier update + conflict
detection succeeded. Each agent state (success / skipped / rate-limited /
errored) renders a state-specific placeholder. The existing #49
sections (delta/notes/diff/conflicts) ALWAYS render regardless of agent
state.

Spec: docs/superpowers/specs/2026-05-04-copier-update-claude-agent-design.md

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 17: Local review circus + push as draft + monitor + flip ready

**Files:**
- None modified directly; only review + push + bot interaction

This task is the project's mandatory pre-flight per the global CLAUDE.md PR workflow rule (every PR, every type, runs both subagent reviewers before `gh pr create`).

- [ ] **Step 1: Confirm branch state**

```bash
cd /mnt/code/fastmcp-server-template
git log origin/main..HEAD --oneline
```

Expected: ~10-12 commits on the branch (one per task, plus the spec commit from brainstorming, plus this plan commit).

- [ ] **Step 2: Dispatch primary code-quality reviewer (`pr-review-toolkit:code-reviewer`)**

Use the Agent tool with `subagent_type: pr-review-toolkit:code-reviewer`. Prompt should include:

- The PR closes #36
- Two-part change: aggregator script (Python, with unit tests) + workflow integration
- Migration prediction: NA (this is a new feature, not a structural change to existing workflow)
- Verification: rendered template, full gate green (ruff, mypy, pytest), aggregator unit tests green (12 tests), workflow YAML parses

Bar: nothing flagged at any severity.

- [ ] **Step 3: Dispatch second-opinion reviewer (`superpowers:code-reviewer`)**

Same context, framed as fresh independent read. Look for:

- Whether the agent prompts are unambiguous
- Whether the aggregator's overflow heuristic is correct under adversarial input
- Whether failure-mode handling has any silent-failure risk
- Whether the workflow integration breaks any existing #49 behaviour

Bar: nothing flagged at any severity.

- [ ] **Step 4: Address any findings, re-run BOTH reviewers, until both clean**

Per the project's "Re-run until clean" rule.

- [ ] **Step 5: Push branch and open PR as draft**

```bash
git push -u origin feat/copier-update-claude-agent
gh pr create --draft --title "feat(workflow): wire claude-code agent into copier-update.yml" \
  --body-file <(cat <<'EOF'
## Summary

Closes #36. Extends downstream `copier-update.yml` with three Claude Code agent steps + an aggregator script that composes their structured JSON outputs into the existing #49-shaped PR body.

## Architecture

Five new failure-tolerant workflow steps + new Python aggregator + three agent prompt files. See `docs/superpowers/specs/2026-05-04-copier-update-claude-agent-design.md` for the full design.

## Test plan

- [x] `pytest scripts/tests/` — 12 aggregator unit tests pass
- [x] Render template against `tests/fixtures/smoke-answers.yml` — rendered downstream workflow YAML parses
- [x] Full template gate green: ruff, mypy, pytest
- [x] Local review circus clean (pr-review-toolkit + superpowers, both rounds, both nothing flagged)
- [ ] template-ci.yml runs the full gate + aggregator-test job once landed
- [ ] First downstream cron after merge serves as the integration test

## Out of scope

- Tier 3 (claude opens upstream PR on template-bug detection) — separate spec deferred per Q1.D in brainstorming.

## Spec + plan

- Spec: `docs/superpowers/specs/2026-05-04-copier-update-claude-agent-design.md`
- Plan: `docs/superpowers/plans/2026-05-04-copier-update-claude-agent.md`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)
```

- [ ] **Step 6: Schedule a wakeup ~5 min out for CI + claude-review**

After the PR opens, claude-review fires automatically on draft pushes. Schedule a wakeup to verify all 4 surfaces per the `feedback_read_all_review_surfaces.md` memory:

- CI status
- claude-review PR-level body
- Formal reviews
- Inline review comments

If any bot finds something, address per the one-round iteration cap, re-run BOTH local reviewers on the new diff, push fix, re-check.

- [ ] **Step 7: Flip ready**

Once all 4 surfaces clean: `gh pr ready <PR-number>`.

- [ ] **Step 8: Schedule a second wakeup ~10 min after flip-to-ready**

For gemini's flip-to-ready review (per `.gemini/config.yaml`'s `include_drafts: false` setting). If gemini flags anything: surface to user (cumulative-iteration cap).

- [ ] **Step 9: Report final state to user when both bots clean**

PR is then awaiting human merge — never merge autonomously.
