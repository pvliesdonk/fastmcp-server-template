"""The `_preset_contract_env` helper is repeated verbatim in six tests.

It cannot be one shared module: a sibling import resolves only when a
project's `tests/` is not a package, and several downstreams make it one.
So each template-owned test that builds from the environment carries its own
copy; this test keeps the copies identical, so a fix to one reaches all.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CARRIERS = (
    "tests/test_config_contract.py.jinja",
    "tests/test_health.py.jinja",
    "tests/test_model_facing_text.py.jinja",
    "tests/test_serve_logging.py.jinja",
    "tests/test_task_backend.py.jinja",
    "tests/test_tool_outcomes.py.jinja",
)
# From the `def` line through the helper's last statement; the signature's
# closing `) -> None:` sits in column 0, so "up to the next unindented line"
# would stop inside the signature and compare nothing.
_DEF = re.compile(
    r"^def _preset_contract_env\(.*?^        monkeypatch\.setenv\(key, value\)\n",
    re.MULTILINE | re.DOTALL,
)


def _helper(relpath: str) -> str:
    text = (REPO / relpath).read_text(encoding="utf-8")
    found = _DEF.findall(text)
    assert len(found) == 1, f"{relpath}: expected one _preset_contract_env"
    return found[0]


def test_every_carrier_defines_the_helper_identically() -> None:
    copies = {path: _helper(path) for path in CARRIERS}
    reference = copies[CARRIERS[0]]
    differing = [path for path, body in copies.items() if body != reference]
    assert not differing, f"_preset_contract_env differs in: {differing}"


def test_every_carrier_calls_the_helper() -> None:
    for path in CARRIERS:
        text = (REPO / path).read_text(encoding="utf-8")
        assert "_preset_contract_env(request, monkeypatch)" in text, path
