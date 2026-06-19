# Phase 1 tooling: `tools/manifest_snapshot.py`

The repo ships a stdlib-only, read-only tool that does the mechanical diff. Reuse
it — don't hand-roll `git log` loops. Run everything from the book repo root
(`.../aosp-dev-book/book`); the tool finds the AOSP checkout via `--aosp-root`,
`$AOSP_ROOT`, or by walking up to a `.repo/`.

All four subcommands are read-only against the AOSP tree (they only run
`repo manifest -r` and `git log`); they never write inside `.repo/`.

## The four subcommands

### `snap` — pin the current manifest
```
python3 tools/manifest_snapshot.py snap --aosp-root $ANDROID_BUILD_TOP [--no-prompt]
```
Writes `manifest-snapshots/<branch>/<date>/{manifest.xml,metadata.json}` with every
`<project>` pinned to its current HEAD SHA. `--label`/`--notes` annotate it;
`--no-prompt` skips the interactive label/notes prompts. This is fast (one
`repo manifest -r`); it does **not** read commit history.

### `history` — full per-repo commit log for ONE version
```
python3 tools/manifest_snapshot.py history --aosp-root $ANDROID_BUILD_TOP
```
Writes one flat file `manifest-snapshots/_history/<branch>_<date>.history.txt`:
a header, a "Skipped (shallow/ignored)" list, then one section per repo with its
SHA and the full `<sha> <subject>` log. This walks `git log` across every
non-shallow repo, so it is **slow** (minutes) and the file is **large** (hundreds
of MB on a full tree). It prints per-repo progress to stderr; `--no-progress`
silences it. Shallow projects (clone-depth or a live `.git/shallow`) and
`--ignore-glob`/`ignore-globs.txt` paths are skipped (listed, not logged).

### `compare` — diff two snapshots
```
python3 tools/manifest_snapshot.py compare \
    manifest-snapshots/<branchA>/<dateA> \
    manifest-snapshots/<branchB>/<dateB> \
    --aosp-root $ANDROID_BUILD_TOP
```
Classifies projects (added/removed/moved/unchanged), and for moved ones runs
`git log old..new` against the local `.repo/projects/<path>.git`. Commits come
from local object stores — no network; if a SHA is unreachable locally it
degrades to a Googlesource link.

### `compare-history` — diff two history files + a newer snapshot
```
python3 tools/manifest_snapshot.py compare-history \
    --history-a manifest-snapshots/_history/<old>.history.txt \
    --snapshot-b manifest-snapshots/<newbranch>/<date> \
    --history-b manifest-snapshots/_history/<new>.history.txt \
    --aosp-root $ANDROID_BUILD_TOP
```
Per moved repo it set-diffs the two history files' commit-SHA lists to produce
"new in B" and "dropped from A". The newer snapshot supplies the authoritative
project list + groups; the two history files supply the commit lists. Use this
when your two history files were captured at different sub-revisions (see the
coherence gotcha below) — it keeps the project set and the commit lists aligned.

## Output layout

`compare` and `compare-history` both write a per-comparison directory:
```
manifest-snapshots/_compare/<oldrev>-to-<newrev>/
  report.md           navigator: summary counts, moved-by-module-group, skipped, added/removed tables
  changes.txt         per-repo commit lists (compare-history: NEW / DROPPED blocks)
  added-removed.txt   added/removed projects with full inline history
  analysis-prompt.txt (compare only) an LLM prompt framing the changelog
```
`<oldrev>`/`<newrev>` have ref prefixes stripped and slashes flattened.

`report.md` is the navigator you start from. It is small (~hundreds of KB) and
safe to read whole. `changes.txt` / `added-removed.txt` are large (tens of MB) —
**never read them whole**; `grep` the specific repo section:
```
grep -n -A 60 '^frameworks/base   (' manifest-snapshots/_compare/<dir>/changes.txt | head -80
```
The per-repo section header is `<path>   (<name>)`, followed by a `NEW (n):`
block (and `DROPPED (m):` for compare-history).

## Gotchas (each cost real time the first time)

- **Ref-name filenames.** A manifest's `default revision` is often a tag like
  `refs/tags/android-16.0.0_r4`. The tool slugifies it (`_revision_slug`) so the
  slashes don't become directories — if you extend the tool, reuse that helper
  for any new output path.
- **Non-UTF-8 commit subjects.** Old/imported AOSP commits carry raw Latin-1
  bytes; `git log` output is arbitrary bytes. Decode subprocess output with
  `errors="replace"` or a strict UTF-8 decode crashes mid-run.
- **Snapshot vs history coherence.** The android-16 *snapshot* recoverable from
  git and the android-16 *history file* you generated may be different
  sub-revisions (e.g. qpr2 vs r4) with different per-repo SHAs. Mixing one's
  SHAs with the other's commit lists is incoherent. Prefer `compare-history`
  (history for both sides' commits, newer snapshot only for the project list).
- **Size + LFS.** `history` files (~hundreds of MB) and the big compare `.txt`
  outputs should be tracked with **git LFS** (`.gitattributes`: `*.history.txt`
  and `_compare/**/changes.txt` / `added-removed.txt` → `filter=lfs`), with the
  generated `_compare/`/`_history/` dirs gitignored unless you deliberately
  commit a specific output. Largest non-LFS blob must stay < 100 MB (GitHub hard
  limit). Pushing LFS objects can drop the SSH connection with `EXIT=141`
  (SIGPIPE) *after* a successful upload — the ref didn't move but the object is
  server-side, so just retry the push; it's fast the second time.
- **Don't `repo gc` between snapshots.** For full-depth repos, switching the
  checkout to the newer release keeps the older SHAs locally so `compare` can log
  `old..new` offline — but a `repo gc`/prune in between prunes them, and those
  repos degrade to Googlesource links.

## If you need to extend the tool

It has a unit-test suite (`tools/test_manifest_snapshot.py`, stdlib `unittest`).
Add a failing test first, keep it stdlib-only and read-only, reuse the existing
helpers (`index_history`, `read_repo_commit_pairs`, `diff_commit_lists`,
`skip_reason`, `_revision_slug`, `emit_progress`), and run
`python3 tools/test_manifest_snapshot.py` before and after.
