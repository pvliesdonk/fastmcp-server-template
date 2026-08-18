"""Render the template with the Claude plugin toggle off/on and assert gating."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_ANSWERS = _REPO / "tests" / "fixtures" / "smoke-answers.yml"


def _render(tmp_path: Path, plugin_on: bool) -> Path:
    answers = tmp_path / "answers.yml"
    text = _ANSWERS.read_text(encoding="utf-8")
    text = text.replace(
        "include_claude_plugin: true",
        f"include_claude_plugin: {'true' if plugin_on else 'false'}",
    )
    answers.write_text(text, encoding="utf-8")
    out = tmp_path / "out"
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
            str(_REPO),
            str(out),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return out


@pytest.fixture(scope="module")
def rendered_off(tmp_path_factory) -> Path:
    return _render(tmp_path_factory.mktemp("plugin-off"), plugin_on=False)


@pytest.fixture(scope="module")
def rendered_on(tmp_path_factory) -> Path:
    return _render(tmp_path_factory.mktemp("plugin-on"), plugin_on=True)


class TestPluginOff:
    def test_no_plugin_directory_leaks(self, rendered_off: Path):
        assert not (rendered_off / ".claude-plugin").exists()

    def test_no_stamper_helper_or_contract_asserts(self, rendered_off: Path):
        stamper = (rendered_off / "scripts" / "stamp_manifests.py").read_text(
            encoding="utf-8"
        )
        assert "_stamp_claude_plugin_manifests" not in stamper
        contract = (rendered_off / "tests" / "test_release_flow_contract.py").read_text(
            encoding="utf-8"
        )
        assert ".claude-plugin/plugin/.mcp.json" not in contract


class TestPluginOn:
    def test_scaffold_files_present_and_valid(self, rendered_on: Path):
        plugin_json = json.loads(
            (
                rendered_on
                / ".claude-plugin"
                / "plugin"
                / ".claude-plugin"
                / "plugin.json"
            ).read_text(encoding="utf-8")
        )
        assert plugin_json["name"] == "smoke-mcp"
        # Seeded at 0.0.0: the live version is owned by stamp_manifests.py +
        # the release flow, never by a render.
        assert plugin_json["version"] == "0.0.0"

        mcp_json = json.loads(
            (rendered_on / ".claude-plugin" / "plugin" / ".mcp.json").read_text(
                encoding="utf-8"
            )
        )
        server = mcp_json["smoke-mcp"]
        assert server["command"] == "uvx"
        i = server["args"].index("--from")
        assert server["args"][i + 1].endswith("==0.0.0")

    def test_stamper_and_contract_suite_are_paired(self, rendered_on: Path):
        """The lockstep contract: the stamp helper and the flow-contract
        suite's plugin asserts appear together, so
        tests/test_release_flow_contract.py in the rendered project holds on
        a fresh scaffold (the promotion guard lists the plugin paths
        unconditionally by design)."""
        stamper = (rendered_on / "scripts" / "stamp_manifests.py").read_text(
            encoding="utf-8"
        )
        assert "_stamp_claude_plugin_manifests(version)" in stamper
        contract = (rendered_on / "tests" / "test_release_flow_contract.py").read_text(
            encoding="utf-8"
        )
        assert '".claude-plugin/plugin/.claude-plugin/plugin.json"' in contract
        assert '".claude-plugin/plugin/.mcp.json"' in contract

    def test_stamper_rewrites_both_manifests(self, rendered_on: Path):
        """Run the rendered stamp script for real against the scaffold."""
        # The script stages what it stamps for knope's release commit, so it
        # needs a real git index; the render is not a repo yet.
        if not (rendered_on / ".git").exists():
            subprocess.run(["git", "init", "-q"], cwd=rendered_on, check=True)
        subprocess.run(
            ["python3", "scripts/stamp_manifests.py", "9.9.9"],
            cwd=rendered_on,
            check=True,
            capture_output=True,
            text=True,
        )
        plugin_json = json.loads(
            (
                rendered_on
                / ".claude-plugin"
                / "plugin"
                / ".claude-plugin"
                / "plugin.json"
            ).read_text(encoding="utf-8")
        )
        assert plugin_json["version"] == "9.9.9"
        mcp_json = json.loads(
            (rendered_on / ".claude-plugin" / "plugin" / ".mcp.json").read_text(
                encoding="utf-8"
            )
        )
        args = mcp_json["smoke-mcp"]["args"]
        assert args[args.index("--from") + 1] == "smoke-mcp[all]==9.9.9"
