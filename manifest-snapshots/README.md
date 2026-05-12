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
    <A-branch>_<A-date>__vs__<B-branch>_<B-date>.md
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

The report is written to `manifest-snapshots/_compare/<A>__vs__<B>.md`. Use `--out FILE` to send it elsewhere. The report contains:

- A summary table (added / removed / moved / unchanged project counts; total commits across moved projects)
- A per-module-group section: every moved project appears under **every group** its manifest entry lists, with the `git log --oneline --no-merges old..new` output inline plus a Googlesource compare link
- Added/Removed tables at the bottom

Commit lists come from the local `.repo/projects/<path>.git/` object stores via read-only `git log` — no network access. If either SHA is unreachable locally (e.g., comparing very old snapshots after a `repo gc`), the project's commit list is replaced with a link to the Googlesource compare page.

## The read-only guarantee

Both subcommands are strictly read-only against the AOSP tree:

- `snap` writes only inside `manifest-snapshots/`.
- `compare` only invokes `git --git-dir=… log …` — no `fetch`, `gc`, `commit`, `pack-refs`, or anything that mutates refs/objects.

Tests in `tools/test_manifest_snapshot.py` assert this invariant.
