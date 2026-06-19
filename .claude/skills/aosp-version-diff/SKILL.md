---
name: aosp-version-diff
description: >-
  Compare two AOSP releases (e.g. android-16 vs android-17) and turn the diff
  into a written report of the important platform changes. Use this whenever the
  user wants to know what changed between two Android/AOSP versions, generate an
  "Android N updates" report or appendix, diff two repo manifests/branches, find
  newly-added projects or new code modules in a version, or fill gaps in an
  existing version-changes report. Triggers on requests like "what's new in
  android 17", "diff android16 to android17", "find modules added in the new
  release that my report is missing", or "compare two AOSP branches with commit
  history". Reuses the repo's tools/manifest_snapshot.py rather than reinventing
  the diff, and uses an agent team to source-verify and append missing modules.
metadata:
  author: utzcoz
---

# AOSP version diff → changes report

This skill captures a proven, two-phase workflow for answering "what changed
between two AOSP releases, and which of it matters?" It leans on an existing
tool (`tools/manifest_snapshot.py`) for the mechanical diff, and on a small
agent team for the judgement-heavy parts: deciding what's significant, verifying
claims against real source, and finding modules a first draft missed.

The guiding principle throughout is **accuracy over coverage**: a smaller report
whose every claim is checked against the actual Android source beats a broad one
that paraphrases commit subjects. Every architectural claim cites a real path you
opened.

## When to use which phase

- **Phase 1 — Compare** (`references/tooling.md`): you have (or can produce) the
  two releases and want the raw per-repository changeset, then a curated report.
- **Phase 2 — Gap-append** (`references/gap-analysis.md`): a report already
  exists and you want to find and add the important modules it missed — both
  newly-*added* projects and new code *modules introduced inside moved repos*.

Phase 2 is the "backend" that keeps a report honest: a single drafting pass
almost always misses modules, because the changeset is huge (hundreds of moved
repos, dozens of added projects) and a drafter naturally anchors on the
headline features. Phase 2 systematically diffs "what the changeset added"
against "what the report mentions" and closes the difference.

## Prerequisites

- The repo's `tools/manifest_snapshot.py` (subcommands `snap`, `history`,
  `compare`, `compare-history`). Read `references/tooling.md` for exact commands,
  flags, and the gotchas that bite (ref-name filenames, LFS, non-UTF-8 commit
  subjects, the snapshot-vs-history coherence trap).
- A local AOSP checkout (e.g. `$ANDROID_BUILD_TOP`) synced to whichever
  release you're analyzing. The tools are **read-only** against it; never write
  into the AOSP tree.
- For the source-verification and gap phases: the ability to spawn subagents
  (cap at 10 concurrent). Without subagents, the same steps run inline, slower.

## Phase 1: produce the changeset and the report

1. **Capture each side.** With the checkout synced to the older release, run
   `history` (full per-repo commit log) and/or `snap` (pinned manifest). Re-sync
   to the newer release and repeat. The two large `.txt` history files and the
   snapshots are the raw material. See `references/tooling.md` for the commands
   and which artifact feeds which comparison.

2. **Diff.** `compare` diffs two snapshots; `compare-history` diffs two history
   files plus a newer-side snapshot (use this when the two history files were
   captured at different sub-revisions — it keeps the project list and the commit
   lists coherent). Both write a per-comparison directory under
   `manifest-snapshots/_compare/<old>-to-<new>/` containing `report.md`
   (navigator), `changes.txt` (per-repo commit lists), and `added-removed.txt`.

3. **Curate into a report.** Organize by subsystem, then by change category
   (New projects / New modules / Architecture changes / Notable integrations).
   The hard part is *selection*: hundreds of repos moved, but most of the signal
   is in a handful. Apply a scope policy — see `references/gap-analysis.md` §Scope
   — and treat `external/*` dependencies as **integration signals**: describe how
   and *why* a new external dep was pulled in (what platform capability it
   enables, what consumes it), never its internal code. A new `external/openxr-sdk`
   means "XR runtime support arrived", not "here's OpenXR's changelog".

For a large report, fan out per-subsystem analyst agents (one per book Part /
subsystem), each reading the actual source for its repos and writing a cited
section, then synthesize under a size budget. Keep a verification pass (below).

## Phase 2: find and append the modules the report missed

This is the backend that makes the report trustworthy. Full procedure with the
exact extraction commands and agent prompts is in `references/gap-analysis.md`.
The shape:

1. **Build the candidate set deterministically.** Extract every *added* project
   from the changeset's `report.md`, subtract the ones already named in the
   existing report. Separately, scan high-signal *moved* repos for new
   modules/services/directories introduced within them (the changeset's
   `changes.txt` "NEW" commit subjects are the cheap index). This second pass
   matters because the biggest gaps hide inside repos that merely "moved" —
   a new service added to `frameworks/base` won't show up as an added *project*.

2. **Triage with an agent team (≤10).** Partition candidates by area, one agent
   per batch. Each agent: confirms a candidate is genuinely absent from the
   report, reads the real Android source to learn what it is, and classifies it —
   `part` (subsystem), `category` (New project / New module / Notable
   integration), and `relevance` (add-worthy vs out-of-scope, with a reason).
   Ruthlessly drop noise: empty placeholder repos, pure relocations, routine
   third-party uprevs, prebuilts, toolchains, vendor/board.

3. **Curate, then append concisely.** "Reduce gaps": add only the high-signal
   findings. Each addition is a tight, source-cited bullet. Mind the report's
   size budget — if appending pushes it over, trim lower-value existing prose
   (never citations or diagrams) to make room.

4. **Review → fix loop until clean.** Spawn independent verifiers (not the
   authors) to adversarially check every new claim against source. Fix what they
   find. Repeat until a round surfaces no new material issue. This loop is the
   point — newly-written content is exactly where fabricated paths and
   off-by-a-bit symbol names creep in.

## Output conventions

- Real source paths in every claim; verify each path exists in the analyzed tree.
- If the report is a book chapter/appendix, follow the book's own rules
  (`book/CLAUDE.md` + `book-writer` skill): manual section numbering, a
  descriptive heading before each Mermaid block, quoted Mermaid labels, no
  epigraph, and a size ceiling. Validate diagrams with `./serve.sh png <file>`
  (require `errors=0`) and register the file in `mkdocs.yml` nav + `llms.txt`.
- Persist working state (scope, candidate lists, findings, drafts) under a
  gitignored scratch dir (e.g. `.superpowers/<topic>/`) so a long run is
  resumable and the agent team's findings survive.

## Gotchas worth knowing up front

These cost real time the first time around; `references/tooling.md` has detail.

- The manifest's default revision can be a **tag** (`refs/tags/android-16.0.0_r4`).
  Slashes in it must be slugified or they become directories in output paths.
- `git log` output is **not** guaranteed UTF-8; decode with `errors="replace"`.
- The android-16 *snapshot* in git history and the android-16 *history file* may
  be different sub-revisions (qpr2 vs r4). Don't mix a snapshot's SHAs with a
  different revision's commit lists — use `compare-history` so the sides stay
  coherent.
- The big `history`/`compare` outputs are large; track them with **git LFS** and
  keep generated `_compare/`/`_history/` gitignored. Pushing the LFS objects can
  SIGPIPE after a successful upload — retry; the objects are already server-side
  so the retry just moves the ref.
