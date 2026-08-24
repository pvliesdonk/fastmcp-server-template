from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
ANSWERS = REPO / "tests" / "fixtures" / "smoke-answers.yml"


def render(tmp_path: Path, enabled: bool) -> Path:
    answers = tmp_path / "answers.yml"
    text = ANSWERS.read_text(encoding="utf-8").replace(
        "enable_automatic_claude_review: false",
        f"enable_automatic_claude_review: {'true' if enabled else 'false'}",
    )
    answers.write_text(text, encoding="utf-8")
    output = tmp_path / "rendered"
    subprocess.run(
        [
            "uv",
            "run",
            "--no-project",
            "--with",
            "copier",
            "copier",
            "copy",
            "--trust",
            "--defaults",
            "--vcs-ref=HEAD",
            "--data-file",
            str(answers),
            str(REPO),
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return output


@pytest.fixture(scope="module")
def review_off(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return render(tmp_path_factory.mktemp("review-off"), enabled=False)


@pytest.fixture(scope="module")
def review_on(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return render(tmp_path_factory.mktemp("review-on"), enabled=True)


def test_answer_defaults_to_false() -> None:
    answers = yaml.safe_load((REPO / "copier.yml").read_text(encoding="utf-8"))
    assert answers["enable_automatic_claude_review"]["default"] is False


@pytest.mark.parametrize("fixture_name", ["review_off", "review_on"])
def test_explicit_claude_responder_is_always_present(
    fixture_name: str, request: pytest.FixtureRequest
) -> None:
    rendered = request.getfixturevalue(fixture_name)
    assert (rendered / ".github/workflows/claude.yml").is_file()


def test_automatic_review_is_absent_by_default(review_off: Path) -> None:
    workflows = review_off / ".github/workflows"
    assert not (workflows / "claude-code-review.yml").exists()
    assert not (workflows / ".jinja").exists()


def test_automatic_review_renders_when_enabled(review_on: Path) -> None:
    workflow = review_on / ".github/workflows/claude-code-review.yml"
    parsed = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    assert set(parsed["jobs"]) == {"wait-for-ci", "claude-review"}
    text = workflow.read_text(encoding="utf-8")
    assert "github.event.pull_request.draft == false" in text
    assert "cancel-in-progress: true" in text


def test_template_repo_has_no_active_automatic_reviewer() -> None:
    assert not (REPO / ".github/workflows/claude-code-review.yml").exists()
