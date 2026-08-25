"""Offline self-test for the upstream customManagers regex in .github/renovate.json.

Reads the actual matchString and managerFilePatterns from the committed config
and applies them to every Jinja file they cover, asserting the capture groups behave: depName is always
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
GITHUB_DIR = REPO / ".github"


def _manager(dep_name: str | None = None) -> dict:
    """The action-pin manager (default) or the one pinned to *dep_name*."""
    cfg = json.loads(CONFIG.read_text())
    managers = cfg["customManagers"]
    if dep_name is None:
        (manager,) = [m for m in managers if "depNameTemplate" not in m]
    else:
        (manager,) = [m for m in managers if m.get("depNameTemplate") == dep_name]
    return manager


def _matcher(manager: dict | None = None) -> re.Pattern[str]:
    (match_string,) = (manager or _manager())["matchStrings"]
    # Renovate uses JS/RE2 named groups `(?<name>)`; Python `re` needs `(?P<name>)`.
    return re.compile(match_string.replace("(?<", "(?P<"))


def _covered_files(manager: dict | None = None) -> list[Path]:
    """Every Jinja file under .github/ that the manager's file patterns select.

    Derived from the committed patterns rather than a hard-coded glob so the
    test cannot silently cover a narrower set than Renovate does (#492).
    Patterns are Renovate's `/regex/` form, matched against repo-relative paths.
    """
    pats = [
        re.compile(p.strip("/")) for p in (manager or _manager())["managerFilePatterns"]
    ]
    return sorted(
        f
        for f in GITHUB_DIR.rglob("*.jinja")
        if any(p.search(f.relative_to(REPO).as_posix()) for p in pats)
    )


def _captures() -> list[tuple[str, str]]:
    pat = _matcher()
    hits: list[tuple[str, str]] = []
    for wf in _covered_files():
        for m in pat.finditer(wf.read_text()):
            hits.append((m.group("depName"), m.group("currentValue")))
    return hits


def test_file_pattern_covers_every_action_pin() -> None:
    """No `@vX` pin under .github/**/*.jinja may sit outside the manager's reach.

    Composite actions under .github/actions/ carried the same setup-uv pin as
    the workflows but were invisible to Renovate, so a bump left the fleet on
    two majors of one action (#492).  Only pins the matchString captures are
    checked: SHA-pinned actions are outside this manager's remit by design.
    """
    pat = _matcher()
    covered = set(_covered_files())
    uncovered = sorted(
        f.relative_to(REPO).as_posix()
        for f in GITHUB_DIR.rglob("*.jinja")
        if f not in covered and pat.search(f.read_text())
    )
    assert not uncovered, f"action pins outside managerFilePatterns: {uncovered}"
    assert any(
        f.relative_to(REPO).as_posix().startswith(".github/actions/") for f in covered
    ), "composite actions under .github/actions/ are not covered"


def test_each_action_pinned_to_one_version() -> None:
    """A Renovate bump must move every captured occurrence of an action together.

    Scoped to the Jinja files this manager owns.  The template's own real
    workflows (`template-*.yml`) are bumped by Renovate's native manager in a
    separate PR, so a transient split between them and the fleet pins is
    tolerated here rather than turning one of the two PRs red.
    """
    versions: dict[str, set[str]] = {}
    for dep_name, current_value in _captures():
        versions.setdefault(dep_name, set()).add(current_value)
    drifted = {d: sorted(v) for d, v in versions.items() if len(v) > 1}
    assert not drifted, f"action pinned at differing versions: {drifted}"


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
    setup_uv_values = {v for d, v in pairs if d == "astral-sh/setup-uv"}
    # Exact semver pin captured whole (not truncated to e.g. "v8"); the literal
    # value drifts with every Renovate bump, so assert the shape, not a version.
    assert any(re.fullmatch(r"v\d+\.\d+\.\d+", v) for v in setup_uv_values)
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


def test_knope_cli_manager_captures_the_version_input() -> None:
    """The second manager tracks knope-dev/action's `version:` input.

    The action-pin manager above bumps the `@vX.Y.Z` ref; the CLI version
    the input names lives on its own line and needs this dedicated manager
    (depName knope-dev/knope, github-releases datasource). Both release
    workflows must carry exactly one identical pin, or the prepare and tag
    halves could run different knope versions.
    """
    manager = _manager("knope-dev/knope")
    pat = _matcher(manager)
    pins: dict[str, list[str]] = {}
    for wf in _covered_files(manager):
        found = [m.group("currentValue") for m in pat.finditer(wf.read_text())]
        if found:
            pins[wf.name] = found
    assert set(pins) == {"release-prepare.yml.jinja", "release.yml.jinja"}, (
        f"knope CLI pin found in: {sorted(pins)}"
    )
    values = {v for found in pins.values() for v in found}
    assert len(values) == 1, f"knope CLI pins disagree across workflows: {pins}"
    (value,) = values
    assert re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", value), value
