"""The roadmapping convention's scaffold, asserted on the smoke render.

Covers the pieces `copier copy` lays down for the fleet planning model: the
planning labels bootstrap ensures, the issue forms (epic "Done when",
research, feature surface impact), the `roadmapping` skill and its Claude
Code symlink, the seeded roadmap index, the shipped GitHub-planning-objects
reference page inside a valid OKF bundle root, and the always-loaded
pointer in AGENTS.md.  Skill-name drift across the four registries is
guarded separately by test_shared_skill_paths.py.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

FORMS = Path(".github/ISSUE_TEMPLATE")


def _form(render: Path, name: str) -> dict:
    return yaml.safe_load((render / FORMS / name).read_text())


def _field(form: dict, field_id: str) -> dict:
    matches = [item for item in form["body"] if item.get("id") == field_id]
    assert len(matches) == 1, f"expected one body item with id {field_id!r}"
    return matches[0]


def test_bootstrap_ensures_planning_labels(smoke_render: Path) -> None:
    text = (smoke_render / ".github/workflows/bootstrap.yml").read_text()
    for label in ("research", "refinement", "breaking"):
        assert f"gh label create {label} \\" in text, label
    assert "fallback for a package milestone" in text


def test_epic_form_has_frozen_done_when(smoke_render: Path) -> None:
    form = _form(smoke_render, "epic.yml")
    field = _field(form, "done-when")
    assert field["type"] == "textarea"
    assert field["validations"]["required"] is True
    assert "frozen" in field["attributes"]["description"]
    # The release highlight stays a separate, editable field.
    assert _field(form, "user-facing-summary")["validations"]["required"] is True
    after_filing = form["body"][-1]["attributes"]["value"]
    assert "refinement sub-issue" in after_filing
    assert "Package milestone" in after_filing


def test_research_form(smoke_render: Path) -> None:
    form = _form(smoke_render, "research.yml")
    assert form["labels"] == ["research"]
    for required_id in ("question", "decision", "appetite"):
        assert _field(form, required_id)["validations"]["required"] is True
    appetite = _field(form, "appetite")
    assert appetite["type"] == "dropdown"
    assert len(appetite["attributes"]["options"]) == 3
    assert _field(form, "resolves")["validations"]["required"] is False


def test_feature_form_asks_surface_impact(smoke_render: Path) -> None:
    field = _field(_form(smoke_render, "feature-request.yml"), "surface-impact")
    assert field["type"] == "dropdown"
    assert field["validations"]["required"] is True
    assert "Not sure" in field["attributes"]["options"]


def test_roadmapping_skill_rendered(smoke_render: Path) -> None:
    skill = smoke_render / ".agents/skills/roadmapping/SKILL.md"
    text = skill.read_text()
    assert "## Packages" in text
    assert "DOMAIN-ROADMAPPING-START" in text
    assert "TEMPLATE-OWNED" in text
    assert (
        smoke_render / ".agents/skills/roadmapping/references/refinement-review.md"
    ).is_file()
    link = smoke_render / ".claude/skills/roadmapping"
    assert link.is_symlink()
    assert link.readlink() == Path("../../.agents/skills/roadmapping")


def test_roadmap_index_seeded(smoke_render: Path) -> None:
    text = (smoke_render / "docs/design/roadmap.md").read_text()
    assert "agent-authored" in text
    assert "## Packages" in text
    assert "## Known unknowns" in text
    # Argument only: the seed must not teach state-tracking by example.
    assert "%" not in text


def test_reference_bundle_valid(smoke_render: Path) -> None:
    page = smoke_render / "docs/design/reference/github-planning-objects.md"
    assert page.is_file()
    assert (smoke_render / "docs/design/reference/index.md").is_file()
    assert (smoke_render / "docs/design/reference/log.md").is_file()
    proc = subprocess.run(
        [sys.executable, "scripts/check_references.py", "docs/design/reference"],
        cwd=smoke_render,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "github-planning-objects" in proc.stdout


def test_agents_md_points_at_the_roadmap(smoke_render: Path) -> None:
    text = (smoke_render / "AGENTS.md").read_text()
    assert "docs/design/roadmap.md" in text
    assert "- `roadmapping` —" in text


def test_pr_template_carries_design_section(smoke_render: Path) -> None:
    text = (smoke_render / ".github/PULL_REQUEST_TEMPLATE.md").read_text()
    assert "## Design" in text
    assert "docs/design/` do not now show" in text
