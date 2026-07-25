"""Unit tests for the config-surface generator (template-repo only)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import gen_config_surface as g


@pytest.fixture
def fake_project(tmp_path):
    """A minimal rendered-project layout the generator can read."""
    (tmp_path / ".copier-answers.yml").write_text(
        "_commit: v2.11.2\n"
        "_src_path: gh:pvliesdonk/fastmcp-server-template\n"
        "project_name: demo-mcp\n"
        "python_module: demo_mcp\n"
        "env_prefix: DEMO_MCP\n"
        "human_name: Demo MCP\n"
        "docker_registry: ghcr.io/demo\n"
        "enable_authorization: false\n",
        encoding="utf-8",
    )
    src = tmp_path / "src" / "demo_mcp"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("", encoding="utf-8")
    return tmp_path


@pytest.fixture
def template_root():
    """The template repo root — where config-presentation.yml lives."""
    return Path(g.__file__).resolve().parent.parent


class TestLoadAnswers:
    def test_reads_the_copier_answers_file(self, fake_project):
        answers = g.load_answers(fake_project)
        assert answers["env_prefix"] == "DEMO_MCP"
        assert answers["python_module"] == "demo_mcp"

    def test_missing_answers_file_fails_with_a_clear_message(self, tmp_path):
        with pytest.raises(SystemExit, match="copier-answers"):
            g.load_answers(tmp_path)


class TestLoadPresentation:
    def test_substitutes_the_prefix_token(self, fake_project, template_root):  # noqa: ARG002
        pres = g.load_presentation(template_root, "DEMO_MCP")
        names = [v["name"] for v in pres["vars"]]
        assert "DEMO_MCP_HTTP_PATH" in names
        assert not any("{PREFIX}" in n for n in names)

    def test_unprefixed_external_vars_are_left_alone(self, fake_project, template_root):  # noqa: ARG002
        pres = g.load_presentation(template_root, "DEMO_MCP")
        names = [v["name"] for v in pres["vars"]]
        assert "FASTMCP_LOG_LEVEL" in names


class TestCollectVars:
    def test_includes_every_core_field(self, fake_project):
        from fastmcp_pvl_core import server_config_surface

        collected = {
            v.suffix for v in g.collect_vars(fake_project, g.load_answers(fake_project))
        }
        assert {f.suffix for f in server_config_surface()} <= collected

    def test_provenance_order_is_core_then_template_then_external(self, fake_project):
        vars_ = g.collect_vars(fake_project, g.load_answers(fake_project))
        ranks = [
            ("core", "template", "external", "domain").index(v.provenance)
            for v in vars_
        ]
        assert ranks == sorted(ranks)

    def test_core_ordering_matches_declaration_order(self, fake_project):
        from fastmcp_pvl_core import server_config_surface

        core = [
            v.suffix
            for v in g.collect_vars(fake_project, g.load_answers(fake_project))
            if v.provenance == "core"
        ]
        assert core == [f.suffix for f in server_config_surface()]

    def test_authz_vars_absent_when_the_answer_is_false(self, fake_project):
        names = {
            v.name for v in g.collect_vars(fake_project, g.load_answers(fake_project))
        }
        assert "DEMO_MCP_ACL_PATH" not in names

    def test_authz_vars_present_when_the_answer_is_true(self, fake_project):
        p = fake_project / ".copier-answers.yml"
        p.write_text(
            p.read_text(encoding="utf-8").replace(
                "enable_authorization: false", "enable_authorization: true"
            ),
            encoding="utf-8",
        )
        names = {
            v.name for v in g.collect_vars(fake_project, g.load_answers(fake_project))
        }
        assert "DEMO_MCP_ACL_PATH" in names

    def test_prefixed_names_use_the_projects_prefix(self, fake_project):
        names = {
            v.name for v in g.collect_vars(fake_project, g.load_answers(fake_project))
        }
        assert "DEMO_MCP_BASE_URL" in names
        assert not any(n.startswith("SCHOLAR") for n in names)

    def test_every_var_carries_at_least_one_tag(self, fake_project):
        untagged = [
            v.name
            for v in g.collect_vars(fake_project, g.load_answers(fake_project))
            if not v.tags
        ]
        assert untagged == []

    def test_auth_mode_is_collected_despite_being_inferred(self, fake_project):
        """inferred means no wizard control, NOT undocumented — it must still be emitted."""
        vars_ = g.collect_vars(fake_project, g.load_answers(fake_project))
        auth_mode = next(v for v in vars_ if v.suffix == "AUTH_MODE")
        assert auth_mode.inferred is True

    def test_collection_is_deterministic_under_hash_randomisation(self, fake_project):
        """Two runs in separate processes must agree, or the render-twice CI diff fails."""
        import os
        import subprocess

        scripts_dir = str(Path(g.__file__).parent)
        project = str(fake_project)
        prog = (
            f"import sys; sys.path.insert(0, {scripts_dir!r});"
            "import gen_config_surface as g;"
            f"a = g.load_answers({project!r});"
            f"print(','.join(v.name for v in g.collect_vars({project!r}, a)))"
        )
        outs = set()
        for seed in ("1", "2", "3"):
            r = subprocess.run(
                [sys.executable, "-c", prog],
                capture_output=True,
                text=True,
                check=True,
                env={**os.environ, "PYTHONHASHSEED": seed},
            )
            outs.add(r.stdout.strip())
        assert len(outs) == 1


class TestEnsureCoreAvailable:
    def test_parses_the_core_floor_from_pyproject(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            'dependencies = [\n  "fastmcp-pvl-core>=4.5.0,<5",\n]\n', encoding="utf-8"
        )
        assert g._core_floor(tmp_path) == "4.5.0"

    def test_missing_floor_fails_loudly(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            "dependencies = []\n", encoding="utf-8"
        )
        with pytest.raises(SystemExit, match="fastmcp-pvl-core"):
            g._core_floor(tmp_path)
