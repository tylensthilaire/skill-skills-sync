#!/usr/bin/env bash
# Build the distributable .plugin from the skill in this repo.
#
#   ./build.sh            -> dist/<name>.plugin
#   ./build.sh /some/dir  -> writes the .plugin into /some/dir
#
# The .plugin is a build artifact (gitignored). Attach it to a GitHub Release.
# The plugin version is read from the skill's `metadata.version` frontmatter,
# so the two can never drift — bump the skill, rebuild, and the manifest follows.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Exactly one skill lives under skills/<name>/ — discover it (keeps this script
# identical across every skill repo). Plain glob, so it works on bash 3.2 (macOS).
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
OUT_DIR="${1:-$ROOT/dist}"

[ -f "$SKILL" ] || { echo "error: skill not found at $SKILL" >&2; exit 1; }

# Read name / version / description from the skill frontmatter (single source of
# truth). metadata.version is nested; description is a YAML folded scalar (>-).
read_fm() {
  python3 - "$SKILL" "$1" <<'PY'
import re, sys
text = open(sys.argv[1]).read()
m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
lines = (m.group(1) if m else "").splitlines()
field = sys.argv[2]

def scalar(key):
    """Top-level `key:` — plain value or a folded/literal block scalar body."""
    for i, ln in enumerate(lines):
        s = re.match(rf"^{key}:\s*(.*)$", ln)
        if not s:
            continue
        first = s.group(1).strip()
        if first in (">", ">-", ">+", "|", "|-", "|+"):
            body, j = [], i + 1
            while j < len(lines) and (lines[j].startswith("  ") or lines[j].strip() == ""):
                body.append(lines[j].strip())
                j += 1
            return " ".join(x for x in body if x)
        return first.strip("'\"")
    return ""

def nested(parent, key):
    """`key:` indented under a top-level `parent:` block."""
    inside = False
    for ln in lines:
        if re.match(rf"^{parent}:\s*$", ln):
            inside = True
            continue
        if inside:
            if re.match(r"^\S", ln):
                break
            s = re.match(rf"^\s+{key}:\s*(.*)$", ln)
            if s:
                return s.group(1).strip().strip("'\"")
    return ""

print(scalar("name") if field == "name"
      else scalar("description") if field == "description"
      else nested("metadata", "version"))
PY
}

FM_NAME="$(read_fm name)"
VERSION="$(read_fm version)"
DESC="$(read_fm description)"

[ -n "$VERSION" ] || { echo "error: no metadata.version in $SKILL" >&2; exit 1; }
[ "$FM_NAME" = "$NAME" ] || { echo "error: frontmatter name '$FM_NAME' != skill folder '$NAME'" >&2; exit 1; }

# Keywords: derive from the skill name so this script needs no per-repo edits.
KEYWORDS="$(NAME="$NAME" python3 -c 'import json,os;print(json.dumps(os.environ["NAME"].split("-")+["claude-skill"]))')"

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
PKG="$STAGE/$NAME"
mkdir -p "$PKG/.claude-plugin" "$PKG/skills"

# Package the whole skill folder (SKILL.md + scripts/ references/ knowledge/ …).
cp -R "$SKILL_DIR" "$PKG/skills/$NAME"
[ -f "$ROOT/README.md" ] && cp "$ROOT/README.md" "$PKG/README.md"

DESC_JSON="$(DESC="$DESC" python3 -c 'import json,os;print(json.dumps(os.environ["DESC"]))')"
cat > "$PKG/.claude-plugin/plugin.json" <<JSON
{
  "name": "$NAME",
  "version": "$VERSION",
  "description": $DESC_JSON,
  "author": { "name": "Tylen St Hilaire" },
  "keywords": $KEYWORDS
}
JSON

# Validate before zipping.
python3 - "$PKG" <<'PY'
import json, re, os, sys
base = sys.argv[1]; ok = True
def chk(c, m):
    global ok; print(("[PASS] " if c else "[FAIL] ") + m); ok = ok and c
pj = json.load(open(f"{base}/.claude-plugin/plugin.json"))
name = pj.get("name", "")
chk(re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name) is not None, "name is kebab-case")
chk(re.fullmatch(r"\d+\.\d+\.\d+", pj.get("version", "")) is not None, f"version is semver ({pj.get('version')})")
sm = f"{base}/skills/{name}/SKILL.md"
chk(os.path.isfile(sm), "SKILL.md present")
t = open(sm).read()
chk(t.count("```") % 2 == 0, "code fences balanced")
fm = re.match(r"^---\n(.*?)\n---\n", t, re.DOTALL)
chk(fm is not None, "frontmatter present")
chk(fm is None or "[[" not in fm.group(1), "no vault wikilinks in frontmatter")
sys.exit(0 if ok else 1)
PY

mkdir -p "$OUT_DIR"
PLUGIN="$OUT_DIR/$NAME.plugin"
STAGE_ZIP="$STAGE/$NAME.plugin"
( cd "$PKG" && zip -rq "$STAGE_ZIP" . -x "*.DS_Store" )
cp "$STAGE_ZIP" "$PLUGIN"

echo "built $PLUGIN (v$VERSION)"
