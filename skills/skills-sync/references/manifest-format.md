# skills.json — manifest format

The manifest declares which skills a project borrows, from where, at what
version. It lives at the project root.

```json
{
  "targets": [".claude/skills"],
  "skills": [
    {
      "name": "setup-llm-wiki",
      "source": "https://github.com/ORG/skills-repo.git",
      "path": "skills/setup-llm-wiki",
      "ref": "v1.0.0",
      "hash": "sha256:PINNED-CONTENT-HASH"
    },
    {
      "name": "a11y-audit",
      "source": "https://github.com/ORG/a11y-skills.git",
      "path": "skills/a11y-audit",
      "ref": "v2.3.1",
      "hash": "sha256:PINNED-CONTENT-HASH"
    }
  ]
}
```

## Fields

- **targets** — the agent skills folders to install into. Add one entry
  per agent runtime the project uses (the format is standard; only the
  scanned folder varies by agent, e.g. `.claude/skills`, `.cursor/skills`).
- **name** — the skill's folder name. Stable across versions; versions live
  in refs and tags, never in folder names.
- **source** — git URL of the repo holding the skill.
- **path** — path to the skill's folder within that repo (repos may hold
  several skills).
- **ref** — the pinned git ref: a release tag or a full commit SHA. Never a
  branch name — branches move.
- **hash** — sha256 content hash of the skill folder at that ref, as printed
  by `install.py`. This is what guarantees the file that runs is the file
  that was reviewed. Leave it out on first add; `install.py` prints the hash
  to pin. Refuse to run skills whose hash does not match.

## Origin frontmatter

The release process writes `source`, `source-path`, and `ref` keys into each
SKILL.md's frontmatter (the skill format allows extra frontmatter keys). `ref`
is the exact tag or SHA the release was cut at — written verbatim so it feeds
the manifest's `ref` field and stays checkout-able; it is not the human-facing
`metadata.version` (which may read `0.1.0` while the tag is `v0.1.0`). Skills
that carry this frontmatter can be picked up by `install.py init` to create a
manifest from scratch — registering themselves and any other such skills
already on disk, each pin verified against its stamped ref before it lands.
Write it at release time, never by hand.

## Skills declaring dependencies

A skill may propose additions to `skills.json` — e.g. a one-shot that adds the
operation skills it sets up (`setup-llm-wiki` adding `llm-wiki-ingest` and
`llm-wiki-lint` at its own source and ref). The skill only edits the manifest, as a
reviewable change; fetching, verifying, and installing stay `skills-sync`'s
job. If there's no manifest, the declaring skill offers `skills-sync` rather
than creating one itself.

## One-shot skills

One-shot skills (like `setup-llm-wiki`) stay in the manifest only until they've
run. After a successful run, remove the entry and delete the installed copy —
the conventions it seeded into `raw/` (and their wiki docs) remain.
