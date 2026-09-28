"""Turn a copy of the smoke render into a project with one required domain var.

Run from inside the copy.  Uncomments the `api_token` example that
`config.py` ships in CONFIG-FIELDS and CONFIG-FROM-ENV
(`env(..., required=True)`) and returns the variable from
`config_contract_env` in `tests/conftest.py`.  template-ci then runs the
copy's gate, which proves the documented example works end to end: every
template-owned test builds through the seam, `serve` refuses in one line, and
the generated configuration reference marks the variable required.

Takes no arguments: the project is the current directory, its one
`src/*/config.py` is the config it edits, and the env prefix comes from the
render's `.copier-answers.yml`.  Exits
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


def _replace_once(path: Path, old: str, new: str) -> None:
    path = Path(_within_cwd(path))
    src = path.read_text(encoding="utf-8")
    if src.count(old) != 1:
        sys.exit(f"{path}: expected exactly one occurrence of {old!r}")
    path.write_text(src.replace(old, new, 1), encoding="utf-8")


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
    _replace_once(config, _FIELD, _uncomment(_FIELD))
    _replace_once(config, _READ, _uncomment(_READ))
    _replace_once(
        project / "tests" / "conftest.py",
        _EMPTY_CONTRACT,
        f'    """\n    return {{"{prefix}_API_TOKEN": "test-token"}}\n',
    )


if __name__ == "__main__":
    main()
