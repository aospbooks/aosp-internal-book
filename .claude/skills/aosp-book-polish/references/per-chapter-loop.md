# Phases A & B — prioritization and the per-chapter convergent loop

## Phase A — Prioritize (run once)

Goal: a `queue.json` ordered so the most-changed chapters land first.

1. Read the changeset `report.md` (per-repo `new`/`dropped` counts) and the
   new-version appendix.
2. Map each subsystem to its chapter(s) via `agents/_content/manifest.toml`
   (Part → chapters).
3. Score each chapter = sum of NEW commits across its repos + count of new
   modules touching it. Sort descending → `queue.json`.
4. Initialize `state.json` with every chapter `pending` (plus any new chapters
   from Phase C once known).

Ignore `external/*` commit volume when scoring "what changed in the platform" —
external uprevs dominate raw counts but rarely change what a chapter must say
(they fold in as integration notes). When in doubt, weight `frameworks/*`,
`system/*`, `packages/modules/*`, `art/`, `bionic/`, `hardware/interfaces/`.

## Phase B — the loop

```
for each chapter, in priority waves (<= agent cap):
  if pending: back it up (.superpowers/book-polish/backups/<slug>.bak.md, once)
              Rewriter rewrites body -> status=review, round=1
  loop:
    Reviewers (accuracy + mermaid + structure) -> findings
    material = MAJOR findings + mermaid errors + structure violations
    if material > 0:  Rewriter fixes exactly those; dry_rounds=0; round++
    else:             dry_rounds++; if dry_rounds >= 2: status=done; break
  checkpoint state.json after every step
```

Even a lightly-changed chapter gets one rewrite+review cycle; it converges fast
because there is little to change. Convergence = two consecutive clean rounds
(no MAJOR, no Mermaid errors, no structure violations) — pragmatically, "all
reviewer findings fixed and the batch gate is green."

## Agent roles (≤10 concurrent by default)

- **Rewriter (per chapter):** reads the current chapter, its `.bak` (taken
  first), the chapter's repos in the new AOSP source, and that subsystem's NEW
  commits (grep `changes.txt` per repo — never read it whole). Verifies every
  existing citation against the new tree, corrects stale class/line references,
  and appends new-feature section(s) **before "Try It"** under the invariants.
  Fold the cheap accuracy self-check in here: the Rewriter opens each cited path
  to confirm it exists and is true for the new version, and runs
  `./serve.sh png <chapter>` itself to confirm `errors=0` before returning.
- **Reviewers (per chapter, independent of the Rewriter):**
  - *Accuracy* — open every cited path; confirm it exists and the claim is true
    for the new version. `[MAJOR]` = fabricated/wrong/false; `[MINOR]` = imprecise.
  - *Mermaid* — `./serve.sh png`; require `errors=0`; flag diagrams that render
    wrong, overflow, or misrepresent the architecture.
  - *Structure-lint* — numbering monotonic + no dups; Try-It→Summary terminal;
    no epigraph; chapter number/title unchanged vs git.
- **Fixers:** apply exactly the material findings; nothing else.

Reviewers are adversarial and read-only; they report, you dispatch fixers. Run
reviewers as independent agents (not the Rewriter re-grading itself) so the
review is genuinely independent. **One author/fixer per file at a time** — two
agents editing the same chapter in parallel will clobber each other; multiple
agents may *read* the same file concurrently (reviewers are fine in parallel).

## The deterministic batch gate (run yourself, every wave)

Cheap mechanical checks before/after the review team, so agents focus on
accuracy. For each touched chapter `ch` with leading number `n`:

```bash
leak=$(grep -nE "/home/[a-z]+|~/[a-z]|/Users/[a-z]|<username>" "$ch.md" | head -1)
err=$(./serve.sh png "$ch.md" 2>&1 | grep -o "errors=[0-9]*" | tail -1)
dups=$(grep -oE "^#{2,4} ${n}\.[0-9]+(\.[0-9]+){0,3}" "$ch.md" | sort | uniq -d)   # full token!
title=$(diff <(head -1 backups/$ch.bak.md) <(head -1 "$ch.md") >/dev/null && echo ok || echo CHANGED)
# terminal: last two '## ' headings should be 'Try It' then 'Summary'
```

Require: `errors=0`, `dups` empty, `title=ok`, `leak` empty, terminal
Try-It→Summary. The dup regex MUST use the full `${n}\.[0-9]+(\.[0-9]+){0,3}`
token — a 3-level pattern false-flags 4-level numbers.

## Throughput tips

- ~6 chapters per wave keeps you within a 10-agent cap with room for reviewers.
- Mark a wave `done` in `state.json` and append a one-line entry to `log.md`
  only after its batch gate is green — that's the resumable checkpoint.
- Retry any subagent that returns a transient `403 / "Please run /login" / API
  Error` — re-dispatch the same task; it almost always succeeds on retry.
