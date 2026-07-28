# PR B: run Vale over the render in template-ci

**Goal:** template CI fails when rendered prose carries a Vale error, and the detach-scrub guard covers every rule it claims to guard.

**Closes:** #270

**Spec:** `docs/superpowers/specs/2026-07-27-config-surface-1b-restructured-design.md` §3, §3.2, §4.1.

This plan states decisions and how each is verified. Exact edits belong in the execution, not here: PR A's 420-line recipe produced about twenty review findings against one in the prose it described.

## Scope

One file, `.github/workflows/template-ci.yml`. No template sources, no generator, no docs.

## Decisions

**D1 — the gate runs over the render, not the template repo.** `/tmp/smoke` already exists in the job; the linted set is what a downstream would receive.

**D2 — configuration is extracted, never restated.** `files`, `version` and the exclusion glob come from the rendered `.github/workflows/ci.yml` using the `awk '/^  vale:/{f=1}'` anchor the two existing lockstep steps use. #143/#159 settled that duplicating Vale's configuration lets two surfaces drift, making a finding visible to one and silent in the other. A gate that hardcodes `docs README.md` passes while linting a different set than the downstream it protects.

**D3 — assert zero, no baseline.** `main` is clean, so there is nothing to baseline. A baseline would also have to be maintained and retired.

**D4 — two variants, chosen for what they change in the linted set.** Corrected twice during review. The job's existing second render toggles `enable_structural_gate`, which nothing under `docs/` or `README.md` is conditioned on, so its prose is byte-identical and linting it buys nothing. `enable_authorization` is the flag that matters: off, it drops `docs/guides/authorization.md` entirely and changes both `README.md` and `docs/guides/authentication.md`. The gate renders that variant itself and lints both. The style packs are fetched once and copied, since the network fetch is the expensive part and both renders resolve the same `Packages` line.

**D5 — the strict run is advisory, not gating.** An accepted vocabulary term suppresses non-spelling rules inside its match span, so a plain zero can hide a flagged pattern. `main` is currently clean both ways. Gate on the plain run, which is what a downstream experiences; report the strict run without failing on it, so a suppressed pattern is visible without making a downstream's own vocabulary additions break template CI. Revisit if the advisory output proves noisy.

**D6 — both halves of the #199 pair per scrub rule.** Five substitution rules, four anchored; add the fifth. #199 pairs each anchor with a `check_replacement`, because absence of the old wording never proves the substitution fired, only that the text is gone. The fifth rule needs both.

**D7 — one matrix leg.** `render-and-gate` is a 4-wide Python matrix, and
Vale's result does not depend on the Python version while `vale sync`
downloads style packages on every run. The gate runs on `3.11` only. Decided
during execution; the alternative was a separate job that would have to
re-render.

## Verification

A gate that has never failed is untested. Each of these is run and its output recorded:

| Check | Expected |
|---|---|
| Inject an error into a rendered doc, run the job's Vale step | fails |
| Revert, re-run | passes |
| Reword the fifth anchor phrase in `CLAUDE.md.jinja`, run the anchor step | fails, naming that anchor |
| Revert, re-run | passes |
| Both render variants | 0 errors |
| Extracted `files`/`version`/glob | equal to the rendered `ci.yml`'s values |

The extraction check matters most: it is the one that silently degrades. Assert the extracted values are non-empty and match, so a future `ci.yml` restructure that breaks the `awk` anchor fails loudly rather than linting nothing.

## Traps from PR A

- Park `.vscode/` before any render, and add it to `.git/info/exclude` first. Untracked until PR G; a dirty tree makes copier mint a temp commit and `_commit` differs between two identical renders.
- `vale sync` after every fresh render, or vale exits `E100 [loadStyles]`.
- Run `check_render_hygiene.py` on a pristine render. `vale sync` and `uv sync` both write into the tree.
- `git reset --soft` leaves the index staged, so a selective `git add` after it is a no-op and the commit takes everything.

## Out of scope

- #267 (See also reference) and #268 (AST-scan wording) — assigned to PRs C and E.
- Making the gate strict by default. D5 defers it.
- The downstream `ci.yml` Vale job itself, which already works.
