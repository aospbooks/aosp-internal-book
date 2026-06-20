---
name: aosp-book-polish
description: >-
  Update or polish the AOSP Internals reference book (the chapters at the repo
  root -- NN-slug.md -- plus the appendices and the generated agents/ Part-skills)
  so it is accurate and current for a newly-synced or newer AOSP/Android source
  tree. Use this whenever the user says anything like "polish the book for
  Android NN", "update the reference book to the new AOSP version", "the AOSP
  source got re-synced, bring the book up to date", "deep-rewrite the chapters
  against the new source", or -- importantly -- "cover the new Android
  modules/projects in the book". It drives a resumable, changeset-prioritized,
  per-chapter convergent deep-rewrite with an agent-team accuracy + Mermaid
  review loop, and MANDATORILY runs a gap analysis that finds newly-added
  modules/projects and folds them into existing chapters (or adds new
  chapters/Parts only by an explicit threshold). Trigger it even when the user
  only says "update the book for the new Android" without naming this process,
  and even when they only want the new-modules part.
---

# AOSP Book Polish

Bring the AOSP Internals book into sync with a newer AOSP source tree:
deep-rewrite existing chapters for accuracy, append new-feature content where a
subsystem changed, and — always — **find newly-added modules/projects and make
sure the book covers them** (fold into an existing chapter first; add a new
chapter/Part only when a threshold is met).

This is a large, multi-`/goal`-run, agent-team job. It is built to be
**resumable** and **convergent**: each chapter is rewritten then reviewed until
two consecutive clean rounds, and durable state lets a fresh run pick up where
the last stopped.

## When to use

- The local AOSP checkout (its path supplied to you as a parameter, usually
  `androidNN-release`) was synced to a newer version and the book should reflect it.
- The user asks to update/polish the book, deep-rewrite chapters, or
  specifically to **cover newly-added modules** (the mandatory Phase C below).
- Pairs with the **`aosp-version-diff`** skill: that skill produces the 16→17
  style changeset (`manifest-snapshots/_compare/<A>-to-<B>/`) this skill consumes.

If there is no changeset yet, run `aosp-version-diff` first (or
`tools/manifest_snapshot.py compare`) — the changeset drives prioritization and
the new-module gap analysis.

## Inputs

- **AOSP source** — the AOSP checkout root, **supplied as a parameter** (e.g. in
  the task prompt); READ-ONLY. Never write into it, and never hardcode its path.
- **Changeset** — `manifest-snapshots/_compare/<old>-to-<new>/`: `report.md`
  (navigator + per-repo `new`/`dropped` counts), `changes.txt` (per-repo NEW
  commits — large, grep per repo, never read whole), `added-removed.txt` (added
  / removed projects — the seed for Phase C).
- **Book conventions** — `book/CLAUDE.md` (the writing rules; these are
  non-negotiable), `.claude/skills/book-writer/SKILL.md` (chapter structure +
  Mermaid syntax), `agents/_content/manifest.toml` (Part → chapter mapping),
  existing chapters as style exemplars.
- **The Android-NN appendix** (e.g. `D-appendix-android-17-updates.md`) — a
  curated map of the new version's changes; a per-chapter checklist of what to
  fold in, and the candidate universe for the Phase C gap analysis.

## The five hard invariants (never violate)

These protect book integrity during autonomous rewrites. Full detail in
`references/invariants.md` — read it before editing any chapter.

1. **Chapter identity is immutable** — filename and the `# Chapter N: Title`
   line (number AND title) never change. Only body content changes.
2. **Manual section numbering** (`## N.1`, `### N.1.2`) is preserved, monotonic,
   **no duplicates**. Terminal structure stays "Try It" then "Summary" (an
   optional key-files table may follow Summary). No epigraph under the title.
3. **Mermaid** follows CLAUDE.md rules and must pass `./serve.sh png <chapter>`
   with `errors=0` — CI does NOT validate Mermaid, so this gate is the only
   backstop. Also eyeball each diagram for overflow/overlap and architectural
   correctness.
4. **Real source citations** — every architectural claim cites a repo-relative
   AOSP path that exists in the new tree. **Never** put a local absolute or
   home-relative path (`/home/...`, `/Users/...`, `~/...`) or a username in
   chapter text — repo-relative AOSP paths only.
5. **Per-chapter backup before rewriting** — copy to
   `.superpowers/book-polish/backups/<slug>.bak.md` (once; never overwrite) so a
   bad rewrite is diffable/restorable.

## Workflow

```
Phase A  Prioritize        (once) rank chapters by changeset signal -> queue.json
Phase B  Per-chapter loop  deep-rewrite + agent-team review to convergence
Phase C  New modules       (MANDATORY) gap analysis -> fold first, new chapter by threshold
Phase D  Bookkeeping+gates  regenerate skills, build, leak-sweep; user commits
```

Run Phase B over the queue and Phase C for the leftovers; they share the same
per-chapter convergent loop and the same gates. Checkpoint durable state after
every step so a fresh `/goal` run resumes.

### Phase A — Prioritize (once)

Map each in-scope subsystem to its chapter(s) via `manifest.toml`, rank chapters
by 16→17-style signal (sum of NEW commits across the chapter's repos + count of
new modules touching it), and write `queue.json` (highest-priority first). The
most valuable chapters then land first even if a run stops early. Initialize
`state.json` with every chapter `pending`. See `references/per-chapter-loop.md`.

### Phase B — Per-chapter convergent polish

For each chapter, in priority waves (≤ the agent cap): back it up, deep-rewrite
the body for accuracy against the new source + append new-feature sections
(before "Try It"), then run an **independent** agent-team review (accuracy +
Mermaid + structure-lint), fix the material findings, and repeat until **two
consecutive clean rounds**. One author agent per file (never two agents editing
the same file at once). Full procedure, agent roles, and the gate batch script
in `references/per-chapter-loop.md`.

### Phase C — Newly-added modules/projects (MANDATORY)

This phase is required even when Phase B looks done — new modules are easy to
miss because they have no existing chapter. **Always run it.** The full
procedure is in `references/new-modules.md`. In brief:

1. **Gap analysis (in a subagent)** — two candidate sets, see
   `references/new-modules.md`:
   - **(A) changeset-driven** (version bump): the *added* projects (changeset
     `added-removed.txt` + the new-version appendix's enumerated new modules).
   - **(B) whole-tree sweep** (when asked to "read across the whole source and
     find what's left"): enumerate EVERY project from `<aosp-root>/.repo/project.list`
     and grep each path + last segment across `[0-9][0-9]-*.md`; keep in-scope
     platform roots, drop noise (`external/`, `prebuilts/`, `vendor/`, `device/`,
     test/toolchain). This catches subsystems that predate the diff baseline and
     were never written up — (A) by construction cannot.
   Either way, produce the *uncovered* list with, per module: real source path,
   what it is (verified from source), substance (LOC / substantial-vs-stub), and
   a recommended placement. Beware the name-grep's false positives (concept
   covered under another name; deprecated/sample/empty repos) — verify concept
   coverage and substance, don't trust the grep.
2. **Placement policy (threshold):**
   - A new capability that **extends an existing subsystem** → fold a new
     numbered section into that chapter (preferred — do this first).
   - A **substantial new top-level subsystem that does not fit any chapter** →
     a new chapter (appended number, continuing past the last one).
   - A **cluster** of related new repos forming a new domain → a new **Part**
     appended after the last numbered Part, before Appendices.
   - `external/*` deps and thin/stub/relocation/prebuilt modules → a brief
     **integration note** in the most relevant chapter (or leave to the
     appendix). They never get their own chapter.
3. Author the sections/notes (with Mermaid where it clarifies) and run them
   through the **same** convergent review loop as Phase B.
4. New chapter/Part → do the new-chapter bookkeeping in Phase D.

### Phase D — Bookkeeping & gates

After chapters reach convergence, and after any new chapter/Part. Full checklist
in `references/bookkeeping.md`. Gates that must be green:

- `python3 agents/build.py` regenerated and `agents/build.py --check` exits 0
  (content changes stale the Part-skills — rule 12).
- `mkdocs build` succeeds **in the project Docker image** (local `mkdocs` fails
  on the `!!python` tag — that's environmental, not your error).
- Every touched chapter `./serve.sh png` reports `errors=0`.
- No local-path/username leaks anywhere in the touched files.
- New chapter only: `manifest.toml`, `mkdocs.yml` nav, the `docs/` symlink,
  `README.md` + `agents/README.md` counts/tables, and `llms.txt` updated; a new
  Part also needs a hand-authored `agents/_content/parts/<id>/SKILL.md` before
  `build.py` will run.

## Agent-team orchestration (≤10 by default)

Process the queue in waves. Per wave: spawn one **author** agent per chapter
(distinct files only), then independent **reviewer** agents (accuracy + Mermaid
+ structure), then targeted **fixers**. Fold the cheap accuracy self-check into
the author (have it verify every cited path against source and run
`serve.sh png` itself), then run a deterministic batch gate yourself and a
separate adversarial review team. **Retry any subagent that hits a transient
API/network/tool error** (≤3×) — these happen and a retry almost always works.

## Resumable state — `.superpowers/book-polish/` (gitignored)

`state.json` (`{phase, sections:{<slug>:{status,round,dry_rounds,priority,part}},
new_parts, done_count, total}`), `queue.json`, `new-chapters.json`,
`backups/<slug>.bak.md`, `findings/`, `log.md`. On start, if `state.json`
exists, resume from it; else initialize via Phase A. Steps are idempotent.

## Commit policy

Do NOT auto-commit. Keep all changes local on the current branch; do not create
a branch or push. The user reviews and commits. When the user does ask to
commit: stage everything, **confirm nothing under `.superpowers/` or `docs/` is
staged**, and use a plain commit (no `Co-Authored-By` trailer — CLAUDE.md rule).

## Gotchas learned the hard way

- **`git checkout -- agents/` reverts your manifest + Part templates.**
  `manifest.toml` and `agents/_content/parts/*/SKILL.md` live under `agents/`, so
  a blanket checkout to clear a subagent's stray `build.py` regen also wipes your
  bookkeeping. Revert only the generated platform trees, or re-apply + regenerate.
- **A new Part needs its source template first.** `build.py` fails with
  "Missing SKILL.md for part <id>" until you hand-author
  `agents/_content/parts/<id>/SKILL.md` (copy an existing Part's as a model).
- **The dup-section gate must use full tokens.** A regex like `^#{2,3} N\.[0-9]+`
  mis-flags 4-level numbers (`N.1.5.1` → "N.1.5"). Match the whole token:
  `^#{2,4} N\.[0-9]+(\.[0-9]+){0,3}` then `sort | uniq -d`.
- **`mkdocs build` must run in Docker.** Validate with
  `docker compose run --rm --no-deps --entrypoint sh serve -c "mkdocs build"`.
- **Front matter (00) and intro (01) go last** — they enumerate the book's
  structure, so update them after new chapters/Parts exist. They have no
  Try-It/Summary; do not add them.

## References

- `references/new-modules.md` — the mandatory Phase C gap-analysis-and-add procedure
- `references/per-chapter-loop.md` — Phase A/B: prioritization, the convergent loop, agent roles, the batch gate
- `references/invariants.md` — the hard invariants + book conventions in full
- `references/bookkeeping.md` — Phase D: regeneration, new-chapter wiring, gates, commit
