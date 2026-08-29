# One repository for the template and pvl-core: investigation and decision

**Date:** 2026-08-29
**Closes:** #507 (investigate merging fastmcp-server-template and fastmcp-pvl-core into one repository)
**Does not cover:** implementing any option (a plan under `docs/superpowers/plans/`
follows only if the recommendation is ratified); contacting the downstream
projects (their preference is recorded as an open question); changes to either
repo's release model beyond what the decision itself requires.

## Problem

The template and `fastmcp-pvl-core` change in lockstep but live in two
repositories with two release trains. Issue #507 lists five recurring costs —
floor-bump PR churn, the adoption-lag window in which downstream Renovate
proposes a library version the template cannot import, render-time import
coupling (`gen_config_surface.py`), cross-repo design specs, and three-tier
issue routing — and asks for a decision on whether one repository holding both
halves removes them without losing three things the split provides:
independent PyPI versioning of the library, a template that
`copier copy gh:pvliesdonk/fastmcp-server-template` can point at, and separate
release cadences.

This document records the investigation, weighs four options, and recommends
one. "Keep two repos" is an acceptable outcome per the issue, and is in fact
the recommendation — with automation that removes most of the observed cost.

## Verified facts the design rests on

| Fact | How verified |
|------|--------------|
| pvl-core shipped 29 stable releases from v0.1.0 (2026-04-20) to v5.1.0 (2026-08-27); the template shipped 89 releases (v1.0.0, same day, to v6.0.0) in the same 19 weeks — a ~3:1 cadence mismatch | `git tag --sort=creatordate` with `git log -1 --format=%cs` per tag in a pvl-core clone; `grep -c '^## v' CHANGELOG.md` here |
| The template's floor moved 9 times (1.0, 2.0, 3.2, 4.0, 4.10.1, 4.11.0, 4.11.2, 4.11.3, 5.0.0); roughly two-thirds of pvl-core's stable releases required no template change at all | `pyproject.toml.jinja:18-55` floor-history comment; CHANGELOG entries #10, #113, #153, #181, #329, #443, #446, #515 |
| Adoption lag is already near zero: pvl-core 4.11.0, 4.11.2, 4.11.3, and 5.0.0 were each adopted by a template release **the same day** (v3.3.0 2026-08-13, v5.3.0 2026-08-19, v5.3.1 2026-08-20, v6.0.0 2026-08-26); the largest observed window was the 3.x line: 19 days from 3.0.0 (2026-05-29) to the adopting v2.0.0 (2026-06-17), 14 days counting from the 3.2.0 the new floor named | pvl-core tag dates cross-joined with `CHANGELOG.md` release headings mapping the adoption PRs |
| The split's real damage has been breakage incidents, not calendar lag: 4.11.1's help-text rewording broke the render idempotency gate the day it shipped (#335/#336), and 5.0.0 turned template main red the day it shipped because `scripts-and-invariants` installed core unbounded (#509) | `template-ci.yml:1651-1662` comment ("an unbounded install picked up 5.0.0 the day it shipped and turned main red"); #336 PR body |
| Both breakage classes already have merged guards: #336 makes the generator bootstrap resolve the project's full constraint, and #509 caps the scripts-tests install at the template's declared major | `gen_config_surface.py` `ensure_core_available` (constraint parsed at ~L2891); `template-ci.yml:1659-1662` |
| copier picks the version to copy/update by listing git tags, **silently discarding any tag that does not parse as PEP 440**, and taking the max | copier 9.10.2 `copier/_vcs.py:129-147` (`checkout_latest_tag` filters through `valid_version`, which returns `False` on `InvalidVersion`) |
| A prefixed tag such as `pvl-core-v5.1.0` is PEP 440-invalid and therefore invisible to copier, while `v5.1.0` is valid — so a monorepo works only if the **library** renames its tag namespace and the template keeps `v*` | `packaging.version.parse("pvl-core-v5.1.0")` raises `InvalidVersion`; `parse("v5.1.0")` == 5.1.0 |
| pvl-core releases via python-semantic-release with `tag_format = "v{version}"`, publishing to PyPI from its release workflow — the same `v*` namespace the template's `template-release.yml` derives versions from (`git describe --tags --match 'v*'`) | pvl-core `pyproject.toml` `[tool.semantic_release]`; `.github/workflows/template-release.yml` version-compute step |
| `_subdirectory` is read from the template's config **at the ref being rendered**, and `_src_path` stays the plain repo URL — so a layout move inside the repo does not require downstream `.copier-answers.yml` edits; separately, with a non-root `_subdirectory` copier stops applying its default excludes (this repo already re-lists them explicitly in `_exclude`) | copier `_template.py:504-513`, `_main.py:1015`, `_template.py:331`; `copier.yml:317-326` |
| The template already runs a self-hosted Renovate ("upstream detector", `.github/renovate.json` + `template-renovate.yml`) with regex custom managers for pins Renovate cannot natively see inside `.jinja` files — but **no manager covers the `fastmcp-pvl-core` floor in `pyproject.toml.jinja`**, so today the floor-bump PR is always hand-made | `.github/renovate.json` (two custom managers: Action pins, knope CLI pin) |
| Cross-repo spec references are real but small: 12 files in pvl-core name this repo (mostly `docs/superpowers/` specs and plans); this repo's `CLAUDE.md` points at a scaffold spec in a third repo (`markdown-vault-mcp`) | `grep -rl fastmcp-server-template` in the pvl-core clone; `CLAUDE.md` "Spec" section |
| The two repos' release machinery is structurally different: manual `bump` dispatch + shell-computed version + `promote_upgrading.py` here, PSR there, and knope release-PRs in generated projects | `template-release.yml`; pvl-core `release.yml`; `CLAUDE.md:222-230` |

## Design

### The options

**A. Status quo.** Two repos, hand-made floor-bump PRs. Baseline; every cost
in the issue persists, though the two worst incident classes (#336, #509) are
already guarded.

**B. Monorepo.** One repository holding both halves. The workable shape, per
the verified copier mechanics:

- The merged repo keeps the name `fastmcp-server-template` (or the template
  half stays at the root of whatever the repo is called), so every
  downstream's `_src_path: gh:pvliesdonk/fastmcp-server-template` survives
  unchanged. Either the template stays at the root with the library nested
  under `lib/` (one `_exclude` entry), or the template moves under
  `template/` with `_subdirectory` — both verified workable, the first is
  smaller.
- The **library** moves its tag namespace: PSR `tag_format =
  "pvl-core-v{version}"`. Such tags are PEP 440-invalid, so copier keeps
  seeing only the template's `v*` tags, and `template-release.yml`'s
  `--match 'v*'` glob (which matches leading-`v` names only) also keeps
  working unchanged. PSR derives the last version from tags matching its
  `tag_format`, so the switch needs a one-time dual tag (`pvl-core-v5.1.0`
  on the same commit as `v5.1.0`) `[unverified: from PSR docs and config
  reading, not tested]`.
- Template CI installs the library from the sibling tree instead of PyPI,
  which genuinely kills the #336/#509 incident class *for the template* and
  lets a breaking library change and its adoption land as one PR — the
  strongest concrete benefit on offer.
- Costs: PyPI trusted publishing re-scoped to the new repo/workflow; CI
  path-filtering (`paths:` on `lib/**` vs the rest) so 89-releases-a-quarter
  template traffic does not run the library's matrix; two release trains
  interleaved on one releases page and one issue tracker; branch rulesets,
  labels, and issue forms merged; the floor in `pyproject.toml.jinja` still
  must be maintained for *downstreams* (they install from PyPI), so a new
  guard has to keep floor == "latest released or current source" — replacing,
  not removing, the coupling bookkeeping; and a new failure mode where the
  template silently depends on unreleased library code. Downstream Renovate
  still waits on a PyPI release, so B removes the template's share of the
  adoption window, not the downstreams'.

**C. Two repos + automation.** Extend the existing upstream detector with a
third regex custom manager: match
`"fastmcp-pvl-core(\[extra\])?>=X,<Y"` in `pyproject.toml.jinja`
(datasource `pypi`, package `fastmcp-pvl-core`). Renovate then opens the
floor-bump PR the day a library release ships, exactly as it already does for
Action pins inside `.jinja` files. A bump that needs real adoption work (a
major like 5.0.0) arrives as a **red** PR — template-ci renders and imports —
which turns the adoption from something to remember into a failing check with
a diff attached. Costs removed: floor-bump churn (the PR is machine-made) and
most of the adoption window (bot latency instead of human memory). Costs
untouched: render-time import coupling stays (but is guarded), specs stay
cross-repo, routing stays three-tier.

**D. Monorepo with the library as a path dependency or vendored.** Rejected
without detailed scoring: vendoring forfeits independent PyPI versioning (a
stated must-preserve), and a path dependency cannot be expressed in the
rendered project's `pyproject.toml`, which downstreams install from PyPI.

### Decision

**Recommendation: Option C — keep two repositories, automate the floor bump.**

The evidence does not support the monorepo's premise. Two-thirds of library
releases were template-invisible, so a shared train would mostly couple
unrelated work. Adoption lag is already same-day in every recent case — the
split's observable damage was two incident classes, both of which have merged
guards, and the remaining manual step (the floor-bump PR) is exactly the kind
of pin the repo's upstream detector already automates for GitHub Actions.
Meanwhile Option B's ledger is long: a PSR tag-namespace migration, PyPI
trusted-publisher re-scoping, path-filtered CI, merged rulesets/labels/forms,
interleaved release history at a 3:1 cadence mismatch — and it does not even
delete the floor bookkeeping, it converts it into a floor-vs-source guard,
while adding the unreleased-dependency failure mode.

The cross-repo spec and routing costs are real but are the price of the
split's chief benefit: the library is independently versioned and consumable
without the template, and the template's very hot release cadence (89 in 19
weeks) stays out of the library's history. Option B is recorded above with
verified mechanics so it can be revisited cheaply if the coupling profile
changes (say, if most library releases start forcing template changes).

| Decision | Choice |
|----------|--------|
| Repository layout | Keep two repositories |
| Floor-bump PRs | Automated: third custom manager in `.github/renovate.json` (regex on `pyproject.toml.jinja`, datasource `pypi`) |
| Adoption of breaking majors | Unchanged: hand-written template PR, now triggered by the bot's red floor-bump PR instead of memory |
| Cross-repo specs | Accepted cost; keep the existing practice of linking the other repo's spec from the issue/PR body |
| Issue routing | Unchanged three-tier (`CONTRIBUTING.md` "Where to send fixes") |
| Tag namespaces | Unchanged (`v*` in both repos — only a monorepo would force a rename) |

## Risks and mitigations

- **Renovate cannot parse the constraint from `pyproject.toml.jinja`** (it is
  not valid TOML to a native manager). Mitigated by using a regex custom
  manager, the same technique the file's two existing managers use; the match
  string targets the quoted dependency string, not the TOML structure.
- **The bot PR lands red on a breaking major and sits unmerged.** That is the
  designed behavior — it is the adoption work item, with CI attached. The
  dependency dashboard (already enabled) keeps it visible.
- **A library release that breaks the template without a floor bump**
  (the 4.11.1 prose case) is not fixed by Option C. It is already mitigated
  by #336 (bootstrap resolves the full constraint, so copy-time and
  check-time agree) and #509 (major-capped installs); the residual case — a
  same-major release changing generated prose — surfaces in the bot PR's CI
  run rather than in downstream renders `[unverified: depends on the bot PR
  re-rendering before a human next renders, which the render-and-gate job
  does on every PR]`.
- **This document itself renders nowhere**: it lives under
  `docs/superpowers/`, which `copier.yml` `_exclude`s, so no downstream sees
  it and no Vale/mkdocs surface changes.

## Sequencing

1. This document merges (ratifying or amending the recommendation in PR
   review) and closes #507.
2. If ratified, a follow-up issue covers the Renovate custom manager for the
   pvl-core floor — a change to `.github/renovate.json` only, template-repo
   scoped, invisible to downstreams.

## Open questions

- Whether the four consuming projects would prefer the library and template
  pinned at one version `[unverified: owner/downstream input; nothing in
  either repo records a preference]`. Option C does not foreclose it — a
  downstream can already pin both.
- The PSR tag-format migration mechanics recorded under Option B
  `[unverified]` — only relevant if B is ever revisited.
