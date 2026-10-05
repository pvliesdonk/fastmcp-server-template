"""The `self-review` pre-push hook passes only a pushed commit whose review
the self-reviewing skill recorded."""

from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import check_self_review as csr

REPORT = "## Self-review abc..def\n\nCharters: rules.\nCoverage: full\n"


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def _commit(repo: Path, name: str) -> str:
    (repo / name).write_text(name, encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "commit", "-q", "-m", name)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    _commit(root, "a")
    monkeypatch.chdir(root)
    return root


def _record(monkeypatch: pytest.MonkeyPatch, report: str, *argv: str) -> int:
    monkeypatch.setattr(sys, "stdin", io.StringIO(report))
    return csr.main(["--record", *argv])


def test_push_without_a_record_fails_and_names_the_way_out(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sha = _git(repo, "rev-parse", "HEAD")
    assert csr.check({"PRE_COMMIT_TO_REF": sha}) == 1
    err = capsys.readouterr().err
    assert sha[:12] in err
    assert "self-reviewing skill" in err
    assert csr.SKIP_HINT in err


def test_recorded_commit_passes(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert _record(monkeypatch, REPORT) == 0
    sha = _git(repo, "rev-parse", "HEAD")
    assert csr.check({"PRE_COMMIT_TO_REF": sha}) == 0
    assert csr.record_path(sha).read_text(encoding="utf-8") == REPORT


def test_a_commit_after_the_review_needs_a_new_record(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert _record(monkeypatch, REPORT) == 0
    later = _commit(repo, "b")
    assert csr.check({"PRE_COMMIT_TO_REF": later}) == 1


@pytest.mark.usefixtures("repo")
def test_a_report_without_the_heading_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert _record(monkeypatch, "LGTM\n") == 1
    assert not csr.record_dir().exists()


@pytest.mark.usefixtures("repo")
def test_root_push_falls_back_to_the_local_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert _record(monkeypatch, REPORT) == 0
    assert csr.check({"PRE_COMMIT_LOCAL_BRANCH": "refs/heads/main"}) == 0


def test_tag_pushes_pass(repo: Path) -> None:
    sha = _git(repo, "rev-parse", "HEAD")
    env = {"PRE_COMMIT_TO_REF": sha, "PRE_COMMIT_REMOTE_BRANCH": "refs/tags/v1.0.0"}
    assert csr.check(env) == 0


def test_a_record_is_shared_across_worktrees(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert _record(monkeypatch, REPORT) == 0
    sha = _git(repo, "rev-parse", "HEAD")
    tree = tmp_path / "wt"
    _git(repo, "worktree", "add", "-q", "--detach", str(tree), sha)
    monkeypatch.chdir(tree)
    assert csr.check({"PRE_COMMIT_TO_REF": sha}) == 0


def test_rendered_config_runs_the_hook_at_pre_push(smoke_render: Path) -> None:
    config = yaml.safe_load((smoke_render / ".pre-commit-config.yaml").read_text())
    hooks = {h["id"]: h for r in config["repos"] for h in r["hooks"]}
    hook = hooks["self-review"]
    assert hook["stages"] == ["pre-push"]
    assert hook["entry"] == "python3 scripts/check_self_review.py --hook"
    assert (smoke_render / "scripts" / "check_self_review.py").is_file()
