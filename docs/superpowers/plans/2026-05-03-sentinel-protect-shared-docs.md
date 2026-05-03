# Sentinel-protect shared docs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move three shared-infrastructure docs (`docs/deployment/docker.md`, `docs/deployment/oidc.md`, `docs/guides/authentication.md`) out of `_skip_if_exists` and add `DOMAIN-{TOPIC}-EXTRA` sentinel blocks at end-of-file, so future template improvements flow to downstream consumers while their domain-specific notes survive `copier update`.

**Architecture:** Two-part atomic change in a single PR — drop three lines from `copier.yml`'s `_skip_if_exists` so future template updates flow through, AND append `DOMAIN-{TOPIC}-EXTRA-START`/`-END` sentinel blocks to each of the three `.jinja` files so downstream notes land inside a copier-update-safe zone. Block contains a `## Project-specific notes` heading so downstream's content has a visible home in the published docs site.

**Tech Stack:** `copier` (template renderer, reads `copier.yml`), `mkdocs-material` + `mkdocs-llmstxt` (docs site, validated via `mkdocs build --strict` in `template-ci.yml`'s `downstream-gate` job), HTML comments inside markdown for sentinel markers (matches the pre-existing `<!-- DOMAIN-START -->` convention in `CLAUDE.md.jinja` and `README.md.jinja`).

---

## File Structure

| File | Change | Responsibility |
|---|---|---|
| `copier.yml` | Modify (remove 3 lines from `_skip_if_exists`) | Stop preserving downstream's whole-file copies on update |
| `docs/deployment/docker.md.jinja` | Append ~6 lines (DOMAIN-DOCKER-EXTRA block) | Container deployment doc + downstream notes zone |
| `docs/deployment/oidc.md.jinja` | Append ~6 lines (DOMAIN-OIDC-EXTRA block) | OIDC deployment doc + downstream notes zone |
| `docs/guides/authentication.md.jinja` | Append ~6 lines (DOMAIN-AUTH-EXTRA block) | Auth conceptual guide + downstream notes zone |

No new files. No deletions. No tests touched (existing `template-ci.yml` `mkdocs build --strict` gate covers verification).

---

## Task 1: Predict case-3 migration risk per downstream

**Why first:** Spec says "Manual verification before merging: spot-check each downstream's actual current docker.md / oidc.md / authentication.md against the template's content to predict how many will hit case-3 conflicts." If any downstream is heavily customised, document that in the PR body so the user knows to budget reconciliation time.

**Files:**
- Read: `docs/deployment/docker.md.jinja`, `docs/deployment/oidc.md.jinja`, `docs/guides/authentication.md.jinja` (template versions)
- Read via gh API: same three paths in each of `pvliesdonk/image-generation-mcp`, `pvliesdonk/markdown-vault-mcp`, `pvliesdonk/scholar-mcp`, `pvliesdonk/paperless-mcp`

- [ ] **Step 1: Render the template's current shape**

```bash
rm -rf /tmp/smoke
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
```

Expected: render succeeds.

- [ ] **Step 2: Diff each downstream's current file against the rendered template**

For each of the 4 downstream consumers and 3 files, fetch and diff:

```bash
for repo in image-generation-mcp markdown-vault-mcp scholar-mcp paperless-mcp; do
  for path in docs/deployment/docker.md docs/deployment/oidc.md docs/guides/authentication.md; do
    echo "=== $repo $path ==="
    # Render the downstream-equivalent path by mapping {project_name}/{python_module}
    # against the smoke fixture's substitutions, OR just compare raw structure
    # since the smoke render uses smoke-mcp/smoke_mcp and downstreams use their own.
    # Diff against the unrendered .jinja for shape, not exact-match — what we want
    # to know is: did downstream add new sections, or only edit substituted strings?
    gh api "repos/pvliesdonk/$repo/contents/$path" --jq '.content' 2>/dev/null \
      | base64 -d > /tmp/$repo-$(basename $path) 2>/dev/null \
      || echo "  (file not present)"
  done
done
```

Expected: each file fetched (or "file not present" noted).

- [ ] **Step 3: Categorise each file as case-1 / case-2 / case-3**

Per the spec migration table, for each fetched downstream file inspect:

- **Case 1 (clean merge — unchanged):** structure matches template exactly modulo project-name substitutions. Look for: same section headings, same paragraph order, same example values modulo `{project_name}`.
- **Case 2 (clean — additions only at end):** template content intact, with extra paragraphs/sections appended after the last template section. These will land inside the new EXTRA block automatically.
- **Case 3 (conflict — mid-file edits):** template content has been replaced or edited inline (e.g. paragraph rewritten, section reordered, env var renamed). These will need one-time reconciliation.

Record each (repo, file) → category. Plain text notes file is fine.

- [ ] **Step 4: Summarise findings for the PR body**

Write a 3-5 line summary of which downstreams hit which case. Save to `/tmp/migration-summary.txt` for inclusion in the PR body in Task 8. Example shape:

```
Migration prediction (4 consumers × 3 files = 12 cells):
- Case 1 (clean — no customisation): N cells
- Case 2 (additions land in EXTRA block automatically): N cells
- Case 3 (one-time mid-file conflict): N cells
  - <repo> <file>: <one-line description of the customisation that will conflict>
```

If all 12 cells are case-1 or case-2, note that no manual reconciliation is expected.

- [ ] **Step 5: Commit only if any notes were added**

This task produces no code changes — skip commit.

---

## Task 2: Drop three files from `_skip_if_exists`

**Files:**
- Modify: `copier.yml` (remove 3 lines, currently around line 56-58 in the `_skip_if_exists` list)

- [ ] **Step 1: Find the exact line numbers**

Run: `grep -n "docs/deployment/docker.md\|docs/deployment/oidc.md\|docs/guides/authentication.md" copier.yml`

Expected output (line numbers may shift slightly):
```
56:  - "docs/deployment/docker.md"
57:  - "docs/deployment/oidc.md"
58:  - "docs/guides/authentication.md"
```

- [ ] **Step 2: Edit `copier.yml` to remove those three lines and the preceding comment block**

The current block (preceded by an explanatory comment):

```yaml
  # Shared deployment/auth docs — rendered as starter content on first copy,
  # but consumers typically customize them with domain-specific env vars,
  # auth flows, and deployment notes.  Protected from copier update to avoid
  # clobbering that customization.  Tracked for future sentinel-based
  # protection in issue #29.
  - "docs/deployment/docker.md"
  - "docs/deployment/oidc.md"
  - "docs/guides/authentication.md"
```

Replace with NOTHING (remove the entire block including the explanatory comment, since the explanation is now obsolete — issue #29 IS this PR).

Use the Edit tool with `old_string` set to the full block above and `new_string` empty.

- [ ] **Step 3: Verify the edit**

Run: `grep -n "docs/deployment\|docs/guides/authentication" copier.yml`

Expected: matches only inside `_exclude` (where the three files don't appear) or in test fixture references — NOT inside `_skip_if_exists`.

- [ ] **Step 4: Don't commit yet**

Tasks 3-5 also modify files; they all commit together at the end of Task 6 (after gate green). This keeps the change atomic per the spec's "two-part change in a single PR" requirement.

---

## Task 3: Add DOMAIN-DOCKER-EXTRA block to `docker.md.jinja`

**Files:**
- Modify: `docs/deployment/docker.md.jinja` (append at end)

- [ ] **Step 1: Read the file's current end-of-file**

Run: `tail -10 docs/deployment/docker.md.jinja`

Confirm the file ends with a section like `## UID/GID` content. The new block goes after the last existing line.

- [ ] **Step 2: Append the DOMAIN-DOCKER-EXTRA block**

Use the Edit tool. Set `old_string` to the last few lines of the file (enough to be unique). Set `new_string` to the same content followed by:

```markdown


<!-- DOMAIN-DOCKER-EXTRA-START -->
<!-- Project-specific notes for Docker deployment; kept across copier update. -->

## Project-specific notes

<!-- Add domain-specific caveats here (e.g. "the /data/uploads volume must
     be writable by UID Y", "container needs cap_add: SYS_PTRACE for
     debugging tools"). Use sub-headings to organize if needed. -->

<!-- DOMAIN-DOCKER-EXTRA-END -->
```

Note: blank line BEFORE `<!-- DOMAIN-DOCKER-EXTRA-START -->` separates it from the preceding template section. The `## Project-specific notes` heading is INSIDE the sentinel block so the rendered docs site shows a labeled section even when downstream hasn't customised yet.

- [ ] **Step 3: Verify**

Run: `tail -15 docs/deployment/docker.md.jinja`

Expected: ends with `<!-- DOMAIN-DOCKER-EXTRA-END -->` followed by trailing newline.

- [ ] **Step 4: Don't commit yet**

---

## Task 4: Add DOMAIN-OIDC-EXTRA block to `oidc.md.jinja`

**Files:**
- Modify: `docs/deployment/oidc.md.jinja` (append at end)

- [ ] **Step 1: Read the file's current end-of-file**

Run: `tail -10 docs/deployment/oidc.md.jinja`

Confirm the file ends with `## Subpath Deployments` content or similar.

- [ ] **Step 2: Append the DOMAIN-OIDC-EXTRA block**

Use the Edit tool. Same pattern as Task 3. Append:

```markdown


<!-- DOMAIN-OIDC-EXTRA-START -->
<!-- Project-specific notes for OIDC deployment; kept across copier update. -->

## Project-specific notes

<!-- Add domain-specific caveats here (e.g. "Keycloak requires X claim",
     "Authelia token-cache quirk for /admin paths", "this server's audience
     claim must include 'mcp'"). Use sub-headings to organize if needed. -->

<!-- DOMAIN-OIDC-EXTRA-END -->
```

- [ ] **Step 3: Verify**

Run: `tail -15 docs/deployment/oidc.md.jinja`

Expected: ends with `<!-- DOMAIN-OIDC-EXTRA-END -->` followed by trailing newline.

- [ ] **Step 4: Don't commit yet**

---

## Task 5: Add DOMAIN-AUTH-EXTRA block to `authentication.md.jinja`

**Files:**
- Modify: `docs/guides/authentication.md.jinja` (append at end)

- [ ] **Step 1: Read the file's current end-of-file**

Run: `tail -10 docs/guides/authentication.md.jinja`

Confirm the file ends with `## Known Limitations: MCP OAuth token refresh` content or similar.

- [ ] **Step 2: Append the DOMAIN-AUTH-EXTRA block**

Use the Edit tool. Same pattern as Tasks 3 and 4. Append:

```markdown


<!-- DOMAIN-AUTH-EXTRA-START -->
<!-- Project-specific notes for authentication; kept across copier update. -->

## Project-specific notes

<!-- Add domain-specific caveats here (e.g. "paperless-mcp tokens expire
     every 60 min", "this server requires the 'admin' scope for write tools",
     "bearer-token middleware skips /health for liveness probes"). Use
     sub-headings to organize if needed. -->

<!-- DOMAIN-AUTH-EXTRA-END -->
```

- [ ] **Step 3: Verify**

Run: `tail -15 docs/guides/authentication.md.jinja`

Expected: ends with `<!-- DOMAIN-AUTH-EXTRA-END -->` followed by trailing newline.

- [ ] **Step 4: Don't commit yet**

---

## Task 6: Render + full gate verification + atomic commit

**Files:**
- Read: rendered `/tmp/smoke/` after copier render
- Test: `template-ci.yml` gate equivalents run locally

- [ ] **Step 1: Render the template against smoke fixture**

```bash
rm -rf /tmp/smoke
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
```

Wait — copier reads from the git index. Since Tasks 2-5 are uncommitted, the render won't pick them up. We need to commit first OR add `--vcs-ref=HEAD~0` won't help either. The right call: commit a WIP commit to a temporary throwaway, render, then if green proceed to the real commit. Simpler: just commit first (Task 2-5 changes together) and render against that commit.

Reorder: commit first, then verify. Step 2 below does both.

- [ ] **Step 2: Stage and commit the 4-file change**

```bash
git add copier.yml docs/deployment/docker.md.jinja \
        docs/deployment/oidc.md.jinja docs/guides/authentication.md.jinja
git status  # verify exactly these 4 files are staged
```

Expected `git status` output:
```
modified:   copier.yml
modified:   docs/deployment/docker.md.jinja
modified:   docs/deployment/oidc.md.jinja
modified:   docs/guides/authentication.md.jinja
```

Then commit with a HEREDOC message:

```bash
git commit -m "$(cat <<'EOF'
feat(template): sentinel-protect shared deployment + auth docs (closes #29)

Three template-owned docs files lived in `_skip_if_exists`, so future
template improvements never reached downstream consumers and downstream
customisations could never coexist with template updates:

- docs/deployment/docker.md
- docs/deployment/oidc.md
- docs/guides/authentication.md

Two-part change (atomic — neither alone solves the problem):

1. Drop the three files from `copier.yml`'s `_skip_if_exists` list so
   future template updates flow through to downstream on `copier update`
   via copier's standard 3-way merge.

2. Append `DOMAIN-{TOPIC}-EXTRA-START` / `-END` sentinel blocks at
   end-of-file in each of the three .jinja files. Each block contains
   a `## Project-specific notes` heading so downstream's domain-specific
   notes have a visible home in the published docs site.

Sentinel names follow the post-#91 unified `DOMAIN-*` family (used for
prose-customisation in template-owned markdown like CLAUDE.md.jinja
and README.md.jinja). The post-#97 "Domain-only fix" enumeration in
CLAUDE.md.jinja already says "anything inside a `DOMAIN-*`, `CONFIG-*`,
or `PROJECT-*` sentinel block" — captures the new family without
further docs edits.

## Migration story for the 4 existing downstream consumers

On the next `copier update` after this lands, each downstream sees three
changed files. Per-file 3-way merge:

- Unchanged from template → clean merge, picks up new template content +
  new empty DOMAIN-EXTRA block at end.
- Customised inside what becomes the EXTRA zone (end-of-file additions)
  → clean, additions land inside the new sentinel markers via standard
  3-way merge.
- Customised by replacing/editing template content (mid-file edits) →
  conflict markers, one-time fix-up to relocate the customisation into
  the new `## Project-specific notes` block.

[Engineer: paste the contents of /tmp/migration-summary.txt produced
by Task 1 Step 4 here, replacing this placeholder block. If the file
is empty / unrun, run Task 1 first.]

The remaining `_skip_if_exists` docs (`docs/index.md`, `docs/installation.md`,
`docs/configuration.md`, `docs/tools/index.md`, `docs/prompts.md`) stay as
project-narrative pages — different design space per file, tracked
separately in #106.

Spec: docs/superpowers/specs/2026-05-03-sentinel-protect-shared-docs-design.md

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Expected: commit succeeds with the 4 files included.

- [ ] **Step 3: Render the template after commit**

```bash
rm -rf /tmp/smoke
uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
```

Expected: render succeeds.

- [ ] **Step 4: Verify the rendered files contain the sentinels**

```bash
grep "DOMAIN-DOCKER-EXTRA" /tmp/smoke/docs/deployment/docker.md
grep "DOMAIN-OIDC-EXTRA" /tmp/smoke/docs/deployment/oidc.md
grep "DOMAIN-AUTH-EXTRA" /tmp/smoke/docs/guides/authentication.md
```

Expected: each grep returns 2 lines (START + END markers).

- [ ] **Step 5: Run mkdocs build --strict on the rendered project**

```bash
cd /tmp/smoke
uv sync --no-default-groups --group docs --frozen 2>&1 | tail -2 \
  || uv sync --no-default-groups --group docs 2>&1 | tail -2  # fallback if no uv.lock
uv run mkdocs build --strict 2>&1 | tail -5
```

Expected: `Documentation built in <Ns> seconds` with no warnings/errors. The HTML comments inside the sentinel blocks render as nothing in the output (they're markdown comments, stripped by the parser).

- [ ] **Step 6: Verify the rendered docs site shows the new section**

```bash
grep -A 2 "Project-specific notes" /tmp/smoke/site/deployment/docker/index.html | head -5
```

Expected: an empty H2 section labeled "Project-specific notes" appears in the rendered HTML for each of the three pages.

- [ ] **Step 7: Run the full template gate (the same gate template-ci.yml runs)**

```bash
cd /tmp/smoke
uv sync --all-extras --all-groups
uv run ruff check .
uv run ruff format --check .
uv run mypy src/ tests/
uv run pytest -x -q
```

Expected: all green (this is just a docs-only change, but the standard gate confirms nothing else broke).

- [ ] **Step 8: If gate fails, fix forward**

If any step in 5-7 fails:
- amend the commit with the fix: `git add <fixed-files> && git commit --amend --no-edit`
- re-render and re-run from Step 3

Don't commit a separate "fix" commit — keep the change atomic per the spec.

---

## Task 7: Local review circus

**Files:**
- Read: the entire commit diff (`git show HEAD`)

Per the project's `pr-workflow` discipline (CLAUDE.md), run both subagent reviewers on the diff before pushing.

- [ ] **Step 1: Dispatch primary reviewer**

Use the Agent tool with `subagent_type=pr-review-toolkit:code-reviewer`. Prompt should include:

- The PR closes #29
- Two-part change: drop from `_skip_if_exists` + add DOMAIN-EXTRA sentinels
- The migration story summary from Task 1
- Verification: rendered template passes `mkdocs build --strict`, full gate green
- Bar: nothing flagged at any severity

- [ ] **Step 2: Dispatch second-opinion reviewer**

Use the Agent tool with `subagent_type=superpowers:code-reviewer`. Same context as Step 1, framed as "fresh independent read, don't confirm the other reviewer".

- [ ] **Step 3: Address findings**

If either reviewer flags anything at any severity:
- Address the finding (or defend in writing if the reviewer is wrong)
- Amend the commit (`git add ... && git commit --amend --no-edit`)
- Re-render + re-run gate (Task 6 Step 3-7)
- Re-dispatch BOTH reviewers on the new diff (per the project rule "Re-run until clean")

Loop until both reviewers report nothing at any severity.

- [ ] **Step 4: No commit step here — Task 6's commit is amended in place**

---

## Task 8: Push as draft, await CI/bot, address findings, flip ready

**Files:**
- None modified directly; only push + bot interaction

- [ ] **Step 1: Push the branch**

```bash
git push -u origin feat/sentinel-protect-shared-docs
```

Expected: push succeeds.

- [ ] **Step 2: Open the PR as draft**

```bash
gh pr create --draft --title "feat(template): sentinel-protect shared deployment + auth docs" --body "$(cat <<'EOF'
## Summary

Two-part change in a single PR. Closes #29.

1. **Drop from `_skip_if_exists`** — `docs/deployment/docker.md`, `docs/deployment/oidc.md`, `docs/guides/authentication.md` move out of the skip-list so future template improvements (new env vars, OIDC quirks, container best-practices) flow to downstream consumers on `copier update`.
2. **Add `DOMAIN-{TOPIC}-EXTRA` sentinel blocks** at end-of-file in each of the three `.jinja` files. Block contains a `## Project-specific notes` heading so downstream's domain notes survive future template updates AND have a visible home in the published docs site.

Sentinel naming uses the post-#91 unified `DOMAIN-*` family. Post-#97 "Domain-only fix" enumeration in CLAUDE.md.jinja already covers it.

## Migration prediction (case-3 risk)

[Engineer: paste the contents of /tmp/migration-summary.txt from Task 1 Step 4 here, replacing this placeholder block.]

## Out of scope

The remaining `_skip_if_exists` docs (`docs/index.md`, `docs/installation.md`, `docs/configuration.md`, `docs/tools/index.md`, `docs/prompts.md`) — different per-file design space, tracked in #106.

## Test plan

- [x] Rendered template with `--vcs-ref=HEAD` against `tests/fixtures/smoke-answers.yml`. All three sentinel blocks present in rendered output.
- [x] `mkdocs build --strict` succeeds on the rendered project; new `## Project-specific notes` heading visible in the rendered HTML.
- [x] Full gate green: `ruff check`, `ruff format --check`, `mypy src/ tests/`, `pytest -x -q`.
- [x] Local review circus: both pr-review-toolkit and superpowers, nothing flagged at any severity.
- [ ] template-ci.yml runs the full Python 3.11–3.14 matrix + `mkdocs build --strict` gate once landed on the branch.

## Spec

`docs/superpowers/specs/2026-05-03-sentinel-protect-shared-docs-design.md`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: PR opens as draft, CI starts.

- [ ] **Step 3: Wait for CI + claude-review (auto on draft push)**

Schedule a wakeup ~4 min out. When it fires:

```bash
gh pr checks <PR-number>
```

Expected: all green.

- [ ] **Step 4: Read all 4 review surfaces (per `feedback_read_all_review_surfaces.md`)**

```bash
gh api repos/pvliesdonk/fastmcp-server-template/issues/<PR>/comments \
  --jq '[.[] | select(.user.login | contains("claude"))] | last | .body' \
  | tail -25
gh api repos/pvliesdonk/fastmcp-server-template/pulls/<PR>/reviews
gh api repos/pvliesdonk/fastmcp-server-template/pulls/<PR>/comments
```

Verify ALL four signals (CI status + claude-review body LGTM + gemini formal review LGTM + zero unresolved inline comments).

- [ ] **Step 5: Address any findings (one round only, per project's bot-iteration cap)**

If any bot flags anything:
- Address the finding (or defend in PR comment if bot is wrong — don't push without addressing)
- Re-run the local review circus (Task 7) on the new diff before pushing
- Force-push the amend: `git push --force-with-lease origin feat/sentinel-protect-shared-docs`
- Schedule another wakeup ~4 min out, return to Step 3

If a SECOND round of bot findings appears, surface to user — per the project's "if a third round is needed, surface to the user" rule (the third round = round 2 of iteration after the initial post-open review).

- [ ] **Step 6: Flip ready**

Once all 4 surfaces are clean:

```bash
gh pr ready <PR-number>
```

Expected: `✓ Pull request ... is marked as "ready for review"`.

- [ ] **Step 7: Re-trigger gemini after flip-to-ready (optional but recommended)**

Per the global CLAUDE.md, gemini-code-assist auto-runs on PR open + flip-to-ready (subject to per-repo `.gemini/config.yaml`). If the `.gemini/config.yaml` has `include_drafts: false` (which it does in this repo per #84), then flipping ready triggers gemini's first review on this PR. Schedule a wakeup ~10 min out and re-check all 4 surfaces.

If gemini finds something on the flip-to-ready review, that's still round 1 of gemini iteration (the draft phase only had claude-review). Address per Step 5 cap rules.

- [ ] **Step 8: Report final state**

Once all 4 surfaces clean and PR is ready, report status to user. The PR is then awaiting human merge — don't merge autonomously.

---
