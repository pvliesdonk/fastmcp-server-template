# Claude Code agent for copier-update PRs

**Issue:** [#36](https://github.com/pvliesdonk/fastmcp-server-template/issues/36)
**Date:** 2026-05-04
**Status:** Approved (awaiting implementation plan)

## Problem

The weekly `copier-update.yml` cron in each downstream consumer (`image-generation-mcp`, `markdown-vault-mcp`, `scholar-mcp`, `paperless-mcp`) opens a PR carrying the latest template changes. The existing workflow (post-#49) builds a rich PR body with delta / release notes / diff / conflict-file list — but the *interpretation* of that material remains entirely manual. Operators repeatedly hand-analyze the same patterns:

- New sentinels appeared in the template; downstream's mid-file customisation needs migrating into the new sentinel zone (the #29/#108 case-3 pattern, observed on 9 of 12 cells in the most recent migration prediction).
- A file dropped from `_skip_if_exists`; copier resyncs as if first-time, conflict markers everywhere; downstream-specific bits need parsing out into the appropriate sentinel block.
- Files sit in `_exclude` (e.g. `tests/test_tools.py`, `docs/design.md`); template's own `.jinja` source has evolved between refs but downstream's local copy didn't get touched. Whether to port the upstream evolution is a judgment call per file.
- The CHANGELOG between two refs has accumulated entries; some ship through automatically, some need opt-in (e.g. a new tool wired in `_server_deps.py` which is in `_skip_if_exists`), some are template-internal noise. Operator triages each one to know what they just got.

These are exactly the cases where Claude Code can help — read the template's history at both refs, classify each item, articulate trivial mechanical fixes for auto-commit, surface the rest for human judgment in the PR body.

## Scope

Three jobs, all part of the same `copier-update.yml` workflow extension:

- **Job A — Conflict resolution** (T1 + T2 from issue #36). Claude reads each `<<<<<<< before updating` / `>>>>>>>` region in conflicted files. Trivial mechanical fixes are applied as one atomic auto-commit; non-trivial cases get a per-conflict triage paragraph in the PR body.
- **Job B — Changelog triage**. Claude reads the template's CHANGELOG between downstream's previous `_commit` and the new ref. Per-entry classification: ships-automatically / needs-opt-in / informational. Action-required entries get full prose in the PR body; rest get one-line entries or roll-up counts.
- **Job C — Excluded-file evolution**. For each `.jinja`-suffixed entry under `_exclude`, Claude diffs the template's source between the two refs. Per-file classification: recommend-port / skip / informational. Action-required diffs get full prose; rest collapse.

**Out of scope** (deferred per Q1.D in brainstorming):

- **Tier 3 from #36** — claude-code opens an upstream PR on the template repo when it detects a template bug. Different repo, different secret, different review surface. Defer to a separate spec; pursue once Job A's accuracy is observed in the wild.

## Architecture

The workflow extends `.github/workflows/copier-update.yml.jinja` (renders to each downstream's `.github/workflows/copier-update.yml`). Workflow shape after the change:

```
1. Checkout downstream + read previous _commit                          (existing)
2. Run copier update --conflict=inline → conflict_count, conflict_files (existing)

3. Clone fastmcp-server-template into /tmp/template                     (NEW)
4. Check CLAUDE_CODE_OAUTH_TOKEN availability                           (NEW — gating gate)
5. Three parallel claude-code steps (gated on token + per-job triggers) (NEW)
   - Job A: only if conflict_count > 0
   - Job B: when refs differ
   - Job C: when refs differ
6. Aggregator step composes PR body                                     (NEW)
7. Open or update PR with composed body + push                          (existing, lightly modified)
```

Steps 3-6 are **all failure-tolerant**. A PR is always opened as long as the existing copier update + conflict detection (steps 1-2) succeeded. The existing #49-shaped body sections (delta/notes/diff/conflicts) ALWAYS render regardless of agent state.

Each agent step uses `continue-on-error: true` and writes its output to a workspace file (`/tmp/agent-job-{a,b,c}.json`). The aggregator reads each file independently. Missing or errored outputs render as state-specific placeholders without affecting other sections.

**Job A's auto-commits** happen as a single atomic `git commit` at the end of the agent's reasoning. Mid-flight crashes leave the working tree clean — no partial state lands on the branch.

The template clone (step 3) gives Jobs A/B/C local-filesystem access to `/tmp/template` at any ref via `git checkout`. This matches the tool shape Claude Code uses elsewhere (file reads, `git log`, `git diff`); no API rate-limit bookkeeping inside agent prompts.

## Per-job agent contracts

Each of the three claude-code invocations has its own prompt template, allowed-tools constraint, and JSON output schema.

### Job A — Conflict resolution

- *Trigger:* `conflict_count > 0` AND `agent_enabled == true`
- *Allowed tools:* file read/write, `git add` / `git commit` (constrained to one final commit at the end)
- *Task:* for each `<<<<<<<` / `>>>>>>>` region in each conflict file, decide auto-resolvable or needs-review.
  - **Auto-resolvable** = agent can articulate the precise transformation in *one sentence* with no ambiguity about which downstream lines belong where (Q5.B with mandatory articulation).
  - For auto-resolvable: apply resolution to the working tree + record `{file, region, classification: "auto", articulation, resolved_diff_excerpt}`.
  - For needs-review: leave conflict markers in place + record `{file, region, classification: "review", recommended_resolution, reasoning}`.
- *Final action:* if any auto-resolutions were applied, single `git commit -m "auto-resolve <N> trivial conflicts (claude-code)"` carrying all of them.
- *Output:* `/tmp/agent-job-a.json`:
  ```json
  {
    "status": "ok",
    "auto_resolved": [
      {"file": "...", "region": "L42-L78", "articulation": "...", "commit_sha": "..."}
    ],
    "needs_review": [
      {"file": "...", "region": "L120-L145", "recommended_resolution": "...", "reasoning": "..."}
    ]
  }
  ```

### Job B — Changelog triage

- *Trigger:* refs differ AND `agent_enabled == true`
- *Allowed tools:* file read only (no git mutations)
- *Task:* for each entry in `/tmp/template/CHANGELOG.md` between `(previous_commit, new_ref]`, classify as one of three:
  - `ships-automatically` — template-owned file changed; downstream gets it via this update with no further action.
  - `needs-opt-in` — downstream must wire something (uncomment scaffold, add env var, register a tool, etc.).
  - `informational` — internal template-side change (CI plumbing, release wiring, docs-only) with no downstream-facing effect.
- For each entry, write one-paragraph operator-relevant summary.
- *Output:* `/tmp/agent-job-b.json`:
  ```json
  {"status": "ok", "entries": [{"pr_number": 89, "title": "...", "classification": "needs-opt-in", "summary": "..."}]}
  ```

### Job C — Excluded-file evolution

- *Trigger:* refs differ AND `agent_enabled == true`
- *Allowed tools:* file read, `git log`, `git diff` (no mutations)
- *Task:* for each `.jinja`-suffixed entry in `/tmp/template/copier.yml`'s `_exclude` list (skip directory globs and stock excludes like `.git`, `*.pyc`):
  - Run `git diff <previous_commit>..<new_ref> -- <path>`. Empty diff → skip.
  - Classify the diff: `recommend-port` (downstream's local copy benefits from the upstream change), `skip` (template-maintainer concern only), `informational`.
  - Write short summary of what changed.
- *Output:* `/tmp/agent-job-c.json`:
  ```json
  {"status": "ok", "files": [{"file": "...", "classification": "recommend-port", "summary": "...", "diff_summary": "..."}]}
  ```

## PR body composition

The aggregator (step 6) reads `/tmp/agent-job-{a,b,c}.json` and composes a body of this shape:

```markdown
## Template update: vX.Y.Z → vA.B.C       (existing — from #49)

### Release notes                          (existing — from #49)
### Diff summary                           (existing — from #49)
### Conflicts                              (existing — from #49, file list)

---

## Agent analysis

### 🔧 Conflict resolutions               (Job A — present only if conflict_count > 0)

**Auto-committed by claude-code** — VERIFY before merging:
- `oidc.md` (commit abc1234): _Moved 12 lines of "remote OIDC mode" customisation
  into the new DOMAIN-OIDC-EXTRA block; template body accepted unchanged._

**Needs review** — conflict markers remain, operator must resolve:
- `authentication.md`: Conflict between template's new "MCP OAuth refresh" section
  and downstream's renamed cross-reference anchor. Recommended approach: ...

### ✨ New features in this update         (Job B — always present when refs differ)

**Needs your attention** (action-required, full prose):
- #89 wire register_server_info_tool — needs opt-in. ...

**Ships through automatically** (informational, one-line each):
- #84 ship .gemini/config.yaml — applied this run
- ...

**Internal / no downstream effect** (count rollup):
- 4 informational entries: #87, #91, #93, #97

### 📦 Excluded-file upstream changes       (Job C — always present when refs differ)
(Same three-stratum structure: recommend-port / skip / informational)
```

### Stratification rules

- **Action-required class** — full prose paragraph in body (the "Auto-committed verify" + "Needs review" + "Needs your attention" + "Recommend port" buckets).
- **Informational class** — one-line entries.
- **Roll-up class** — count + ID list (no per-item prose).

The agent's JSON output drives classification per item; aggregator renders.

### Auto-commit articulation surfaces here verbatim

Per Q5.B's mandatory-articulation constraint: every auto-committed item shows the agent's one-sentence rationale + commit SHA, so the operator can scrutinize the actual diff before merging.

### Overflow safety net (per Q4)

After composition, if body length > 60k chars (safety margin under GitHub's 65k limit):

1. Take the longest action-required section (typically Job A or B's prose stratum).
2. Replace it in the body with: `[full <section> analysis in comment #N below — N items]`.
3. Post the spilled content as a follow-up PR comment.
4. Re-measure; if still > 60k, repeat with the next-longest section.

For determinism across re-runs (same template state → same body), the aggregator orders items consistently (PR# ascending) and renders deterministically; comment-spill happens to the same section across re-runs.

## Graceful fallback for missing token / agent failure

Two specific failure modes need explicit handling beyond the generic `continue-on-error`:

**(a) `CLAUDE_CODE_OAUTH_TOKEN` not set in the downstream repo.** Workflow detects this up-front (step 4 — token-check) and skips the agent steps. Aggregator renders an "agent disabled — token not configured" placeholder per section, distinct from the runtime-error placeholder so the operator knows it's a config issue.

**(b) claude-code rate limited / API failure.** Step writes a structured error to its JSON output. Two refinements:

1. **Distinguish rate-limit from generic failure** — when exit code + error message indicate 429/quota, agent step writes `{"status": "rate_limited"}`; aggregator renders "rate-limited — full analysis deferred to next cron" instead of generic "errored". Operator knows it's transient.
2. **No in-workflow retry** — per the global CLAUDE.md rate-limit discipline. Next weekly cron is the natural retry cycle.

### Aggregator's four-state contract per section

| Job state | Source signal | Body rendering |
|---|---|---|
| Success | JSON file present + valid + `status != "error"` | Full agent output, stratified + overflow-handled |
| Skipped (no token) | JSON file absent + `agent_enabled == false` upstream | "🔒 Agent disabled — `CLAUDE_CODE_OAUTH_TOKEN` not configured. To enable: ..." |
| Rate limited | JSON file contains `{"status": "rate_limited", ...}` | "⏳ Agent rate-limited — full analysis will retry on next cron." |
| Errored | JSON file contains `{"status": "error", "message": ...}` OR file missing despite `agent_enabled == true` | "⚠️ Agent failed — see workflow log [link]" |

In every case, the PR is opened with the composed body. The existing #49 sections (delta/notes/diff/conflicts) ALWAYS render regardless of agent state.

## Testing

**Tested:**

1. **Workflow YAML validity** — existing `template-ci.yml` smoke render verifies the rendered downstream workflow. New steps inherit this gate.
2. **Aggregator script unit tests** — `scripts/copier_update_aggregator.py` (in template repo, in `_skip_if_exists`, same pattern as `bump_manifests.py`); tests at `scripts/tests/test_copier_update_aggregator.py` (template-repo-only, excluded from rendering). New `template-ci.yml` job runs `pytest scripts/tests/`. Required cases:
   - Each of the four section states per Job (success / skipped / rate-limited / errored) renders correctly
   - Stratification correctly buckets items into action-required vs informational vs roll-up
   - Overflow safety net triggers when body > 60k; longest action-required section spills to follow-up comment
   - Deterministic ordering — same JSON inputs across re-runs produce byte-identical body
3. **Agent JSON schema validation** — aggregator validates each `/tmp/agent-job-*.json` against a fixed schema before consuming. Malformed → that section becomes errored placeholder. Tests cover schema failures.
4. **Cost gating verification (manual)** — first downstream cron after merge: workflow log shows Job A short-circuited when `conflict_count == 0`; Jobs B + C skipped when refs equal.

**Not tested:**

- LLM output quality / classification accuracy — observed empirically on first few real PRs; prompt-tuned based on operator feedback. No CI gate for "is the agent's reasoning good".
- Multi-cron-cycle drift (template advanced 2× since last sync) — deterministic-ordering invariant should handle; verified at first multi-version-jump cron.

## Cost & idempotency

**Cost discipline:**

- Job A only fires when `conflict_count > 0`. Most weekly cron runs hit zero conflicts (template advances rarely produce mid-file conflicts).
- Jobs B + C fire when refs differ. They skip when the cron has no work (template hasn't advanced).
- Steady state across the 4 downstream consumers: ~1-3 agent invocations per consumer per week, modulated by template release cadence. Below the operational-tooling cost noise floor.

**Idempotency:**

- The existing `copier-update.yml` rebuilds the `copier/update` branch fresh on every cron run (`git checkout -B`). Each run produces a fresh state.
- Aggregator's deterministic-ordering invariant means the same template state produces byte-identical output across re-runs. Rewriting the PR body on each run is the existing `#49` behaviour and stays unchanged.
- Job A's auto-commit lands ON the recreated branch; doesn't accumulate across cron cycles.

## Out of scope (separately tracked)

- **Tier 3 from #36** — upstream PR on template when claude detects a template bug. Defer pending Job A's observed accuracy.
- **Per-conflict commits** (each auto-resolution as its own commit instead of one atomic) — defer. Commits-per-resolution vs one-atomic is a UX preference that's hard to know in advance; observe on first real PR, revisit if operator finds the atomic shape unwieldy.
- **Manual `/agent` re-trigger** — defer; operator can re-dispatch the workflow if needed (existing capability).
