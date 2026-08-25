---
name: aosp-appendices
description: |
  AOSP Internals — Appendices. Use when looking up a key file path
  (per-chapter table of the most important AOSP source files: build, init,
  kernel, HAL, framework services, system apps, infrastructure) or the
  meaning of an AOSP-specific acronym/term (Treble, VINTF, GKI, APEX, AIDL,
  HIDL, etc.), why Kotlin is absent from the public API, or what changed from
  Android 16 to Android 17. Reference material — load when you need a concrete
  path, a definition, or a changelog rather than narrative explanation.
metadata:
  author: 'utzcoz'
  version: '2026.06.24'
  last-updated: '2026-08-26'
---

# AOSP Internals — Appendices

Reference material: a per-chapter index of key source files, a glossary of
AOSP-specific terms, a note on the Kotlin/public-API asymmetry, and the
Android 16→17 changelog.

## Files in this skill

- `A-appendix-key-files.md` — per-chapter table of the most important AOSP source files (sorted ascending by chapter number)
- `B-appendix-glossary.md` — definitions of AOSP-specific acronyms and terms
- `C-appendix-kotlin-public-api.md` — why Kotlin is heavily used in AOSP services yet absent from the `android.*` public API
- `D-appendix-android-17-updates.md` — important platform changes from Android 16 to Android 17, by subsystem, grounded in the 16→17 changeset and verified against AOSP 17 source

## When to load which file

- Need a specific source file path for a subsystem → `A-appendix-key-files.md`
- Need a definition of an AOSP acronym (Treble, VINTF, GKI, APEX, AIDL, HIDL, etc.) → `B-appendix-glossary.md`
- Question about Kotlin's role in AOSP vs. the public API → `C-appendix-kotlin-public-api.md`
- What changed from Android 16 to Android 17 → `D-appendix-android-17-updates.md`
