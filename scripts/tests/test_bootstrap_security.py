"""Guard the security settings `bootstrap.yml` applies and the policy they point at.

Two things reach a generated project here and neither is visible by reading
the template:

- `bootstrap.yml.jinja` must keep a job that enables private vulnerability
  reporting, gated on the repository being public (GitHub offers the feature
  on public repositories only, see
  docs/design/reference/github-repository-security-settings.md), plus
  Dependabot alerts.  Losing the job silently returns every downstream to the
  state markdown-vault-mcp#1510 complained about.
- `SECURITY.md.jinja` must render into a policy whose reporting link targets
  the project's own repository and whose project-editable part sits inside
  the `DOMAIN-SECURITY` sentinel pair, the seam a downstream keeps across
  `copier update`.

Rendering goes through a plain Jinja environment: the workflow uses only
`{% raw %}` blocks around GitHub expressions, and the policy uses only
variable substitution.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from jinja2 import Environment

_REPO = Path(__file__).resolve().parents[2]
_BOOTSTRAP = _REPO / ".github" / "workflows" / "bootstrap.yml.jinja"
_SECURITY = _REPO / "SECURITY.md.jinja"


def _render(template: Path, **context: str) -> str:
    env = Environment(keep_trailing_newline=True, autoescape=False)
    return env.from_string(template.read_text(encoding="utf-8")).render(**context)


def _security_run_script() -> str:
    workflow = yaml.safe_load(_render(_BOOTSTRAP))
    job = workflow["jobs"]["security"]
    steps = job["steps"]
    assert len(steps) == 1, "the security job is one step, so one run log names every setting"
    assert steps[0]["env"]["GH_TOKEN"] == "${{ secrets.RELEASE_TOKEN }}", (
        "the security calls need administration:write, which only RELEASE_TOKEN carries"
    )
    return steps[0]["run"]


def test_bootstrap_enables_private_vulnerability_reporting_on_public_repos() -> None:
    script = _security_run_script()
    assert 'gh api -X PUT "repos/${REPO}/private-vulnerability-reporting"' in script
    assert "gh api \"repos/${REPO}\" --jq '.private'" in script, (
        "the PUT must be gated on visibility: GitHub documents private "
        "vulnerability reporting for public repositories only"
    )


def test_bootstrap_enables_dependabot_alerts() -> None:
    script = _security_run_script()
    assert 'gh api -X PUT "repos/${REPO}/vulnerability-alerts"' in script


def test_bootstrap_security_job_is_independent_of_the_settings_job() -> None:
    workflow = yaml.safe_load(_render(_BOOTSTRAP))
    assert "needs" not in workflow["jobs"]["security"], (
        "a ruleset failure must not hide the security settings, and vice versa"
    )


def test_security_policy_links_the_projects_own_reporting_form() -> None:
    rendered = _render(_SECURITY, github_org="acme", project_name="widget-mcp")
    assert "https://github.com/acme/widget-mcp/security/advisories/new" in rendered
    assert rendered.count("<!-- DOMAIN-SECURITY-START -->") == 1
    assert rendered.count("<!-- DOMAIN-SECURITY-END -->") == 1
    assert rendered.index("<!-- DOMAIN-SECURITY-START -->") < rendered.index(
        "<!-- DOMAIN-SECURITY-END -->"
    )
    assert "{{" not in rendered and "{%" not in rendered, "unrendered Jinja in the policy"


def test_security_policy_is_rendered_not_copied() -> None:
    plain = _REPO / "SECURITY.md"
    assert plain.exists() and _SECURITY.exists()
    assert "fastmcp-server-template/security/advisories/new" in plain.read_text(encoding="utf-8")
    assert "{{ github_org }}" in _SECURITY.read_text(encoding="utf-8"), (
        "the rendered policy must point at the generated project's repository, "
        "never at the template's"
    )
