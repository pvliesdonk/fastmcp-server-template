# One repository for the template and pvl-core: investigation and decision

**Date:** 2026-08-29 (revised same day with the owner's weighting of the criteria)
**Closes:** #507 (investigate merging fastmcp-server-template and fastmcp-pvl-core into one repository)
**Does not cover:** performing the migration (each step in Sequencing becomes
its own follow-up issue after this document is ratified); changes to either
half's release *model* beyond what the merge itself requires.

## Problem

The template and `fastmcp-pvl-core` are one product split across two
repositories. The split is not between two products but through the middle of
one:

- **The template is core's documentation.** pvl-core's own `docs/` holds no
  operator documentation at all — only internal ADRs, specs, and maintainer
  notes. Everything an operator reads about core's surface (the config env
  vars, whose help text core itself owns via `server_config_surface`; the
  auth modes; deployment) exists only as the template's rendered docs site.
- **The template is core's example implementation.** `server.py.jinja` wires
  13 core symbols in the blessed order; the rendered project is the reference
  consumer that shows what core is *for*. Core is not usable without it, and
  the template is meaningless without core.
- **A downstream has two places to report problems.** The three-tier routing
  (`CONTRIBUTING.md` "Where to send fixes", the `authoring-issues-prs`
  skill) exists largely to explain which of two trackers an observation
  belongs in — and issues routinely impact both halves (#502 here was the
  adoption half of pvl-core#283; #446 here carried pvl-core#280's scope
  fix into the fleet), so the routing decision is often wrong-by-half no
  matter which tracker is picked.

Two costs named in #507 turn out **not** to matter, and this document weighs
them accordingly. Release cadence: the template ships often (89 releases in
19 weeks vs core's 29) because small workflow steps need a release to be
tried, while core can accumulate — that difference is by design and can
continue unchanged inside one repository, since the two release trains keep
separate tag namespaces (mechanics verified below). Adoption lag: it is
already near zero (same-day in every recent case) because one owner drives
both repos; nothing needed fixing there.

Two pieces of owner context bound the whole analysis. First, **every
downstream consumer is the owner's own**: the fleet is a family of MCP
servers with different domain purposes that share the fastmcp wrapper code,
the CI and release infrastructure, and the documentation scaffolding — and
the prime directive for the family is **anti-divergence**: a fix to one must
reach all, and they must stay similar in appearance and behavior. There is
no external consumer whose expectations constrain the design. Second, that
prime directive is what produced the current split in the first place: the
shared logic became a package (pvl-core) and the shared scaffolding became
the template.

The question is therefore threefold: does one repository holding both
halves remove the coupling and reporting costs without losing a working
`copier copy gh:pvliesdonk/fastmcp-server-template` and independent release
cadences; does the shared logic even need to *be* a package, or could it be
integral to the template; and — since the template's actual job is
**continuous fleet synchronization with the template as authority**, not
one-time scaffolding — is copier, a scaffolding tool with a merge-based
update, even the right mechanism for that job?

## Verified facts the design rests on

| Fact | How verified |
|------|--------------|
| pvl-core's `docs/` contains `adr/`, `specs/`, `superpowers/`, `jobs.md`, `forking.md` — no operator documentation; the template's `docs/configuration.md` content is generated from core's own `server_config_surface` help text | `ls docs` in a pvl-core clone; `scripts/gen_config_surface.py` imports `server_config_surface` (~L585, "owns the help text and tags for every `ServerConfig` field") |
| `server.py.jinja:16-30` imports 13 symbols from `fastmcp_pvl_core`; `config.py.jinja` and `cli.py.jinja` import more — the rendered project is core's reference consumer | read at HEAD |
| Cross-repo issue pairs are routine: #502 (template) adopts pvl-core#283; #446 (template) carries pvl-core#280; 12 files in pvl-core reference this repo by name (specs, plans, README, CLAUDE.md) | issue bodies; `grep -rl fastmcp-server-template` in the pvl-core clone |
| Cadence context (not an argument either way): 29 stable core releases vs 89 template releases in the same 19 weeks; core adoptions were same-day in every recent case (4.11.0→v3.3.0, 4.11.2→v5.3.0, 4.11.3→v5.3.1, 5.0.0→v6.0.0), the largest window being the 3.x line (19 days from 3.0.0) | `git tag --sort=creatordate` in the clone; `CHANGELOG.md` release headings mapping the adoption PRs |
| The split's incident classes: 4.11.1's help-text rewording broke the render idempotency gate the day it shipped (#335/#336); 5.0.0 turned template main red the day it shipped (#509). Both have merged guards, but both exist *because* template CI installs core from PyPI rather than from source | `template-ci.yml:1651-1662` comment; #336 PR body |
| copier picks the version to copy/update by listing git tags, **silently discarding any tag that does not parse as PEP 440**, and taking the max | copier 9.10.2 `copier/_vcs.py:129-147` (`checkout_latest_tag` filters through `valid_version`) |
| A prefixed tag such as `pvl-core-v5.1.0` is PEP 440-invalid and therefore invisible to copier, while `v5.1.0` is valid — so both release trains coexist in one repo if the **library** renames its tag namespace and the template keeps `v*` | `packaging.version.parse("pvl-core-v5.1.0")` raises `InvalidVersion`; `parse("v5.1.0")` == 5.1.0 |
| pvl-core releases via python-semantic-release, `tag_format = "v{version}"`, PyPI publish in its release workflow; the template's `template-release.yml` derives versions with `git describe --tags --match 'v*'` — a glob a `pvl-core-v*` tag does not match, so the template's release machinery survives the merge unchanged | pvl-core `pyproject.toml` `[tool.semantic_release]`; `template-release.yml` version-compute step |
| Every downstream's `_src_path` is the repo-level URL `gh:pvliesdonk/fastmcp-server-template` (consumed by `copier-update.yml.jinja:81-88`); `_subdirectory` is read from the template's config at the ref being rendered, so an internal layout change needs no downstream edits — but a repo *rename* would put every downstream on GitHub redirects | copier `_template.py:504-513`, `_main.py:1015`; `copier.yml` (no `_subdirectory` today) |
| `copier.yml`'s `_exclude` already replaces copier's defaults wholesale and excludes template-repo-only trees (`docs/superpowers`, `scripts/tests`, …) — a nested library tree is one more entry | `copier.yml:317-350` |
| The floor in `pyproject.toml.jinja` (`"fastmcp-pvl-core>=5.0.0,<6"`) must keep existing while core is an installed package: downstreams install core from an index, so a merged repo replaces the floor-bump *PR* with a floor-vs-source consistency guard, not with nothing | `pyproject.toml.jinja:55` and its 37-line floor-history comment; `copier.yml:48-60` `_tasks`/`_migrations` install core from PyPI at scaffold time |
| The template already needs a whole apparatus to defend the files that ARE integral to it: sentinel markers (`DOMAIN-*`, "TEMPLATE-OWNED — DO NOT EDIT"), the `_skip_if_exists` seeded-once list, `scripts/report_seeded_changes.py` diffing downstream edits to seeded files, the structural gate, and the `copier update` 3-way merge arbitrating every divergence. None of this machinery is needed for code that lives in site-packages | `copier.yml:122-220`; `scripts/report_seeded_changes.py`; `REVIEW.md`/`AGENTS.md.jinja` sentinel conventions; render-hygiene notes in `CLAUDE.md` |
| copier's update is by design a merge, not an enforcement: it regenerates a fresh project, diffs it against the current one, re-applies the diff with git-style conflict markers or `.rej` files, and its own recovery path (`copier recopy`) "discards all the smart update algorithm" | copier docs, "Updating a project" |
| The projen model is the opposite contract: every managed file is generated from a versioned package dependency, "most files are marked read-only, and an 'anti tamper' check is configured in the CI build workflow to ensure that files are not updated during build"; updates flow by bumping the dependency and re-running synthesis | projen README |
| `scripts/gen_config_surface.py --check` already implements exactly that contract for the config artifacts: deterministic generation from the installed core version, with CI failing on any hand edit — it is a working synthesis-plus-anti-tamper check inside this very template | `template-ci.yml:428-429`; the generator's `ensure_core_available` bootstrap |
| Reusable workflows can be called cross-repo from a public repository as `owner/repo/.github/workflows/<file>@<ref>`, referenced by tag/SHA/branch — so downstream workflow files can shrink to stubs whose pinned ref Renovate bumps like any Action pin | GitHub Actions docs, "Reusing workflows" |
| Push-based central settings (organization rulesets, required-workflow rules, safe-settings) require an organization on a Team/Enterprise plan; the fleet lives under a personal account, so that family is closed unless the fleet moves to an org | GitHub docs, "Creating rulesets for repositories in your organization" |

## Design

### Weighing

The criteria, in the owner's order of weight:

1. **Anti-divergence across the family** — a fix to one downstream must
   reach all, identically; the fleet stays uniform in behavior and
   appearance. This is the prime directive the whole architecture serves.
2. **One product, one home** — docs and example implementation next to the
   API they document; changes spanning API + docs + example land atomically.
3. **One place to report** — a downstream files one issue; cross-half impact
   is a label, not a routing decision.
4. Must-preserves: `copier copy gh:…` keeps working; independent release
   cadences.
5. Non-factors: release-train interleaving, cadence mismatch, adoption lag —
   and, since every consumer is the owner's, *where* the wheel is served
   from (public PyPI is plumbing, not a constraint; a private index or
   git-tag installs would serve equally).

### The options against that weighing

**A. Status quo.** Leaves both dominant costs fully in place. Rejected.

**C. Two repos + an automated floor bump** (a Renovate custom manager for
the core constraint in `pyproject.toml.jinja`, alongside the two the
upstream detector already has). This was the previous revision's
recommendation, and under the new weighing it is revealed as treating the
cheapest symptom: it removes hand-made floor PRs — a cost the owner does not
rank — and does nothing for docs colocation, atomic changes, or the split
tracker. Not a competing end state; at most an interim convenience if the
migration is deferred.

**C′. Two repos, one tracker.** Disable issues on pvl-core, point its issue
templates' `config.yml` contact link at this repo's tracker, transfer open
issues (GitHub redirects transferred-issue URLs; plain-text `#N` references
in old commit messages become stale — an accepted, bounded cost). Fixes
criterion 2 completely, criterion 1 not at all: docs, example, and API still
change in two repos. Insufficient alone, but it is **independently
shippable and reversible**, which makes it the natural first step of B's
migration rather than an alternative to it.

**D. Core integral to the template — no package at all.** The deepest
variant of the question: since every consumer is the owner's, nothing
*forces* core to be a distributable package; its code could ship as
template-owned files rendered into every downstream and propagated by
`copier update`. Rejected, and the reason is the strongest conclusion of
this investigation — see "Why core stays a package" below. In short:
the package boundary, not the repo boundary, is what actually enforces
the anti-divergence prime directive.

### Why core stays a package: the drift fence

There are two separate boundaries in today's architecture: the **repo**
boundary (two GitHub repositories) and the **package** boundary (core is an
installed wheel, not files in the downstream tree). This investigation
concludes the repo boundary is accidental and should go — but the package
boundary is load-bearing, for three reasons:

1. **The fence hierarchy.** The verified-facts table lists the apparatus the
   template needs to defend the files that *are* integral: sentinels,
   seeded-once lists, seeded-change reports, the structural gate, and
   `copier update`'s 3-way merge arbitrating every divergence. All of it
   exists because template-owned files sit in the downstream working tree,
   where agents (and humans) can and do edit them — agents in particular
   love deviating from template-owned code as "project divergence". Code in
   site-packages needs none of that machinery: an agent working in a
   downstream *cannot* "slightly adapt" `fastmcp_pvl_core`, because it is
   not in the repository. The import boundary is the one fence agents do
   not cross. Making core integral would move its entire codebase from
   behind that fence into the sentinel-and-merge world, multiplying the
   drift surface by the size of core — in the name of anti-divergence.

2. **Propagation.** A core fix today reaches the fleet as: release core →
   Renovate opens a green, conflict-free version-bump PR on every
   downstream — conflict-free *because* no downstream can hold local edits
   to core code. Integral propagation would be: template release → N
   `copier update` runs, each a 3-way merge against files an agent may have
   touched, with conflicts landing on a human. For "fix one, fix all,
   identically", the pin bump is strictly better. A package pin also
   guarantees the same *bytes execute* everywhere; a rendered file only
   guarantees the same starting text.

3. **What integrality would quietly lose.** Core's test suite and typing
   run once, in core's own CI, against the exact artifact downstreams
   install; integral core code would have its tests either duplicated into
   every downstream or dropped. And the version floor — today a meaningful
   compatibility contract with a documented history — would dissolve into
   "whichever template version last rendered you".

The corollary: PyPI itself is demoted to plumbing. The design needs *an*
installed package with a version; it does not need a public index. Public
PyPI stays because it is free, already wired, and what Renovate
understands — but a move to a private index would change nothing above.

### The sync mechanism: from merge to synthesis

The template's actual job is continuous fleet synchronization with the
template as authority. copier's design center is one-time scaffolding with
occasional improvements *merged in later* — regenerate, diff, re-apply with
conflict markers, and when that fails, `recopy` and lose the algorithm.
Every guard this repo has grown — sentinels, seeded-once lists,
seeded-change reports, render hygiene, migration scripts, the update
regression check — is hand-built machinery forcing a merge tool to act
like an authority. The friction is structural, not a usage problem.

Worse, **copier's merge semantics leak through to downstream agents**.
Template-owned files arrive as ordinary, editable working-tree files whose
upstream changes come as merges; an agent reading the repo infers "file I
may edit", and the sentinel prose itself narrates the merge mechanics
("kept across copier update"), which frames divergence as a supported
workflow. The ownership model is communicated only as prose convention —
the one channel agents reliably discount. A synthesis model communicates it
in-band, in the channels agents actually respect: a generated-file header,
a read-only bit, and a CI check that fails on any hand edit.

Three tool families exist for the job. Template-and-merge (copier, cruft,
the template-sync GitHub Actions) — copier is already the best of this
family; the others are strictly weaker, so there is no better *copier*.
Push-based central settings — closed to a personal account (see verified
facts). And **config synthesis from a versioned package** — the projen
model: managed files are generated from a versioned dependency, read-only,
anti-tampered by CI, and updated by bumping the dependency and re-running
synthesis. No 3-way merge exists in this model; a local edit to a managed
file does not get merged around, it fails CI.

This fleet has already independently built one-third of that model and it
is the third that works best: `gen_config_surface.py --check` *is*
synthesis with an anti-tamper check, versioned by the installed core. The
conclusion is to finish the move rather than shop for a better merge tool:

- Core's wheel grows a **`pvl sync`** command; the template-owned files
  become synthesized outputs of templates shipped as package data (the
  existing `.jinja` files, largely as-is).
- Downstream CI asserts **`pvl sync --check`**; a fleet update is a
  Renovate pin bump plus one deterministic regeneration commit —
  conflict-free by construction.
- Domain-owned and seeded-once files are simply *not synthesized* — the
  existing `_skip_if_exists`/sentinel inventory is exactly the ownership
  metadata the synthesizer needs, and the DOMAIN blocks become real escape
  hatches instead of merge conventions.
- CI logic gets a complementary shrink lever: downstream workflow files
  become few-line stubs calling reusable workflows in this (public) repo
  at a pinned tag, which Renovate bumps like any Action pin — workflow
  *logic* leaves the file-sync problem entirely. **This lever is the
  cheap, template-only quick win of the whole document**: it needs
  neither the repo merge nor the synthesizer, ships through one normal
  template release, and downstream Renovate's *native* github-actions
  manager already bumps `uses:` refs in the (real, rendered) stub files.
  Per-workflow, reversible, starting with the highest-churn workflow.
  The bounded work items: Jinja variance becomes `with:` inputs; secrets
  are passed explicitly in the stub (`secrets: inherit` is documented for
  same-org callers, not a personal account); the aggregate `CI Success`
  check keeps its exact context by living in the stub, so rulesets are
  untouched; PyPI trusted publishing validates the *caller's* workflow
  file, so stubs keeping their filenames need no publisher changes. As a
  bonus, `template-ci` can then *call* the same reusable workflow it
  ships instead of re-implementing the rendered gate.
- copier's remaining role is day-0 scaffolding — its actual design
  center — until `pvl new` (synthesis from an empty answers file) replaces
  even that; `copier update` retires with the last migrated file class,
  and with it the merge-conflict bug class (#251 and kin) and most future
  `UPGRADING.md` entries.

This composes with the other two conclusions rather than competing: one
repository, whose wheel carries the library *and* the way of working —
the package boundary, already established as the drift fence, becomes the
distribution channel for the entire template authority.

**B. Monorepo.** One repository holding both halves. Removes criterion 1's
cost (one tree: an API change, its operator docs, and the example
implementation are one PR) and criterion 2's (one tracker, trivially). The
must-preserves survive, on verified mechanics:

- *Independent core versioning:* core keeps PSR and its own version line;
  only its `tag_format` changes (`pvl-core-v{version}`), with a one-time
  dual tag so PSR can find its last release `[unverified: from PSR docs and
  config reading, not tested]`.
- *`copier copy gh:…` keeps working:* copier only sees PEP 440-parseable
  tags, which after the rename are exactly the template's `v*` line; the
  repo keeps its name (below), so `_src_path` across the fleet is untouched.
- *Independent cadences:* both release trains continue as they are —
  `template-release.yml` unchanged (its `--match 'v*'` glob does not match
  `pvl-core-v*`), PSR unchanged but for the tag format.

What B costs, all bounded and mechanical: the tree import with history, one
`_exclude` entry, CI path filtering, PyPI trusted-publisher re-scoping,
rulesets/labels/issue-forms merge, and a floor-vs-source guard replacing the
floor grep. What B does *not* buy: downstreams still install core from PyPI,
so their Renovate still waits on a core release — B removes the template's
share of the coupling, not the fleet's PyPI dependency. And one genuine new
failure mode arrives: template CI testing against sibling source can pass on
unreleased core code; the floor-vs-source guard exists to keep that visible.

### Decision

Three conclusions:

**Merge the repositories (Option B)** — the repo boundary is accidental —
with C′ (tracker consolidation) executed first as the reversible opening
step. Under the stated weighing this is not close: the coupling and
reporting costs are removed only by B, every cost B introduces is a
one-time mechanical migration or a small permanent guard, and the
must-preserves survive on mechanics verified above rather than assumed. The
previous revision's recommendation (C) stands corrected: it optimized a
cost that carries no weight.

**Keep core a package (reject D)** — the package boundary is load-bearing.
It is the drift fence and the conflict-free propagation channel, which
makes it the mechanism that actually delivers the anti-divergence prime
directive; dissolving it into the template would trade the family's best
divergence defense away in anti-divergence's name. The half of the split
that hurt was the one built first (the repo split); the half that looks
removable is the one doing the work.

**Replace merge with synthesis as the sync mechanism** — the target
architecture is the projen pattern implemented on this stack: template
authority shipped inside the core wheel (`pvl sync` + `pvl sync --check`),
copier demoted to day-0 scaffolding and ultimately replaced by `pvl new`.
This is stated as the destination, not an aspiration: it is the largest
work item in this document, and that is a sequencing fact, not a reason to
stay — the migration runs file class by file class, each class moved
permanently deleting its drift surface, its merge conflicts, and its
`UPGRADING.md` tail, with the config artifacts already migrated today as
proof the contract works.

| Decision | Choice |
|----------|--------|
| Repository layout | One repository holding both halves |
| Core packaging | Stays an installed wheel with its own version line — the drift fence and the conflict-free propagation channel; never rendered into downstream trees |
| Distribution index | Public PyPI retained as plumbing (free, wired, Renovate-native); swappable for a private index without touching the design |
| Sync mechanism (target) | Synthesis from the core wheel: `pvl sync` generates template-owned files from package-data templates; `pvl sync --check` in downstream CI; fleet update = Renovate pin bump + one regeneration commit |
| copier's role | Day-0 scaffolding only, until `pvl new` replaces it; `copier update` retires with the last migrated file class |
| CI logic distribution | Downstream workflows become stubs calling this repo's reusable workflows at a pinned tag (Renovate-bumped); workflow logic leaves file sync entirely |
| Ownership signalling to agents | In-band, machine-enforced (generated-file header, read-only bit, failing `--check`) instead of prose sentinels narrating merge mechanics |
| Merged-repo identity | Keep `fastmcp-server-template` (name and root layout): the only shape where the fleet's `_src_path` and the documented `copier copy` command survive with zero migration; merging into `pvl-core` or a new name puts every downstream on rename redirects for no benefit |
| Library placement | Nested tree (e.g. `core/`), template stays at the root; one `_exclude` entry keeps it out of renders — smaller change than `_subdirectory`, which would move every template file |
| Tag namespaces | Template keeps `v*` (copier-visible, PEP 440-valid); core moves to `pvl-core-v*` (PEP 440-invalid, copier-invisible), via PSR `tag_format` plus a one-time dual tag |
| Issue tracker | One (this repo's); pvl-core's issues transferred, its tracker disabled — shippable before the code merge as step 1 |
| Issue routing | `CONTRIBUTING.md` three-tier collapses to two: this repo (library *or* template — one tracker, a label distinguishes) / domain (downstream) |
| Floor bookkeeping | `pyproject.toml.jinja`'s core constraint stays (downstreams install from PyPI); the hand-made floor-bump PR is replaced by a CI guard asserting floor == latest released core or current source version |

## Risks and mitigations

- **The PSR tag-format migration is the least-tested step** `[unverified]`.
  Mitigate by doing it while the repos are still separate (it is orthogonal
  to the merge): rename core's tag namespace in place, watch one release
  ship correctly, then import the tree.
- **Template code silently depending on unreleased core.** The
  floor-vs-source guard fails template CI whenever `pyproject.toml.jinja`'s
  floor names a version older than the source tree's — the release that
  unblocks it is core's own, cut on its normal cadence.
- **Transferred issues renumber.** GitHub redirects the old URLs; bare
  `#N` references inside pvl-core's commit history and specs go stale.
  Accepted: the specs move into this repo in the same migration and can be
  touched up as they land.
- **PyPI trusted publishing** must be re-scoped to the workflow path in the
  merged repo before the first post-merge core release; until then core can
  still release from the old repo, which stays intact (archived, not
  deleted) until the migration completes.
- **The synthesis migration is the largest work item here** — a small
  synthesizer plus porting every file class. Contained by the increment
  rule (a class at a time, each independently shippable and valuable) and
  by reuse: the `.jinja` templates move into the wheel largely as-is, the
  ownership inventory already exists (`_skip_if_exists`, `_exclude`,
  sentinels), and the bootstrap chicken-and-egg (a fresh project needs
  core to synthesize) is already solved by `gen_config_surface.py`'s
  `uv run --with` re-exec trick.
- **projen itself was considered and set aside**: adopting it would bring
  jsii/npm tooling into a pure-Python fleet; the pattern matters, not the
  tool, and the pattern is already half-implemented natively here.
- **This document itself renders nowhere**: it lives under
  `docs/superpowers/`, which `copier.yml` `_exclude`s, so no downstream sees
  it and no Vale/mkdocs surface changes.

## Sequencing

Each step is a follow-up issue once this document is ratified; 1 and 2 are
independently shippable before any code moves, and each step leaves both
halves releasable. One item does not need ratification at all: the
**reusable-workflow conversion** (step 7's workflow class) is template-only,
per-workflow, and reversible — it can start immediately, regardless of when
or whether the merge and synthesis land:

1. **C′ / tracker consolidation** — transfer pvl-core's open issues here,
   disable its tracker, point its issue-template `config.yml` at this repo.
   Reversible; delivers the reporting fix immediately.
2. **Tag namespace** — PSR `tag_format = "pvl-core-v{version}"` in
   pvl-core, one-time dual tag of the latest release, one release shipped
   to prove it.
3. **Tree import** — pvl-core's history imported under `core/`
   (`git filter-repo`/subtree merge), one `_exclude` entry, render asserted
   byte-identical to pre-merge.
4. **CI split** — `paths:` filtering (core matrix on `core/**`; template-ci
   on the rest); template CI installs core from the sibling tree; the
   floor-vs-source guard replaces `template-ci.yml`'s floor grep.
5. **Publishing** — PyPI trusted publisher re-scoped; first core release
   from the merged repo; old repo archived with a pointer README.
6. **Paper cutover** — `CONTRIBUTING.md` routing rewrite, labels/rulesets/
   issue-forms merge, pvl-core's `docs/` (ADRs, specs, superpowers) moved
   in, `UPGRADING.md` policy extended to say which core changes get entries.
7. **Synthesis migration** — runs after (or overlapping) the merge, file
   class by file class, each class its own issue: `pvl sync` skeleton in
   core reusing the existing `.jinja` templates as package data, with the
   config artifacts (already synthesized today) as the first class carried
   over; then workflows — either as synthesized stubs calling this repo's
   reusable workflows at a pinned tag, or synthesized whole — then docs
   scaffolding, packaging files, and agent-instruction files. A class is
   "migrated" when its files carry the generated header, `pvl sync
   --check` gates them in downstream CI, and they are dropped from
   copier's render surface. `copier update` retires with the last class;
   day-0 scaffolding stays on copier until `pvl new` exists.

## Open questions

- The PSR `tag_format` migration mechanics `[unverified]` — resolved by
  Sequencing step 2 before anything irreversible happens.

(An earlier revision asked whether the consuming projects would prefer the
library and template pinned at one version; the question dissolved once the
owner confirmed every downstream is their own. Single-versioning remains
possible but undesirable: it would make every template micro-release churn
a meaningless core bump through the fleet.)
