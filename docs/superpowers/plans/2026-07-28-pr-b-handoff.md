# PR B review record — Vale gate in template-ci

What the review rounds found and how each was settled. Kept because the
"verified clean" list below is what stops the next session re-litigating shell
that has already been checked empirically.

Read with `docs/superpowers/plans/2026-07-28-pr-b-vale-gate.md` (decisions
D1-D9).

## Findings and their resolution

### 1. The pack list was restated, in the step whose own comment forbids restating

`.vale.ini`'s `Packages =` is the source of truth. Four places enumerated it by
hand: this workflow's cache `path:`, the rendered `ci.yml`'s cache `path:`, the
rendered pre-commit `vale-sync` hook's `for p in`, and `.vale.ini`'s own
`BasedOnStyles`. The gate extracts `version`, `files` and `vale_flags` from the
rendered `ci.yml` precisely so they cannot drift, and carries a comment saying
"Extract, never restate (#143/#159)" — while hardcoding the pack list twice.

Consequence of adding a fifth pack: both caches miss it, so it is re-downloaded
every run and the cache steps silently stop doing their job; the pre-commit hook
never sees it as missing, so a downstream's local `vale` breaks with no sync;
and a `BasedOnStyles` entry `Packages` does not fetch makes vale exit
`E100 [loadStyles]`, which the gate reports as "rendered prose must be clean" —
the packs-versus-prose misdiagnosis its `vale sync` guard exists to prevent.

**Settled:** a `vale pack-list lockstep` step derives the set from `Packages =`
and asserts all four enumerations against it; the gate consumes the derived list
via `VALE_PACKS`. The pre-commit hook was a member of the class the original
finding had not enumerated — found by grepping every pack name across the repo.
`actions/cache` cannot take a shell variable in `path:`, so the two cache lists
stay literal and are asserted rather than generated. #159's rule that
`.vale/styles/config/` is never cached is preserved: the enumeration stays
directory-wise.

### 2. The authorization render bypassed the render-hygiene gate

It was rendered inside the Vale step — after `uv sync` and before the gate's own
pack copy, a position where hygiene can never be checked. PR #252 established
that hygiene covers the gate-off render "because a Jinja tag at EOF only appears
in one branch of a conditional", and `enable_authorization=false` is exactly
such a branch.

**Settled:** rendered beside its sibling variants, above the hygiene step and in
its argument list. Review then found two more members of the same class — the
clean-tree toggle renders — sitting below the hygiene step; those were split
into their own render step and added too. Hygiene now covers all five variants.
`/tmp/smoke2` is deliberately excluded: the idempotence step already asserts it
is byte-identical to `/tmp/smoke`.

### 3. `--vcs-ref=HEAD` was missing on the new render

**Settled by pinning every render step**, not by documenting the gap. The Vale
gate made the cost concrete: run locally in a tag-bearing clone, it reported 19
errors against docs merged `main` had already fixed (copier rendered
`_commit: v2.11.2`; the next commit on main is `1fd4657 fix(docs): clear every
Vale error`). The assertion-only siblings failed less loudly the same way. The
`smoke`/`smoke2` idempotence pair must stay pinned together or it reports a
failure that does not exist.

### 4. Extraction pipelines could not print their own diagnostics

A zero-match `grep` exits 1, and under `pipefail` that killed the step at the
assignment — before the guard written to diagnose exactly that case could print.
The shape #159 already fixed once in the version-pin step. **Settled:** every
extraction pipeline carries `|| true`, with the emptiness caught by the guard.

### 5. The gate could pass over nothing

Verified empirically: `vale --glob='!**' docs README.md` prints "0 errors ... in
0 files." and exits 0. The non-empty extraction guards did not cover a `files`
list or glob that stays syntactically valid while matching nothing.
**Settled:** the gate reads back vale's own file count and requires it positive.

### 6. The `vale-sync` extraction re-introduced a shape #159 removed

The `PRECOMMIT` awk was unanchored and unbounded — the two defects `868ed9e`
fixed in the sibling extraction 100 lines above. With the hook's loop reworded,
awk scanned to EOF and captured a later hook's `for p in` as this one's.
**Settled:** anchored at both ends and bounded by the next `- id:`. Confirmed by
constructing both cases.

### 7. The advisory block could turn into a red build with no diagnostic

It runs under the step's `set -euo pipefail`, and its `cp` calls were unguarded,
so a moved `accept.txt` would abort the step with `cp: cannot stat …` and no
`::error::` — after the real gate had already passed. The diagnostic-loss shape
#256 removed from this file. **Settled:** existence check, `trap` restoring the
vocabulary on any exit, and a non-fatal wrapper.

### 8. Maintainer comments understated the number of places to update

`ci.yml.jinja` said a pack change means updating "both" places, and
`.pre-commit-config.yaml.jinja` told the reader its hook goes blind without
saying to update the list. Harmless while drift was silent; actively misleading
now that the lockstep makes it fatal. **Settled:** both name the full set.

## Not actionable

- Checksum diagnostics: a missing checksum line and a corrupt tarball produce
  the same message. Scored below threshold.
- `#` comments in `accept.txt`: gemini raised a HIGH on #145 claiming Vale's
  vocabulary files do not support them. The maintainer did not act and the
  comments are still there. Left alone.
- `restore-keys: vale-styles-v1-` could restore a stale pack snapshot when
  `.vale.ini.jinja` changes the pinned `ai-tells` URL. Pre-existing: the same
  pattern already ships unmodified in `ci.yml.jinja`'s own Vale job, so it is a
  mirrored design choice, not a defect this branch introduces.
- Registry packs are unpinned by design (`.vale.ini.jinja` says so), so an
  upstream rule release can turn the gate red on a PR that touched no prose.
  Accepted; the alternative is pinning three packs and owning the bumps.

## Verified clean — do not re-litigate

Confirmed by more than one independent reviewer, several empirically:

- `read -ra VALE_FLAGS <<<"$GLOB"` yields one correct argv element; the rendered
  `vale_flags` carries no inner quotes, per `ci.yml.jinja`. A diff-only reviewer
  re-raised this from the shell-quoted convenience copy in `CLAUDE.md` and was
  wrong: the gate's own run prints the glob unquoted and lints 13 files.
- `mapfile` without `|| true` is safe: process-substitution status cannot trip
  `set -e`, and the `${#FILES[@]}` guard catches an extraction break.
- `STRICT=$(... | grep -vc ... || true)` is correct under `pipefail`.
- The checksum flow matches the release asset layout; a no-match `grep` fails
  the guard rather than passing silently. Both `errata-ai/vale` and
  `vale-cli/vale` serve the same asset via GitHub's org redirect; the URL now
  names `vale-cli` to match the other two surfaces.
- The fifth scrub anchor matches `CLAUDE.md.jinja` exactly once, is
  unconditional, sits outside both `TEMPLATE-TRACKING` ranges, and its `sed -e`
  matches `FORKING.md.jinja` verbatim. Post-scrub `! grep -niF 'copier update'`
  still holds.
- `hashFiles('.vale.ini.jinja')` is a sound cache key: no Jinja expressions, so
  it renders verbatim.
- The unbounded `awk` extraction anchor on the `ci.yml` side is the accepted
  convention since `44bfee1`; the only later `version:` match is setup-uv's
  `"latest"`, which the semver filter empties and the non-empty guard catches.
- Curl-downloading the binary instead of `vale-cli/vale-action` is a deliberate
  documented divergence, not a silent reversion.
- The advisory block honours #159's "never cache `.vale/styles/config/`".

## Standing traps

- Park `.vscode/` in `.git/info/exclude` before any render. Any uncommitted
  change makes copier mint a temp commit, so `_commit` differs between two
  otherwise identical renders and the idempotence check fails spuriously.
- `vale sync` after every fresh render or vale exits `E100`.
- `git reset --soft` leaves the index staged, so a later selective `git add`
  is a no-op and the commit takes everything.
