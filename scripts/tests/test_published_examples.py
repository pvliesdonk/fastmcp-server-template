"""Tests for scripts/published_examples.py (#716, part 2)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from published_examples import (
    blocks,
    env_from_config,
    expectations,
    parse_info,
    published_pages,
    unquoted_extras,
)

PAGE = """---
description: "x"
kind: how-to
---

# Install

## From PyPI

```bash
pip install demo-mcp[all]
uv tool install "demo-mcp[all]"
echo "see demo-mcp[all]"  # pip install demo-mcp[all] in a comment
[ -f x ] && echo ${arr[0]} && [[ -n "$x" ]]
```

## Quick start

```python { .run data-expect="results" }
results = [1]
```

    ```python
    indented, not a fence at column 0 but still a fence
    ```

```json { .config data-expect="read_only=True, port=8000" }
{"mcpServers": {"a": {"env": {"DEMO_MCP_READ_ONLY": "true"}}, "b": {"env": {}}}}
```

```python {.fragment}
x = 1
```

~~~python
plain tilde fence
~~~

```text
a ``` inside text is not a closing fence
```
"""


def test_blocks_carry_lang_tags_code_and_heading_trail() -> None:
    found = blocks(PAGE)
    assert [(b.lang, b.classes) for b in found] == [
        ("bash", []),
        ("python", ["run"]),
        ("python", []),
        ("json", ["config"]),
        ("python", ["fragment"]),
        ("python", []),
        ("text", []),
    ]
    run = found[1]
    assert run.attrs == {"data-expect": "results"}
    assert run.code == "results = [1]\n"
    assert run.heading_trail == ["Install", "Quick start"]
    assert run.line == 19
    assert found[2].code == "indented, not a fence at column 0 but still a fence\n"
    assert found[6].code == "a ``` inside text is not a closing fence\n"


def test_parse_info_forms() -> None:
    assert parse_info("python") == ("python", [], {})
    assert parse_info("python { .run }") == ("python", ["run"], {})
    assert parse_info('json {.config data-expect="a=1" title="x"}') == (
        "json",
        ["config"],
        {"data-expect": "a=1", "title": "x"},
    )
    assert parse_info('bash title="x"') == ("bash", [], {"title": "x"})
    assert parse_info("") == ("", [], {})


def test_expectations_parse_python_literals() -> None:
    assert expectations("read_only=True, port=8000, name='a b'") == {
        "read_only": True,
        "port": 8000,
        "name": "a b",
    }
    assert expectations("") == {}
    with pytest.raises(ValueError, match="x"):
        expectations("x")


def test_env_from_config_json_servers_and_dotenv() -> None:
    (json_block,) = [b for b in blocks(PAGE) if "config" in b.classes]
    assert env_from_config(json_block) == [
        ("a", {"DEMO_MCP_READ_ONLY": "true"}),
        ("b", {}),
    ]
    dotenv = blocks(
        '```bash { .config }\nexport A=1\nB="two words"\n# comment\n\nC=3 # trailing\n```\n'
    )[0]
    assert env_from_config(dotenv) == [("env", {"A": "1", "B": "two words", "C": "3"})]
    with pytest.raises(ValueError, match="mcpServers"):
        env_from_config(blocks('```json { .config }\n{"other": 1}\n```\n')[0])


def test_unquoted_extras_flags_only_the_unsafe_token() -> None:
    (shell,) = [b for b in blocks(PAGE) if b.lang == "bash"]
    assert unquoted_extras(shell.code) == [(1, "demo-mcp[all]", '"demo-mcp[all]"')]
    assert unquoted_extras("pip install 'a[b]'\nuvx --from a[b,c] a\n") == [
        (2, "a[b,c]", '"a[b,c]"')
    ]


def test_published_pages_honour_exclude_docs_and_readme(tmp_path: Path) -> None:
    (tmp_path / "mkdocs.yml").write_text(
        "exclude_docs: |\n  design/**\n  drafts\n  releases/next.md\n", encoding="utf-8"
    )
    for rel in (
        "index.md",
        "design/d.md",
        "use/drafts/x.md",
        "releases/next.md",
        "use/a.md",
    ):
        path = tmp_path / "docs" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# x\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# r\n", encoding="utf-8")
    assert [p.relative_to(tmp_path).as_posix() for p in published_pages(tmp_path)] == [
        "README.md",
        "docs/index.md",
        "docs/use/a.md",
    ]
