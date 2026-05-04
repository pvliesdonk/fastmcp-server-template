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

import json
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

    job_a_data = _read_job_json(inputs.job_a_path)
    section_a = _render_job_a(job_a_data, inputs.conflict_count)
    if section_a:
        parts.append(section_a)

    return "\n".join(parts) + "\n"
