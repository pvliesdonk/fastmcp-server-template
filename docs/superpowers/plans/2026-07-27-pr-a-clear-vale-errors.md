# PR A: clear the rendered docs' Vale errors

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a rendered project's `docs/` and `README.md` report zero Vale errors, so PR B can add a CI gate that asserts zero without a baseline file.

**Architecture:** Two authored `.jinja` docs files carry 20 Vale errors between them. Every fix is a prose edit in the template source. No code, no generator, no CI change — those are PR B onwards. The design spec written during brainstorming rides along in this PR rather than getting its own.

**Tech Stack:** Markdown + Jinja2 template sources; `vale` 3.14.2; `copier` for rendering.

**Spec:** `docs/superpowers/specs/2026-07-27-config-surface-1b-restructured-design.md` (PR A in §3).

## Global Constraints

- **Fixes must reach existing downstreams.** `.vale.ini` and `.vale/styles/config/vocabularies/Base/accept.txt` are both in `copier.yml`'s `_skip_if_exists`, so a term added to either reaches **new renders only**. Every spelling error in this plan is therefore fixed by **rewording the prose**, never by adding a vocabulary term.
- **Replacement wording must itself be Vale-clean.** Measured against the live binary: `For example,` and `For instance,` both trip `ai-tells.FormalTransitions`; `such as` is clean. Never replace `e.g.` with "for example".
- **`ai-tells.EmDashUsage` flags an em dash at any spacing, and an en dash too.** `A—B` unspaced is an error.
- **Marker tokens are load-bearing.** `DOMAIN-AUTHZ-SCOPES-START`, `DOMAIN-AUTHZ-SCOPES-END`, `DOMAIN-AUTHZ-EXTRA-START`, `DOMAIN-AUTHZ-EXTRA-END` must survive verbatim. Only the human-readable text *after* a marker token may change.
- **The exit criterion is `vale` reporting zero, not "the 20 listed errors are fixed".** Vale's reported set shifts as edits land: only 6 of the file's 11 spaced em dashes are currently reported, for reasons not derivable from `.vale.ini`. Fix the whole class, then re-run until zero.
- **`.vscode/` is untracked on this branch** (its ignore rule is PR G). Move it aside before any render, or `copier` mints a temp commit per render and `_commit` differs between two otherwise identical renders.
- Verification renders use `--vcs-ref=HEAD`, so **commit before rendering**.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `docs/guides/{% if enable_authorization %}authorization.md{% endif %}.jinja` | the authorization guide; 19 errors | Modify |
| `docs/guides/config-migration.md.jinja` | the config migration guide; 1 error | Modify |
| `docs/superpowers/specs/2026-07-27-config-surface-1b-restructured-design.md` | design spec | Already committed as `f4b5552`; rides along |

The authorization guide's filename contains a Jinja conditional, so it renders only when `enable_authorization` is true. Quote the path in every shell command.

---

## Task 0: File the issue and prepare the branch

**Files:** none (git + GitHub only)

- [ ] **Step 1: Confirm the issue text with the human before filing**

Filing is outward-facing. Show this draft and wait for approval:

> **Title:** `docs/guides/authorization.md` fails Vale with 19 errors in every authz-enabled downstream
>
> **Body:**
> `docs/guides/authorization.md` renders with 19 Vale errors, and `docs/guides/config-migration.md` with 1. Both files are template-owned prose that ships to downstream projects.
>
> Every downstream rendered with `enable_authorization: true` runs Vale over `docs/` in `ci.yml` with `MinAlertLevel = error` and `fail_on_error: true`, so those projects have a red `vale` job today.
>
> Errors span 7 rules: `Google.EmDash` (6), `ai-tells.EmDashUsage` (4), `Vale.Spelling` (3), `Google.Latin` (3), `write-good.ThereIs` (1), `Google.OptionalPlurals` (1), `ai-tells.EmphaticCopula` (1), plus `ai-tells.OverusedVocabulary` (1) in the migration guide.
>
> Fixes must be prose rewordings. `.vale.ini` and the Vocab accept list are both `_skip_if_exists`, so adding an accepted term would reach new renders only and leave existing downstreams red.
>
> **Verification:** render the template and run `vale --glob='!docs/{superpowers,design,decisions}/**' docs README.md`; it must report 0 errors.

- [ ] **Step 2: File it**

```bash
gh issue create --repo pvliesdonk/fastmcp-server-template \
  --title "docs/guides/authorization.md fails Vale with 19 errors in every authz-enabled downstream" \
  --body-file /tmp/pr-a-issue.md
```

Write the approved body to `/tmp/pr-a-issue.md` first. Append the agent-attribution signature line required by the operator's global instructions.

- [ ] **Step 3: Rename the branch so it reflects the PR**

```bash
git branch -m docs/config-surface-1b-redesign fix/docs-vale-errors
git branch --show-current
```

Expected: `fix/docs-vale-errors`

---

## Task 1: Clear the authorization guide

**Files:**
- Modify: `docs/guides/{% if enable_authorization %}authorization.md{% endif %}.jinja`

**Interfaces:**
- Consumes: nothing.
- Produces: nothing. Prose only.

- [ ] **Step 1: Confirm the starting state**

```bash
SP=/tmp/pr-a && rm -rf $SP && mv .vscode /tmp/vscode-parked 2>/dev/null
uv run --no-project --with copier copier copy --trust --defaults --vcs-ref=HEAD \
  --data-file tests/fixtures/smoke-answers.yml . $SP 2>&1 | tail -1
mv /tmp/vscode-parked .vscode 2>/dev/null
cd $SP && vale sync >/dev/null 2>&1
vale docs/guides/authorization.md 2>&1 | tail -2
```

Expected: `✖ 19 errors, 0 warnings and 0 suggestions in 1 file.`

- [ ] **Step 2: Sweep every spaced em dash in prose**

Ten replacements. Line 53 is inside a ```toml fence — Vale skips code blocks, so **leave line 53 alone**.

| Line | Replace | With |
|---|---|---|
| 3 | `**authorization** — gating individual tools,` | `**authorization**, gating individual tools,` |
| 9 | `There are two ways to decide which scopes a caller holds — pick the one` | `Two mechanisms decide which scopes a caller holds. Pick the one` |
| 35 | `granted exactly the values in their claim — there is nothing else to` | `granted exactly the values in their claim, and there is nothing else to` |
| 59 | ``- **`*` is the only special scope** — it grants every required scope.`` | ``- **`*` is the only special scope.** It grants every required scope.`` |
| 67 | `Subjects come from the authentication layer — see the` | `Subjects come from the authentication layer. See the` |
| 71 | ``(`{{ env_prefix }}_BEARER_TOKENS_FILE`) — keep the two consistent. In`` | ``(`{{ env_prefix }}_BEARER_TOKENS_FILE`). Keep the two consistent. In`` |
| 95 | `<!-- DOMAIN-AUTHZ-SCOPES-START — list THIS server's gated tools; kept across copier update -->` | `<!-- DOMAIN-AUTHZ-SCOPES-START: list THIS server's gated tools; kept across copier update -->` |
| 106 | `- [Authentication guide](authentication.md) — how callers obtain the` | `- [Authentication guide](authentication.md): how callers obtain the` |

Line 9's replacement also clears the `write-good.ThereIs` error at 9:1.

Lines 28-31 are one sentence with a pair of em dashes. Replace the whole block:

```markdown
Authorization reads OIDC **claims**, meaning what the identity provider
asserts about the *user* (their groups/roles), not the OAuth scopes the
client negotiated. Set `{{ env_prefix }}_AUTHZ_CLAIM` to the claim that
carries the user's group/role list.
```

- [ ] **Step 3: Fix the Latin abbreviations**

`such as`, never "for example" — the latter trips `ai-tells.FormalTransitions`.

Line 19:

```markdown
  to that claim's name, such as `groups`.
```

Lines 61-63, replace the whole bullet:

```markdown
- **Scope vocabulary is yours.** Per-project or per-folder gating is
  encoded into the scope string itself, such as `read:project-foo` or
  `write:vault/personal`.
```

- [ ] **Step 4: Fix the spelling, plurals, and emphasis errors**

`uncomment`, `IdP's` and `overridable` are all absent from the Vocab list, and adding them would not reach existing downstreams. Reword instead.

Lines 21-24, replace the whole paragraph. This clears `Google.OptionalPlurals` (21), `Vale.Spelling` on "uncomment" (22), the em dash (23), and `Google.Latin` (24) together:

```markdown
To turn either on: set the relevant `{{ env_prefix }}_*` variables
and enable the matching block in `src/{{ python_module }}/server.py`,
which ships commented out (plus the config field it reads in
`config.py`). Both may run together, such as an OIDC deployment that
keeps a bearer break-glass account.
```

Line 33:

```markdown
**No mapping is needed when the names already match.** If your identity provider's
```

Lines 73-74:

```markdown
`"bearer-anon"`, which you can change with
`{{ env_prefix }}_BEARER_DEFAULT_SUBJECT`).
```

Line 82, which clears both `ai-tells.EmphaticCopula` and its trailing em dash:

```markdown
  running half-configured. A scope-*name* typo is not structural:
```

- [ ] **Step 5: Verify the marker tokens survived**

```bash
grep -c "DOMAIN-AUTHZ-SCOPES-START\|DOMAIN-AUTHZ-SCOPES-END\|DOMAIN-AUTHZ-EXTRA-START\|DOMAIN-AUTHZ-EXTRA-END" \
  'docs/guides/{% if enable_authorization %}authorization.md{% endif %}.jinja'
```

Expected: `4`

- [ ] **Step 6: Re-render and re-run Vale until it reports zero**

```bash
git add -A && git commit -q -m "wip" && mv .vscode /tmp/vscode-parked 2>/dev/null
rm -rf /tmp/pr-a && uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/pr-a 2>&1 | tail -1
mv /tmp/vscode-parked .vscode 2>/dev/null
cd /tmp/pr-a && vale docs/guides/authorization.md 2>&1 | tail -2
```

Expected: `0 errors`. If any error remains, fix it and repeat this step — the reported set shifts as edits land.

- [ ] **Step 7: Squash the wip commit and commit properly**

```bash
git reset --soft HEAD~1
git add 'docs/guides/{% if enable_authorization %}authorization.md{% endif %}.jinja'
git commit -m "$(cat <<'EOF'
fix(docs): clear the authorization guide's Vale errors

The guide rendered with 19 Vale errors, and every downstream created with
enable_authorization: true runs Vale over docs/ at MinAlertLevel = error
with fail_on_error: true. Those projects have a red vale job today.

Every fix is a reword rather than a new accepted term. The Vocab list and
.vale.ini are both _skip_if_exists, so a term added to either would reach
new renders only and leave the affected projects red.

The em-dash sweep covers all ten prose occurrences, not the six Vale
currently reports; the reported subset shifts as edits land, and the one
inside the TOML fence is left alone because Vale skips code blocks.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01As25PstUQeTR47J5SP5g7P
EOF
)"
```

---

## Task 2: Clear the migration guide

**Files:**
- Modify: `docs/guides/config-migration.md.jinja:77`

**Interfaces:**
- Consumes: nothing.
- Produces: nothing. Prose only.

- [ ] **Step 1: Confirm the error**

```bash
cd /tmp/pr-a && vale docs/guides/config-migration.md 2>&1 | tail -2
```

Expected: `1 error`, `ai-tells.OverusedVocabulary` on `genuinely` at 77:58.

- [ ] **Step 2: Reword line 77**

Current:

```markdown
`config-presentation.domain.yml` only for a var the scan genuinely cannot
```

Replace with:

```markdown
`config-presentation.domain.yml` only for a var the scan cannot
```

The adverb carries no meaning the sentence needs; deleting it is the whole fix.

- [ ] **Step 3: Re-render and verify the full CI scope reports zero**

This is the gate PR B will automate, run by hand here.

```bash
git add -A && git commit -q -m "wip" && mv .vscode /tmp/vscode-parked 2>/dev/null
rm -rf /tmp/pr-a && uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml . /tmp/pr-a 2>&1 | tail -1
mv /tmp/vscode-parked .vscode 2>/dev/null
cd /tmp/pr-a && vale sync >/dev/null 2>&1
vale --glob='!docs/{superpowers,design,decisions}/**' docs README.md 2>&1 | tail -2
```

Expected: `✖ 0 errors, 0 warnings and 0 suggestions in 13 files.`

- [ ] **Step 4: Verify the gate-off render is clean too**

`authorization.md` does not exist when `enable_authorization` is false, but the migration guide does. `template-ci` renders both variants.

```bash
mv .vscode /tmp/vscode-parked 2>/dev/null
rm -rf /tmp/pr-a-off && uv run --no-project --with copier copier copy --trust --defaults \
  --vcs-ref=HEAD --data-file tests/fixtures/smoke-answers.yml \
  --data enable_authorization=false . /tmp/pr-a-off 2>&1 | tail -1
mv /tmp/vscode-parked .vscode 2>/dev/null
cd /tmp/pr-a-off && vale sync >/dev/null 2>&1
vale --glob='!docs/{superpowers,design,decisions}/**' docs README.md 2>&1 | tail -2
```

Expected: `0 errors`.

- [ ] **Step 5: Squash and commit**

```bash
git reset --soft HEAD~1
git add docs/guides/config-migration.md.jinja
git commit -m "$(cat <<'EOF'
fix(docs): drop an overused adverb from the migration guide

ai-tells.OverusedVocabulary flags "genuinely", and the adverb carries no
meaning the sentence needs. With this the whole rendered docs set reports
zero Vale errors, which is what lets the next PR gate on zero without a
baseline file.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01As25PstUQeTR47J5SP5g7P
EOF
)"
```

---

## Task 3: Confirm the render is otherwise unaffected

**Files:** none (verification only)

Prose edits should not change anything structural. This task proves it.

- [ ] **Step 1: Render twice and diff**

```bash
mv .vscode /tmp/vscode-parked 2>/dev/null
rm -rf /tmp/pr-a-1 /tmp/pr-a-2
for d in /tmp/pr-a-1 /tmp/pr-a-2; do
  uv run --no-project --with copier copier copy --trust --defaults --vcs-ref=HEAD \
    --data-file tests/fixtures/smoke-answers.yml . $d 2>&1 | tail -1
done
mv /tmp/vscode-parked .vscode 2>/dev/null
diff -r /tmp/pr-a-1 /tmp/pr-a-2 && echo "RENDERS IDENTICAL"
```

Expected: `RENDERS IDENTICAL`. If `_commit` differs, `.vscode/` was not parked.

- [ ] **Step 2: Check render hygiene on both variants**

```bash
python3 scripts/check_render_hygiene.py /tmp/pr-a-1 /tmp/pr-a-off
```

Expected: `render hygiene OK` for both.

- [ ] **Step 3: Confirm the docs site still builds**

An edit that breaks a heading anchor breaks `mkdocs --strict`. Line 82's change removes bold from `**not**` and line 59's moves a bold span; neither is a heading, but prove it.

```bash
cd /tmp/pr-a-1 && uv sync --all-extras --all-groups -q 2>&1 | tail -1
uv run mkdocs build --strict 2>&1 | tail -2
```

Expected: `Documentation built in …` with no warnings.

- [ ] **Step 4: Confirm only the two intended files changed**

```bash
git diff --name-only 352c0c9..HEAD
```

Expected exactly three paths — the two guides plus the design spec from `f4b5552`:

```
docs/guides/config-migration.md.jinja
docs/guides/{% if enable_authorization %}authorization.md{% endif %}.jinja
docs/superpowers/specs/2026-07-27-config-surface-1b-restructured-design.md
```

---

## Wrap-up

- [ ] **Run the pre-push review** over `origin/main..HEAD` before opening the PR, per the operator's global instructions.
- [ ] **Open the PR** with `Closes #<issue from Task 0>` in the **commit message**, not only the body — GitHub acts on the squashed commit message, and a stale `Closes` line in Stage 1a's squash auto-closed three issues that still had work outstanding.
- [ ] **Do not merge and do not release.** Both are human-only.
- [ ] Note in the PR body that the design spec rides along, and link it.

## What this PR deliberately does not do

- No CI change. Gating on zero is PR B, together with the missing `check_anchor` for the fifth detach-scrub rule.
- No generator, no `config-presentation.yml`, no markers. Those are PRs D-F.
- No new accepted Vale terms, for the propagation reason in Global Constraints.
- `docs/guides/authorization.md`'s prose is corrected, not restructured. Content changes belong to the PR that owns that content.
