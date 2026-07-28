# Config-surface Stage 1b, restructured into reviewable PRs

**Date:** 2026-07-27
**Status:** design approved. PR A shipped; B-H not started.
**Supersedes:** `docs/superpowers/plans/2026-07-26-config-surface-generation-1b.md` (abandoned; exists only on the unpushed `feat/config-surface-splicing` spike at `283811e`, not on `main`)
**Upstream spec:** `docs/superpowers/specs/2026-07-25-config-generation-and-ownership-model-design.md`, Stage 1
**Closes (design-level):** #257, #260, #266, plus three issues still to be filed (§8)

## 1. Why this design exists

A first attempt at Stage 1b was implemented, reviewed three times by a
seven-lens adversarial review, and abandoned. It is preserved unpushed on
`feat/config-surface-splicing` at `283811e` as a spike.

The scope was not wrong. The unit of review was. The branch reached **3,515
added lines across 17 files** in a single range, and the reviews found **12
confirmed findings in the third round alone** — two of which would have failed
CI or shipped broken output to every downstream.

The decisive evidence was not the count. Round 2's fixes introduced three new
defects that were each instances of the class round 1 had just closed; round
3 then found a fourth, in the same function, twelve lines from a sibling fixed
in the same edit. Iteration was not converging.

### 1.1 What actually failed, and what did not

This split drives the whole decomposition.

**Mechanism survived.** Across three rounds with independent execution, no
lens found a confirmed defect in: the splice engine and its marker guards, the
`json-splice` structural replacement, `--check` read-only semantics,
determinism under varying `PYTHONHASHSEED`, or byte-parity with
`bump_manifests.py`. Lens 6 validated the generated `server.json` against the
real published registry schema with zero errors, and proved the version-bump
round trip leaves the file byte-identical.

**Content failed, repeatedly.** Every round found defects in *which vars go
where*, *what "required" means*, *what a default is*, and *what the prose
claims*. A representative sample:

- `KV_STORE_URL` was moved into the stdio package on the strength of core's
  help prose, reversing a decision PR #153's review thread had already settled
  on the code — `build_event_store` is called only inside `if transport ==
  "http":`.
- `isRequired` was emitted for four OIDC vars, asserting something false: a
  container with none of them set starts and serves unauthenticated.
- `x: str | None = None`, the ordinary spelling of an optional setting,
  published as **Required: Yes** in every downstream README.
- A rewording of `CLAUDE.md.jinja` silently broke the `detach-smoke` scrub,
  and the guard built to catch exactly that passed, because it had no anchor
  for the rule that broke.

The difference is reviewability. A mechanism defect is visible by reading
code. A content defect is visible only by reading rendered output against an
external source of truth — the template's own code, the review record, the
published schema, or a lint tool's actual behaviour.

### 1.2 Root cause

Three rounds of review located one root cause with two faces.

**No verification feedback loop for prose.** `template-ci` renders the
template but never runs Vale over the result; it only grep-checks `.vale.ini`
structurally. Every prose defect was therefore found by hand, late, or would
have been found by a downstream's red build. The normalisation layer was
written to *guess* which shapes would trip rules nobody had measured.

**The wrong source of truth for content decisions.** Core's help text
describes what the *library* can do. The template's own `cli.py.jinja` decides
what the *scaffold* does. Decisions were made from the former.

## 2. Design principles

1. **Every PR ships a rendered artifact a reviewer can read.** No PR asks a
   reviewer to simulate a generator in their head.
2. **Verification before generation.** The prose safety net lands before
   anything generates prose.
3. **Minimal over speculative.** Rules exist for shapes that are observed,
   not imagined. The safety net covers the unobserved.
4. **Salvage what execution verified; redecide what judgement produced.**

## 3. PR sequence

Strictly sequential off `main` — one PR at a time, per the repo's
no-stacked-PRs rule. Each row is independently shippable and independently
revertible.

| PR | Scope | Primary verification |
|---|---|---|
| **A** | Clear the 20 Vale errors in `authorization.md` and `config-migration.md` | `vale` over a render reports 0 |
| **B** | `template-ci` runs Vale over the render; add the missing `check_anchor` | A deliberately injected error fails the build |
| | *B decides whether the gate also runs with the domain vocabulary dropped. An accepted term suppresses non-spelling rules inside its match span, so a plain zero can pass prose carrying a flagged pattern. PR A leaves both runs clean, so B starts from zero either way.* | |
| **C** | OIDC prose corrections (key derivation, re-registration, restart) | Every claim cited to a `fastmcp` file and symbol |
| **D** | Markdown splice engine + the two OIDC doc tables + `required_vars` | The rendered tables read correctly to an operator |
| **E** | README core + domain tables + `documented_defaults` + the `MISSING` fix | A real `ProjectConfig` field renders Required correctly both ways |
| **F** | `json-splice` + `server.json` arrays + `packaging` / `choices` / key validation | Schema-valid; `bump_manifests` round trip byte-identical; every guard bites |
| **G** | `.vscode/` ignore + the `.mcp.json/` trailing-slash fix | Both patterns verified in a fresh `git init` inside a render |
| **H** | Remove dead `READ_ONLY` from `packaging/mcpb/manifest.json.in.jinja` | No `_READ_ONLY` env var anywhere in a render |

G and H are independent of the rest and may land at any point.

### 3.1 Why C is separate from D

Both touch `docs/guides/authentication.md` and `docs/deployment/oidc.md`, so
folding C into D would look economical. It is not. Verifying claims about a
third-party library against its source is a different review activity from
reviewing a table generator, and mixing them is how the first attempt
*relocated* a false claim rather than fixing it: a correction was written,
reviewed alongside unrelated generator changes, and turned out to assert
something new that was also untrue.

C touches prose sections. D replaces tables. They occupy disjoint regions of
the same files.

### 3.2 Why B carries the `check_anchor` fix

`template-ci` scrubs `copier update` wording out of `CLAUDE.md` for the
detach-fork smoke test, and guards that scrub with `check_anchor` calls that
assert each anchored phrase still exists. There are five substitution rules
and only four anchors. The unguarded rule is precisely the one a reword broke,
so the guard passed while the scrub silently failed.

Both B and the anchor fix are "make `template-ci` actually verify what it
claims to verify". They belong together.

## 4. Design decisions

### 4.1 Vale safety net, no baseline

`template-ci` renders the template and runs Vale over `docs/` and `README.md`,
and asserts **zero** errors.

Scope, version and exclusion glob must be **extracted from the rendered
`ci.yml`**, not restated. #143/#159 established that Vale's scope is derived
and compared rather than duplicated, because two surfaces drifting apart make
a finding visible to one and silent to the other; the existing lockstep steps
compare `ci.yml` against `.pre-commit-config.yaml` using an `awk` anchor on
the `vale:` job. This gate is a third surface, so it either reuses that anchor
or the lockstep grows to assert over all three.

No baseline file. The pre-existing errors are not acceptable noise.
`docs/guides/authorization.md` ships to any downstream rendered with
`enable_authorization: true`, and those projects run Vale at
`MinAlertLevel = error` with `fail_on_error: true`, so such a project's build
would be red.

No current consumer is exposed: all seven sibling checkouts in this
workspace render with `enable_authorization` false or absent, so the blast
radius today is zero. (Checked against each checkout's
`.copier-answers.yml`; that is the local working set, which may not be the
full consumer list.)
That makes this the cheapest possible moment to fix it rather than a reason to
defer.

That argument covers prose near a marker, not the marker line itself. PR A
left the `DOMAIN-AUTHZ-SCOPES-START` line alone: editing it bought no
error-count improvement, and a marker line is where a `copier update` 3-way
merge is most likely to conflict for a downstream that customised the block
beneath it. Where an edit is unnecessary, low blast radius is not a reason to
make it.

PR A fixes the errors; a baseline would have recorded them as accepted, and
would then have to be maintained and eventually retired.

The errors span 8 rules across two authored files. `docs/guides/authorization.md`
carries 19: 6 `Google.EmDash`, 4 `ai-tells.EmDashUsage`, 3 `Vale.Spelling`, 3
`Google.Latin`, and one each of `write-good.ThereIs`,
`Google.OptionalPlurals`, `ai-tells.EmphaticCopula`.
`docs/guides/config-migration.md` carries 1, `ai-tells.OverusedVocabulary`.

**The net covers the whole render, not only the generated regions, because
the authored prose is agent-written too.** `ai-tells` is a rule pack built
from the writing tics of Claude models, and every finding here is one:
`git blame` attributes the authorization guide's flagged lines to a commit
co-authored by Claude Opus 4.8. During the abandoned attempt, three further
`ai-tells` errors were introduced by the agent doing the fixing — a spaced em
dash and an italicised `*not*` in a README edit, and a normaliser that emitted
"For example," while its own docstring said that phrase trips
`FormalTransitions`. A gate scoped to generated output would have caught none
of them. The author of this prose cannot self-review for these patterns; only
the tool surfaces them.

### 4.2 Prose normalisation: minimal, verified against core

The generator normalises core's help text for the Vale-linted markdown
destination only. The rule set covers **exactly the shapes core currently
emits**, and no more:

- a spaced em dash,
- `e.g.` in the comma-clause shape,
- the vocabulary term `JWTs`.

No residual sweeps. No sentence-initial branch. No catch-alls for shapes core
has never produced. Every one of those speculative constructs produced a
defect in the abandoned attempt, and none of them was reachable by any real
input.

The sufficiency check is what makes this safe, and it has two halves that must
not be confused:

- **A unit test** iterates `server_config_surface()`, pushes every real help
  string through the normaliser, and asserts no *known-bad pattern* survives —
  a spaced or unspaced dash of either kind, a Latin abbreviation, a
  formal-transition phrase. It is a pattern assertion, not a lint run, so it
  needs no `vale` binary and runs everywhere.
- **`template-ci` (§4.1)** runs the real Vale binary over the rendered output.
  That is the authority. The unit test exists to fail fast and to localise the
  offending var; it is never the reason to believe the output is clean.

Together they prove the rule set is sufficient *for the pinned core*. When a
future core introduces a new shape, `template-ci` goes red and a rule is added
then — which is the entire purpose of §4.1.

The rules this generated prose must follow are recorded once, in PR A's
execution record. They are writing rules, not properties of the tool.


### 4.3 Required-ness for domain vars

`_discover_domain_vars` stops collapsing "no default declared" into `None`.
`dataclasses` already distinguishes them — `field.default is MISSING` — and
discarding that distinction made the documented rule unimplementable and
published the common case wrongly.

The resulting rule is honest and needs no new vocabulary:

| Field | Signal | Required |
|---|---|---|
| `vault_path: str = field(default="/data")` | has a default | No |
| `api_key: str \| None = None` | has a default | No |
| `api_key: str = field(metadata={...})` | no default; cannot construct without it | Yes |

Template-enumerable vars continue to use the explicit `required_vars:` list,
because their required-ness is a semantic property of the feature, not of the
dataclass.

### 4.4 Destination-specific formatters

A var's default has four destinations with four correct answers. Each pair is
pinned apart by a test; the abandoned attempt merged the fourth and wrote a
test asserting they agreed.

| Destination | Default renders as | Rationale |
|---|---|---|
| env file (`_format_value`) | real default, else `example` | the reader wants something fillable |
| markdown cell (`_md_default_cell`) | real default, else declared documented default, else `(none)`; always a code span | the column states what happens if you set nothing |
| `server.json` (`_json_default`) | real default as a string, else `placeholder` | the schema's own split: `default` is behaviour, `placeholder` is guidance |
| wizard spec | untouched core prose | not linted, not a value field |

`isRequired` is **never** emitted into `server.json`. `required_vars:` means
"required for the feature this var belongs to"; the docs tables get away with
it because they sit under an `## OIDC` heading that supplies the condition. A
package manifest has no such context and the schema offers no conditional
scoping, so the flag would assert something false.

### 4.5 Salvage boundary

Carried forward from the spike, with their tests, because three rounds
verified them by execution:

- `splice_region` and its four marker guards
- the `json-splice` structural replacement and the `registryType` cross-check
- `--check` read-only semantics
- determinism (no set iteration feeding ordered output)
- `bump_manifests.py` byte-parity and its round-trip test

Redecided from scratch, because judgement produced them and judgement was
wrong:

- which vars appear in which destination
- `required_vars`, `documented_defaults`, `packaging`, `choices` contents
- every normaliser rule
- every prose claim about `fastmcp` behaviour

## 5. Verification contract

Every PR that changes generated output verifies along three axes the
abandoned attempt never checked. All three blockers found in round 1 lived
outside the intersection of "fresh render" and "core's current help text".

1. **An existing downstream.** Re-run the check with `_skip_if_exists` files
   reset to their pre-change state. `.vale.ini`,
   `.vale/styles/config/vocabularies/Base/accept.txt`, `.gitignore` and
   `packaging/mcpb/manifest.json.in` reach new renders only. A fix that
   depends on one of them does not propagate and is not a fix.
2. **Downstream-authored help text.** The README domain region renders text a
   downstream author wrote, which no test in this repo can enumerate. Exercise
   it with multi-line help, help containing a pipe, and help containing
   markup.
3. **A core whose prose differs from today's.** The normaliser's sufficiency
   test pins the current core; the safety net covers the next one.

Additional invariants:

- Any PR touching `CLAUDE.md.jinja` greps `FORKING.md.jinja` and
  `template-ci.yml` for a scrub rule matching the edited sentence. That
  coupling is invisible from the file itself.
- Any content decision that contradicts an apparent prior choice is checked
  against the review record (`gh api .../pulls/<N>/comments`, `/reviews`,
  `/issues/<N>/comments`) before it is made.
- Every mechanical edit asserts that it applied. Two silent `str.replace()`
  no-ops occurred in the abandoned attempt, one of which was reported as a
  completed fix.
- Every `SystemExit` a downstream can hit during `copier update` has its
  recovery documented in `docs/guides/config-migration.md`.

## 6. Rollout hazards

These must reach the release note and the rollout issue.

- **README's domain table conflicts for every downstream.** Six of the seven local
  checkouts carry a hand-written table inside the `DOMAIN` fence that PR E replaces with
  `GENERATED-ENV-TABLE-DOMAIN` markers. A downstream that resolves the
  conflict by keeping its own table *without* the markers gets a hard CI
  failure, not a silent skip: `splice_region` raises and `ci.yml` runs
  `--check`. The migration guide must name the marker pair, state that only
  the rows between them may be deleted, and give the recovery for a
  missing-marker error mid-update.
- **`_skip_if_exists` fixes do not propagate.** PR G's `.gitignore`
  corrections and PR H's manifest cleanup reach new renders only. Each affected
  downstream needs a one-time manual edit.
- **Stage 1b must merge before the template is released**, or downstreams
  receive generated documentation without the corresponding fixes.

## 7. Out of scope

- `.pre-commit-config.yaml` reclassification (Stage 1c, #254).
- Pushing prose fixes upstream into `fastmcp-pvl-core`. Filed as core#237;
  the template-side rules are still required for downstreams pinned to older
  cores.
- `docs/deployment/docker.md`'s deployment-subset table and
  `packaging/mcpb/manifest.json.in`'s `env` block remain hand-owned. They are
  env-var surfaces the generator deliberately does not own, and any statement
  about generator ownership must say so.

## 8. Issues

| PR | Issue |
|---|---|
| A | #266 — the rendered docs fail Vale (19 in `authorization.md`, 1 in `config-migration.md`) |
| B | to file — `template-ci` never runs Vale over the render, and one scrub rule is unguarded |
| C, D, E | #260 (authored-prose remainder) |
| F | #257 (`server.json` remainder) |
| G | to file — `.vscode/` is untracked noise and `.mcp.json/` never matched the file |
| H | to file — dead `READ_ONLY` in the `.mcpb` manifest (the remainder of #240) |

Two pre-existing defects were found by PR A's review and filed rather than
folded in, since neither belongs to a prose-linting change:

- **#267** — the authorization guide's `See also` has no pvl-core reference.
  Raised twice on #181 and unanswered. Belongs with C, which owns that
  guide's prose.
- **#268** — `config-migration.md` misdescribes the AST scan and steers a
  reader into the duplicate-name `SystemExit`. The same wording appears in
  five files, so it is a sweep. Belongs with E, which owns domain discovery.

At merge time the **squashed commit message's** closing keywords are what
GitHub acts on, not the PR body. A stale `Closes` line in Stage 1a's squashed
commit auto-closed three issues that still had work outstanding.
