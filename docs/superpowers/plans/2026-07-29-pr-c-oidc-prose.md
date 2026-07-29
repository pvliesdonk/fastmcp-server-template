# PR C: OIDC prose corrections

**Goal:** the authored OIDC prose states only claims that hold against the pinned `fastmcp`/`fastmcp-pvl-core`, each cited to a symbol; drop the false "ephemeral signing key" framing (#260).

**Closes:** none by keyword — `Refs #260`. C fixes #260's authored-**prose** surfaces in `oidc.md.jinja` and `authentication.md.jinja`; the false claim then survives only in the two env-var **table rows** (PR D's region, D1), so #260 closes when D lands. The wizard-spec surface is already correct (generated from corrected core metadata) and the core-runtime warning already landed in pvl-core 4.5.0 (D4).

> **#267 (See also) was dropped from this PR.** The plan originally added an authorization-guide bullet linking pvl-core's README (D6, below). The preflight circus found it (a) misattributed FastMCP **core**'s `AuthMiddleware` hide/deny behaviour to pvl-core — the spike's exact failure mode, a "fix" asserting a new false claim — and (b) carried a broken anchor. Combined with lens 3's point that it reverses #181's stated operator-only "no implementer back-link" rule, the decision was to **drop the bullet** rather than reword it (rewording accurately would have to name `AuthMiddleware`, reintroducing the API symbol #181 purged). #267 is resolved separately, not by this PR. D6 is retained below struck-through as the record of what was tried.

**Spec:** `docs/superpowers/specs/2026-07-27-config-surface-1b-restructured-design.md` — PR C row, §3.1, §5. This is PR C of the strictly-sequential Stage 1b series; A (#269) and B (#271) are merged.

This plan states decisions and the verification method. It does **not** pre-write the corrected sentences: the spike's defining failure was writing prose corrections from core's *help text* rather than its *code*, and one "correction" asserted something new that was also false. Every replacement sentence is authored at execution against the installed source, not from this plan and not from #260's citations (which are against fastmcp 3.3.1; the lock now resolves 3.4.5 — D2).

## Global constraints

- **Cite every behavioural claim.** Any sentence asserting what `fastmcp` or `fastmcp-pvl-core` *does* names the file and symbol it was verified against, in the PR body. A claim you cannot cite is a claim you have not verified — remove it or mark it `[unverified]` and ask.
- **Source of truth is code at the pinned floor**, read from the render's venv (`cd /tmp/smoke && uv run python -c "import inspect; ..."`), never help text and never recall. Floors: `fastmcp-pvl-core>=4.5.0,<5`, `fastmcp>=3.2.4` (lock currently resolves `fastmcp 3.4.5`, `pvl-core 4.5.0`).
- **Vale-clean.** B's gate runs on this PR: 0 errors over the render. No spaced em dash, no `e.g.`/`i.e.`, no `ai-tells` tics. Use the colon form the guides already use. This is agent-authored prose, so the author cannot self-review for these — the gate is the authority (spec §4.1).
- **Prose regions only.** Do not touch any env-var table in these files; those are PR D's region (D1). Do not touch a `DOMAIN-*` marker line or the text between marker fences.
- **CLAUDE.md.jinja coupling.** These files carry no detach-scrub anchors, but if any edit strays into `CLAUDE.md.jinja`, grep `FORKING.md.jinja` and `template-ci.yml` for a scrub rule matching the edited sentence first (spec §5).

## File structure

Three authored `.jinja` files. Each task owns disjoint prose within them.

| File | C owns (prose) | Off-limits (PR D's region) |
|---|---|---|
| `docs/deployment/oidc.md.jinja` | `## JWT Signing Key` section + its admonitions; the client re-registration / Authelia section | the env-var table at the top (rows incl. the false `OIDC_JWT_SIGNING_KEY` row) |
| `docs/guides/authentication.md.jinja` | the `## OIDC` narrative (proxy-flow claims) | the OIDC env-var table |
| ~~`authorization.md.jinja`~~ | ~~`## See also`~~ (Task 4 dropped — see header) | whole file left unchanged |

## Decisions

**D1 — C is prose-only; the false table row is D's to remove.** The `OIDC_JWT_SIGNING_KEY` row in `oidc.md.jinja`'s env-var table repeats the ephemeral claim, but the table is PR D's region: D replaces it with content generated from core's field metadata, whose signing-key help already reads correctly. C does not edit that row. Consequence a reviewer must be told, in the PR body: after C, the *table* still shows the false row; it is removed by D's generated replacement, and the whole series lands before any release. Editing it in C would break the disjoint-region invariant (§3.1) — the exact prose+table mixing that let the spike relocate a false claim — and D would have to undo the hand-edit when it adds splice markers.

**D2 — re-verify against the resolved lock, not #260.** #260 verified against fastmcp 3.3.1; the lock resolves 3.4.5. The derivation block was confirmed byte-identical at 3.4.5 during planning, but every claim is re-run at execution and cited to the version the lock actually resolves, recorded in the PR body.

**D3 — the correction is the two real caveats, verified.** Replace "ephemeral / regenerated on startup / invalidates tokens on restart / Required on Linux/Docker" with what the code does, confirmed at plan time and to be re-confirmed:
- When `oidc_jwt_signing_key` is unset, the key is **derived from the client secret** (`OAuthProxy.__init__`, `fastmcp/server/auth/oauth_proxy/proxy.py` — `jwt_signing_key is None` → `derive_jwt_key(high_entropy_material=upstream_client_secret, salt="fastmcp-jwt-signing-key")`), and `derive_jwt_key` is deterministic HKDF (`fastmcp/server/auth/jwt_issuer.py`; verified `derive_jwt_key(...) == derive_jwt_key(...)` for equal input). **Tokens survive a restart.**
- The real reason to set an explicit key: rotating the client secret changes the derived key and invalidates every issued token; an explicit key decouples token validity from secret rotation.
- `oidc_jwt_signing_key` and `oidc_verify_access_token` apply only on the oidc-proxy path (`fastmcp_pvl_core._auth.build_oidc_proxy_auth`); `build_remote_auth` ignores both. Say so if the surrounding prose implies otherwise.

**D4 — do not cite the runtime warning for this claim.** pvl-core carried the same falsehood in a platform-gated runtime warning; at 4.5.0 `_warn_oidc_caveats` no longer mentions the signing key at all (it warns only about `verify_id_token` without `openid` scope). The docs are now the last surface carrying the false claim. Cite the derivation code directly; do not point the reader at a warning that no longer says it.

**D5 — classify each re-registration/restart claim before touching it.** "Clients must re-authenticate after every restart" is a fastmcp-behaviour claim (cite or correct). "Authelia does not support Dynamic Client Registration (RFC 7591)" is a *provider* fact, not a fastmcp claim — it cannot be cited to a fastmcp symbol, so verify it against Authelia's own docs and leave it if correct, rather than forcing a citation it cannot have. The plan does not assume any of these is wrong; each is verified and corrected only if it fails.

**D6 — ~~#267 is one See-also bullet~~ DROPPED.** Original plan: add a colon-form bullet to the authorization guide's `## See also` pointing at pvl-core's README "Authorization" section, on the theory that a README link is not the API surface `2a0e36d` purged. The circus refuted the execution: the bullet as written misattributed core's `AuthMiddleware` hide/deny behaviour to pvl-core (a new false claim) and used a broken anchor, and an accurate rewrite would have to name `AuthMiddleware` — reintroducing the very symbol `2a0e36d` removed. Bullet dropped; #267 resolved separately. Kept here as the record.

## Tasks

Park `.vscode/` in `.git/info/exclude` before the first render (idempotence trap). Render once at HEAD and re-render only after a `.jinja` edit — copier reads the git index, so commit or `--vcs-ref=HEAD` as in CLAUDE.md's local routine. Run B's gate (`vale …`) after each task; it is the acceptance check.

Commit per task. Each commit message records the symbols cited for that task's claims.

### Task 1 — `oidc.md.jinja`: the JWT signing key prose (#260)

**Files:** Modify `docs/deployment/oidc.md.jinja` (the `## JWT Signing Key` section and its admonition blocks only; not the env-var table row).

- [ ] **Verify the facts** against the render's venv, recording output for the PR body:
  ```bash
  cd /tmp/smoke && uv run python -c "
  import inspect
  from fastmcp.server.auth.oauth_proxy import proxy
  from fastmcp.server.auth.jwt_issuer import derive_jwt_key
  s = inspect.getsource(proxy); i = s.find('jwt_signing_key is None')
  print(s[i-40:i+320])                      # derivation path
  print('deterministic:', derive_jwt_key(high_entropy_material='x', salt='fastmcp-jwt-signing-key')
                        == derive_jwt_key(high_entropy_material='x', salt='fastmcp-jwt-signing-key'))
  import fastmcp, fastmcp_pvl_core
  print('fastmcp', fastmcp.__version__, 'pvl-core', fastmcp_pvl_core.__version__)"
  ```
  Expected: the `derive_jwt_key(...salt='fastmcp-jwt-signing-key')` block; `deterministic: True`. If either differs, stop and reassess — the correction changes.
- [ ] **Rewrite** the section per D3: drop "ephemeral / regenerated on startup / invalidates tokens on restart / Required on Linux/Docker" and the Linux-specific admonition; state the derivation, the restart survival, and the secret-rotation caveat as the actual reason to set the key. Keep the `openssl rand -hex 32` example (still valid guidance for an explicit key).
- [ ] **Re-render** and run B's gate:
  ```bash
  # render per CLAUDE.md step 3, then:
  cd /tmp/smoke && vale --glob='!docs/{superpowers,design,decisions}/**' docs README.md
  ```
  Expected: `0 errors`.
- [ ] **Assert the false claim is gone and the real caveat present** in the render:
  ```bash
  ! grep -niE 'ephemeral|regenerated on startup|invalidates tokens on restart|Required on Linux' /tmp/smoke/docs/deployment/oidc.md
  grep -niE 'derived from|secret rotation|rotating' /tmp/smoke/docs/deployment/oidc.md
  ```
  Expected: first exits 0 (no match), second prints the new caveat. Note both still match the untouched table row's `ephemeral` cell — scope the first grep to below the `## JWT Signing Key` heading, or accept the table row as D1's deferred region and grep the section only.
- [ ] **Commit.** `docs(oidc): correct the JWT signing-key claim — derived, not ephemeral (refs #260)`, body citing `proxy.py`/`jwt_issuer.py` at the resolved version.

### Task 2 — `oidc.md.jinja`: re-registration / restart claims (#260, spec C row)

**Files:** Modify `docs/deployment/oidc.md.jinja` (the client-registration / Authelia section and any remaining restart claim).

- [ ] **Inventory** every remaining behavioural claim in the prose: run `grep -niE 'restart|re-authenticate|re-regist|register|Dynamic Client|persist' docs/deployment/oidc.md.jinja` and list each hit.
- [ ] **Classify** each per D5: fastmcp-behaviour (verify against `fastmcp`/`pvl-core` source, cite) vs provider-fact (verify against the provider's docs) vs already-correct (leave). Record the classification and citation/source per claim.
- [ ] **Correct only the ones that fail.** Do not touch a claim that verifies. Do not force a fastmcp citation onto a provider fact.
- [ ] **Re-render, run B's gate** (`vale …` = 0 errors), and re-grep to confirm no corrected claim reintroduced a tic.
- [ ] **Commit.** `docs(oidc): verify the client-registration and restart claims against source (refs #260)`.

### Task 3 — `authentication.md.jinja`: the OIDC narrative

**Files:** Modify `docs/guides/authentication.md.jinja` (the `## OIDC` narrative only; not the OIDC env-var table).

- [ ] **Inventory** the proxy-flow claims (e.g. "the server proxies OIDC itself", the numbered redirect/login/callback steps) via `grep -n -A20 '^## OIDC' docs/guides/authentication.md.jinja`.
- [ ] **Verify** each against `fastmcp_pvl_core._auth.build_oidc_proxy_auth` and the `OAuthProxy` it constructs (`inspect.getsource`); cite. Correct only what fails.
- [ ] **Re-render, run B's gate** = 0 errors.
- [ ] **Commit.** `docs(authn): verify the OIDC proxy-flow narrative against pvl-core (refs #260)`.

### Task 4 — ~~authorization guide: the missing See-also (#267)~~ DROPPED

Implemented then reverted (see D6 and the header note). The circus found the bullet misattributed core behaviour and carried a broken anchor; #267 is resolved separately, not in this PR. The authorization guide is unchanged from `main`.

## Verification contract (spec §5)

| Check | How | Expected |
|---|---|---|
| Every claim cited | PR body lists file:symbol per behavioural sentence, at the resolved lock version | no uncited behavioural claim |
| Prose is Vale-clean | B's gate over the render (both authz variants) | 0 errors |
| `#260` false claim gone from prose | grep the corrected sections | no `ephemeral`/`invalidates on restart`/`Required on Linux` in prose (table row is D1) |
| `#260` real caveats present | grep | derivation + secret-rotation caveat present |
| ~~`#267` reference present~~ | — | Task 4 dropped after review (see header); the authorization guide is unchanged from `main`, so there is no bullet to check |
| Downstream unaffected | none of these three files is `_skip_if_exists` | edits propagate on `copier update`; no reset-file re-run needed |
| Mechanical edits applied | each task's post-grep asserts the change is in the *render*, not just the source | no silent no-op |

## Traps (from A/B)

- Park `.vscode/` in `.git/info/exclude` before any render, or copier mints a temp commit and `_commit` differs between two renders.
- `vale sync` after every fresh render, or Vale exits `E100`. B's gate step does this; a hand-run must too.
- Render from the git index: commit the `.jinja` edit or use `--vcs-ref=HEAD`, or the edit does not render.
- Do not re-render into `/tmp/smoke` after `uv sync`/`vale sync` and then run the hygiene guard; those write into the tree.

## Out of scope

- The OIDC env-var tables in both files (PR D).
- `wizard-spec.json.jinja` (retired by generation in a later stage; its help already reads correctly).
- Pushing prose fixes upstream into `fastmcp-pvl-core` (core#237).
- `docs/deployment/docker.md`'s deployment-subset table and the `.mcpb` manifest `env` block (hand-owned, spec §7).
