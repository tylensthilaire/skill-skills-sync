---
source: https://github.com/tylensthilaire/skill-skills-sync.git
source-path: skills/skills-sync
ref: v0.1.0
name: skills-sync
description: >-
  Install, verify, and update the pinned skills a project lists in skills.json,
  and copy any conventions those skills carry into raw/ for the agent to
  ingest. Use this
  whenever skills.json is mentioned or present; whenever the user asks to
  install, set up, sync, verify, or update skills; whenever a freshly cloned
  project has a skills manifest but an empty or missing agent skills folder;
  whenever a skill fails to trigger because it isn't installed; and whenever a
  newly installed skill has a knowledge/ directory whose conventions need
  copying into raw/.
license: Artistic-2.0
metadata:
  author: Tylen St Hilaire
  version: "0.1.0"
---

# Skills install

Install the skills a project lists in `skills.json`, check each against its
pin, and copy any conventions they carry (the files in a skill's `knowledge/`)
into `raw/` for the agent to ingest.

Every installed skill is a pinned copy of a source, checked against a content
hash in the manifest — the file that runs is the file that was reviewed. A
locally edited copy is a fork: `verify` flags it, and nothing here silently
overwrites it. Skills not listed in the manifest (e.g. ones the user wrote)
are simply unmanaged, and left alone.

## The manifest

`skills.json` at the project root. Format and a worked example:
`references/manifest-format.md`. Read that file before editing a manifest.

## Commands

The mechanical work is in `scripts/install.py` (needs python3 + git):

```
python3 <this-skill's-folder>/scripts/install.py install [name]   # fetch, verify, install
python3 <this-skill's-folder>/scripts/install.py update  [name]   # report refs newer than the pin
python3 <this-skill's-folder>/scripts/install.py verify  [name]   # installed copies vs manifest hashes
python3 <this-skill's-folder>/scripts/install.py list    [name]   # manifest entries and their status
```

`[name]` is optional: omit it to act on every manifest entry, or pass one
skill's name to act on just that one. Add `--manifest PATH` for a manifest
other than `./skills.json`.

The script prints what it did and any hash to pin; on a hash mismatch it
refuses and says why. `verify` reports each installed copy as `ok`, `modified`
(a local fork), or `missing`. `update` is read-only — it reports newer tags
but changes nothing.

**Manifest present but skills not installed** (e.g. a freshly cloned project):
run `install`.

## After installing: copy conventions into `raw/`

A skill can carry project conventions as files in its own `knowledge/`
directory. For each newly installed or updated skill that has one, copy those
files into the project's `raw/` so the agent ingests them like any other source:

1. **Probe** — does the project have a wiki (`raw/` and `wiki/` present, and
   referenced from AGENTS.md)?
2. **Offer** — if not, offer to install and run `setup-llm-wiki` (add it to
   the manifest if the user agrees). If the user declines a wiki, copy nothing
   — the conventions stay readable inside the skill's own `knowledge/` folder,
   which is a fully supported fallback, not an error.
3. **Check `raw/`** — for each file in the skill's `knowledge/`, look for an
   existing copy in `raw/` with a `from` field naming the same skill:
   - none → copy it in (step 4);
   - present at the same version → nothing to do;
   - present at an older version → this skill owns the file, so replace it with
     the new version (the one allowed exception to raw's immutability), then
     re-ingest.
4. **Copy in, with origin frontmatter** — write each `knowledge/` file into
   `raw/` with frontmatter recording `from` (the skill) and `version` (the
   skill version). Show the change before writing it — a copy into `raw/` is
   reviewable, not silent. Then ingest each into the wiki like any source (see
   `llm-wiki-ingest`): a wiki doc per file, indexed, linked back to the raw file.
5. **Report** — list what was copied, updated, or skipped.

## When there is no manifest

A project without a manifest is fine — it's just unmanaged. This skill owns
creating one; no other skill creates a manifest with its own logic — they offer
this skill instead. Create one the first time a skill needs it.

Run `python3 .../scripts/install.py init`: it creates `skills.json`, registers
this skill from its own origin frontmatter (documented in
`references/manifest-format.md`), and adopts any other skills already in the
skills folder that carry origin frontmatter. Each pin is **verified before it
lands** — the skill is fetched at its stamped `ref` and the manifest pins the
hash of *that* release, so init can never write a (ref, hash) pair the next
`install` would reject. A local copy that differs from its ref is still adopted
(pinned to the release) but flagged as drifted — tell the user to run
`install <name>` to sync it, unless it's a deliberate local fork. A ref that
can't be fetched is skipped, and skills without origin frontmatter are reported;
both are left for the user to pin by hand.

## Updating skills

Checking is automated; taking an update is deliberate. Run `update` (all
entries) or `update <name>` (one) to report, per skill, the release tags newer
than the pinned ref. It's read-only — it rewrites nothing — and it answers the
question "are my skills up to date?".

To take an update, keep the new pin reviewable: bump `ref` in the manifest and
clear its `hash` (a manifest edit — show it first), run `install <name>` (it
prints the new hash to pin), then re-run the copy-into-`raw/` steps above — step
3 replaces the older copy and re-ingests. Never pin a hash you haven't
reviewed; the hash is what vouches that the running file is the reviewed one.

If `verify` reports a skill as `modified`, tell the user plainly: this copy is
a fork. Offer to (a) diff it against the pinned version, (b) restore the pinned
version, or (c) keep the fork — in which case suggest carrying the change at
the source instead.
