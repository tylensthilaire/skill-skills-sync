#!/usr/bin/env python3
"""stamp.py — write origin frontmatter into the skill's SKILL.md at release time.

Usage:
    ./stamp.py <ref>        # e.g. ./stamp.py v0.1.0

Writes three top-level frontmatter keys that `skills-sync` reads to trace an
installed copy back to its source (see the skills-sync skill's
references/manifest-format.md):

    source       git URL of this repo (from `git remote get-url origin`)
    source-path  path to the skill folder within the repo (skills/<name>)
    ref          the tag/SHA passed on the command line

`ref` is the exact git ref this release is cut at — written verbatim so it feeds
a manifest's `ref` field and stays checkout-able. It is NOT the human-facing
metadata.version (which may read 0.1.0 while the tag is v0.1.0).

Refuses to run on a dirty working tree so you never tag a half-stamped state.
The flow is one atomic, reviewable step: stamp -> review -> commit -> tag.
Because `ref` is the tag name you choose up front, stamping before you tag is
self-consistent: the committed SKILL.md declares the same ref the tag points at.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def sh(*args: str) -> str:
    return subprocess.run(
        args, cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def find_skill_dir() -> Path:
    skills = ROOT / "skills"
    dirs = [d for d in sorted(skills.iterdir()) if d.is_dir()] if skills.exists() else []
    if len(dirs) != 1:
        sys.exit(f"error: expected exactly one skill under {skills}, found {len(dirs)}")
    return dirs[0]


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] in ("-h", "--help"):
        sys.exit(__doc__)
    ref = sys.argv[1].strip()

    # Clean tree only — stamp/review/commit/tag is one atomic, reviewable step.
    if sh("git", "status", "--porcelain"):
        sys.exit("error: working tree is dirty — commit or stash first, then stamp")

    try:
        source = sh("git", "remote", "get-url", "origin")
    except subprocess.CalledProcessError:
        sys.exit("error: no 'origin' remote — `git remote add origin <url>` so source can be recorded")

    skill_dir = find_skill_dir()
    source_path = skill_dir.relative_to(ROOT).as_posix()
    md = skill_dir / "SKILL.md"
    text = md.read_text()

    m = re.match(r"^(---\n)(.*?)(\n---\n)", text, re.DOTALL)
    if not m:
        sys.exit(f"error: {md} has no frontmatter block")
    open_, body, close = m.group(1), m.group(2), m.group(3)

    # Drop any prior top-level stamp, then re-add at the top of the block (idempotent).
    kept = [ln for ln in body.splitlines()
            if not re.match(r"^(source|source-path|ref):", ln)]
    stamp = [f"source: {source}", f"source-path: {source_path}", f"ref: {ref}"]
    md.write_text(open_ + "\n".join(stamp + kept) + close + text[m.end():])

    print(f"stamped {md}")
    for line in stamp:
        print(f"  {line}")
    print(f"\nreview, then:  git commit -am 'release {ref}'  &&  git tag {ref}")


if __name__ == "__main__":
    main()
