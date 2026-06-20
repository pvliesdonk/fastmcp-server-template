# Clean detach from the copier template for independent forks

- **Status:** Approved (design)
- **Date:** 2026-06-20
- **Issue:** [#182](https://github.com/pvliesdonk/fastmcp-server-template/issues/182)
- **Related:** pvliesdonk/fastmcp-pvl-core#194 (the pvl-core half of the
  foldability work — out of scope here)

## Problem

A fork that takes over a single server, or wants its own opinionated variant,
must be able to **detach** from this copier template and from the fleet-wide
guidance the template ships. A fork is not a downstream: it stops tracking the
template entirely rather than receiving `copier update` PRs. Today the detach is
undocumented and partly manual, and the rendered `CLAUDE.md` / CI actively
assume the project still tracks the template (it tells you to `copier update`
and to route fixes upstream to pvl-core / the template).

The template cannot ship a *pre-detached* project — the rendered `CLAUDE.md` and
CI are **correct for a tracked project**. So the work is to make the exit
**mechanical and documented**, and to prove the documented exit actually
produces a clean standalone state.

## Goals

1. Ship a rendered detach guide (`FORKING.md`) at the project root.
2. Make the `CLAUDE.md` scrub a single mechanical `sed`, by wrapping the
   genuinely template-coupled content in dedicated markers.
3. Document which rendered CI workflows a standalone fork prunes vs keeps.
4. Add template-CI smoke assertions that perform the documented detach and
   verify the resulting state (the issue's Verification block).

## Non-goals

- Does **not** touch `fastmcp-pvl-core` (separate issue/PR).
- Does **not** remove the template's ability to render new fleet members — this
  documents the *fork's* exit, not a template teardown.
- Does **not** ship a `scripts/detach.sh`. Per the design decision, the detach
  is **documented copy-paste commands only**; `FORKING.md` is the source of
  truth and template-CI mirrors the same commands inline.
- Does **not** scrub `README.md` structurally. README cleanup is offered as a
  documented optional step in the guide, not enforced by markers or CI.

## Design decisions (resolved during brainstorming)

| Decision | Choice |
|----------|--------|
| Guide location | Top-level `FORKING.md` (rendered from `FORKING.md.jinja`), **not** in the mkdocs site nav. |
| Review-bot wiring | A standalone fork strips **all** bot wiring: `claude.yml`, `claude-code-review.yml`, and `.gemini/config.yaml` — plus `copier-update.yml` (the unambiguous template-automation strip). |
| Detach form | Documented commands only; no maintained script. |
| Test placement | Inline shell steps in `template-ci.yml`, consistent with the existing `CLAUDE.md sentinel structure` / `Dockerfile sentinel structure` assertion steps — not a new `scripts/tests/*.py`. |

## Workflow classification (rendered `.jinja` workflows)

A standalone fork keeps its own CI/release and prunes template-origin
automation and fleet review wiring:

| Workflow / file | Fate | Why |
|-----------------|------|-----|
| `.github/workflows/ci.yml` | **Keep** | The fork's own CI gate. |
| `.github/workflows/codeql.yml` | **Keep** | Generic security scanning. |
| `.github/workflows/coverage-status.yml` | **Keep** | Generic coverage reporting. |
| `.github/workflows/docs.yml` | **Keep** | The fork's own docs publishing. |
| `.github/workflows/release.yml` | **Keep** | The fork's own release pipeline. |
| `.github/workflows/copier-update.yml` | **Strip** | Template-update automation — meaningless once detached. |
| `.github/workflows/claude.yml` | **Strip** | Fleet review-bot wiring. |
| `.github/workflows/claude-code-review.yml` | **Strip** | Fleet review-bot wiring. |
| `.gemini/config.yaml` | **Strip** | gemini-code-assist fleet scope control. |

Note: `release.yml` still legitimately needs `RELEASE_TOKEN`; only the
`copier-update` justification for that token disappears. The README cleanup step
covers the now-stale `copier-update` references.

## Components

### 1. `FORKING.md.jinja` (new — repo root, template-owned)

Renders to `FORKING.md` in every generated project. A normal `.jinja` file:
re-rendered on `copier update` (so a still-tracked project always has the
current guide), **not** in `_skip_if_exists`. The detach itself deletes the file
as part of the exit (it is no longer relevant once standalone).

Structure:

1. **Fork vs downstream** — what detaching means and when to do it; a fork is
   not a downstream (it stops receiving template updates entirely).
2. **Step 1 — stop tracking:**
   ```bash
   rm .copier-answers.yml
   ```
   Stops `copier update` from ever reattaching. The weekly cron that runs it is
   removed in Step 2.
3. **Step 2 — prune template-origin CI:**
   ```bash
   rm -f .github/workflows/copier-update.yml \
         .github/workflows/claude.yml \
         .github/workflows/claude-code-review.yml
   rm -rf .gemini
   ```
   Explicitly states which workflows are **kept** (`ci`, `codeql`,
   `coverage-status`, `docs`, `release`).
4. **Step 3 — scrub `CLAUDE.md`:**
   ```bash
   sed -i '/<!-- TEMPLATE-TRACKING-START -->/,/<!-- TEMPLATE-TRACKING-END -->/d' CLAUDE.md
   ```
   Removes the bot-reviewer paragraph and the Shared-Infrastructure /
   Contributing-fixes-upstream sections. Everything else stays as fork-useful
   contributor guidance. Notes: a fork that has added its own
   `.claude/CLAUDE.md` applies the same scrub there (the template does not
   render `.claude/CLAUDE.md`, so a clean render has nothing to scrub there).
5. **Step 4 — README cleanup (optional, documented):** remove the `Template`
   badge, the `copier-update.yml` row in the `RELEASE_TOKEN` secrets table, and
   the "uv.lock refresh after copier update" subsection.
6. **Closing** — you are now standalone; future template/pvl-core fixes are
   yours to port manually.

The guide uses Jinja variables (`github_org`, `project_name`, …) only where it
quotes paths that already vary; the commands above are static.

### 2. `TEMPLATE-TRACKING` markers in `CLAUDE.md.jinja`

Add two `<!-- TEMPLATE-TRACKING-START -->` / `<!-- TEMPLATE-TRACKING-END -->`
marker pairs around exactly the content that is **wrong for a detached fork**.
The markers are HTML comments (invisible in rendered Markdown) and live inside
the existing `TEMPLATE-OWNED SECTIONS` block, so they are re-rendered on
`copier update` and harmless to tracked projects.

Wrapped range 1 — the bot-reviewer paragraph under `## PR Discipline`:

> **Bot reviewers (claude-review, gemini-code-assist) are merge gates, not pair
> reviewers.** …

This paragraph becomes stale the moment the bot workflows are stripped, so it
travels with the detach scrub. The surrounding "every PR needs an issue" and
"GitHub Review Types" guidance is fork-neutral and stays **outside** the
markers.

Wrapped range 2 — the `## Shared Infrastructure` and
`## Contributing fixes upstream` sections (contiguous, near the end of the
template-owned block, before the `TEMPLATE-OWNED SECTIONS END` fence). These tell
the reader to `copier update` and to route fixes to pvl-core / the template —
both meaningless for a standalone fork.

The single `sed` range-delete in Step 3 removes **all** `TEMPLATE-TRACKING`
ranges in one pass.

### 3. `template-ci.yml` assertions

Two new steps, consistent with the existing inline-shell assertion pattern.

**3a. Marker-balance step** (mirrors the existing `CLAUDE.md sentinel
structure` step): assert the rendered `CLAUDE.md` has equal counts of
`<!-- TEMPLATE-TRACKING-START -->` and `<!-- TEMPLATE-TRACKING-END -->`, and at
least one of each. A dropped marker breaks copier's 3-way merge silently, so it
must fail loudly. Uses the `grep -c … || true` idiom already established in the
file (so a zero match surfaces as an `::error::` rather than aborting the step
via `set -e`).

**3b. Detach smoke step** (placed **last**, after the idempotence check and the
gate, so mutating the render in place is safe — nothing downstream needs the
pristine tree). Runs the exact commands `FORKING.md` documents, then asserts the
issue's Verification block against the mutated tree:

- `test ! -f .copier-answers.yml`
- no `copier` references remain under `.github/`
- `CLAUDE.md` contains none of `fleet`, `downstream conforms`,
  `shape lives in pvl-core` (case-insensitive), **and** no
  `## Shared Infrastructure` / `## Contributing fixes upstream` headings
- the stripped workflows (`copier-update.yml`, `claude.yml`,
  `claude-code-review.yml`) and `.gemini/` are gone
- the kept workflows (`ci.yml`, `release.yml`) still exist

## Test strategy (failure modes enumerated)

Per the TDD discipline, the assertions exist to catch specific failure modes,
not to decorate the happy path:

- **Marker imbalance / drop.** A future edit deletes one
  `TEMPLATE-TRACKING-START`/`END` line → the scrub `sed` deletes the wrong span
  (or nothing). Caught by 3a.
- **Marker rename / typo.** The guide's `sed` pattern and the markers drift out
  of sync → 3b's "no Shared Infrastructure heading" assertion fails because the
  scrub left the section in place.
- **Workflow added to the template but not classified.** A new fleet workflow
  ships without being added to the strip list → not auto-caught (documented
  limitation; see Risks), but the kept/stripped assertions in 3b guard the named
  ones against accidental relocation/removal.
- **Detach corrupts kept CI.** The strip command's glob is too broad and removes
  `ci.yml`/`release.yml` → caught by 3b's "kept workflows still exist".
- **`.copier-answers.yml` path/name changes.** copier's `_answers_file` is
  customised → 3b's `test ! -f .copier-answers.yml` would pass falsely; the
  guide and CI both hard-code the default `.copier-answers.yml`, matching
  `copier.yml`'s `_answers_file`. If that default ever changes, both must change
  together (noted in the guide near the command).

## Risks & mitigations

- **Guide ↔ CI drift.** The detach commands live in two places (FORKING.md and
  template-ci). Mitigation: 3b runs the *intent* of the commands and asserts the
  end state, so a guide that documents a different command set will fail CI when
  the end state diverges. Accepted consequence of "documented commands only, no
  shared script."
- **Root `FORKING.md` linting.** mkdocs reads `docs/` only, so a root-level
  `FORKING.md` is not published and not built under `--strict`. Vale, if wired,
  should likewise not target the repo root. **Verify during implementation**
  that neither the local gate nor template-CI lints `FORKING.md`; if Vale does
  pick it up, either exclude it or make the prose Vale-clean.
- **New unclassified workflows.** Future template workflows are not
  automatically added to the strip/keep lists. Mitigation: the workflow
  classification table in this spec and in `FORKING.md` is the reference; a
  reviewer adding a workflow updates both. Out of scope to auto-detect.

## Verification (from the issue — run on a rendered + detached project)

```bash
test ! -f .copier-answers.yml && echo "copier answers removed"
grep -rn "copier" .github/ ; echo "<-- expect no template-update workflow refs"
grep -rniE "fleet|downstream conforms|shape lives in pvl-core" CLAUDE.md .claude/CLAUDE.md ; echo "<-- expect none"
```

(The `.claude/CLAUDE.md` path is absent in a clean render; the grep simply finds
no file there, which satisfies "expect none".)
