"""Input checks in the build-plugin-zip composite action's two scripts (#694).

`vendor.py` rewrites a staged plugin directory and `verify.py` vets the
unpacked zip before it is published.  Both take a directory and a version
from the command line, and `verify.py` also follows a path read out of the
archive's own `.mcp.json`; none of them may reach outside the directory
they were pointed at.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ACTION = (
    Path(__file__).resolve().parents[2] / ".github" / "actions" / "build-plugin-zip"
)
# The action ships its scripts beside action.yml, outside any package; mypy
# only sees them through this path insertion, hence the import ignores.
sys.path.insert(0, str(ACTION))

import vendor  # type: ignore[import-not-found]  # noqa: E402
import verify  # type: ignore[import-not-found]  # noqa: E402

WHEEL = "pkg-1.2.3-py3-none-any.whl"


@pytest.fixture(autouse=True)
def _in_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The scripts only act inside the working directory, as in the action."""
    monkeypatch.chdir(tmp_path)


def _staged(root: Path, *, from_spec: str = "pkg[all]==1.0.0") -> Path:
    (root / ".claude-plugin").mkdir(parents=True)
    (root / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "pkg", "version": "1.0.0"}), encoding="utf-8"
    )
    (root / ".mcp.json").write_text(
        json.dumps({"pkg": {"command": "uvx", "args": ["--from", from_spec, "pkg"]}}),
        encoding="utf-8",
    )
    (root / "wheels").mkdir()
    (root / "wheels" / WHEEL).write_bytes(b"wheel")
    return root


@pytest.mark.parametrize("version", ["1.2.3", "1.2.3-rc.1", "0.0.0-dev"])
def test_vendor_accepts_the_versions_the_workflows_pass(
    tmp_path: Path, version: str
) -> None:
    root = _staged(tmp_path / "stage")
    assert vendor.main(["vendor.py", str(root), version]) == 0
    manifest = json.loads((root / ".claude-plugin" / "plugin.json").read_text())
    assert manifest["version"] == version


@pytest.mark.parametrize("version", ["", "v1.2.3", "1.2", "1.2.3; rm -rf /", "1.2.3\n"])
def test_vendor_refuses_a_malformed_version(tmp_path: Path, version: str) -> None:
    root = _staged(tmp_path / "stage")
    before = (root / ".claude-plugin" / "plugin.json").read_bytes()
    with pytest.raises(vendor.VendorError, match="version"):
        vendor.main(["vendor.py", str(root), version])
    assert (root / ".claude-plugin" / "plugin.json").read_bytes() == before


def test_vendor_refuses_to_write_through_a_link_out_of_the_stage(
    tmp_path: Path,
) -> None:
    root = _staged(tmp_path / "stage")
    outside = tmp_path / "outside.json"
    outside.write_text((root / ".mcp.json").read_text(), encoding="utf-8")
    (root / ".mcp.json").unlink()
    (root / ".mcp.json").symlink_to(outside)
    before = outside.read_bytes()
    with pytest.raises(vendor.VendorError, match="outside"):
        vendor.main(["vendor.py", str(root), "1.2.3"])
    assert outside.read_bytes() == before


def _vendored(root: Path, spec_tail: str) -> Path:
    root = _staged(root)
    vendor.stamp_version(root, "1.2.3")
    mcp = json.loads((root / ".mcp.json").read_text())
    mcp["pkg"]["args"][1] = "${CLAUDE_PLUGIN_ROOT}/" + spec_tail
    (root / ".mcp.json").write_text(json.dumps(mcp), encoding="utf-8")
    return root


def test_verify_accepts_a_spec_naming_the_vendored_wheel(tmp_path: Path) -> None:
    root = _vendored(tmp_path / "unpacked", f"wheels/{WHEEL}[all]")
    assert verify.main(["verify.py", str(root), "1.2.3"]) == 0


def test_verify_refuses_a_spec_that_escapes_the_archive(tmp_path: Path) -> None:
    """A `..` spec naming a real file outside the zip must not verify."""
    (tmp_path / "escaped.whl").write_bytes(b"not shipped")
    root = _vendored(tmp_path / "unpacked", "wheels/../../escaped.whl")
    with pytest.raises(verify.VerifyError, match="archive"):
        verify.main(["verify.py", str(root), "1.2.3"])


def test_verify_refuses_a_spec_that_is_not_a_wheel(tmp_path: Path) -> None:
    root = _vendored(tmp_path / "unpacked", "wheels/../.mcp.json")
    with pytest.raises(verify.VerifyError):
        verify.main(["verify.py", str(root), "1.2.3"])


def test_vendor_refuses_a_stage_outside_the_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _staged(tmp_path / "stage")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    with pytest.raises(vendor.VendorError, match="working directory"):
        vendor.main(["vendor.py", str(root), "1.2.3"])


def test_verify_refuses_an_archive_outside_the_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _vendored(tmp_path / "unpacked", f"wheels/{WHEEL}")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    with pytest.raises(verify.VerifyError, match="working directory"):
        verify.main(["verify.py", str(root), "1.2.3"])
