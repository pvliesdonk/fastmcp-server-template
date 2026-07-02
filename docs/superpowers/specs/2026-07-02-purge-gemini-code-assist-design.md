# Purge dead gemini-code-assist wiring from the template

**Date:** 2026-07-02
**Repo:** `pvliesdonk/fastmcp-server-template`
**Downstream tracking issue:** markdown-vault-mcp#797 (stays open until propagation)
**Status:** Approved design, ready for implementation plan.

## Problem

The `gemini-code-assist` hosted review bot **stopped operating on 2026-07-01**
(it no longer posts on any repo in the fleet). The template still ships its
config and documents it as a live merge gate, so every project generated from
the template — and every existing project on a `copier update` — inherits stale
references to a dead service:

- `.gemini/config.yaml` (+ `.gemini/config.yaml.jinja`) configure a bot that
  never runs.
- `CLAUDE.md.jinja` documents `gemini-code-assist` as a merge gate (line 103)
  and lists `.gemini/config.yaml` in the Shared Infrastructure "Ships…" list
  (line 251).
- `FORKING.md.jinja` (lines 32, 41) instructs detached forks to `rm -rf
  .gemini` and explains what it is.
- `.github/workflows/template-ci.yml`'s detach-fork smoke test (lines 346, 389,
  429) strips `.gemini` and asserts the CLAUDE.md bot paragraph gets scrubbed.

Because `CLAUDE.md` and `FORKING.md` are re-rendered on every `copier update`
(neither is in `_skip_if_exists`) and `.gemini/config.yaml` is **not** in
`_skip_if_exists` either, a downstream local edit would be reverted — so the
durable fix must be here, in the template.

## Coupling (the reason this is 5 files, not 2)

The CLAUDE.md bot paragraph, `FORKING.md`'s strip step, and the `template-ci`
smoke test are three views of one fact. Rewording the CLAUDE.md paragraph
without updating `template-ci.yml:389` would leave a **vacuous assertion**: the
grep `grep -qF 'claude-review, gemini-code-assist' CLAUDE.md` would never match
the new prose, so its `&& exit 1` never fires — it would pass by never testing
anything, silently rotting the detach-fork guarantee it exists to enforce. The
fork-strip machinery must move in lockstep with the prose it verifies.

## Design

One coherent PR: purge the dead service. Five files.

### 1. Delete the `.gemini/` directory

Remove both `.gemini/config.yaml` and `.gemini/config.yaml.jinja`. The service
is dead; the config does nothing.

### 2. `CLAUDE.md.jinja:103` — reword the bot-reviewer paragraph

Drop `gemini-code-assist`; make the paragraph singular around the one remaining
bot.

- **From:** `**Bot reviewers (claude-review, gemini-code-assist) are merge
  gates, not pair reviewers.** Local review must be complete before the PR
  opens. If a bot finds anything on first run, the local review was incomplete
  — that is a discipline failure to investigate, not "address-and-move-on." Run
  a local code-review pass on the cumulative diff before `gh pr create`; the
  bots are not a substitute.`
- **To:** `**The bot reviewer (claude-review) is a merge gate, not a pair
  reviewer.** Local review must be complete before the PR opens. If it finds
  anything on first run, the local review was incomplete — that is a discipline
  failure to investigate, not "address-and-move-on." Run a local code-review
  pass on the cumulative diff before `gh pr create`; it is not a substitute.`

### 3. `CLAUDE.md.jinja:251` — drop `.gemini/config.yaml` from the Ships-list

Remove the `` `.gemini/config.yaml` (gemini-code-assist scope control), ``
clause from the Shared Infrastructure sentence. The sentence keeps every other
listed artifact.

- **From:** `…`scripts/bump_manifests.py`, server.py skeleton, `.gemini/config.yaml` (gemini-code-assist scope control), and this very section of CLAUDE.md.`
- **To:** `…`scripts/bump_manifests.py`, server.py skeleton, and this very section of CLAUDE.md.`

### 4. `FORKING.md.jinja` — remove the `.gemini` strip step

- Line 32: remove the `rm -rf .gemini` line from the Step 2 prune command block.
- Line 41: remove the `` - `.gemini/` — gemini-code-assist fleet scope control. ``
  bullet from the "What this removes and why" list.

The surrounding `rm -f …/copier-update.yml …/claude.yml …/claude-code-review.yml`
and `scripts/copier_update_*` lines stay.

### 5. `.github/workflows/template-ci.yml` — sync the detach smoke test

- Line 346: remove `rm -rf .gemini` from the Step-2 prune command.
- Line 389: update the scrub assertion so it stays meaningful against the
  reworded prose. The paragraph is inside the `<!-- TEMPLATE-TRACKING -->`
  range that the smoke test's `sed` range-delete removes, so the assertion
  verifies that scrub. Change the grepped literal to a substring unique to the
  **reworded** paragraph:
  - **From:** `grep -qF 'claude-review, gemini-code-assist' CLAUDE.md \`
  - **To:** `grep -qF 'bot reviewer (claude-review)' CLAUDE.md \`
- Line 429: remove `.gemini \` from the "stripped files gone" assertion loop
  (the file no longer ships, so asserting the detach removed it is stale).

## Scope

One PR on `fastmcp-server-template`, off a fresh `origin/main` (v2.10.0). Needs
its own issue on that repo (`Closes #N`). Branch: `chore/purge-gemini-code-assist`.

**Downstream:** markdown-vault-mcp#797 stays **open**. After this PR merges +
the template releases, a `copier update` on markdown-vault-mcp re-renders
CLAUDE.md (bot prose + Ships-list) and removes `.gemini/config.yaml`, closing
#797. A note goes on #797 recording that the durable fix is upstream and #797
closes on the propagation update.

## Explicitly out of scope

- `CHANGELOG.md:171` (`#84 … ship .gemini/config.yaml`) — historical
  PSR-managed record; append-only, not rewritten.
- `docs/superpowers/**` — gitignored working docs; every hit is historical
  plan/spec text, not live wiring.
- `scripts/tests/test_copier_update_aggregator.py:91,119` — uses the string
  `".gemini/config.yaml"` only as **synthetic fixture data** for a copier-update
  aggregator test (an arbitrary example changelog title); it is not Gemini
  wiring and asserting on it is unrelated to this change.

## Verification

```bash
# .gemini gone
[ ! -e .gemini ] && echo OK
# no live gemini refs in the rendered-source files this PR owns
! grep -rniI 'gemini' CLAUDE.md.jinja FORKING.md.jinja .github/workflows/template-ci.yml && echo OK
# the smoke-test assertion greps the reworded literal
grep -qF 'bot reviewer (claude-review)' .github/workflows/template-ci.yml && echo OK
# template-ci smoke test still passes end-to-end (CI)
```

Remaining `gemini` hits after the PR are confined to `CHANGELOG.md`,
`docs/superpowers/**`, and the aggregator test fixture — all out of scope above.

## Open questions

None. Purge-vs-neutralize (delete `.gemini/` vs leave a disabled config) and the
`template-ci.yml` assertion sync are both settled: delete, and sync the
assertion to the reworded literal.
