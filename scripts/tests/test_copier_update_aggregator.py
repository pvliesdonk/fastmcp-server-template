# scripts/tests/test_copier_update_aggregator.py
"""Tests for scripts/copier_update_aggregator.py."""

from __future__ import annotations

import sys
from pathlib import Path

# Make the script importable as a module (pytest runs from repo root).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import copier_update_aggregator as agg  # pyright: ignore[reportMissingImports]


def test_compose_body_all_jobs_skipped() -> None:
    """When agent_enabled=False, body has only #49 sections + skip notices."""
    inputs = agg.AggregatorInputs(
        existing_body="## Template update: v1.0.0 → v1.1.0\n\n### Release notes\n\n- #1 feat: foo\n",
        agent_enabled=False,
        job_a_path=None,
        job_b_path=None,
        job_c_path=None,
        conflict_count=0,
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
    )
    body = agg.compose_body(inputs)
    assert "🔧 Conflict resolutions" in body
    assert "⚠️" in body
    assert "Agent failed" in body
    assert "workflow log" in body


def test_compose_body_job_b_rate_limited(write_job_json) -> None:
    """Job B rate-limited: shows transient-failure placeholder."""
    job_b = write_job_json(
        "agent-job-b",
        {"status": "rate_limited", "message": "429 from anthropic API"},
    )
    inputs = agg.AggregatorInputs(
        existing_body="## Template update: v1.0.0 → v1.1.0\n",
        agent_enabled=True,
        job_a_path=None,
        job_b_path=job_b,
        job_c_path=None,
        conflict_count=0,
    )
    body = agg.compose_body(inputs)
    assert "✨ New features in this update" in body
    assert "⏳" in body
    assert "rate-limited" in body or "rate_limited" in body
    assert "next cron" in body


def test_unknown_classification_falls_back_to_informational_job_b(
    write_job_json,
) -> None:
    """Job B entries with off-spec classification (typo / wrong casing) fall back
    to the 'informational' rollup rather than vanishing silently."""
    job_b = write_job_json(
        "agent-job-b",
        {
            "status": "ok",
            "entries": [
                {
                    "pr_number": 1,
                    "title": "off-spec classification",
                    "classification": "NEEDS-OPT-IN",  # wrong casing
                    "summary": "x",
                },
                {
                    "pr_number": 2,
                    "title": "typo classification",
                    "classification": "internal",  # not in the 3-key set
                    "summary": "y",
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
    )
    body = agg.compose_body(inputs)
    # Both entries appear in the rollup count + ID list (informational stratum).
    assert "#1" in body
    assert "#2" in body


def test_unknown_classification_falls_back_to_informational_job_c(
    write_job_json,
) -> None:
    """Job C files with off-spec classification fall back to 'informational'."""
    job_c = write_job_json(
        "agent-job-c",
        {
            "status": "ok",
            "files": [
                {
                    "file": "weird.md",
                    "classification": "RECOMMEND-PORT",  # wrong casing
                    "summary": "x",
                    "diff_summary": "y",
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
    )
    body = agg.compose_body(inputs)
    # Entry appears in body (informational stratum) instead of being dropped.
    assert "weird.md" in body


def test_string_or_null_pr_number_does_not_crash_sort_job_b(
    write_job_json,
) -> None:
    """Job B sort tolerates string and null pr_number values without TypeError.

    LLMs may emit `pr_number: "89"` (string) or `pr_number: null` for
    malformed entries. Without coercion the mixed-type sort would raise
    TypeError, which `_safe_render` would catch and degrade the WHOLE
    section to an error placeholder.
    """
    job_b = write_job_json(
        "agent-job-b",
        {
            "status": "ok",
            "entries": [
                {
                    "pr_number": "89",  # string instead of int
                    "title": "string pr",
                    "classification": "ships-automatically",
                    "summary": "",
                },
                {
                    "pr_number": None,  # null
                    "title": "null pr",
                    "classification": "ships-automatically",
                    "summary": "",
                },
                {
                    "pr_number": 50,  # int (the normal case)
                    "title": "int pr",
                    "classification": "ships-automatically",
                    "summary": "",
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
    )
    body = agg.compose_body(inputs)
    # Job B's section rendered without TypeError-degrading to error. (Job C
    # may show a missing-file placeholder; we assert about Job B specifically.)
    start = body.find("### ✨ New features")
    end = body.find("\n### ", start + 1)
    job_b_section = body[start : end if end != -1 else len(body)]
    assert "Agent failed" not in job_b_section
    assert "string pr" in job_b_section or "#89" in job_b_section
    assert "int pr" in job_b_section or "#50" in job_b_section


def test_hash_prefixed_pr_number_does_not_crash_sort_job_b(
    write_job_json,
) -> None:
    """Job B sort tolerates LLM-emitted `#`-prefixed pr_number forms.

    LLMs sometimes emit `pr_number: "#89"` mirroring how PRs are written
    in prose. Without `lstrip("#")` int() raises ValueError, which
    `_safe_render` would catch and degrade the WHOLE section.
    """
    job_b = write_job_json(
        "agent-job-b",
        {
            "status": "ok",
            "entries": [
                {
                    "pr_number": "#89",
                    "title": "hash-prefixed",
                    "classification": "ships-automatically",
                    "summary": "",
                },
                {
                    "pr_number": 50,
                    "title": "plain int",
                    "classification": "ships-automatically",
                    "summary": "",
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
    )
    body = agg.compose_body(inputs)
    start = body.find("### ✨ New features")
    end = body.find("\n### ", start + 1)
    job_b_section = body[start : end if end != -1 else len(body)]
    assert "Agent failed" not in job_b_section
    assert "hash-prefixed" in job_b_section
    assert "plain int" in job_b_section


def test_null_file_does_not_crash_sort_job_c(write_job_json) -> None:
    """Job C sort tolerates null file values without TypeError."""
    job_c = write_job_json(
        "agent-job-c",
        {
            "status": "ok",
            "files": [
                {
                    "file": None,  # null
                    "classification": "informational",
                    "summary": "x",
                    "diff_summary": "y",
                },
                {
                    "file": "real.md",
                    "classification": "informational",
                    "summary": "x",
                    "diff_summary": "y",
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
    )
    body = agg.compose_body(inputs)
    # Job C's section rendered without TypeError-degrading to error. (Job B
    # may show a missing-file placeholder; we assert about Job C specifically.)
    job_c_section = body[body.find("### 📦 Excluded-file") :]
    assert "Agent failed" not in job_c_section
    assert "real.md" in job_c_section


def test_compose_body_job_c_rate_limited(write_job_json) -> None:
    """Job C rate-limited: shows transient-failure placeholder."""
    job_c = write_job_json(
        "agent-job-c",
        {"status": "rate_limited", "message": "429 from anthropic API"},
    )
    inputs = agg.AggregatorInputs(
        existing_body="## Template update: v1.0.0 → v1.1.0\n",
        agent_enabled=True,
        job_a_path=None,
        job_b_path=None,
        job_c_path=job_c,
        conflict_count=0,
    )
    body = agg.compose_body(inputs)
    assert "📦 Excluded-file upstream changes" in body
    assert "⏳" in body
    assert "rate-limited" in body or "rate_limited" in body
    assert "next cron" in body


def test_overflow_section_boundary_ignores_agent_subheaders(
    write_job_json, tmp_path: Path
) -> None:
    """Section boundary detection anchors to known SECTION_MARKERS only.

    A bare `body.find("\\n### ", ...)` would split a section prematurely
    if agent-supplied text (Job A articulation, Job B/C summaries) contained
    a `### Sub-header` line. The boundary search instead uses the next known
    marker so agent text is preserved intact.
    """
    # ~6000 lines * ~12 chars/line ~= 72k chars — enough to push the body
    # past BODY_LIMIT (60k) so overflow actually triggers.  The previous
    # 800-line filler stayed under the limit, leaving the overflow branch
    # unverified (the `assert overflow` below now fails the test if that
    # regresses).
    long_summary = "intro paragraph\n\n### Background subsection\n\n" + (
        "filler line\n" * 6000
    )
    job_b = write_job_json(
        "agent-job-b",
        {
            "status": "ok",
            "entries": [
                {
                    "pr_number": 1,
                    "title": "feat with subheader in summary",
                    "classification": "needs-opt-in",
                    "summary": long_summary,
                },
            ],
        },
    )
    overflow_dir = tmp_path / "overflow"
    inputs = agg.AggregatorInputs(
        existing_body="## Template update: v1.0.0 → v1.1.0\n",
        agent_enabled=True,
        job_a_path=None,
        job_b_path=job_b,
        job_c_path=None,
        conflict_count=0,
    )
    body, overflow = agg.compose_body_with_overflow(inputs, overflow_dir=overflow_dir)
    assert overflow, (
        "expected overflow with 6000-line filler (~72k chars > 60k BODY_LIMIT)"
    )
    spilled = overflow[0].read_text(encoding="utf-8")
    # The full agent summary including the `### Background subsection`
    # line must travel with the section, not be left orphaned in body.
    assert "Background subsection" in spilled
    assert "Background subsection" not in body


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
    )
    body, overflow = agg.compose_body_with_overflow(inputs, overflow_dir=overflow_dir)
    assert len(body) <= 60_000
    # Body preserves the section-name signal in the spill placeholder so
    # the operator can tell which section was spilled at a glance.
    assert "New features in this update" in body
    assert "follow-up comment" in body
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
                {
                    "pr_number": 1,
                    "title": "small feature",
                    "classification": "ships-automatically",
                    "summary": "applied",
                }
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
    )
    body, overflow = agg.compose_body_with_overflow(
        inputs, overflow_dir=tmp_path / "overflow"
    )
    assert len(body) < 60_000
    assert overflow == []


def test_deterministic_ordering(write_job_json) -> None:
    """Same inputs across two runs produce byte-identical body."""
    payload = {
        "status": "ok",
        "entries": [
            {
                "pr_number": 100,
                "title": "a",
                "classification": "ships-automatically",
                "summary": "x",
            },
            {
                "pr_number": 200,
                "title": "b",
                "classification": "needs-opt-in",
                "summary": "y",
            },
            {
                "pr_number": 50,
                "title": "c",
                "classification": "ships-automatically",
                "summary": "z",
            },
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
    )
    inputs2 = agg.AggregatorInputs(
        existing_body="## Template update: v1.0.0 → v1.1.0\n",
        agent_enabled=True,
        job_a_path=None,
        job_b_path=job_b2,
        job_c_path=None,
        conflict_count=0,
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
    )
    body = agg.compose_body(inputs)
    assert "⚠️" in body and "failed" in body.lower()


def test_cli_entry_point_writes_body_file(tmp_path: Path, write_job_json) -> None:
    """Invoking the script via subprocess writes a composed body to --output."""
    import subprocess

    job_a = write_job_json(
        "agent-job-a",
        {
            "status": "ok",
            "auto_resolved": [
                {
                    "file": "docs/foo.md",
                    "region": "L1-L5",
                    "articulation": "trivial",
                    "commit_sha": "abc1234",
                }
            ],
            "needs_review": [],
        },
    )
    existing = tmp_path / "existing.md"
    existing.write_text("## Template update: v1.0.0 → v1.1.0\n", encoding="utf-8")
    output = tmp_path / "out.md"
    overflow_dir = tmp_path / "overflow"

    script = Path(__file__).resolve().parent.parent / "copier_update_aggregator.py"
    subprocess.run(
        [
            sys.executable,
            str(script),
            "--existing-body",
            str(existing),
            "--agent-enabled",
            "true",
            "--job-a",
            str(job_a),
            "--conflict-count",
            "2",
            "--output-body",
            str(output),
            "--overflow-dir",
            str(overflow_dir),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert output.exists()
    body = output.read_text(encoding="utf-8")
    assert "## Template update: v1.0.0 → v1.1.0" in body
    assert "🔧 Conflict resolutions" in body


def test_template_not_advanced_suppresses_jobs_b_and_c() -> None:
    """When template_advanced=False, Jobs B and C sections are omitted entirely.

    Even if the JSON files are absent (Jobs B/C were correctly gated off in the
    workflow), the aggregator should NOT render 'Agent failed' placeholders for
    them — the gating is intentional, not a failure.
    """
    inputs = agg.AggregatorInputs(
        existing_body="## Template update: v1.0.0 → v1.0.0 (re-run)\n",
        agent_enabled=True,
        job_a_path=None,
        job_b_path=None,
        job_c_path=None,
        conflict_count=0,
        template_advanced=False,
    )
    body = agg.compose_body(inputs)
    assert "✨ New features" not in body
    assert "📦 Excluded-file" not in body
    assert "Agent failed" not in body


def test_job_b_entries_sorted_by_pr_number(write_job_json) -> None:
    """Job B entries render in PR# ascending order regardless of input order."""
    job_b = write_job_json(
        "agent-job-b",
        {
            "status": "ok",
            "entries": [
                # Deliberately scrambled input order
                {
                    "pr_number": 100,
                    "title": "c",
                    "classification": "ships-automatically",
                    "summary": "",
                },
                {
                    "pr_number": 50,
                    "title": "a",
                    "classification": "ships-automatically",
                    "summary": "",
                },
                {
                    "pr_number": 75,
                    "title": "b",
                    "classification": "ships-automatically",
                    "summary": "",
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
    )
    body = agg.compose_body(inputs)
    # Find positions of the three entries in the output
    pos_50 = body.find("#50")
    pos_75 = body.find("#75")
    pos_100 = body.find("#100")
    assert 0 <= pos_50 < pos_75 < pos_100  # ascending order in body


def test_overflow_loop_terminates_when_existing_body_alone_exceeds_limit(
    write_job_json, tmp_path: Path
) -> None:
    """Pathological case: existing #49 body alone is > 60k chars.

    Aggregator should spill each agent section ONCE (each spill produces a
    short replacement) and then break out of the loop, NOT loop forever
    re-picking the replacement as a section to spill. Replacement uses a
    non-`###` heading so the section finder skips it after spilling.
    """
    long_existing = "## Template update: v1.0.0 → v2.0.0\n\n" + ("x" * 70_000)
    job_a = write_job_json(
        "agent-job-a",
        {
            "status": "ok",
            "auto_resolved": [
                {
                    "file": "f.md",
                    "region": "L1-L10",
                    "articulation": "y" * 1000,
                    "commit_sha": "deadbeef",
                }
            ],
            "needs_review": [],
        },
    )
    inputs = agg.AggregatorInputs(
        existing_body=long_existing,
        agent_enabled=True,
        job_a_path=job_a,
        job_b_path=None,
        job_c_path=None,
        conflict_count=1,
    )
    overflow_dir = tmp_path / "overflow"
    body, overflow = agg.compose_body_with_overflow(inputs, overflow_dir=overflow_dir)
    # The loop must terminate (this would hang the test if it didn't);
    # at most ONE overflow per agent section.
    assert len(overflow) <= 3
    # Body still exceeds limit (because existing_body alone does), but
    # the loop didn't infinitely spill stub replacements.
    assert "full analysis posted as a follow-up comment" in body


def test_agent_disabled_renders_per_section_placeholders() -> None:
    """When agent_enabled=False, sections that WOULD have run get distinct skip notices.

    Sections gated out (e.g. Job A with no conflicts) are omitted entirely.
    """
    inputs = agg.AggregatorInputs(
        existing_body="## Template update: v1.0.0 → v1.1.0\n",
        agent_enabled=False,
        job_a_path=None,
        job_b_path=None,
        job_c_path=None,
        conflict_count=2,  # Job A would have run
        template_advanced=True,  # Jobs B/C would have run
    )
    body = agg.compose_body(inputs)
    assert "🔧 Conflict resolutions" in body
    assert "✨ New features" in body
    assert "📦 Excluded-file" in body
    # The disabled notice appears (per-section, but the notice itself appears
    # multiple times — once under each section's heading)
    assert body.count("Agent disabled") >= 3
    assert "CLAUDE_CODE_OAUTH_TOKEN" in body


def test_no_agent_sections_suppresses_agent_analysis_header() -> None:
    """Agent-analysis header is suppressed when no sections will follow it.

    Edge case: agent_enabled=True with all gates closed (no conflicts,
    template_advanced=False) — previously emitted an orphaned `## Agent
    analysis` separator with nothing under it.
    """
    existing = "## Template update: v1.0.0 → v1.0.0 (re-run)\n"
    inputs = agg.AggregatorInputs(
        existing_body=existing,
        agent_enabled=True,
        job_a_path=None,
        job_b_path=None,
        job_c_path=None,
        conflict_count=0,
        template_advanced=False,
    )
    body = agg.compose_body(inputs)
    assert "## Agent analysis" not in body
    # Body is just the existing body (single trailing newline).  Asserting
    # equality rather than `"---" not in body` because the real workflow's
    # existing-body construction may include horizontal rules for unrelated
    # reasons; the regression invariant is "nothing was appended after the
    # existing body", not "no horizontal rule appears anywhere".
    assert body.rstrip() == existing.rstrip()


def test_agent_disabled_no_gates_suppresses_agent_analysis_header() -> None:
    """Same suppression holds when agent_enabled=False and both gates closed."""
    existing = "## Template update: v1.0.0 → v1.0.0 (re-run)\n"
    inputs = agg.AggregatorInputs(
        existing_body=existing,
        agent_enabled=False,
        job_a_path=None,
        job_b_path=None,
        job_c_path=None,
        conflict_count=0,
        template_advanced=False,
    )
    body = agg.compose_body(inputs)
    assert "## Agent analysis" not in body
    assert "Agent disabled" not in body  # nothing to disable; no section emitted
    assert body.rstrip() == existing.rstrip()


def test_job_b_informational_rollup_drops_null_pr_numbers(write_job_json) -> None:
    """Informational entries with pr_number=null are dropped from the rollup.

    Without filtering, an LLM-emitted entry with `pr_number: null` rendered
    as the literal "#None" inside the rollup line.
    """
    job_b = write_job_json(
        "agent-job-b",
        {
            "status": "ok",
            "entries": [
                {
                    "pr_number": None,
                    "title": "internal merge with no PR",
                    "classification": "informational",
                    "summary": "",
                },
                {
                    "pr_number": 87,
                    "title": "real PR",
                    "classification": "informational",
                    "summary": "",
                },
                {
                    "pr_number": 91,
                    "title": "another real PR",
                    "classification": "informational",
                    "summary": "",
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
    )
    body = agg.compose_body(inputs)
    assert "#None" not in body
    assert "#87" in body
    assert "#91" in body
    # Count reflects the displayed entries (2), not the raw bucket (3).
    assert "(2 entries)" in body


def test_job_b_informational_rollup_all_null_pr_numbers_omits_rollup_line(
    write_job_json,
) -> None:
    """If every informational entry has null pr_number, the rollup line is omitted entirely."""
    job_b = write_job_json(
        "agent-job-b",
        {
            "status": "ok",
            "entries": [
                {
                    "pr_number": None,
                    "title": "internal a",
                    "classification": "informational",
                    "summary": "",
                },
                {
                    "pr_number": None,
                    "title": "internal b",
                    "classification": "informational",
                    "summary": "",
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
    )
    body = agg.compose_body(inputs)
    assert "#None" not in body
    assert "Internal / no downstream effect" not in body


def test_job_b_bullet_strata_coerce_null_pr_number_to_placeholder(
    write_job_json,
) -> None:
    """needs-opt-in and ships-automatically bullets coerce null pr_number to #?.

    Bullet entries carry prose detail (title, summary) that's useful even
    when the PR number is missing, so they're preserved with a placeholder
    rather than dropped (which is the rollup's choice).
    """
    job_b = write_job_json(
        "agent-job-b",
        {
            "status": "ok",
            "entries": [
                {
                    "pr_number": None,
                    "title": "untracked merge a",
                    "classification": "needs-opt-in",
                    "summary": "Pulled in via cherry-pick; manual opt-in needed.",
                },
                {
                    "pr_number": None,
                    "title": "untracked merge b",
                    "classification": "ships-automatically",
                    "summary": "",
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
    )
    body = agg.compose_body(inputs)
    assert "#None" not in body
    assert "#? untracked merge a — needs opt-in." in body
    assert "#? untracked merge b — applied this run" in body
    # Prose detail is preserved
    assert "Pulled in via cherry-pick" in body


def test_job_c_bullet_strata_coerce_null_file_to_placeholder(
    write_job_json,
) -> None:
    """recommend-port and informational bullets coerce null file to `(unnamed)`."""
    job_c = write_job_json(
        "agent-job-c",
        {
            "status": "ok",
            "files": [
                {
                    "file": None,
                    "classification": "recommend-port",
                    "summary": "Untracked port — file path missing.",
                    "diff_summary": "+10 lines on something",
                },
                {
                    "file": None,
                    "classification": "informational",
                    "summary": "Trivial change without path.",
                    "diff_summary": "1 line",
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
    )
    body = agg.compose_body(inputs)
    # Backticked literal `None` must not leak into the body
    assert "`None`" not in body
    assert "`(unnamed)`: Untracked port — file path missing." in body
    assert "`(unnamed)`: Trivial change without path." in body


def test_job_a_no_resolutions_suppresses_section_header(write_job_json) -> None:
    """Job A returns empty when status=ok with both auto_resolved and needs_review empty.

    Edge case: agent ran on a real conflict (conflict_count > 0), reported
    status=ok, but neither stratum populated.  Previously emitted an
    orphaned `### 🔧 Conflict resolutions` header with nothing under it;
    now the whole section is suppressed and (since this was the only
    section) the parent `## Agent analysis` header is suppressed too.
    """
    job_a = write_job_json(
        "agent-job-a",
        {"status": "ok", "auto_resolved": [], "needs_review": []},
    )
    inputs = agg.AggregatorInputs(
        existing_body="## Template update: v1.0.0 → v1.1.0\n",
        agent_enabled=True,
        job_a_path=job_a,
        job_b_path=None,
        job_c_path=None,
        conflict_count=2,
        template_advanced=False,  # only Job A would run; suppression cascades
    )
    body = agg.compose_body(inputs)
    assert "🔧 Conflict resolutions" not in body
    assert "## Agent analysis" not in body


def test_job_b_only_informational_with_null_pr_suppresses_section_header(
    write_job_json,
) -> None:
    """Job B returns empty when entries exist but every stratum filters out.

    Edge case: every entry is informational with null pr_number — the rollup
    drops them all, leaving no content under the `### ✨` header.  Also
    pass an empty Job C JSON so its render returns "" cleanly (rather than
    the error placeholder a missing job_c_path would produce while
    template_advanced=True).
    """
    job_b = write_job_json(
        "agent-job-b",
        {
            "status": "ok",
            "entries": [
                {
                    "pr_number": None,
                    "title": "untracked a",
                    "classification": "informational",
                    "summary": "",
                },
                {
                    "pr_number": None,
                    "title": "untracked b",
                    "classification": "informational",
                    "summary": "",
                },
            ],
        },
    )
    job_c_empty = write_job_json("agent-job-c", {"status": "ok", "files": []})
    inputs = agg.AggregatorInputs(
        existing_body="## Template update: v1.0.0 → v1.1.0\n",
        agent_enabled=True,
        job_a_path=None,
        job_b_path=job_b,
        job_c_path=job_c_empty,
        conflict_count=0,
    )
    body = agg.compose_body(inputs)
    assert "✨ New features in this update" not in body
    assert "## Agent analysis" not in body


def test_job_c_only_skip_with_null_file_suppresses_section_header(
    write_job_json,
) -> None:
    """Job C returns empty when only skip entries exist and every one has null file.

    Empty Job B JSON paired with the null-file Job C so the missing-data
    error placeholder doesn't smear the assertion.
    """
    job_c = write_job_json(
        "agent-job-c",
        {
            "status": "ok",
            "files": [
                {
                    "file": None,
                    "classification": "skip",
                    "summary": "untracked a",
                    "diff_summary": "",
                },
                {
                    "file": None,
                    "classification": "skip",
                    "summary": "untracked b",
                    "diff_summary": "",
                },
            ],
        },
    )
    job_b_empty = write_job_json("agent-job-b", {"status": "ok", "entries": []})
    inputs = agg.AggregatorInputs(
        existing_body="## Template update: v1.0.0 → v1.1.0\n",
        agent_enabled=True,
        job_a_path=None,
        job_b_path=job_b_empty,
        job_c_path=job_c,
        conflict_count=0,
    )
    body = agg.compose_body(inputs)
    assert "📦 Excluded-file upstream changes" not in body
    assert "## Agent analysis" not in body


# ── Silent-failure annotations ────────────────────────────────────────────────


def test_read_job_json_no_warning_for_none_path(capsys) -> None:
    """Path=None is expected-missing; no stderr annotation emitted."""
    result = agg._read_job_json(None)
    assert result is None
    assert capsys.readouterr().err == ""


def test_read_job_json_no_warning_for_missing_file(tmp_path, capsys) -> None:
    """Non-existent path is expected-missing; no stderr annotation emitted."""
    result = agg._read_job_json(tmp_path / "absent.json")
    assert result is None
    assert capsys.readouterr().err == ""


def test_read_job_json_no_warning_for_directory_path(tmp_path, capsys) -> None:
    """Directory path fails is_file() and returns None silently (not an OSError warning)."""
    result = agg._read_job_json(tmp_path)  # tmp_path is a directory
    assert result is None
    assert capsys.readouterr().err == ""


def test_read_job_json_warns_on_malformed_json(tmp_path, capsys) -> None:
    """JSONDecodeError emits a ::warning:: annotation to stderr."""
    bad = tmp_path / "job.json"
    bad.write_text("not valid json {", encoding="utf-8")
    result = agg._read_job_json(bad)
    assert result is None
    err = capsys.readouterr().err
    assert "::warning::" in err
    assert str(bad) in err


def test_read_job_json_warns_on_oserror(tmp_path, capsys, monkeypatch) -> None:
    """OSError emits a ::warning:: annotation to stderr."""
    p = tmp_path / "job.json"
    p.write_text('{"status": "ok"}', encoding="utf-8")

    def raise_oserror(*_args, **_kwargs):
        raise OSError("permission denied")

    monkeypatch.setattr(type(p), "read_text", raise_oserror)
    result = agg._read_job_json(p)
    assert result is None
    err = capsys.readouterr().err
    assert "::warning::" in err
    assert str(p) in err


def test_read_job_json_warns_on_unicode_error(tmp_path, capsys) -> None:
    """UnicodeDecodeError emits a ::warning:: annotation to stderr."""
    p = tmp_path / "job.json"
    p.write_bytes(b"\xff\xfe not utf-8")  # invalid UTF-8 sequence

    result = agg._read_job_json(p)
    assert result is None
    err = capsys.readouterr().err
    assert "::warning::" in err
    assert str(p) in err


def test_main_missing_existing_body_exits_1_with_error_annotation(
    tmp_path, capsys
) -> None:
    """main() returns exit code 1 with a ::error:: annotation when --existing-body is absent."""
    rc = agg.main(
        [
            "--existing-body",
            str(tmp_path / "nonexistent.md"),
            "--agent-enabled",
            "false",
            "--conflict-count",
            "0",
            "--output-body",
            str(tmp_path / "out.md"),
            "--overflow-dir",
            str(tmp_path / "overflow"),
        ]
    )
    assert rc == 1
    err = capsys.readouterr().err
    assert "::error::" in err
    assert "nonexistent.md" in err


def test_job_c_skip_rollup_drops_null_file(write_job_json) -> None:
    """skip rollup mirrors Job B informational rollup: null file dropped, count adjusts."""
    job_c = write_job_json(
        "agent-job-c",
        {
            "status": "ok",
            "files": [
                {
                    "file": None,
                    "classification": "skip",
                    "summary": "untracked",
                    "diff_summary": "",
                },
                {
                    "file": ".github/workflows/template-ci.yml",
                    "classification": "skip",
                    "summary": "Template-CI plumbing only.",
                    "diff_summary": "+2 lines",
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
    )
    body = agg.compose_body(inputs)
    assert "`None`" not in body
    assert "`.github/workflows/template-ci.yml`" in body
    # Count reflects the displayed entry (1), not the raw bucket (2).
    assert "(1 file)" in body
