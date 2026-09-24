"""The rendered classifiers name exactly the Python versions CI requires
(#662): the matrix gained 3.14 while the classifiers stayed at 3.13, and a
downstream that added the missing line by hand read as drift outside every
sentinel.  A matrix entry marked `experimental` may fail, so it is not a
version the project claims."""

from __future__ import annotations

import re
import tomllib
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from pathlib import Path


def _ci_versions(root: Path) -> set[str]:
    ci = yaml.safe_load((root / ".github/workflows/ci.yml").read_text())
    versions: set[str] = set()
    for job in ci["jobs"].values():
        include = job.get("strategy", {}).get("matrix", {}).get("include", [])
        versions |= {
            str(e["python-version"])
            for e in include
            if "python-version" in e and not e.get("experimental", False)
        }
    return versions


def test_classifiers_match_the_required_ci_matrix(smoke_render: Path) -> None:
    project = tomllib.loads((smoke_render / "pyproject.toml").read_text())
    classifiers = project["project"]["classifiers"]
    claimed = {
        m.group(1)
        for c in classifiers
        if (m := re.fullmatch(r"Programming Language :: Python :: (3\.\d+)", c))
    }
    required = _ci_versions(smoke_render)
    assert required, "found no required python-version in ci.yml's matrix"
    assert claimed == required


def test_development_status_sits_in_the_project_block(smoke_render: Path) -> None:
    text = (smoke_render / "pyproject.toml").read_text()
    block = re.search(
        r"# PROJECT-CLASSIFIERS-START.*?# PROJECT-CLASSIFIERS-END", text, re.DOTALL
    )
    assert block, "pyproject.toml has no PROJECT-CLASSIFIERS block"
    assert "Development Status ::" in block.group(0)
    assert text.count("Development Status ::") == 1
