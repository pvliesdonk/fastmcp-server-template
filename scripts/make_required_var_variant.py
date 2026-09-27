"""Turn a copy of the smoke render into a project with one required domain var.

Uncomments the `api_token` example that `config.py` ships in CONFIG-FIELDS and
CONFIG-FROM-ENV (`env(..., required=True)`) and returns the variable from
`config_contract_env` in `tests/conftest.py`. template-ci then runs the copy's
gate, which proves the documented example works end to end: every
template-owned test builds through the seam, `serve` refuses in one line, and
the generated configuration reference marks the variable required.

Exits non-zero when an anchor it edits is missing, so a reworded example or a
moved sentinel fails loudly instead of testing nothing.

Usage: make_required_var_variant.py PROJECT_DIR PYTHON_MODULE ENV_PREFIX
"""

from __future__ import annotations

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


def _uncomment(block: str) -> str:
    return "".join(
        line.replace("# ", "", 1) for line in block.splitlines(keepends=True)
    )


def _replace_once(path: Path, old: str, new: str) -> None:
    src = path.read_text(encoding="utf-8")
    if src.count(old) != 1:
        sys.exit(f"{path}: expected exactly one occurrence of {old!r}")
    path.write_text(src.replace(old, new, 1), encoding="utf-8")


def main(root: str, module: str, prefix: str) -> None:
    project = Path(root)
    config = project / "src" / module / "config.py"
    _replace_once(config, _FIELD, _uncomment(_FIELD))
    _replace_once(config, _READ, _uncomment(_READ))
    _replace_once(
        project / "tests" / "conftest.py",
        _EMPTY_CONTRACT,
        f'    """\n    return {{"{prefix}_API_TOKEN": "test-token"}}\n',
    )


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__.rsplit("Usage: ", 1)[1].strip())
    main(*sys.argv[1:4])
