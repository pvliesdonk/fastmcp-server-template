# Claude review-workflow hardening

**Date:** 2026-07-08
**Status:** Design — awaiting review
**Scope:** The template's two Claude GitHub workflows (`claude-code-review.yml.jinja`,
`claude.yml.jinja`) plus a new `REVIEW.md.jinja`. Rolls out to the four
downstream repos via `copier update`.

## Problem

The `claude-review` bot in downstream projects consistently complains about
four things (not all in every PR):

1. **"Running a custom command."** The reviewer runs the `code-review` plugin's
   `/code-review:code-review` slash command; the bot narrates this as a "custom
   command," which reads as a warning.
2. **Can't run the gate.** The bot reports it could not execute `pytest`/`ruff`/
   `mypy` ("Bash tool required approval for anything beyond basic git read
   commands") and falls back to static reading of the diff.
3. **Can't create inline comments.**
4. **Can't create commits to fix things itself.**

## Root-cause analysis (verified against upstream)

The complaints split cleanly across the two workflows, and three of the four are
concrete misconfigurations confirmed against the canonical
`anthropics/claude-code-action@v1` examples and the Claude Code docs
(`/en/github-actions`, `/en/code-review`).

| # | Workflow | Root cause | Canonical evidence |
|---|----------|-----------|--------------------|
| 3 (inline) | `claude-code-review.yml` | The reviewer sets **no `claude_args`**, so the inline-comment tool `mcp__github_inline_comment__create_inline_comment` — which is **not** in the default allow-set — is never granted. It cannot post inline. | `examples/pr-review-comprehensive.yml` allow-lists exactly that tool. |
| 2 (gate) | `claude-code-review.yml` | The reviewer is a **diff-correctness reviewer, not a gate-runner**. Upstream's review example allow-lists only `gh pr` tools — never `pytest`/`ruff`/`mypy`. The lament is the reviewer straying outside its lane, not a missing permission. | `/en/code-review` recommends telling the reviewer (via `REVIEW.md`) to skip "anything your CI already enforces like linting." |
| 1 (custom cmd) | `claude-code-review.yml` | `/code-review:code-review` is a **legitimate first-party plugin** (there is no built-in `/code-review` in the action runtime — it must be installed as a plugin). The "custom command" line is benign narration. | `/en/github-actions` "Using skills" shows the identical `plugins:` + `/code-review:code-review` invocation as the blessed pattern. |
| 3/4 (mention) | `claude.yml` (`@claude` responder) | Permissions diverged to `contents: read` / `pull-requests: read` / `issues: read`. Inline comments need `pull-requests: write`; commits need `contents: write`. | `examples/claude.yml` uses `contents: write`, `pull-requests: write`, `issues: write`. |

## Decisions

Locked with the user:

- **Keep the plugin** for the reviewer (tuned multi-agent review + verification +
  severity tags). Complaint #1 stays cosmetic-only.
- **Both** scope *and* investigate for #2: a `REVIEW.md` tells the reviewer not to
  reproduce CI, but it keeps a scoped Bash allow-list so it can run a *targeted*
  check to verify a single finding (freedom to investigate, not re-run the gate).
- **@claude responder gets full write** (`contents`/`pull-requests`/`issues:
  write`) — fixes #3 and #4 on mention.
- **Review depends on CI**, via **`pull_request` trigger + a wait-for-CI step**
  (keeps the canonical PR-context path the plugin/inline-posting is documented to
  support — avoids the off-canonical `workflow_run`-for-review risk). The review
  **only runs if CI passed**.

## Design

### 1 — `claude.yml.jinja` (the `@claude` responder)

Realign the `permissions:` block to the canonical `examples/claude.yml`:

```yaml
permissions:
  contents: write        # was read — enables commit fixes (#4)
  pull-requests: write   # was read — enables inline comments (#3)
  issues: write          # was read
  id-token: write
  actions: read
```

**Keep** the template's stricter fork-guard `if:` (the head-repo check on
`pull_request_review*` events) — that is deliberate hardening upstream lacks, not
drift. No other changes.

**Security note.** `claude-code-action` gates who can trigger it: it only acts for
users with write access to the repo (an @claude mention from a random external
commenter does not get a write token). The fork-context events are additionally
guarded by the `if:`. Granting write is the documented posture for the responder.

### 2 — `claude-code-review.yml.jinja` (the reviewer)

Keep the plugin invocation (`/code-review:code-review --comment <url>`,
`track_progress: true`, `display_report: true`). Add:

**a. The canonical allow-list** (fixes #3, enables targeted investigation):

```yaml
claude_args: |
  --allowedTools "mcp__github_inline_comment__create_inline_comment,Bash(gh pr comment:*),Bash(gh pr diff:*),Bash(gh pr view:*),Bash(gh run view:*),Bash(gh run list:*),Bash(uv run pytest:*),Bash(uv run mypy:*),Bash(uv run ruff:*)"
```

- `mcp__github_inline_comment__create_inline_comment` — the missing inline-comment
  tool (**#3**).
- `gh run view`/`gh run list` — **read** CI results instead of re-running them.
- `uv run pytest`/`mypy`/`ruff` — **freedom to investigate** one finding (scoped;
  `REVIEW.md` sets the norm that this is not for reproducing the gate).

**b. `actions: read`** added to the `permissions:` block so the reviewer can read
CI results. **Keep `contents: read`** — the reviewer must never commit.

**c. Environment setup** so the targeted `uv run` checks actually work — mirror
`ci.yml.jinja`'s lint job: `astral-sh/setup-uv@v8.2.0`, cache the interpreter,
`uv python install 3.12`, `uv sync --all-extras --all-groups`. (Cost: this adds
setup time to each review; accepted as the price of live investigation.)

**d. Trigger + CI gate** — replace the bare `pull_request` job with a
two-job structure so the review only runs after CI passes:

- Job `wait-for-ci`: on the same `pull_request` event, poll the **CI** workflow
  run for the PR **head SHA** until it completes, and emit
  `outputs.ci_passed = (conclusion == 'success')`.
- Job `review`: `needs: wait-for-ci`, `if: needs.wait-for-ci.outputs.ci_passed
  == 'true'`. If CI failed, the review is skipped **neutrally** (no scary red
  review check on the PR).

Prefer a **`gh`-based poll** (dependency-free, matches the template's ethos)
over a third-party wait-action, because polling the **workflow-run conclusion**
(not individual check names) is the only correct way to tolerate CI's
`continue-on-error` experimental 3.14 matrix job.

#### wait-for-ci failure modes (must be handled)

Per the project's failure-mode-enumeration discipline, the poll must address:

1. **Check-not-yet-created race** — the review job and CI start on the same
   event; the CI run for the head SHA may not exist yet when the poll begins.
   Poll with retry; "no run found yet" ≠ "passed."
2. **Wrong SHA** — check runs attach to `github.event.pull_request.head.sha`, not
   `github.sha` (the merge commit). Use the head SHA.
3. **Self-deadlock** — poll only the workflow **named `CI`**, never this review
   workflow, so it can't wait on itself.
4. **Experimental matrix job** — CI's Python 3.14 job is `continue-on-error:
   true`. Gating on the **run conclusion** (not per-check) correctly treats its
   failure as non-blocking.
5. **Timeout** — set a job `timeout-minutes` and a poll deadline; on timeout,
   emit `ci_passed=false` (skip the review) rather than idling forever.
6. **CI failed** — `ci_passed=false` → review skipped (the gating decision).
7. **CI never ran** (paths filter / skipped) — resolves via the timeout in (5) to
   a skip.

### 3 — new `REVIEW.md.jinja` → `REVIEW.md`

A repo-root `REVIEW.md` — read by the reviewer as highest-priority instructions —
following the same **template-owned + `DOMAIN` sentinel** pattern as
`CLAUDE.md.jinja` (NOT `_skip_if_exists`; a `<!-- DOMAIN-REVIEW-START/END -->`
block carries per-project rules that survive `copier update`, the rest is
template-owned and overwritten).

Fleet-wide (template-owned) content:

- **Don't reproduce CI.** CI already enforces ruff (lint + format), mypy, the
  pytest matrix, dependency audit, secret scan, Vale prose, and (if enabled) the
  structural gate. Do not report findings those checks already gate, and do not
  re-run the full gate. Read CI results (`gh run view`) when you need them.
- **Investigate narrowly.** You may run a single targeted command to confirm one
  specific hypothesis — not to re-execute the suite.
- **Focus.** Correctness, security, and regressions introduced by the diff.
- **Verification bar.** Behavior claims need a `file:line` citation, not an
  inference from naming.
- **Convergence.** After the first review, suppress repeat nits; post Important
  findings only.

Keep it short (the doc warns a long `REVIEW.md` dilutes the rules that matter).

### 4 — `CLAUDE.md.jinja` (generated project): document the CI dependency

Add a short line to a template-owned section of the generated project's
`CLAUDE.md` so contributors aren't surprised when no review appears on a red PR:

> The automated Claude review runs **only after CI passes** — if CI is red, no
> review is posted; fix CI and push, and the review runs on the next green run.

This keeps expectations aligned with the `wait-for-ci` gate (design §2d). One
sentence, in the template-owned CI/workflow area (not a `DOMAIN` block).

### copier.yml wiring

- **No `copier.yml` change is required.** Per the existing comment (~line 107),
  named root `.md` files render via `.jinja` precedence automatically:
  `REVIEW.md.jinja` renders to `REVIEW.md` in generated projects, while a plain
  `REVIEW.md` in the template repo stays template-only. Like `CLAUDE.md`,
  `REVIEW.md` is template-owned (NOT `_skip_if_exists`) with a `DOMAIN-REVIEW`
  sentinel block, so no `_skip_if_exists` / `_exclude` entry is needed.
- No new copier variable is required; `REVIEW.md` content is static plus the
  `DOMAIN-REVIEW` sentinel.

### Fix the class, not the instance

The template's **own** non-`.jinja` `.github/workflows/claude.yml` and
`claude-code-review.yml` carry the identical defects (the reviewer has no
`claude_args`, so the same inline-comment tool is missing). They are fixed in the
same PR — the `.jinja` (downstream) and non-`.jinja` (this repo's own) copies
move together. Two justified divergences between the twins: (1) the wait-for-CI
target is the `CI` workflow downstream and the `template-ci` workflow here; (2)
the reviewer's `pull_request` trigger matches each repo's CI trigger — the
downstream `.jinja` reviewer adds `branches: [main]` (downstream `ci.yml` is
main-only, so firing elsewhere would only idle the poll to timeout), while this
repo's reviewer keeps all-PR triggering (its `template-ci` runs on every PR).
A plain `REVIEW.md` is added at the template root alongside `REVIEW.md.jinja` so
this repo's own reviewer is scoped too.

## Testing & verification plan

Because running a plugin review + inline posting has moving parts, verify
empirically before rollout (do not trust static reasoning alone):

1. **Render gate** (per the template's `CLAUDE.md`): commit, render with
   `--vcs-ref=HEAD` and `smoke-answers.yml`, run the generated project's full
   local gate. Confirm `REVIEW.md`, both workflows, and `copier.yml` render
   cleanly and `template-ci` passes on 3.11–3.14.
2. **Live PR on the template's own generated smoke, or a canary downstream
   repo:** open a test PR and confirm, in order:
   - the review job **waits** for CI and is **skipped** when CI is red;
   - on green CI, the reviewer **posts inline comments** (proves the
     `mcp__github_inline_comment__create_inline_comment` grant is what the plugin
     uses — if the plugin posts by another path, adjust the allow-list);
   - the reviewer **reads CI results** rather than re-running the gate, and no
     longer emits the "couldn't run pytest" lament;
   - an `@claude` mention asking for a fix can **commit** and **comment inline**
     (proves the responder write perms).
3. Only after (2) passes, roll out downstream via `copier update`.

## Rollout

Template PR closes the tracking issue, then `copier update` to the four
downstream consumers (each a separate PR per the fleet-convergence process).
`REVIEW.md` lands as a new template-owned file; downstream per-repo review rules
go in the `DOMAIN-REVIEW` block.

## Out of scope

- The **managed Code Review service** (Claude GitHub App) is unavailable — it
  requires a Team/Enterprise plan, which this account does not have. The
  self-hosted GitHub Actions path in this spec is therefore the only option, not
  merely the chosen one.
- Switching the reviewer to a plain natural-language prompt (would erase the
  "custom command" narration but lose the tuned plugin pipeline) — rejected.
