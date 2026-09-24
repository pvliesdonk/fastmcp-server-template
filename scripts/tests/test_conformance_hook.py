"""The rendered pre-commit config runs the template-conformance check at
pre-push (#259), and FORKING.md's detach command removes exactly that hook."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from pathlib import Path

_SPAN = re.compile(
    r"^\s*# >>> template-tracking: conformance hook.*?"
    r"^\s*# <<< template-tracking: conformance hook\n",
    re.MULTILINE | re.DOTALL,
)


def _hooks(config: dict) -> dict[str, dict]:
    return {h["id"]: h for repo in config["repos"] for h in repo["hooks"]}


def test_conformance_hook_runs_at_pre_push(smoke_render: Path) -> None:
    config = yaml.safe_load((smoke_render / ".pre-commit-config.yaml").read_text())
    hook = _hooks(config)["template-conformance"]
    assert hook["stages"] == ["pre-push"]
    assert "--since auto --hook" in hook["entry"]
    assert "pre-push" in config["default_install_hook_types"]


def test_detach_span_removes_only_the_hook(smoke_render: Path) -> None:
    text = (smoke_render / ".pre-commit-config.yaml").read_text()
    assert len(_SPAN.findall(text)) == 1
    detached = yaml.safe_load(_SPAN.sub("", text))
    remaining = _hooks(detached)
    assert "template-conformance" not in remaining
    assert len(remaining) == len(_hooks(yaml.safe_load(text))) - 1


def test_markers_are_not_sentinel_shaped(smoke_render: Path) -> None:
    """A `-START`/`-END` pair would make the conformance check treat the
    hook as project-owned content and stop checking it."""
    text = (smoke_render / ".pre-commit-config.yaml").read_text()
    span = _SPAN.search(text)
    assert span
    assert not re.search(r"-(START|END)\b", span.group(0))
