"""Offline unit tests for the rendered scripts/vendor_spa.py pipeline.

vendor_spa.py is module-agnostic (discovers src/*/static/app.src.html), so we
exercise it against a temp project tree — never the network. Generate-mode
(download) is covered by template-ci's render, not here.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


_VENDOR_SPA = Path(__file__).resolve().parent.parent / "vendor_spa.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("vendor_spa", _VENDOR_SPA)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    # Discovery is deferred to main(); import is safe without a project tree.
    spec.loader.exec_module(mod)
    return mod


def _make_tree(tmp_path: Path, src_html: str) -> Path:
    static = tmp_path / "src" / "demo_mod" / "static"
    static.mkdir(parents=True)
    (static / "app.src.html").write_text(src_html, encoding="utf-8")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "vendor_spa.py").write_text(
        _VENDOR_SPA.read_text(encoding="utf-8"), encoding="utf-8"
    )
    return tmp_path


def test_vendored_versions_has_ext_apps_only():
    mod = _load_module()
    assert set(mod.VENDORED_VERSIONS) == {"ext-apps"}
    assert mod.VENDORED_VERSIONS["ext-apps"]["version"] == "1.3.1"


def test_check_fails_when_app_html_absent(tmp_path: Path):
    tree = _make_tree(
        tmp_path, "<html><head></head><body>app___get_status</body></html>"
    )
    result = subprocess.run(
        [sys.executable, str(tree / "scripts" / "vendor_spa.py"), "--check"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "does not exist" in result.stderr


def test_check_passes_then_fails_on_source_drift(tmp_path: Path):
    src = "<html><head></head><body>app___get_status</body></html>"
    tree = _make_tree(tmp_path, src)
    mod = _load_module()
    # Hand-build an app.html carrying the correct source-hash marker.
    marker = mod._SOURCE_HASH_MARKER.format(hash=mod._source_hash(src))
    out = src.replace("</head>", marker + "\n</head>")
    (tree / "src" / "demo_mod" / "static" / "app.html").write_text(
        out, encoding="utf-8"
    )
    ok = subprocess.run(
        [sys.executable, str(tree / "scripts" / "vendor_spa.py"), "--check"],
        capture_output=True,
        text=True,
    )
    assert ok.returncode == 0, ok.stderr
    # Mutate the source → --check must fail.
    (tree / "src" / "demo_mod" / "static" / "app.src.html").write_text(
        src.replace("app___get_status", "app___get_info"), encoding="utf-8"
    )
    drift = subprocess.run(
        [sys.executable, str(tree / "scripts" / "vendor_spa.py"), "--check"],
        capture_output=True,
        text=True,
    )
    assert drift.returncode == 1
    assert "out of date" in drift.stderr


def test_starter_src_html_is_inlineable(tmp_path: Path):
    """The shipped app.src.html must carry exactly the ext-apps module import
    that _inline_module rewrites, and the app___ tool literals."""
    starter = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "{{python_module}}"
        / "static"
        / "app.src.html"
    )
    text = starter.read_text(encoding="utf-8")
    assert "import { App }" in text
    assert "@modelcontextprotocol/ext-apps@1.3.1/app-with-deps" in text
    assert "app___get_status" in text
    assert "app___get_info" in text
    assert "{{" not in text and "{%" not in text  # no Jinja in static body
