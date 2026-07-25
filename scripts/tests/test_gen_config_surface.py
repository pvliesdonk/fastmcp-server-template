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
    def test_substitutes_the_prefix_token(self, template_root):
        pres = g.load_presentation(template_root, "DEMO_MCP")
        names = [v["name"] for v in pres["vars"]]
        assert "DEMO_MCP_HTTP_PATH" in names
        assert not any("{PREFIX}" in n for n in names)

    def test_unprefixed_external_vars_are_left_alone(self, template_root):
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

    def test_template_provenance_preserves_declaration_order(
        self, fake_project, template_root
    ):
        """A within-rank sort (e.g. by name) would pass the rank-only ordering
        test above but still be wrong — pin declaration order directly."""
        p = fake_project / ".copier-answers.yml"
        p.write_text(
            p.read_text(encoding="utf-8").replace(
                "enable_authorization: false", "enable_authorization: true"
            ),
            encoding="utf-8",
        )
        answers = g.load_answers(fake_project)
        presentation = g.load_presentation(template_root, str(answers["env_prefix"]))
        expected = [
            v["name"] for v in presentation["vars"] if v["provenance"] == "template"
        ]
        collected = [
            v.name
            for v in g.collect_vars(fake_project, answers)
            if v.provenance == "template"
        ]
        assert collected == expected

    def test_missing_env_prefix_fails_loudly(self, fake_project):
        answers = g.load_answers(fake_project)
        del answers["env_prefix"]
        with pytest.raises(SystemExit, match="env_prefix"):
            g.collect_vars(fake_project, answers)

    def test_duplicate_var_name_raises_a_clear_error(self, fake_project, monkeypatch):
        def _fake_load_presentation(project_root, env_prefix):  # noqa: ARG001
            return {
                "vars": [
                    {
                        "name": f"{env_prefix}_TRANSPORT",  # collides with core
                        "provenance": "template",
                        "type_name": "str",
                        "default": None,
                        "help": "duplicate on purpose",
                        "tags": ["server"],
                    }
                ]
            }

        monkeypatch.setattr(g, "load_presentation", _fake_load_presentation)
        with pytest.raises(SystemExit, match="duplicate"):
            g.collect_vars(fake_project, g.load_answers(fake_project))

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

    def test_missing_pyproject_fails_loudly(self, tmp_path):
        with pytest.raises(SystemExit, match=r"pyproject\.toml"):
            g._core_floor(tmp_path)

    @pytest.mark.xfail(reason="floor bump lands in the wiring commit", strict=True)
    def test_matches_the_real_projects_declared_floor(self):
        """Pin against the repo's real pyproject.toml.jinja, not a fixture —
        a fabricated fixture can't notice the declared floor lagging behind
        the fastmcp-pvl-core version this generator actually needs (4.5.0)."""
        real_pyproject = (
            Path(__file__).resolve().parent.parent.parent / "pyproject.toml.jinja"
        )
        floor = g._CORE_FLOOR_RE.search(real_pyproject.read_text(encoding="utf-8"))
        assert floor is not None
        major, minor = (int(part) for part in floor.group(1).split(".")[:2])
        assert (major, minor) >= (4, 5)

    def test_returns_immediately_when_both_deps_are_importable(self, monkeypatch):
        monkeypatch.setattr(g, "_core_importable", lambda: True)
        monkeypatch.setattr(g, "_yaml_importable", lambda: True)

        def _boom(*_args, **_kwargs):
            raise AssertionError("execvpe should not be called")

        monkeypatch.setattr(g.os, "execvpe", _boom)
        # Returns before ever touching project_root, so a nonexistent path is fine.
        g.ensure_core_available(Path("/nonexistent"))

    def test_second_failure_raises_instead_of_looping(self, monkeypatch):
        monkeypatch.setattr(g, "_core_importable", lambda: False)
        monkeypatch.setattr(g, "_yaml_importable", lambda: False)
        monkeypatch.setenv("_GEN_CONFIG_BOOTSTRAPPED", "1")

        def _boom(*_args, **_kwargs):
            raise AssertionError("execvpe should not be called on a repeat failure")

        monkeypatch.setattr(g.os, "execvpe", _boom)
        with pytest.raises(SystemExit, match="still not importable"):
            g.ensure_core_available(Path("/nonexistent"))

    def test_reexec_argv_shape_and_preservation(self, tmp_path, monkeypatch):
        (tmp_path / "pyproject.toml").write_text(
            'dependencies = [\n  "fastmcp-pvl-core>=4.5.0,<5",\n]\n', encoding="utf-8"
        )
        monkeypatch.setattr(g, "_core_importable", lambda: False)
        monkeypatch.setattr(g, "_yaml_importable", lambda: False)
        monkeypatch.delenv("_GEN_CONFIG_BOOTSTRAPPED", raising=False)

        recorded = {}

        def _record_execvpe(file, args, env):
            recorded["file"] = file
            recorded["args"] = args
            recorded["env"] = env

        monkeypatch.setattr(g.os, "execvpe", _record_execvpe)

        g.ensure_core_available(tmp_path, argv=["--check", "--extra-flag"])

        assert recorded["file"] == "uv"
        args = recorded["args"]
        assert "uv" in args
        assert "run" in args
        assert "--no-project" in args
        assert "fastmcp-pvl-core==4.5.0" in args
        assert "pyyaml" in args
        assert args.count("--with") == 2
        # Original script arguments must survive into the re-exec's argv.
        assert "--check" in args
        assert "--extra-flag" in args
        assert recorded["env"]["_GEN_CONFIG_BOOTSTRAPPED"] == "1"

    def test_execvpe_oserror_becomes_a_clear_system_exit(self, tmp_path, monkeypatch):
        (tmp_path / "pyproject.toml").write_text(
            'dependencies = [\n  "fastmcp-pvl-core>=4.5.0,<5",\n]\n', encoding="utf-8"
        )
        monkeypatch.setattr(g, "_core_importable", lambda: False)
        monkeypatch.setattr(g, "_yaml_importable", lambda: False)
        monkeypatch.delenv("_GEN_CONFIG_BOOTSTRAPPED", raising=False)

        def _raise_oserror(*_args, **_kwargs):
            raise OSError("uv not found")

        monkeypatch.setattr(g.os, "execvpe", _raise_oserror)

        with pytest.raises(SystemExit, match="uv"):
            g.ensure_core_available(tmp_path)


class TestRenderEnvFile:
    def _env_text(self, fake_project, template_root, path=".env.example"):
        answers = g.load_answers(fake_project)
        pres = g.load_presentation(template_root, str(answers["env_prefix"]))
        vars_ = g.collect_vars(fake_project, answers)
        return g.render_env_file(pres["files"][path], vars_, answers)

    def test_includes_all_eighteen_core_vars(self, fake_project, template_root):
        """The hand-written .env.example was missing six of them."""
        text = self._env_text(fake_project, template_root)
        for suffix in (
            "APP_DOMAIN",
            "AUTH_MODE",
            "BEARER_DEFAULT_SUBJECT",
            "EVENT_STORE_URL",
            "KV_STORE_URL",
            "OIDC_VERIFY_ACCESS_TOKEN",
        ):
            assert f"DEMO_MCP_{suffix}" in text

    def test_env_example_lines_are_commented_out(self, fake_project, template_root):
        text = self._env_text(fake_project, template_root)
        for line in text.splitlines():
            if "DEMO_MCP_" in line:
                assert line.lstrip().startswith("#")

    def test_packaging_env_lines_are_not_commented(self, fake_project, template_root):
        text = self._env_text(fake_project, template_root, "packaging/env.example")
        assert any(line.startswith("FASTMCP_LOG_LEVEL=") for line in text.splitlines())

    def test_section_titles_appear_in_declared_order(self, fake_project, template_root):
        text = self._env_text(fake_project, template_root)
        positions = [
            text.index(t)
            for t in ("--- Server ---", "--- Authentication ---", "--- Logging ---")
        ]
        assert positions == sorted(positions)

    def test_authz_section_absent_when_answer_false(self, fake_project, template_root):
        assert "Authorization" not in self._env_text(fake_project, template_root)

    def test_help_text_appears_as_a_comment(self, fake_project, template_root):
        text = self._env_text(fake_project, template_root)
        assert "Interface the HTTP server binds to." in text

    def test_render_hygiene_no_trailing_whitespace_single_final_newline(
        self, fake_project, template_root
    ):
        text = self._env_text(fake_project, template_root)
        assert not any(line != line.rstrip() for line in text.splitlines())
        assert text.endswith("\n") and not text.endswith("\n\n")

    def test_output_is_stable_across_calls(self, fake_project, template_root):
        assert self._env_text(fake_project, template_root) == self._env_text(
            fake_project, template_root
        )


class TestWriteArtifacts:
    def test_writes_then_reports_clean(self, fake_project):
        g.write_artifacts(fake_project, check=False)
        assert (fake_project / ".env.example").exists()
        assert g.write_artifacts(fake_project, check=True) == []

    def test_check_reports_a_stale_file_without_writing(self, fake_project):
        g.write_artifacts(fake_project, check=False)
        target = fake_project / ".env.example"
        target.write_text("tampered\n", encoding="utf-8")
        assert ".env.example" in g.write_artifacts(fake_project, check=True)
        assert target.read_text(encoding="utf-8") == "tampered\n"

    def test_check_reports_a_missing_file(self, fake_project):
        assert ".env.example" in g.write_artifacts(fake_project, check=True)
