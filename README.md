# Skills Sync Agent Skill

Install, update and verify the skills you use in a project across different 
devices and team members. skills-sync makes sure you're always using the same
version, from the same source.

**Version:** 0.1.0 · **License:** Artistic-2.0

> Maintaining or releasing this skill? See [CONTRIBUTING.md](./CONTRIBUTING.md)
> for the repo layout, build, stamping, and release process.

## What it does

`skills.json` declares which skills a project borrows, from where, at what
version — each entry pinned to a git `ref` and a `sha256` content hash. This
skill acts on that manifest:

- **install** — fetch each skill at its pinned ref, verify its content hash
  against the manifest, and copy it into the project's agent skills folder(s).
  A hash mismatch is refused: the file that runs is the file that was reviewed.
- **update** — report, per skill, the release tags newer than the pinned ref.
  Read-only: it changes nothing; taking an update is a deliberate re-pin.
- **verify** — compare installed copies against the manifest hashes; flag any
  that are missing, unpinned, or a local fork.
- **init** — create a `skills.json` where none exists, from the origin
  frontmatter (`source` / `source-path` / `ref`) that stamped skills carry.
  These are trust-on-first-use pins.
- **list** — show manifest entries and their installed status.

It also copies any conventions a freshly installed skill carries (the docs in
its `knowledge/` folder) into `raw/` for the agent to ingest.

The engine is a Python script — stdlib only, needs `python3` and `git`, no
third-party packages — see
[`skills/skills-sync/scripts/install.py`](./skills/skills-sync/scripts/install.py)
and the manifest reference at
[`skills/skills-sync/references/manifest-format.md`](./skills/skills-sync/references/manifest-format.md).

## Installing

skills-sync is **project-scoped** — it manages one project's `skills.json` and
installs into that project's agent skills folder — so you add it to a project,
not to your agent globally. There's a one-time chicken-and-egg step (it can't
install itself before it exists), so you place it once and then it manages
itself.

**Via agent (recommended)** Point your agent at this repo and ask:

> Install skills-sync from
> https://github.com/tylensthilaire/skill-skills-sync into this project: clone
> it at the latest release tag, copy `skills/skills-sync` into `.claude/skills/`,
> then run its `init` to create `skills.json`.

`init` creates the manifest and self-registers skills-sync from its stamped
origin frontmatter (a trust-on-first-use pin). From then on skills-sync manages
itself and every other skill you add — `install`, `update`, `verify`.

**Manually** The same steps, if you'd rather not hand it to an agent:

```
git clone --branch <latest-tag> https://github.com/tylensthilaire/skill-skills-sync.git
cp -R skill-skills-sync/skills/skills-sync <your-project>/.claude/skills/
cd <your-project>
python3 .claude/skills/skills-sync/scripts/install.py init
```

(Latest tag is on the [Releases](../../releases) page.) `init` also adopts any
other stamped skills already in your skills folder.
