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
