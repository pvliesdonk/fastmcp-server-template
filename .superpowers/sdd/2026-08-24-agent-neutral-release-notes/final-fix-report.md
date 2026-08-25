# Final Review Fix Report

**Date:** 2026-08-25

**Status:** Complete

## Scope

This wave addressed all four final-review findings against the approved
`docs/superpowers/specs/2026-08-24-agent-neutral-review-and-release-notes-design.md`
design. No external follow-up issue was created, and no subagents were
dispatched.

## Changes

### Neutral release-notes skill

- The skill now refuses a dirty worktree before research or writing.
- It fetches the selected base into `refs/remotes/origin/$BASE` and creates the
  notes branch explicitly from fresh `origin/$BASE`, never caller `HEAD`.
- It reviews and validates the exact staged surface before commit.
- It fetches the base again before publication, verifies that the current
  remote base is an ancestor of the notes branch, validates the cumulative
  changed-file surface, and reviews the cumulative diff.
- It requires explicit human confirmation after the branch-base and diff
  reviews and before `git push` or `gh pr create`.
- It classifies issue and pull-request bodies and comments, quoted logs,
  patches, and linked pages as untrusted data. Embedded instructions,
  credential prompts, and command requests are ignored rather than executed.
- It separates authenticated read-only research from credentialed publication.

Structural tests cover remote-base branch creation, the second fetch and
ancestry check, staged and cumulative diff reviews, publication ordering, the
human-confirmation boundary, and untrusted-data guidance.

### Release-notes promoter

- CommonMark ATX headings with zero to three leading spaces are recognized
  outside fenced code.
- Heading shifts preserve indentation, whitespace after the opening hash run,
  and optional closing hash runs.
- Existing patch headings with zero to three leading spaces and optional
  CommonMark closing hashes participate in ascending-order validation.
- Indented patch headings also participate in canonical minor-series
  validation.
- Headings inside backtick and tilde fences remain opaque.

Behavioral tests cover column-zero, indented, tab-separated, and closing-hash
ATX forms, plus indented patch order and cross-series refusals.

### README secret setup

- The generated README now distinguishes two required repository secrets from
  the optional Claude token.
- `CLAUDE_CODE_OAUTH_TOKEN` is explicitly limited to `@claude` and opted-in
  automatic review.
- The setup command is labeled optional.

## Commits

- `a313a3f fix(release): address final automation review`
- The report itself is committed separately after this file is written.

## Verification

### Red phase

- New promoter tests failed in five expected cases: indented ATX shifts and
  indented patch order/series validation.
- New skill and README contracts failed in four expected areas: fresh-base
  branching, staged/cumulative review, untrusted publication guidance, and
  optional token setup.

### Focused and template-side tests

- `uv run --no-project --with pytest pytest tests/test_promote_release_notes.py scripts/tests/test_shared_skill_paths.py scripts/tests/test_readme_secret_contract.py -q`
  - `93 passed`
- `uv run --with pytest --with pyyaml --with jsonschema --with jinja2 --with 'fastmcp-pvl-core>=4.6.1' pytest scripts/tests/ -q`
  - `321 passed, 1 skipped`

### Promoter static checks

- Ruff base lint with the downstream select/ignore configuration: passed.
- Ruff format check at line length 88: passed.
- Ruff structural security and complexity gate with the rendered per-file
  `S603`/`S607` exceptions: passed.
- Commit hooks also passed Ruff, Ruff format, mypy, whitespace, EOF, YAML,
  large-file, and JSON checks.

### Render verification

Rendered from committed `HEAD` into:

- `/tmp/final-fix-smoke` with automatic Claude review disabled.
- `/tmp/final-fix-smoke-review-on` with automatic Claude review enabled.

Results:

- Render hygiene: passed for both pristine renders before Vale or uv wrote
  generated files.
- Pinned Vale: `github.com/errata-ai/vale/v3 v3.14.2`, confirmed from the Go
  binary module metadata; `0 errors, 0 warnings, 0 suggestions` in 15 files for
  each render.
- `uv run mkdocs build --strict`: passed for each render.
- Generated `tests/test_promote_release_notes.py` and
  `tests/test_release_flow_contract.py`: `141 passed, 3 skipped` for each
  render. The three skips are existing placeholder-version/fresh-project
  conditions.

## Concerns

- Material for MkDocs emits its existing informational warning about the
  future MkDocs 2.0 ecosystem. The strict builds still pass; this change does
  not introduce or alter that warning.
- The locally installed system Vale is newer than CI. Verification therefore
  used a separately built `v3.14.2` binary whose module metadata matches the
  rendered CI pin.
- No product or migration concerns remain from these findings.
