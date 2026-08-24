# Agent-Neutral Review and Release Notes Design

**Date:** 2026-08-24

**Status:** Approved

## Purpose

Remove mandatory model invocations from pull-request and release automation
without losing agent-assisted review or evidence-driven release notes.

The current workflows make Claude availability part of repository correctness:
automatic review spends Claude credits on every eligible pull request, and
Release Prepare calls a headless Claude drafting workflow that holds the release
pull request in draft until it succeeds. Exhausted credits therefore produce
failed checks and can stop a release before a human has decided whether its
notes need more work.

The replacement keeps agent assistance under human control:

- explicit `@claude` mentions remain available;
- automatic Claude review is optional and disabled by default;
- a provider-neutral skill lets a human use a coding agent of their choice to
  research release notes and open a normal pull request; and
- Release Prepare verifies and promotes repository state using deterministic
  code only.

## Invariants

1. Every release identity has release notes. Release Prepare has no bypass when
   notes are absent.
2. Release candidates and their stable release share one notes identity.
   `vX.Y.Z-rc.1`, later `vX.Y.Z-rc.N` releases, and `vX.Y.Z` all use the
   `vX.Y.Z` summary entry.
3. The first release candidate requires reviewed notes. Later candidates do not
   require an update merely because more commits landed.
4. Whether existing notes still describe the meaningful release delta is a
   human review decision on the knope pull request. Automation checks presence,
   not freshness.
5. No release or required pull-request check depends on model credits, model
   availability, or a particular model provider.
6. Agent-written release notes always reach the repository through an ordinary,
   human-reviewable pull request.
7. Release preparation performs no creative transformation. It validates and
   promotes a constrained staging artifact mechanically.

## Ownership Boundaries

### Human-operated drafting

The provider-neutral release-notes skill lives at
`.agents/skills/writing-release-notes/SKILL.md`. Agent-specific instructions may
point to it, but its contract and commands must not assume a specific coding
agent.

A human invokes the skill with their preferred coding agent. The agent performs
GitHub API research, writes the notes, runs the prose and documentation gates,
and opens a normal pull request. No GitHub Actions workflow invokes this skill.

### Deterministic release preparation

A template-owned promotion script runs in the knope preparation sequence after
knope has computed the version and before the release commit. It decides only
whether the required target entry exists and, when necessary, converts the
reviewed `next` artifact into that entry.

### Human release review

The knope pull request is ready for review as soon as deterministic preparation
finishes. Its review checklist asks the reviewer to compare the notes watermark
with the release delta and decide whether meaningful behavior is missing. The
reviewer may request a separate notes pull request, but no workflow equates a
watermark mismatch with incorrect notes.

## Release-Notes Workflow

### Before the first release candidate

The human invokes the release-notes skill against the branch that will be
released, normally `main` or `release/X.Y`. The agent:

1. researches the release range through the GitHub API, following commits to
   pull requests and linked issues;
2. writes `docs/releases/next.md` through the staging contract below;
3. records the research range end as a commit SHA;
4. runs Vale and `uv run mkdocs build --strict`;
5. creates a branch, commits the allowed notes surface, pushes it, and opens a
   normal pull request against the release branch; and
6. leaves the pull request body with evidence, upgrade classification,
   documentation-staleness observations, and intentionally omitted claims.

After human review and merge, Release Prepare can consume `next.md`.

### Between release candidates

The first candidate promotes `next.md` into the shared `vX.Y.Z` entry. Later
candidates find that target entry and need no staging artifact.

The knope pull-request reviewer decides whether intervening fixes materially
change the release narrative. Tiny stabilization fixes need no notes update. If
an update is warranted, a human invokes the skill in refresh mode and the agent
opens a normal pull request editing the existing canonical `X.Y` page directly.

### Stable promotion

Stable `vX.Y.Z` reuses the entry established for its release candidates. The
same-source promotion guard remains independent of notes freshness.

### Backfill and redraft

The skill also supports a known-target mode for post-release backfills and full
redrafts. It edits the canonical page through a normal pull request. The
existing deterministic Release Notes Publish workflow continues to update the
matching versioned documentation and GitHub release body after such a pull
request merges.

## Staging Contract

`docs/releases/next.md` is committed review state, not a published documentation
page. MkDocs excludes it from output, the release index never links it, and the
post-release publisher ignores a next-only change.

The file has this constrained shape:

```markdown
# Next release

<!-- notes-range-end: <commit SHA> -->

<!-- RELEASE-SUMMARY NEXT START -->
One concise user-facing summary.
<!-- RELEASE-SUMMARY NEXT END -->

## <theme>

Evidence-linked narrative.

## Upgrading

Migration guidance, when needed.
```

The title, watermark, and summary markers must each occur exactly once. The
summary must be non-empty. Theme content may contain ordinary Markdown, but the
promotion script treats fenced code blocks as opaque when adjusting headings.

Patch headings are undated. Release Prepare runs before the tag exists, and the
new process deliberately has no mandatory post-tag agent run to backfill a
date. Git tags and GitHub releases remain the release-date authority.

## Promotion State Machine

The promotion script receives knope's computed version and strips any `-rc.N`
suffix to derive the stable target `vX.Y.Z`. It computes the minor-series page
as `docs/releases/X.Y.md` and searches for exactly one matching
`RELEASE-SUMMARY vX.Y.Z` block.

| Target entry | `next.md` | Result |
|---|---|---|
| Present | Absent | Succeed without changing notes. This is the later-RC and stable-promotion path. |
| Absent | Present | Validate and consume `next.md`, promoting it to the target entry. |
| Absent | Absent | Refuse preparation. The release identity has no reviewed notes. |
| Present | Present | Refuse preparation as ambiguous. Update the canonical page and remove `next.md`, or remove an obsolete staging artifact. |

There is no skip input or emergency bypass. The remedy for missing notes is a
normal notes pull request.

### New minor-series page

When `docs/releases/X.Y.md` does not exist, promotion:

1. replaces the staging title with `# X.Y`;
2. replaces `NEXT` in the summary markers with `vX.Y.Z`;
3. retains the research watermark;
4. adds the empty patch-release sentinels;
5. inserts the new minor page into `docs/releases/index.md` newest first;
6. deletes `docs/releases/next.md`; and
7. stages every affected file for knope's release commit.

### Existing minor-series page

When the minor page exists but the target entry does not, promotion:

1. converts the staging document into an undated `## vX.Y.Z` patch section;
2. replaces `NEXT` in the summary markers with `vX.Y.Z`;
3. adjusts nested heading levels without changing headings inside fenced code;
4. replaces the canonical page's current watermark with the staging watermark;
5. appends the section inside the patch sentinels in version order;
6. deletes `docs/releases/next.md`; and
7. stages every affected file for knope's release commit.

The script validates all inputs and computes every output before replacing any
file. A malformed staging document, duplicate marker, missing sentinel, or
unexpected target layout refuses preparation without partial writes.

Re-dispatch remains safe. Release Prepare recreates its preparation branch from
the release branch, where `next.md` still exists until the release pull request
merges, and repeats the same deterministic promotion.

## Release Pull Request

Release Prepare no longer has `skip_notes` or `full_redraft` inputs and no
`draft-notes` job. It does not put the release pull request into draft state.

The knope pull-request body says that the target release-notes entry is present
and asks reviewers to:

1. review any mechanical promotion diff;
2. compare the notes watermark with commits through the release source SHA;
3. decide whether changes after that watermark materially alter user-facing
   behavior, upgrade guidance, or the summary; and
4. request and merge a separate agent-assisted or hand-written notes pull
   request when an update is needed, then re-dispatch Release Prepare.

GitHub's strict required-check behavior already prevents merging a stale knope
pull request after the base branch changes.

## Pull-Request Review Automation

The explicit `.github/workflows/claude.yml` responder remains in generated
projects. It runs only after a human writes `@claude`, so it is non-invasive and
its provider coupling is intentional and visible.

Automatic Claude review becomes a Copier option. It is disabled by default and
conditionally includes `.github/workflows/claude-code-review.yml` only when a
project opts in. The template repository itself does not run automatic Claude
review.

The existing automatic review behavior may remain provider-specific behind the
option. A provider-neutral code-review skill is a separate follow-up issue; it
is not required to remove the mandatory workflow dependency.

No repository ruleset may require an agent-review check. CI remains the
deterministic merge gate.

## Removed Automation

The following release-note machinery is removed:

- `.github/workflows/release-notes.yml` and its reusable-call and manual
  dispatch modes;
- the Claude CLI installation and `anthropics/claude-code-action` invocation;
- `CLAUDE_CODE_OAUTH_TOKEN` as a release requirement;
- the release-notes concurrency bucket;
- drafting-runner sandbox, snapshots, artifacts, and credential-isolated landing
  job;
- preparation-branch lease logic used only by headless drafting;
- the release pull request's draft hold and ready-state lift; and
- `skip_notes` and `full_redraft` Release Prepare inputs.

The deterministic Release Notes Publish workflow remains.

## Skill Changes

The existing evidence contract remains valuable and moves from
`.claude/skills/writing-release-notes/` to
`.agents/skills/writing-release-notes/`. It is revised for a human-operated
working copy:

- replace workflow-provided context with explicit inputs or safe derivation;
- replace workflow artifact output with branch, commit, push, and pull-request
  creation;
- add prepare-next, refresh-known-target, and backfill/redraft modes;
- retain API-driven range enumeration, issue and pull-request evidence,
  first-party dependency research, net-delta synthesis, attribution rules,
  upgrade classification, documentation checks, Vale, and strict MkDocs;
- permit ordinary local git inspection while keeping the GitHub compare API
  authoritative for release ranges; and
- require the agent to stop before overwriting unrelated working-tree changes.

Agent-specific repository instructions point to the neutral skill path. Ignore
rules preserve `.agents/skills/` so the skill remains tracked.

## Documentation And Secrets

Generated documentation must describe the human-owned sequence:

1. invoke the release-notes skill and merge its `next.md` pull request;
2. dispatch Release Prepare;
3. review the deterministic promotion and assess notes freshness in the knope
   pull request; and
4. merge the knope pull request to release.

The secret table lists `CLAUDE_CODE_OAUTH_TOKEN` only for `@claude` and the
optional automatic-review workflow. Release documentation must not imply that
the token is needed to prepare or publish.

Forking guidance no longer removes a release-notes drafting workflow. It may
keep or remove the neutral skill independently, like other contributor
guidance.

## Migration

This change needs an `UPGRADING.md` entry because downstream operators must
change how they prepare releases and because automatic review changes from
unconditional to opt-in.

The migration instructions must tell downstream maintainers to:

1. set the new Copier automatic-review answer to true if they want to preserve
   automatic Claude review;
2. stop dispatching the removed Release Notes workflow;
3. create and merge `docs/releases/next.md` through the neutral skill before
   preparing a release identity that has no canonical summary;
4. remove any repository rule that independently requires the old Claude review
   check; and
5. retain `CLAUDE_CODE_OAUTH_TOKEN` only when using `@claude` or optional
   automatic review.

Existing canonical release pages remain valid. No historical notes migration is
required.

## Verification

### Promotion script

Unit tests cover:

- new minor-page promotion;
- patch-section insertion;
- RC-to-stable identity normalization;
- all four target-entry and `next.md` presence states;
- malformed title, watermark, summary, and patch sentinels;
- duplicate target markers;
- heading conversion with fenced code blocks;
- index insertion and placeholder replacement;
- file deletion and exact staging behavior;
- failure without partial file replacement; and
- safe repetition through a recreated preparation branch.

### Release-flow contracts

Structural tests prove that:

- knope invokes promotion after version computation and before its release
  commit;
- promotion stages its affected files;
- Release Prepare contains no model invocation, model token, notes bypass,
  reusable drafting job, or draft hold;
- release-body composition still normalizes RC tags to the stable summary
  marker; and
- Release Notes Publish ignores `next.md` while continuing to publish canonical
  page edits.

### Template variants

Template CI renders and hygiene-checks automatic review both disabled and
enabled. The default smoke render uses the disabled state. Tests assert that
`claude.yml` exists in both variants and `claude-code-review.yml` exists only in
the enabled variant.

The usual rendered-project checks remain required: render hygiene, YAML parsing,
Ruff, mypy, pytest, Vale, and strict MkDocs.

## Follow-up

Create a separate issue to design a provider-neutral local code-review skill.
That work should define review inputs, evidence and severity conventions,
targeted verification, and pull-request output independently of any hosted model
workflow.
