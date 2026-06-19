# Phase 2 backend: agent-team gap analysis & append

The goal: given an existing version-changes report and the Phase 1 changeset,
find the important modules the report missed and append them — verified against
real source. A first drafting pass reliably misses things because the changeset
is huge and a drafter anchors on headline features. This phase is the
counter-pressure.

There are **two complementary kinds of gap**, and you need both passes:
1. **Added projects** — whole new repos in the newer release.
2. **New modules inside *moved* repos** — a new service/dir/API added within a
   repo that merely "moved" (e.g. a new system service in `frameworks/base`).
   These never appear as added *projects*, so a project-level diff misses them
   entirely — yet they're often the most interesting changes.

## Scope policy (apply in every pass)

Decide in/out per candidate. This is the same policy used for the report itself.

- **Analyze the code** for platform paths: `frameworks/*`, `system/*`,
  `packages/{apps,modules}/*`, `art/`, `libcore/`, `bionic/`,
  `hardware/interfaces/`, `build/{soong,make}`, and new `device/google/*`.
- **Integration-only** for `external/*`: describe how/why it's integrated (what
  consumes it, what capability it signals), never its internal code. A new
  `external/*` dep is a *signal* — e.g. `external/openxr-sdk` ⇒ XR runtime support.
- **Drop as noise**: vendor/board repos (`broadcom*`, `hikey`, per-OEM
  `device/<vendor>/*` except `device/google/*`), `prebuilts/*`, toolchains,
  test-infra; empty/placeholder repos (only OWNERS or an empty initial commit);
  pure relocations (a dir moved between repos, no new behavior); routine
  third-party version bumps; repos whose new commits are all bugfixes.

When in doubt, prefer **reduce gaps**: append only genuinely high-signal
findings. A handful of real new modules beats twenty marginal ones, especially
under a size budget.

## Pass 1: added projects not in the report

Build the candidate set deterministically so agents only investigate real gaps:
```bash
D=manifest-snapshots/_compare/<old>-to-<new>
APP=<the existing report file>
# added project paths from the navigator's Added table
sed -n '/## Added projects/,/## Removed projects/p' $D/report.md \
  | grep '^|' | sed -E 's/^\| *[^|]*\| *`([^`]*)`.*/\1/' | grep -vE '^Name$|^---' \
  > /tmp/added.txt
# subtract those already referenced anywhere in the report
: > /tmp/missing.txt
while read p; do [ -n "$p" ] && grep -qF "$p" "$APP" || echo "$p" >> /tmp/missing.txt; done < /tmp/added.txt
```
Partition `/tmp/missing.txt` by area (e.g. `packages/`, `system/`, a
multi-repo cluster like the SDV tree, and `external/|hardware/|prebuilts/`) so
each agent gets a coherent batch.

## Pass 2: new modules inside moved repos

For each high-signal moved repo (use the report's priority/scope list — e.g.
`frameworks/base`, `frameworks/native`, `packages/modules/*`, `system/core`,
`art`, `build/soong`), index its NEW commit subjects cheaply and look for new
subsystems. **Never read `changes.txt` whole** — grep one repo's section:
```bash
grep -n -A 9999 '^frameworks/base   (' $D/changes.txt \
  | sed -n '/NEW (/,/^DROPPED/p' \
  | grep -iE 'add .*(service|module|manager|daemon|api|profile)|new .*(module|feature)|initial' \
  | head -60
```
The hits are candidates; confirm each against real source before believing it.

## The agent team (≤10 concurrent)

One agent per candidate batch (or per moved repo cluster). Give each agent a
prompt of this shape — the specifics that make it work are: confirm-absent,
read-real-source, classify, and cite-one-real-path:

```
You investigate newly-added Android <N> modules possibly MISSING from <report file>.
Repo root: <book repo>. AOSP source: <aosp root> (READ-ONLY).
Candidates: <inject this agent's batch>.
For EACH candidate:
 1. Confirm it is genuinely NOT covered: grep <report file> for the path AND its
    short name (it may be covered collectively under a cluster). If covered, mark
    covered=true and skip.
 2. If uncovered, read the ACTUAL source under <aosp root>/<path> (README,
    Android.bp, AndroidManifest, key entry points) to learn what it IS and why
    it's new in <N>. For external/* describe integration only, never internals.
 3. Classify: part (subsystem), category (New project | New module | Notable
    integration), relevance (add-worthy | out-of-scope + reason), one_line citing
    ONE real path you opened.
Write a Markdown table to <scratch>/found-<batch>.md:
| Path | Covered? | Part | Category | Relevance | What it is (cite source) |
Return a 3-5 line summary naming the add-worthy gaps. Do NOT edit the report or commit.
```

Persist every agent's table under a gitignored scratch dir
(`.superpowers/<topic>/gaps/`) and consolidate into a `SUMMARY.md` (add-worthy →
moderate → out-of-scope-with-reason). Logging the *excluded* set with reasons
matters: it shows nothing was silently dropped, which is the whole point of a
gap pass.

## Appending the findings (concise, budget-aware)

Curate to the high-signal set ("reduce gaps"). For each addition write ONE tight,
source-cited bullet in the report's voice; group by the report's existing
structure. To insert safely without parallel-edit conflicts, have agents emit
**snippets + an exact insertion anchor** (an existing line to insert after)
rather than editing the report directly; then apply the snippets sequentially
yourself.

If the report has a size budget and the additions push it over, trim lower-value
existing prose to make room — tighten verbose paragraphs, never delete citations
or diagrams. Keep a backup of the pre-append report so you can diff/restore.

## The review → fix loop (the part that earns trust)

Newly-written content is exactly where fabricated paths and slightly-wrong symbol
names appear. So verify it adversarially, and loop:

1. Spawn **independent** verifiers (not the authors) — one per appended section.
   Each opens every cited path/symbol in the real source and confirms the claim
   is accurate for this release. Classify findings `[MAJOR]` (fabricated/wrong
   path or false claim) vs `[MINOR]` (imprecise wording); "CLEAN" if all hold.
2. Fix every finding at the source of the claim.
3. Re-verify the fixed claims. Repeat until a round surfaces **no new material
   issue** (zero MAJOR, and MINORs addressed). That convergence — not a fixed
   number of rounds — is the stop condition.

Common real findings from this loop: a module called an "AIDL HAL" when it's a
framework-internal `aidl_interface` (not under `hardware/interfaces/`); a method
cited as `start/stop` when the AIDL has `startTrack/stopTrack`; a handler
attributed to the wrong file in the same module; "every component" when it's
"most components". They're small, but they're the difference between a report a
reader can trust and one they can't.

## Why this is structured as a team, not one pass

The candidate set is large and each candidate needs real source reading, so
fan-out is a genuine speedup. More importantly, the **author/verifier split** is
what catches fabrications: the agent that wrote a bullet is the worst one to
check it. Independent verification against source is the mechanism that makes
"accuracy over coverage" real rather than a slogan.
