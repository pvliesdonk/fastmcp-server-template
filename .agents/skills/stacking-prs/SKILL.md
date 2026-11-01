---
name: stacking-prs
description: >-
  Use when one issue ships as several dependent pull requests: when asked to build stacked PRs or a stack, or when sizing a change splits it into more than one PR. Sets the plan's shape, the self-review gate between PRs, and the restack after a squash merge, with or without the gh-stack extension.
---

<!-- ===== TEMPLATE-OWNED — re-rendered on template updates. ===== -->

# Stacking pull requests

A stack is one issue shipped as several pull requests, each based on the branch of the one below it. It is not an epic: an epic groups issues. When the PRs must reach `main` together rather than one by one, run them on an integration branch instead (`docs/contribute/integration-branches.md`).

## 1. Plan the stack before the first edit

- Write the implementation plan with one section per PR, bottom first. Head each section with the PR's title, its branch, and its base: `main` for the bottom PR, the branch below for every other.
- Size each PR by the `authoring-issues-prs` skill's "Size the change before coding" step.
- End every PR's section with this task: pass the gates in `AGENTS.md`, run the `self-reviewing` skill against the PR's base, fix or justify every finding, push, and open the PR as a draft with `--base <base>`.
- Mark a section done in the plan once its PR is pushed. After a compaction, re-read the plan and resume at the first section not done.

## 2. Build one PR at a time

- Create a PR's branch only after the PR below is self-reviewed and pushed, and branch it from that pushed branch.
- Self-review each PR against its own base. One review over the whole stack is not a review of any PR in it.
- Write `Stacked on #<PR below>` and `Refs #<issue>` in each PR body; only the top PR carries `Closes #<issue>`.
- When a lower PR needs a change, commit it on that PR's branch, restack (step 3), and run `self-reviewing` again on each PR above before you push it: the `self-review` hook keys its record by commit, and a restack rewrites every commit above.
- Push one branch per `git push`: the `self-review` hook checks only the first branch of a push that sends several, so `gh stack push`, `sync` and `submit` bypass it for the rest.

## 3. Restack

With the `gh-stack` extension (`gh extension list` names it), restack with `gh stack rebase` and follow the `gh-stack` skill's non-interactive rules where your agent has it. Without the extension, run `gh extension install github/gh-stack` if the environment allows installing it; otherwise use git, from the top branch of the stack:

- `main` moved: `git fetch origin main && git rebase --update-refs origin/main`.
- The bottom PR was squash-merged:

  ```bash
  git fetch origin
  git rebase --update-refs --onto origin/main origin/<merged-branch>
  gh pr edit <PR above it> --base main
  ```

  `--update-refs` moves every branch in between along with the top one. After a squash merge, never rebase onto `main` without `--onto`: git replays the merged commits and conflicts with their squash. If `origin/<merged-branch>` is gone or no longer at the merged tip, pass the merged PR's last commit instead: `gh pr view <merged PR> --json headRefOid --jq .headRefOid`.

Then push each restacked branch with `git push --force-with-lease origin <branch>`, bottom first, each after its self-review.

## 4. Merge

Merge the bottom PR first. After it lands, restack and retarget (step 3) before you merge the next one.
