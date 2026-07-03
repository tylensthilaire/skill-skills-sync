#!/usr/bin/env bash
# release.sh — cut a versioned release locally: stamp -> review -> build -> commit -> tag.
#
#   ./release.sh v0.1.0                    # stamp, show diff, prompt, then commit + tag + build
#   ./release.sh v0.1.0 -m "…"             # custom commit/tag message
#   ./release.sh v0.1.0 -y                 # skip the review prompt
#   ./release.sh v0.1.0 --skip-version-check
#
# This is the CLI-tagging path and it does LOCAL work only: it never pushes and
# never creates the GitHub Release — it prints those commands for you to run, so
# the outward-facing actions stay in your hands. Prefer tagging in the GitHub UI?
# Don't use this script; follow the manual steps in CONTRIBUTING.md.
set -euo pipefail

usage() {
  cat >&2 <<'U'
usage: ./release.sh vX.Y.Z [-m msg] [-y] [--skip-version-check]

Cuts a versioned release locally: stamp origin frontmatter -> review -> build ->
commit -> tag. Never pushes and never creates the GitHub Release — those commands
are printed for you to run. Prefer tagging in the GitHub UI? See CONTRIBUTING.md.
U
}

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

REF=""
MSG=""
ASSUME_YES=0
SKIP_VERSION_CHECK=0
while [ $# -gt 0 ]; do
  case "$1" in
    -m) MSG="${2:-}"; shift 2 ;;
    -y|--yes) ASSUME_YES=1; shift ;;
    --skip-version-check) SKIP_VERSION_CHECK=1; shift ;;
    -h|--help) usage; exit 0 ;;
    -*) echo "error: unknown option $1" >&2; usage; exit 2 ;;
    *) if [ -z "$REF" ]; then REF="$1"; else echo "error: unexpected argument $1" >&2; exit 2; fi; shift ;;
  esac
done

[ -n "$REF" ] || { usage; exit 2; }

# Release tags are vMAJOR.MINOR.PATCH. For a non-release ref (e.g. a SHA), use stamp.py directly.
echo "$REF" | grep -Eq '^v[0-9]+\.[0-9]+\.[0-9]+$' || {
  echo "error: ref '$REF' is not a vX.Y.Z release tag" >&2; exit 2; }

# Discover the one skill in this repo (same rule as build.sh).
SKILL_DIR=""
count=0
for d in "$ROOT"/skills/*/; do
  [ -d "$d" ] || continue
  SKILL_DIR="${d%/}"
  count=$((count + 1))
done
[ "$count" -eq 1 ] || { echo "error: expected exactly one skill under $ROOT/skills, found $count" >&2; exit 1; }
NAME="$(basename "$SKILL_DIR")"
SKILL="$SKILL_DIR/SKILL.md"

# Preflight ------------------------------------------------------------------
[ -z "$(git status --porcelain)" ] || { echo "error: working tree is dirty — commit or stash first" >&2; exit 1; }
git remote get-url origin >/dev/null 2>&1 || { echo "error: no 'origin' remote — git remote add origin <url>" >&2; exit 1; }
if git rev-parse -q --verify "refs/tags/$REF" >/dev/null; then
  echo "error: tag $REF already exists" >&2; exit 1
fi

# metadata.version must match the tag (minus the leading v), unless overridden.
VERSION="$(python3 - "$SKILL" <<'PY'
import re, sys
fm = re.match(r"^---\n(.*?)\n---\n", open(sys.argv[1]).read(), re.DOTALL)
lines = (fm.group(1) if fm else "").splitlines()
inside = False
for ln in lines:
    if re.match(r"^metadata:\s*$", ln):
        inside = True; continue
    if inside:
        if re.match(r"^\S", ln):
            break
        m = re.match(r"^\s+version:\s*(.*)$", ln)
        if m:
            print(m.group(1).strip().strip("'\"")); break
PY
)"
EXPECTED="${REF#v}"
if [ "$SKIP_VERSION_CHECK" -eq 0 ] && [ "$VERSION" != "$EXPECTED" ]; then
  echo "error: metadata.version ('$VERSION') != tag ('$REF' -> '$EXPECTED')." >&2
  echo "       Bump metadata.version in $SKILL first, or pass --skip-version-check." >&2
  exit 1
fi

[ -n "$MSG" ] || MSG="release: $NAME $REF"

# Stamp ----------------------------------------------------------------------
echo "==> stamping origin frontmatter ($REF)"
python3 "$ROOT/stamp.py" "$REF"

echo
echo "==> review the stamp diff:"
git --no-pager diff -- "$SKILL"

if [ "$ASSUME_YES" -eq 0 ]; then
  printf '\nBuild, commit, and tag %s? [y/N] ' "$REF"
  read -r reply || reply=""
  case "$reply" in
    y|Y|yes|YES) ;;
    *) echo "aborted — the stamp is in your working tree; revert with:  git checkout -- $SKILL"; exit 1 ;;
  esac
fi

# Build + validate first — a bad bundle must abort here, before we commit or tag.
# (A post-tag build failure would strand the tag on an unbuildable commit.)
echo "==> building plugin"
if ! "$ROOT/build.sh"; then
  echo "error: build/validation failed — nothing committed or tagged." >&2
  echo "       the stamp is in your working tree; revert with:  git checkout -- $SKILL" >&2
  exit 1
fi

# Publish the skills.json pin hash — the value skills-sync verifies on install
# — computed with skills-sync's own hasher so it can't drift from what consumers
# check. Over the stamped working tree, which is exactly what the tag captures.
echo "==> computing skills.json pin hash"
HASH="$(python3 "$SKILL_DIR/scripts/install.py" hash "$SKILL_DIR")"
printf '%s\n' "$HASH" > "$ROOT/dist/$NAME.sha256"
echo "    $HASH  ->  dist/$NAME.sha256"

# Commit + tag ---------------------------------------------------------------
echo "==> committing"
git commit -qam "$MSG"
echo "==> tagging $REF"
git tag -a "$REF" -m "$MSG"

cat <<DONE

released $NAME $REF locally. Next (outward-facing — run when ready):
  git push --follow-tags
  gh release create $REF dist/$NAME.plugin dist/$NAME.sha256 --title "$NAME $REF" --generate-notes
DONE
