"""Turn a copy of the smoke render into a project with one required domain var.

Run from inside the copy.  Uncomments the `api_token` example that
`config.py` ships in CONFIG-FIELDS and CONFIG-FROM-ENV
(`env(..., required=True)`) and returns the variable from
`config_contract_env` in `tests/conftest.py`.  template-ci then runs the
copy's gate, which proves the documented example works end to end: every
template-owned test builds through the seam, `serve` refuses in one line, and
the generated configuration reference marks the variable required.

Takes no arguments: the project is the current directory, and its Python
module and env prefix come from the render's `.copier-answers.yml`.  Exits
non-zero when an anchor it edits is missing, so a reworded example or a moved
sentinel fails loudly instead of testing nothing.
"""

from __future__ import annotations

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
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _answer(answers: str, key: str) -> str:
    """One identifier-valued answer from `.copier-answers.yml`."""
    match = re.search(rf"^{key}: *(\S+) *$", answers, re.MULTILINE)
    if match is None or _IDENTIFIER.fullmatch(match[1]) is None:
        sys.exit(f".copier-answers.yml: no identifier-valued {key!r} answer")
    return match[1]


def _uncomment(block: str) -> str:
    return "".join(
        line.replace("# ", "", 1) for line in block.splitlines(keepends=True)
    )


def _replace_once(path: Path, old: str, new: str) -> None:
    src = path.read_text(encoding="utf-8")
    if src.count(old) != 1:
        sys.exit(f"{path}: expected exactly one occurrence of {old!r}")
    path.write_text(src.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    project = Path.cwd()
    answers = (project / ".copier-answers.yml").read_text(encoding="utf-8")
    module = _answer(answers, "python_module")
    prefix = _answer(answers, "env_prefix")
    config = project / "src" / module / "config.py"
    _replace_once(config, _FIELD, _uncomment(_FIELD))
    _replace_once(config, _READ, _uncomment(_READ))
    _replace_once(
        project / "tests" / "conftest.py",
        _EMPTY_CONTRACT,
        f'    """\n    return {{"{prefix}_API_TOKEN": "test-token"}}\n',
    )


if __name__ == "__main__":
    main()
