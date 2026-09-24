"""Unit tests for the template-conformance comparison (#653); the end-to-end
run against a real `copier update` happens in check_update_regression.py.
Importing the module must be side-effect free: the `uv run` fallback lives
in main() only."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import check_template_conformance as c
import report_seeded_changes as r

SCRIPT = Path(__file__).resolve().parents[1] / "check_template_conformance.py"

PRISTINE_MD = """\
# Title

Template prose.

<!-- DOMAIN-START — project prose goes here -->
<!-- DOMAIN-END -->

Closing template prose.
"""

PRISTINE_PY = """\
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Config:
    name: str = "x"
    # CONFIG-FIELDS-START — add domain fields below
    # CONFIG-FIELDS-END
    items: list[str] = field(default_factory=list)
"""


def _tree(root: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return root


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        [
            "git",
            "-c",
            "user.email=t@localhost",
            "-c",
            "user.name=t",
            "-c",
            "commit.gpgsign=false",
            *args,
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def test_importing_the_module_does_not_reexec() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            f"import sys; sys.path.insert(0, {str(SCRIPT.parent)!r}); "
            "import check_template_conformance; print('imported')",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.stdout.strip() == "imported", proc.stderr


def test_content_inside_a_sentinel_conforms() -> None:
    project = PRISTINE_MD.replace(
        "<!-- DOMAIN-END -->", "Project prose.\n\nMore of it.\n<!-- DOMAIN-END -->"
    )
    assert c.compare_text(project, PRISTINE_MD, python=False).hunks == []


def test_whitespace_and_blank_lines_are_not_drift() -> None:
    project = PRISTINE_MD.replace("Template prose.", "Template prose.   \n\n\n")
    assert c.compare_text(project, PRISTINE_MD, python=False).hunks == []


def test_prose_outside_a_sentinel_is_drift_at_its_project_line() -> None:
    project = PRISTINE_MD.replace(
        "Closing template prose.", "Closing template prose.\n\nProject prose."
    )
    drift = c.compare_text(project, PRISTINE_MD, python=False)
    assert len(drift.hunks) == 1
    assert "+Project prose." in drift.hunks[0]
    assert drift.ranges == [(10, 10)]


def test_rewritten_template_line_shows_both_sides() -> None:
    project = PRISTINE_MD.replace("Template prose.", "Rewritten prose.")
    (hunk,) = c.compare_text(project, PRISTINE_MD, python=False).hunks
    assert "-Template prose." in hunk
    assert "+Rewritten prose." in hunk


def test_deleted_sentinel_block_is_drift() -> None:
    project = PRISTINE_MD.replace(
        "<!-- DOMAIN-START — project prose goes here -->\n<!-- DOMAIN-END -->\n", ""
    )
    (hunk,) = c.compare_text(project, PRISTINE_MD, python=False).hunks
    assert "-<!-- DOMAIN-START" in hunk


def test_invented_sentinel_does_not_shield_its_content() -> None:
    project = PRISTINE_MD.replace(
        "Closing template prose.",
        "<!-- INVENTED-START -->\nsneaky\n<!-- INVENTED-END -->\nClosing template prose.",
    )
    (hunk,) = c.compare_text(project, PRISTINE_MD, python=False).hunks
    assert "+sneaky" in hunk


def test_release_written_version_line_is_compared_by_key_only() -> None:
    pristine = '[project]\nname = "x"\nversion = "0.1.0"\n'
    pattern = c._TOOL_WRITTEN_LINES["pyproject.toml"]
    bumped = pristine.replace('"0.1.0"', '"5.0.0"')
    assert (
        c.compare_text(bumped, pristine, python=False, tool_written=pattern).hunks == []
    )
    renamed = bumped.replace('name = "x"', 'name = "y"')
    assert c.compare_text(renamed, pristine, python=False, tool_written=pattern).hunks


def test_marker_quoted_in_prose_is_not_a_sentinel() -> None:
    pristine = "Put it in `# DOMAIN-HOOKS-START`.\nx\n`# DOMAIN-HOOKS-END` closes it.\n"
    assert c.sentinel_names(c.normalize(pristine)) == set()


def test_unbalanced_render_marker_is_not_a_sentinel() -> None:
    assert c.sentinel_names(["# FOO-START", "x"]) == set()


def test_python_added_import_and_sentinel_field_conform() -> None:
    project = PRISTINE_PY.replace(
        "from dataclasses import dataclass, field",
        "from dataclasses import dataclass, field\nfrom pathlib import Path",
    ).replace(
        "    # CONFIG-FIELDS-END",
        "    root: Path = Path('/data')\n    # CONFIG-FIELDS-END",
    )
    assert c.compare_text(project, PRISTINE_PY, python=True).hunks == []


def test_python_removed_template_import_is_drift() -> None:
    project = PRISTINE_PY.replace(
        "from dataclasses import dataclass, field", "from dataclasses import dataclass"
    )
    (hunk,) = c.compare_text(project, PRISTINE_PY, python=True).hunks
    assert "-from dataclasses import field" in hunk


def test_python_use_of_an_added_import_outside_a_sentinel_is_drift() -> None:
    project = PRISTINE_PY.replace(
        "from dataclasses import dataclass, field",
        "from dataclasses import dataclass, field\nfrom pathlib import Path",
    ).replace('    name: str = "x"', '    name: str = "x"\n    root: Path = Path("/")')
    (hunk,) = c.compare_text(project, PRISTINE_PY, python=True).hunks
    assert '+    root: Path = Path("/")' in hunk


def test_python_with_conflict_markers_is_still_compared() -> None:
    project = PRISTINE_PY.replace(
        '    name: str = "x"',
        '<<<<<<< before updating\n    name: str = "y"\n=======\n'
        '    name: str = "x"\n>>>>>>> after updating',
    )
    drift = c.compare_text(project, PRISTINE_PY, python=True)
    assert any("+<<<<<<< before updating" in h for h in drift.hunks)


def _render(tmp_path: Path) -> Path:
    root = _tree(
        tmp_path / "render",
        {
            "docs/index.md": PRISTINE_MD,
            "src/pkg/config.py": PRISTINE_PY,
            "src/pkg/tools.py": "seeded\n",
            ".env.example": "GENERATED=1\n",
            ".copier-answers.yml": "_commit: v1\n",
            "server.json": '{"version": "0.1.0"}\n',
            ".agents/skills/s/SKILL.md": "skill\n",
        },
    )
    (root / ".claude/skills").mkdir(parents=True)
    (root / ".claude/skills/s").symlink_to("../../.agents/skills/s")
    return root


def test_template_owned_skips_seeded_generated_and_answers(tmp_path: Path) -> None:
    owned = c.template_owned(_render(tmp_path), ["src/pkg/tools.py"])
    assert owned == [
        ".agents/skills/s/SKILL.md",
        ".claude/skills/s",
        "docs/index.md",
        "src/pkg/config.py",
    ]


def test_check_reports_deleted_file_replaced_symlink_and_drift(tmp_path: Path) -> None:
    render = _render(tmp_path)
    project = _tree(
        tmp_path / "project",
        {
            "docs/index.md": PRISTINE_MD + "\nProject prose.\n",
            "src/pkg/config.py": PRISTINE_PY,
            "src/pkg/tools.py": "anything the project likes\n",
            ".claude/skills/s": "a real file where the template has a link\n",
        },
    )
    drifts = {d.path: d for d in c.check(render, c.read_worktree(project), [])}
    assert set(drifts) == {
        ".agents/skills/s/SKILL.md",
        ".claude/skills/s",
        "docs/index.md",
        "src/pkg/tools.py",
    }
    assert "deleted" in drifts[".agents/skills/s/SKILL.md"].note
    assert "symlink" in drifts[".claude/skills/s"].note
    assert drifts["docs/index.md"].hunks


def test_binary_file_compares_by_bytes(tmp_path: Path) -> None:
    render = tmp_path / "render"
    render.mkdir()
    (render / "logo.png").write_bytes(b"\x89PNG\xff")
    same = c.compare_file("logo.png", render, lambda _rel: b"\x89PNG\xff")
    other = c.compare_file("logo.png", render, lambda _rel: b"\x89PNG\xfe")
    assert same is None
    assert other is not None and "binary" in other.note


def test_read_revision_sees_the_commit_not_the_worktree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _tree(tmp_path / "repo", {"sub/a.txt": "committed\n"})
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "c")
    (repo / "sub/a.txt").write_text("edited\n", encoding="utf-8")
    monkeypatch.chdir(repo / "sub")
    read = c.read_revision("HEAD")
    assert read("a.txt") == b"committed\n"
    assert read("missing.txt") is None


def test_last_commits_names_the_commit_that_wrote_the_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _tree(tmp_path, {"docs/index.md": PRISTINE_MD})
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "scaffold")
    (repo / "docs/index.md").write_text(PRISTINE_MD + "Project prose.\n")
    _git(repo, "commit", "-qam", "feat: write prose into the template body")
    monkeypatch.chdir(repo)
    drift = c.compare_text(
        (repo / "docs/index.md").read_text(), PRISTINE_MD, python=False
    )
    (commit,) = c.last_commits("docs/index.md", drift.ranges, "HEAD")
    assert commit.endswith("feat: write prose into the template body")


def _hygienic(text: str) -> bool:
    return (
        text.endswith("\n")
        and not text.endswith("\n\n")
        and all(line == line.rstrip() for line in text.splitlines())
    )


def test_report_states_conformance_explicitly() -> None:
    text = c.render_report([], c.report_header(src="gh:x/t", ref="v1", what="w"))
    assert "Every template-owned file matches" in text
    assert _hygienic(text)


def test_report_lists_each_drift_with_its_description() -> None:
    drift = c.compare_text(
        PRISTINE_MD + "\nProject prose.\n", PRISTINE_MD, python=False
    )
    drift.path = "docs/index.md"
    text = c.render_report(
        [drift, c.Drift("gone.md", note="deleted in the project")],
        c.report_header(src="gh:x/t", ref="v1", what="w"),
        lambda d: "Blame here." if d.path == "docs/index.md" else "",
    )
    assert "1 template-owned" not in text and "2 template-owned file(s)" in text
    assert "## `docs/index.md`" in text and "Blame here." in text
    assert "## `gone.md`" in text and "deleted in the project" in text
    assert "Decay issue" in text
    assert _hygienic(text)


def test_report_truncates_a_long_diff() -> None:
    drift = c.Drift(
        "big.md", hunks=["@@ x @@\n" + "\n".join(f"+{i}" for i in range(200))]
    )
    text = c.render_report([drift], "# h\n")
    assert "more line(s); run the script for all" in text


def test_update_drift_report_compares_head_with_the_previous_render(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The migration's drift report judges HEAD (the pre-update project)
    against the previous ref's render, and flags files that now carry
    conflict markers in the working tree."""
    render = _render(tmp_path)
    repo = _tree(
        tmp_path / "repo",
        {
            "docs/index.md": PRISTINE_MD + "\nProject prose.\n",
            "src/pkg/config.py": PRISTINE_PY,
            ".agents/skills/s/SKILL.md": "skill\n",
        },
    )
    (repo / ".claude/skills").mkdir(parents=True)
    (repo / ".claude/skills/s").symlink_to("../../.agents/skills/s")
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "docs: prose in the template body")
    (repo / "docs/index.md").write_text(
        "<<<<<<< before updating\nx\n=======\ny\n>>>>>>> after updating\n"
    )
    monkeypatch.chdir(repo)
    monkeypatch.setattr(r, "_skip_patterns", lambda _src, _ref: ["src/pkg/tools.py"])
    text = r._drift_report("gh:x/t", "v1", {}, render)
    assert "1 template-owned file(s)" in text
    assert "## `docs/index.md`" in text
    assert "also has conflict markers" in text
    assert "docs: prose in the template body" in text
    assert "config.py" not in text


def test_update_drift_report_writes_a_failure_instead_of_raising(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(_src: str, _ref: str) -> list[str]:
        raise RuntimeError("offline")

    monkeypatch.setattr(r, "_skip_patterns", boom)
    text = r._drift_report("gh:x/t", "v1", {}, tmp_path)
    assert "could not be made" in text and "offline" in text
    assert "--rev HEAD --ref v1" in text


def test_skip_removes_a_stale_drift_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".copier-template-drift.md").write_text("stale")
    assert r._skip("unchanged") == 0
    assert not (tmp_path / ".copier-template-drift.md").exists()


def test_main_without_answers_exits_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert c.main([]) == 2


def test_main_with_an_unknown_revision_exits_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _tree(tmp_path, {".copier-answers.yml": "_commit: v1\n_src_path: gh:x/t\n"})
    _git(repo, "init", "-q")
    monkeypatch.chdir(repo)
    monkeypatch.setattr(c, "_reexec_with_deps", lambda: False)
    assert c.main(["--rev", "no-such-rev"]) == 2


def test_update_drift_report_survives_a_missing_checker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "check_template_conformance", None)
    text = r._drift_report("gh:x/t", "v1", {}, tmp_path)
    assert "could not be made" in text


def _drift_of(project: str, path: str = "docs/index.md") -> c.Drift:
    drift = c.compare_text(project, PRISTINE_MD, python=False)
    drift.path = path
    return drift


def test_new_since_keeps_only_hunks_the_base_lacks() -> None:
    old = PRISTINE_MD.replace("Template prose.", "Old drift.")
    new = old + "\nNew drift.\n"
    (kept,) = c.new_since([_drift_of(new)], [_drift_of(old)])
    assert len(kept.hunks) == 1
    assert "+New drift." in kept.hunks[0]
    assert "Old drift." not in kept.hunks[0]


def test_new_since_ignores_drift_that_only_moved() -> None:
    old = PRISTINE_MD + "\nMoved drift.\n"
    moved = PRISTINE_MD.replace("# Title", "# Title\n\nMoved drift.")
    assert c.new_since([_drift_of(moved)], [_drift_of(old)]) == []


def test_new_since_counts_repeated_hunks() -> None:
    old = PRISTINE_MD + "\nSame.\n"
    twice = PRISTINE_MD.replace("# Title", "# Title\n\nSame.") + "\nSame.\n"
    (kept,) = c.new_since([_drift_of(twice)], [_drift_of(old)])
    assert len(kept.hunks) == 1


def test_new_since_reports_a_new_note_and_drops_an_old_one() -> None:
    gone = c.Drift("gone.md", note="deleted in the project")
    assert c.new_since([gone], [gone]) == []
    assert c.new_since([gone], []) == [gone]


def test_since_against_a_branch_reports_only_the_branch_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    render = _render(tmp_path)
    repo = _tree(
        tmp_path / "repo",
        {
            "docs/index.md": PRISTINE_MD + "\nOld drift on main.\n",
            "src/pkg/config.py": PRISTINE_PY,
        },
    )
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "main")
    (repo / "src/pkg/config.py").write_text(
        PRISTINE_PY.replace('name: str = "x"', 'name: str = "x"\n    extra: int = 1')
    )
    _git(repo, "commit", "-qam", "feat: field outside the sentinel")
    monkeypatch.chdir(repo)
    head = c.check(render, c.read_revision("HEAD"), [])
    base = c.check(render, c.read_revision("main~1"), [])
    new = c.new_since(head, base)
    assert [d.path for d in new] == ["src/pkg/config.py"]
    assert "+    extra: int = 1" in new[0].hunks[0]


def test_base_drift_renders_the_version_the_base_pinned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _tree(tmp_path / "repo", {".copier-answers.yml": "_commit: v8.0.0\n"})
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "pinned at v8")
    monkeypatch.chdir(repo)
    seen: list[str] = []

    def fake_drift_at(
        _src: str, ref: str, _answers: object, _read: object, _root: Path
    ) -> list[c.Drift]:
        seen.append(ref)
        return []

    monkeypatch.setattr(c, "drift_at", fake_drift_at)
    assert c._base_drift("gh:x/t", "HEAD", tmp_path) == []
    assert seen == ["v8.0.0"]


def test_since_report_does_not_claim_the_tree_conforms() -> None:
    message = c.clean_message("origin/main")
    assert message == (
        "Nothing here differs from the template that did not already differ "
        "at `origin/main`."
    )
    text = c.render_report([], "# h\n", clean=message)
    assert message in text
    assert "Every template-owned file" not in text
    assert c.clean_message(None).startswith("Every template-owned file matches")


def _clone_with_origin(tmp_path: Path) -> Path:
    """A clone whose origin/main is one commit behind a local feature branch."""
    origin = _tree(tmp_path / "origin", {"a.txt": "a\n"})
    _git(origin, "init", "-q", "-b", "main")
    _git(origin, "add", "-A")
    _git(origin, "commit", "-qm", "base")
    subprocess.run(
        ["git", "clone", "-q", str(origin), str(tmp_path / "clone")], check=True
    )
    clone = tmp_path / "clone"
    _git(clone, "checkout", "-qb", "feature")
    (clone / "b.txt").write_text("b\n")
    _git(clone, "add", "-A")
    _git(clone, "commit", "-qm", "feature")
    return clone


def test_derive_base_is_the_merge_base_with_origin_main(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clone = _clone_with_origin(tmp_path)
    monkeypatch.chdir(clone)
    monkeypatch.delenv("TEMPLATE_CONFORMANCE_BASE", raising=False)
    assert c.derive_base() == _git(clone, "rev-parse", "HEAD~1").strip()
    monkeypatch.setenv("TEMPLATE_CONFORMANCE_BASE", "some-ref")
    assert c.derive_base() == "some-ref"


def test_derive_base_without_a_remote_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _tree(tmp_path, {"a.txt": "a\n"})
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "c")
    monkeypatch.chdir(repo)
    monkeypatch.delenv("TEMPLATE_CONFORMANCE_BASE", raising=False)
    with pytest.raises(ValueError, match="origin/main"):
        c.derive_base()


def test_hook_mode_passes_when_it_cannot_compare(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)  # no answers file: the comparison cannot run
    assert c.main([]) == 2
    assert c.main(["--hook"]) == 0


def test_hook_mode_fails_on_added_drift_and_says_how_to_skip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    clone = _clone_with_origin(tmp_path)
    (clone / ".copier-answers.yml").write_text("_commit: v1\n_src_path: gh:x/t\n")
    _git(clone, "add", "-A")
    _git(clone, "commit", "-qm", "answers")
    monkeypatch.chdir(clone)
    monkeypatch.delenv("TEMPLATE_CONFORMANCE_BASE", raising=False)
    monkeypatch.setattr(c, "_reexec_with_deps", lambda: False)
    added = c.Drift(
        "docs/index.md", hunks=["@@ project line 3 @@\n+new"], ranges=[(3, 3)]
    )
    monkeypatch.setattr(c, "drift_at", lambda *_a: [added])
    monkeypatch.setattr(c, "_base_drift", lambda *_a: [])
    assert c.main(["--rev", "HEAD", "--since", "auto", "--hook"]) == 1
    out = capsys.readouterr().out
    assert "## `docs/index.md`" in out
    assert "SKIP=template-conformance git push" in out
