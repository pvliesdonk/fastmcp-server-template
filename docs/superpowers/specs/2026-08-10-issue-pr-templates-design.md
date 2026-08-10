# Downstream issue/PR templates + contributing guide

**Date:** 2026-08-10
**Status:** Approved (design)
**Scope:** One implementation cycle — adds issue forms, a PR template, a contributing guide, and the label plumbing that makes them work, to the copier template so every downstream inherits them. The template repo (fastmcp-server-template) dogfoods the same files directly.

## Problem

Contributed issues on downstream MCP-server repos are unclear, incomplete, or
overclaim. Two failure modes dominate:

1. **Overclaimed cause** — the filer asserts a root cause they did not verify,
   presented as researched fact. The implementer inherits a false floor of
   confidence.
2. **Incomplete observation** — no concrete behaviour, no version/commit, no
   repro, so the issue is not actionable.

There are currently no issue templates, no PR template, and no contributing
guide rendered to downstream. Downstream filers (both Claude agent sessions and
human contributors) get no structure and no discipline cues.

## Goal

Ship a set of GitHub issue/PR templates that encode the writing-issues
discipline — observation not work order, uncertainty markers, one-issue-one-
problem — and a contributing guide that carries the same rules in prose, so
every downstream inherits them via `copier copy`/`copier update`, and the
template repo itself uses the same files.

## Approach

**Skeletal fields, discipline in the text.** Standard conventional fields with
light validation. The writing-issues rules live in the `description` and
`placeholder` prose of each form — not in heavy required-field machinery. The
cause field is explicitly labelled "do not claim a cause you did not verify";
unverified causes must carry the `[unverified]` marker and the sentence "I have
not verified the cause."

## Architecture

### Dogfooding: one source, two consumers

The seven content files (four issue forms, `config.yml`, PR template,
`CONTRIBUTING.md`) are **plain files with no Jinja substitution**. They are
correct for both the template repo and downstream because:

- "this repo" is contextually relative in the routing prose, and
- the upstream references (`pvliesdonk/fastmcp-pvl-core`,
  `pvliesdonk/fastmcp-server-template`) are already literal in `CLAUDE.md.jinja`
  — not substituted — and are literally true for the template repo too.

Plain files are copied verbatim by copier and are update-tracked (copier 3-way
merges non-Jinja files on `copier update`). They live in this repo's `.github/`
and repo root, so GitHub uses them for fastmcp-server-template directly, AND
copier copies them to every downstream. **Zero duplication, zero `_exclude`,
zero render step.**

This deliberately drops the originally-planned `{{ project_name }}`
substitution in the PR template and CONTRIBUTING.md: generic phrasing ("this
server", "this repo") works for both consumers, and avoiding substitution keeps
the files plain and shared.

### Files

| # | File | Type | Shared with this repo? |
|---|---|---|---|
| 1 | `.github/ISSUE_TEMPLATE/bug-report.yml` | plain `.yml`, new | yes |
| 2 | `.github/ISSUE_TEMPLATE/feature-request.yml` | plain `.yml`, new | yes |
| 3 | `.github/ISSUE_TEMPLATE/decay.yml` | plain `.yml`, new | yes |
| 4 | `.github/ISSUE_TEMPLATE/question.yml` | plain `.yml`, new | yes |
| 5 | `.github/ISSUE_TEMPLATE/config.yml` | plain `.yml`, new | yes |
| 6 | `.github/PULL_REQUEST_TEMPLATE.md` | plain `.md`, new | yes |
| 7 | `CONTRIBUTING.md` | plain `.md`, new | yes |
| 8 | `.github/workflows/bootstrap.yml.jinja` | edit (add label-create calls) | no — downstream only (existing jinja) |
| 9 | `.github/workflows/template-labels.yml` | plain `.yml`, new, **excluded via `_exclude`** | this repo only |
| 10 | `CLAUDE.md.jinja` §"Contributing fixes upstream" (line 258) | edit → pointer | no — downstream only |

All seven content files are **template-owned**: not in `_skip_if_exists`, so
`copier update` regenerates them — fleet-wide best-practice convergence is the
goal.

## Issue forms

Each form carries a top-level `labels:` and a short header `description` linking
to `CONTRIBUTING.md` (GitHub also auto-links CONTRIBUTING.md in the issue
chooser). Field list and the exact discipline text follow.

### bug-report.yml — `labels: ["bug"]`

- **What happened?** *(textarea, required)* — one sentence: expected vs actual.
  `placeholder: "A one-liner: 'expected X, got Y.'"`
- **Observed** *(textarea, required)* — concrete behaviour.
  `description:` "Describe what you actually saw. Paste the real error text or
  trace — not a summary of it. Include where it occurred."
- **Expected** *(textarea, required)* — what should have happened.
- **Reproduction** *(textarea, required)* — steps + version/commit.
  `description:` "Only include steps you actually ran and the version you
  actually checked."
- **Suspected cause** *(textarea, optional)* — **the discipline lives here.**
  `description:` "Do **not** claim a cause you did not verify. If you haven't
  checked, say so, mark the line `[unverified]`, and add the sentence 'I have
  not verified the cause.' If you did check, write `[verified: how]`."
- **Open questions / scope** *(textarea, optional)*.
  `description:` "Unknowns the implementer should verify (mark each
  `[unverified]`). What this issue is *not* about."

### feature-request.yml — `labels: ["feature"]`

- **What problem does this solve?** *(textarea, required)*.
  `description:` "Describe the problem or unmet need — not a solution. Who hits
  it, and when?"
- **Desired outcome** *(textarea, required)*.
  `description:` "Describe the outcome, not how to implement it."
- **Implementation ideas** *(textarea, optional)*.
  `description:` "Non-binding starting points only. This issue does not
  prescribe an implementation."

### decay.yml — `labels: ["decay"]`

Supersedes the inline decay block at `CLAUDE.md.jinja:89`. Header `description:`
"Constrain this to decay that will compound — not anything imperfect."

- **What** *(textarea, required)* — the structural problem in one sentence.
- **Where** *(textarea, required)* — file/symbol + the metric or observation
  that flagged it.
- **Why it compounds** *(textarea, required)* — what gets harder or riskier if
  left.
- **Suggested direction** *(textarea, optional)*.
  `description:` "A starting point, not a prescribed refactor."

### question.yml — `labels: ["question"]`

- **Question** *(textarea, required)*.
- **What I've already tried** *(textarea, optional)*.

### config.yml

```yaml
blank_issues_enabled: false
```

No `contact_links`. A project-specific docs-site contact link would require
Jinja and re-split the file; GitHub already surfaces CONTRIBUTING.md in the
chooser, so a docs link is YAGNI. `blank_issues_enabled: false` forces a choice
among the four forms — the discipline culture wants structure, and all common
issue kinds are covered.

## PR template — `.github/PULL_REQUEST_TEMPLATE.md`

Plain markdown, generic (no substitution). Sections:

- **Closes / Refs** — `Closes #N` (or `Refs #N`). Note: "No orphan PRs — create
  the issue first if none exists. Pure typo fixes and Renovate dependency bumps
  excepted."
- **What & why** — one or two sentences, observation framing.
- **What this PR deliberately does NOT do** — deferrals, each with its issue
  number. Encodes the honest-deferral rule.
- **Local review** — checkbox: "Ran a local code-review pass on the cumulative
  diff before `gh pr create`."
- **Docs impact** — mini-checklist: README, `docs/` site pages, `docs/design/`,
  inline docstrings. Mirrors the "Documentation Discipline" section of
  `CLAUDE.md.jinja`. Phrased to cover both a published mkdocs site (downstream)
  and internal docs (this repo).

## CONTRIBUTING.md

Plain markdown, shared. Carries the writing-issues discipline in prose:

- **Observation, not work order** — describe what was observed; do not
  diagnose, design, or prescribe.
- **The uncertainty rule** — every cause statement marked `[verified: how]` or
  `[unverified]`; unverified causes carry "I have not verified the cause."
- **One issue, one observed problem** — a second suspected problem gets its own
  issue; a suspected shared code path gets one `[unverified]` line here.
- **Remove before posting** — the common-mistakes list (no "root cause is X;
  fix by Y", no implementation steps, no "this could cause issues").
- **Upstream contributing routing** (three tiers, lifted from
  `CLAUDE.md.jinja:258`, now single-sourced here):
  - **Library-level fix** (`fastmcp_pvl_core`) → PR on `pvliesdonk/fastmcp-pvl-core`.
  - **Template-level fix** (template-owned files: Dockerfile, workflows,
    `server.py` skeleton, CLAUDE.md sections) → PR on
    `pvliesdonk/fastmcp-server-template`.
  - **Domain-only fix** (inside `DOMAIN-*`/`CONFIG-*`/`PROJECT-*` sentinel
    blocks, `tools.py`, `resources.py`, `prompts.py`, `domain.py`, `tests/`)
    → PR on this repo.
- A short pointer to the issue forms and the PR template.

## Labels

GitHub issue form `labels:` does **not** auto-create labels — a missing label is
silently skipped ([GitHub issue-form syntax][gh-forms]). So the four labels
must exist in each repo. Copier cannot ship labels (they are repo settings), so
two idempotent label-ensure halves:

[gh-forms]: https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms

### Downstream — extend `bootstrap.yml.jinja`

The existing `labels:` job already creates the `dependencies` label via
`gh label create --force` (its own comment notes "GitHub silently drops labels
that don't exist"). Add four calls alongside it:

```
gh label create bug        --color d73a4a --description "Something isn't working"          --force
gh label create feature    --color a2eeef --description "New feature or request"            --force
gh label create decay      --color fbca04 --description "Structural debt worth refactoring later" --force
gh label create question   --color d876e3 --description "Further information is requested"  --force
```

The job runs on push-to-main when `bootstrap.yml` changes, so the PR
introducing these labels self-triggers their creation.

### This repo — new `template-labels.yml`

`bootstrap.yml.jinja` is downstream-only; this repo has no label-ensure today.
New `.github/workflows/template-labels.yml` mirrors the `labels` job: ensures the
same four labels **plus** the `dependencies` label (Renovate needs it; same job,
idempotent either way). Excluded from downstream via `_exclude` (matches the
`template-*` convention). Triggers: `push` to `main` (on changes to
`template-labels.yml`) + `workflow_dispatch`. `permissions: issues: write`,
using `github.token`.

Label set is deliberately minimal: `bug`, `feature`, `decay`, `question` — no
`triage`. Adding `triage` to every form is a future enhancement, not in this
change.

## CLAUDE.md.jinja edit

The "Contributing fixes upstream" section (line 258) becomes a one-line pointer
to `CONTRIBUTING.md` and the new issue/PR templates. The three-tier routing
content moves to CONTRIBUTING.md as the single source. Minimal edit, removes
duplication. (This repo's own `CLAUDE.md` is separate and unchanged.)

## Render hygiene

- No Jinja in the seven content files → no `trim_blocks`/EOF-blank-line trap
  (issue #251), no `{% raw %}` needed.
- `scripts/check_render_hygiene.py` covers all rendered files; the new plain
  files must be trailing-whitespace/EOF-clean (they are written clean).
- `template-ci` self-test renders with smoke-answers and runs the downstream
  gate; the seven plain files appear in the render and pass hygiene. No Python
  added, so ruff/mypy/pytest are unaffected.
- CONTRIBUTING.md is **not** Vale-gated — the Vale file set is `docs/**` +
  `README.md`. Adding CONTRIBUTING.md to Vale is a separate `ci.yml.jinja` glob
  edit, noted as optional follow-up, not in this change.

## Failure modes addressed

- **Overclaimed cause** — the bug form's "Suspected cause" field description
  forbids unverified claims and requires the `[unverified]` marker + the
  explicit uncertainty sentence. CONTRIBUTING.md restates the rule in prose.
- **Incomplete observation** — required fields (Observed, Expected,
  Reproduction) force the concrete behaviour, exact text, and version/commit.
- **Prescribed implementation** — feature form separates "desired outcome"
  (required) from "implementation ideas" (optional, non-binding); issue
  templates carry no implementation steps.
- **Orphan PRs / silent deferral** — PR template requires `Closes #N` and a
  "deliberately does NOT do" section with issue numbers.

## Scope boundary (what this change is NOT)

- No `actions/labeler` or regex labeler workflow — form `labels:` + the two
  bootstrap/template-labels jobs cover it.
- No copier toggle (`enable_issue_templates`) — default-on; the four forms
  always render. A toggle is YAGNI until a downstream asks.
- No CONTRIBUTING.md Vale gating — optional follow-up.
- No `triage` label — minimal set now.
- No changes to this repo's own `CLAUDE.md` — separate, unchanged.
- The decay form supersedes the inline `CLAUDE.md.jinja:89` block only by making
  the CLAUDE.md.jinja section point at it; the form is the replacement.

## Verification

- `template-ci` renders the template with `tests/fixtures/smoke-answers.yml`
  and runs the downstream gate: hygiene, Vale (docs + README), ruff, mypy,
  pytest. All must pass.
- Render locally and confirm the seven plain files land verbatim in
  `/tmp/smoke/.github/ISSUE_TEMPLATE/`, `/tmp/smoke/.github/PULL_REQUEST_TEMPLATE.md`,
  and `/tmp/smoke/CONTRIBUTING.md`.
- Confirm `.github/workflows/template-labels.yml` does **not** appear in the
  smoke render (it is `_exclude`d).
- Confirm `bootstrap.yml` in the smoke render contains the four new
  `gh label create` calls.
- Confirm `CLAUDE.md.jinja`'s contributing section now points to CONTRIBUTING.md
  and no longer restates the three-tier routing.
