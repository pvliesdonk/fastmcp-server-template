#!/usr/bin/env python3
"""Generate the config-surface artifacts from a single source of truth.

Reads a rendered project's ``.copier-answers.yml`` and its
``config-presentation.yml``, then merges four provenance sources into one
declaration-ordered variable list:

- ``core`` — from ``fastmcp_pvl_core.server_config_surface()``, which owns
  the help text and tags for every ``ServerConfig`` field.
- ``template`` / ``external`` — from ``config-presentation.yml``, the
  template-owned vars core does not know about.
- ``domain`` — reserved for a project's own ``ProjectConfig`` fields.

This script is template-owned and ships byte-identical to every project, so
it discovers the project root and its dependency floor at runtime rather
than hard-coding a package name or version. ``config-presentation.yml``
ships the same way; ``{PREFIX}`` in it is substituted with the project's
``env_prefix`` at generation time, not by Jinja.

copier's ``_tasks`` run before any virtualenv exists for the freshly
rendered project, so this script cannot assume ``fastmcp-pvl-core`` or
PyYAML are importable; ``ensure_core_available`` re-execs itself under
``uv run --no-project`` with both pinned ad hoc when the import fails.

Usage::

    python scripts/gen_config_surface.py           # Generate config artifacts
    python scripts/gen_config_surface.py --check    # Verify they are up-to-date (offline)
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from typing import Any

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Var:
    """One config variable, from whichever provenance produced it."""

    name: str  # full env var name, e.g. "SCHOLAR_MCP_BASE_URL" or "FASTMCP_LOG_LEVEL"
    suffix: str | None  # part after "{PREFIX}_", or None for unprefixed vars
    provenance: str  # "core" | "template" | "external" | "domain"
    type_name: str
    default: object
    help: str
    tags: tuple[str, ...]
    inferred: bool
    wizard: Mapping[str, object]


# Rank order for the provenance merge; vars are ordered by this rank first,
# then by declaration order within each provenance.
_PROVENANCE_ORDER = ("core", "template", "external", "domain")

_CORE_FLOOR_RE = re.compile(r"fastmcp-pvl-core\s*>=\s*([0-9]+\.[0-9]+\.[0-9]+)")


# ---------------------------------------------------------------------------
# Answers + presentation config
# ---------------------------------------------------------------------------


def load_answers(project_root: Path | str) -> dict[str, object]:
    """Read `.copier-answers.yml` from a rendered project."""
    import yaml

    project_root = Path(project_root)
    answers_path = project_root / ".copier-answers.yml"
    if not answers_path.exists():
        raise SystemExit(
            f"ERROR: {answers_path} not found — this script must be run from "
            "the root of a project rendered by copier (missing "
            ".copier-answers.yml)."
        )
    data = yaml.safe_load(answers_path.read_text(encoding="utf-8"))
    return data or {}


def _substitute_prefix(obj: Any, env_prefix: str) -> Any:
    """Recursively replace the literal token ``{PREFIX}`` with *env_prefix*.

    Applies to dict keys as well as values — ``wizard_routing`` options emit
    dicts keyed by ``"{PREFIX}_TRANSPORT"``.
    """
    if isinstance(obj, str):
        return obj.replace("{PREFIX}", env_prefix)
    if isinstance(obj, dict):
        return {
            _substitute_prefix(k, env_prefix): _substitute_prefix(v, env_prefix)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_substitute_prefix(item, env_prefix) for item in obj]
    return obj


def load_presentation(project_root: Path | str, env_prefix: str) -> dict[str, Any]:
    """Load `config-presentation.yml` with `{PREFIX}` substituted."""
    import yaml

    project_root = Path(project_root)
    presentation_path = project_root / "config-presentation.yml"
    if not presentation_path.exists():
        raise SystemExit(f"ERROR: {presentation_path} not found.")
    raw = yaml.safe_load(presentation_path.read_text(encoding="utf-8"))
    return _substitute_prefix(raw, env_prefix)


# ---------------------------------------------------------------------------
# Provenance merge
# ---------------------------------------------------------------------------


def collect_vars(
    project_root: Path | str, answers: Mapping[str, object]
) -> tuple[Var, ...]:
    """Merge core + presentation-declared vars into one provenance-ordered tuple.

    Ordering is contractual: template-ci renders the template twice and diffs
    the results, so the merge must be deterministic across processes. Core
    vars come from ``server_config_surface()``, which returns a
    declaration-ordered tuple for exactly this reason — never iterate a
    ``set``/``frozenset`` here.
    """
    from fastmcp_pvl_core import server_config_surface

    project_root = Path(project_root)
    if "env_prefix" not in answers:
        raise SystemExit(
            "ERROR: 'env_prefix' missing from .copier-answers.yml — a project "
            "rendered by this template always answers that question."
        )
    env_prefix = str(answers["env_prefix"])
    # config-presentation.yml ships byte-identical, so it lives at *project_root*
    # in a real rendered project. Fall back to the copy co-located with this
    # script (the template repo root, when running the template's own tests)
    # so collect_vars works against a project_root that only has the parts a
    # caller actually needs — e.g. a bare .copier-answers.yml in unit tests.
    presentation_root = (
        project_root
        if (project_root / "config-presentation.yml").exists()
        else _project_root()
    )
    presentation = load_presentation(presentation_root, env_prefix)

    collected: list[Var] = [
        Var(
            name=f"{env_prefix}_{field.suffix}",
            suffix=field.suffix,
            provenance="core",
            type_name=field.type_name,
            default=field.default,
            help=field.help,
            tags=tuple(field.tags),
            inferred=field.inferred,
            wizard=dict(field.wizard),
        )
        for field in server_config_surface()
    ]

    prefix_marker = f"{env_prefix}_"
    for raw in presentation.get("vars", ()):
        when_answer = raw.get("when_answer")
        if when_answer is not None and not answers.get(when_answer):
            continue
        name = raw["name"]
        suffix = name[len(prefix_marker) :] if name.startswith(prefix_marker) else None
        collected.append(
            Var(
                name=name,
                suffix=suffix,
                provenance=raw["provenance"],
                type_name=raw["type_name"],
                default=raw.get("default"),
                help=raw["help"],
                tags=tuple(raw.get("tags", ())),
                inferred=bool(raw.get("inferred", False)),
                wizard=dict(raw.get("wizard", {})),
            )
        )

    seen_names: dict[str, str] = {}
    for var in collected:
        prior_provenance = seen_names.get(var.name)
        if prior_provenance is not None:
            raise SystemExit(
                f"ERROR: duplicate config var name {var.name!r} — declared by "
                f"both the {prior_provenance!r} and {var.provenance!r} "
                "provenance sources. Every var name must be unique across "
                "core, template, external, and domain."
            )
        seen_names[var.name] = var.provenance

    return tuple(sorted(collected, key=lambda v: _PROVENANCE_ORDER.index(v.provenance)))


# ---------------------------------------------------------------------------
# Self-bootstrap
# ---------------------------------------------------------------------------


def _core_floor(project_root: Path) -> str:
    """Parse the `fastmcp-pvl-core>=X.Y.Z` floor from the project's pyproject.toml."""
    pyproject_path = project_root / "pyproject.toml"
    if not pyproject_path.exists():
        raise SystemExit(f"ERROR: {pyproject_path} not found.")
    text = pyproject_path.read_text(encoding="utf-8")
    match = _CORE_FLOOR_RE.search(text)
    if match is None:
        raise SystemExit(
            f"ERROR: no 'fastmcp-pvl-core>=X.Y.Z' dependency found in {pyproject_path}"
        )
    return match.group(1)


def _core_importable() -> bool:
    """Whether `fastmcp_pvl_core` can be imported in the current interpreter."""
    try:
        import fastmcp_pvl_core  # noqa: F401
    except ImportError:
        return False
    return True


def _yaml_importable() -> bool:
    """Whether `yaml` (PyYAML) can be imported in the current interpreter."""
    try:
        import yaml  # noqa: F401
    except ImportError:
        return False
    return True


def ensure_core_available(
    project_root: Path, argv: Sequence[str] | None = None
) -> None:
    """Re-exec under `uv run` if fastmcp-pvl-core or PyYAML is not importable.

    copier's ``_tasks`` run before any virtualenv exists for the freshly
    rendered project, so this script cannot assume its dependencies are
    installed. When either import fails, re-exec the whole process under
    ``uv run --no-project`` with the core library and PyYAML pinned ad hoc —
    this must NOT create a persistent virtualenv, since template-ci renders
    the template twice and diffs the results.

    ``_GEN_CONFIG_BOOTSTRAPPED`` guards against re-exec'ing more than once:
    if the dependencies are still missing right after a re-exec, that is a
    real, unrecoverable problem (not something a second re-exec would fix),
    so this raises a clear error instead of looping forever.

    *argv* is the script's own arguments (excluding argv[0]) to preserve
    across the re-exec; defaults to ``sys.argv[1:]``.
    """
    if _core_importable() and _yaml_importable():
        return

    if os.environ.get("_GEN_CONFIG_BOOTSTRAPPED") == "1":
        raise SystemExit(
            "ERROR: fastmcp-pvl-core and/or PyYAML are still not importable "
            "after re-executing under `uv run` — check that `uv` is on PATH "
            "and that both packages are resolvable from this environment."
        )

    floor = _core_floor(project_root)
    script = str(Path(__file__).resolve())
    extra_argv = list(sys.argv[1:] if argv is None else argv)
    args = [
        "uv",
        "run",
        "--no-project",
        "--with",
        f"fastmcp-pvl-core=={floor}",
        "--with",
        "pyyaml",
        "python",
        script,
        *extra_argv,
    ]
    env = dict(os.environ)
    env["_GEN_CONFIG_BOOTSTRAPPED"] = "1"
    try:
        os.execvpe("uv", args, env)
    except OSError as exc:
        raise SystemExit(
            f"ERROR: could not re-exec under `uv run` ({exc}) — install `uv` "
            "(https://docs.astral.sh/uv/) or run this script inside an "
            "environment that already has fastmcp-pvl-core and PyYAML "
            "installed."
        ) from exc


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _project_root() -> Path:
    """The generated project's root — this script lives at <root>/scripts/."""
    return Path(__file__).resolve().parent.parent


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point. Returns 0 on success."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify the generated artifacts are up to date without writing them.",
    )
    args = parser.parse_args(argv)

    project_root = _project_root()
    ensure_core_available(project_root, argv)

    if args.check:
        print(
            "ERROR: --check is not available in this version of the script.",
            file=sys.stderr,
        )
        return 1

    answers = load_answers(project_root)
    variables = collect_vars(project_root, answers)
    print(
        f"Collected {len(variables)} config variables for {answers.get('env_prefix')}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
