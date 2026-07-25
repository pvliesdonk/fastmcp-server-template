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
import dataclasses
import importlib
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
# Domain discovery
# ---------------------------------------------------------------------------


def _load_domain_presentation(
    presentation_root: Path, env_prefix: str
) -> dict[str, Any]:
    """Load `config-presentation.domain.yml`, tolerating its absence.

    Unlike `load_presentation`'s template-owned file (mandatory in every
    render), this one is *seeded* — a downstream project owns and edits it,
    and it is not wired into every render yet. A missing file means
    "nothing manually declared" rather than a configuration error.
    """
    import yaml

    domain_path = presentation_root / "config-presentation.domain.yml"
    if not domain_path.exists():
        return {"vars": []}
    raw = yaml.safe_load(domain_path.read_text(encoding="utf-8")) or {}
    return _substitute_prefix(raw, env_prefix)


def _import_project_config(project_root: Path, python_module: str) -> type | None:
    """Import ``{python_module}.config.ProjectConfig``, or ``None`` if it can't be.

    A freshly rendered project has no dependencies installed yet, and this
    generator's own unit tests use fixture projects with no config module at
    all — both are legitimate "nothing to discover" cases, not errors.

    Only ``sys.path`` is restored before returning. ``sys.modules`` is
    deliberately left alone here: `typing.get_type_hints` (used inside
    `fastmcp_pvl_core.domain_env_suffixes`, which the caller runs against the
    returned class right after this) resolves a class's annotations via
    ``sys.modules[cls.__module__]``, so popping the module before that scan
    runs would turn every annotation lookup into a `NameError`. The caller
    owns popping ``sys.modules`` once it is done using the returned class.
    """
    src_dir = project_root / "src"
    if not src_dir.is_dir():
        return None

    added_to_path = str(src_dir) not in sys.path
    if added_to_path:
        sys.path.insert(0, str(src_dir))
    try:
        module = importlib.import_module(f"{python_module}.config")
        return module.ProjectConfig
    except (ImportError, AttributeError):
        return None
    finally:
        if added_to_path:
            sys.path.remove(str(src_dir))


def _discover_domain_vars(
    project_root: Path, env_prefix: str, answers: Mapping[str, object]
) -> tuple[Var, ...]:
    """Auto-discover domain vars from the project's own ``ProjectConfig``.

    AST-scans ``ProjectConfig.from_env`` via
    ``fastmcp_pvl_core.domain_env_suffixes`` and pulls each field's
    ``help``/``tags`` from its dataclass ``metadata``. This is best-effort
    enrichment, not a required provenance source: a fresh render has no
    domain fields (and often no venv yet to even import its own package),
    so any failure to import or introspect is treated as "nothing to
    discover" rather than an error.

    Every discovered var is tagged ``domain`` (in addition to whatever tags
    its field metadata declares) so it always lands in a file spec's
    ``tags: [domain]`` section regardless of the field author's own tag
    choices.

    ``sys.modules`` entries for the imported module are popped before
    returning, once every use of the class (the `domain_env_suffixes` scan
    and the `dataclasses.fields` walk below) is finished — so repeated calls
    against different fixture projects sharing a module name (as the test
    suite does) never see a stale cached module from an earlier call.
    """
    python_module = answers.get("python_module")
    if not python_module:
        return ()
    python_module = str(python_module)
    project_config_cls = _import_project_config(project_root, python_module)
    if project_config_cls is None:
        return ()

    try:
        from fastmcp_pvl_core import domain_env_suffixes

        try:
            suffixes = domain_env_suffixes(project_config_cls)
        except Exception:
            return ()

        fields_by_suffix = {
            f.name.upper(): f for f in dataclasses.fields(project_config_cls)
        }
        discovered: list[Var] = []
        for suffix in sorted(suffixes):
            field_info = fields_by_suffix.get(suffix)
            metadata = field_info.metadata if field_info is not None else {}
            if field_info is None:
                default = None
            elif field_info.default is not dataclasses.MISSING:
                default = field_info.default
            elif field_info.default_factory is not dataclasses.MISSING:
                default = field_info.default_factory()
            else:
                default = None
            tags = tuple(dict.fromkeys((*metadata.get("tags", ()), "domain")))
            discovered.append(
                Var(
                    name=f"{env_prefix}_{suffix}",
                    suffix=suffix,
                    provenance="domain",
                    type_name=(
                        str(field_info.type) if field_info is not None else "str"
                    ),
                    default=default,
                    help=str(metadata.get("help", "")),
                    tags=tags,
                    inferred=False,
                    wizard=dict(metadata.get("wizard", {})),
                )
            )
        return tuple(discovered)
    finally:
        sys.modules.pop(f"{python_module}.config", None)
        sys.modules.pop(python_module, None)


# ---------------------------------------------------------------------------
# Provenance merge
# ---------------------------------------------------------------------------


def _presentation_root(project_root: Path) -> Path:
    """Where `config-presentation*.yml` live for *project_root*.

    Both presentation files ship byte-identical, so they live at
    *project_root* in a real rendered project. Fall back to the copy
    co-located with this script (the template repo root, when running the
    template's own tests) so callers work against a project_root that only
    has the parts a caller actually needs — e.g. a bare `.copier-answers.yml`
    in unit tests.
    """
    project_root = Path(project_root)
    if (project_root / "config-presentation.yml").exists():
        return project_root
    return _project_root()


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
    presentation_root = _presentation_root(project_root)
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

    domain_presentation = _load_domain_presentation(presentation_root, env_prefix)
    for raw in domain_presentation.get("vars", ()):
        when_answer = raw.get("when_answer")
        if when_answer is not None and not answers.get(when_answer):
            continue
        name = raw["name"]
        suffix = name[len(prefix_marker) :] if name.startswith(prefix_marker) else None
        collected.append(
            Var(
                name=name,
                suffix=suffix,
                provenance=raw.get("provenance", "domain"),
                type_name=raw["type_name"],
                default=raw.get("default"),
                help=raw["help"],
                tags=tuple(raw.get("tags", ())),
                inferred=bool(raw.get("inferred", False)),
                wizard=dict(raw.get("wizard", {})),
            )
        )

    collected.extend(_discover_domain_vars(project_root, env_prefix, answers))

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
# Rendering
# ---------------------------------------------------------------------------


def _format_default(default: object) -> str:
    """Render a var's default as the text after ``=`` in an env file.

    ``None`` and an empty sequence both render as an empty value — an env
    file leaves "no default" blank for the reader to fill in, rather than
    spelling out ``None`` or ``()``. Booleans render lower-case, matching
    shell/env convention.
    """
    if default is None:
        return ""
    if isinstance(default, bool):
        return "true" if default else "false"
    if isinstance(default, (list, tuple)):
        return ",".join(str(item) for item in default)
    return str(default)


def render_env_file(
    spec: Mapping[str, Any], vars_: Sequence[Var], answers: Mapping[str, object]
) -> str:
    """Render one whole-file env artifact's full text.

    ``spec`` is one entry from ``config-presentation.yml``'s ``files``
    mapping (already ``{PREFIX}``-substituted by `load_presentation`).
    ``{HUMAN_NAME}`` / ``{PROJECT_NAME}`` header tokens are substituted here
    from *answers*, since `load_presentation` only replaces ``{PREFIX}``.

    Each section claims the first-declared, not-yet-claimed vars whose tags
    intersect its own — so a var whose tags span multiple sections (e.g. a
    core field tagged both ``server`` and ``apps``) appears exactly once,
    under whichever section is declared first. A section with no matching
    vars (its tags matched nothing, or its ``when_answer`` gate is false)
    emits no header at all — a dangling header with nothing under it would
    fail render-hygiene review and confuse a reader.
    """
    human_name = str(answers.get("human_name", ""))
    project_name = str(answers.get("project_name", ""))

    def _sub(text: str) -> str:
        return text.replace("{HUMAN_NAME}", human_name).replace(
            "{PROJECT_NAME}", project_name
        )

    lines: list[str] = []

    def _blank() -> None:
        if lines and lines[-1] != "":
            lines.append("")

    header = spec.get("header")
    if header:
        for header_line in _sub(str(header)).rstrip("\n").split("\n"):
            lines.append(f"# {header_line}".rstrip())

    commented = bool(spec.get("commented", False))
    value_prefix = "# " if commented else ""
    placed: set[str] = set()

    for section in spec.get("sections", ()):
        when_answer = section.get("when_answer")
        if when_answer is not None and not answers.get(when_answer):
            continue
        section_tags = set(section.get("tags", ()))
        section_vars = [
            v for v in vars_ if v.name not in placed and section_tags & set(v.tags)
        ]
        if not section_vars:
            continue
        placed.update(v.name for v in section_vars)

        _blank()
        title = section.get("title")
        if title is not None:
            lines.append(f"# --- {title} ---")
        note = section.get("note")
        if note is not None:
            lines.append(f"# {_sub(str(note))}".rstrip())

        for var in section_vars:
            for help_line in var.help.splitlines():
                lines.append(f"# {help_line}".rstrip())
            lines.append(f"{value_prefix}{var.name}={_format_default(var.default)}")

    text = "\n".join(lines).rstrip("\n")
    return f"{text}\n" if text else ""


# Whole-file env artifacts this generator writes today. `config-presentation
# .yml` also declares `examples/*.env` (kind: env) and a `wizard-spec.json`
# (kind: wizard) — those are a later task's responsibility, so this list is
# deliberately narrower than "every kind: env file spec".
_ENV_ARTIFACT_PATHS = (".env.example", "packaging/env.example")


def write_artifacts(project_root: Path, *, check: bool) -> list[str]:
    """Render and write (or, with ``check=True``, just compare) the artifacts.

    Returns the relative paths that are missing or whose on-disk content
    differs from the freshly rendered text — with ``check=False`` those are
    the paths actually written; an already-current file is left untouched
    (not even its mtime is bumped) and omitted from the result either way.
    """
    project_root = Path(project_root)
    answers = load_answers(project_root)
    env_prefix = str(answers["env_prefix"])
    presentation = load_presentation(_presentation_root(project_root), env_prefix)
    vars_ = collect_vars(project_root, answers)

    changed: list[str] = []
    for rel_path in _ENV_ARTIFACT_PATHS:
        spec = presentation["files"][rel_path]
        text = render_env_file(spec, vars_, answers)
        target = project_root / rel_path
        current = target.read_text(encoding="utf-8") if target.exists() else None
        if current == text:
            continue
        changed.append(rel_path)
        if not check:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
    return changed


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
