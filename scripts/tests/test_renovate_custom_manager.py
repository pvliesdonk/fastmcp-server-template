"""Offline self-test for the upstream customManagers regex in .github/renovate.json.

Reads the actual matchStrings and managerFilePatterns from the committed config
and applies them to every Jinja file they cover, asserting the capture groups behave: depName is always
owner/repo (subpath stripped), codeql-action dedupes to one depName, known
pins are captured with the right currentValue, and a SHA pin's digest and
version comment are captured separately. Keeps the regexes and their contract
in sync — edit a regex, this test re-verifies it. It also holds the pin
policy itself: every action is pinned to a commit SHA (#694).
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


def _matchers(manager: dict | None = None) -> list[re.Pattern[str]]:
    # Renovate uses JS/RE2 named groups `(?<name>)`; Python `re` needs `(?P<name>)`.
    return [
        re.compile(match_string.replace("(?<", "(?P<"))
        for match_string in (manager or _manager())["matchStrings"]
    ]


def _matcher(manager: dict | None = None) -> re.Pattern[str]:
    (pattern,) = _matchers(manager)
    return pattern


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


def _captures_with_digest() -> list[tuple[str, str, str | None]]:
    """``(depName, currentValue, currentDigest or None)`` for every capture."""
    hits: list[tuple[str, str, str | None]] = []
    for wf in _covered_files():
        text = wf.read_text()
        for pat in _matchers():
            for m in pat.finditer(text):
                digest = m.groupdict().get("currentDigest")
                hits.append((m.group("depName"), m.group("currentValue"), digest))
    return hits


def _captures() -> list[tuple[str, str]]:
    return [(dep, value) for dep, value, _ in _captures_with_digest()]


def test_file_pattern_covers_every_action_pin() -> None:
    """No `@vX` pin under .github/**/*.jinja may sit outside the manager's reach.

    Composite actions under .github/actions/ carried the same setup-uv pin as
    the workflows but were invisible to Renovate, so a bump left the fleet on
    two majors of one action (#492).  Only pins the matchString captures are
    checked; a pin neither matchString reads is caught by
    test_every_action_is_pinned_to_a_commit_sha.
    """
    pats = _matchers()
    covered = set(_covered_files())
    uncovered = sorted(
        f.relative_to(REPO).as_posix()
        for f in GITHUB_DIR.rglob("*.jinja")
        if f not in covered and any(p.search(f.read_text()) for p in pats)
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
    versions: dict[str, set[tuple[str, str | None]]] = {}
    for dep_name, current_value, digest in _captures_with_digest():
        versions.setdefault(dep_name, set()).add((current_value, digest))
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


def test_digest_and_version_are_captured_separately() -> None:
    """A SHA pin yields its 40-hex digest and the `# vX` comment as its version.

    Renovate updates both from those two groups; a SHA captured as the version
    would make it look up a tag that does not exist.
    """
    captures = _captures_with_digest()
    for dep_name, current_value, digest in captures:
        assert current_value.startswith("v") and current_value[1:2].isdigit(), (
            f"{dep_name} captured non-version {current_value!r}"
        )
        assert digest is None or re.fullmatch(r"[0-9a-f]{40}", digest), (
            f"{dep_name} captured malformed digest {digest!r}"
        )
    vale = [c for c in captures if c[0] == "vale-cli/vale-action"]
    assert vale, "SHA-pinned vale-action must be captured with its digest"
    assert all(digest is not None for _, _, digest in vale)


_USES = re.compile(r"uses:\s+(?P<ref>[\w.-]+/[\w.-]+(?:/[\w./-]+)?@\S+)(?P<rest>.*)")
_SHA_PIN = re.compile(r"[^@]+@[0-9a-f]{40}")
_VERSION_COMMENT = re.compile(r"\s+#\s+v\d\S*")


def test_every_action_is_pinned_to_a_commit_sha() -> None:
    """Every third-party or GitHub action is pinned to a commit SHA plus `# vX`.

    Covers the Jinja sources every project renders and the template's own
    workflows. A tag can be moved after review; a SHA cannot, and SonarCloud
    rates each tag pin a vulnerability in every rendered project
    (githubactions:S7637, #694). Local `./` actions are exempt.
    """
    offenders = []
    for path in sorted(GITHUB_DIR.rglob("*")):
        if not path.is_file() or not (".yml" in path.name or ".yaml" in path.name):
            continue
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            m = _USES.search(line)
            if m is None:
                continue
            if not _SHA_PIN.fullmatch(m["ref"]) or not _VERSION_COMMENT.match(
                m["rest"]
            ):
                offenders.append(f"{path.relative_to(REPO)}:{lineno}: {line.strip()}")
    assert not offenders, "actions not pinned to `@<sha>  # vX`:\n" + "\n".join(
        offenders
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
