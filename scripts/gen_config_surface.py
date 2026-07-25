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
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
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
    example: str | None = None  # shown as the value when `default` is null


# Rank order for the provenance merge; vars are ordered by this rank first,
# then by declaration order within each provenance.
_PROVENANCE_ORDER = ("core", "template", "external", "domain")

_CORE_FLOOR_RE = re.compile(r"fastmcp-pvl-core\s*>=\s*([0-9]+\.[0-9]+\.[0-9]+)")


def _clean_help(help_text: str) -> str:
    """Strip RST inline-literal markup (````word````) down to a single backtick.

    Core's help text is RST-flavoured prose; a double-backtick reads as noise
    in a plain-text env file comment. Applied once, here, at the point every
    Var's ``help`` is set — so every consumer (both env files here and
    whatever Task 3's wizard spec does with ``var.help``) inherits already-
    clean text instead of each needing to remember to clean it again.
    """
    return help_text.replace("``", "`")


def _require_env_prefix(answers: Mapping[str, object]) -> str:
    """Return ``answers["env_prefix"]``, or raise the same `SystemExit` every caller expects.

    Both `collect_vars` and `write_artifacts` need this value before they can
    do anything else; sharing one guard means a malformed answers file always
    fails the same deliberate way, never with a bare `KeyError` from whichever
    caller forgot to check first.
    """
    if "env_prefix" not in answers:
        raise SystemExit(
            "ERROR: 'env_prefix' missing from .copier-answers.yml — a project "
            "rendered by this template always answers that question."
        )
    return str(answers["env_prefix"])


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
    all — both are legitimate "nothing to discover" cases, not errors. Any
    exception raised while resolving it — the module doesn't exist, it lacks
    a ``ProjectConfig`` attribute, or its own top level raises (a missing env
    var, a broken third-party import, a mid-edit ``SyntaxError``) — is
    treated the same way, since domain discovery is best-effort enrichment
    that must never turn an unrelated project's problem into a hard failure
    of this generator.

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
    except Exception:
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
    domain fields (and often no venv yet to even import its own package), so
    a failure to *import* the project's config module is silently treated as
    "nothing to discover". A failure *during the scan itself* (the module
    imported fine but `domain_env_suffixes` couldn't resolve it — e.g. a type
    hint referencing something not importable at module scope) is not
    swallowed silently: `domain_env_suffixes`'s own contract is that such a
    failure must propagate rather than yield a silently-incomplete set, so
    this prints a warning naming the exception and returns no domain vars,
    rather than letting `--check` (Task 4) report "up to date" while every
    domain var is actually missing.

    Every discovered var is tagged ``domain`` (in addition to whatever tags
    its field metadata declares) so it always lands in a file spec's
    ``tags: [domain]`` section regardless of the field author's own tag
    choices. Declaration order is contractual for every other provenance;
    suffixes with a matching dataclass field are ordered the same way the
    field is declared, and any suffix `domain_env_suffixes` found with no
    matching field (e.g. read directly rather than through a field) is
    appended afterwards, sorted, so the whole result stays deterministic.

    Every ``sys.modules`` entry gained while importing and introspecting the
    project's config module — including any side-effect submodules it pulls
    in along the way — is removed before returning, once every use of the
    class (the `domain_env_suffixes` scan and the `dataclasses.fields` walk)
    is finished. That cleanup runs on every exit path, including the early
    returns above, so a later call against a different project that happens
    to share the same module name never resolves against a stale cached
    package from an earlier call in the same process.
    """
    python_module = answers.get("python_module")
    if not python_module:
        return ()
    python_module = str(python_module)

    modules_before = frozenset(sys.modules)
    try:
        project_config_cls = _import_project_config(project_root, python_module)
        if project_config_cls is None:
            return ()

        from fastmcp_pvl_core import domain_env_suffixes

        try:
            suffixes = domain_env_suffixes(project_config_cls)
        except Exception as exc:
            print(
                f"WARNING: domain env-var discovery failed for "
                f"{python_module}.config: {exc.__class__.__name__}: {exc}",
                file=sys.stderr,
            )
            return ()

        fields = dataclasses.fields(project_config_cls)
        fields_by_suffix = {f.name.upper(): f for f in fields}
        ordered_suffixes = [
            f.name.upper() for f in fields if f.name.upper() in suffixes
        ]
        ordered_suffixes.extend(sorted(suffixes.difference(ordered_suffixes)))

        discovered: list[Var] = []
        for suffix in ordered_suffixes:
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
                    help=_clean_help(str(metadata.get("help", ""))),
                    tags=tags,
                    inferred=False,
                    wizard=dict(metadata.get("wizard", {})),
                )
            )
        return tuple(discovered)
    finally:
        for name in set(sys.modules) - modules_before:
            del sys.modules[name]


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
    env_prefix = _require_env_prefix(answers)
    presentation_root = _presentation_root(project_root)
    presentation = load_presentation(presentation_root, env_prefix)

    collected: list[Var] = [
        Var(
            name=f"{env_prefix}_{field.suffix}",
            suffix=field.suffix,
            provenance="core",
            type_name=field.type_name,
            default=field.default,
            help=_clean_help(field.help),
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
                help=_clean_help(raw["help"]),
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
                help=_clean_help(raw["help"]),
                tags=tuple(raw.get("tags", ())),
                inferred=bool(raw.get("inferred", False)),
                wizard=dict(raw.get("wizard", {})),
            )
        )

    collected.extend(_discover_domain_vars(project_root, env_prefix, answers))

    # Placeholder examples for vars whose real `default` is null — keyed by
    # full var name so a core var (whose help/tags/default this template does
    # not own) can still get one, without redeclaring the whole var.
    examples_map: dict[str, str] = presentation.get("examples", {}) or {}
    if examples_map:
        collected = [
            dataclasses.replace(v, example=examples_map[v.name])
            if v.name in examples_map
            else v
            for v in collected
        ]

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

    ``set``/``frozenset`` are sorted before joining: unlike ``list``/``tuple``
    (whose declared order is meaningful and preserved as-is), a set's
    iteration order is not stable across processes, and template-ci renders
    the template twice and diffs the results — an unsorted join would make
    that diff flaky. A ``dict`` default has no defined env-file rendering, so
    it is rejected loudly rather than silently rendered as whatever
    ``str()``/``repr()`` would print (also order-unstable, pre-3.7 dict
    ordering guarantees aside — the point is there is no *sensible* rendering,
    not just an unstable one).
    """
    if default is None:
        return ""
    if isinstance(default, bool):
        return "true" if default else "false"
    if isinstance(default, dict):
        raise SystemExit(
            f"ERROR: a var default of type dict ({default!r}) has no defined "
            "env-file rendering — give it a scalar or sequence default, or "
            "an `example` string, instead."
        )
    if isinstance(default, (set, frozenset)):
        return ",".join(sorted(str(item) for item in default))
    if isinstance(default, (list, tuple)):
        return ",".join(str(item) for item in default)
    return str(default)


def _format_value(var: Var, sub: Callable[[str], str]) -> str:
    """The text after ``=`` for one var: its real default, else its example.

    A ``None`` default (no real default at all) falls back to `var.example`
    — a presentation-declared placeholder shown so a reader knows the
    expected *shape* of the value (a JSON blob, a file path, a URL), not just
    that the field exists. A real default, even a falsy one (``False``,
    ``0``, an empty sequence), always wins over an example: only "no default
    at all" is ambiguous enough to need one. *sub* applies the same
    ``{HUMAN_NAME}``/``{PROJECT_NAME}`` substitution the header and section
    notes get, since an example like ``/etc/{PROJECT_NAME}/tokens.toml`` is
    only useful once ``{PROJECT_NAME}`` is a real project name.
    """
    if var.default is not None:
        return _format_default(var.default)
    if var.example:
        return sub(var.example)
    return ""


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
    under whichever section is declared first. A section gated off by a
    false ``when_answer``, or with no matching vars *and* no ``note``, emits
    nothing at all — a dangling header with nothing under it would fail
    render-hygiene review and confuse a reader. A section with a ``note`` but
    no matching vars still emits its header and note: that is a deliberate
    signpost (e.g. "domain vars are discovered from your ProjectConfig") that
    must survive even when the project using it happens to have none yet —
    otherwise a project with no domain fields gives its reader no hint that
    domain vars exist as a concept at all. A section's own ``exclude`` list
    (full var names) drops specific vars even though their tags match — used
    when a var's tag-based inclusion would be actively wrong for one
    artifact (e.g. `examples/bearer-auth.env` excludes `BEARER_TOKENS_FILE`,
    since shipping both it and `BEARER_TOKEN` together makes core prefer the
    non-existent tokens file and refuse to start).
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
        excluded = set(section.get("exclude", ()))
        section_vars = [
            v
            for v in vars_
            if v.name not in placed
            and v.name not in excluded
            and section_tags & set(v.tags)
        ]
        note = section.get("note")
        if not section_vars and note is None:
            continue
        placed.update(v.name for v in section_vars)

        _blank()
        title = section.get("title")
        if title is not None:
            lines.append(f"# --- {title} ---")
        if note is not None:
            for note_line in _sub(str(note)).rstrip("\n").split("\n"):
                lines.append(f"# {note_line}".rstrip())

        for var in section_vars:
            for help_line in var.help.splitlines():
                lines.append(f"# {help_line}".rstrip())
            lines.append(f"{value_prefix}{var.name}={_format_value(var, _sub)}")

    text = "\n".join(lines).rstrip("\n")
    return f"{text}\n" if text else ""


# `when: <token>` wizard hints (a var's own `wizard` mapping, and a
# `wizard_routing` entry's top-level `when`) expand to the same two-
# dimensional `showIf` the schema expects — `server` alone gates on the
# routing "deployment" choice; `oidc`/`bearer` additionally gate on the
# routing "auth" choice, since OIDC/bearer-specific vars only make sense once
# both a server deployment *and* that auth mode are selected.
_WIZARD_SHOW_IF: dict[str, dict[str, list[str]]] = {
    "server": {"deployment": ["server"]},
    "oidc": {"deployment": ["server"], "auth": ["oidc", "both"]},
    "bearer": {"deployment": ["server"], "auth": ["bearer", "both"]},
}

# The full vocabulary a `Var.wizard` hint mapping is allowed to use.
# `_validate_wizard_hint` rejects anything outside this — an unrecognised key
# or value used to be silently ignored (`_wizard_show_if` returned `None` for
# an unknown `when`, and only `control: emit` was ever checked), which let a
# typo silently promote a var to a primary, always-visible wizard question
# instead of failing loudly.
_KNOWN_WIZARD_HINT_KEYS = frozenset({"group", "when", "secret", "control"})
# `emit`: a `wizard_routing` option already emits this var (no question of
# its own). `none`: documented in the env artifacts, no wizard control at
# all — the parallel of `emit` for a var nothing routes for (e.g. a
# development-only var). Neither implies `inferred`, which means something
# different: "this value is derived from other settings", not "unrouted".
_KNOWN_WIZARD_CONTROL_VALUES = frozenset({"emit", "none"})

_TYPE_NAME_CLASS_RE = re.compile(r"<class '(?:[\w.]+\.)?(\w+)'>$")
_QUESTION_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def _wizard_show_if(when: object, *, source: str) -> dict[str, list[str]] | None:
    """Map a scalar ``when`` hint to the spec's `showIf`.

    Returns ``None`` for no hint at all (``when`` is falsy). Raises loudly
    for a non-empty ``when`` that doesn't match a known token — *source*
    names the offending var or `wizard_routing` question in the message, so
    a typo (e.g. ``when: servr``) fails the generation run instead of
    silently rendering as if `when` had never been set (which would make the
    var/question a primary, always-visible one — never the intended
    behaviour for a hint author who bothered to write a `when` at all).
    """
    if not when:
        return None
    token = str(when)
    show_if = _WIZARD_SHOW_IF.get(token)
    if show_if is None:
        raise SystemExit(
            f"ERROR: {source} has unknown wizard 'when' token {token!r} — "
            f"known tokens are {sorted(_WIZARD_SHOW_IF)!r}."
        )
    return show_if


def _validate_wizard_hint(var: Var) -> None:
    """Reject any `Var.wizard` hint outside the known vocabulary, loudly.

    Checked once per var, regardless of whether that var ends up producing a
    question — a bad hint on an `inferred`/`control`-skipped var is still a
    bug in `config-presentation.yml` worth catching, not just a bug in
    whichever var happens to reach the wizard. Mirrors this file's existing
    loud-failure style (`_format_default`'s dict rejection, `collect_vars`'s
    duplicate-name guard).
    """
    unknown_keys = set(var.wizard) - _KNOWN_WIZARD_HINT_KEYS
    if unknown_keys:
        raise SystemExit(
            f"ERROR: {var.name} has unknown wizard hint key(s) "
            f"{sorted(unknown_keys)!r} — known keys are "
            f"{sorted(_KNOWN_WIZARD_HINT_KEYS)!r}."
        )
    _wizard_show_if(var.wizard.get("when"), source=var.name)
    control = var.wizard.get("control")
    if control is not None and control not in _KNOWN_WIZARD_CONTROL_VALUES:
        raise SystemExit(
            f"ERROR: {var.name} has unknown wizard 'control' value "
            f"{control!r} — known values are "
            f"{sorted(_KNOWN_WIZARD_CONTROL_VALUES)!r}."
        )


def _wizard_question_type(type_name: str) -> str:
    """Normalise a `Var.type_name` down to one of the spec's four question types.

    `type_name` is annotation-form dependent: a core/template field (declared
    under ``from __future__ import annotations``) carries the literal
    annotation string (``"str | None"``, ``"Path"``), but a domain field
    discovered from a project *without* that import carries
    ``repr(field.type)`` instead (``"<class 'pathlib.Path'>"``). Both forms
    are reduced to their base token before matching, rather than matching
    either exact string — a union (``"str | None"``) or generic
    (``"tuple[str, ...]"``) is reduced to its first/outer name the same way.
    Anything that isn't recognisably ``bool``/``int``/``float`` renders as a
    plain text question — including `Path`, which has no dedicated wizard
    control in this spec.
    """
    match = _TYPE_NAME_CLASS_RE.match(type_name)
    normalized = match.group(1) if match else type_name
    normalized = normalized.split("|", 1)[0].split("[", 1)[0].strip()
    base = normalized.lower()
    if base == "bool":
        return "bool"
    if base in ("int", "float"):
        return "number"
    return "text"


def _wizard_label(var: Var) -> str:
    """A human-readable label derived from the var's suffix (full name if unprefixed)."""
    token = var.suffix or var.name
    return token.replace("_", " ").title()


def _routing_question(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Render one already-`{PREFIX}`-substituted `wizard_routing` entry as a question."""
    question: dict[str, Any] = {"id": raw["id"], "label": raw["label"]}
    help_text = raw.get("help")
    if help_text:
        question["help"] = help_text
    question["type"] = raw["type"]
    show_if = _wizard_show_if(raw.get("when"), source=f"wizard_routing[{raw['id']!r}]")
    if show_if is not None:
        question["showIf"] = show_if
    options = raw.get("options")
    if options:
        rendered_options: list[dict[str, Any]] = []
        for option in options:
            rendered: dict[str, Any] = {
                "value": option["value"],
                "label": option["label"],
            }
            emit = option.get("emit")
            if emit:
                rendered["emit"] = dict(emit)
            rendered_options.append(rendered)
        question["options"] = rendered_options
    return question


def _var_question(
    var: Var, labels: Mapping[str, str], help_overrides: Mapping[str, str]
) -> dict[str, Any] | None:
    """Render one `Var`'s wizard hint as a question, or ``None`` to emit nothing.

    ``inferred=True`` means "no wizard control offered" — the var still
    appears in the env artifacts (`collect_vars`/`render_env_file` never
    filter on it), only the wizard spec skips it. A `control: emit` hint
    (``TRANSPORT``) means a `wizard_routing` option already emits the var as
    a side effect of the routing choice — a second, independent question for
    it would let a user pick a value that contradicts that routing choice.
    A `control: none` hint (``DEBUG_PORT``, ``DEBUG_WAIT``) means the var is
    documented in the env artifacts but has no wizard-appropriate control at
    all — unlike `inferred`, nothing about its value is derived from another
    setting; it is just out of scope for the wizard.

    *labels*/*help_overrides* are the `wizard_labels`/`wizard_help` override
    maps from `config-presentation.yml`, keyed by full var name — checked
    before falling back to `_wizard_label`/`var.help`, since the mechanical
    fallbacks read as env-file prose (`"Oidc Client Id"`) or carry markup
    and paragraph-length text the wizard UI renders verbatim and unstyled.
    """
    _validate_wizard_hint(var)
    if var.inferred:
        return None
    if var.wizard.get("control") in ("emit", "none"):
        return None

    question: dict[str, Any] = {
        "id": (var.suffix or var.name).lower(),
        "label": labels.get(var.name, _wizard_label(var)),
        "type": _wizard_question_type(var.type_name),
        "var": var.name,
    }
    help_text = help_overrides.get(var.name, var.help)
    if help_text:
        question["help"] = help_text
    group = var.wizard.get("group")
    if group:
        question["advancedGroup"] = str(group)
    show_if = _wizard_show_if(var.wizard.get("when"), source=var.name)
    if show_if is not None:
        question["showIf"] = show_if
    return question


def _register_question_id(question_id: str, seen: dict[str, str], source: str) -> None:
    """Reserve *question_id* for *source*, raising loudly on a collision or a bad shape.

    `wizard.js` keys all wizard state by `answers[question.id]`, so two
    questions sharing an id — e.g. a domain field literally named ``auth`` or
    ``deployment`` colliding with a `wizard_routing` id — would silently
    corrupt every `showIf` evaluation rather than raise. Also rejects an id
    that doesn't match the schema's own `^[a-z][a-z0-9_]*$` (e.g. a
    dataclass field with a leading underscore), since that would fail
    schema validation with a far less useful error message.
    """
    if not _QUESTION_ID_RE.match(question_id):
        raise SystemExit(
            f"ERROR: {source} produced an invalid wizard question id "
            f"{question_id!r} — must match ^[a-z][a-z0-9_]*$."
        )
    prior = seen.get(question_id)
    if prior is not None:
        raise SystemExit(
            f"ERROR: duplicate wizard question id {question_id!r} — produced "
            f"by both {prior} and {source}. Every question id must be unique."
        )
    seen[question_id] = source


def _wizard_guard(raw: Mapping[str, Any], index: int) -> dict[str, Any]:
    """Render one `wizard_guards` entry, rejecting a non-list `when` value.

    ``list(scalar_string)`` silently explodes a scalar into one list entry
    per character (`when: {deployment: server}` → `["s", "e", ...]`) instead
    of raising — a guard's `when` must already be a list in YAML (e.g.
    `[server]`), so this checks that rather than coercing.
    """
    when_raw = raw["when"]
    when: dict[str, list[str]] = {}
    for key, value in when_raw.items():
        if not isinstance(value, list):
            raise SystemExit(
                f"ERROR: wizard_guards[{index}] has a non-list 'when[{key!r}]' "
                f"value {value!r} — expected a list of strings, e.g. [server]."
            )
        when[key] = list(value)
    return {"level": raw["level"], "message": raw["message"], "when": when}


def render_wizard_spec(
    pres: Mapping[str, Any], vars_: Sequence[Var], answers: Mapping[str, object]
) -> str:
    """Render the config-wizard spec (`docs/javascripts/config-wizard/wizard-spec.json`).

    ``pres`` is the loaded, already `{PREFIX}`-substituted
    `config-presentation.yml` (the same value `write_artifacts` already loads
    for the env artifacts) — its ``wizard_routing``, ``wizard_guards``,
    ``wizard_labels``, and ``wizard_help`` keys drive the questions, guards,
    and label/help overrides; ``examples`` is not used here (it feeds
    env-file value rendering only, via `_format_value`).

    ``secretKeys`` is derived from the *emitted questions*, not from
    `vars_` independently — a secret var that later gains `inferred`,
    `control: emit`, or `control: none` (and so stops producing a question)
    must drop out of `secretKeys` too, rather than leaving the rendered
    project's own schema-conformance check (`secretKeys` must be a subset of
    every question's ``var``) to fail downstream instead of this generator
    catching it.

    Key order within every emitted object is fixed by this function's own
    dict-literal construction, never by iterating a `set`/`frozenset` or by
    passing through whatever order an external mapping happened to iterate
    in — `template-ci` renders the template twice and diffs the results, so
    the JSON text must be byte-identical across processes regardless of
    `PYTHONHASHSEED`.
    """
    project_name = str(answers.get("project_name", ""))
    docker_registry = str(answers.get("docker_registry", ""))
    env_prefix = str(answers.get("env_prefix", ""))
    labels: Mapping[str, str] = pres.get("wizard_labels") or {}
    help_overrides: Mapping[str, str] = pres.get("wizard_help") or {}

    seen_ids: dict[str, str] = {}
    questions: list[dict[str, Any]] = []
    for raw in pres.get("wizard_routing", ()):
        question = _routing_question(raw)
        _register_question_id(
            question["id"], seen_ids, f"wizard_routing[{raw['id']!r}]"
        )
        questions.append(question)
    for var in vars_:
        var_question = _var_question(var, labels, help_overrides)
        if var_question is not None:
            _register_question_id(var_question["id"], seen_ids, var.name)
            questions.append(var_question)

    question_vars = {q["var"] for q in questions if "var" in q}
    secret_keys = [
        var.name
        for var in vars_
        if var.wizard.get("secret") and var.name in question_vars
    ]

    guards = [
        _wizard_guard(raw, index)
        for index, raw in enumerate(pres.get("wizard_guards", ()))
    ]

    spec = {
        "version": 1,
        "meta": {
            "projectName": project_name,
            "dockerImage": f"{docker_registry}/{project_name}:latest",
            "envPrefix": env_prefix,
        },
        "secretKeys": secret_keys,
        "questions": questions,
        "guards": guards,
    }
    text = json.dumps(spec, indent=2, ensure_ascii=False)
    return f"{text}\n"


# `kind` -> renderer, dispatched per `config-presentation.yml` `files` entry.
# `env` renderers take that entry's own file spec; `wizard` takes the whole
# presentation (it has no per-file content of its own — see `files:` in
# `config-presentation.yml`, where `docs/javascripts/config-wizard/wizard-
# spec.json` declares only `kind: wizard` and nothing else).
_ENV_KIND = "env"
_WIZARD_KIND = "wizard"
_KNOWN_FILE_KINDS = frozenset({_ENV_KIND, _WIZARD_KIND})


def write_artifacts(project_root: Path, *, check: bool) -> list[str]:
    """Render and write (or, with ``check=True``, just compare) the artifacts.

    Every artifact this generator produces is driven off `config-
    presentation.yml`'s ``files`` mapping — adding or removing a `files:`
    entry there changes what gets generated, with no second list to keep in
    sync (YAML mapping order is insertion order, so iterating ``files``
    directly is as deterministic as the fixed tuple it replaces). An
    unrecognised ``kind`` fails loudly instead of either silently producing
    nothing or raising a bare `KeyError`.

    Returns the relative paths that are missing or whose on-disk content
    differs from the freshly rendered text — with ``check=False`` those are
    the paths actually written; an already-current file is left untouched
    (not even its mtime is bumped) and omitted from the result either way.
    """
    project_root = Path(project_root)
    answers = load_answers(project_root)
    env_prefix = _require_env_prefix(answers)
    presentation = load_presentation(_presentation_root(project_root), env_prefix)
    vars_ = collect_vars(project_root, answers)

    artifacts: list[tuple[str, str]] = []
    for rel_path, file_spec in presentation.get("files", {}).items():
        kind = file_spec.get("kind")
        if kind == _ENV_KIND:
            text = render_env_file(file_spec, vars_, answers)
        elif kind == _WIZARD_KIND:
            text = render_wizard_spec(presentation, vars_, answers)
        else:
            raise SystemExit(
                f"ERROR: config-presentation.yml files[{rel_path!r}] has "
                f"unknown kind {kind!r} — expected one of "
                f"{sorted(_KNOWN_FILE_KINDS)!r}."
            )
        artifacts.append((rel_path, text))

    changed: list[str] = []
    for rel_path, text in artifacts:
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
    """Entry point. Returns 0 on success.

    Without ``--check``, renders and writes every artifact `write_artifacts`
    knows about, then reports which paths were written (nothing, if they
    were already current). With ``--check``, compares only — nothing is ever
    written on this path — and returns 1 if any artifact is missing or
    stale, after printing each such path to stderr with a pointer to the
    command that fixes it; this is what a copier ``_tasks`` entry and CI both
    rely on to fail loudly instead of silently shipping stale files.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify the generated artifacts are up to date without writing them.",
    )
    args = parser.parse_args(argv)

    project_root = _project_root()
    ensure_core_available(project_root, argv)

    answers = load_answers(project_root)
    variables = collect_vars(project_root, answers)
    print(
        f"Collected {len(variables)} config variables for {answers.get('env_prefix')}."
    )

    if args.check:
        stale = write_artifacts(project_root, check=True)
        if not stale:
            return 0
        for path in stale:
            print(
                f"STALE: {path} is missing or out of date — run: "
                "python scripts/gen_config_surface.py",
                file=sys.stderr,
            )
        return 1

    written = write_artifacts(project_root, check=False)
    if written:
        for path in written:
            print(f"Wrote {path}.")
    else:
        print("All config artifacts already up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
