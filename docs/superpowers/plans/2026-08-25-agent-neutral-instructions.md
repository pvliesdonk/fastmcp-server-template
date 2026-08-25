# Agent-Neutral Instruction Surface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 48k-char Claude-only `CLAUDE.md` with a ≤24k `AGENTS.md` core, a 3-line `CLAUDE.md` stub, and five portable skills under `.agents/skills/` that Claude Code reaches through `.claude/skills/` symlinks — migrated automatically on `copier update`.

**Architecture:** `AGENTS.md.jinja` is a rename of `CLAUDE.md.jinja` keeping every sentinel; task-shaped sections move verbatim into `.agents/skills/<name>/SKILL.md.jinja`; `copier.yml` gains `_preserve_symlinks: true` and a `_migrations` script that splices a downstream's DOMAIN blocks from `HEAD:CLAUDE.md` into `AGENTS.md`. Guards live in `template-ci.yml` (size, sentinels, scrub anchors), `scripts/tests/` (symlinks, frontmatter, migration), and a rendered `tests/test_agent_instructions.py`.

**Tech Stack:** copier 9.17.2 (`_preserve_symlinks`, `_migrations`), Jinja, pytest, bash in GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-25-agent-neutral-instructions-design.md`

## Global Constraints

- Smoke render `AGENTS.md` ≤ 24 000 characters; rendered projects assert `AGENTS.md` ≤ 40 000.
- Every template-owned `.agents/skills/<name>` has `.claude/skills/<name>` as a **relative** symlink `../../.agents/skills/<name>`; nothing under `.claude/skills/` is a real directory.
- Skill frontmatter: `name` equals its directory; `description` non-empty.
- Content moves verbatim first (Task 2), trims in Task 4 — never both in one commit.
- Every commit: `python3 scripts/check_render_hygiene.py` on a fresh render is clean; `uv run pytest scripts/tests -q` passes; rendered gate (`ruff`, `mypy`, `pytest`) passes.
- Render command (always from a **commit**, copier ignores the working tree):
  ```bash
  rm -rf /tmp/smoke && uv run --no-project --with copier copier copy --trust --defaults \
    --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
  ```
- `UPGRADING.md` notes go under `## Unreleased` only (`python3 scripts/promote_upgrading.py --check`).
- The template repo's own maintainer `CLAUDE.md` (plain file, not rendered) stays; only its wording changes.
- Work on branch `feat/agent-neutral-instructions` from `origin/main`.

---

### Task 1: `AGENTS.md.jinja` replaces `CLAUDE.md.jinja`; stub `CLAUDE.md`; repoint every reader

**Files:**
- Rename: `CLAUDE.md.jinja` → `AGENTS.md.jinja` (git mv, no content change)
- Create: `CLAUDE.md.jinja` (stub)
- Modify: `.github/workflows/template-ci.yml` (lines 89, 91, 279–303, 1225–1395 — every `CLAUDE.md` inside the smoke/detach steps; **not** lines 1036–1049, which grep this repo's own maintainer `CLAUDE.md`)
- Modify: `FORKING.md.jinja:53-84`, `README.md.jinja:147,191`, `CONTRIBUTING.md:108,125,141`, `.vale.ini.jinja:9`, `copier.yml:146,220,237,256-258` (comments), `.agents/skills/writing-release-notes/SKILL.md:240`
- Modify: `tests/test_commit_conventions.py.jinja:30`, `tests/{% if enable_structural_gate %}test_structural_gate.py{% endif %}.jinja:224,242`, `tests/test_release_flow_contract.py.jinja:1349`, `scripts/tests/test_claude_review_gating.py:72,84`
- Modify: `CLAUDE.md` (this repo's maintainer doc, lines 5–6, 25, 108–124, 187–189)

**Interfaces:**
- Produces: rendered `AGENTS.md` with the identical sentinel structure CLAUDE.md had (3 DOMAIN pairs, 3 TEMPLATE-TRACKING pairs, 2 TEMPLATE-OWNED fences); rendered `CLAUDE.md` equal to `STUB` below. Later tasks and the migration script depend on this exact stub text.

- [ ] **Step 1: Branch and rename**

```bash
git fetch origin && git checkout -b feat/agent-neutral-instructions origin/main
git mv CLAUDE.md.jinja AGENTS.md.jinja
```

- [ ] **Step 2: Write the stub `CLAUDE.md.jinja`** (exact bytes; the migration script and tests compare against them)

```markdown
@AGENTS.md

Project instructions live in `AGENTS.md` (domain content between its `DOMAIN-START` / `DOMAIN-END` markers). This file is template-owned; do not add content here.
```

File ends with a single newline after the sentence (no trailing blank line — render hygiene).

- [ ] **Step 3: Repoint the smoke-render checks in `template-ci.yml`**

Replace `CLAUDE.md` with `AGENTS.md` in: lines 89 and 91 (gate-off render), the whole `CLAUDE.md sentinel structure` step (rename the step to `AGENTS.md sentinel structure`), and the detach-smoke step (1225–1395: `count_occurrences`, the `sed -i.bak ... CLAUDE.md && rm -f CLAUDE.md.bak`, every `grep ... CLAUDE.md` assertion, and the comment text). Do it mechanically:

```bash
python3 - <<'EOF'
from pathlib import Path
p = Path(".github/workflows/template-ci.yml"); lines = p.read_text().splitlines(keepends=True)
for i, line in enumerate(lines):
    n = i + 1
    if (88 <= n <= 92) or (279 <= n <= 303) or (1225 <= n <= 1395):
        lines[i] = line.replace("CLAUDE.md", "AGENTS.md")
p.write_text("".join(lines))
EOF
grep -n 'CLAUDE.md' .github/workflows/template-ci.yml
```

Expected remaining matches: only the Vale block (≈1036–1049, this repo's own file) and comments at ≈1543/1597. Fix the `AGENTS.md.jinja is reworded` comment wording the script produced (it reads naturally).

- [ ] **Step 4: Repoint the other readers**

```bash
sed -i 's/`CLAUDE\.md`/`AGENTS.md`/g; s/CLAUDE\.md && rm -f CLAUDE\.md\.bak/AGENTS.md \&\& rm -f AGENTS.md.bak/; s/from `CLAUDE\.md`/from `AGENTS.md`/' FORKING.md.jinja
sed -i 's/in this README and in `CLAUDE\.md`/in this README and in `AGENTS.md`/; s|\[`CLAUDE\.md`\](CLAUDE\.md)|[`AGENTS.md`](AGENTS.md)|' README.md.jinja
sed -i 's/policy in `CLAUDE\.md`/policy in `AGENTS.md`/; s/release model in `CLAUDE\.md`/release model in `AGENTS.md`/; s/`CLAUDE\.md` sections/`AGENTS.md` sections/' CONTRIBUTING.md
sed -i 's/section in CLAUDE\.md/section in AGENTS.md/' .vale.ini.jinja
sed -i 's/policy in `CLAUDE\.md`/policy in `AGENTS.md`/' .agents/skills/writing-release-notes/SKILL.md
sed -i 's|REPO_ROOT / "CLAUDE.md"|REPO_ROOT / "AGENTS.md"|g; s/`CLAUDE\.md`/`AGENTS.md`/g; s/CLAUDE\.md/AGENTS.md/g' tests/test_commit_conventions.py.jinja 'tests/{% if enable_structural_gate %}test_structural_gate.py{% endif %}.jinja'
sed -i 's/`CLAUDE\.md`'"'"'s "Manifest version lockstep"/`AGENTS.md`'"'"'s "Manifest version lockstep"/' tests/test_release_flow_contract.py.jinja
sed -i 's|/ "CLAUDE.md")|/ "AGENTS.md")|g' scripts/tests/test_claude_review_gating.py
```

Then hand-edit: `FORKING.md.jinja:84` sentence `If your fork added its own .claude/CLAUDE.md, apply the same scrub there.` stays as is (it is about a fork's Claude-local file). In `copier.yml` comments (146, 220, 237, 256–258) replace `CLAUDE.md` with `AGENTS.md` and `CLAUDE.md.jinja` with `AGENTS.md.jinja`. In this repo's maintainer `CLAUDE.md`: line 5–6 → "Generated projects get their own `AGENTS.md` rendered from `AGENTS.md.jinja` (plus a stub `CLAUDE.md` that imports it)"; line 25 and 108–124, 187–189 → `AGENTS.md.jinja` / rendered `AGENTS.md`.

- [ ] **Step 5: Commit, render, verify**

```bash
git add -A && git commit -q -m "refactor(agents): rename CLAUDE.md.jinja to AGENTS.md.jinja and stub CLAUDE.md

Refs #484 #485"
rm -rf /tmp/smoke && uv run --no-project --with copier copier copy --trust --defaults --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
python3 scripts/check_render_hygiene.py /tmp/smoke
diff <(printf '@AGENTS.md\n\nProject instructions live in `AGENTS.md` (domain content between its `DOMAIN-START` / `DOMAIN-END` markers). This file is template-owned; do not add content here.\n') /tmp/smoke/CLAUDE.md && echo STUB OK
grep -cE '^<!-- DOMAIN-START -->$' /tmp/smoke/AGENTS.md   # expect 3
grep -cE '^<!-- TEMPLATE-TRACKING-START -->$' /tmp/smoke/AGENTS.md   # expect 3
cd /tmp/smoke && uv sync --all-extras --all-groups -q && uv run ruff check . && uv run mypy src/ tests/ && uv run pytest -x -q
cd - && uv run pytest -q scripts/tests
```

Expected: hygiene OK, `STUB OK`, 3 / 3, rendered gate green, scripts tests green.

- [ ] **Step 6: Run the detach-smoke scrub locally against the render** (the CI step is long; reproduce its core to catch a missed `CLAUDE.md`)

```bash
cd /tmp/smoke && sed -i.bak -e '/<!-- TEMPLATE-TRACKING-START -->/,/<!-- TEMPLATE-TRACKING-END -->/d' AGENTS.md && rm AGENTS.md.bak
! grep -niF 'copier update' AGENTS.md | grep -v 'Kept across\|preserved across\|survive `copier update`\|re-verified by' ; cd -
```

Expected: no output from the final grep (the substitutions are exercised by CI; this only proves the range-delete anchors moved with the file).

- [ ] **Step 7: Amend if anything was missed, then push**

```bash
git push -u origin feat/agent-neutral-instructions
```

---

### Task 2: Move task-shaped sections into portable skills; symlinks; `_preserve_symlinks`

**Files:**
- Create: `.agents/skills/releasing/SKILL.md.jinja`, `.agents/skills/config-contract/SKILL.md.jinja`, `.agents/skills/logging-standard/SKILL.md.jinja`, `.agents/skills/tool-registration/SKILL.md.jinja`, `.agents/skills/repository-protection/SKILL.md.jinja`
- Rename: `.claude/skills/authoring-issues-prs/` → `.agents/skills/authoring-issues-prs/` (git mv)
- Create symlinks: `.claude/skills/{releasing,config-contract,logging-standard,tool-registration,repository-protection,authoring-issues-prs,writing-release-notes}` → `../../.agents/skills/<name>`
- Modify: `AGENTS.md.jinja` (remove moved sections), `copier.yml` (`_preserve_symlinks: true`, `_skip_if_exists` comment at lines 76–78), `.gitignore.jinja:49-52` and `.gitignore:27-30` (comment), `CONTRIBUTING.md:22`, `.github/ISSUE_TEMPLATE/epic.yml:78`, `scripts/tests/test_shared_skill_paths.py`, `.github/workflows/template-ci.yml` (detach scrub file set + counts + kept-section loop), `FORKING.md.jinja` (scrub file set), `CLAUDE.md` (maintainer doc, line 27–30)

**Interfaces:**
- Produces: `TEMPLATE_SKILLS = ("authoring-issues-prs", "config-contract", "logging-standard", "releasing", "repository-protection", "tool-registration", "writing-release-notes")` — the canonical tuple; Task 3's tests and migration script import it from `scripts/migrate_agent_instructions.py`, so define it there in Task 3 and copy the literal into `scripts/tests/test_shared_skill_paths.py` now.

- [ ] **Step 1: Write the failing skill-layout test** (replace `scripts/tests/test_shared_skill_paths.py`)

```python
"""Template-owned contributor skills live under .agents/skills/ (portable) and
are reachable by Claude Code through .claude/skills/<name> symlinks (#486)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
AGENTS_SKILLS = REPO / ".agents" / "skills"
CLAUDE_SKILLS = REPO / ".claude" / "skills"
TEMPLATE_SKILLS = (
    "authoring-issues-prs",
    "config-contract",
    "logging-standard",
    "releasing",
    "repository-protection",
    "tool-registration",
    "writing-release-notes",
)
_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def _skill_file(name: str) -> Path:
    d = AGENTS_SKILLS / name
    for candidate in (d / "SKILL.md.jinja", d / "SKILL.md"):
        if candidate.is_file():
            return candidate
    raise AssertionError(f"{name}: no SKILL.md(.jinja) under .agents/skills/")


@pytest.mark.parametrize("name", TEMPLATE_SKILLS)
def test_skill_is_portable_and_symlinked(name: str) -> None:
    _skill_file(name)
    link = CLAUDE_SKILLS / name
    assert link.is_symlink(), f".claude/skills/{name} must be a symlink"
    assert link.readlink() == Path(f"../../.agents/skills/{name}"), link.readlink()
    assert link.resolve() == (AGENTS_SKILLS / name).resolve()


@pytest.mark.parametrize("name", TEMPLATE_SKILLS)
def test_skill_frontmatter(name: str) -> None:
    text = _skill_file(name).read_text(encoding="utf-8")
    m = _FRONTMATTER.match(text)
    assert m, f"{name}: SKILL.md lacks YAML frontmatter"
    fm = m.group(1)
    assert re.search(rf"^name: {re.escape(name)}$", fm, re.M), f"{name}: name must equal dir"
    assert re.search(r"^description: \S", fm, re.M), f"{name}: description missing"


def test_no_real_directories_under_claude_skills() -> None:
    real = [p.name for p in CLAUDE_SKILLS.iterdir() if p.is_dir() and not p.is_symlink()]
    assert not real, f"real directories under .claude/skills/ (must be symlinks): {real}"


def test_every_agents_skill_has_a_symlink() -> None:
    missing = [p.name for p in AGENTS_SKILLS.iterdir() if p.is_dir() and not (CLAUDE_SKILLS / p.name).is_symlink()]
    assert not missing, f"skills without a .claude/skills symlink: {missing}"


def test_gitignore_keeps_both_skill_roots() -> None:
    for path in (REPO / ".gitignore", REPO / ".gitignore.jinja"):
        text = path.read_text(encoding="utf-8")
        assert "!.agents/skills/" in text, path
        assert "!.claude/skills/" in text, path
```

- [ ] **Step 2: Run it to see it fail**

Run: `uv run pytest -q scripts/tests/test_shared_skill_paths.py`
Expected: FAIL — `no SKILL.md(.jinja) under .agents/skills/` for the five new names; symlink assertions fail for all seven.

- [ ] **Step 3: Extract the sections from `AGENTS.md.jinja` into skill files**

Locate the ranges by heading (line numbers are from `main` at `816d027`; verify with `grep -n '^## \|^<!-- TEMPLATE-TRACKING' AGENTS.md.jinja` first):

| Skill | Cut from `AGENTS.md.jinja` (inclusive, by heading) |
|---|---|
| `logging-standard` | `## Logging Standard` (202) through the line before `## Config & Customization Contract` (249) |
| `config-contract` | `## Config & Customization Contract` (250) through the line before `## Claude Code plugin channel` (294) — **but** cut the `### Tool icons` subsection (272–275) out of this range and put it in `tool-registration` |
| `releasing` | `## Claude Code plugin channel` (295) through `<!-- TEMPLATE-TRACKING-END -->` (368) — this includes Pre-release smoke, Release model, Unstable channel, Release machinery, and the TEMPLATE-TRACKING-wrapped Release notes pages |
| `tool-registration` | `## Tool Registration Checklist` (370) through the line before `## Repository protection (rulesets)` (386), plus `### Tool icons` from config-contract, plus the `## Public import surface guard` section (grep `Public import surface` — it sits inside one of the above ranges; keep it with tool-registration) |
| `repository-protection` | `## Repository protection (rulesets)` (387) through the line before the third `<!-- TEMPLATE-TRACKING-START -->` (392) |

Use a script so the cut is exact and the removed text is byte-identical to the inserted text:

```bash
python3 - <<'EOF'
from pathlib import Path
src = Path("AGENTS.md.jinja"); lines = src.read_text().splitlines(keepends=True)
def idx(prefix, start=0):
    for i in range(start, len(lines)):
        if lines[i].startswith(prefix): return i
    raise SystemExit(f"missing {prefix!r}")
cuts = {}
a = idx("## Logging Standard"); b = idx("## Config & Customization Contract")
cuts["logging-standard"] = (a, b)
c = idx("## Claude Code plugin channel")
cuts["config-contract"] = (b, c)
tt2 = idx("<!-- TEMPLATE-TRACKING-END -->", idx("## Release notes pages"))
cuts["releasing"] = (c, tt2 + 1)
d = idx("## Tool Registration Checklist"); e = idx("## Repository protection (rulesets)")
cuts["tool-registration"] = (d, e)
f = idx("<!-- TEMPLATE-TRACKING-START -->", e)
cuts["repository-protection"] = (e, f)
bodies = {k: "".join(lines[s:t]) for k, (s, t) in cuts.items()}
# Tool icons subsection moves from config-contract to tool-registration.
cc = bodies["config-contract"]; i = cc.index("### Tool icons"); j = cc.index("### Dockerfile extension points")
bodies["tool-registration"] += cc[i:j]; bodies["config-contract"] = cc[:i] + cc[j:]
desc = {
 "logging-standard": "Use before adding or changing any logging call in src/: the structlog-based standard, log levels, exception handling, and message format every module follows.",
 "config-contract": "Use when adding a domain configuration field, env var, Dockerfile extension, mcpb install-screen entry, or release-manifest stamp: the sentinel-based config and customization contract.",
 "releasing": "Use before any release work: the trunk release model, the unstable edge channel, the prepare/release/promotion machinery, release-notes pages, the pre-release artifact smoke test, and the Claude Code plugin channel.",
 "tool-registration": "Use when adding, renaming, or documenting an MCP tool: the registration checklist, the get_server_info tool, tool icons, and the public import-surface guard.",
 "repository-protection": "Use when changing branch or tag rulesets, required checks, or the bootstrap workflow: how repository protection is applied and kept in sync.",
}
for k, body in bodies.items():
    out = Path(f".agents/skills/{k}/SKILL.md.jinja"); out.parent.mkdir(parents=True)
    out.write_text(f"---\nname: {k}\ndescription: >-\n  {desc[k]}\n---\n\n<!-- ===== TEMPLATE-OWNED — re-rendered on template updates. ===== -->\n\n" + body.rstrip("\n") + "\n")
keep = []
skip = sorted(cuts.values())
for i, line in enumerate(lines):
    if any(s <= i < t for s, t in skip): continue
    keep.append(line)
src.write_text("".join(keep))
EOF
git diff --stat
```

Then open `AGENTS.md.jinja` and remove the now-dangling `### Tool icons` cross-reference text if any sentence in a kept section links to `#tool-icons` (grep `tool-icons`); repoint it to `.agents/skills/tool-registration/SKILL.md`.

- [ ] **Step 4: Move `authoring-issues-prs`, create the symlinks, enable symlink preservation**

```bash
git mv .claude/skills/authoring-issues-prs .agents/skills/authoring-issues-prs
for s in authoring-issues-prs config-contract logging-standard releasing repository-protection tool-registration writing-release-notes; do
  ln -s "../../.agents/skills/$s" ".claude/skills/$s"
done
ls -l .claude/skills/
```

In `copier.yml`, directly under `_templates_suffix: .jinja` add:

```yaml
# Contributor skills are canonical under .agents/skills/ (portable, read by
# Cursor/Codex/…); Claude Code only scans .claude/skills/, so each ships a
# relative symlink there.  Copier must copy the link, not its target (#486).
_preserve_symlinks: true
```

Update the `_skip_if_exists` comment (lines 76–78) to: "Contributor skills are deliberately NOT listed here: every template-owned skill under .agents/skills/ and its .claude/skills/ symlink is re-rendered on every update."

- [ ] **Step 5: Repoint skill references**

```bash
sed -i 's|`\.claude/skills/authoring-issues-prs/`|`.agents/skills/authoring-issues-prs/`|' CONTRIBUTING.md
sed -i 's|`\.claude/skills/authoring-issues-prs/SKILL\.md`|`.agents/skills/authoring-issues-prs/SKILL.md`|' .github/ISSUE_TEMPLATE/epic.yml
grep -rn 'claude/skills/authoring' --include='*.md' --include='*.yml' --include='*.jinja' . | grep -v '^./.worktrees\|^./docs/superpowers'
```

Expected: only `AGENTS.md.jinja:≈409` remains → edit that sentence to `The `authoring-issues-prs` skill (`.agents/skills/authoring-issues-prs/SKILL.md`, reachable by Claude Code via `.claude/skills/`) fires…`. Update `.gitignore.jinja:49-50` comment to "Everything under .claude/ is local EXCEPT skills/ — that subtree holds symlinks into .agents/skills/, template-owned on copier update." and mirror in this repo's `.gitignore:27-28`. Update this repo's `CLAUDE.md:27-30` bullet to: "`.github/ISSUE_TEMPLATE/*.yml`, `CONTRIBUTING.md`, and every skill under `.agents/skills/` (with its `.claude/skills/` symlink) are copied verbatim into generated projects and re-rendered on `copier update`."

- [ ] **Step 6: Extend the detach scrub to the skill files** (`template-ci.yml` detach step and `FORKING.md.jinja` Step 3)

In `template-ci.yml`, change `count_occurrences` to count across the scrub set and make the `sed` loop over it:

```bash
          SCRUB_FILES="AGENTS.md .agents/skills/releasing/SKILL.md .agents/skills/config-contract/SKILL.md .agents/skills/tool-registration/SKILL.md"
          count_occurrences() {
            cat $SCRUB_FILES | grep -oF "$1" | wc -l | tr -d '[:space:]' || true
          }
```

Keep every `check_anchor` count as it is (the strings moved files, not counts). Change the scrub to:

```bash
          for f in $SCRUB_FILES; do
            sed -i.bak \
              -e '/<!-- TEMPLATE-TRACKING-START -->/,/<!-- TEMPLATE-TRACKING-END -->/d' \
              -e '/<!-- ===== TEMPLATE-OWNED SECTIONS BELOW/d' \
              -e '/<!-- ===== TEMPLATE-OWNED SECTIONS END ===== -->/d' \
              -e 's/ Kept across copier update\.//' \
              -e 's/ on top of the shipped defaults survive `copier update`\./ on top of the shipped defaults are yours to maintain./' \
              -e 's/ are preserved across `copier update`\./ are domain-owned./' \
              -e 's/The block is preserved across `copier update`\./The block is domain-owned./' \
              -e 's| on every `copier copy`/`copier update` and re-verified by| whenever config fields change, and re-verified by|' \
              "$f" && rm -f "$f.bak"
          done
```

Post-scrub assertions: the `! grep … copier update` and `fleet|downstream…` greps run over `$SCRUB_FILES` (use `grep -rniE … $SCRUB_FILES`). `Release notes pages section survived` → grep `.agents/skills/releasing/SKILL.md`. In the kept-section loop, remove `## Logging Standard`, `## Config & Customization Contract`, `## Server Info Tool`, `## Tool Registration Checklist` (moved) and add `'^## Documentation Discipline$'` and `'^## Breaking Changes and the'` as the over-run guards around the remaining two TEMPLATE-TRACKING pairs. Update the pair-boundary comment: AGENTS.md now holds pairs 1 (PR Discipline) and 3 (Shared Infrastructure); pair 2 lives in the releasing skill. Add `.agents/skills/releasing/SKILL.md` to the post-scrub "replacement text produced" counts the same way.

In `template-ci.yml`'s `AGENTS.md sentinel structure` step: expect **2** TEMPLATE-TRACKING pairs in `AGENTS.md` and add:

```bash
          rel=$(grep -cE '^<!-- TEMPLATE-TRACKING-START -->$' .agents/skills/releasing/SKILL.md || true)
          [ "$rel" = "1" ] || { echo "::error::expected 1 TEMPLATE-TRACKING pair in releasing skill, found $rel"; exit 1; }
```

Also in the detach step's "Step 2" rm list add nothing (the skills stay in a fork; `FORKING.md.jinja:50-51` already says retain or remove). In `FORKING.md.jinja` Step 3, wrap the `sed` in the same `for f in AGENTS.md .agents/skills/releasing/SKILL.md .agents/skills/config-contract/SKILL.md .agents/skills/tool-registration/SKILL.md; do … done` loop and extend the prose: "the copier-update wording that the `releasing`, `config-contract`, and `tool-registration` skills carry".

- [ ] **Step 7: Run the skill-layout test; commit; render; full gate**

```bash
uv run pytest -q scripts/tests/test_shared_skill_paths.py      # expect all pass
git add -A && git commit -q -m "refactor(agents): move task-shaped guidance into portable skills under .agents/skills/

Verbatim relocation of Logging Standard, Config & Customization Contract,
Tool Registration + Server Info + icons, Repository protection, and the
release sections into .agents/skills/<name>/SKILL.md, each reachable by
Claude Code through a .claude/skills/<name> symlink; authoring-issues-prs
joins them. copier preserves the links (_preserve_symlinks).

Refs #484 #486"
rm -rf /tmp/smoke && uv run --no-project --with copier copier copy --trust --defaults --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
python3 scripts/check_render_hygiene.py /tmp/smoke
ls -l /tmp/smoke/.claude/skills/            # seven symlinks
head -3 /tmp/smoke/.agents/skills/releasing/SKILL.md
wc -c /tmp/smoke/AGENTS.md                  # expect ≈ 19k
cd /tmp/smoke && uv sync --all-extras --all-groups -q && uv run ruff check . && uv run mypy src/ tests/ && uv run pytest -x -q; cd -
uv run pytest -q scripts/tests
```

Expected: hygiene OK, seven symlinks, frontmatter rendered, ≈19k, gates green.

- [ ] **Step 8: Verify Claude Code sees the symlinked skills in the render**

```bash
cd /tmp/smoke && timeout 120 claude -p "List every available project skill name, one per line, nothing else." --max-turns 1; cd -
```

Expected: the seven names appear. Push.

---

### Task 3: Migration script + rendered guard + template guard

**Files:**
- Create: `scripts/migrate_agent_instructions.py`
- Create: `scripts/tests/test_migrate_agent_instructions.py`
- Create: `tests/test_agent_instructions.py` (rendered into every project; plain `.py`, no Jinja needed)
- Modify: `copier.yml` (`_migrations`), `.github/workflows/template-ci.yml` (size budget step after the sentinel step; detach Step 2 `rm -f scripts/migrate_agent_instructions.py`), `FORKING.md.jinja` (Step 2 rm list)

**Interfaces:**
- Produces: `scripts/migrate_agent_instructions.py` with `STUB: str`, `TEMPLATE_SKILLS: tuple[str, ...]`, `DOMAIN_RE: re.Pattern`, `domain_blocks(text) -> list[str]`, `is_placeholder(block) -> bool`, `splice(agents_text, head_claude_text) -> tuple[str, int]`, `migrate(root: Path, *, head_claude: str | None) -> list[str]`, `main() -> int`.

- [ ] **Step 1: Write the failing migration tests**

```python
"""The after-stage copier migration that moves a downstream from CLAUDE.md to
AGENTS.md without a human step (spec §4)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
import migrate_agent_instructions as mig  # noqa: E402

PLACEHOLDER = "<!-- DOMAIN-START -->\n<!-- Describe your service's design here. Kept across copier update. -->\n<!-- DOMAIN-END -->\n"
FILLED = "<!-- DOMAIN-START -->\nReal design prose.\n\n- bullet\n<!-- DOMAIN-END -->\n"
AGENTS_FRESH = "# X\n\n## Design\n" + PLACEHOLDER + "\n## Project Structure\n" + PLACEHOLDER + "\n## Key Design Decisions\n" + PLACEHOLDER
HEAD_CLAUDE = "# X\n\n## Design\n" + FILLED + "\n## Project Structure\n" + PLACEHOLDER + "\n## Key Design Decisions\n" + FILLED.replace("Real", "Decision")


def _project(tmp_path: Path, *, agents: str = AGENTS_FRESH, claude: str = "<<<<<<< before updating\nold\n=======\nnew\n>>>>>>> after updating\n") -> Path:
    (tmp_path / "AGENTS.md").write_text(agents, encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text(claude, encoding="utf-8")
    (tmp_path / ".agents" / "skills" / "releasing").mkdir(parents=True)
    (tmp_path / ".agents" / "skills" / "releasing" / "SKILL.md").write_text("---\nname: releasing\n---\n")
    (tmp_path / ".claude" / "skills").mkdir(parents=True)
    return tmp_path


def test_is_placeholder_recognises_the_seeded_comment() -> None:
    assert mig.is_placeholder("<!-- Describe your service's design here. Kept across copier update. -->\n")
    assert mig.is_placeholder("\n  \n")
    assert not mig.is_placeholder("Real prose\n")


def test_splice_moves_only_filled_blocks_into_empty_ones() -> None:
    out, moved = mig.splice(AGENTS_FRESH, HEAD_CLAUDE)
    assert moved == 2
    blocks = mig.domain_blocks(out)
    assert "Real design prose." in blocks[0]
    assert mig.is_placeholder(blocks[1])
    assert "Decision design prose." in blocks[2]


def test_splice_never_overwrites_a_filled_agents_block() -> None:
    already = AGENTS_FRESH.replace(PLACEHOLDER, FILLED.replace("Real", "Kept"), 1)
    out, moved = mig.splice(already, HEAD_CLAUDE)
    assert moved == 1  # only Key Design Decisions
    assert "Kept design prose." in mig.domain_blocks(out)[0]


def test_migrate_rewrites_stub_and_replaces_real_skill_dir(tmp_path: Path) -> None:
    root = _project(tmp_path)
    real = root / ".claude" / "skills" / "releasing"
    real.mkdir(); (real / "SKILL.md").write_text("stale copy")
    actions = mig.migrate(root, head_claude=HEAD_CLAUDE)
    assert (root / "CLAUDE.md").read_text(encoding="utf-8") == mig.STUB
    assert "Real design prose." in (root / "AGENTS.md").read_text(encoding="utf-8")
    link = root / ".claude" / "skills" / "releasing"
    assert link.is_symlink() and os.readlink(link) == "../../.agents/skills/releasing"
    assert any("git show HEAD:CLAUDE.md" in a for a in actions)


def test_migrate_is_idempotent(tmp_path: Path) -> None:
    root = _project(tmp_path)
    mig.migrate(root, head_claude=HEAD_CLAUDE)
    after_first = (root / "AGENTS.md").read_text(encoding="utf-8")
    actions = mig.migrate(root, head_claude=HEAD_CLAUDE)
    assert (root / "AGENTS.md").read_text(encoding="utf-8") == after_first
    assert not any("spliced" in a for a in actions)


def test_migrate_noop_without_head_claude_or_agents(tmp_path: Path) -> None:
    assert mig.migrate(tmp_path, head_claude=None) == []
    (tmp_path / "CLAUDE.md").write_text("x")
    assert mig.migrate(tmp_path, head_claude="no blocks here") == []


def test_stub_matches_the_template(tmp_path: Path) -> None:
    # CLAUDE.md.jinja has no Jinja in it, so its bytes ARE the render.
    assert (REPO / "CLAUDE.md.jinja").read_text(encoding="utf-8") == mig.STUB
```

- [ ] **Step 2: Run to see them fail**

Run: `uv run pytest -q scripts/tests/test_migrate_agent_instructions.py`
Expected: `ModuleNotFoundError: migrate_agent_instructions`.

- [ ] **Step 3: Write `scripts/migrate_agent_instructions.py`**

```python
"""Move a downstream from CLAUDE.md to AGENTS.md during `copier update`.

Runs from copier.yml `_migrations` (after-stage, every update, after the
old-render → project diff has been applied).  Copier re-renders CLAUDE.md as
the stub and leaves inline conflict markers where the project's DOMAIN
content used to be; the project's real pre-update CLAUDE.md is still at git
HEAD, so recover from there — never from the conflict-marked file.

Steps (each printed when taken):
1. Splice HEAD:CLAUDE.md's filled DOMAIN blocks into AGENTS.md's empty ones
   (by ordinal).  A filled AGENTS.md block is never overwritten.
2. Overwrite CLAUDE.md with the stub.
3. Replace any real directory at .claude/skills/<template skill> with the
   relative symlink into .agents/skills/ the template ships.
4. Point at `git show HEAD:CLAUDE.md` so hand edits outside DOMAIN blocks
   can be re-applied to AGENTS.md — the only case that needs a human.

Idempotent; a no-op on `copier copy` (no HEAD:CLAUDE.md) and on a project
that already migrated.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

STUB = (
    "@AGENTS.md\n"
    "\n"
    "Project instructions live in `AGENTS.md` (domain content between its "
    "`DOMAIN-START` / `DOMAIN-END` markers). This file is template-owned; "
    "do not add content here.\n"
)

TEMPLATE_SKILLS: tuple[str, ...] = (
    "authoring-issues-prs",
    "config-contract",
    "logging-standard",
    "releasing",
    "repository-protection",
    "tool-registration",
    "writing-release-notes",
)

DOMAIN_RE = re.compile(r"(<!-- DOMAIN-START -->\n)(.*?)(<!-- DOMAIN-END -->)", re.DOTALL)
_PLACEHOLDER_RE = re.compile(r"^<!--.*Kept across copier update\.\s*-->$")


def domain_blocks(text: str) -> list[str]:
    return [m.group(2) for m in DOMAIN_RE.finditer(text)]


def is_placeholder(block: str) -> bool:
    lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
    return all(_PLACEHOLDER_RE.match(ln) for ln in lines)


def splice(agents_text: str, head_claude_text: str) -> tuple[str, int]:
    head = domain_blocks(head_claude_text)
    moved = 0
    counter = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal moved, counter
        i = counter
        counter += 1
        if i < len(head) and is_placeholder(m.group(2)) and not is_placeholder(head[i]):
            moved += 1
            return m.group(1) + head[i] + m.group(3)
        return m.group(0)

    return DOMAIN_RE.sub(repl, agents_text), moved


def _fix_skill_links(root: Path, actions: list[str]) -> None:
    claude_skills = root / ".claude" / "skills"
    for name in TEMPLATE_SKILLS:
        if not (root / ".agents" / "skills" / name).is_dir():
            continue
        link = claude_skills / name
        target = f"../../.agents/skills/{name}"
        if link.is_symlink():
            if os.readlink(link) == target:
                continue
            link.unlink()
        elif link.is_dir():
            shutil.rmtree(link)
            actions.append(f"removed real directory .claude/skills/{name} (now a symlink)")
        claude_skills.mkdir(parents=True, exist_ok=True)
        link.symlink_to(target)
        actions.append(f"linked .claude/skills/{name} -> {target}")


def migrate(root: Path, *, head_claude: str | None) -> list[str]:
    actions: list[str] = []
    agents = root / "AGENTS.md"
    if head_claude is None or not agents.is_file() or not DOMAIN_RE.search(head_claude):
        return actions
    text = agents.read_text(encoding="utf-8")
    new_text, moved = splice(text, head_claude)
    if moved:
        agents.write_text(new_text, encoding="utf-8")
        actions.append(f"spliced {moved} DOMAIN block(s) from HEAD:CLAUDE.md into AGENTS.md")
    claude = root / "CLAUDE.md"
    if not claude.is_file() or claude.read_text(encoding="utf-8") != STUB:
        claude.write_text(STUB, encoding="utf-8")
        actions.append("rewrote CLAUDE.md as the @AGENTS.md stub")
    _fix_skill_links(root, actions)
    actions.append(
        "CLAUDE.md content before this update is at `git show HEAD:CLAUDE.md`; "
        "re-apply any hand edits made outside its DOMAIN blocks to AGENTS.md"
    )
    return actions


def _head_claude(root: Path) -> str | None:
    proc = subprocess.run(
        ["git", "show", "HEAD:CLAUDE.md"], cwd=root, capture_output=True, text=True, check=False
    )
    return proc.stdout if proc.returncode == 0 else None


def main() -> int:
    root = Path.cwd()
    for line in migrate(root, head_claude=_head_claude(root)):
        print(f"migrate_agent_instructions: {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to green; lint**

Run: `uv run pytest -q scripts/tests/test_migrate_agent_instructions.py && uv run ruff check scripts/ && uv run mypy scripts/migrate_agent_instructions.py scripts/tests/test_migrate_agent_instructions.py`
Expected: all pass.

- [ ] **Step 5: Wire the migration and the rendered guard**

`copier.yml` `_migrations`:

```yaml
_migrations:
  - "python scripts/gen_config_surface.py"
  # CLAUDE.md → AGENTS.md move (#484/#485): splices the project's DOMAIN
  # blocks from HEAD:CLAUDE.md into AGENTS.md, rewrites CLAUDE.md as the
  # stub, and reconciles .claude/skills/ symlinks.  Idempotent.
  - "python scripts/migrate_agent_instructions.py"
```

Create `tests/test_agent_instructions.py`:

```python
"""Agent-instruction surface contract (template-owned).

AGENTS.md is the single always-loaded instruction file every coding agent
reads; CLAUDE.md is a stub importing it; skills live under .agents/skills/
with .claude/skills/ symlinks for Claude Code.  Claude Code warns above
40 000 characters of always-loaded instructions, and the template owns
~20k of AGENTS.md, so the DOMAIN blocks are the lever when this fails.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENTS_LIMIT = 40_000
STUB = (
    "@AGENTS.md\n\nProject instructions live in `AGENTS.md` (domain content between its "
    "`DOMAIN-START` / `DOMAIN-END` markers). This file is template-owned; do not add content here.\n"
)


def test_agents_md_within_always_loaded_budget() -> None:
    size = len((REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8"))
    assert size <= AGENTS_LIMIT, (
        f"AGENTS.md is {size} chars; Claude Code degrades above {AGENTS_LIMIT}. "
        "Trim the DOMAIN blocks (move detail into docs/ or a project skill under "
        ".agents/skills/) — the template-owned sections are budgeted separately."
    )


def test_claude_md_is_the_stub() -> None:
    assert (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8") == STUB, (
        "CLAUDE.md is template-owned and must stay the @AGENTS.md stub; put content in AGENTS.md"
    )


def test_claude_skill_links_resolve_into_agents_skills() -> None:
    claude_skills = REPO_ROOT / ".claude" / "skills"
    agents_skills = (REPO_ROOT / ".agents" / "skills").resolve()
    for entry in claude_skills.iterdir():
        assert entry.is_symlink(), f"{entry} must be a symlink into .agents/skills/"
        assert entry.resolve().parent == agents_skills, entry
        assert (entry / "SKILL.md").is_file(), f"{entry} does not resolve to a SKILL.md"
```

`template-ci.yml`: after the `AGENTS.md sentinel structure` step add

```yaml
      - name: AGENTS.md template-owned size budget
        working-directory: /tmp/smoke
        run: |
          # Claude Code warns above 40k always-loaded chars.  The smoke render's
          # DOMAIN blocks are near-empty, so this measures the template's share;
          # 24k leaves every downstream >=16k for domain content (#484).
          size=$(wc -c < AGENTS.md | tr -d '[:space:]')
          [ "$size" -le 24000 ] || { echo "::error::AGENTS.md template-owned prose is ${size} chars (> 24000). Move guidance into a skill under .agents/skills/ rather than growing the always-loaded file."; exit 1; }
```

Detach smoke Step 2 and `FORKING.md.jinja` Step 2: add `scripts/migrate_agent_instructions.py` to the `rm -f` list beside `scripts/copier_update_notes.py`.

- [ ] **Step 6: Commit; prove the migration end-to-end with a real `copier update`**

```bash
git add -A && git commit -q -m "feat(agents): migrate downstream CLAUDE.md into AGENTS.md on copier update, with guards

Refs #484 #485 #486"
# Simulate a downstream on the previous template release, then update to HEAD.
rm -rf /tmp/mig && uv run --no-project --with copier copier copy --trust --defaults --vcs-ref=v5.6.3 --data-file tests/fixtures/smoke-answers.yml . /tmp/mig >/dev/null 2>&1
cd /tmp/mig && git init -q && python3 - <<'EOF'
from pathlib import Path
p = Path("CLAUDE.md"); t = p.read_text()
t = t.replace("<!-- Describe your service's design here. Kept across copier update. -->", "This service indexes widgets.", 1)
p.write_text(t)
EOF
git add -A && git -c user.email=a@b -c user.name=t commit -qm "downstream with domain content"
uv run --no-project --with copier copier update --trust --defaults --skip-answered --conflict=inline --vcs-ref=HEAD 2>&1 | grep -i 'migrate_agent\|error'
grep -n 'This service indexes widgets.' AGENTS.md          # expect one hit inside the first DOMAIN block
diff <(git show HEAD:CLAUDE.md >/dev/null; cat CLAUDE.md) /mnt/code/mcp-servers/fastmcp-server-template/CLAUDE.md.jinja && echo STUB OK
ls -l .claude/skills/ | grep -c '^l'                        # expect 7
git status --short | head; cd -
```

Expected: migration prints `spliced 1 DOMAIN block(s)…`, the widget line is in `AGENTS.md`, `STUB OK`, 7 symlinks. (The `.claude/skills/authoring-issues-prs` real directory from v5.6.3 must have been replaced — check `ls -l` shows a link, not a dir.)

Note `--vcs-ref=HEAD` for update needs the template path in `.copier-answers.yml` to be absolute; if the answers file recorded `.`, run the copy step with the absolute template path (`/mnt/code/mcp-servers/fastmcp-server-template`).

- [ ] **Step 7: Render, hygiene, full gate, push**

Same commands as Task 2 Step 7, plus `uv run pytest -q scripts/tests`. Push.

---

### Task 4: Trim `AGENTS.md.jinja` to the 24k budget and add the Skills section

**Files:**
- Modify: `AGENTS.md.jinja` only

**Interfaces:**
- Consumes: skill names from Task 2. Must keep every string other tests/workflows assert: the `## Conventions` prose `tests/test_commit_conventions.py.jinja` lists (read its `REQUIRED_PHRASES`/equivalent constants before touching Conventions), `## Structural health` heading and `Structural quality (diff) passes`, `## Hard PR Acceptance Gates`, `## PR Discipline`, `## GitHub Review Types` (kept-section loop; if you merge it into PR Discipline, update the loop in `template-ci.yml`), `Automatic agent review is disabled` / `The automated Claude review runs` (test_claude_review_gating), `## Shared Infrastructure`, `## Contributing fixes upstream`, `## Key Design Decisions`, all scrub anchors and their counts.

- [ ] **Step 1: Measure**

Run: `rm -rf /tmp/smoke && … copier copy … && wc -c /tmp/smoke/AGENTS.md`
Expected: ≈19k already (Task 2 removed ~30k). If ≤ 22k, the trim is light; do Step 2 regardless for the Skills section.

- [ ] **Step 2: Add the Skills section** directly after `## Conventions`' closing paragraph and before `## Breaking Changes` (inside the TEMPLATE-OWNED fences, outside any TEMPLATE-TRACKING block):

```markdown
## Skills

Detailed guidance lives in skills under `.agents/skills/` (portable; Claude Code reaches them through `.claude/skills/` symlinks). They load only when invoked, so invoke them explicitly:

- `releasing` — before any release, release-candidate, unstable-channel, plugin-channel, or release-notes work.
- `config-contract` — before adding a config field, env var, Dockerfile extension point, mcpb install-screen entry, or release-manifest stamp.
- `logging-standard` — before adding or changing a logging call.
- `tool-registration` — before adding, renaming, or documenting an MCP tool, `get_server_info`, icons, or the public import surface.
- `repository-protection` — before changing rulesets, required checks, or the bootstrap workflow.
- `authoring-issues-prs` — when filing an issue or opening a PR.
- `writing-release-notes` — when drafting a `docs/releases/` page.

Project-owned skills follow the same shape: a directory under `.agents/skills/` plus a relative symlink in `.claude/skills/`.
```

- [ ] **Step 3: Trim** — in a single pass, without changing any asserted string: merge `## GitHub Review Types` into the end of `## PR Discipline` as a short list **only if** you also update the kept-section loop in `template-ci.yml` (otherwise leave the heading); merge `## Documentation Conventions (user-facing vs internal)` into `## Documentation Discipline`; shorten `## Pre-commit Hooks` to the hook list plus the one sentence carrying ` on top of the shipped defaults survive `copier update`.`; drop paragraphs that restate what the moved skills now own (e.g. the pre-commit paragraph about release stamping) in favour of "see the `releasing` skill".

- [ ] **Step 4: Render, assert budget, full gate, detach checks**

```bash
git add -A && git commit -q -m "docs(agents): trim AGENTS.md to the always-loaded budget and add the Skills section

Refs #484"
rm -rf /tmp/smoke && uv run --no-project --with copier copier copy --trust --defaults --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
wc -c /tmp/smoke/AGENTS.md                                  # expect <= 24000
python3 scripts/check_render_hygiene.py /tmp/smoke
for a in '<!-- TEMPLATE-TRACKING-START -->' ' Kept across copier update.' ' on top of the shipped defaults survive `copier update`.'; do printf '%-60s %s\n' "$a" "$(cat /tmp/smoke/AGENTS.md /tmp/smoke/.agents/skills/{releasing,config-contract,tool-registration}/SKILL.md | grep -oF "$a" | wc -l)"; done
cd /tmp/smoke && uv sync --all-extras --all-groups -q && uv run ruff check . && uv run mypy src/ tests/ && uv run pytest -x -q; cd -
uv run pytest -q scripts/tests
```

Expected: ≤ 24000; anchor counts 3 / 3 / 1 (matching `check_anchor`); gates green. Push.

---

### Task 5: `UPGRADING.md`, maintainer docs, PR

**Files:**
- Modify: `UPGRADING.md` (append under `## Unreleased`), `CLAUDE.md` (this repo; "Layout" bullets), `README.md` (this repo, line 32 mention)

- [ ] **Step 1: Append to `UPGRADING.md` under `## Unreleased`**

```markdown
### CLAUDE.md is now a stub; AGENTS.md carries the instructions

Project instructions moved to `AGENTS.md`, which every AAIF-aware agent reads;
`CLAUDE.md` is a three-line stub importing it. Task-shaped guidance (release
model and machinery, config contract, logging standard, tool registration,
repository protection) moved into skills under `.agents/skills/`, each with a
`.claude/skills/<name>` symlink so Claude Code still finds it.

`copier update` migrates automatically: the DOMAIN blocks from your committed
`CLAUDE.md` are spliced into `AGENTS.md`, `CLAUDE.md` is rewritten as the stub,
and the old `.claude/skills/authoring-issues-prs/` directory becomes a symlink.
Review the update PR's `AGENTS.md` diff to confirm your three DOMAIN blocks
arrived.

Do by hand only if it applies:

- If you had edited template-owned prose in `CLAUDE.md` outside the DOMAIN
  blocks, re-apply it in `AGENTS.md` — the migration prints a pointer to
  `git show HEAD:CLAUDE.md`.
- If your `.gitignore` predates the `!.agents/skills/` or `!.claude/skills/`
  exceptions, add both (the file is seeded once), or git ignores the skills
  and their symlinks.
- If `AGENTS.md` exceeds 40 000 characters, `tests/test_agent_instructions.py`
  fails: shorten the DOMAIN blocks or move detail into a project skill.
```

Run: `python3 scripts/promote_upgrading.py --check` → well-formed.

- [ ] **Step 2: Update this repo's maintainer docs**

`CLAUDE.md` "Layout": `AGENTS.md.jinja` + stub `CLAUDE.md.jinja`; `.agents/skills/*/SKILL.md.jinja` template-owned skills with `.claude/skills/` symlinks; `scripts/migrate_agent_instructions.py`. Add a "Render hygiene"-style paragraph: "Always-loaded budget: `template-ci` fails when the smoke `AGENTS.md` exceeds 24k; new guidance goes into a skill." `README.md:32` → `AGENTS.md`.

- [ ] **Step 3: Commit, final full verification, local review, PR**

```bash
git add -A && git commit -q -m "docs: upgrade notes and maintainer docs for the AGENTS.md move

Closes #484
Closes #485
Closes #486"
rm -rf /tmp/smoke && … copier copy … && python3 scripts/check_render_hygiene.py /tmp/smoke
cd /tmp/smoke && vale sync >/dev/null && vale --glob='!docs/{superpowers,design,decisions}/**' docs README.md; uv sync --all-extras --all-groups -q && uv run ruff check . && uv run ruff format --check . && uv run mypy src/ tests/ && uv run pytest -x -q; cd -
uv run pytest -q scripts/tests
```

Run the local code-review pass (`/code-review feat/agent-neutral-instructions medium`), address findings, then open the PR with the repository template (`.github/PULL_REQUEST_TEMPLATE.md`): Closes #484 #485 #486; deliberately not doing #496; UPGRADING note present; docs impact: `AGENTS.md.jinja`, `UPGRADING.md`, `FORKING.md.jinja`, `CONTRIBUTING.md`.

---

## Self-review against the spec

- §1 AGENTS.md canonical, sentinels kept, Skills section, 24k budget → Tasks 1, 4, 3 (budget step).
- §2 CLAUDE.md stub → Task 1 (+ test in Task 3).
- §3 five skills verbatim, authoring-issues-prs move, symlinks, `_preserve_symlinks`, references repointed, verbatim-then-trim commits → Task 2, Task 4.
- §4 migration steps 1–4, idempotent, no-op on copy, UPGRADING → Task 3, Task 5. Deviation recorded: the script always prints the `HEAD:CLAUDE.md` pointer instead of detecting hand edits (no previous render is available at migration time); the spec's "only case needing a human" is unchanged.
- §5 guards: template size, symlink/frontmatter tests, stub equality, sentinel/scrub repoint, migration unit tests, rendered 40k/stub/symlink test → Tasks 1–3.
- Ownership table and risks → covered by `_skip_if_exists` comment (Task 2) and UPGRADING (Task 5).
- Names used consistently: `TEMPLATE_SKILLS`, `STUB`, `migrate(root, *, head_claude)`, `splice`, `domain_blocks`, `is_placeholder`, skill directory names.
