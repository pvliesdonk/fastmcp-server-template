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

The question is therefore twofold: does one repository holding both halves
remove the coupling and reporting costs without losing a working
`copier copy gh:pvliesdonk/fastmcp-server-template` and independent release
cadences — and, deeper, does the shared logic even need to *be* a package,
or could it be integral to the template?

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

Two conclusions, one per boundary:

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

| Decision | Choice |
|----------|--------|
| Repository layout | One repository holding both halves |
| Core packaging | Stays an installed wheel with its own version line — the drift fence and the conflict-free propagation channel; never rendered into downstream trees |
| Distribution index | Public PyPI retained as plumbing (free, wired, Renovate-native); swappable for a private index without touching the design |
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
- **This document itself renders nowhere**: it lives under
  `docs/superpowers/`, which `copier.yml` `_exclude`s, so no downstream sees
  it and no Vale/mkdocs surface changes.

## Sequencing

Each step is a follow-up issue once this document is ratified; 1 and 2 are
independently shippable before any code moves, and each step leaves both
halves releasable:

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

## Open questions

- The PSR `tag_format` migration mechanics `[unverified]` — resolved by
  Sequencing step 2 before anything irreversible happens.

(An earlier revision asked whether the consuming projects would prefer the
library and template pinned at one version; the question dissolved once the
owner confirmed every downstream is their own. Single-versioning remains
possible but undesirable: it would make every template micro-release churn
a meaningless core bump through the fleet.)
