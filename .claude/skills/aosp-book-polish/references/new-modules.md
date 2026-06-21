# Phase C — Newly-added modules/projects (mandatory)

The reason this phase is mandatory and separate: a newly-added module has **no
existing chapter**, so the per-chapter polish loop (Phase B) will never surface
it. New modules are the single easiest thing to miss in a version bump. Run this
even when the rest of the book looks done — and run it whenever the user asks
only to "cover the new modules" without mentioning the rest.

## Step 1 — Gap analysis (run in a subagent)

Always do the analysis in a subagent (read-only), not inline — it keeps the
candidate set deterministic and the verification honest, and it scales.

There are **three ways to build the candidate set**. They answer different
questions; for thorough coverage do (A) on a version bump, (B) when the user
asks to "read across the whole source and find what's left" (or periodically,
since (A) by construction never flags a subsystem that existed before the diff
baseline and was never written up), and (C) whenever official release notes
exist for the version — they surface a class neither (A) nor (B) can.

**(A) Changeset-driven — what's NEW (don't guess, derive it):**
- The *added* projects in the changeset: `manifest-snapshots/_compare/<old>-to-<new>/added-removed.txt`.
- The new-version appendix's enumerated new projects/modules (e.g.
  `D-appendix-android-17-updates.md`, the `### New projects` / `### New modules`
  subsections per Part). If a curated appendix exists, it is the best candidate
  list — most of its entries should already be folded by Phase B; you are
  hunting the *leftovers*.
- Optionally any prior gap findings under `.superpowers/android17-report/gaps/`.

**(B) Whole-tree sweep — what's LEFT (every project vs the book):** scan the
ENTIRE manifest, not just the diff. This catches substantial subsystems that
have been in AOSP for releases but never got a chapter.
- Enumerate every project path from the AOSP checkout's `<aosp-root>/.repo/project.list`
  (the authoritative ~1000+ project list; `<aosp-root>` is the parameter-supplied
  source path). Fall back to the newest `manifest-snapshots/_history/<branch>_*.history.txt`
  if `.repo` is absent.
- For each path, grep the main chapters `[0-9][0-9]-*.md` for the **full path**
  AND the **last path segment**; zero hits ⇒ candidate. Do this with a script —
  it's mechanical and ~1000 projects is too many by hand.
- Keep only **in-scope platform roots** (`frameworks/`, `system/`,
  `packages/{apps,modules,services,providers}/`, `art`, `bionic`, `libcore`,
  `hardware/interfaces`, `hardware/google`, `build/{soong,make,release}`,
  `bootable/`) and **drop noise** (`external/`, `prebuilts/`, `vendor/`,
  `toolchain/`, `kernel/prebuilts`, `device/`, `test/`, `cts/`, `tools/test/`,
  `*-vendor`). This typically cuts ~1000 projects to a few dozen candidates.

**(C) Release-notes-driven — what GOOGLE called out (the behavior/API class):**
methods (A) and (B) are both *project*-granular: they find new repos and
never-covered subsystems. They are structurally blind to the most common kind of
version change — a **new framework API, behavior change, or deprecation inside a
repo that merely "moved"**. A new `CameraCaptureSession.updateOutputConfigurations()`
method, an SDK-gated relaunch-behavior change, or a deprecated manifest attribute
never appears as an added *project*; on a real release `frameworks/base` alone
carries 15,000+ commits, so a project-level diff cannot surface them. The fix is
to mine the official release notes directly:
- Fetch the version's announcement pages (WebFetch). For Android these are the
  developer **Beta/release blog** (`android-developers.googleblog.com`, the
  "behavior changes" / "features" post) and the AOSP **whatsnew** page
  (`source.android.com/docs/whatsnew/android-NN-release`, the platform-internals
  list). Ask the fetch to enumerate every feature with its exact API / class /
  permission / flag / property names.
- For EACH highlighted item, extract its distinctive token (the symbol, flag,
  constant, or manifest attr) and grep it across the chapter bodies
  `[0-9][0-9]-*.md`. Zero hits (or hits only in the appendix / only the generic
  English word) ⇒ candidate. Triage with a script; the high-signal tokens are
  CamelCase symbols / `ALL_CAPS` constants / `dotted.flag.names`, not common words.
- Triage is noisy by nature (generic tokens like "lock-free" or "Login" match many
  chapters), so a grep hit is only a *hint*: hand every candidate to a verifying
  subagent that reads the candidate chapter AND opens the AOSP source. Release-note
  prose is loose — it frames Play-services/app-SDK features and platform changes
  alike, and it paraphrases. Verify (1) that the change is genuinely an **AOSP
  platform** change (not a Google Play / first-party-app feature), and (2) the
  exact symbol/flag/path before writing. The blog regularly names a flag that
  doesn't exist verbatim in AOSP — the agents on the 17 pass corrected several
  (`enable_windowing_edge_drag_resize`, `status_bar_connected_displays`).
- Classify each confirmed gap as a **fold** (almost always — these extend an
  existing subsystem's chapter; e.g. a new camera2 method → the camera chapter, an
  SDK-37 activity-relaunch change → the activity/window chapter), not a new chapter.

For (B) especially, hand the candidate list to verification subagents
**partitioned by tree area** (e.g. one for `system/`, one for `packages/`, one
for `frameworks/`+`hardware/`) — it's too much for one agent and the areas are
independent. For (C), partition the highlighted items by their home chapter's
Part so each agent verifies a coherent set.

**Coverage check (deterministic, both methods):** for EACH candidate, grep the
main chapters `[0-9][0-9]-*.md` (NOT the appendices) for the module's **source
path** AND its **name/concept**. "Covered" = a real section/paragraph discusses
it; "uncovered" = it appears only in the appendix or nowhere in the body.

**Beware false positives from the name-grep (the sweep's main hazard):** a crude
last-segment grep produces both *false-uncovered* (the concept IS covered but
under a different name — e.g. `system/bpf` is "eBPF" in ch5/ch35, `system/libfmq`
is "FMQ" in ch10) and *false-in-scope* (deprecated/sample/prebuilt/empty repos
that look real). The verifying subagents MUST re-check concept coverage (search
the abbreviation/feature name, not just the path) and confirm the candidate is
substantial live platform code — never trust the grep alone.

**Verify against source:** for each genuinely-uncovered candidate, open its path
in the AOSP tree and record: the real repo-relative path(s), a one-paragraph
"what it is" (from source, not the appendix), and its **substance** — approx LOC
and whether it is substantial platform code, a thin/stub/relocation, an
`external/*` dependency, or a prebuilt.

Have the subagent write the result to `.superpowers/book-polish/new-modules-gap.md`
(a table: Module | Source path | What it is | Substance | Coverage | Recommendation)
and return the same list.

## Step 2 — Placement policy (the threshold)

Decide per module. **Fold into an existing chapter first**; reach for a new
chapter only when nothing fits and the code is substantial.

| Situation | Action |
|---|---|
| Extends an existing subsystem | **Fold** a new numbered section into that chapter (preferred) |
| Substantial NEW top-level subsystem, fits no chapter | **New chapter** — append it (number past the last one) by default; or, if the user wants logical ordering, **insert** it at its Part position via a coordinated whole-book renumber (see `bookkeeping.md` → "Renumbering chapters") |
| Cluster of related new repos forming a new domain | **New Part** appended after the last numbered Part, before Appendices (or inserted at its logical position via a renumber) |
| `external/*` dep, or thin/stub/relocation/prebuilt | **Integration note** in the most relevant chapter (how/why integrated), or leave to the appendix — never its own chapter |

A new chapter must clear all three: (a) genuinely new top-level
subsystem/project in scope (`frameworks/*`, `system/*`, `packages/{apps,modules}/*`,
`art/`, `bionic/`, `hardware/interfaces/`, new `device/google/*`); (b) substantial
platform code (not a stub/relocation/prebuilt); (c) does not fit an existing
chapter's scope. If a capability merely extends an existing subsystem, append it
to that chapter instead.

Record decisions in `.superpowers/book-polish/new-chapters.json`:
`[{slug, number, title, part, rationale, source_repos, status}]` and any new
Parts. Cross-check candidate chapter scope against `manifest.toml`.

### Real examples from the Android 16→17 pass

- **Folded into existing chapters:** WebApp/PWA → ch26; mmd → ch8/ch29;
  guardian/pmgd → ch29; ImsStack + GBA → ch36; casefolding_remover → ch34;
  bert_collector → ch4; usbauthservice + aoad → ch39; AiSeal → ch50 (+ AVF
  cross-ref in ch54); PersonalContext → ch50; native Rust Zygote → ch18;
  Wi-Fi USD → ch35; VirtualGamepad → ch51; amemdiff (host tool) → ch8 note.
- **New chapters (cleared the threshold):** Software Defined Vehicle (65) and
  SDV Middleware (66) → new **Part XVI**; NPU Manager (67) → folded into Part XII;
  LFI in-process sandbox (68) → folded into Part IX.
- **Integration note / appendix-only:** OpenXR (`external/openxr-sdk`, headers +
  two flagged feature strings, zero in-tree consumers) → conservative note in
  ch60, full detail in the appendix.

## Step 3 — Author, then converge

Author the new sections/notes (with Mermaid where it genuinely clarifies the
architecture), then run them through the **same convergent review loop as Phase
B** (`references/per-chapter-loop.md`): one author per file, independent
adversarial accuracy + Mermaid review, fix material findings, repeat to two
clean rounds. Notes for thin/external modules should be proportionate — a short
paragraph that references the mechanism and cross-links the appendix, not a full
section. Be accurate and conservative: a "signal of future support" (vendored
headers, flagged feature strings, no consumer) must not read as a shipping
subsystem.

## Step 4 — Bookkeeping for new chapters/Parts

Only if Step 2 added a chapter or Part — see `references/bookkeeping.md`.
Folds and notes into existing chapters need only the standard Phase D
regeneration (`build.py`) and gates; they do not touch `manifest.toml`/nav/
README/`llms.txt` (within-scope additions, per CLAUDE.md rule 11).
