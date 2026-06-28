# Structural-health gate (Spec 1: local-first gate + eyes + advisory)

**Status:** approved design, pre-implementation
**Date:** 2026-06-28
**Scope:** the *generated* project (ships via `.jinja`); additive/advisory to the
four downstream consumers.

## Problem

The template ships strong **correctness** gates (ruff lint/format, mypy strict,
pytest, 80% patch coverage via diff-cover, pip-audit, gitleaks, vale) and **zero
structural** ones. Structure is an orthogonal axis: cyclomatic complexity, god
classes/functions, dead code, leaking abstractions, names that drift from
behaviour. Without a structural layer, agent-authored ("vibe-coded") changes grow
this debt unchecked, and the debt is invisible until a human reads the code.

The goal is to **stop structural debt from growing** while **never blocking on
pre-existing debt**, and to surface bigger pre-existing problems as refactor-later
issues — the structural analogue of how patch-coverage gates the diff (hard) while
full coverage is informational (soft).

## Two non-negotiable constraints (why the obvious design is wrong)

1. **This is a template feeding four downstream repos.** Adding strict structural
   rules to the *whole-repo* `ruff check` (the brief's original "Door" bucket of
   absolute thresholds) would make every consumer's next `copier update` fail CI
   wherever their *existing* code trips a new rule. The gate must therefore be
   **diff-scoped**: new/changed code is held to the bar; existing code is not,
   until it is touched.

2. **CI-only enforcement guarantees whack-a-mole.** If the only place the gate
   runs is CI, the coding agent commits, pushes, watches CI go red, and patches
   blindly against a signal it cannot reproduce locally. Every gate must be
   **runnable locally and named in CLAUDE.md**, with CI as a backstop — not the
   primary signal.

## Decomposition

This is Spec 1 of two. The split is along **"what the agent runs locally" (now)**
vs **"what CI persists for everyone" (later)** — *not* "blocking now / advisory
later". The advisory full-repo signal is local-first because its primary consumer
is the agent, and the agent is local.

|                         | Spec 1 — local-first (the agent)                       | Spec 2 — CI persistence (deferred)                          |
| ----------------------- | ------------------------------------------------------ | ----------------------------------------------------------- |
| **Diff-gate** (block)   | pre-push hook + CLAUDE.md command                      | CI `structure` job (backstop) — *included in Spec 1*        |
| **Full-repo** (advise)  | documented analyzer commands + CLAUDE.md when/what     | committed baseline, deduped+capped issue filing, ratchet    |
| **Eyes** (qualitative)  | CLAUDE.md signalling + decay-issue template            | —                                                           |

Spec 2 (the committed `structural-baseline.json`, automated deduped/capped issue
filing, and the ratchet that tightens over time) is **explicitly out of scope
here** and is the part that genuinely needs CI and the most tuning. Spec 1 ships
nothing that forward-references it.

## Spec 1 design

### 1. Diff-gate — blocking, local-first

**Mechanism (de-risked empirically).** `diff-quality` from the `diff_cover`
package (already in the `dev` dependency group) runs a linter and reports
violations **only on changed lines**, with `--fail-under`. Its `ruff.check` driver
runs `ruff check --output-format pylint`; its `--options` flag passes arguments
straight through to ruff. So:

```bash
uv run diff-quality --violations=ruff.check \
  --options="--extend-select=<STRUCTURAL>" \
  --compare-branch=origin/main --fail-under=100
```

runs ruff with the strict structural rules **added on top of** the project config,
filtered to the diff. The whole-repo `ruff check` keeps **today's** selection, so
existing downstream code stays green. Two-tier selection, one already-present
dependency, no new tooling.

**`<STRUCTURAL>` rule set** — complexity + size + security, deliberately **absent**
from the whole-repo `[tool.ruff.lint] select`:

- `C901` — mccabe cyclomatic complexity
- `PLR0911` / `PLR0912` / `PLR0913` / `PLR0915` — too-many
  returns / branches / args / statements
- `S` — security (bandit-equivalent)

> `PLR0904` (god-class) and `PLR0914` (too-many-locals) were dropped: both are ruff preview-only rules and enabling them requires the global `--preview` flag, which would ship all of ruff's unstable preview behaviour to downstream — god-class detection stays with the CLAUDE.md eyes and the deferred full-repo audit.

Diff attribution is by line: a `C901` violation is reported at the function `def`
line, so a **new** complex function (its `def` is in the diff) blocks, while
adding one line inside an existing complex function (its `def` unchanged) does
not. This is the intended "don't grow worse" semantics.

**Thresholds** (`max-complexity`, `max-args`, `max-statements`, …) live as
commented policy constants in the rendered `pyproject.toml` under
`[tool.ruff.lint.mccabe]` / `[tool.ruff.lint.pylint]`, starting at ruff defaults
(complexity 10, args 5, statements 50). One commented block; editable on
instantiation.

**Escape hatch.** `# noqa: C901` (etc.) plus a justifying comment, for genuinely
irreducible new code.

**Local-first placement.** A pre-commit **pre-push** hook is the natural home: a
commit-time hook has no base branch and sees only partial commits, but pre-push
has the full branch and a base, so the hook runs the *identical* command CI runs
over the *same* range (`HEAD` vs `origin/main`). Green-locally ⇒ green-in-CI by
construction.

```yaml
# .pre-commit-config.yaml.jinja
default_install_hook_types: [pre-commit, pre-push]
# ...
  - repo: local
    hooks:
      - id: structural-diff-gate
        name: structural quality (diff vs origin/main)
        entry: uv run diff-quality --violations=ruff.check
               --options=--extend-select=<STRUCTURAL>
               --compare-branch=origin/main --fail-under=100
        language: system
        pass_filenames: false
        stages: [pre-push]
```

The exact `--options` quoting above is illustrative, not asserted: how
`diff-quality` splits the `--options` string into ruff argv is resolved
empirically by test #2 below, and the hook/CI commands are then written to match
that verified form byte-for-byte.

The strict rules stay **out** of the commit-time whole-file `ruff check` —
including them there would re-fail pre-existing debt in any file the agent touches,
which is the *other* whack-a-mole.

**CI backstop.** A new PR-only `structure` job in `ci.yml.jinja`, structurally a
sibling of the existing diff-cover steps: checkout `fetch-depth: 0`, fetch the base
branch, skip when the diff touches no `.py` files, then run the same
`diff-quality` command. Non-zero exit fails the job; downstream marks it required
in branch protection (like `codecov/patch`).

**Toggle.** `copier.yml` gains `enable_structural_gate` (`bool`, default `true`),
mirroring `enable_authorization` / `include_mcp_apps_scaffold`. When `false`, the
hook, the CI job, and the CLAUDE.md gate line are not rendered.

### 2. Local advisory full-repo audit — non-blocking

**Delivery: documented commands only** (no vendored script → zero cross-repo sync
burden; each analyzer optional and degrades gracefully if absent). CLAUDE.md.jinja
documents on-demand invocations:

```bash
uv run --with radon python -m radon cc -s -n C src/    # complexity hotspots
uv run --with radon python -m radon mi -s src/         # maintainability index
uv run --with vulture vulture src/                     # dead-code candidates
```

CLAUDE.md states **when** to run (before substantial work in an unfamiliar area;
when about to touch a flagged module) and **what to do** with the output:

- File a **refactor-later issue** (using the decay template below, via the
  writing-issues skill) for a **tier-1 hotspot**, an **extreme single-function
  complexity outlier**, or a **god-class**.
- **Never fix inline** — that is scope creep.
- **vulture findings need confirmation** before action (it over-reports on
  importable/decorated/framework-registered code); keep a whitelist.

Raw analyzer output without churn weighting is the accepted tradeoff for
commands-only delivery; churn × complexity hotspot fusion belongs with Spec 2's
baseline.

### 3. Eyes — qualitative, in CLAUDE.md.jinja

Added to the generated project's CLAUDE.md (the gate routine integrates into the
existing **Hard PR Acceptance Gates** / **Pre-commit Hooks** sections):

- **Local-shape rules** — concrete and checkable: function length, nesting depth,
  parameter count ≤ 5, "a new responsibility is a new collaborator, not a longer
  class".
- **Full local-gate routine names every gate inline** — ruff (check then format),
  mypy, pytest, diff-cover patch coverage, **and the structural diff command** —
  so the agent knows the structural gate exists even if hooks are not installed.
- **Signalling instruction** — when you notice decay that will *compound*
  (god class forming, dead branch, leaking abstraction, a name no longer matching
  behaviour) **outside the scope of the current change**, neither fix it inline
  (scope creep) nor pass over it silently: open an issue. Constrained to "decay
  that will compound", not "anything imperfect".
- **Decay-issue template** — What / Where / Why it compounds / Suggested direction.
- **Ownership statement** — the diff-gate blocks new code; pre-existing problems
  get filed as refactor-later issues. **No forward reference** to the deferred
  Spec 2 ratchet; the prose is self-contained and reviewable on its own.

## Testing (TDD; runs inside the smoke gate)

A new `tests/test_structural_gate.py.jinja` (skipped/absent when
`enable_structural_gate` is `false`):

1. **Two-tier proof** — a deliberately over-complex snippet fires the structural
   rule under `--extend-select=<STRUCTURAL>` but **not** under the project's base
   config. Guards the core invariant (strict-on-diff, lenient-on-repo) and that
   the structural rules are never accidentally promoted into the whole-repo
   `select`.
2. **`--options` argv-splitting** — an empirical red test that ruff actually
   *receives* the extended rules through `diff-quality --options`. This closes the
   `vale_flags`-class quoting trap (a string passed to a tool that splits it into
   argv): write the failing test first, confirm the splitting behaviour, then wire
   the hook/CI to match exactly.
3. **Pre-push wiring** — rendered `.pre-commit-config.yaml` contains the
   `structural-diff-gate` hook with `stages: [pre-push]` and the file declares
   `default_install_hook_types: [pre-commit, pre-push]`.
4. **CI wiring** — rendered `.github/workflows/ci.yml` contains the `structure`
   job invoking `diff-quality` with `--extend-select`.
5. **Doc/hook anti-drift** — rendered `CLAUDE.md` local-gate routine contains the
   structural command, so the documented command and the hook command cannot
   silently diverge.

## Failure modes tracked

- **Ordering** — the base branch must be fetched before `diff-quality` runs in CI,
  or the compare resolves against a missing/stale ref. Mirrors the existing
  diff-cover "fetch base branch" step.
- **`S` in tests** — `S101` (assert) and friends would fire on new test lines.
  Rendered `pyproject.toml` `[tool.ruff.lint.per-file-ignores]` adds the test-only
  `S` ignores (no-op for the base select, active for the diff pass).
- **No-diff renders** — in template-ci's smoke render there is no PR diff →
  `diff-quality` reports 100% → passes (step present but inert). Correct.
- **Hook not installed** — if `pre-commit install` was skipped, the pre-push hook
  is silent; CI still catches the violation, and CLAUDE.md's documented command is
  the manual fallback. Bootstrap installs hooks; implementation confirms it picks
  up the `pre-push` type via `default_install_hook_types`.
- **Stale `origin/main` at push** — the hook compares against the local
  `origin/main` ref without fetching (no network in hooks). Minor staleness
  possible; CI does the authoritative fetch+compare.

## Policy decisions (settled)

- `--fail-under=100` — zero new structural violations on the diff; `# noqa` is the
  escape hatch.
- **Non-zero-exit hard-fail** (not a soft commit status) — so the *one* command is
  byte-identical as pre-push hook and CI gate. The `codecov/patch` soft-status
  pattern cannot run in a hook and would break local/CI parity.
- **Documented commands only** for the advisory audit — no vendored `audit.py`.

## Out of scope (Spec 2)

Committed `structural-baseline.json`; automated, deduped, capped issue filing in
CI; ratchet that tightens ceilings after genuine improvement; churn × complexity
hotspot fusion. Also out of scope for both specs: applying the layer to this
template repo's own `scripts/` (generated projects only).
