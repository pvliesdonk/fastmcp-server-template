# Contributing

These rules govern every issue and pull request, whether a person or an
agent writes it, and where each kind of fix goes. Where the
`authoring-issues-prs` skill (`.agents/skills/authoring-issues-prs/`) and
this file disagree, this file wins.

## Filing issues

File every issue with a form from `.github/ISSUE_TEMPLATE/`:

- **Bug report**: something does not work as expected.
- **Feature request**: a new capability or enhancement.
- **Epic**: a multi-feature effort that ships as one user-facing story; see
  [Epics, packages and the roadmap](#epics-packages-and-the-roadmap).
- **Research**: a question whose answer changes what happens next, with an
  appetite agreed before starting.
- **Decay / structural debt**: a refactor-later observation.
- **Question / support**: a question or support request.

Before filing, search the target repo's issues, open **and** closed, for
the same observation; if it is on file, comment there instead. File with
the `authoring-issues-prs` skill: it also adds the sub-issue links and
milestones a form cannot.

### Observation, not work order

An issue records what was **observed**; it does not diagnose, design, or
prescribe a fix.

- Describe what you saw: the concrete behaviour, the exact error text or
  trace, where it occurred, and the version or commit you checked.
- State a cause only with a marker from the uncertainty rule below.
- Leave out architecture proposals and implementation steps.

### The uncertainty rule

Mark every cause statement:

- `[verified: how]`: you checked, and this is how.
- `[unverified]`: you have not checked.

When the cause is unverified, include this sentence:

> I have not verified the cause.

### One issue, one observed problem

Open a separate issue for a second suspected problem instead of adding it to
the body. If you suspect it shares a code path, also add one line under Open
Questions: `[unverified]: <suspected problem> may share this code path`.

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

An **epic** is a story: a parent issue labelled `epic`. A **package** is
the payload of one release cut: a milestone. An issue may belong to both.

- File an epic with the Epic form. Write "Done when" as an outcome before
  decomposing it and keep it fixed through refinement; to change it, first
  record the reason in the roadmap. "What changes for the user" is the
  release-notes highlight; edit it freely.
- Link children as native GitHub sub-issues. Start every epic with a
  `refinement` sub-issue that points at its roadmap entry and "Done when",
  and close it when feature issues plausibly cover that outcome. Do not
  start implementing an epic whose only open child is its refinement task.
- Keep a Research issue within its agreed appetite; when you close it,
  update the roadmap argument with its evidence.
- Name packages `NNN content-name`, with gaps (`010`, `020`, `030`). The
  current package is the lowest open ordinal; sort the Milestones page
  alphabetically to see it. Record a package's kind (major, minor, patch) as
  intent in the roadmap index; the release tool chooses the version.
- Put an issue in a package only when it commits to shipping in that cut.
  Leave backlog issues without a milestone, and create no `Backlog` or
  `Future` milestone.
- Leave an epic without a milestone; its children carry theirs. Assign an
  epic that ships atomically in one package, and its children, to that
  package. In a cross-repo epic, use packages only in the repository
  cutting the release; label the epic `ships-atomically` elsewhere, or
  before a package is committed.
- Keep the release PR out of the package. Release Prepare warns about open
  items in the current package and about open atomic epics, but does not
  block a cut.
- After a stable default-branch release, which moves its package's open
  items to backlog, lists them in the job summary and closes the milestone,
  re-commit each leftover to a package deliberately. Branch releases and
  prereleases leave trunk packages alone.

To land an atomic epic of many pull requests without holding up trunk, you
may run it on an integration branch, `integration/<epic>`. Children
squash-merge into it, `main` is merged into it, never rebased onto, and one
final pull request brings it to `main` with a merge commit, never a squash.
Children write `Part of #<epic>`, because a closing keyword acts only on a
merge into the default branch; the final pull request carries the `Closes`
lines. The workflow and how to review the final pull request:
`docs/contribute/integration-branches.md`.

Keep direction, intended package order and known unknowns in
`docs/design/roadmap.md`, each marked `stated`, `derived` or `evidenced`;
keep status and issue dependencies in GitHub. Read the `roadmapping` skill
before charting, refining or revisiting any of these.

Apply the `breaking` label only to a known break of an existing operator or
library contract, assessed against the last stable release, not to a change
that merely touches that surface. No gate blocks a breaking PR: hold
implementation or merge to batch breaks, or ship the compatible half first
and file the breaking half separately.

## Agent-authored posts

An agent's post through a human's credentials appears under that human's
name: issue bodies and comments, PR descriptions and comments, review
summaries and inline replies. These rules apply to every agent product and
every credential. A distinct bot identity for agent posts is better still
where a project can set one up; the footer is the fallback for a shared
one.

**Writing.** End every such post with this attribution footer. Keep its
first words exactly as shown, because later readers grep for them, and name
the product you actually are, never another one:

```markdown
---
_Agent-authored: written by [Claude Code](https://claude.ai/code) under
this account's credentials. Analysis and proposal, not a decision by the
account holder._
```

Write as a proposer; the account holder decides in a reply. When the post
is the account holder's words dictated verbatim, keep the footer and say so
in the post. Keep the `Co-Authored-By:` trailer on commits; the footer is
for GitHub posts only.

**Reading.** Before treating a post under a human's name as their decision,
check it for the `Agent-authored:` marker: it may be an earlier session's
output, including yours. Treat a marked post as a proposal until a human's
reply adopts it. Weigh an unmarked post that predates this rule on its
content.

## Pull requests

- Link every PR to at least one issue with `Closes #N` or `Refs #N` in its
  body; one PR may close several (`Closes #A, closes #B`). When the work has
  no issue yet, such as a bug found in the wild or an opportunistic
  cleanup, create the issue first. Pure typo fixes and Renovate dependency
  bumps may skip the issue.
- Mark a commit breaking (`feat!:` / `BREAKING CHANGE:`) only under the
  breaking-change policy in `AGENTS.md`: the change breaks the operator
  surface (env var, config file, CLI flag, deployment layout, on-disk
  state) or the public library interface, assessed against the **last
  stable release**, not the previous commit. MCP-surface changes (tools,
  resources, prompts) are not breaking on their own.
- Squash-merge issue and feature PRs; merge an integration branch's final
  PR with a merge commit.
- List what the PR deliberately does **not** do, each with its tracking
  issue.
- Before `gh pr create`, review the cumulative diff with the
  `self-reviewing` skill (`.agents/skills/self-reviewing/SKILL.md`).
- Update `README.md`, the `docs/` site, `docs/design/` and inline
  docstrings in the same PR as the code they describe.
- For a feature, review its spec in session or offline and include the
  approved spec under the PR's Design section, folded when long. When it
  exceeds the body limit, keep a decision summary in the body and ask a
  human to attach the Markdown file in GitHub's UI, using no undocumented
  upload API; never truncate the spec silently. Write no spec for a small
  bug or enhancement.
- Keep specs and plans in `docs/superpowers/`, which is local and
  gitignored; commit no new files there, and leave its tracked historical
  files as they are. At merge, port every enduring decision the spec
  records but the code and `docs/design/` do not show to `docs/design/` or
  an ADR.

## Releases

Merging is not releasing. Decide when and from where to cut with the
release model in the `releasing` skill (`.agents/skills/releasing/SKILL.md`):
release from a quiescent trunk by default, and use a short-lived
`release/X.Y` branch only to exclude unfinished work or patch a shipped
release. An open atomic epic with unclosed children (package first,
`ships-atomically` label as fallback; see
[Epics](#epics-packages-and-the-roadmap)) means release from before it
started, or wait.

## Where to send fixes

- **Library-level fix** (anything in `fastmcp_pvl_core`): open a PR on
  `pvliesdonk/fastmcp-pvl-core`. A name imported from `fastmcp_pvl_core` is
  re-exported by `src/fastmcp_pvl_core/__init__.py` there and implemented in
  the private module for its area (`_auth.py`, `_config.py`, `_health.py`,
  …), with its tests in `tests/test_<area>*.py`. Leave this project's
  `fastmcp-pvl-core` constraint in `pyproject.toml` alone: it is
  template-owned (it sits above the `PROJECT-DEPS` block). After the
  library release:
  - if the constraint admits the release, run
    `uv lock --upgrade-package fastmcp-pvl-core` and commit `uv.lock`,
    which this project owns;
  - otherwise (a fix that needs a higher floor, or the next major), open a
    template PR that bumps the constraint in `pyproject.toml.jinja`; this
    project gets it on its next `copier update`.
- **Template-level fix** (anything template-owned: `Dockerfile`, workflows,
  `server.py` skeleton, `AGENTS.md` sections, template documentation pages):
  open a PR on `pvliesdonk/fastmcp-server-template`. Edit the rendered
  file's path with `.jinja` appended (`docs/deploy/docker.md` comes from
  `docs/deploy/docker.md.jinja`), or the same path for a file the template
  copies verbatim, such as this one. After the template release, the weekly
  `copier update` workflow brings the fix here; dispatch it manually to get
  it sooner.
- **Domain-only fix** (anything inside a `DOMAIN-*`, `CONFIG-*` or
  `PROJECT-*` sentinel block, `tools.py`, `resources.py`, `prompts.py`,
  `domain.py`, `tests/`): open a PR on this repo.
