# Triaged fixes → template v1.1.10 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship four independent template fixes as four PRs against
`main`, then release them as patch version **v1.1.10**.

**Architecture:** Each PR is a standalone branch cut from
`origin/main`. Tests are expressed as assertions in
`.github/workflows/template-ci.yml` (the template's own CI) — the
"failing test" step means adding the assertion, running the smoke
render locally (`copier copy` → `/tmp/smoke`), and watching the
assertion fail before the code change lands. After all four PRs are
merged to `main`, a single `template-release.yml` dispatch tags
`v1.1.10` and exercises the #38 fix end-to-end.

**Tech Stack:** Copier (Jinja2 templates), GitHub Actions, `jq`,
`grep`, Bash.

**Spec:**
`docs/superpowers/specs/2026-04-23-triaged-fixes-v1.1.10-design.md`

**Issues closed:** #31, #30, #37, #38.

---

## File Structure

Files touched across the plan:

| Path | PR | Action |
|---|---|---|
| `docs/deployment/docker.md` → `…docker.md.jinja` | PR 1 | rename + substitute |
| `docs/deployment/oidc.md` → `…oidc.md.jinja` | PR 1 | rename + substitute |
| `docs/guides/authentication.md` → `…authentication.md.jinja` | PR 1 | rename + substitute |
| `.github/workflows/template-ci.yml` | PRs 1, 2, 4 | add `grep` assertions |
| `Dockerfile.jinja` | PR 2 | add 2 sentinel pairs |
| `CLAUDE.md.jinja` | PR 3 | append section |
| `.github/workflows/release.yml.jinja` | PR 4 | replace jq block |

The three docs files (PR 1) are owned by the copier template; copier's
`_skip_if_exists` entries in `copier.yml` use **rendered** paths
(`docs/deployment/docker.md`, etc.) and do NOT need to change when the
source files gain a `.jinja` suffix.

---

## Phase 0 — Prep

### Task 0.1: Fetch latest `main`

- [ ] **Step 1: Update local main**

```bash
git fetch origin --tags --prune
git switch main
git pull --ff-only origin main
git log --oneline -3
```

Expected: top commit is `chore(release): v1.1.9` or newer.

---

## Phase 1 — PR 1: #31 render shared docs with consumer env_prefix

Branch: `fix/shared-docs-env-prefix`.

### Task 1.1: Create branch and the failing CI assertion

**Files:**
- Modify: `.github/workflows/template-ci.yml` (append a new step after
  the existing CLAUDE.md sentinel check, around line 80).

- [ ] **Step 1: Create branch**

```bash
git switch -c fix/shared-docs-env-prefix origin/main
```

- [ ] **Step 2: Add the assertion step (the "failing test")**

Append this as a new step to the `smoke` job in
`.github/workflows/template-ci.yml`, immediately after the existing
`CLAUDE.md sentinel structure` step:

```yaml
      - name: shared docs render with consumer env_prefix
        working-directory: /tmp/smoke
        run: |
          # Smoke answers set env_prefix=SMOKE_MCP — rendered docs
          # should name some consumer-prefixed env var, never the placeholder.
          # Positive probe runs against all three files so a silent render
          # failure in any one file is caught.
          # Negative check uses a word-boundary regex so legitimate
          # rendered tokens like SMOKE_MCP_SERVER_NAME don't false-positive
          # as MCP_SERVER_ leaks (substring collision).
          for f in \
              docs/deployment/oidc.md \
              docs/deployment/docker.md \
              docs/guides/authentication.md; do
            grep -qE 'SMOKE_MCP_[A-Z][A-Z0-9_]*' "$f" \
              || { echo "::error::$f missing any SMOKE_MCP_ env var — substitution did not occur"; exit 1; }
          done
          ! grep -lE '(^|[^A-Z0-9_])MCP_SERVER_' \
              docs/deployment/docker.md \
              docs/deployment/oidc.md \
              docs/guides/authentication.md \
            || { echo "::error::MCP_SERVER_ placeholder literal leaked into shared docs"; exit 1; }
          ! grep -lF fastmcp-server-template \
              docs/deployment/docker.md \
              docs/deployment/oidc.md \
              docs/guides/authentication.md \
            || { echo "::error::fastmcp-server-template literal leaked into shared docs"; exit 1; }
```

- [ ] **Step 3: Run the smoke render locally and watch it fail**

```bash
rm -rf /tmp/smoke
uv run --no-project --with copier copier copy --trust --defaults --vcs-ref HEAD \
  --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
cd /tmp/smoke
grep -qE 'SMOKE_MCP_[A-Z][A-Z0-9_]*' docs/deployment/oidc.md && echo PASS-pos || echo FAIL-pos
if grep -lE '(^|[^A-Z0-9_])MCP_SERVER_' docs/deployment/docker.md docs/deployment/oidc.md docs/guides/authentication.md; then echo FAIL-leak; else echo PASS-no-leak; fi
```

Expected: `FAIL-pos` and `FAIL-leak`. That's your "red" — the
assertion is live and the current code does not satisfy it.

`--vcs-ref HEAD` is needed locally so copier renders from the
branch tip instead of the latest tag. CI does not need it because
`actions/checkout` produces a shallow clone with no tags visible.

- [ ] **Step 4: Commit the assertion**

```bash
cd /mnt/code/fastmcp-server-template
git add .github/workflows/template-ci.yml
git commit -m "test(ci): assert shared docs render with consumer env_prefix"
```

### Task 1.2: Rename the three docs to `.jinja`

**Files:**
- Rename: `docs/deployment/docker.md` → `docs/deployment/docker.md.jinja`
- Rename: `docs/deployment/oidc.md` → `docs/deployment/oidc.md.jinja`
- Rename: `docs/guides/authentication.md` → `docs/guides/authentication.md.jinja`

- [ ] **Step 1: Pre-rename jinja-token sweep**

```bash
grep -En '\{\{|\{%' \
  docs/deployment/docker.md \
  docs/deployment/oidc.md \
  docs/guides/authentication.md
```

Expected: empty output. If any line prints, wrap those literal blocks
in `{% raw %}{% endraw %}` inside the file before renaming, otherwise
Jinja2 will try to interpret them during `copier copy` and either
crash or silently change content.

- [ ] **Step 2: Rename via `git mv`**

```bash
git mv docs/deployment/docker.md docs/deployment/docker.md.jinja
git mv docs/deployment/oidc.md docs/deployment/oidc.md.jinja
git mv docs/guides/authentication.md docs/guides/authentication.md.jinja
```

- [ ] **Step 3: Commit the rename (no content change yet)**

```bash
git commit -m "refactor(docs): rename shared docs to .jinja for env_prefix substitution"
```

### Task 1.3: Substitute env_prefix and docker registry in the renamed files

**Files:**
- Modify: `docs/deployment/docker.md.jinja`
- Modify: `docs/deployment/oidc.md.jinja`
- Modify: `docs/guides/authentication.md.jinja`

- [ ] **Step 1: Replace `MCP_SERVER_` → `{{ env_prefix }}_`**

```bash
sed -i 's/MCP_SERVER_/{{ env_prefix }}_/g' \
  docs/deployment/docker.md.jinja \
  docs/deployment/oidc.md.jinja \
  docs/guides/authentication.md.jinja
```

- [ ] **Step 2: Replace the hardcoded ghcr path**

```bash
sed -i 's#ghcr\.io/pvliesdonk/fastmcp-server-template:latest#{{ docker_registry }}/{{ project_name }}:latest#g' \
  docs/deployment/docker.md.jinja \
  docs/deployment/oidc.md.jinja \
  docs/guides/authentication.md.jinja
```

- [ ] **Step 3: Audit for residual literals**

```bash
grep -En 'MCP_SERVER_|fastmcp-server-template|smoke-mcp|Smoke MCP|smoke_mcp' \
  docs/deployment/docker.md.jinja \
  docs/deployment/oidc.md.jinja \
  docs/guides/authentication.md.jinja
```

Expected: empty output. If anything prints, replace with the
appropriate `{{ env_prefix }}_`, `{{ project_name }}`,
`{{ human_name }}`, or `{{ python_module }}` by hand, then re-run.

- [ ] **Step 4: Re-run the smoke render and verify green**

```bash
rm -rf /tmp/smoke
uv run --no-project --with copier copier copy --trust --defaults --vcs-ref HEAD \
  --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
cd /tmp/smoke
for f in docs/deployment/oidc.md docs/deployment/docker.md docs/guides/authentication.md; do
  grep -qE 'SMOKE_MCP_[A-Z][A-Z0-9_]*' "$f" && echo "OK-pos $f"
done
if grep -lE '(^|[^A-Z0-9_])MCP_SERVER_' docs/deployment/docker.md docs/deployment/oidc.md docs/guides/authentication.md; then echo FAIL; else echo OK-no-leak; fi
if grep -lF fastmcp-server-template docs/deployment/docker.md docs/deployment/oidc.md docs/guides/authentication.md; then echo FAIL; else echo OK-no-fst; fi
cd /mnt/code/fastmcp-server-template
```

Expected: three `OK-pos ...` prints (one per file), `OK-no-leak`, `OK-no-fst`.

- [ ] **Step 5: Commit**

```bash
git add docs/deployment/docker.md.jinja \
        docs/deployment/oidc.md.jinja \
        docs/guides/authentication.md.jinja
git commit -m "fix(docs): render shared deployment/auth docs with {{ env_prefix }} and {{ docker_registry }}/{{ project_name }} (#31)"
```

### Task 1.4: Push and open PR 1

- [ ] **Step 1: Push**

```bash
git push -u origin fix/shared-docs-env-prefix
```

- [ ] **Step 2: Open PR**

```bash
gh pr create --repo pvliesdonk/fastmcp-server-template \
  --base main --head fix/shared-docs-env-prefix \
  --title "fix(docs): render shared docs with consumer env_prefix (#31)" \
  --body "$(cat <<'EOF'
## Summary
- Rename the three shared deployment/auth docs to `.jinja` so copier
  substitutes `{{ env_prefix }}_` and `{{ docker_registry }}/{{ project_name }}`
- Add template-ci assertions that fail if the placeholder prefix or
  the hardcoded ghcr path ever leaks back in

## Test plan
- [x] template-ci smoke render produces `SMOKE_MCP_OIDC_ISSUER` in rendered `docs/deployment/oidc.md`
- [x] rendered shared docs contain no `MCP_SERVER_` or `fastmcp-server-template` literals
- [x] `_skip_if_exists` rendered-path semantics unchanged — existing consumer files still preserved on update

Closes #31. Spec:
`docs/superpowers/specs/2026-04-23-triaged-fixes-v1.1.10-design.md`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Wait for `template-ci` to go green, request review, merge**

Wait for CI on the PR. Expected: green on all Python 3.11–3.14 matrix
rows. Merge via squash (the repo default). Delete remote branch after
merge.

- [ ] **Step 4: Update local `main`**

```bash
git switch main
git pull --ff-only origin main
```

---

## Phase 2 — PR 2: #30 Dockerfile state-dir + VOLUME sentinels

Branch: `feat/dockerfile-state-volume-sentinels`.

### Task 2.1: Branch and add failing sentinel-count assertion

**Files:**
- Modify: `.github/workflows/template-ci.yml`

- [ ] **Step 1: Create branch**

```bash
git switch -c feat/dockerfile-state-volume-sentinels origin/main
```

- [ ] **Step 2: Add assertion step**

Append this as a new step to the `smoke` job in
`.github/workflows/template-ci.yml`, immediately after the
`shared docs render with consumer env_prefix` step added in PR 1:

```yaml
      - name: Dockerfile sentinel structure
        working-directory: /tmp/smoke
        run: |
          for marker in \
            "# DOCKERFILE-STATE-DIRS-START" \
            "# DOCKERFILE-STATE-DIRS-END" \
            "# DOCKERFILE-VOLUMES-START" \
            "# DOCKERFILE-VOLUMES-END"; do
            count=$(grep -cF "$marker" Dockerfile)
            [ "$count" = "1" ] || { echo "::error::expected 1 '$marker' sentinel, found $count"; exit 1; }
          done
```

- [ ] **Step 3: Run the smoke render and verify the step fails**

```bash
rm -rf /tmp/smoke
uv run --no-project --with copier copier copy --trust --defaults \
  --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
cd /tmp/smoke
grep -cF '# DOCKERFILE-STATE-DIRS-START' Dockerfile
cd /mnt/code/fastmcp-server-template
```

Expected: prints `0`. The assertion is live, current code does not
satisfy it.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/template-ci.yml
git commit -m "test(ci): assert Dockerfile STATE-DIRS and VOLUMES sentinels present"
```

### Task 2.2: Add sentinels to `Dockerfile.jinja`

**Files:**
- Modify: `Dockerfile.jinja` (lines 38 and 47).

- [ ] **Step 1: Wrap the `mkdir -p /data/...` fragment**

Change `Dockerfile.jinja` lines 37–38 from:

```dockerfile
    && useradd -r ... \
    && mkdir -p /data/service /data/state/fastmcp \
    && chown -R appuser:appuser /app /data
```

to:

```dockerfile
    && useradd -r ... \
    # DOCKERFILE-STATE-DIRS-START — domain state subdirs; kept across copier update
    && mkdir -p /data/service /data/state/fastmcp \
    # DOCKERFILE-STATE-DIRS-END
    && chown -R appuser:appuser /app /data
```

(The exact text of the `useradd` line is whatever is in
`Dockerfile.jinja` today — do not rewrite it. Only insert the two
comment lines and leave the `&& mkdir ...` line between them.)

- [ ] **Step 2: Wrap the `VOLUME` line**

Change `Dockerfile.jinja` line 47 from:

```dockerfile
VOLUME ["/data/service", "/data/state"]
```

to:

```dockerfile
# DOCKERFILE-VOLUMES-START — mounted volume list; kept across copier update
VOLUME ["/data/service", "/data/state"]
# DOCKERFILE-VOLUMES-END
```

- [ ] **Step 3: Re-render and verify green**

```bash
rm -rf /tmp/smoke
uv run --no-project --with copier copier copy --trust --defaults \
  --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
cd /tmp/smoke
for marker in \
  "# DOCKERFILE-STATE-DIRS-START" \
  "# DOCKERFILE-STATE-DIRS-END" \
  "# DOCKERFILE-VOLUMES-START" \
  "# DOCKERFILE-VOLUMES-END"; do
  c=$(grep -cF "$marker" Dockerfile)
  echo "$marker: $c"
done
cd /mnt/code/fastmcp-server-template
```

Expected: each marker prints count `1`.

- [ ] **Step 4: Commit**

```bash
git add Dockerfile.jinja
git commit -m "feat(dockerfile): sentinel-protect state-dir mkdir and VOLUME (#30)"
```

### Task 2.3: Push and open PR 2

- [ ] **Step 1: Push**

```bash
git push -u origin feat/dockerfile-state-volume-sentinels
```

- [ ] **Step 2: Open PR**

```bash
gh pr create --repo pvliesdonk/fastmcp-server-template \
  --base main --head feat/dockerfile-state-volume-sentinels \
  --title "feat(dockerfile): sentinel-protect state-dir mkdir + VOLUME (#30)" \
  --body "$(cat <<'EOF'
## Summary
- Add `DOCKERFILE-STATE-DIRS-START/END` around the `mkdir -p /data/...` line
- Add `DOCKERFILE-VOLUMES-START/END` around the `VOLUME [...]` line
- Extend template-ci to assert exactly one of each marker in the rendered Dockerfile

## Test plan
- [x] template-ci passes
- [x] rendered Dockerfile still builds (default `docker build .` unchanged in shape)

Closes #30. Spec:
`docs/superpowers/specs/2026-04-23-triaged-fixes-v1.1.10-design.md`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Wait for CI, request review, merge, update local main**

```bash
# after merge
git switch main
git pull --ff-only origin main
```

---

## Phase 3 — PR 3: #37 CLAUDE.md upstream contribution guidance

Branch: `docs/claude-md-contributing-upstream`.

### Task 3.1: Branch

- [ ] **Step 1: Create branch**

```bash
git switch -c docs/claude-md-contributing-upstream origin/main
```

### Task 3.2: Append the section to `CLAUDE.md.jinja`

**Files:**
- Modify: `CLAUDE.md.jinja`

- [ ] **Step 1: Locate the existing Shared Infrastructure section**

```bash
grep -n 'Shared Infrastructure\|Shared infrastructure' CLAUDE.md.jinja
```

Note the line number of the end of the existing section (the
paragraph ending with "… propagate here via copier update ...").

- [ ] **Step 2: Append the new section after it**

Insert the following block immediately after the last line of the
existing Shared Infrastructure paragraph (before the next `##` or
sentinel):

```markdown
## Contributing fixes upstream

- **Library-level fix** (anything you'd change in `fastmcp_pvl_core`):
  open a PR on `pvliesdonk/fastmcp-pvl-core`. After merge + release,
  bump `fastmcp-pvl-core` in this project's `pyproject.toml` (or wait
  for copier update).
- **Template-level fix** (anything template-owned in this file —
  `Dockerfile`, workflows, `server.py` skeleton, `CLAUDE.md` sections):
  open a PR on `pvliesdonk/fastmcp-server-template`. After merge +
  release, this project gets the fix on the next weekly `copier update`
  cron (or dispatch the workflow manually).
- **Domain-only fix** (anything inside `DOMAIN-START`/`DOMAIN-END`
  sentinels, `tools.py`, `resources.py`, `prompts.py`, `domain.py`,
  `tests/`): PR on this repo directly.

If a conflict marker appears in a copier-update bot PR, the conflict
itself often signals a template bug — investigate whether the template's
version needs fixing before resolving locally.
```

- [ ] **Step 3: Re-render and verify sentinel structure intact**

```bash
rm -rf /tmp/smoke
uv run --no-project --with copier copier copy --trust --defaults \
  --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
cd /tmp/smoke
start=$(grep -cE '^<!-- DOMAIN-START -->$' CLAUDE.md)
end=$(grep -cE '^<!-- DOMAIN-END -->$' CLAUDE.md)
echo "DOMAIN-START=$start DOMAIN-END=$end"
grep -q "## Contributing fixes upstream" CLAUDE.md && echo "section present"
cd /mnt/code/fastmcp-server-template
```

Expected: `DOMAIN-START=3 DOMAIN-END=3 section present`.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md.jinja
git commit -m "docs(claude-md): add 'Contributing fixes upstream' section (#37)"
```

### Task 3.3: Push and open PR 3

- [ ] **Step 1: Push**

```bash
git push -u origin docs/claude-md-contributing-upstream
```

- [ ] **Step 2: Open PR**

```bash
gh pr create --repo pvliesdonk/fastmcp-server-template \
  --base main --head docs/claude-md-contributing-upstream \
  --title "docs(claude-md): add 'Contributing fixes upstream' section (#37)" \
  --body "$(cat <<'EOF'
## Summary
- Append a new section to CLAUDE.md.jinja that tells agents where to open PRs
  for library-level, template-level, and domain-only fixes
- Existing sentinel assertion (3 DOMAIN-START, 3 DOMAIN-END) still passes

## Test plan
- [x] Rendered CLAUDE.md contains the new section
- [x] DOMAIN sentinel count unchanged

Closes #37. Spec:
`docs/superpowers/specs/2026-04-23-triaged-fixes-v1.1.10-design.md`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Wait for CI, review, merge, update local main**

```bash
git switch main
git pull --ff-only origin main
```

---

## Phase 4 — PR 4: #38 upsert marketplace.json in publish-claude-plugin-pr

Branch: `fix/release-marketplace-upsert`.

### Task 4.1: Branch and add failing CI assertion

**Files:**
- Modify: `.github/workflows/template-ci.yml`

- [ ] **Step 1: Create branch**

```bash
git switch -c fix/release-marketplace-upsert origin/main
```

- [ ] **Step 2: Add assertion step**

Append this as a new step to the `smoke` job in
`.github/workflows/template-ci.yml`, immediately after the
`Dockerfile sentinel structure` step added in PR 2:

```yaml
      - name: release.yml marketplace upsert
        working-directory: /tmp/smoke
        run: |
          # PR 4 of v1.1.10 replaces the jq map-only update with an
          # upsert that appends a new git-subdir entry when the plugin
          # is absent. The rendered workflow must carry both markers.
          grep -qF '"git-subdir"' .github/workflows/release.yml \
            || { echo "::error::release.yml missing git-subdir marker — upsert regressed"; exit 1; }
          grep -qF '".claude-plugin/plugin"' .github/workflows/release.yml \
            || { echo "::error::release.yml missing .claude-plugin/plugin path — upsert regressed"; exit 1; }
          grep -qF 'any(.[]; .name == $name)' .github/workflows/release.yml \
            || { echo "::error::release.yml missing upsert branch — still silently no-ops on missing entry"; exit 1; }
```

- [ ] **Step 3: Run smoke render and watch it fail**

```bash
rm -rf /tmp/smoke
uv run --no-project --with copier copier copy --trust --defaults \
  --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
cd /tmp/smoke
grep -qF '"git-subdir"' .github/workflows/release.yml && echo PASS || echo FAIL
cd /mnt/code/fastmcp-server-template
```

Expected: `FAIL`.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/template-ci.yml
git commit -m "test(ci): assert release.yml carries marketplace upsert block"
```

### Task 4.2: Replace the jq block in `release.yml.jinja`

**Files:**
- Modify: `.github/workflows/release.yml.jinja` (lines 345–357).

- [ ] **Step 1: Replace the `Bump marketplace.json entry` step**

Find this block (around line 345):

```yaml
      - name: Bump marketplace.json entry
        env:
          VERSION: {% raw %}${{ needs.release.outputs.version }}{% endraw %}
        run: |
          cd catalog
          jq --arg v "$VERSION" --arg ref "v$VERSION" '
            .plugins |= map(
              if .name == "{{ project_name }}"
              then .version = $v | .source.ref = $ref
              else . end
            )
          ' marketplace.json > marketplace.json.tmp
          mv marketplace.json.tmp marketplace.json
```

Replace it with:

```yaml
      - name: Bump marketplace.json entry
        env:
          VERSION: {% raw %}${{ needs.release.outputs.version }}{% endraw %}
        run: |
          cd catalog
          NEW_ENTRY=$(jq -n \
            --arg name    "{{ project_name }}" \
            --arg url     "https://github.com/{{ github_org }}/{{ project_name }}.git" \
            --arg ref     "v$VERSION" \
            --arg version "$VERSION" \
            '{
              name: $name,
              source: {
                source: "git-subdir",
                url: $url,
                path: ".claude-plugin/plugin",
                ref: $ref
              },
              version: $version
            }')
          jq --arg name "{{ project_name }}" \
             --arg v    "$VERSION" \
             --arg ref  "v$VERSION" \
             --argjson new "$NEW_ENTRY" '
            .plugins |= (
              if any(.[]; .name == $name)
              then map(if .name == $name then .version = $v | .source.ref = $ref else . end)
              else . + [$new]
              end
            )
          ' marketplace.json > marketplace.json.tmp
          mv marketplace.json.tmp marketplace.json
```

- [ ] **Step 2: Sanity-check jq on a fixture**

Validate the jq expressions locally against a small fixture so a
syntax error is caught before CI:

```bash
# Append path (empty catalog)
echo '{"plugins":[]}' | jq \
  --arg name "smoke-mcp" --arg v "1.2.3" --arg ref "v1.2.3" \
  --argjson new '{"name":"smoke-mcp","source":{"source":"git-subdir","url":"https://github.com/x/y.git","path":".claude-plugin/plugin","ref":"v1.2.3"},"version":"1.2.3"}' '
  .plugins |= (
    if any(.[]; .name == $name)
    then map(if .name == $name then .version = $v | .source.ref = $ref else . end)
    else . + [$new]
    end
  )'

# Update path (catalog already has the entry)
echo '{"plugins":[{"name":"smoke-mcp","source":{"source":"git-subdir","url":"https://github.com/x/y.git","path":".claude-plugin/plugin","ref":"v1.0.0"},"version":"1.0.0"}]}' | jq \
  --arg name "smoke-mcp" --arg v "1.2.3" --arg ref "v1.2.3" \
  --argjson new '{}' '
  .plugins |= (
    if any(.[]; .name == $name)
    then map(if .name == $name then .version = $v | .source.ref = $ref else . end)
    else . + [$new]
    end
  )'
```

Expected:
- First command prints a catalog with one appended `smoke-mcp` entry
  at version `1.2.3`.
- Second command prints a catalog where the existing `smoke-mcp`
  entry's `version` is `1.2.3` and `source.ref` is `v1.2.3`. No
  second entry appended.

- [ ] **Step 3: Re-render and verify the CI assertion now passes**

```bash
rm -rf /tmp/smoke
uv run --no-project --with copier copier copy --trust --defaults \
  --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
cd /tmp/smoke
grep -qF '"git-subdir"' .github/workflows/release.yml && echo OK-gs
grep -qF '".claude-plugin/plugin"' .github/workflows/release.yml && echo OK-path
grep -qF 'any(.[]; .name == $name)' .github/workflows/release.yml && echo OK-upsert
cd /mnt/code/fastmcp-server-template
```

Expected: `OK-gs`, `OK-path`, `OK-upsert` all print.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/release.yml.jinja
git commit -m "fix(release): upsert marketplace.json when plugin is absent (#38)"
```

### Task 4.3: Push and open PR 4

- [ ] **Step 1: Push**

```bash
git push -u origin fix/release-marketplace-upsert
```

- [ ] **Step 2: Open PR**

```bash
gh pr create --repo pvliesdonk/fastmcp-server-template \
  --base main --head fix/release-marketplace-upsert \
  --title "fix(release): upsert marketplace.json when plugin is absent (#38)" \
  --body "$(cat <<'EOF'
## Summary
- Replace the map-only jq with an upsert in `publish-claude-plugin-pr`
- Prospective new entry shape matches the live `markdown-vault-mcp`
  entry (git-subdir, path=.claude-plugin/plugin, url=github https URL)
- Existing consumers with a catalog entry see identical update
  behaviour; first-time consumers now get a real append PR instead
  of a silent no-op
- Template-ci asserts both the `git-subdir` and `.claude-plugin/plugin`
  literals plus the upsert branch (`any(.[]; .name == $name)`) are
  present in the rendered workflow

## Test plan
- [x] Local jq fixture exercises both append and update paths
- [x] template-ci smoke render carries all three expected literals
- [ ] v1.1.10 release dispatch exercises the append path end-to-end
      against the real `pvliesdonk/claude-plugins` catalog

Closes #38. Spec:
`docs/superpowers/specs/2026-04-23-triaged-fixes-v1.1.10-design.md`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Wait for CI, review, merge, update local main**

```bash
git switch main
git pull --ff-only origin main
```

---

## Phase 5 — Release v1.1.10

### Task 5.1: Dispatch the release workflow

- [ ] **Step 1: Confirm `main` is at the expected tip**

```bash
git log --oneline -6 origin/main
```

Expected: the four merge commits for PRs 1–4 are visible above
`chore(release): v1.1.9`.

- [ ] **Step 2: Dispatch `template-release.yml`**

```bash
gh workflow run template-release.yml \
  --repo pvliesdonk/fastmcp-server-template \
  --ref main \
  -f bump=patch
```

- [ ] **Step 3: Watch the run**

```bash
gh run list --repo pvliesdonk/fastmcp-server-template \
  --workflow template-release.yml --limit 1
gh run watch --repo pvliesdonk/fastmcp-server-template <RUN_ID>
```

Expected: run completes green; new tag `v1.1.10` created; GitHub
release entry produced.

### Task 5.2: Verify the marketplace publication end-to-end

- [ ] **Step 1: Check the catalog PR**

```bash
gh pr list --repo pvliesdonk/claude-plugins --state open --limit 5 \
  --json number,title,author,createdAt
```

Expected: a PR titled
`chore: bump fastmcp-server-template to v1.1.10` opened by
`github-actions[bot]`, appending a brand-new catalog entry (the
append path is exercised because the template itself has never been
listed).

- [ ] **Step 2: Inspect the appended entry**

```bash
gh pr diff <PR_NUMBER> --repo pvliesdonk/claude-plugins
```

Expected: the diff adds a JSON object with
`name: fastmcp-server-template`, `version: 1.1.10`, and a
`source.git-subdir` block pointing at the v1.1.10 tag.

- [ ] **Step 3: If the append path fails, open an issue**

If `publish-claude-plugin-pr` goes red or opens no PR, open a new
`priority/high` issue with the run URL, the rendered workflow
snippet, and the `jq` stderr — then move the spec's risk note into
the issue body. Do not hand-patch the catalog.

### Task 5.3: Close issues and update tracking

- [ ] **Step 1: Close #31, #30, #37, #38 with release pointer**

```bash
for n in 31 30 37 38; do
  gh issue close "$n" --repo pvliesdonk/fastmcp-server-template \
    --reason completed \
    --comment "Fixed in v1.1.10 — released 2026-04-23."
done
```

- [ ] **Step 2: Commit a follow-up note to `docs/superpowers/plans/`**

If any deviation from the plan happened (surprising conflict,
renamed branch, extra PR), append a short "Execution notes" section
to this plan document on a follow-up commit with the specifics.
Skip if everything ran to spec.

---

## Non-goals (unchanged from spec)

- Issue **#29** (sentinel-protect shared docs pages) — deferred; no
  consumer has needed inline domain customization yet.
- Issue **#28** (PAT → GitHub App token) — separate workstream;
  requires creating the App outside this repo.
- Issue **#36** (Claude Code auto-analyze / auto-fix conflicts in
  `copier-update.yml`) — ambitious; needs its own design spec.
