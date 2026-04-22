# Copier sync + CLAUDE.md parity — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `copier update` work end-to-end across three MCP services (`markdown-vault-mcp`, `scholar-mcp`, `image-generation-mcp`) — producing either a human-reviewable bot PR or a green no-op run, never an unmergeable mess.

**Architecture:** Single source of truth is `fastmcp-server-template`. Release v1.1.5 bundles (a) CLAUDE.md Shared Infrastructure section, (b) `Dockerfile.jinja` sentinel markers for domain customization, (c) upstreamed `bump_manifests.py` hardening, (d) CI assertion for rendered CLAUDE.md shape. Consumers then get two PRs each: a CLAUDE.md sentinel migration + a convergence PR for drifted template-owned files. Final state: each consumer's `copier update` bot PR contains only the `_commit` bump, and the next Monday cron produces no PR.

**Tech Stack:** `copier` ≥9.0, `uv`, `ruff`, `mypy`, `pytest`, GitHub Actions, `gh` CLI, python-semantic-release.

**Repos touched:**
- Template: `/mnt/code/fastmcp-server-template` (branch `feat/shared-infra-claude-md`)
- `markdown-vault-mcp`: `/mnt/code/markdown-mcp` (has unmerged branch `refactor/claude-md-sentinels`)
- `scholar-mcp`: `/mnt/code/scholar-mcp`
- `image-generation-mcp`: `/mnt/code/image-gen-mcp`

**Spec:** `docs/superpowers/specs/2026-04-22-copier-sync-and-claude-md-parity-design.md` (same repo as this plan).

**Pre-flight assumptions (already true — verify if you hit surprises):**
- `RELEASE_TOKEN` PAT has `workflow` scope and is rotated in all four repos' Secrets.
- Template main is at `v1.1.4`. Each consumer's `.copier-answers.yml:_commit` is `v1.1.4`.
- `fastmcp-pvl-core` is stable at `v1.0.0-rc.1`; not touched by this plan.
- You are working on `feat/shared-infra-claude-md` in the template repo.

---

## File Structure

### Files created

- `fastmcp-server-template/docs/superpowers/plans/2026-04-22-copier-sync-and-claude-md-parity.md` — this plan (already created).

### Files modified

**Template repo (Phase 1):**
- `Dockerfile.jinja` — add `DOCKERFILE-APT-DEPS-*` and `DOCKERFILE-UV-EXTRAS-*` sentinel blocks.
- `scripts/bump_manifests.py.jinja` — incorporate defensive `isinstance()` hardening upstreamed from image-gen.
- `.github/workflows/template-ci.yml` — add a step asserting rendered CLAUDE.md contains both sentinel fences.
- (Already done on branch: `CLAUDE.md.jinja` Shared Infrastructure section; `docs/superpowers/specs/...` spec.)

**markdown-vault-mcp (Phase 2):**
- `CLAUDE.md` — sentinel-restructure (via existing `refactor/claude-md-sentinels` branch).
- `scripts/bump_manifests.py`, `.gitignore`, `docker-entrypoint.sh`, `Dockerfile`, `compose.yml`, `docs/deployment/docker.md`, `docs/deployment/oidc.md`, `docs/guides/authentication.md` — converge to template.

**scholar-mcp (Phase 2):**
- `CLAUDE.md` — sentinel-restructure.
- `.gitignore`, `docker-entrypoint.sh`, `Dockerfile`, `docs/deployment/docker.md`, `docs/deployment/oidc.md`, `docs/guides/authentication.md` — converge to template.

**image-generation-mcp (Phase 2):**
- `CLAUDE.md` — sentinel-restructure.
- `Dockerfile` — adopt sentinel shape with image-gen's customizations inside the new `DOCKERFILE-APT-DEPS-*` / `DOCKERFILE-UV-EXTRAS-*` blocks.
- `codecov.yml`, `.gitignore`, `docker-entrypoint.sh`, `docs/deployment/docker.md`, `docs/deployment/oidc.md`, `docs/guides/authentication.md` — converge to template.

### Files NOT touched (explicitly)

- `fastmcp-pvl-core/*` — drift in scope of this plan is not a core-lib issue.
- Any `src/{{python_module}}/*.py` in consumers — no code changes, only config and CLAUDE.md.
- `pyproject.toml` sentinels and `config.py` sentinels — already correct.

---

## Working order

The plan is 4 phases. **Each phase must complete before the next starts.** Within Phase 3, the three consumer tracks are independent and can be done in parallel by separate subagents if using `subagent-driven-development`.

**Note on phase ordering vs. the spec:** The spec (§3.3) lists Phase 1.5 (drift triage) → Phase 2 (CLAUDE.md migration) → Phase 3 (release v1.1.5) → Phase 4 (propagate). This plan reorders slightly: template changes + release happen before per-consumer work. Rationale:
- Consumers reference a fixed released tag (`v1.1.5`) rather than a moving `main` branch.
- `--vcs-ref v1.1.5` is meaningful only after the release is cut.
- The plan's Phase 1 still contains only template-side changes; consumer-side work (the spec's Phase 2 + Phase 1.5 consumer convergence) is bundled into Phase 3 of this plan.

If you need to match the spec literally, swap Phase 2 (release) with Phase 3 (consumer work) and substitute `--vcs-ref main` for `--vcs-ref v1.1.5` in the dry-render commands.

---

## Phase 0 — Prep (one task)

### Task 1: File follow-up issues in the template repo

**Files:** none (GitHub issue creation only)

- [ ] **Step 1: File the GitHub App token issue**

```bash
gh issue create --repo pvliesdonk/fastmcp-server-template \
  --title "Migrate copier-update.yml from PAT to GitHub App token" \
  --label "enhancement,ci" \
  --body "$(cat <<'EOF'
## Context

`.github/workflows/copier-update.yml` currently authenticates via `RELEASE_TOKEN` PAT (with `workflow` scope added 2026-04-22). This pattern has three drawbacks:

- PAT is tied to a single human account; blast radius on compromise = all repos the human owns.
- Rotation is manual.
- All bot commits show as the human's identity.

## Proposal

Migrate to a GitHub App installation token via [`actions/create-github-app-token`](https://github.com/actions/create-github-app-token).

- Create a "fastmcp-copier-update" GitHub App with `contents:write`, `pull-requests:write`, `workflows:write` scopes, installed only on the four repos in this fleet.
- Replace `token: \${{ secrets.RELEASE_TOKEN }}` in the workflow with a generated installation token.
- Replace `RELEASE_TOKEN` secret in consumer repos with `APP_ID` + `APP_PRIVATE_KEY` secrets.
- Commits appear as "fastmcp-copier-update[bot]".

## References

- Dependabot and Renovate both use this pattern.
- Spec: `docs/superpowers/specs/2026-04-22-copier-sync-and-claude-md-parity-design.md` §3.1.
EOF
)"
```

Expected: issue URL printed.

- [ ] **Step 2: File the shared-docs sentinel issue**

```bash
gh issue create --repo pvliesdonk/fastmcp-server-template \
  --title "Sentinel-protect shared docs/deployment/*.md + docs/guides/authentication.md" \
  --label "enhancement" \
  --body "$(cat <<'EOF'
## Context

The 2026-04-22 copier-sync plan converges these shared docs pages (keeps them fully template-owned). This is the right near-term answer — future `fastmcp-pvl-core` auth/OIDC/deployment changes can propagate across the fleet.

## Proposal

Introduce sentinel blocks analogous to `CONFIG-FIELDS-*` inside:
- `docs/deployment/docker.md.jinja`
- `docs/deployment/oidc.md.jinja`
- `docs/guides/authentication.md.jinja`

Proposed marker names: `DOCS-DEPLOYMENT-EXTRA-START` / `DOCS-DEPLOYMENT-EXTRA-END` and `DOCS-AUTH-EXTRA-START` / `DOCS-AUTH-EXTRA-END`. Each consumer can extend the template-owned content with domain-specific caveats without losing future template updates.

Defer until a consumer actually needs domain customization inside these pages; do not introduce sentinels pre-emptively.

## References

- Spec: `docs/superpowers/specs/2026-04-22-copier-sync-and-claude-md-parity-design.md` §3.1 (follow-ups).
EOF
)"
```

Expected: issue URL printed.

- [ ] **Step 3: Record issue URLs**

No commit — issue URLs are auto-filed in GitHub. Note the two URLs in session output for later reference.

---

## Phase 1 — Template v1.1.5 (all changes on `feat/shared-infra-claude-md`)

This phase produces one template release that bundles the spec, Dockerfile sentinels, bump_manifests hardening, and template-ci assertion. Do NOT release yet — that's Phase 3.

### Task 2: Add `DOCKERFILE-APT-DEPS` and `DOCKERFILE-UV-EXTRAS` sentinel blocks to `Dockerfile.jinja`

**Files:**
- Modify: `/mnt/code/fastmcp-server-template/Dockerfile.jinja`

**Purpose of the sentinels:**
- `DOCKERFILE-APT-DEPS-*` lets domains add APT packages to the base `apt-get install` line. Image-gen needs `git-lfs` there (already in template); a domain that needs e.g. `poppler-utils` for PDF work extends this block.
- `DOCKERFILE-UV-EXTRAS-*` lets domains pass additional `--extra <name>` flags to `uv sync`. Image-gen uses `--extra all` to pull in its provider SDK extras.

- [ ] **Step 1: Read current `Dockerfile.jinja` to confirm state**

```bash
cd /mnt/code/fastmcp-server-template
cat Dockerfile.jinja | head -30
```

Expected: file starts with `FROM python:3.12-slim`, has `RUN apt-get install ... git git-lfs gosu` and `uv sync --frozen --no-install-project --no-dev` lines.

- [ ] **Step 2: Apply the edit**

Replace the single `RUN apt-get install` block and both `uv sync` lines with sentinel-protected equivalents. Here is the exact new Dockerfile.jinja content (full file — copy verbatim):

```dockerfile
FROM python:3.12-slim

# DOCKERFILE-APT-DEPS-START — add domain apt packages below; kept across copier update
RUN apt-get update && apt-get install -y --no-install-recommends git git-lfs gosu \
    && rm -rf /var/lib/apt/lists/* \
    && git lfs install --system
# DOCKERFILE-APT-DEPS-END

COPY --from=ghcr.io/astral-sh/uv:0.6 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# DOCKERFILE-UV-EXTRAS-START — append `--extra <name>` flags below to pull domain-specific extras; kept across copier update
# Install dependencies first (cache layer).
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv sync --frozen --no-install-project --no-dev

# Copy source and install project.
COPY pyproject.toml README.md /app/
COPY src/ /app/src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev
# DOCKERFILE-UV-EXTRAS-END

# Create non-root user with configurable UID/GID for bind-mount compatibility.
ARG APP_UID=1000
ARG APP_GID=1000
RUN if [ "$APP_UID" -eq 0 ] || [ "$APP_GID" -eq 0 ]; then \
        echo "ERROR: APP_UID and APP_GID must be non-zero" >&2; exit 1; \
    fi \
    && groupadd -r --gid $APP_GID --non-unique appuser \
    && useradd -r --uid $APP_UID --gid $APP_GID --no-log-init -d /app appuser \
    && mkdir -p /data/service /data/state/fastmcp \
    && chown -R appuser:appuser /app /data

COPY --chmod=0755 docker-entrypoint.sh /usr/local/bin/
ENV PATH="/app/.venv/bin:$PATH" \
    FASTMCP_HOME=/data/state/fastmcp

EXPOSE 8000

VOLUME ["/data/service", "/data/state"]

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["{{ project_name }}", "serve", "--transport", "http", "--host", "0.0.0.0"]
```

Use the `Write` tool to write this to `Dockerfile.jinja`.

- [ ] **Step 3: Verify smoke render still works**

```bash
cd /mnt/code/fastmcp-server-template
rm -rf /tmp/smoke && uv run --no-project --with copier \
  copier copy --trust --defaults --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
grep -n "DOCKERFILE-APT-DEPS-START\|DOCKERFILE-UV-EXTRAS-START" /tmp/smoke/Dockerfile
```

Expected: grep shows both markers at the correct lines. `copier copy` exits 0.

- [ ] **Step 4: Commit**

```bash
cd /mnt/code/fastmcp-server-template
git add Dockerfile.jinja
git commit -m "$(cat <<'EOF'
feat(dockerfile): add APT-DEPS and UV-EXTRAS sentinel blocks

Lets domains extend the base apt install line and pass additional
--extra flags to uv sync without losing them on copier update.
Image-gen needs both (git-lfs already in template; provider SDKs
via --extra all).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 3: Upstream image-gen's defensive `isinstance()` checks to `scripts/bump_manifests.py.jinja`

**Files:**
- Modify: `/mnt/code/fastmcp-server-template/scripts/bump_manifests.py.jinja`

Image-gen has local hardening the template lacks. These checks are generic (top-level-dict validation, packages-list validation, pkg-dict validation, null-identifier handling). Upstream so all fleet members benefit.

- [ ] **Step 1: Apply the hardening**

Use `Edit` to replace the `server = _load(server_path); ... _dump(server_path, server)` block in `scripts/bump_manifests.py.jinja`:

OLD (exact match):
```python
    server = _load(server_path)
    server["version"] = version
    for pkg in server.get("packages", []):
        if pkg.get("registryType") == "pypi":
            pkg["version"] = version
        elif pkg.get("registryType") == "oci":
            identifier = pkg.get("identifier", "")
            new_id, n = re.subn(r":v[^:]+$", f":v{version}", identifier)
            if n == 0:
                print(
                    f"WARNING: OCI identifier {identifier!r} has no ':v<tag>' "
                    "suffix to bump — left unchanged",
                    file=sys.stderr,
                )
            pkg["identifier"] = new_id
    _dump(server_path, server)
```

NEW:
```python
    server = _load(server_path)
    if not isinstance(server, dict):
        print(
            f"{server_path} must contain a JSON object (top-level)",
            file=sys.stderr,
        )
        return 1
    server["version"] = version
    packages = server.get("packages", [])
    if not isinstance(packages, list):
        packages = []
    for pkg in packages:
        if not isinstance(pkg, dict):
            continue
        if pkg.get("registryType") == "pypi":
            pkg["version"] = version
        elif pkg.get("registryType") == "oci":
            # ``or ""`` covers both the absent-key and the JSON-null cases;
            # ``dict.get(key, default)`` only returns default when the key
            # is absent, not when the value is None.
            identifier = pkg.get("identifier") or ""
            new_id, n = re.subn(r":v[^:]+$", f":v{version}", identifier)
            if n == 0:
                print(
                    f"WARNING: OCI identifier {identifier!r} has no ':v<tag>' "
                    "suffix to bump — left unchanged",
                    file=sys.stderr,
                )
            pkg["identifier"] = new_id
    _dump(server_path, server)
```

- [ ] **Step 2: Run local smoke render, verify Python is valid**

```bash
cd /mnt/code/fastmcp-server-template
rm -rf /tmp/smoke && uv run --no-project --with copier \
  copier copy --trust --defaults --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
uv run --no-project python -c "import ast; ast.parse(open('/tmp/smoke/scripts/bump_manifests.py').read())"
```

Expected: both commands exit 0 (smoke render produces a valid Python file).

- [ ] **Step 3: Commit**

```bash
cd /mnt/code/fastmcp-server-template
git add scripts/bump_manifests.py.jinja
git commit -m "$(cat <<'EOF'
feat(bump_manifests): add defensive isinstance + null-identifier guards

Upstreamed from image-generation-mcp's local hardening.  Handles
malformed server.json (non-dict top level, non-list packages,
non-dict pkg entries) and JSON-null OCI identifier by falling back
to empty string rather than raising TypeError in re.subn.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 4: Add CLAUDE.md sentinel assertion to `template-ci.yml`

**Files:**
- Modify: `/mnt/code/fastmcp-server-template/.github/workflows/template-ci.yml`

Cheap regression guard — if anyone (including a future copier-update bot) renders a CLAUDE.md without sentinel markers, template-ci catches it on PR.

- [ ] **Step 1: Apply the edit**

Use `Edit` on `.github/workflows/template-ci.yml`. Add a new step immediately after the existing `- name: pytest` step.

OLD (end of file):
```yaml
      - name: pytest
        working-directory: /tmp/smoke
        run: uv run pytest -x -q
```

NEW:
```yaml
      - name: pytest
        working-directory: /tmp/smoke
        run: uv run pytest -x -q

      - name: CLAUDE.md sentinel structure
        working-directory: /tmp/smoke
        run: |
          grep -q 'DOMAIN-START' CLAUDE.md || { echo "::error::missing DOMAIN-START marker"; exit 1; }
          grep -q 'TEMPLATE-OWNED SECTIONS BELOW' CLAUDE.md || { echo "::error::missing TEMPLATE-OWNED fence"; exit 1; }
          grep -q 'TEMPLATE-OWNED SECTIONS END' CLAUDE.md || { echo "::error::missing TEMPLATE-OWNED end fence"; exit 1; }
```

- [ ] **Step 2: Verify locally by running the grep against the current smoke render**

```bash
cd /tmp/smoke
grep -q 'DOMAIN-START' CLAUDE.md && echo "✓ DOMAIN-START"
grep -q 'TEMPLATE-OWNED SECTIONS BELOW' CLAUDE.md && echo "✓ TEMPLATE-OWNED fence"
grep -q 'TEMPLATE-OWNED SECTIONS END' CLAUDE.md && echo "✓ TEMPLATE-OWNED end fence"
```

Expected: three checkmarks.

- [ ] **Step 3: Commit**

```bash
cd /mnt/code/fastmcp-server-template
git add .github/workflows/template-ci.yml
git commit -m "$(cat <<'EOF'
ci(template): assert rendered CLAUDE.md has sentinel structure

Cheap regression guard.  If the CLAUDE.md.jinja sentinel fences are
ever accidentally removed, template-ci fails on PR instead of
silently shipping to consumers.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 5: Run full local template gate

**Files:** none (verification only)

- [ ] **Step 1: Full smoke render and gate**

```bash
cd /mnt/code/fastmcp-server-template
rm -rf /tmp/smoke /tmp/smoke2
uv run --no-project --with copier \
  copier copy --trust --defaults --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke
uv run --no-project --with copier \
  copier copy --trust --defaults --data-file tests/fixtures/smoke-answers.yml . /tmp/smoke2
diff -r /tmp/smoke /tmp/smoke2 > /tmp/smoke-diff 2>&1 || { echo "NOT IDEMPOTENT:"; cat /tmp/smoke-diff; exit 1; }
echo "✓ idempotent"
cd /tmp/smoke
uv sync --all-extras --dev
uv run ruff check .
uv run ruff format --check .
uv run mypy src/
uv run pytest -x -q
grep -q 'DOMAIN-START' CLAUDE.md && grep -q 'TEMPLATE-OWNED SECTIONS BELOW' CLAUDE.md && grep -q 'TEMPLATE-OWNED SECTIONS END' CLAUDE.md && echo "✓ sentinels"
```

Expected: idempotent, ruff/mypy/pytest all pass, three sentinels present.

- [ ] **Step 2: No commit needed**

If anything fails, back up and fix the preceding task. Do not proceed to Task 6.

### Task 6: Open PR for the feat branch

**Files:** none (GitHub PR creation only)

- [ ] **Step 1: Push and open PR**

```bash
cd /mnt/code/fastmcp-server-template
git push -u origin feat/shared-infra-claude-md
gh pr create --base main --head feat/shared-infra-claude-md \
  --title "feat: template v1.1.5 — CLAUDE.md Shared Infrastructure + Dockerfile sentinels + bump_manifests hardening" \
  --body "$(cat <<'EOF'
## Summary

Bundles the changes needed to unblock copier-update across the fleet (see `docs/superpowers/specs/2026-04-22-copier-sync-and-claude-md-parity-design.md`).

- `CLAUDE.md.jinja`: adds Shared Infrastructure section inside the TEMPLATE-OWNED block (pre-existing on branch).
- `Dockerfile.jinja`: adds `DOCKERFILE-APT-DEPS-*` and `DOCKERFILE-UV-EXTRAS-*` sentinel blocks so domains can extend without losing customization across copier update. Image-gen's `--extra all` + git-lfs customization will fit inside these.
- `scripts/bump_manifests.py.jinja`: defensive isinstance + null-identifier handling upstreamed from image-gen.
- `template-ci.yml`: asserts rendered CLAUDE.md contains both sentinel fences.

## Test plan

- [x] Local render + idempotence check: `rm -rf /tmp/smoke && copier copy ... . /tmp/smoke` × 2, `diff -r`
- [x] Local gate: `uv sync --all-extras --dev && uv run ruff check . && uv run ruff format --check . && uv run mypy src/ && uv run pytest -x -q`
- [x] Sentinel grep passes on rendered `CLAUDE.md`

## Release note

After merge, dispatch `template-release.yml` with `bump: patch` → `v1.1.5`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: PR URL printed.

- [ ] **Step 2: Wait for template-ci to pass, then merge**

```bash
gh pr checks <PR_NUMBER> --watch
gh pr merge <PR_NUMBER> --squash --delete-branch
```

Expected: all checks green, PR merged, `feat/shared-infra-claude-md` deleted on remote.

- [ ] **Step 3: Update local main**

```bash
cd /mnt/code/fastmcp-server-template
git checkout main
git pull --ff-only origin main
```

---

## Phase 2 — Release template v1.1.5

### Task 7: Dispatch `template-release.yml` to tag v1.1.5

**Files:** none

- [ ] **Step 1: Dispatch with `bump: patch`**

```bash
gh workflow run template-release.yml --repo pvliesdonk/fastmcp-server-template \
  -f bump=patch
sleep 3
gh run list --repo pvliesdonk/fastmcp-server-template --workflow=template-release.yml --limit 1
```

Expected: run in `queued` or `in_progress` state.

- [ ] **Step 2: Watch run to completion**

```bash
RUN_ID=$(gh run list --repo pvliesdonk/fastmcp-server-template --workflow=template-release.yml --limit 1 --json databaseId -q '.[].databaseId')
gh run watch "$RUN_ID" --repo pvliesdonk/fastmcp-server-template --exit-status
```

Expected: run completes with `success`.

- [ ] **Step 3: Verify tag and release exist**

```bash
gh release view v1.1.5 --repo pvliesdonk/fastmcp-server-template | head -20
```

Expected: release page with v1.1.5 notes.

- [ ] **Step 4: Pull the new tag locally**

```bash
cd /mnt/code/fastmcp-server-template
git fetch --tags
git tag -l 'v1.1.5'
```

Expected: output line `v1.1.5`.

---

## Phase 3 — Per-consumer alignment

Three tracks, one per consumer. Each track has a CLAUDE.md migration PR and a file-convergence PR. Tracks are independent — can be done in parallel by separate subagents.

**Before starting any track,** pause the weekly cron on all three consumers so a Monday firing doesn't race your PRs. Comment out the `schedule:` block on each:

### Task 8: Temporarily disable copier-update cron on all three consumers

**Files:** each consumer's `.github/workflows/copier-update.yml`

- [ ] **Step 1: For each consumer, create a one-commit PR that comments out the cron**

```bash
for d in /mnt/code/markdown-mcp /mnt/code/scholar-mcp /mnt/code/image-gen-mcp; do
  cd "$d"
  git checkout -B chore/pause-copier-cron origin/main
  # Comment the cron schedule line
  sed -i.bak 's|^\( *- cron: "0 6 \* \* 1"\)|# \1  # TEMPORARILY PAUSED during copier-sync effort — see copier-sync plan|' .github/workflows/copier-update.yml
  rm -f .github/workflows/copier-update.yml.bak
  git add .github/workflows/copier-update.yml
  git commit -m "chore(ci): pause copier-update cron during fleet-sync PRs"
  git push -u origin chore/pause-copier-cron
  gh pr create --base main --head chore/pause-copier-cron \
    --title "chore(ci): pause copier-update cron during fleet-sync" \
    --body "Temporarily comment out the Monday 06:00 UTC cron so fleet-sync PRs don't race with bot runs. Reverted in Phase 4."
done
```

- [ ] **Step 2: Merge each PR (green CI expected — no functional change)**

```bash
for r in markdown-vault-mcp scholar-mcp image-generation-mcp; do
  PR=$(gh pr list --repo pvliesdonk/$r --head chore/pause-copier-cron --json number -q '.[].number')
  gh pr checks "$PR" --repo pvliesdonk/$r --watch
  gh pr merge "$PR" --repo pvliesdonk/$r --squash --delete-branch
done
```

- [ ] **Step 3: Pull main on each consumer**

```bash
for d in /mnt/code/markdown-mcp /mnt/code/scholar-mcp /mnt/code/image-gen-mcp; do
  cd "$d" && git checkout main && git pull --ff-only origin main
done
```

### Track A — markdown-vault-mcp

### Task 9: Finish and merge the existing `refactor/claude-md-sentinels` branch

**Files:**
- `/mnt/code/markdown-mcp/CLAUDE.md` (already edited on branch)

- [ ] **Step 1: Check the branch state**

```bash
cd /mnt/code/markdown-mcp
git fetch origin
git checkout refactor/claude-md-sentinels
git log --oneline main..HEAD
```

Expected: 3 commits (`6e036f1 refactor(claude-md): add DOMAIN + TEMPLATE-OWNED sentinel structure`, `1bfe553 review: add DOMAIN-START/END to Reference + Shared Infrastructure`, `93cbdf9 review: drop Shared Infrastructure from MV CLAUDE.md`).

- [ ] **Step 2: Verify the current CLAUDE.md matches the template v1.1.4 TEMPLATE-OWNED block**

```bash
cd /mnt/code/markdown-mcp
diff <(sed -n '/TEMPLATE-OWNED SECTIONS BELOW/,/TEMPLATE-OWNED SECTIONS END/p' CLAUDE.md) \
     <(cd /mnt/code/fastmcp-server-template && git show v1.1.4:CLAUDE.md.jinja | sed -n '/TEMPLATE-OWNED SECTIONS BELOW/,/TEMPLATE-OWNED SECTIONS END/p' | sed "s/{{ human_name }}/Markdown Vault MCP/g; s/{{ python_module }}/markdown_vault_mcp/g; s/{{ env_prefix }}/MARKDOWN_VAULT_MCP/g")
```

Expected: either no output (match) or very small cosmetic diff. If the diff is substantive, the `refactor/claude-md-sentinels` branch is stale — fix before merging.

- [ ] **Step 3: Run the gate locally**

```bash
cd /mnt/code/markdown-mcp
uv sync --all-extras --dev
uv run ruff check .
uv run ruff format --check .
uv run mypy src/
uv run pytest -x -q
```

Expected: all green. CLAUDE.md changes don't touch code so this is a regression check.

- [ ] **Step 4: Push + open PR + merge**

```bash
cd /mnt/code/markdown-mcp
git push -u origin refactor/claude-md-sentinels
if ! gh pr view refactor/claude-md-sentinels >/dev/null 2>&1; then
  gh pr create --base main --head refactor/claude-md-sentinels \
    --title "refactor(claude-md): add DOMAIN + TEMPLATE-OWNED sentinel structure" \
    --body "Structural migration only — wraps domain-owned sections in DOMAIN-START/END sentinels and fences the template-owned block with TEMPLATE-OWNED comments. No functional changes. Prepares for clean copier-update diffs from template v1.1.5."
fi
PR=$(gh pr view refactor/claude-md-sentinels --json number -q '.number')
gh pr checks "$PR" --watch
gh pr merge "$PR" --squash --delete-branch
git checkout main && git pull --ff-only origin main
```

### Task 10: MV convergence PR (non-CLAUDE.md drift)

**Files:**
- Modify: `/mnt/code/markdown-mcp/scripts/bump_manifests.py`, `.gitignore`, `docker-entrypoint.sh`, `Dockerfile`, `compose.yml`, `docs/deployment/docker.md`, `docs/deployment/oidc.md`, `docs/guides/authentication.md`

Strategy: dry-render the template at `v1.1.5` with MV's answers into a scratch dir, then copy each drifted file across wholesale. `compose.yml` (if MV has real customization) gets inspected case-by-case.

- [ ] **Step 1: Dry-render reference**

```bash
rm -rf /tmp/ref-mv
uv run --no-project --with copier \
  copier copy --trust --defaults \
  --vcs-ref v1.1.5 \
  --data-file /mnt/code/markdown-mcp/.copier-answers.yml \
  /mnt/code/fastmcp-server-template /tmp/ref-mv
ls /tmp/ref-mv/scripts/bump_manifests.py /tmp/ref-mv/.gitignore /tmp/ref-mv/docker-entrypoint.sh /tmp/ref-mv/Dockerfile
```

Expected: all four files exist.

- [ ] **Step 2: Create branch**

```bash
cd /mnt/code/markdown-mcp
git checkout -B chore/converge-template-drift
```

- [ ] **Step 3: Inspect each drifted file's diff, then copy from /tmp/ref-mv where converging**

```bash
cd /mnt/code/markdown-mcp
for f in scripts/bump_manifests.py .gitignore docker-entrypoint.sh Dockerfile compose.yml docs/deployment/docker.md docs/deployment/oidc.md docs/guides/authentication.md; do
  echo "=== $f ==="
  diff -u "$f" "/tmp/ref-mv/$f" | head -40
done > /tmp/mv-converge-diffs.txt
less /tmp/mv-converge-diffs.txt
```

Review each diff. For each file where drift is pure noise or stale content (no domain intent), copy from `/tmp/ref-mv`:

```bash
cd /mnt/code/markdown-mcp
cp /tmp/ref-mv/scripts/bump_manifests.py scripts/bump_manifests.py
cp /tmp/ref-mv/.gitignore .gitignore
cp /tmp/ref-mv/docker-entrypoint.sh docker-entrypoint.sh
cp /tmp/ref-mv/docs/deployment/docker.md docs/deployment/docker.md
cp /tmp/ref-mv/docs/deployment/oidc.md docs/deployment/oidc.md
cp /tmp/ref-mv/docs/guides/authentication.md docs/guides/authentication.md
```

For `Dockerfile` and `compose.yml`: MV's Dockerfile drift should be inspected — if MV has no real domain customization, copy across; otherwise migrate customizations inside the new `DOCKERFILE-APT-DEPS-*` / `DOCKERFILE-UV-EXTRAS-*` blocks. MV's compose.yml has documented drift: inspect to decide converge-or-keep.

```bash
cd /mnt/code/markdown-mcp
diff -u Dockerfile /tmp/ref-mv/Dockerfile
diff -u compose.yml /tmp/ref-mv/compose.yml
```

If the Dockerfile diff is purely the template's new sentinels (no real MV customization), copy the reference. If MV has real extras, edit the reference file to put MV's content inside sentinel blocks, then write that to `Dockerfile`.

- [ ] **Step 4: Run gate locally**

```bash
cd /mnt/code/markdown-mcp
uv sync --all-extras --dev
uv run ruff check . && uv run ruff format --check . && uv run mypy src/ && uv run pytest -x -q
```

Expected: all green. If Dockerfile or compose syntax broke, fix inline.

- [ ] **Step 5: Commit + PR**

```bash
cd /mnt/code/markdown-mcp
git add -A
git commit -m "$(cat <<'EOF'
chore(copier): converge drifted template-owned files to v1.1.5 shape

Dry-renders the v1.1.5 template with MV's answers and syncs
template-owned files (scripts/bump_manifests.py, .gitignore,
docker-entrypoint.sh, Dockerfile, compose.yml, docs/deployment/*,
docs/guides/authentication.md) to the reference shape.  Pre-empts
the copier-update bot PR from surfacing these as conflict markers.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git push -u origin chore/converge-template-drift
gh pr create --base main --head chore/converge-template-drift \
  --title "chore(copier): converge drifted template-owned files to v1.1.5" \
  --body "Pre-emptive alignment before the next copier-update bot run. See spec \`docs/superpowers/specs/2026-04-22-copier-sync-and-claude-md-parity-design.md\` §2.4 + §3.3 Phase 1.5 in the template repo."
```

- [ ] **Step 6: Wait CI, merge, update local main**

```bash
cd /mnt/code/markdown-mcp
PR=$(gh pr view chore/converge-template-drift --json number -q '.number')
gh pr checks "$PR" --watch
gh pr merge "$PR" --squash --delete-branch
git checkout main && git pull --ff-only origin main
```

### Track B — scholar-mcp

### Task 11: scholar CLAUDE.md sentinel migration PR

**Files:**
- Modify: `/mnt/code/scholar-mcp/CLAUDE.md`

Current scholar CLAUDE.md has no sentinels at all. Goal: wrap domain content in `DOMAIN-START/END`, insert the full TEMPLATE-OWNED block from template v1.1.4 verbatim.

- [ ] **Step 1: Dry-render reference**

```bash
rm -rf /tmp/ref-scholar
uv run --no-project --with copier \
  copier copy --trust --defaults \
  --vcs-ref v1.1.4 \
  --data-file /mnt/code/scholar-mcp/.copier-answers.yml \
  /mnt/code/fastmcp-server-template /tmp/ref-scholar
```

Use v1.1.4 (not v1.1.5) because Phase 4 bot PR will carry v1.1.5's Shared Infrastructure delta. This PR keeps the sentinel migration small and reviewable.

- [ ] **Step 2: Create branch**

```bash
cd /mnt/code/scholar-mcp
git checkout -B refactor/claude-md-sentinels
```

- [ ] **Step 3: Construct the new CLAUDE.md**

Read the current scholar CLAUDE.md and the reference template CLAUDE.md:

```bash
cat /mnt/code/scholar-mcp/CLAUDE.md
cat /tmp/ref-scholar/CLAUDE.md
```

Produce a merged file with this structure (use the `Write` tool to overwrite `/mnt/code/scholar-mcp/CLAUDE.md`):

```markdown
# scholar-mcp

FastMCP server scaffold. See [TEMPLATE.md](TEMPLATE.md) for customisation guide.

## Design
<!-- DOMAIN-START -->
<!-- Add scholar-mcp design notes here. Kept across copier update. -->
<!-- DOMAIN-END -->

## Project Structure
<!-- DOMAIN-START -->
```
src/scholar_mcp/
  server.py            -- FastMCP server factory (make_server) + auth wiring
  config.py            -- env var loading; add domain config fields here
  cli.py               -- CLI entry point (serve command)
  _server_deps.py      -- lifespan + Depends() DI; ServiceBundle holds all services
  _server_tools.py     -- MCP tools; dispatches to category modules
  _server_resources.py -- MCP resources; add domain resources here
  _server_prompts.py   -- MCP prompts; add domain prompts here
  _task_queue.py       -- In-memory task queue for background async operations
  _rate_limiter.py     -- Rate limiter, retry, try-once + RateLimitedError
```
<!-- DOMAIN-END -->

<!-- ===== TEMPLATE-OWNED SECTIONS BELOW — DO NOT EDIT; CHANGES WILL BE OVERWRITTEN ON COPIER UPDATE ===== -->

<!-- [COPY THE TEMPLATE-OWNED BODY FROM /tmp/ref-scholar/CLAUDE.md VERBATIM: the block between the `<!-- ===== TEMPLATE-OWNED SECTIONS BELOW` line and the `<!-- ===== TEMPLATE-OWNED SECTIONS END` line, not including the fence comments themselves] -->

<!-- ===== TEMPLATE-OWNED SECTIONS END ===== -->

## Key Patterns
<!-- DOMAIN-START -->

- Library is sync; MCP layer uses `asyncio.to_thread()` for blocking calls
- Write tools tagged `tags={"write"}`, hidden via `mcp.disable(tags={"write"})` in read-only mode
- All tools have MCP annotations (`readOnlyHint`, `destructiveHint`, `openWorldHint`)
- Auth: `_build_bearer_auth()` + `_build_oidc_auth()` called in `make_server()`; MultiAuth when both set
- `_ENV_PREFIX` in `config.py` controls all env var names — change once, affects everything
- **Async task queue**: S2 tools try once (`retry=False`); on 429 `RateLimitedError`, queue with retries for background execution. PDF tools always queue (unless cache hit). `TaskQueue` lives in `ServiceBundle.tasks`.
- **Tool queueing pattern**: extract tool logic into `async def _execute(*, retry=True) -> str`, try with `retry=False`, catch `RateLimitedError` and `bundle.tasks.submit(_execute(retry=True))`
<!-- DOMAIN-END -->
```

The marker `[COPY THE TEMPLATE-OWNED BODY ...]` means: paste the exact content between the two `=====` fence comments in `/tmp/ref-scholar/CLAUDE.md`. Do not include the fence comments themselves — they are already in the target structure above.

Extract it mechanically then splice:

```bash
awk '/===== TEMPLATE-OWNED SECTIONS BELOW/,/===== TEMPLATE-OWNED SECTIONS END/' /tmp/ref-scholar/CLAUDE.md | sed '1d;$d' > /tmp/scholar-owned-block.md
wc -l /tmp/scholar-owned-block.md
python3 - <<'PY'
from pathlib import Path
p = Path('/mnt/code/scholar-mcp/CLAUDE.md')
body = p.read_text().replace(
    '<!-- [COPY THE TEMPLATE-OWNED BODY FROM /tmp/ref-scholar/CLAUDE.md VERBATIM: the block between the `<!-- ===== TEMPLATE-OWNED SECTIONS BELOW` line and the `<!-- ===== TEMPLATE-OWNED SECTIONS END` line, not including the fence comments themselves] -->',
    Path('/tmp/scholar-owned-block.md').read_text().rstrip(),
)
p.write_text(body)
PY
```

Expected: the extracted block is ~85 lines (Conventions + Hard PR Gates + GitHub Review Types + Documentation Discipline + Logging Standard + Config & Customization Contract).

- [ ] **Step 4: Verify sentinel structure + gate passes**

```bash
cd /mnt/code/scholar-mcp
grep -c 'DOMAIN-START' CLAUDE.md   # expect 3
grep -c 'DOMAIN-END' CLAUDE.md     # expect 3
grep -c 'TEMPLATE-OWNED SECTIONS BELOW' CLAUDE.md  # expect 1
grep -c 'TEMPLATE-OWNED SECTIONS END' CLAUDE.md    # expect 1
uv sync --all-extras --dev
uv run ruff check . && uv run ruff format --check . && uv run mypy src/ && uv run pytest -x -q
```

Expected counts as listed; gate all green.

- [ ] **Step 5: Commit + PR**

```bash
cd /mnt/code/scholar-mcp
git add CLAUDE.md
git commit -m "$(cat <<'EOF'
refactor(claude-md): add DOMAIN + TEMPLATE-OWNED sentinel structure

Wraps domain content (Project Structure, Key Patterns, async task
queue notes) in <!-- DOMAIN-START --> / <!-- DOMAIN-END --> blocks
and adopts the template v1.1.4 TEMPLATE-OWNED block verbatim.

No functional changes — purely a structural move so next copier
update produces a small, reviewable diff instead of a wall of
conflict markers.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git push -u origin refactor/claude-md-sentinels
gh pr create --base main --head refactor/claude-md-sentinels \
  --title "refactor(claude-md): add DOMAIN + TEMPLATE-OWNED sentinel structure" \
  --body "Structural move.  No functional changes.  Prepares for clean copier-update diffs from template v1.1.5.  See spec in fastmcp-server-template repo, docs/superpowers/specs/2026-04-22-copier-sync-and-claude-md-parity-design.md §3.2."
```

- [ ] **Step 6: Wait CI, merge, update local main**

```bash
cd /mnt/code/scholar-mcp
PR=$(gh pr view refactor/claude-md-sentinels --json number -q '.number')
gh pr checks "$PR" --watch
gh pr merge "$PR" --squash --delete-branch
git checkout main && git pull --ff-only origin main
```

### Task 12: scholar convergence PR (non-CLAUDE.md drift)

**Files:**
- Modify: `/mnt/code/scholar-mcp/.gitignore`, `docker-entrypoint.sh`, `Dockerfile`, `docs/deployment/docker.md`, `docs/deployment/oidc.md`, `docs/guides/authentication.md`

Note: scholar's `scripts/bump_manifests.py` already matches template — no action on that file. `compose.yml` and `codecov.yml` match — no action.

- [ ] **Step 1: Dry-render reference at v1.1.5**

```bash
rm -rf /tmp/ref-scholar-v1.1.5
uv run --no-project --with copier \
  copier copy --trust --defaults \
  --vcs-ref v1.1.5 \
  --data-file /mnt/code/scholar-mcp/.copier-answers.yml \
  /mnt/code/fastmcp-server-template /tmp/ref-scholar-v1.1.5
```

- [ ] **Step 2: Create branch and inspect**

```bash
cd /mnt/code/scholar-mcp
git checkout -B chore/converge-template-drift
for f in .gitignore docker-entrypoint.sh Dockerfile docs/deployment/docker.md docs/deployment/oidc.md docs/guides/authentication.md; do
  echo "=== $f ==="
  diff -u "$f" "/tmp/ref-scholar-v1.1.5/$f" | head -40
done > /tmp/scholar-converge-diffs.txt
less /tmp/scholar-converge-diffs.txt
```

- [ ] **Step 3: Converge each file**

```bash
cd /mnt/code/scholar-mcp
for f in .gitignore docker-entrypoint.sh Dockerfile docs/deployment/docker.md docs/deployment/oidc.md docs/guides/authentication.md; do
  cp "/tmp/ref-scholar-v1.1.5/$f" "$f"
done
```

For `Dockerfile`: if scholar has no real domain customization vs v1.1.5 shape, the cp above is correct (adopts the new sentinel shape with empty custom blocks). If scholar has customization the sentinel shape doesn't capture, edit inline.

- [ ] **Step 4: Run gate**

```bash
cd /mnt/code/scholar-mcp
uv sync --all-extras --dev
uv run ruff check . && uv run ruff format --check . && uv run mypy src/ && uv run pytest -x -q
```

- [ ] **Step 5: Commit + PR + merge**

```bash
cd /mnt/code/scholar-mcp
git add -A
git commit -m "$(cat <<'EOF'
chore(copier): converge drifted template-owned files to v1.1.5 shape

Syncs .gitignore, docker-entrypoint.sh, Dockerfile,
docs/deployment/*.md, and docs/guides/authentication.md to the
freshly-rendered template v1.1.5 output.  No domain customization
lost — scholar's drift was pure noise (comment headers missing,
whitespace differences).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git push -u origin chore/converge-template-drift
gh pr create --base main --head chore/converge-template-drift \
  --title "chore(copier): converge drifted template-owned files to v1.1.5" \
  --body "Pre-emptive alignment before the next copier-update bot run."
PR=$(gh pr view chore/converge-template-drift --json number -q '.number')
gh pr checks "$PR" --watch
gh pr merge "$PR" --squash --delete-branch
git checkout main && git pull --ff-only origin main
```

### Track C — image-generation-mcp

### Task 13: IG CLAUDE.md sentinel migration PR

**Files:**
- Modify: `/mnt/code/image-gen-mcp/CLAUDE.md`

- [ ] **Step 1: Dry-render reference**

```bash
rm -rf /tmp/ref-ig
uv run --no-project --with copier \
  copier copy --trust --defaults \
  --vcs-ref v1.1.4 \
  --data-file /mnt/code/image-gen-mcp/.copier-answers.yml \
  /mnt/code/fastmcp-server-template /tmp/ref-ig
```

- [ ] **Step 2: Create branch**

```bash
cd /mnt/code/image-gen-mcp
git checkout -B refactor/claude-md-sentinels
```

- [ ] **Step 3: Construct the new CLAUDE.md**

Use the `Write` tool to overwrite `/mnt/code/image-gen-mcp/CLAUDE.md` with:

```markdown
# image-generation-mcp

FastMCP server scaffold. See [TEMPLATE.md](TEMPLATE.md) for customisation guide.

## Design
<!-- DOMAIN-START -->
<!-- Add image-generation-mcp design notes here. Kept across copier update. -->
<!-- DOMAIN-END -->

## Project Structure
<!-- DOMAIN-START -->
```
src/image_generation_mcp/
  server.py            -- FastMCP server factory (make_server) + auth wiring
  config.py            -- env var loading; add domain config fields here
  cli.py               -- CLI entry point (serve command)
  _server_deps.py      -- lifespan + Depends() DI; replace placeholder service
  _server_tools.py     -- MCP tools; replace example tools with domain tools
  _server_resources.py -- MCP resources; add domain resources here
  _server_prompts.py   -- MCP prompts; add domain prompts here
```
<!-- DOMAIN-END -->

<!-- ===== TEMPLATE-OWNED SECTIONS BELOW — DO NOT EDIT; CHANGES WILL BE OVERWRITTEN ON COPIER UPDATE ===== -->

<!-- [PASTE /tmp/ig-owned-block.md HERE — extracted in next sub-step] -->

<!-- ===== TEMPLATE-OWNED SECTIONS END ===== -->

## Key Patterns
<!-- DOMAIN-START -->

- Library is sync; MCP layer uses `asyncio.to_thread()` for blocking calls
- Write tools tagged `tags={"write"}`, hidden via `mcp.disable(tags={"write"})` in read-only mode
- Auth: composed via `fastmcp_pvl_core.build_auth()` inside `make_server()`; MultiAuth assembled automatically when both bearer + OIDC are configured
- `_ENV_PREFIX` in `config.py` controls all env var names — change once, affects everything
<!-- DOMAIN-END -->
```

Extract the template-owned block and splice:

```bash
awk '/===== TEMPLATE-OWNED SECTIONS BELOW/,/===== TEMPLATE-OWNED SECTIONS END/' /tmp/ref-ig/CLAUDE.md | sed '1d;$d' > /tmp/ig-owned-block.md
# Splice: replace the placeholder line with file contents
python3 -c "
import pathlib
p = pathlib.Path('/mnt/code/image-gen-mcp/CLAUDE.md')
body = p.read_text().replace('<!-- [PASTE /tmp/ig-owned-block.md HERE — extracted in next sub-step] -->', pathlib.Path('/tmp/ig-owned-block.md').read_text().rstrip())
p.write_text(body)
"
```

- [ ] **Step 4: Verify + gate**

```bash
cd /mnt/code/image-gen-mcp
grep -c 'DOMAIN-START' CLAUDE.md   # expect 3
grep -c 'DOMAIN-END' CLAUDE.md     # expect 3
grep -c 'TEMPLATE-OWNED SECTIONS BELOW' CLAUDE.md  # expect 1
grep -c 'TEMPLATE-OWNED SECTIONS END' CLAUDE.md    # expect 1
uv sync --all-extras --dev
uv run ruff check . && uv run ruff format --check . && uv run mypy src/ && uv run pytest -x -q
```

Expected counts as listed; gate all green.

- [ ] **Step 5: Commit + PR + merge**

```bash
cd /mnt/code/image-gen-mcp
git add CLAUDE.md
git commit -m "$(cat <<'EOF'
refactor(claude-md): add DOMAIN + TEMPLATE-OWNED sentinel structure

Wraps domain content in sentinel blocks and adopts the template
v1.1.4 TEMPLATE-OWNED block verbatim.  Prepares for clean
copier-update diffs from template v1.1.5.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git push -u origin refactor/claude-md-sentinels
gh pr create --base main --head refactor/claude-md-sentinels \
  --title "refactor(claude-md): add DOMAIN + TEMPLATE-OWNED sentinel structure" \
  --body "Structural move.  No functional changes."
PR=$(gh pr view refactor/claude-md-sentinels --json number -q '.number')
gh pr checks "$PR" --watch
gh pr merge "$PR" --squash --delete-branch
git checkout main && git pull --ff-only origin main
```

### Task 14: IG convergence PR — includes Dockerfile sentinel adoption

**Files:**
- Modify: `/mnt/code/image-gen-mcp/Dockerfile`, `codecov.yml`, `.gitignore`, `docker-entrypoint.sh`, `docs/deployment/docker.md`, `docs/deployment/oidc.md`, `docs/guides/authentication.md`

Note: IG's `scripts/bump_manifests.py` will match v1.1.5 after the template absorbs its isinstance hardening — no local change needed unless it still diffs after dry-render.

- [ ] **Step 1: Dry-render reference at v1.1.5**

```bash
rm -rf /tmp/ref-ig-v1.1.5
uv run --no-project --with copier \
  copier copy --trust --defaults \
  --vcs-ref v1.1.5 \
  --data-file /mnt/code/image-gen-mcp/.copier-answers.yml \
  /mnt/code/fastmcp-server-template /tmp/ref-ig-v1.1.5
```

- [ ] **Step 2: Create branch and inspect**

```bash
cd /mnt/code/image-gen-mcp
git checkout -B chore/converge-template-drift
for f in Dockerfile codecov.yml .gitignore docker-entrypoint.sh docs/deployment/docker.md docs/deployment/oidc.md docs/guides/authentication.md scripts/bump_manifests.py; do
  echo "=== $f ==="
  diff -u "$f" "/tmp/ref-ig-v1.1.5/$f" | head -40
done > /tmp/ig-converge-diffs.txt
less /tmp/ig-converge-diffs.txt
```

- [ ] **Step 3: Converge non-Dockerfile files**

```bash
cd /mnt/code/image-gen-mcp
for f in codecov.yml .gitignore docker-entrypoint.sh docs/deployment/docker.md docs/deployment/oidc.md docs/guides/authentication.md scripts/bump_manifests.py; do
  cp "/tmp/ref-ig-v1.1.5/$f" "$f"
done
```

If `scripts/bump_manifests.py` diff is empty after the template upstream, this is a no-op cp (idempotent).

- [ ] **Step 4: Migrate Dockerfile customization inside sentinels**

Use the `Write` tool to overwrite `/mnt/code/image-gen-mcp/Dockerfile` with the reference v1.1.5 Dockerfile, but:

- Inside the `DOCKERFILE-APT-DEPS-*` block: keep the v1.1.5 default `RUN apt-get install -y --no-install-recommends git git-lfs gosu ...`. IG's current Dockerfile has no `git-lfs` — re-introducing git-lfs in this convergence is correct; IG builds need it (matches template intent).
  - *If* IG needs additional APT packages beyond `git git-lfs gosu`, add them to the same apt-get install line. Review: `grep apt-get /mnt/code/image-gen-mcp/Dockerfile` before the overwrite for a record of what was there.
- Inside the `DOCKERFILE-UV-EXTRAS-*` block: change both `uv sync` lines to include `--extra all` (image-gen needs this for provider SDKs). The default v1.1.5 template does not include `--extra all`; this is IG's documented customization.

Concrete sequence:

```bash
cd /mnt/code/image-gen-mcp
# Capture original for reference
cp Dockerfile /tmp/ig-dockerfile-prev.txt
# Start from the template-shaped reference
cp /tmp/ref-ig-v1.1.5/Dockerfile Dockerfile
# Add --extra all inside the UV-EXTRAS block (two uv sync commands)
python3 - <<'PY'
from pathlib import Path
p = Path('Dockerfile')
s = p.read_text()
s = s.replace(
    'uv sync --frozen --no-install-project --no-dev',
    'uv sync --frozen --no-install-project --no-dev --extra all',
)
s = s.replace(
    'uv sync --frozen --no-dev',
    'uv sync --frozen --no-dev --extra all',
)
p.write_text(s)
PY
# Verify
grep 'uv sync' Dockerfile
```

Expected: two lines, each ending with `--extra all`.

If IG's pre-convergence Dockerfile had additional APT packages beyond `git git-lfs gosu` (check `/tmp/ig-dockerfile-prev.txt`), append them to the `apt-get install -y --no-install-recommends` line inside the `DOCKERFILE-APT-DEPS-*` block.

- [ ] **Step 5: Run gate**

```bash
cd /mnt/code/image-gen-mcp
uv sync --all-extras --dev
uv run ruff check . && uv run ruff format --check . && uv run mypy src/ && uv run pytest -x -q
```

- [ ] **Step 6: Optional — build the Docker image locally to sanity-check**

```bash
cd /mnt/code/image-gen-mcp
docker build -t image-generation-mcp:local-convergence-check .
```

Expected: successful build. Skip if Docker isn't available — CI will catch regressions.

- [ ] **Step 7: Commit + PR + merge**

```bash
cd /mnt/code/image-gen-mcp
git add -A
git commit -m "$(cat <<'EOF'
chore(copier): converge drifted template-owned files to v1.1.5 shape

- Dockerfile: adopts v1.1.5 sentinel shape; preserves image-gen's
  --extra all customization inside DOCKERFILE-UV-EXTRAS block;
  re-introduces git-lfs into DOCKERFILE-APT-DEPS block.
- codecov.yml: restores __main__.py ignore.
- .gitignore, docker-entrypoint.sh, docs/deployment/*.md,
  docs/guides/authentication.md: converged to template shape.
- scripts/bump_manifests.py: matches template now that IG's
  defensive checks are upstreamed.

Pre-empts the copier-update bot PR from surfacing these as conflict
markers on the next cron.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git push -u origin chore/converge-template-drift
gh pr create --base main --head chore/converge-template-drift \
  --title "chore(copier): converge drifted template-owned files to v1.1.5" \
  --body "Pre-emptive alignment before the next copier-update bot run.  Includes Dockerfile migration to the new DOCKERFILE-APT-DEPS / DOCKERFILE-UV-EXTRAS sentinel shape with image-gen's --extra all customization inside the UV-EXTRAS block."
PR=$(gh pr view chore/converge-template-drift --json number -q '.number')
gh pr checks "$PR" --watch
gh pr merge "$PR" --squash --delete-branch
git checkout main && git pull --ff-only origin main
```

---

## Phase 4 — Dispatch copier-update + steady-state verification

### Task 15: Dispatch copier-update on each consumer and review resulting bot PR

**Files:** none (per-consumer workflow dispatch + PR review)

- [ ] **Step 1: Re-enable cron and dispatch on markdown-vault-mcp**

```bash
cd /mnt/code/markdown-mcp
git checkout -B chore/resume-copier-cron
sed -i 's|^# \(    - cron: "0 6 \* \* 1"\).*|\1  # Monday 06:00 UTC|' .github/workflows/copier-update.yml
git add .github/workflows/copier-update.yml
git commit -m "chore(ci): resume copier-update cron after fleet-sync"
git push -u origin chore/resume-copier-cron
PR=$(gh pr create --base main --head chore/resume-copier-cron --title "chore(ci): resume copier-update cron" --body "Fleet-sync complete; re-enable weekly cron." --json url -q '.url' 2>/dev/null || gh pr view chore/resume-copier-cron --json number -q '.number')
# Merge the resume-cron PR
PR_NUM=$(gh pr view chore/resume-copier-cron --json number -q '.number')
gh pr checks "$PR_NUM" --watch
gh pr merge "$PR_NUM" --squash --delete-branch
git checkout main && git pull --ff-only origin main
# Now dispatch the copier-update workflow
gh workflow run copier-update.yml --repo pvliesdonk/markdown-vault-mcp
sleep 5
RUN_ID=$(gh run list --repo pvliesdonk/markdown-vault-mcp --workflow=copier-update.yml --limit 1 --json databaseId -q '.[].databaseId')
gh run watch "$RUN_ID" --repo pvliesdonk/markdown-vault-mcp --exit-status
```

Expected: workflow run succeeds. Either no diff (runs exits with `changed=false`, no PR opened) — unlikely given the Shared Infrastructure insert into CLAUDE.md — or a small bot PR lands on `copier/update`.

- [ ] **Step 2: Human-review the MV bot PR (acceptance criterion #6 gate)**

```bash
gh pr view copier/update --repo pvliesdonk/markdown-vault-mcp
gh pr diff copier/update --repo pvliesdonk/markdown-vault-mcp
```

Expected diff:
- `.copier-answers.yml`: `_commit` bumped to `v1.1.5`.
- `CLAUDE.md`: Shared Infrastructure section inserted inside the TEMPLATE-OWNED block.
- (No other files should diff.)

**Hard checklist before merging** (all must be true):
- [ ] CI is green on the PR.
- [ ] Diff contains only the two expected files.
- [ ] CLAUDE.md diff is a pure insert of the Shared Infrastructure section — no deletions, no modifications of other template-owned content.
- [ ] You read the diff line-by-line, not just the summary.

If any checkbox fails, **stop and investigate — do not merge**. If the diff contains other files, the convergence PR missed something; open a follow-up convergence PR and re-run the workflow after it lands.

If all checks pass:

```bash
PR=$(gh pr view copier/update --repo pvliesdonk/markdown-vault-mcp --json number -q '.number')
gh pr merge "$PR" --repo pvliesdonk/markdown-vault-mcp --squash --delete-branch
```

- [ ] **Step 3: Resume cron + dispatch + review for scholar-mcp**

```bash
cd /mnt/code/scholar-mcp
git checkout -B chore/resume-copier-cron
sed -i 's|^# \(    - cron: "0 6 \* \* 1"\).*|\1  # Monday 06:00 UTC|' .github/workflows/copier-update.yml
git add .github/workflows/copier-update.yml
git commit -m "chore(ci): resume copier-update cron after fleet-sync"
git push -u origin chore/resume-copier-cron
gh pr create --base main --head chore/resume-copier-cron \
  --title "chore(ci): resume copier-update cron" \
  --body "Fleet-sync complete; re-enable weekly cron."
PR_NUM=$(gh pr view chore/resume-copier-cron --json number -q '.number')
gh pr checks "$PR_NUM" --watch
gh pr merge "$PR_NUM" --squash --delete-branch
git checkout main && git pull --ff-only origin main
gh workflow run copier-update.yml --repo pvliesdonk/scholar-mcp
sleep 5
RUN_ID=$(gh run list --repo pvliesdonk/scholar-mcp --workflow=copier-update.yml --limit 1 --json databaseId -q '.[].databaseId')
gh run watch "$RUN_ID" --repo pvliesdonk/scholar-mcp --exit-status
gh pr view copier/update --repo pvliesdonk/scholar-mcp
gh pr diff copier/update --repo pvliesdonk/scholar-mcp
```

Apply the hard checklist from Step 2 (all four checkboxes must be true). If good:

```bash
PR=$(gh pr view copier/update --repo pvliesdonk/scholar-mcp --json number -q '.number')
gh pr merge "$PR" --repo pvliesdonk/scholar-mcp --squash --delete-branch
```

- [ ] **Step 4: Resume cron + dispatch + review for image-generation-mcp**

```bash
cd /mnt/code/image-gen-mcp
git checkout -B chore/resume-copier-cron
sed -i 's|^# \(    - cron: "0 6 \* \* 1"\).*|\1  # Monday 06:00 UTC|' .github/workflows/copier-update.yml
git add .github/workflows/copier-update.yml
git commit -m "chore(ci): resume copier-update cron after fleet-sync"
git push -u origin chore/resume-copier-cron
gh pr create --base main --head chore/resume-copier-cron \
  --title "chore(ci): resume copier-update cron" \
  --body "Fleet-sync complete; re-enable weekly cron."
PR_NUM=$(gh pr view chore/resume-copier-cron --json number -q '.number')
gh pr checks "$PR_NUM" --watch
gh pr merge "$PR_NUM" --squash --delete-branch
git checkout main && git pull --ff-only origin main
gh workflow run copier-update.yml --repo pvliesdonk/image-generation-mcp
sleep 5
RUN_ID=$(gh run list --repo pvliesdonk/image-generation-mcp --workflow=copier-update.yml --limit 1 --json databaseId -q '.[].databaseId')
gh run watch "$RUN_ID" --repo pvliesdonk/image-generation-mcp --exit-status
gh pr view copier/update --repo pvliesdonk/image-generation-mcp
gh pr diff copier/update --repo pvliesdonk/image-generation-mcp
```

Apply the hard checklist from Step 2. If good:

```bash
PR=$(gh pr view copier/update --repo pvliesdonk/image-generation-mcp --json number -q '.number')
gh pr merge "$PR" --repo pvliesdonk/image-generation-mcp --squash --delete-branch
```

### Task 16: Wait for next Monday cron, verify green no-op on all three

**Files:** none

- [ ] **Step 1: On the Monday following the Task 15 merges, inspect the most recent run on each consumer**

```bash
for r in markdown-vault-mcp scholar-mcp image-generation-mcp; do
  echo "=== $r ==="
  gh run list --repo pvliesdonk/$r --workflow=copier-update.yml --limit 1
  RUN=$(gh run list --repo pvliesdonk/$r --workflow=copier-update.yml --limit 1 --json databaseId -q '.[].databaseId')
  gh run view "$RUN" --repo pvliesdonk/$r --log 2>&1 | grep -E "Keeping template|changed=(true|false)" | head -3
done
```

Expected for each repo: run status `success`, `changed=false`, no branch push. This confirms acceptance criterion #2.

- [ ] **Step 2: Confirm no `copier/update` branch or open PR exists**

```bash
for r in markdown-vault-mcp scholar-mcp image-generation-mcp; do
  echo "=== $r ==="
  gh pr list --repo pvliesdonk/$r --head copier/update --state open --limit 3
done
```

Expected: no open PRs on `copier/update`.

- [ ] **Step 3: Close out the spec**

The spec's success criteria §5 are now either satisfied or explicitly partial. Summarize in a comment on the spec PR (#26 or successor) or on a new "retrospective" issue:

```bash
gh issue create --repo pvliesdonk/fastmcp-server-template \
  --title "RETRO: copier-sync + CLAUDE.md parity completion" \
  --body "Spec: docs/superpowers/specs/2026-04-22-copier-sync-and-claude-md-parity-design.md

## Acceptance criteria

1. Mergeable bot PR without hand-fixes: <list the three PRs from Task 15>
2. Empty PR (no-op): <list the three Task 16 run IDs>
3. All three consumers have DOMAIN + TEMPLATE-OWNED sentinels: ✓ (Tasks 9, 11, 13)
4. Template v1.1.5 tagged: <link to release>
5. template-ci asserts CLAUDE.md structure: ✓ (Task 4)
6. Bot PRs human-reviewed on diff: ✓ (Task 15 step 2)

## Follow-ups

- Issue #<N>: migrate copier-update to GitHub App token
- Issue #<N>: sentinel-protect shared docs/deployment + docs/guides pages
"
```

---

## Rollback

Each phase is independently revertable:

- **Phase 0:** close the follow-up issues.
- **Phase 1:** `git revert` the merge commit on `main` in the template repo. The v1.1.5 tag can be force-deleted (`git tag -d v1.1.5 && git push origin :refs/tags/v1.1.5`) but this is unusual — prefer releasing v1.1.6 with any fix instead.
- **Phase 2 per-consumer PRs:** `gh pr revert` or manually revert on main. CLAUDE.md has no runtime effect.
- **Phase 4 bot PRs:** revert the copier-update bot PR. The `_commit` will remain at v1.1.5 in `.copier-answers.yml` unless also rolled back.

---

## Open questions (flag if you hit these)

- **Task 9 step 2 diff check:** if MV's TEMPLATE-OWNED block has substantively diverged from v1.1.4, the existing `refactor/claude-md-sentinels` branch may need a follow-up commit to re-align. This is a small fixup, not a spec change.
- **Task 10 / 12 / 14 compose.yml handling:** MV has compose.yml drift not characterized in the audit. If the engineer finds real domain configuration there (volumes, env files, etc.), introducing a `COMPOSE-DOMAIN-*` sentinel block to `compose.yml.jinja` is in scope of Phase 1.5 — file a small template PR alongside, or lean on `--conflict=inline` for the next copier update.
- **Task 15 unexpected diff:** if the bot PR contains file changes beyond `.copier-answers.yml` + `CLAUDE.md`, the convergence PR missed a drift point. Stop, diff, identify the miss, and converge in a follow-up small PR before merging the bot PR.
