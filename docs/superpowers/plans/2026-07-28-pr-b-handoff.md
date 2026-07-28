# PR B handoff — Vale gate in template-ci

Written 2026-07-28, mid-review. **Not clean. Do not push.**

Read with `.superpowers/sdd/pr-b-brief.md` (original scope) and
`docs/superpowers/plans/2026-07-28-pr-b-vale-gate.md` (decisions D1-D7).

## State

Branch `ci/vale-gate-over-render`, HEAD `b4bc2ee`, 5 commits, **unpushed**.
Base `main` @ `1fd4657`. `Closes #270`.

Files touched: `.github/workflows/template-ci.yml`, `CLAUDE.md`,
`docs/superpowers/plans/2026-07-28-pr-b-vale-gate.md`.

Circus round 2 ran against `1fd4657..3087af3`, one commit behind current HEAD.

## Resolved in `b4bc2ee`

The local routine in `CLAUDE.md` ordered `vale sync` before the
render-hygiene check. Lenses 1, 2 and 3 each found it independently. Fixed:
hygiene is step 4, Vale is step 5, and the caveat names both `uv sync` and
`vale sync` as tree-writers. Two false claims in the same block were also
corrected (a version described as pinned but absent, and "3.11-3.14" for a
step gated to 3.11).

Verified empirically: `check_render_hygiene.py` **fails** on a `vale sync`'d
render, because `_SKIP_DIRS` covers `.git/.venv/__pycache__` and the tool
caches but not `.vale/styles`. So it walks the downloaded packs and reports
`Google/EmDash.yml` as a violation. The ordering fix is load-bearing.

## Open findings — none fixed

### 1. The pack list is restated, in the step whose own comment forbids restating (lens 5)

`template-ci.yml:365-371` (cache `path:`) and `:442`
(`for PACK in Google proselint write-good ai-tells`).

`.vale.ini.jinja:45` (`Packages =`) is the source of truth. The step extracts
`version`, `files` and `vale_flags` from the rendered `ci.yml` precisely so
they cannot drift, and carries a comment at `:388-390` saying "Extract, never
restate (#143/#159)". The pack list is the one piece of Vale configuration it
hardcodes instead — twice. `ci.yml.jinja:290-292` already says a pack change
means updating "both" places; this makes it four, and that comment was not
updated.

Consequence of adding a fifth pack: the cache `path:` misses it so it is
re-downloaded every run, silently defeating the cache step's stated purpose;
and the copy loop misses it so `/tmp/smoke-authz-off` lacks a style that
`BasedOnStyles` lists, and Vale exits `E100 [loadStyles]`. The step reports
that as `::error::vale reports errors in /tmp/smoke-authz-off — rendered prose
must be clean`: exactly the packs-versus-prose misdiagnosis the adjacent
`vale sync` guard exists to prevent.

Direction: derive the pack list from the rendered `.vale.ini`'s `Packages =`
line and drive the copy loop from it. `actions/cache` cannot take a shell
variable in `path:`, so that list stays literal — assert it equals the
rendered `Packages` set so drift fails loudly. Note #159 forbids caching
`.vale/styles/config/` (restore-keys would clobber a new vocab term with a
stale snapshot), so the four-directory enumeration must stay directory-wise.

### 2. The new render variant bypasses the render-hygiene gate (lens 4)

`template-ci.yml:432-437` renders `/tmp/smoke-authz-off`; the hygiene call at
`:106` covers only `/tmp/smoke` and `/tmp/smoke-gate-off`.

PR #252 established the rule and the in-file comment at `:100-102` states it:
hygiene covers the gate-off render "because a Jinja tag at EOF only appears in
one branch of a conditional". `enable_authorization=false` is exactly such a
branch, and per D4 it is materially different prose. A trailing-whitespace or
`{%- endif %}`-at-EOF defect living only in that branch is the latent
`copier update` conflict class of #251, now rendered in CI but never checked.

It is also rendered after `uv sync` and then written into by the pack copy, so
it can never be checked where it currently sits.

Direction: move the render up beside the `structural gate toggle-off render`
step, extend `:106` to pass all three directories, and have the Vale step
consume the existing directory instead of doing its own `rm -rf` + `copier
copy`. `check_render_hygiene.py`'s `main()` takes an argv list; confirm it
accepts three positional paths before relying on it.

### 3. `--vcs-ref=HEAD` missing on the new render (lens 5, lower confidence)

Consistent with every sibling render step and with the acknowledged gap
documented at `:129-137`, so CI is unaffected (tagless checkout). But this
step exists to lint the prose being changed, so in a tag-bearing local clone
it lints released prose rather than the working tree — sharper than for the
assertion-only siblings. Either pin both renders or extend the comment at
`:135-137` to record that the Vale gate now depends on that gap. Folding the
render into the sibling block (finding 2) makes the posture consistent either
way.

## Not actionable

- Checksum diagnostics: a missing checksum line and a corrupt tarball produce
  the same message. Lens 4 scored it ~60%, below threshold.
- `#` comments in `accept.txt`: gemini raised a HIGH on #145 claiming Vale's
  vocabulary files do not support them. The maintainer did not act and the
  comments are still there. Left alone.

## Verified clean, do not re-litigate

Confirmed independently by more than one lens:

- `read -ra VALE_FLAGS <<<"$GLOB"` yields one correct argv element; the
  rendered `vale_flags` carries no inner quotes, per `ci.yml.jinja:330-336`.
- `mapfile` without `|| true` is safe: process-substitution status cannot trip
  `set -e`, and the `${#FILES[@]}` guard catches an extraction break.
- `STRICT=$(... | grep -vc ... || true)` is correct under `pipefail` in all
  three cases.
- The checksum flow matches errata-ai/vale's release asset layout; a no-match
  `grep` fails the guard rather than passing silently.
- `|| true` on `CI_VER`/`PC_VER` restores the posture `868ed9e` (#159) set for
  the sibling step; the version-pin step had carried the unguarded form since
  `44bfee1` and was never swept.
- The fifth scrub anchor matches `CLAUDE.md.jinja:210` exactly once, is
  unconditional, sits outside both `TEMPLATE-TRACKING` ranges, and its `sed -e`
  matches `FORKING.md.jinja:61` verbatim. Post-scrub `! grep -niF 'copier
  update'` still holds.
- `hashFiles('.vale.ini.jinja')` is a sound cache key: no Jinja expressions, so
  it renders verbatim.
- The unbounded `awk` extraction anchor is the accepted convention on the
  `ci.yml` side since `44bfee1`; the only later `version:` match is setup-uv's
  `"latest"`, which the semver filter empties and the non-empty guard catches.
- Curl-downloading the binary instead of `vale-cli/vale-action` is a
  deliberate documented divergence, not a silent reversion.
- The advisory block honours #159's "never cache `.vale/styles/config/`": it
  backs up and restores `accept.txt`, and `config/` is outside the cached paths.

## Next session

1. Read the sixth lens's output, never collected:
   `/tmp/claude-1000/-mnt-code-mcp-servers-fastmcp-server-template/980e7f63-3844-474f-8293-9126fddafcc6/tasks/ad10737f2ba45719c.output`
2. Fix findings 1-3 in one commit.
3. Re-run the **full** circus against `origin/main..HEAD`. Round 2's findings
   were structural, so a subset re-run is not valid.
4. Only then push and open the PR. Merging and release dispatch are human-only.

## Standing traps

- Park `.vscode/` in `.git/info/exclude` before any render; a dirty tree makes
  copier mint a temp commit and `_commit` differs between two identical renders.
- `vale sync` after every fresh render or vale exits `E100`.
- `git reset --soft` leaves the index staged, so a later selective `git add`
  is a no-op and the commit takes everything.
