---
name: writing-release-notes
description: >-
  Use when drafting or revising a release-notes page under docs/releases/ for
  a release pull request. Defines API-backed evidence research, the
  per-minor page format, and the Vale and strict-docs-build gates for a
  maintainer or local coding agent.
---

<!-- ===== TEMPLATE-OWNED - re-rendered on template updates. ===== -->

# Writing release notes

The pages under `docs/releases/` are the canonical human-facing narrative of
each release; the GitHub release body is a summary plus a link to them, and
`CHANGELOG.md` is the machine-written commit-level audit trail. This skill is
the contract for producing a page: what to research, what counts as evidence,
what the page looks like, and which gates it must pass.

## Inputs

Work from the existing `knope/prepare/*` release PR branch. Derive:

- `VERSION` from `pyproject.toml`. For an RC, remove the pre-release suffix;
  the page and summary marker always use the target stable version.
- `TAG` as `vVERSION` and `MINOR` as the `X.Y` part of `VERSION`; the page is
  `docs/releases/MINOR.md`.
- `PREV` as the highest stable tag strictly below the target version,
  series-aware with `sort -V`; it is empty for a first release.
- `HEAD_SHA` with `HEAD_SHA=$(git rev-parse HEAD)`. This is the exact checked-out
  release PR head to use as the GitHub API range endpoint.
- The page mode. Create the page for a new minor. Add a patch section inside
  the patch sentinels when the page does not cover a patch target. Revise the
  existing section when its `RELEASE-SUMMARY` marker already covers the target;
  never add a duplicate section.

## Local authoring flow

Work on the existing `knope/prepare/*` release PR branch. Determine the target
stable version from `pyproject.toml`; an RC writes the stable version's marker.
Write the release page, run `vale docs/releases/` and `uv run mkdocs build
--strict`, commit the notes surface, push it to the release branch, and let a
maintainer review the diff before marking the PR ready.

For a post-release correction, make an ordinary notes PR. Apply the same
evidence, format, and quality requirements. Use the released tag's timestamp
when adding a date that a pre-release draft could not yet state.

## Non-negotiables

1. **No evidence, no narrative.** Every causal claim must trace to a linked
   issue or PR you actually read, and the page links it. Drop claims that lack
   evidence. Concrete numbers appear only verbatim from their source.
2. **Output is reviewed before it publishes.** A maintainer reviews the page
   in the release PR or an ordinary notes PR. The review verifies evidence,
   not just prose.
3. **Never touch `CHANGELOG.md`.** It is machine-generated. The changelog
   answers what landed; release notes answer whether and how to upgrade.
4. **Never write from `git log`.** Commit subjects are not release-note
   evidence. A page that mirrors a commit list needs more research.
5. **Write the net delta, not the development journey.** Describe the shipped
   state relative to `PREV`. Do not report intermediate regressions, fixes,
   reverted work, or superseded behavior as release information.

## Research procedure

### 1. Enumerate the range through the API

- Commit list: `gh api "repos/OWNER/REPO/compare/${PREV}...${HEAD_SHA}"`.
  Paginate past 250 commits. If `PREV` is empty, use the release compare view
  or full commit list. The API is authoritative because a local clone may be
  shallow.
- Commit to PR: `gh api "repos/OWNER/REPO/commits/SHA/pulls"`. Never infer a
  PR number from a commit subject.
- PR to issues: query each PR's GraphQL `closingIssuesReferences`. Do not grep
  `Closes #N` from bodies because UI-created links have no text form.

### 2. Group before reading deeply

Build themes from the linked issues and PRs:

- An epic with children closed in the range is one theme. Its "What changes
  for the user" paragraph can seed the section and summary after verification.
- The release milestone or `ships-atomically` label identifies work intended
  to ship as one story.
- A first-party upstream bump, including `fastmcp-pvl-core` or a copier
  update, is a research lead of its own.
- Group remaining material by what changes for readers. Do not invent
  structure when epics and milestones are absent.

Research themes separately when practical, then synthesize from concise briefs
that record what shipped, the motivating problem, issue reporter, enablement,
numbers with sources, relevant docs pages, and the final shipped end state.

### 3. Attribute reports correctly

Issue reporters, not commit authors, identify outside demand. Do not infer
outside demand from a maintainer-filed tracking issue. Verify that a quoted
person wrote the cited artifact before attributing the quote to them.

### 4. Synthesize by reader need

Regroup briefs when separate deliverables form one recipe or a fix belongs in a
different theme. Conventional-commit scopes are not the outline. Collapse
development chronology into the shipped end state before writing.

### 5. Research first-party dependency bumps

For a first-party upstream bump, read the old and new versions from the range
endpoints through the API. Read the upstream release pages and GitHub release
bodies before following into upstream PRs or issues. Surface only the behavior
an operator or user of this server experiences, link upstream evidence, and do
not list bare dependency bumps. Third-party bumps stay out unless a linked
local issue makes one a user-facing story.

## Writing the page

For every significant feature, answer in order:

1. What it is for someone new to it.
2. Why it fits this server, supported by the motivating issue.
3. How to enable it, including exact env vars, defaults, and config.
4. The tool or API surface, only after the reader can act on it.

A list of shipped tools is not a release-note section.

### Upgrading

Do not trust `!` markers or `BREAKING CHANGE:` footers. Compare the actual
surfaces between `PREV` and `HEAD` through the API and classify changes against
the breaking-change policy in `CLAUDE.md`:

- import surface: `tests/public_import_surface.txt`;
- operator surface: `.env.example` and configuration;
- tool surface: registered-tools docs, which is not breaking alone but can
  need a migration note when behavior moved.

Follow that classification when it disagrees with a commit marker and record
the disagreement in the PR description.

### Docs links

Link every current docs page for a feature. If code changed in the range but a
guide did not, treat it as a staleness candidate rather than linking the guide
as authoritative. Record candidates in the PR description without filing
issues automatically.

## Page format

One page serves one minor: `docs/releases/MINOR.md`. Patch sections go inside
the patch sentinels, oldest first. The target page must contain exactly one
non-empty summary block for `TAG`; its markers are load-bearing because the
release body extracts that summary.

    # 3.2

    <!-- RELEASE-SUMMARY v3.2.0 START -->
    One short, user-facing paragraph explaining what this minor means for an
    upgrade decision.
    <!-- RELEASE-SUMMARY v3.2.0 END -->

    ## <theme sections>

    ## Upgrading

    <omit this heading when there is nothing to say>

    <!-- PATCH-RELEASES-START -->
    <!-- PATCH-RELEASES-END -->

Write a patch section as:

    ## v3.2.1 (2026-08-20)

    <!-- RELEASE-SUMMARY v3.2.1 START -->
    One paragraph explaining what this patch fixes and who should care.
    <!-- RELEASE-SUMMARY v3.2.1 END -->

    <evidence-linked detail>

Before the stable tag exists, use the bare patch heading and do not claim the
target shipped. Once the tag exists, use its timestamp for the date. Backfill
missing dates in pages present on the branch when making a later ordinary
notes PR. Avoid em dashes because the shipped Vale packs reject them.

For a new page, add the minor to `docs/releases/index.md`, newest first between
its markers. The first real entry replaces the seeded placeholder. Do not edit
`mkdocs.yml`; if it lacks Release Notes navigation, mention that in the PR.

## Quality gates

- Run `vale docs/releases/`. Run `vale sync` first when style packs are not
  installed. Rewrite prose findings; add legitimate domain vocabulary to
  `.vale/styles/config/vocabularies/Base/accept.txt` in the same change.
- Run `uv run mkdocs build --strict`.

## Output

Commit only the target release page, any release pages or index entries whose
dates you corrected, and any required `accept.txt` additions. The PR
description must include the target tag and compare link, claim-by-claim
evidence or a statement that inline links are the evidence, breaking-change
classification, documentation-staleness candidates, and claims omitted for
lack of evidence.

**Honest failure beats confident junk.** If the range supports only a modest
factual page, write that page. If it supports none, leave the notes unchanged
and tell the maintainer why.
