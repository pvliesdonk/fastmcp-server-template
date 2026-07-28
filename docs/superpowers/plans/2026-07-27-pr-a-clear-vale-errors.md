# PR A: clear the rendered docs' Vale errors — execution record

**Status:** done. This records what was changed and what was learned. It is not
a recipe to re-run: re-executing it against a fresh render would be wrong,
because the lines it edited have already moved.

**Spec:** `docs/superpowers/specs/2026-07-27-config-surface-1b-restructured-design.md` (PR A in §3).
**Issue:** #266.

## What changed

Two authored `.jinja` files, 24 lines. No code, no CI, no generator.

| File | Change |
|---|---|
| `docs/guides/{% if enable_authorization %}authorization.md{% endif %}.jinja` | 19 Vale errors cleared across 7 rules |
| `docs/guides/config-migration.md.jinja` | 1 `ai-tells.OverusedVocabulary` cleared |

Verified: 0 Vale errors in the default and gate-off renders, renders
byte-identical, hygiene clean on both variants, `mkdocs build --strict` passes.

## Measured Vale behaviour

Probed against the live binary with this template's own ruleset. Each of these
contradicts what the rule name suggests, so they are recorded rather than
re-derived.

- **`ai-tells.EmDashUsage` flags an em dash at any spacing, and an en dash
  too.** `A—B` unspaced is an error. Keying a normaliser on the spaced form
  alone leaves failures behind.
- **`For example,` and `For instance,` both trip
  `ai-tells.FormalTransitions`.** Neither can replace `e.g.`. `such as` is
  clean, as is dropping the abbreviation and capitalising the next word.
- **Vale skips code spans and fenced blocks.** Wrapping a literal in backticks
  immunises it against `Vale.Spelling`, which is why a generated table's
  `Default` column should be a code span rather than bare prose.
- **Vale reports a subset.** Only 6 of this file's 11 spaced em dashes were
  reported, and the set shifted as edits landed. The exit criterion has to be
  "re-run until zero", not "fix the reported list".

## Constraints that governed the fix

- **Spelling errors were reworded, never accepted.** `.vale.ini` and
  `.vale/styles/config/vocabularies/Base/accept.txt` are both in
  `_skip_if_exists`, so a term added to either reaches new renders only and
  leaves an existing project red. That ruled out accepting `uncomment`,
  `IdP's`, `overridable` and `middleware`.
- **Replacement wording needs linting too.** Swapping `e.g.` for "for example"
  trades a `Google.Latin` error for a `FormalTransitions` one, and one rewrite
  introduced a fresh `Vale.Spelling` hit on "middleware". Both were caught by
  re-running Vale, not by reading.
- **Vale rewrites must not shed semantic force.** PR #145 established this and
  the maintainer applied it. Dropping the bold from `is **not** structural`
  removed the salience from the guide's one silent-failure warning; the
  negation moved off the copula instead, keeping the emphasis and clearing
  `ai-tells.EmphaticCopula`.
- **Downstream docs are operator-only.** `2a0e36d` deliberately purged the
  pvl-core API surface from this guide. A correction that reintroduced two of
  those symbols was reverted to a behavioural statement pointing at the stub.

## Deliberately not done

- **The `DOMAIN-AUTHZ-SCOPES-START` marker line keeps its em dash.** Editing
  it is unnecessary — with the other occurrences fixed, Vale reports zero
  either way, verified by restoring it — and it would open a `copier update`
  3-way-merge conflict on a block downstream projects customise.
- **The em dash inside the TOML fence is untouched.** Vale skips code blocks.
- **One paragraph was restructured, the rest only reworded.** The "turn either
  on" paragraph told the reader to enable "the matching block" and that "both
  may run together". `server.py.jinja` ships one block of three mutually
  exclusive checks and warns against installing two. That sentence was being
  rewritten anyway, so the contradiction was fixed rather than preserved.

## What this cost, and why the next plan should be shorter

Two rounds of six-lens review produced roughly twenty findings. One was in the
24-line prose change. The rest were in the plan document that described it,
which ran to 420 lines of shell blocks and line-anchored edits for a change
that amounted to sixteen string replacements.

The specific failures were: line anchors that the plan's own first edit
invalidated; `git reset --soft` followed by a selective `git add`, which is a
no-op because the soft reset leaves the index staged; shell blocks that
inherited a working directory from a previous step's `cd`; a `mv` park/restore
that nests on a second run; and mitigations written into the constraints
section but never into the step they governed.

For PRs B-H: keep the plan to the decisions and the verification criteria.
Exact string replacements belong in the execution, not in a document that goes
stale the moment the first one lands.
