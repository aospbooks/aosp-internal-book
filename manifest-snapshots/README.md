# AOSP Manifest Snapshots

Point-in-time, fully-pinned `repo manifest` captures for the AOSP source tree this book documents. Each snapshot resolves every `<project>` to a stable commit SHA so we can later diff two snapshots and see exactly what moved between AOSP releases.

## Directory layout

```
manifest-snapshots/
  <branch>/                            # e.g., android16-qpr2-release/
    <YYYY-MM-DD>/
      manifest.xml                     # pinned manifest from `repo manifest -r`
      metadata.json                    # timestamp, branch, repo version, optional label/notes
  _compare/                            # comparison reports (cross-branch capable)
    <A>__vs__<B>.report.md             # navigator: summary, groups, skipped
    <A>__vs__<B>.changes.txt           # kernel-changelog of moved-project commits
    <A>__vs__<B>.added-removed.txt     # added/removed projects, full history
    <A>__vs__<B>.analysis-prompt.txt   # LLM prompt framing the changelog
  ignore-globs.txt                     # paths to skip in compare (supplements shallow detection)
  README.md                            # this file
```

`_compare/` is a sibling of the per-branch dirs because a comparison can span branches (e.g., last QPR2 snapshot vs. first QPR3 snapshot).

## Taking a snapshot

```bash
python3 tools/manifest_snapshot.py snap
```

The tool walks parent directories looking for `.repo/manifests/default.xml`. Override with `--aosp-root /path/to/aosp` or set `AOSP_ROOT`.

It will prompt for an optional **label** (short tag like `pre-QPR3-cut`) and **notes** (free-form, end with a blank line). Use flags to skip the prompts:

```bash
python3 tools/manifest_snapshot.py snap --label pre-QPR3-cut --notes "Taken right before the QPR3 dev branch was cut."
python3 tools/manifest_snapshot.py snap --no-prompt          # both fields empty
python3 tools/manifest_snapshot.py snap --force               # overwrite today's snapshot
```

The tool **never writes inside `.repo/`** — it only reads `.repo/manifests/default.xml` and shells out to `repo manifest -r -o <target>/manifest.xml` to produce the pinned XML.

## Comparing two snapshots

```bash
python3 tools/manifest_snapshot.py compare \
    manifest-snapshots/android16-qpr2-release/2026-05-12 \
    manifest-snapshots/android17-release/2026-09-01
```

Writes four files to `manifest-snapshots/_compare/`, each prefixed with `<branchA>_<dateA>__vs__<branchB>_<dateB>`:

- `<KEY>.report.md` — navigator: summary counts, moved projects grouped by module group (commit counts + links, no inline commits), the skipped-project list, and added/removed summary tables.
- `<KEY>.changes.txt` — kernel-changelog-style aggregate of every moved project's commits as `<full-sha> <subject>` (`git log --no-merges --pretty=oneline old..new`).
- `<KEY>.added-removed.txt` — projects added or removed between the versions, each with full inline history (fallback Googlesource link if objects are gone).
- `<KEY>.analysis-prompt.txt` — a prompt that frames the changelog for an LLM.

Use `--out-dir DIR` to change where the files land.

**Skipped projects.** Shallow projects (manifest `clone-depth`, or a live `.repo/projects/<path>.git/shallow` marker) can't be diffed across a branch switch, so they're listed under "Skipped" rather than run through `git log`. Add path globs to `manifest-snapshots/ignore-globs.txt` (or pass `--ignore-glob GLOB`, repeatable) to skip more. `--no-skip-shallow` disables the automatic shallow detection; `--ignore-file PATH` points at a different glob file.

Commit lists come from the local `.repo/projects/<path>.git/` object stores via read-only `git log` — no network access. If a SHA is unreachable locally (e.g., comparing very old snapshots after a `repo gc`), that project's entry degrades to a Googlesource compare link.

## The read-only guarantee

Both subcommands are strictly read-only against the AOSP tree:

- `snap` writes only inside `manifest-snapshots/`.
- `compare` only invokes `git --git-dir=… log …` — no `fetch`, `gc`, `commit`, `pack-refs`, or anything that mutates refs/objects.

Tests in `tools/test_manifest_snapshot.py` assert this invariant.
