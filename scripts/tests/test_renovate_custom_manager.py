"""Offline self-test for the upstream customManagers regex in .github/renovate.json.

Reads the actual matchString from the committed config and applies it to every
Jinja workflow, asserting the capture groups behave: depName is always
owner/repo (subpath stripped), codeql-action dedupes to one depName, and known
pins are captured with the right currentValue. Keeps the regex and its
contract in sync — edit the regex, this test re-verifies it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CONFIG = REPO / ".github" / "renovate.json"
WORKFLOW_DIR = REPO / ".github" / "workflows"


def _matcher() -> re.Pattern[str]:
    cfg = json.loads(CONFIG.read_text())
    (manager,) = cfg["customManagers"]
    (match_string,) = manager["matchStrings"]
    # Renovate uses JS/RE2 named groups `(?<name>)`; Python `re` needs `(?P<name>)`.
    return re.compile(match_string.replace("(?<", "(?P<"))


def _captures() -> list[tuple[str, str]]:
    pat = _matcher()
    hits: list[tuple[str, str]] = []
    for wf in WORKFLOW_DIR.glob("*.jinja"):
        for m in pat.finditer(wf.read_text()):
            hits.append((m.group("depName"), m.group("currentValue")))
    return hits


def test_every_depname_is_owner_slash_repo() -> None:
    # Exactly one slash proves the action subpath (e.g. codeql-action/init) is stripped.
    for dep_name, _ in _captures():
        assert dep_name.count("/") == 1, f"subpath not stripped: {dep_name!r}"


def test_codeql_action_dedupes_to_repo() -> None:
    dep_names = {d for d, _ in _captures()}
    assert "github/codeql-action" in dep_names
    assert not any(d.startswith("github/codeql-action/") for d in dep_names)


def test_known_pins_captured() -> None:
    pairs = set(_captures())
    assert ("astral-sh/setup-uv", "v8.2.0") in pairs  # exact pin captured whole
    assert ("actions/checkout", "v7") in pairs  # major-float pin captured
    assert len({d for d, _ in pairs}) >= 15  # sanity: most actions found


def test_no_sha_or_digest_captured() -> None:
    # Every captured version starts with a literal 'v' + digit; a 40-hex commit
    # SHA (e.g. a digest-pinned action) must NOT be captured as a version.
    for dep_name, current_value in _captures():
        assert current_value.startswith("v") and current_value[1:2].isdigit(), (
            f"{dep_name} captured non-version {current_value!r}"
        )
    dep_names = {d for d, _ in _captures()}
    assert "vale-cli/vale-action" not in dep_names, (
        "SHA-pinned vale-action must not be captured"
    )
