#!/usr/bin/env bash
# SessionStart hook — install the binaries a Claude Code on the web container
# does not ship but this repo's documented routines need.
#
# Today that is Vale alone: CLAUDE.md's "Making changes" step 5 calls the Vale
# run "the only pre-push path" for template prose, and a container without the
# binary silently skips it. Everything else the routine needs (uv, python3,
# jq, curl, tar) is already on the image, and every Python tool this repo uses
# is fetched per-invocation by `uv run --with ...`, so there is nothing to
# install for those beyond warming uv's cache.
#
# Local checkouts are left alone: a maintainer's own Vale install (a different
# version, a package manager's copy) must not be shadowed by this one.
set -euo pipefail

[ "${CLAUDE_CODE_REMOTE:-}" = "true" ] || exit 0

REPO="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
BIN="$REPO/.claude/tools/bin"
CI_YML="$REPO/.github/workflows/ci.yml.jinja"

# Extract, never restate (#143/#159). The version lives in the `vale:` job of
# the workflow the template renders for downstreams; template-ci.yml's gate
# reads it from the *rendered* ci.yml with this same awk anchor, and
# CLAUDE.md tells a maintainer to "match the Vale version pinned in the
# rendered .github/workflows/ci.yml". A hard-coded copy here would be a
# fourth restatement of a pin three places already track, and the failure it
# produces — a local run reporting differently from CI — is the exact drift
# that posture exists to prevent.
VER=$(awk '/^  vale:/{f=1} f && /^[[:space:]]+version:/{print; exit}' "$CI_YML" 2>/dev/null \
  | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || true)
if [ -z "$VER" ]; then
  echo "session-start: no vale version pin found in $CI_YML; skipping the vale install" >&2
else
  # Idempotent: the container caches this directory after the hook completes,
  # so a resumed or later session finds the right binary already here. Match
  # on the version, not on mere presence — a bumped pin must reinstall.
  if [ -x "$BIN/vale" ] && "$BIN/vale" --version 2>/dev/null | grep -qF "$VER"; then
    echo "session-start: vale $VER already installed"
  else
    TARBALL="vale_${VER}_Linux_64-bit.tar.gz"
    # vale-cli/vale is the current name (errata-ai/vale redirects); name it the
    # way ci.yml.jinja, .pre-commit-config.yaml.jinja and template-ci.yml
    # already do so all four agree if the redirect is ever retired.
    BASE="https://github.com/vale-cli/vale/releases/download/v${VER}"
    TMP=$(mktemp -d)
    trap 'rm -rf "$TMP"' EXIT
    # Guard every step, not just the checksum compare: an unguarded 404 after a
    # version bump aborts under `set -e` with a bare curl exit code and no clue
    # which pin is wrong.
    if ! curl -sSfL -o "$TMP/$TARBALL" "$BASE/$TARBALL"; then
      echo "session-start: could not download $BASE/$TARBALL — vale $VER release asset missing or unreachable. The version comes from $CI_YML, so check that pin first." >&2
      exit 0
    fi
    if ! curl -sSfL -o "$TMP/checksums.txt" "$BASE/vale_${VER}_checksums.txt"; then
      echo "session-start: could not download the vale $VER checksums file from $BASE" >&2
      exit 0
    fi
    # Catches a truncated or corrupted transfer, not a compromised release:
    # the checksum travels the same channel as the tarball. Same trade
    # template-ci.yml's gate documents and accepts.
    if ! ( cd "$TMP" && grep " $TARBALL\$" checksums.txt | sha256sum -c - >/dev/null ); then
      echo "session-start: vale $VER tarball failed checksum verification" >&2
      exit 0
    fi
    mkdir -p "$BIN"
    if ! tar -xzf "$TMP/$TARBALL" -C "$BIN" vale; then
      echo "session-start: vale $VER tarball has no 'vale' member at its root — release layout changed" >&2
      exit 0
    fi
    echo "session-start: installed vale $VER into $BIN"
  fi
  # PATH for the rest of the session. Appended, not prepended: nothing here
  # should win over a tool the image already provides. Written at most once —
  # the env file is normally fresh per session, but `resume` and `compact` fire
  # SessionStart again, and a re-entered hook must not stack duplicate lines.
  LINE="export PATH=\"\$PATH:$BIN\""
  if [ -n "${CLAUDE_ENV_FILE:-}" ] \
     && ! { [ -f "$CLAUDE_ENV_FILE" ] && grep -qxF "$LINE" "$CLAUDE_ENV_FILE"; }; then
    echo "$LINE" >> "$CLAUDE_ENV_FILE"
  fi
fi

# Warm uv's cache for the two environments every documented routine builds:
# the render (`uv run --no-project --with copier`) and the template's own
# script tests. Both are `uv run --with` invocations that resolve and download
# on first use; doing it here moves that cost into the cached container image
# instead of the first command a session runs. Best-effort — a cold cache only
# makes the first render slower, so a network hiccup here must not fail the
# hook.
uv run --no-project --with copier copier --version >/dev/null 2>&1 \
  || echo "session-start: could not warm the copier cache; the first render will resolve it" >&2
