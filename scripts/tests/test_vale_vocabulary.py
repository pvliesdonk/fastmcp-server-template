"""The template's Vale vocabulary is layered and honest (#366).

Coverage note: the dead-term check lints the default smoke render only. A
term needed solely by prose that renders in a non-default variant
(authorization off, apps off, plugin off) would be reported dead; keep such
prose free of new vocabulary, or extend the fixture set when it happens.

`Template/accept.txt` is template-owned and re-rendered, so a term the
template's prose needs arrives with that prose.  Every term in it must occur
as a whole word in prose Vale actually spell-checks — the file set and glob
`reusable-ci.yml` (the gate every downstream runs, #538) hands to Vale, with
code spans and fenced blocks removed (Vale skips those) — or it is dead
vocabulary that hides a real spelling hit downstream.  `Base/accept.txt`
ships as an empty seed for project terms; `.vale.ini` stays seeded and
activates both layers.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
TEMPLATE_VOCAB = REPO / ".vale/styles/config/vocabularies/Template/accept.txt.jinja"
BASE_VOCAB = REPO / ".vale/styles/config/vocabularies/Base/accept.txt.jinja"
VALE_INI = REPO / ".vale.ini.jinja"
# Fences may be indented (list items) and the closer may be longer than the
# opener; strip generously — a false strip only makes the check stricter.
_FENCE_RE = re.compile(
    r"^[ \t]*(`{3,}|~{3,})[^\n]*\n.*?^[ \t]*\1`*~*[ \t]*$", re.M | re.S
)
_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
_EXCLUDE_GLOB_RE = re.compile(r"!docs/\{([^}]*)\}/\*\*")


def _terms(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _vale_inputs(rendered: Path) -> tuple[list[str], set[str]]:
    """(files, excluded top-level docs dirs) from reusable-ci.yml's Vale step —
    the gate every downstream runs (#538; the rendered ci.yml is a stub that
    calls it) and the same source template-ci extracts from, so this test
    cannot lint a narrower or wider set than a downstream does."""
    del rendered  # the Vale inputs live in this repo, not the render
    ci = yaml.safe_load(
        (REPO / ".github/workflows/reusable-ci.yml").read_text(encoding="utf-8")
    )
    for job in ci["jobs"].values():
        for step in job.get("steps", []):
            if "vale-action" in str(step.get("uses", "")):
                with_ = step.get("with", {})
                files = json.loads(with_["files"])
                m = _EXCLUDE_GLOB_RE.search(str(with_.get("vale_flags", "")))
                excluded = set(m.group(1).split(",")) if m else set()
                return files, excluded
    raise AssertionError("no vale-action step in reusable-ci.yml")


def _linted_prose(rendered: Path) -> str:
    files, excluded = _vale_inputs(rendered)
    parts: list[str] = []
    for entry in files:
        p = rendered / entry
        candidates = [p] if p.is_file() else sorted(p.rglob("*.md"))
        for md in candidates:
            rel = md.relative_to(rendered).parts
            if rel[0] == "docs" and len(rel) > 2 and rel[1] in excluded:
                continue
            text = md.read_text(encoding="utf-8")
            text = _FENCE_RE.sub(" ", text)
            text = _INLINE_CODE_RE.sub(" ", text)
            parts.append(text)
    return "\n".join(parts)


def _used(term: str, prose: str) -> bool:
    return re.search(rf"(?<![\w-]){re.escape(term)}(?![\w-])", prose, re.I) is not None


def test_template_vocabulary_has_terms_and_base_seed_has_none() -> None:
    assert len(_terms(TEMPLATE_VOCAB)) > 20
    assert _terms(BASE_VOCAB) == [], "project seed must ship without template terms"


def test_every_template_term_is_a_whole_word_in_linted_prose(
    smoke_render: Path,
) -> None:
    prose = _linted_prose(smoke_render)
    unused = [t for t in _terms(TEMPLATE_VOCAB) if not _used(t, prose)]
    assert not unused, (
        "dead template vocabulary — not a whole word in any Vale-linted rendered "
        f"prose outside code: {unused}"
    )


def test_rendered_vale_config_activates_both_layers(smoke_render: Path) -> None:
    ini = (smoke_render / ".vale.ini").read_text(encoding="utf-8")
    assert re.search(r"^Vocab = Base, Template$", ini, re.M)
    assert (
        smoke_render / ".vale/styles/config/vocabularies/Template/accept.txt"
    ).is_file()
    assert (smoke_render / ".vale/styles/config/vocabularies/Base/accept.txt").is_file()


def test_vale_ini_stays_seeded_and_template_vocab_is_rendered() -> None:
    skip = yaml.safe_load((REPO / "copier.yml").read_text(encoding="utf-8"))[
        "_skip_if_exists"
    ]
    assert ".vale.ini" in skip
    assert ".vale/styles/config/vocabularies/Base/accept.txt" in skip
    assert not any("Template/accept.txt" in s for s in skip)
    assert re.search(
        r"^Vocab = Base, Template$", VALE_INI.read_text(encoding="utf-8"), re.M
    )
