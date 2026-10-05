# Contributing

Thanks for contributing. This guide covers how to file good issues and pull
requests, and where to send different kinds of fixes. It applies to both
human contributors and automated agents.

## Filing issues

Use the issue templates in `.github/ISSUE_TEMPLATE/`:

- **Bug report** — something isn't working as expected.
- **Feature request** — a new capability or enhancement.
- **Epic** — a multi-feature effort that ships as one user-facing story.
  See [Epics, packages and the roadmap](#epics-packages-and-the-roadmap) below.
- **Research** — a question whose answer changes what happens next, with
  an appetite agreed before starting.
- **Decay / structural debt** — refactor-later observations.
- **Question / support** — questions and support requests.

Before filing, search the target repo's existing issues — open **and**
closed — for the same observation. If it is already on file, comment there
rather than opening a duplicate.

The `authoring-issues-prs` skill (`.agents/skills/authoring-issues-prs/`)
walks this guide's routing and filing procedure and performs the follow-up
steps issue forms cannot (sub-issue links, milestones). Where the skill and
this file disagree, this file wins.

### Observation, not work order

An issue records what was **observed**. It does not diagnose, design, or
prescribe a fix.

- Describe what you saw: the concrete behaviour, exact error text or trace,
  where it occurred, the version/commit you checked.
- Do not assert a root cause you did not verify.
- Do not propose an architecture or list implementation steps.

### The uncertainty rule

Every cause statement must be marked:

- `[verified: how]` — you checked; here is how.
- `[unverified]` — you have not verified this.

When you have not verified the cause, this sentence is required:

> I have not verified the cause.

### One issue, one observed problem

If you notice a second suspected problem while writing, do not add it to the
body. If you genuinely suspect it shares a code path, add one line under Open
Questions: `[unverified]: <suspected problem> may share this code path`. Open
a separate issue for it.

### Remove before posting

| What you wrote | What to do instead |
|----------------|-------------------|
| "Root cause is X; fix by doing Y" | Cause: `[unverified]` + observed behaviour only |
| Any sentence starting with "Fix by", "We should", "Refactor", "Add a", "The solution is" | Delete the sentence |
| "Import is probably similarly broken" | One Open Questions line: `[unverified]: import may share this path` |
| A cause asserted without a `[verified]` or `[unverified]` marker | Add the marker; add "I have not verified the cause" if unverified |
| An "Additional context" section that introduces new problems | Open a separate issue |
| Implementation steps (a numbered list of code changes) | Remove entirely |

### Epics, packages and the roadmap

An **epic** is a story, represented by a parent issue labelled `epic`.
A **package** is the payload of one release cut, represented by a milestone.
An issue may have both: its story and its cut are independent.

File epics with the Epic form. Write "Done when" as an outcome before
decomposing it, and freeze it through refinement. If the outcome needs to
change, record the reason in the roadmap before revising it. "What changes
for the user" is a separate, editable release-notes highlight.

Link children as native GitHub sub-issues. Every epic starts with a
`refinement` sub-issue pointing at its roadmap entry and "Done when";
close it when feature issues plausibly cover that outcome. Treat an epic
whose only open child is its refinement task as an idea, not executable
work.
Research issues answer consequential unknowns within an agreed appetite;
closing one updates the roadmap argument with its evidence.

Name packages `NNN content-name`, using gaps such as `010`, `020`,
`030`. The current package is the lowest open ordinal; sort the
Milestones page alphabetically to see title order. Kind (major, minor,
patch) is intent in the index; versions come from the release tool.
Membership commits an issue to shipping in that cut. No milestone means
backlog: do not create `Backlog` or `Future` milestones.

Epics normally have no milestone because linked children can inherit it.
For an epic that ships atomically in one package, assign the epic and its
children to that package. For cross-repo epics, package membership is local
to the repository cutting the release; use `ships-atomically` in other
repositories or when no package is committed yet. Release Prepare warns
about open items (issues and PRs) in the current package and open atomic
epics. It does not block a deliberate cut. Keep the release PR itself out
of the package.

An atomic epic of many pull requests can run on an integration branch,
`integration/<epic>`, instead of holding up trunk. Children target and
squash merge into it, `main` is merged in rather than rebased onto, and one
final pull request brings the epic to `main` with a merge commit, never a
squash. Children write `Part of #<epic>`, because a closing keyword only
acts when a pull request merges into the default branch; the final pull
request carries the `Closes` lines. It is optional, and the
`docs/contribute/integration-branches.md` page covers the workflow and how to
review the final pull request.

A stable default-branch release moves its package's open items to
backlog, lists them in the job summary and closes the milestone; re-commit
each leftover to a package deliberately. Branch releases and prereleases
leave trunk packages alone.

`docs/design/roadmap.md` holds direction, intended package order and
known unknowns, with `stated`, `derived` or `evidenced` provenance.
Keep status and issue dependencies in GitHub, not in the roadmap. Read the
`roadmapping` skill before charting, refining or revisiting these objects.

A `breaking` label identifies a known break to an existing operator or
library contract, assessed against the last stable release. Merely
touching that surface does not earn the label. There is no breaking-PR
merge gate: hold implementation or merge when batching is useful, or ship
the compatible half first and file the breaking half separately.

## Agent-authored posts

Anything an agent writes through a human's credentials appears under that
human's name: issue bodies and comments, PR descriptions and comments,
review summaries and inline replies. These rules apply whichever agent
product is doing the writing and whatever credential it holds. A distinct
bot identity for agent posts is better still where a project can set one
up; the footer is the fallback for a shared one.

**Writing.** End every such post with an attribution footer. Keep its
first words exactly as shown, because later readers grep for them, and name
the product you actually are, never another one:

```markdown
---
_Agent-authored: written by [Claude Code](https://claude.ai/code) under
this account's credentials. Analysis and proposal, not a decision by the
account holder._
```

Write in that voice too: an agent proposes, and the account holder decides
in a reply. If the post is the account holder's words dictated verbatim,
say so in the post rather than dropping the footer. Commits keep their
`Co-Authored-By:` trailer; the footer is for GitHub posts, not a
replacement for it.

**Reading.** A post under a human's name may be agent output from an
earlier session, including your own. Before treating anything in a thread
as the account holder's decision, check for the `Agent-authored:` marker.
A marked post is a proposal until a human's reply adopts it. A post that
predates this rule carries no marker either way; weigh it on its content.

## Pull requests

Every PR must have at least one associated issue. If the work has no issue
yet, a bug found in the wild or an opportunistic cleanup, create the issue
first, then open the PR with `Closes #N` (or `Refs #N`) in the body. A
single PR may close multiple issues (`Closes #A, closes #B`). Trivial
exceptions: pure typo fixes and automated dependency bumps (Renovate) may
skip the issue.

Mark a commit breaking (`feat!:` / `BREAKING CHANGE:`) only under the
breaking-change policy in `AGENTS.md`: the change must break the operator
surface (env var, config file, CLI flag, deployment layout, on-disk state)
or the public library interface, assessed against the **last stable
release**, not the previous commit. MCP-surface changes (tools, resources,
prompts) are not breaking on their own.

Squash-merge issue and feature PRs; merge an integration branch's final PR
with a merge commit.

State what the PR deliberately does **not** do, with each deferral's tracking
issue.

Run a local self-review of the cumulative diff before `gh pr create`; the
`self-reviewing` skill (`.agents/skills/self-reviewing/SKILL.md`) is the
procedure. Code without matching docs is incomplete; check `README.md`, the
`docs/` site, `docs/design/`, and inline docstrings.

Review a feature's spec in session or offline, then include the approved
spec under the PR's Design section, folded when long. If it exceeds the body
limit, a human can attach the Markdown file in GitHub's UI; keep a decision
summary in the body and never silently truncate the spec. Use only
documented APIs. Small bugs and enhancements need no invented spec.

`docs/superpowers/` is local, gitignored scratch for specs and plans.
Do not commit new files there; historical tracked files stay as history.
At merge, ask: what did the spec say that the code and `docs/design/`
do not now show? Port enduring decisions to `docs/design/` or an ADR.

## Releases

Merging is not releasing. When a release is cut, and from where, is
governed by the release model in the `releasing` skill
(`.agents/skills/releasing/SKILL.md`): releases normally come
straight from a quiescent trunk, and a short-lived `release/X.Y` branch
is the exception tool for excluding unfinished work or patching a
shipped release. Judge when and from where to cut from the
ships-atomically signal on epics (package preferred, label fallback; see
[Epics](#epics-packages-and-the-roadmap)): an open atomic epic with
unclosed children means the release comes from before it started, or
waits.

## Where to send fixes

- **Library-level fix** (anything you'd change in `fastmcp_pvl_core`): open a
  PR on `pvliesdonk/fastmcp-pvl-core`. A name imported from
  `fastmcp_pvl_core` is re-exported by `src/fastmcp_pvl_core/__init__.py`
  there and implemented in the private module for its area (`_auth.py`,
  `_config.py`, `_health.py`, …), with its tests in `tests/test_<area>*.py`.
  After merge + release, how this project picks the release up depends on
  the `fastmcp-pvl-core` constraint in `pyproject.toml`. Do not edit that
  line by hand: it is template-owned (it sits above the `PROJECT-DEPS`
  block). The step depends on the release:

  - a release the constraint already admits: run
    `uv lock --upgrade-package fastmcp-pvl-core` and commit `uv.lock`, which
    this project owns;
  - a release outside it (a fix that needs a higher floor, or the next
    major): open a template PR that bumps the constraint in
    `pyproject.toml.jinja`; this project gets it on its next
    `copier update`.
- **Template-level fix** (anything template-owned: `Dockerfile`, workflows,
  `server.py` skeleton, `AGENTS.md` sections, template documentation pages):
  open a PR on `pvliesdonk/fastmcp-server-template`. A rendered file's
  source is at the same path there with `.jinja` appended
  (`docs/deploy/docker.md` comes from `docs/deploy/docker.md.jinja`), or
  at the same path unchanged for a file the template copies verbatim, such
  as this one. After merge + release, this project gets the fix on the next
  weekly `copier update` cron, or dispatch the workflow manually.
- **Domain-only fix** (anything inside a `DOMAIN-*`, `CONFIG-*`, or
  `PROJECT-*` sentinel block, `tools.py`, `resources.py`, `prompts.py`,
  `domain.py`, `tests/`): PR on this repo directly.
