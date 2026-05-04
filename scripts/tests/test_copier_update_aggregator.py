# scripts/tests/test_copier_update_aggregator.py
"""Tests for scripts/copier_update_aggregator.py."""
from __future__ import annotations

import sys
from pathlib import Path

# Make the script importable as a module (pytest runs from repo root).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import copier_update_aggregator as agg  # noqa: E402  # pyright: ignore[reportMissingImports]


def test_compose_body_all_jobs_skipped() -> None:
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
    subprocess.run(
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
