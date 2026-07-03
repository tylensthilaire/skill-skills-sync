#!/usr/bin/env python3
"""skills-sync: install pinned skills from skills.json.

Commands (NAME is an optional skill name; omit it to act on every entry):
  init             create skills.json where none exists (self-register + adopt, TOFU pins)
  install [NAME]   fetch at the pinned ref, verify hash, copy into targets
  update  [NAME]   report release tags newer than the pinned ref (read-only)
  verify  [NAME]   compare installed copies against manifest hashes
  list    [NAME]   show manifest entries and their installed status

Options:
  --manifest PATH  use a manifest other than ./skills.json

Requires: python3 (stdlib only) + git. No third-party packages.
"""
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_MANIFEST = "skills.json"


def dir_hash(root: Path) -> str:
    """Deterministic content hash of a directory: sha256 over sorted
    (relative-path, file-sha256) pairs. Ignores .git."""
    h = hashlib.sha256()
    files = sorted(
        p for p in root.rglob("*")
        if p.is_file() and ".git" not in p.parts
    )
    for p in files:
        rel = p.relative_to(root).as_posix()
        h.update(rel.encode())
        h.update(b"\0")
        h.update(hashlib.sha256(p.read_bytes()).hexdigest().encode())
        h.update(b"\n")
    return "sha256:" + h.hexdigest()


def load_manifest(path: str) -> dict:
    mp = Path(path)
    if not mp.exists():
        sys.exit(f"error: no manifest at {mp.resolve()}")
    m = json.loads(mp.read_text())
    if not m.get("skills"):
        sys.exit("error: manifest has no 'skills' entries")
    m.setdefault("targets", [".claude/skills"])
    return m


def select(m: dict, name: str) -> list:
    """Entries to act on: all of them, or just the one named. Exits with the
    known names if NAME matches nothing."""
    if name is None:
        return m["skills"]
    matches = [e for e in m["skills"] if e["name"] == name]
    if not matches:
        known = ", ".join(e["name"] for e in m["skills"]) or "(none)"
        sys.exit(f"error: no skill named {name!r} in the manifest (have: {known})")
    return matches


def fetch(entry: dict, workdir: Path) -> Path:
    """Clone entry's source at its pinned ref; return path to the skill folder."""
    dest = workdir / entry["name"]
    subprocess.run(
        ["git", "clone", "--quiet", "--filter=blob:none", entry["source"], str(dest)],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(dest), "checkout", "--quiet", entry["ref"]],
        check=True,
    )
    skill_dir = dest / entry.get("path", ".")
    if not (skill_dir / "SKILL.md").exists():
        sys.exit(f"error: {entry['name']}: no SKILL.md at {entry.get('path', '.')} in {entry['source']}@{entry['ref']}")
    return skill_dir


def cmd_install(manifest_path: str, name: str = None) -> None:
    m = load_manifest(manifest_path)
    unpinned = []
    with tempfile.TemporaryDirectory() as tmp:
        for entry in select(m, name):
            name = entry["name"]
            skill_dir = fetch(entry, Path(tmp))
            actual = dir_hash(skill_dir)
            pinned = entry.get("hash")
            if pinned and actual != pinned:
                sys.exit(
                    f"REFUSED: {name}: content hash mismatch at {entry['ref']}\n"
                    f"  manifest: {pinned}\n  fetched:  {actual}\n"
                    f"The fetched skill is not the one that was reviewed. Investigate before installing."
                )
            if not pinned:
                unpinned.append((name, actual))
            for target in m["targets"]:
                dest = Path(target) / name
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(skill_dir, dest, ignore=shutil.ignore_patterns(".git"))
                print(f"installed  {name}  ->  {dest}  ({entry['ref']})")
    if unpinned:
        print("\nUnpinned entries — add \"hash\": \"...\" to each manifest entry:")
        for name, h in unpinned:
            print(f'  {name}  ->  "hash": "{h}"')


def cmd_verify(manifest_path: str, name: str = None) -> int:
    m = load_manifest(manifest_path)
    worst = 0
    for entry in select(m, name):
        name, pinned = entry["name"], entry.get("hash")
        for target in m["targets"]:
            dest = Path(target) / name
            if not dest.exists():
                print(f"missing    {name}  ({dest})")
                worst = max(worst, 2)
            elif not pinned:
                print(f"unpinned   {name}  ({dest})  installed hash: {dir_hash(dest)}")
                worst = max(worst, 1)
            elif dir_hash(dest) == pinned:
                print(f"ok         {name}  ({dest})")
            else:
                print(f"MODIFIED   {name}  ({dest})  — local copy is a fork of {entry['ref']}")
                worst = max(worst, 1)
    return worst


def cmd_list(manifest_path: str, name: str = None) -> None:
    m = load_manifest(manifest_path)
    for entry in select(m, name):
        pin = entry.get("hash", "UNPINNED")[:19]
        print(f"{entry['name']:<24} {entry['ref']:<12} {pin}  {entry['source']}")


def version_tuple(ref: str):
    """Best-effort semver from a tag like `v1.2.3` / `1.2` -> (1, 2, 3) / (1, 2).
    Returns None for anything that isn't a version tag — in particular a commit
    SHA (hex, no dots), which must never be read as a version."""
    if re.fullmatch(r"[0-9a-f]{7,40}", ref):
        return None
    m = re.match(r"v?(\d+(?:\.\d+)*)", ref)
    return tuple(int(x) for x in m.group(1).split(".")) if m else None


def remote_tags(source: str) -> list:
    """Tag names at a remote, annotated-tag `^{}` peel lines collapsed by --refs."""
    out = subprocess.run(
        ["git", "ls-remote", "--tags", "--refs", source],
        check=True, capture_output=True, text=True,
    ).stdout
    prefix = "refs/tags/"
    return [
        line.split("\t", 1)[1][len(prefix):]
        for line in out.splitlines()
        if "\t" in line and line.split("\t", 1)[1].startswith(prefix)
    ]


def cmd_update(manifest_path: str, name: str = None) -> None:
    """Report, per selected entry, any release tags newer than the pinned ref.
    Read-only: takes no update and rewrites nothing. To take one, bump `ref`,
    clear `hash`, and re-run `install` so the new hash is reviewed before it's
    pinned."""
    m = load_manifest(manifest_path)
    for entry in select(m, name):
        pinned = entry["ref"]
        try:
            tags = remote_tags(entry["source"])
        except subprocess.CalledProcessError:
            print(f"{entry['name']:<24} ERROR      could not reach {entry['source']}")
            continue
        versioned = sorted(
            (t for t in tags if version_tuple(t) is not None), key=version_tuple)
        pinned_ver = version_tuple(pinned)
        if pinned_ver is None:
            latest = versioned[-1] if versioned else "(no version tags)"
            print(f"{entry['name']:<24} {pinned}  pinned to a ref; newest tag: {latest}")
        else:
            newer = [t for t in versioned if version_tuple(t) > pinned_ver]
            if newer:
                print(f"{entry['name']:<24} {pinned}  ->  {', '.join(newer)}")
            else:
                print(f"{entry['name']:<24} {pinned}  up to date")


def read_origin(skill_dir: Path) -> dict:
    """Read the origin frontmatter (source/source-path/ref) from a SKILL.md.
    `ref` is the exact git tag or SHA the release was cut at (checkout-able as
    written) — distinct from the human-facing metadata.version. Returns {} if
    the skill has none."""
    md = skill_dir / "SKILL.md"
    if not md.exists():
        return {}
    lines = md.read_text().splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    origin = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        for key in ("name", "source", "source-path", "ref"):
            if line.startswith(key + ":"):
                origin[key] = line.split(":", 1)[1].strip().strip("'\"")
    return origin if "source" in origin else {}


def cmd_init(manifest_path: str) -> None:
    """Create skills.json where none exists: self-register from this skill's
    own origin frontmatter, then adopt any other skills that have it already
    present in the default target folder. Adopted pins are trust-on-first-use —
    they pin the copy already on disk, not an independently reviewed one."""
    mp = Path(manifest_path)
    if mp.exists():
        sys.exit(f"error: {mp} already exists — nothing to init")
    target = Path(".claude/skills")
    entries, no_origin, needs_ref = [], [], []
    own_dir = Path(__file__).resolve().parent.parent
    candidates = [own_dir]
    if target.exists():
        candidates += [d for d in sorted(target.iterdir())
                       if d.is_dir() and d.resolve() != own_dir.resolve()]
    seen = set()
    for d in candidates:
        origin = read_origin(d)
        name = origin.get("name", d.name)
        if name in seen:
            continue
        seen.add(name)
        if not origin:
            if (d / "SKILL.md").exists():
                no_origin.append(d.name)
            continue
        ref = origin.get("ref")
        if not ref:
            # Has origin frontmatter but no checkout-able ref — don't invent
            # one; a bogus ref would only fail the next `install`. Flag it.
            needs_ref.append(name)
            continue
        entries.append({
            "name": name,
            "source": origin["source"],
            "path": origin.get("source-path", "."),
            "ref": ref,
            "hash": dir_hash(d),
        })
    mp.write_text(json.dumps(
        {"targets": [str(target)], "skills": entries}, indent=2) + "\n")
    print(f"created {mp} with {len(entries)} entr{'y' if len(entries)==1 else 'ies'} (trust-on-first-use pins)")
    for e in entries:
        print(f"  registered  {e['name']}  {e['ref']}")
    for n in no_origin:
        print(f"  skipped     {n}  (no origin frontmatter — add it to the manifest by hand)")
    for n in needs_ref:
        print(f"  skipped     {n}  (origin frontmatter has no ref — pin its tag/SHA in the manifest by hand)")


def parse_rest(rest: list):
    """A command's trailing args: an optional skill NAME and an optional
    --manifest PATH. Returns (name, manifest_path)."""
    name, manifest, i = None, DEFAULT_MANIFEST, 0
    while i < len(rest):
        a = rest[i]
        if a in ("--manifest", "-m"):
            i += 1
            if i >= len(rest):
                sys.exit("error: --manifest needs a path")
            manifest = rest[i]
        elif a.startswith("-"):
            sys.exit(f"error: unknown option {a!r}")
        elif name is None:
            name = a
        else:
            sys.exit(f"error: unexpected argument {a!r}")
        i += 1
    return name, manifest


def main() -> None:
    argv = sys.argv[1:]
    cmd = argv[0] if argv else "install"
    name, manifest = parse_rest(argv[1:])
    if cmd == "init":
        if name:
            sys.exit("error: init takes no skill name")
        cmd_init(manifest)
    elif cmd == "install":
        cmd_install(manifest, name)
    elif cmd == "update":
        cmd_update(manifest, name)
    elif cmd == "verify":
        sys.exit(cmd_verify(manifest, name))
    elif cmd == "list":
        cmd_list(manifest, name)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
