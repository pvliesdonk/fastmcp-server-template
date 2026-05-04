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


def _placeholder(section_title: str, status: str) -> str:
    """Render a state-specific placeholder for a section."""
    if status == "rate_limited":
        msg = "⏳ Agent rate-limited — full analysis will retry on next cron."
    else:  # generic error or missing-but-expected
        msg = "⚠️ Agent failed — see workflow log."
    return f"### {section_title}\n\n{msg}\n"


def _render_job_a(data: dict | None, conflict_count: int) -> str:
    """Render the 🔧 Conflict resolutions section."""
    if conflict_count == 0:
        return ""  # Job A is gated; no section if no conflicts
    if data is None:
        return _placeholder("🔧 Conflict resolutions", "error")
    status = data.get("status", "error")
    if status == "rate_limited":
        return _placeholder("🔧 Conflict resolutions", "rate_limited")
    if status != "ok":
        return _placeholder("🔧 Conflict resolutions", "error")

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


def _render_job_b(data: dict | None) -> str:
    """Render the ✨ New features in this update section."""
    if data is None:
        return _placeholder("✨ New features in this update", "error")
    status = data.get("status", "error")
    if status == "rate_limited":
        return _placeholder("✨ New features in this update", "rate_limited")
    if status != "ok":
        return _placeholder("✨ New features in this update", "error")

    entries = data.get("entries", [])
    if not entries:
        return ""  # No features = no section (rare — refs differed but changelog empty)

    by_class: dict[str, list[dict]] = {"needs-opt-in": [], "ships-automatically": [], "informational": []}
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


def _render_job_c(data: dict | None) -> str:
    """Render the 📦 Excluded-file upstream changes section."""
    if data is None:
        return _placeholder("📦 Excluded-file upstream changes", "error")
    status = data.get("status", "error")
    if status == "rate_limited":
        return _placeholder("📦 Excluded-file upstream changes", "rate_limited")
    if status != "ok":
        return _placeholder("📦 Excluded-file upstream changes", "error")

    files = data.get("files", [])
    if not files:
        return ""

    by_class: dict[str, list[dict]] = {"recommend-port": [], "informational": [], "skip": []}
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

    job_b_data = _read_job_json(inputs.job_b_path)
    section_b = _render_job_b(job_b_data)
    if section_b:
        parts.append(section_b)

    job_c_data = _read_job_json(inputs.job_c_path)
    section_c = _render_job_c(job_c_data)
    if section_c:
        parts.append(section_c)

    return "\n".join(parts) + "\n"
