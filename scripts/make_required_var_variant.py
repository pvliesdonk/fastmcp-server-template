"""Turn a copy of the smoke render into a project with one required domain var.

Run from inside the copy.  Uncomments the `api_token` example that
`config.py` ships in CONFIG-FIELDS and CONFIG-FROM-ENV
(`env(..., required=True)`) and returns the variable from
`config_contract_env` in `tests/conftest.py`.  It also adds, in `server.py`'s
DOMAIN-WIRING block, the check a real domain keeps (the v10.3 upgrade notes
allow it): an empty `api_token` raises `ConfigurationError` when the server is
built.  A config built by hand carries only the field's placeholder, so any
template-owned test that passes one to `make_server` fails here (#705).
template-ci then runs the copy's gate, which proves the documented example
works end to end: every template-owned test builds through the seam, `serve`
refuses in one line, and the generated configuration reference marks the
variable required.

Takes no arguments: the project is the current directory, its one
`src/*/config.py` is the config it edits, its `server.py` sits beside it, and
the env prefix comes from the render's `.copier-answers.yml`.  Exits
non-zero when an anchor it edits is missing, so a reworded example or a moved
sentinel fails loudly instead of testing nothing.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

_FIELD = (
    "    # api_token: str = field(\n"
    '    #     default="",\n'
    '    #     metadata={"help": "Upstream API token.", "tags": ("upstream",)},\n'
    "    # )\n"
)
_READ = '            # api_token=env(_ENV_PREFIX, "API_TOKEN", required=True),\n'
_EMPTY_CONTRACT = '    """\n    return {}\n'
_WIRING_END = "    # DOMAIN-WIRING-END\n"
_PREFIX = re.compile(r"^env_prefix: *(\w+) *$", re.MULTILINE)


def _within_cwd(path: str | os.PathLike[str]) -> str:
    """*path* canonicalised, refusing one outside the working directory (#694).

    Every path this script touches lives in the checkout it runs from, so a
    path that resolves elsewhere (``..``, an absolute path, a symlink) is a
    broken or hostile invocation.  The realpath-then-prefix shape is the one
    SonarCloud's path-injection rules recognise.
    """
    resolved = os.path.realpath(path)
    base_dir = os.path.realpath(os.getcwd())  # noqa: PTH109 - the shape Sonar reads
    if resolved != base_dir and not resolved.startswith(base_dir + os.sep):
        raise SystemExit(f"path {path!r} is outside the working directory")
    return resolved


def _uncomment(block: str) -> str:
    return "".join(
        line.replace("# ", "", 1) for line in block.splitlines(keepends=True)
    )


def _substitute_once(path: Path, old: str, new: str) -> None:
    """Replace the one occurrence of *old* in *path* with *new*.

    The edited text goes through an open handle rather than into
    ``Path.write_text``, which SonarCloud reads as a path argument even for
    the file's own content; the path itself is still checked (#694).
    """
    path = Path(_within_cwd(path))
    src = path.read_text(encoding="utf-8")
    if src.count(old) != 1:
        sys.exit(f"{path}: expected exactly one occurrence of {old!r}")
    with open(path, "w", encoding="utf-8") as fh:  # noqa: PTH123 - see above
        fh.write(src.replace(old, new, 1))


def main() -> None:
    project = Path.cwd()
    configs = sorted(project.glob("src/*/config.py"))
    if len(configs) != 1:
        sys.exit(f"expected exactly one src/*/config.py, found {configs}")
    config = configs[0]
    answers = (project / ".copier-answers.yml").read_text(encoding="utf-8")
    match = _PREFIX.search(answers)
    if match is None:
        sys.exit(".copier-answers.yml: no env_prefix answer")
    prefix = match[1]
    _substitute_once(config, _FIELD, _uncomment(_FIELD))
    _substitute_once(config, _READ, _uncomment(_READ))
    _substitute_once(
        config.parent / "server.py",
        _WIRING_END,
        "    from fastmcp_pvl_core import ConfigurationError\n"
        "\n"
        "    if not config.api_token:\n"
        f'        raise ConfigurationError("{prefix}_API_TOKEN: required but empty")\n'
        + _WIRING_END,
    )
    _substitute_once(
        project / "tests" / "conftest.py",
        _EMPTY_CONTRACT,
        f'    """\n    return {{"{prefix}_API_TOKEN": "test-token"}}\n',
    )


if __name__ == "__main__":
    main()
