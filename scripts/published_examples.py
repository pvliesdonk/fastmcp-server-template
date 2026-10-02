"""Read the fenced examples on published documentation pages (#716).

The helper behind ``tests/test_published_examples.py`` (the template-owned
test that runs tagged Python blocks, loads tagged configuration blocks and
checks every shell block) and behind the W4 rule of
``scripts/check_docs_structure.py``. It knows Markdown fences and the tag
forms, nothing about any project.

Tags use pymdownx's ``attr_list`` form, the one superfences keeps as a fence::

    ```python { .run data-expect="results" }
    ```json { .config data-expect="read_only=True" }
    ```python { .fragment }
"""

from __future__ import annotations

import ast
import fnmatch
import json
import re
import shlex
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from pathlib import Path

_FENCE = re.compile(r"^(?P<indent>[ \t]*)(?P<fence>`{3,}|~{3,})(?P<info>[^`]*)$")
_HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*$")
_ATTRS = re.compile(r"\{(?P<body>[^}]*)\}")
_ATTR = re.compile(
    r"""(?P<key>[\w-]+)=(?:"(?P<dq>[^"]*)"|'(?P<sq>[^']*)'|(?P<bare>\S+))"""
)
_EXTRA = re.compile(
    r"(?<![\w\"'${/-])(?P<token>[A-Za-z0-9][\w.-]*\[[\w,.-]+\])(?![\w\"'])"
)
_DOTENV = re.compile(
    r"^\s*(?:export\s+)?(?P<key>[A-Za-z_][A-Za-z0-9_]*)=(?P<value>.*)$"
)
SHELL_LANGS = frozenset({"bash", "sh", "shell", "zsh", "console"})


@dataclass(frozen=True)
class Block:
    """One fenced block as a reader sees it."""

    lang: str
    classes: list[str]
    attrs: dict[str, str]
    code: str
    line: int
    heading_trail: list[str] = field(default_factory=list)


def parse_info(info: str) -> tuple[str, list[str], dict[str, str]]:
    """Split a fence's info string into language, ``.classes`` and ``key="value"`` attributes."""
    info = info.strip()
    classes: list[str] = []
    attrs: dict[str, str] = {}
    braces = _ATTRS.search(info)
    if braces:
        for token in braces.group("body").split():
            if token.startswith("."):
                classes.append(token[1:])
            elif token.startswith("#"):
                attrs["id"] = token[1:]
            else:
                match = _ATTR.fullmatch(token)
                if match:
                    attrs[match.group("key")] = next(
                        v
                        for v in (
                            match.group("dq"),
                            match.group("sq"),
                            match.group("bare"),
                        )
                        if v is not None
                    )
        info = (info[: braces.start()] + info[braces.end() :]).strip()
    for match in _ATTR.finditer(info):
        attrs[match.group("key")] = next(
            v
            for v in (match.group("dq"), match.group("sq"), match.group("bare"))
            if v is not None
        )
    lang = info.split(None, 1)[0] if info else ""
    return (
        (lang if not lang.startswith(("{", '"')) and "=" not in lang else ""),
        classes,
        attrs,
    )


def blocks(text: str) -> list[Block]:
    """Return every fenced block in *text*, with its heading trail and line number."""
    found: list[Block] = []
    trail: list[tuple[int, str]] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        heading = _HEADING.match(lines[i])
        if heading:
            level = len(heading.group(1))
            trail = [(lv, t) for lv, t in trail if lv < level]
            trail.append((level, heading.group(2)))
            i += 1
            continue
        fence = _FENCE.match(lines[i])
        if not fence:
            i += 1
            continue
        marker, indent, start = fence.group("fence"), fence.group("indent"), i
        body: list[str] = []
        i += 1
        while i < len(lines) and not _closes(lines[i], marker):
            body.append(
                lines[i][len(indent) :] if lines[i].startswith(indent) else lines[i]
            )
            i += 1
        lang, classes, attrs = parse_info(fence.group("info"))
        code = "\n".join(body) + ("\n" if body else "")
        found.append(
            Block(lang, classes, attrs, code, start + 1, [t for _, t in trail])
        )
        i += 1
    return found


def _closes(line: str, marker: str) -> bool:
    stripped = line.strip()
    return (
        stripped.startswith(marker[0] * 3)
        and set(stripped) == {marker[0]}
        and len(stripped) >= len(marker)
    )


def expectations(spec: str) -> dict[str, object]:
    """Parse ``field=literal, field=literal`` into a mapping; literals are Python."""
    out: dict[str, object] = {}
    for part in filter(None, (p.strip() for p in spec.split(","))):
        if "=" not in part:
            raise ValueError(f"expectation {part!r} is not field=literal")
        key, _, value = part.partition("=")
        try:
            out[key.strip()] = ast.literal_eval(value.strip())
        except (ValueError, SyntaxError):
            out[key.strip()] = value.strip()
    return out


def env_from_config(block: Block) -> list[tuple[str, dict[str, str]]]:
    """Return ``(name, env)`` for each environment a configuration block defines.

    A JSON block is an MCP client configuration: one entry per ``mcpServers``
    server, with its ``env``.  Any other block is dotenv-shaped, one entry.
    """
    if block.lang in ("json", "jsonc"):
        data = json.loads(block.code)
        servers = data.get("mcpServers") if isinstance(data, dict) else None
        if not isinstance(servers, dict):
            raise ValueError("a JSON configuration block needs an mcpServers object")
        return [
            (name, {str(k): str(v) for k, v in (server.get("env") or {}).items()})
            for name, server in servers.items()
        ]
    env: dict[str, str] = {}
    for raw in block.code.splitlines():
        match = _DOTENV.match(raw)
        if match is None:
            continue
        value = match.group("value").strip()
        try:
            parts = shlex.split(value, comments=True)
        except ValueError:
            parts = [value]
        env[match.group("key")] = parts[0] if parts else ""
    return [("env", env)]


def unquoted_extras(code: str) -> list[tuple[int, str, str]]:
    """Return ``(line, token, quoted)`` for every unquoted ``pkg[extra]`` in shell code.

    zsh expands ``pkg[extra]`` as a glob and fails with ``no matches found``;
    the quoted form works in every shell.
    """
    found = []
    for number, line in enumerate(code.splitlines(), start=1):
        bare = _strip_quotes_and_comments(line)
        for match in _EXTRA.finditer(bare):
            token = match.group("token")
            found.append((number, token, f'"{token}"'))
    return found


def _strip_quotes_and_comments(line: str) -> str:
    out: list[str] = []
    quote: str | None = None
    for char in line:
        if quote:
            if char == quote:
                quote = None
            else:
                out.append(" ")
            continue
        if char in "\"'":
            quote = char
            continue
        if char == "#":
            break
        out.append(char)
    return "".join(out)


def published_pages(root: Path) -> list[Path]:
    """``README.md`` and every page under ``docs/`` that ``exclude_docs`` keeps."""
    patterns: list[str] = []
    mkdocs = root / "mkdocs.yml"
    if mkdocs.exists():
        config = yaml.safe_load(mkdocs.read_text(encoding="utf-8")) or {}
        patterns = [p for p in str(config.get("exclude_docs") or "").split() if p]
    docs = root / "docs"
    pages = [root / "README.md"] if (root / "README.md").exists() else []
    if docs.is_dir():
        pages.extend(
            p
            for p in sorted(docs.rglob("*.md"))
            if not _excluded(p.relative_to(docs).as_posix(), patterns)
            and not p.name.startswith(".")
        )
    return pages


def _excluded(rel: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        if pattern.endswith("/**") and rel.startswith(pattern[:-2]):
            return True
        if fnmatch.fnmatch(rel, pattern):
            return True
        if "/" not in pattern and any(
            fnmatch.fnmatch(part, pattern) for part in rel.split("/")
        ):
            return True
    return False
