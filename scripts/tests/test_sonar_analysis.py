"""CI-based SonarQube Cloud analysis in the rendered project.

A project's `ci.yml` runs the scan in its own `sonar` job, fed the coverage
report of the Python 3.14 test run, with settings from the rendered
`sonar-project.properties`.  These tests read the smoke render, the tree a
downstream actually gets; Codecov is gone from it entirely.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml


def _properties(render: Path) -> dict[str, str]:
    """The effective settings: later keys replace earlier ones, as in the scanner."""
    values: dict[str, str] = {}
    for line in (render / "sonar-project.properties").read_text().splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    return values


def _ci(render: Path) -> dict:
    return yaml.safe_load((render / ".github/workflows/ci.yml").read_text())


def test_project_key_matches_every_readme_badge(smoke_render: Path) -> None:
    props = _properties(smoke_render)
    assert props["sonar.organization"] == "pvliesdonk"
    assert props["sonar.projectKey"] == "pvliesdonk_smoke-mcp"
    readme = (smoke_render / "README.md").read_text()
    keys = set(
        re.findall(
            r"sonarcloud\.io/api/project_badges/measure\?project=([^&]+)", readme
        )
    )
    assert keys == {props["sonar.projectKey"]}
    for metric in ("alert_status", "coverage", "security_rating", "reliability_rating"):
        assert f"&metric={metric})" in readme, metric


def test_tests_are_test_code_and_nothing_is_indexed_twice(smoke_render: Path) -> None:
    props = _properties(smoke_render)
    assert props["sonar.sources"] == "."
    assert props["sonar.tests"] == "tests"
    # With sources at the root, tests/ must be excluded from them or the
    # scanner fails: a file cannot be both a source and a test.
    assert "tests/**" in props["sonar.exclusions"].split(",")


def test_coverage_counts_only_the_package(smoke_render: Path) -> None:
    """`pytest --cov` measures src/<module> only; any other Python file would
    count as uncovered new code against the quality gate's 80%."""
    props = _properties(smoke_render)
    assert props["sonar.python.coverage.reportPaths"] == "coverage.xml"
    excluded = set(props["sonar.coverage.exclusions"].split(","))
    assert {
        "tests/**",
        "scripts/**",
        "docs/**",
        "examples/**",
        "packaging/**",
        ".github/**",
    } <= excluded
    pyproject = (smoke_render / "pyproject.toml").read_text()
    assert 'source = ["src/smoke_mcp"]' in pyproject


def test_vendored_spa_is_excluded_only_when_scaffolded(
    smoke_render: Path, apps_off_render: Path
) -> None:
    vendored = "src/smoke_mcp/static/app.html"
    assert vendored in _properties(smoke_render)["sonar.exclusions"].split(",")
    assert _properties(apps_off_render)["sonar.exclusions"] == "tests/**"


def test_project_block_closes_the_file(smoke_render: Path) -> None:
    """The PROJECT-SONAR block comes after every template key, so a key the
    project repeats there wins."""
    lines = (smoke_render / "sonar-project.properties").read_text().splitlines()
    start = next(
        i for i, x in enumerate(lines) if x.startswith("# PROJECT-SONAR-START")
    )
    end = next(i for i, x in enumerate(lines) if x.startswith("# PROJECT-SONAR-END"))
    assert start < end == len(lines) - 1
    assert not any("=" in x and not x.startswith("#") for x in lines[start:])


def test_sonar_job_scans_with_the_test_runs_coverage(smoke_render: Path) -> None:
    jobs = _ci(smoke_render)["jobs"]
    sonar = jobs["sonar"]
    assert sonar["needs"] == "test"
    assert sonar["permissions"] == {"contents": "read"}
    steps = {
        s.get("name") or s.get("uses", "").split("@")[0]: s for s in sonar["steps"]
    }
    scan = steps["SonarQube Scan"]
    assert re.fullmatch(
        r"SonarSource/sonarqube-scan-action@[0-9a-f]{40}", scan["uses"]
    ), scan["uses"]
    assert steps["actions/checkout"]["with"]["fetch-depth"] == 0
    assert steps["Download coverage report"]["with"]["name"] == "coverage-xml"
    # Every step after the token check is gated on it, so a fork PR passes.
    for step in sonar["steps"][1:]:
        assert step["if"] == "steps.token.outputs.present == 'true'", step
    assert "sonar" in jobs["ci-success"]["needs"]


def test_coverage_report_is_uploaded_for_pushes_too(smoke_render: Path) -> None:
    """The analysis of main is the one the ratings and badges show."""
    test_job = _ci(smoke_render)["jobs"]["test"]
    upload = next(
        s for s in test_job["steps"] if s.get("name") == "Upload coverage report"
    )
    assert upload["if"] == "matrix.python-version == '3.14'"
    assert upload["with"]["name"] == "coverage-xml"
    assert upload["with"]["if-no-files-found"] == "error"
    # Relative paths: the report is read in another job's checkout.
    assert "relative_files = true" in (smoke_render / "pyproject.toml").read_text()


def test_sonar_token_never_reaches_the_test_job(smoke_render: Path) -> None:
    ci = (smoke_render / ".github/workflows/ci.yml").read_text()
    test_job = yaml.safe_dump(_ci(smoke_render)["jobs"]["test"])
    assert "SONAR_TOKEN" not in test_job
    assert ci.count("secrets.SONAR_TOKEN") == 2  # the check and the scan


def test_codecov_is_gone_from_the_render(smoke_render: Path) -> None:
    assert not (smoke_render / "codecov.yml").exists()
    hits = [
        str(p.relative_to(smoke_render))
        for p in smoke_render.rglob("*")
        if p.is_file()
        and ".git" not in p.parts
        and "codecov" in p.read_text(errors="ignore").lower()
    ]
    assert not hits, hits


REPO = Path(__file__).resolve().parents[2]


def test_template_repo_scans_itself() -> None:
    """The template's own SonarQube Cloud project runs on this CI scan alone
    (its Automatic Analysis is off), with the script tests' coverage."""
    props = _properties(REPO)
    assert props["sonar.projectKey"] == "pvliesdonk_fastmcp-server-template"
    readme = (REPO / "README.md").read_text()
    keys = set(re.findall(r"project_badges/measure\?project=([^&]+)", readme))
    assert keys == {props["sonar.projectKey"]}
    assert props["sonar.python.coverage.reportPaths"] == "coverage.xml"

    ci = yaml.safe_load((REPO / ".github/workflows/template-ci.yml").read_text())
    tests = ci["jobs"]["scripts-and-invariants"]["steps"]
    run = next(s for s in tests if s.get("name") == "Run script unit tests")["run"]
    assert "--cov" in run and "--cov-report=xml" in run
    # Shipped scripts whose tests are the verbatim ones under tests/.
    for shipped_test in (
        "tests/test_dependency_pins.py",
        "tests/test_package_milestones.py",
        "tests/test_promote_release_notes.py",
    ):
        assert shipped_test in run
    upload = next(s for s in tests if s.get("name") == "Upload coverage report")
    assert upload["with"] == {
        "name": "coverage-xml",
        "path": "coverage.xml",
        "if-no-files-found": "error",
        "retention-days": 1,
    }
    sonar = ci["jobs"]["sonar"]
    assert sonar["needs"] == "scripts-and-invariants"
    scan = next(s for s in sonar["steps"] if s.get("name") == "SonarQube Scan")
    assert re.fullmatch(r"SonarSource/sonarqube-scan-action@[0-9a-f]{40}", scan["uses"])
    for step in sonar["steps"][1:]:
        assert step["if"] == "steps.token.outputs.present == 'true'", step


def test_template_repo_config_stays_out_of_renders(smoke_render: Path) -> None:
    """copier gives sonar-project.properties.jinja precedence over the
    template's own plain file of the same name."""
    rendered = (smoke_render / "sonar-project.properties").read_text()
    assert "fastmcp-server-template" not in rendered
