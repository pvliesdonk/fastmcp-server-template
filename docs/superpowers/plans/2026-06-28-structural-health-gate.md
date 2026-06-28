# Structural-health gate (Spec 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a diff-scoped structural-health layer into generated projects — a blocking structural diff-gate (pre-push hook + CI backstop), a documented local advisory audit, and CLAUDE.md agent "eyes" — so agent-authored code can't grow structural debt and the agent reproduces every gate locally before CI.

**Architecture:** Strict structural ruff rules (`C901`, `PLR0904`, `PLR0911-0915`, `S`) are applied **only to the diff** via `diff-quality --violations=ruff.check --options=--extend-select=...`, never added to the whole-repo `ruff check` (so existing downstream code stays green). The same one command runs as a pre-push `pre-commit` hook (local-first) and a PR-only CI `structure` job (backstop). The whole feature is gated behind a `copier.yml` toggle `enable_structural_gate`.

**Tech Stack:** copier/jinja templating; `diff_cover`'s `diff-quality` (already in the generated project's `dev` group); ruff; pre-commit; GitHub Actions; pytest. Advisory analyzers (`radon`, `vulture`) are invoked on-demand via `uv run --with`, not added as dependencies.

**Spec:** `docs/superpowers/specs/2026-06-28-structural-health-gate-design.md`

## Global Constraints

- **Target = the generated project**, edited via `.jinja` files. This repo's own code is out of scope.
- **Python floor `>=3.11`**; jinja workflow files MUST wrap every `${{ ... }}` GitHub expression in `{% raw %}...{% endraw %}` (existing `ci.yml.jinja` convention).
- **Copier reads the git index, not the working tree.** To test a change you MUST commit it first (or `git commit --amend --no-edit`) and render with `--vcs-ref=HEAD`. Uncommitted edits render as empty.
- **Everything new is gated behind `enable_structural_gate`** (`bool`, default `true`). When `false`: no hook, no CI job, no gate command in CLAUDE.md, and `tests/test_structural_gate.py` is not rendered (conditional filename).
- **Canonical structural select string — byte-identical in all three sites** (pre-commit hook, CI job, CLAUDE.md command): `C901,PLR0904,PLR0911,PLR0912,PLR0913,PLR0914,PLR0915,S`
- **Gate policy:** `--fail-under=100`, non-zero-exit hard-fail. `# noqa` is the escape hatch.
- **THE RENDER+TEST LOOP** (referenced as "run the loop" in steps below). Run from this repo root after committing your jinja edits:
  ```bash
  rm -rf /tmp/smoke
  uv run --no-project --with copier copier copy --trust --defaults \
    --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
  cd /tmp/smoke && uv sync --all-extras --all-groups
  ```
  Then run the named test, e.g. `uv run pytest tests/test_structural_gate.py -v`. Return to the repo root (`cd -`) before the next edit.
- **Toggle-off render check** (run once at the end of each task that adds a conditional): render a second smoke with `enable_structural_gate: false` overriding the data file and confirm the gated artifact is absent:
  ```bash
  rm -rf /tmp/smoke-off
  uv run --no-project --with copier copier copy --trust --defaults --vcs-ref=HEAD \
    --data-file tests/fixtures/smoke-answers.yml --data enable_structural_gate=false . /tmp/smoke-off
  ```

---

## File Structure

- `copier.yml` — **modify**: add `enable_structural_gate` toggle.
- `tests/fixtures/smoke-answers.yml` — **modify**: add `enable_structural_gate: true`.
- `pyproject.toml.jinja` — **modify**: add `[tool.ruff.lint.mccabe]`/`[tool.ruff.lint.pylint]` threshold constants and a template-managed `tests/**` `S` per-file-ignore, both toggle-gated.
- `.pre-commit-config.yaml.jinja` — **modify**: add `default_install_hook_types` + the `structural-diff-gate` pre-push hook (toggle-gated).
- `.github/workflows/ci.yml.jinja` — **modify**: add the `structure` job (toggle-gated).
- `CLAUDE.md.jinja` — **modify**: gate command in the acceptance-gates + pre-commit sections; new "Structural health" section (local-shape rules, advisory audit commands, signalling instruction, decay-issue template).
- `tests/{% raw %}{% if enable_structural_gate %}{% endraw %}test_structural_gate.py{% raw %}{% endif %}{% endraw %}.jinja` — **create**: the behavioral + wiring + anti-drift tests.

---

## Task 1: Two-tier structural selection (mechanism + proof)

Establishes the toggle, the ruff threshold config the diff-pass reads, and proves the core invariant: the structural rules fire as an **overlay** (`--extend-select`) but are absent from the base whole-repo config.

**Files:**
- Modify: `copier.yml` (append toggle)
- Modify: `tests/fixtures/smoke-answers.yml`
- Modify: `pyproject.toml.jinja` (ruff threshold blocks + test S-ignore)
- Create: `tests/{% raw %}{% if enable_structural_gate %}{% endraw %}test_structural_gate.py{% raw %}{% endif %}{% endraw %}.jinja`

**Interfaces:**
- Produces: the rendered `tests/test_structural_gate.py` module (later tasks add tests to the **same** file); the canonical select string constant `STRUCTURAL = "C901,PLR0904,PLR0911,PLR0912,PLR0913,PLR0914,PLR0915,S"` defined at module top and reused by later tasks.

- [ ] **Step 1: Add the copier toggle**

In `copier.yml`, append after the `enable_authorization` block:

```yaml
enable_structural_gate:
  type: bool
  default: true
  help: "Scaffold the diff-scoped structural-health gate: strict ruff structural rules (complexity, god-class, too-many-*, security) enforced on changed lines only via diff-quality, as a pre-push hook and a CI 'structure' job, plus the CLAUDE.md structural-health guidance (local-shape rules, advisory radon/vulture audit, decay-issue template). New code is held to the bar; pre-existing code is never blocked. Leave on unless a project deliberately opts out of structural enforcement."
```

- [ ] **Step 2: Exercise the toggle in the smoke render**

In `tests/fixtures/smoke-answers.yml`, append:

```yaml
enable_structural_gate: true
```

- [ ] **Step 3: Write the failing test (two-tier proof)**

Create `tests/{% raw %}{% if enable_structural_gate %}{% endraw %}test_structural_gate.py{% raw %}{% endif %}{% endraw %}.jinja` with:

```python
"""Structural-health gate: behavioural, wiring, and anti-drift tests.

These run inside the generated project's suite (and every downstream's CI),
continuously verifying the diff-scoped structural gate actually enforces what
the template intends. Only rendered when ``enable_structural_gate`` is true.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Canonical structural ruff selection — MUST stay byte-identical to the string
# in .pre-commit-config.yaml, .github/workflows/ci.yml, and CLAUDE.md. The
# anti-drift test in this module enforces that.
STRUCTURAL = "C901,PLR0904,PLR0911,PLR0912,PLR0913,PLR0914,PLR0915,S"

REPO_ROOT = Path(__file__).resolve().parents[1]

# A function whose cyclomatic complexity exceeds the mccabe default (10): a
# long if/elif chain. Written to a temp file and linted via subprocess so this
# test module itself stays simple (and never trips the gate it is testing).
OVER_COMPLEX = '''
def tangled(n):
    if n == 1:
        return 1
    elif n == 2:
        return 2
    elif n == 3:
        return 3
    elif n == 4:
        return 4
    elif n == 5:
        return 5
    elif n == 6:
        return 6
    elif n == 7:
        return 7
    elif n == 8:
        return 8
    elif n == 9:
        return 9
    elif n == 10:
        return 10
    elif n == 11:
        return 11
    return 0
'''


def _ruff(args: list[str], target: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--output-format", "concise", *args, str(target)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def test_structural_rule_fires_only_as_overlay(tmp_path: Path) -> None:
    """C901 fires under --extend-select but NOT under the base project config.

    Guards the core invariant: strict-on-diff, lenient-on-repo. If someone
    promotes these rules into the whole-repo `select`, the base run starts
    reporting C901 and this test fails.
    """
    target = tmp_path / "snippet.py"
    target.write_text(OVER_COMPLEX)

    overlay = _ruff([f"--extend-select={STRUCTURAL}"], target)
    base = _ruff([], target)

    assert "C901" in overlay.stdout, f"overlay should flag C901:\n{overlay.stdout}"
    assert "C901" not in base.stdout, f"base config must NOT flag C901:\n{base.stdout}"
```

- [ ] **Step 4: Commit, render, and verify the test FAILS**

```bash
git add copier.yml tests/fixtures/smoke-answers.yml "tests/{% raw %}{% if enable_structural_gate %}{% endraw %}test_structural_gate.py{% raw %}{% endif %}{% endraw %}.jinja"
git commit -m "test: two-tier structural selection proof (RED)"
```

Run the loop, then:

```bash
uv run pytest tests/test_structural_gate.py::test_structural_rule_fires_only_as_overlay -v
```

Expected: FAIL — `C901` appears in `base.stdout` only if mccabe is misconfigured, but more likely the test errors because `max-complexity` isn't set yet so C901 (even via overlay) may not fire at complexity 12 if the default differs, OR passes spuriously. The intent of RED here: the threshold config in Step 5 makes the overlay deterministic. If it already passes, proceed — Step 5 still locks the thresholds explicitly.

- [ ] **Step 5: Add the ruff threshold constants + test S-ignore (toggle-gated)**

In `pyproject.toml.jinja`, inside `[tool.ruff.lint.per-file-ignores]`, immediately **after** the header comment block and **before** the `# PROJECT-RUFF-IGNORES-START` sentinel, add:

```jinja
{%- raw %}{% endraw %}{% if enable_structural_gate %}
# Template-managed: the structural diff-gate adds `S` (security) on the diff
# pass; assert-based tests would trip S101. Scoped to tests/ so production code
# is still security-linted on the diff. No-op for the base whole-repo select
# (which excludes S).
"tests/**" = ["S101"]
{% endif %}
```

Then, after the `[tool.ruff.format]` block (before `[tool.pytest.ini_options]`), add:

```jinja
{% if enable_structural_gate %}
# Structural-gate thresholds. These rules are NOT in the whole-repo `select`
# above — they apply only on the diff via the structural gate's
# `--extend-select` (see .pre-commit-config.yaml / ci.yml). Values are ruff
# defaults, surfaced here as editable policy constants.
[tool.ruff.lint.mccabe]
max-complexity = 10

[tool.ruff.lint.pylint]
max-args = 5
max-branches = 12
max-returns = 6
max-statements = 50
{% endif %}
```

- [ ] **Step 6: Commit, render, and verify the test PASSES**

```bash
git add pyproject.toml.jinja
git commit -m "feat(scaffold): two-tier structural ruff selection + thresholds"
```

Run the loop, then:

```bash
uv run pytest tests/test_structural_gate.py::test_structural_rule_fires_only_as_overlay -v
```

Expected: PASS — overlay flags `C901`, base does not.

- [ ] **Step 7: Verify toggle-off render omits the test file and ruff blocks**

Run the toggle-off render (Global Constraints), then:

```bash
test ! -f /tmp/smoke-off/tests/test_structural_gate.py && echo "OK: test file absent"
grep -q "tool.ruff.lint.mccabe" /tmp/smoke-off/pyproject.toml && echo "FAIL: mccabe present" || echo "OK: thresholds absent"
```

Expected: both `OK`.

- [ ] **Step 8: Squash-commit the task**

```bash
git reset --soft HEAD~2 && git commit -m "feat(scaffold): two-tier structural ruff selection (gate Task 1)

Add enable_structural_gate toggle; ship structural ruff thresholds applied
only via the diff-gate overlay (not the whole-repo select); prove the
overlay-only invariant with a rendered test."
```

---

## Task 2: Diff-quality end-to-end + pre-push hook

Proves the `--options` argv-splitting (the `vale_flags`-class trap) end-to-end, then wires the local-first pre-push hook.

**Files:**
- Modify: `.pre-commit-config.yaml.jinja`
- Modify: `tests/test_structural_gate.py.jinja` (add tests to the existing file)

**Interfaces:**
- Consumes: `STRUCTURAL` constant and `REPO_ROOT` from Task 1's module.
- Produces: the rendered `.pre-commit-config.yaml` with a `structural-diff-gate` hook and `default_install_hook_types: [pre-commit, pre-push]`.

- [ ] **Step 1: Write the failing end-to-end test (the `--options` trap)**

Append to `tests/test_structural_gate.py.jinja`:

```python
def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def _diff_quality(repo: Path, extend: bool) -> subprocess.CompletedProcess[str]:
    cmd = [
        sys.executable,
        "-m",
        "diff_cover.diff_quality_tool",
        "--violations=ruff.check",
        "--compare-branch=main",
        "--fail-under=100",
    ]
    if extend:
        # EXACTLY the argv element a shell produces from the hook's
        # --options="--extend-select=..." — this is the splitting under test.
        cmd.append(f"--options=--extend-select={STRUCTURAL}")
    return subprocess.run(cmd, cwd=repo, capture_output=True, text=True)


def test_options_reach_ruff_and_gate_is_diff_scoped(tmp_path: Path) -> None:
    """A new over-complex function fails the gate ONLY with the structural
    overlay passed through diff-quality --options; a clean base run passes.

    Proves three things at once: (1) --options actually reaches ruff,
    (2) the diff scoping works, (3) without the overlay the same diff passes.
    """
    repo = tmp_path / "proj"
    repo.mkdir()
    _git(["init", "-b", "main"], repo)
    (repo / "base.py").write_text("x = 1\n")
    _git(["add", "."], repo)
    _git(["commit", "-m", "base"], repo)

    _git(["checkout", "-b", "feature"], repo)
    (repo / "tangled.py").write_text(OVER_COMPLEX)
    _git(["add", "."], repo)
    _git(["commit", "-m", "add tangled"], repo)

    with_overlay = _diff_quality(repo, extend=True)
    without_overlay = _diff_quality(repo, extend=False)

    assert with_overlay.returncode != 0, (
        "structural overlay must fail the diff gate:\n"
        f"{with_overlay.stdout}\n{with_overlay.stderr}"
    )
    assert without_overlay.returncode == 0, (
        "base ruff (no structural overlay) must pass the same diff:\n"
        f"{without_overlay.stdout}\n{without_overlay.stderr}"
    )
```

- [ ] **Step 2: Commit, render, verify it FAILS for the right reason**

```bash
git add tests/test_structural_gate.py.jinja
git commit -m "test: diff-quality --options end-to-end gate (RED)"
```

Run the loop, then:

```bash
uv run pytest tests/test_structural_gate.py::test_options_reach_ruff_and_gate_is_diff_scoped -v
```

Expected: this test should actually **PASS** once rendered, because it exercises `diff-quality` directly (no template wiring needed yet). It is the executable proof that the `--options=--extend-select=...` form works. If it FAILS, the `--options` form is wrong — fix the `cmd.append(...)` form here and mirror the corrected form into Step 3's hook before proceeding. Do not continue past a failing version of this test.

- [ ] **Step 3: Add the pre-push hook**

In `.pre-commit-config.yaml.jinja`, add at the very top of the file (before `repos:`):

```jinja
{% if enable_structural_gate %}
# `pre-commit install` wires both stages so the pre-push structural gate is
# installed alongside the commit-time hooks.
default_install_hook_types: [pre-commit, pre-push]
{% endif %}
```

Then, inside the first `- repo: local` block's `hooks:` list (after the `mypy` hook), add:

```jinja
{% if enable_structural_gate %}
      # Structural-health gate: strict ruff structural rules on CHANGED LINES
      # ONLY (diff vs origin/main), mirroring the CI `structure` job exactly.
      # bash -c so the shell — not pre-commit's arg splitter — owns the
      # --options quoting. Pre-push (not commit-time): a commit has no base to
      # compare and may be partial; pre-push sees the full branch range CI checks.
      - id: structural-diff-gate
        name: structural quality (diff vs origin/main)
        entry: bash -c 'uv run diff-quality --violations=ruff.check --options="--extend-select=C901,PLR0904,PLR0911,PLR0912,PLR0913,PLR0914,PLR0915,S" --compare-branch=origin/main --fail-under=100'
        language: system
        pass_filenames: false
        stages: [pre-push]
{% endif %}
```

- [ ] **Step 4: Write the wiring-presence test**

Append to `tests/test_structural_gate.py.jinja`:

```python
def test_precommit_config_wires_pre_push_hook() -> None:
    text = (REPO_ROOT / ".pre-commit-config.yaml").read_text()
    assert "default_install_hook_types: [pre-commit, pre-push]" in text
    assert "id: structural-diff-gate" in text
    assert "stages: [pre-push]" in text
    assert f"--extend-select={STRUCTURAL}" in text
```

- [ ] **Step 5: Commit, render, verify both tests PASS**

```bash
git add .pre-commit-config.yaml.jinja tests/test_structural_gate.py.jinja
git commit -m "feat(scaffold): structural diff-gate pre-push hook"
```

Run the loop, then:

```bash
uv run pytest tests/test_structural_gate.py -k "options_reach_ruff or pre_push_hook" -v
```

Expected: both PASS.

- [ ] **Step 6: Verify toggle-off render omits the hook**

Run the toggle-off render, then:

```bash
grep -q "structural-diff-gate" /tmp/smoke-off/.pre-commit-config.yaml && echo "FAIL" || echo "OK: hook absent"
```

Expected: `OK`.

- [ ] **Step 7: Squash-commit the task**

```bash
git reset --soft HEAD~3 && git commit -m "feat(scaffold): local-first structural diff-gate pre-push hook (gate Task 2)

Prove diff-quality --options reaches ruff and scopes to the diff (the
vale_flags-class quoting trap, closed end-to-end), then wire the pre-push
hook + default_install_hook_types so the agent hits the same gate CI runs."
```

---

## Task 3: CI `structure` job (backstop)

**Files:**
- Modify: `.github/workflows/ci.yml.jinja`
- Modify: `tests/test_structural_gate.py.jinja`

**Interfaces:**
- Consumes: `STRUCTURAL`, `REPO_ROOT`.
- Produces: rendered `.github/workflows/ci.yml` with a PR-only `structure` job.

- [ ] **Step 1: Write the failing CI-wiring test**

Append to `tests/test_structural_gate.py.jinja`:

```python
def test_ci_has_structure_job() -> None:
    text = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text()
    assert "structure:" in text
    assert "diff-quality" in text
    assert f"--extend-select={STRUCTURAL}" in text
    # PR-only, like the diff-cover patch-coverage steps.
    assert "github.event_name == 'pull_request'" in text
```

- [ ] **Step 2: Commit, render, verify it FAILS**

```bash
git add tests/test_structural_gate.py.jinja
git commit -m "test: CI structure job wiring (RED)"
```

Run the loop, then:

```bash
uv run pytest tests/test_structural_gate.py::test_ci_has_structure_job -v
```

Expected: FAIL — `structure:` not found.

- [ ] **Step 3: Add the `structure` job**

In `.github/workflows/ci.yml.jinja`, append at the end of the `jobs:` block (after the `vale:` job), preserving two-space indentation:

```jinja
{% if enable_structural_gate %}

  structure:
    name: Structural Quality (diff)
    runs-on: ubuntu-latest
    timeout-minutes: 10
    # Diff-scoped, so only meaningful on a PR (needs a base branch to compare).
    if: github.event_name == 'pull_request'
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@v7
        with:
          fetch-depth: 0

      - name: Install uv
        uses: astral-sh/setup-uv@v8.2.0
        with:
          version: "latest"

      - name: Cache Python interpreter
        uses: actions/cache@v6
        with:
          path: ~/.local/share/uv/python
          key: uv-python-3.12-{% raw %}${{ runner.os }}{% endraw %}

      - name: Set up Python
        run: uv python install 3.12

      - name: Install dependencies
        run: uv sync --all-extras --all-groups

      - name: Fetch base branch
        run: git fetch origin {% raw %}${{ github.base_ref }}{% endraw %} --depth=50

      - name: Structural quality (changed lines only)
        env:
          BASE_REF: {% raw %}${{ github.base_ref }}{% endraw %}
        run: |
          # Skip when the diff touches no Python — mirrors the diff-cover guard.
          HAS_PY=$(git diff --name-only "origin/${BASE_REF}...HEAD" | grep -c '\.py$' || true)
          if [ "$HAS_PY" -eq 0 ]; then
            echo "No Python source changes — skipping structural diff gate"
            exit 0
          fi
          uv run diff-quality --violations=ruff.check \
            --options="--extend-select=C901,PLR0904,PLR0911,PLR0912,PLR0913,PLR0914,PLR0915,S" \
            --compare-branch="origin/${BASE_REF}" --fail-under=100
{% endif %}
```

- [ ] **Step 4: Commit, render, verify the test PASSES**

```bash
git add .github/workflows/ci.yml.jinja
git commit -m "feat(scaffold): CI structure job (structural diff backstop)"
```

Run the loop, then:

```bash
uv run pytest tests/test_structural_gate.py::test_ci_has_structure_job -v
```

Expected: PASS.

- [ ] **Step 5: Validate the rendered workflow is well-formed YAML**

```bash
uv run --no-project --with pyyaml python -c "import yaml,sys; yaml.safe_load(open('/tmp/smoke/.github/workflows/ci.yml')); print('OK: ci.yml parses')"
```

Expected: `OK: ci.yml parses`. (Catches a stray jinja/indentation error in the appended job.)

- [ ] **Step 6: Verify toggle-off render omits the job**

```bash
grep -q "Structural Quality (diff)" /tmp/smoke-off/.github/workflows/ci.yml && echo "FAIL" || echo "OK: job absent"
```

Expected: `OK`.

- [ ] **Step 7: Squash-commit the task**

```bash
git reset --soft HEAD~2 && git commit -m "feat(scaffold): CI structure job as structural diff backstop (gate Task 3)"
```

---

## Task 4: CLAUDE.md eyes, advisory audit, gate docs + anti-drift test

Documents the gate in the local routine (so the agent knows it exists), adds the local-shape rules + signalling instruction + decay-issue template + advisory audit commands, and locks the three structural select strings against drift.

**Files:**
- Modify: `CLAUDE.md.jinja`
- Modify: `tests/test_structural_gate.py.jinja`

**Interfaces:**
- Consumes: `STRUCTURAL`, `REPO_ROOT`.
- Produces: a self-contained "Structural health" section in the rendered `CLAUDE.md`; no forward references to Spec 2.

- [ ] **Step 1: Write the failing docs + anti-drift tests**

Append to `tests/test_structural_gate.py.jinja`:

```python
def test_claudemd_documents_the_gate_command() -> None:
    text = (REPO_ROOT / "CLAUDE.md").read_text()
    assert "diff-quality" in text
    assert f"--extend-select={STRUCTURAL}" in text
    # Advisory audit + eyes content present.
    assert "radon" in text and "vulture" in text
    assert "Why it compounds" in text  # decay-issue template marker


def test_structural_select_string_is_identical_across_surfaces() -> None:
    """The select string lives in three rendered files; drift between them is a
    silent gate weakening. Assert all three carry the canonical string verbatim.
    """
    needle = f"--extend-select={STRUCTURAL}"
    precommit = (REPO_ROOT / ".pre-commit-config.yaml").read_text()
    ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text()
    claudemd = (REPO_ROOT / "CLAUDE.md").read_text()
    for name, text in [("pre-commit", precommit), ("ci", ci), ("CLAUDE.md", claudemd)]:
        assert needle in text, f"{name} missing canonical structural select"
```

- [ ] **Step 2: Commit, render, verify they FAIL**

```bash
git add tests/test_structural_gate.py.jinja
git commit -m "test: CLAUDE.md gate docs + structural-select anti-drift (RED)"
```

Run the loop, then:

```bash
uv run pytest tests/test_structural_gate.py -k "claudemd or identical_across" -v
```

Expected: both FAIL (CLAUDE.md has no structural content yet).

- [ ] **Step 3: Add the gate to the acceptance-gates + pre-commit sections**

In `CLAUDE.md.jinja`, in the `## Hard PR Acceptance Gates` list, add a new numbered item after the patch-coverage item (item 4):

```jinja
{% if enable_structural_gate %}
5. **Structural quality (diff) passes** — new/changed code must introduce no new structural violations (complexity, god-class, too-many-*, security). Enforced on the diff only, so pre-existing code is never blocked. Run before pushing:
   ```bash
   uv run diff-quality --violations=ruff.check \
     --options="--extend-select=C901,PLR0904,PLR0911,PLR0912,PLR0913,PLR0914,PLR0915,S" \
     --compare-branch=origin/main --fail-under=100
   ```
   `# noqa: C901` (etc.) with a one-line justification is the escape hatch for genuinely irreducible new code.
{% endif %}
```

In the `## Pre-commit Hooks` section, after the "Run on demand" bullet, add:

```jinja
{% if enable_structural_gate %}
- **Structural gate runs at push time:** the `structural-diff-gate` hook (pre-push stage) runs the command above automatically. `uv run pre-commit install` wires it via `default_install_hook_types`. A clean local push implies a clean CI `structure` job — same command, same range.
{% endif %}
```

- [ ] **Step 4: Add the "Structural health" section**

In `CLAUDE.md.jinja`, add a new top-level section (place it after the `## Pre-commit Hooks` section):

```jinja
{% if enable_structural_gate %}
## Structural health

The structural gate stops *new* debt; these practices and the advisory audit keep existing debt visible.

**Local-shape rules (checkable while you write):**

- Keep functions short and single-purpose; if a function needs a comment to explain a *section*, that section is a function.
- Nesting beyond ~3 levels is a smell — extract or invert/early-return.
- Five parameters is the ceiling; past it, pass an object or split the function.
- A new responsibility is a **new collaborator, not a longer class**. When a class grows a second reason to change, that reason belongs in its own unit.

**Advisory audit (on demand — run before substantial work in an unfamiliar area, or when about to touch a flagged module):**

```bash
uv run --with radon python -m radon cc -s -n C src/    # complexity hotspots (grade C+)
uv run --with radon python -m radon mi -s src/         # maintainability index
uv run --with vulture vulture src/                     # dead-code candidates
```

Each analyzer is optional and degrades gracefully if absent. `vulture` over-reports on importable/decorated/framework-registered code — **confirm before deleting** and keep a whitelist.

**When you notice decay outside the current change's scope** — a god class forming, a dead branch, a leaking abstraction, a name that no longer matches behaviour, or an audit hotspot — do **not** fix it inline (scope creep) and do **not** pass over it silently. **Open an issue** using this template:

> **What:** the structural problem in one sentence.
> **Where:** file/symbol and the metric or observation that flagged it.
> **Why it compounds:** what gets harder or riskier if it's left.
> **Suggested direction:** a starting point, not a prescribed refactor.

Constrain issues to **decay that will compound**, not anything imperfect. The diff-gate blocks new debt; these issues are the refactor-later backlog for pre-existing debt — neither blocks the current PR.
{% endif %}
```

- [ ] **Step 5: Commit, render, verify the tests PASS**

```bash
git add CLAUDE.md.jinja tests/test_structural_gate.py.jinja
git commit -m "docs(scaffold): CLAUDE.md structural-health guidance + anti-drift test"
```

Run the loop, then:

```bash
uv run pytest tests/test_structural_gate.py -v
```

Expected: ALL tests in the module PASS.

- [ ] **Step 6: Verify toggle-off render omits the structural section**

```bash
grep -q "## Structural health" /tmp/smoke-off/CLAUDE.md && echo "FAIL" || echo "OK: section absent"
```

Expected: `OK`.

- [ ] **Step 7: Squash-commit the task**

```bash
git reset --soft HEAD~2 && git commit -m "docs(scaffold): CLAUDE.md structural-health eyes + advisory + anti-drift (gate Task 4)"
```

---

## Task 5: Full gate verification

Confirms the rendered smoke project passes its **entire** gate (not just the new tests) with the feature on, and that `mkdocs`/lint are unaffected.

**Files:** none (verification only).

- [ ] **Step 1: Render and run the full generated gate**

Run the loop, then from `/tmp/smoke`:

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy src/ tests/
uv run pytest -x -q
```

Expected: all green. The new test module is type-checked by mypy (strict) and linted by ruff under the **base** config — confirm it passes both (it uses `from __future__ import annotations`, typed signatures, no `S`-selected base violations).

- [ ] **Step 2: Confirm pre-commit accepts the rendered config**

From `/tmp/smoke` (a git repo after copier init):

```bash
uv run pre-commit validate-config
uv run pre-commit install --install-hooks
git rev-parse --abbrev-ref HEAD >/dev/null && echo "pre-push hook installed:" && ls .git/hooks/pre-push
```

Expected: config valid; a `.git/hooks/pre-push` file exists (proves `default_install_hook_types` wired the stage).

- [ ] **Step 3: Final repo-root commit note**

No code change. Confirm the feature branch contains exactly four squashed feature commits (Tasks 1–4) plus this plan/spec, and that `git status` at the repo root is clean.

```bash
cd - && git log --oneline origin/main..HEAD
```

---

## Self-Review (completed by plan author)

**Spec coverage:**
- Diff-gate mechanism (diff-quality + extend-select, two-tier) → Tasks 1–2. ✓
- Pre-push hook + `default_install_hook_types` → Task 2. ✓
- CI `structure` backstop → Task 3. ✓
- `copier.yml` toggle → Task 1. ✓
- Thresholds as policy constants + `tests/` S-ignore → Task 1. ✓
- Advisory audit (documented commands) → Task 4. ✓
- Eyes: local-shape rules, signalling, decay-issue template, ownership → Task 4. ✓
- All five spec tests (two-tier, `--options` splitting, pre-push wiring, CI wiring, doc/hook anti-drift) → Tasks 1–4. ✓
- Failure modes (ordering/base fetch, S in tests, no-diff renders, hook-not-installed, stale origin/main) → handled in CI guard (Task 3), per-file-ignore (Task 1), CI `if` (Task 3), Task 5 hook-install check, and documented in CLAUDE.md (Task 4). ✓
- No forward references to Spec 2 in shipped prose → Task 4 prose is self-contained. ✓

**Placeholder scan:** no TBD/TODO/"handle edge cases"; every code step shows complete content. ✓

**Type consistency:** `STRUCTURAL`, `REPO_ROOT`, `_ruff`, `_git`, `_diff_quality`, `OVER_COMPLEX` defined in Task 1/2 and reused consistently; the canonical select string is identical everywhere (and Task 4 adds the test that enforces it). ✓
