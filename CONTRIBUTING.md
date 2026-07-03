# Contributing / maintaining

This is the maintainer's guide for the **skills-sync** skill. End users don't need
any of this — see [README.md](./README.md) for installing and using the skill.

## Repository layout

```
.
├── skills/
│   └── skills-sync/
│       ├── SKILL.md          # the skill — single source of truth
│       └── …                 # scripts/, references/, knowledge/ as the skill needs
├── release.sh                # cut a release: stamp → commit → tag → build (CLI path)
├── build.sh                  # builds the distributable .plugin from the skill
├── stamp.py                  # writes origin frontmatter at release time
├── .gitignore
├── README.md                 # user-facing
└── CONTRIBUTING.md           # this file
```

## Editing the skill

`skills/skills-sync/SKILL.md` is the single source of truth; supporting files live
beside it. A few rules keep the bundle buildable:

- **Version lives in `metadata.version`** — SemVer, quoted (e.g. `"0.1.0"`).
  It is the human-facing version; the release *tag* is what gets pinned (below).
- **Code fences must stay balanced.** `build.sh` validates this before zipping.
- **No vault wikilinks in frontmatter.** Keep `[[…]]` out of the frontmatter
  block — `build.sh` rejects it.

## Building the .plugin

```bash
./build.sh                 # -> dist/skills-sync.plugin
./build.sh /path/to/out    # -> writes the .plugin into /path/to/out
```

`build.sh` reads the version from `metadata.version` (so the plugin manifest
can never drift from the skill), generates `.claude-plugin/plugin.json`,
validates the bundle (kebab-case name, semver version, present `SKILL.md`,
balanced fences, no vault wikilinks), and zips the whole skill folder to a
`.plugin`. The output is gitignored.

> Why a script and not copy-paste commands? It is the single source of truth for
> *how to build*, so the docs and the build can't disagree.

## Stamping origin frontmatter

An installed copy traces back to its source through three frontmatter keys —
`source`, `source-path`, `ref` — read by `skills-sync` (see that skill's
`references/manifest-format.md`). `stamp.py` writes them at release time so you
never hand-edit them:

```bash
./stamp.py v0.1.0          # stamps source (origin URL), source-path, ref=v0.1.0
```

`ref` is the exact tag the release is cut at — written verbatim so it feeds a
manifest's `ref` field and stays checkout-able. It is **not** the human-facing
`metadata.version` (which may read `0.1.0` while the tag is `v0.1.0`).
`stamp.py` refuses to run on a dirty tree, so stamping is always one reviewable
step: stamp → review → commit → tag.

## Versioning

The skill follows [SemVer](https://semver.org/) + [Conventional
Commits](https://www.conventionalcommits.org/). Version history lives in git
(tags + release notes); the file carries only `metadata.version`. `0.x` while
it's a maturing tool.

## Releasing a new version

Bump `metadata.version` in `skills/skills-sync/SKILL.md` to the version you're
releasing (SemVer) and commit any pending work so the tree is clean. Then
`release.sh` runs the whole local sequence — stamp → review → build → commit →
tag. It does **local work only**: it never pushes and never creates the GitHub
Release, so the outward-facing steps stay in your hands.

```bash
./release.sh v0.1.0            # stamp, show the diff, prompt, then build + commit + tag
#   -m "…"                     custom commit/tag message
#   -y                         skip the review prompt
#   --skip-version-check       allow metadata.version != tag

# when ready (outward-facing):
git push --follow-tags
gh release create v0.1.0 dist/skills-sync.plugin --title "skills-sync v0.1.0" --generate-notes
```

It refuses to run on a dirty tree, without an `origin` remote, if the tag
already exists, or if `metadata.version` doesn't match the tag (bump it first,
or pass `--skip-version-check`).
