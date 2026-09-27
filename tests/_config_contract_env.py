"""Apply the project's ``config_contract_env`` to a template-owned test.

Template-owned tests that build the config or server from the environment
call :func:`preset_contract_env`, so a project whose ``from_env`` needs a
variable (``env(..., required=True)``) supplies it once, from the
``config_contract_env`` fixture in its own ``tests/conftest.py``.

Template-owned: re-rendered on every ``copier update``.
"""

from __future__ import annotations

import pytest


def preset_contract_env(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Set every variable the project's ``config_contract_env`` returns.

    Resolved via ``getfixturevalue`` so a ``conftest.py`` that predates the
    fixture (``copier update`` never adds it to that project-owned file)
    keeps passing with nothing preset.  Call it after any scrub of the
    prefixed environment and before any value the test pins itself.
    """
    try:
        env = request.getfixturevalue("config_contract_env")
    except pytest.FixtureLookupError:
        return
    for key, value in dict(env).items():
        monkeypatch.setenv(key, value)
