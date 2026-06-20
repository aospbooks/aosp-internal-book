---
name: aosp-infrastructure
description: |
  AOSP Part XIII — Infrastructure. Use when reasoning about Mainline
  modules / APEX (Project Mainline, APEX format/manifest/signing, apexd,
  module catalog, SDK Extensions, module boundaries), OTA updates (A/B
  updates, update_engine, payload format, Virtual A/B with snapshots,
  rollback protection), Virtualization (Android Virtualization Framework,
  pKVM, crosvm, microdroid), Testing (CTS/VTS/MTS, Tradefed, Ravenwood,
  atest, presubmit), or Debugging (Perfetto, atrace, simpleperf, heapprofd,
  logcat, dumpsys). Chapters 54–56.
metadata:
  author: 'utzcoz'
  last-updated: '2026-06-21'
---

# AOSP Part XIII — Infrastructure

Cross-cutting platform infrastructure: how the platform updates itself,
how isolated workloads run, and how tests/traces/profiles work.

## Chapters in this Part

- `54-mainline-modules.md` — Project Mainline, APEX format/manifest/signing, apexd, module catalog, SDK Extensions, module boundaries
- `55-ota-updates.md` — A/B updates, update_engine, payload format, virtual A/B with snapshots, rollback protection
- `56-virtualization.md` — Android Virtualization Framework, pKVM hypervisor, crosvm, microdroid, isolated workloads
- `57-testing.md` — CTS/VTS/MTS, Tradefed, Ravenwood (host-side framework testing), atest, presubmit infrastructure
- `58-debugging-tools.md` — Perfetto trace pipeline, atrace, simpleperf, heapprofd, logcat, dumpsys conventions

## When to load which chapter

- Question mentions APEX, Mainline, apexd, SDK Extensions → `54-mainline-modules.md`
- Question mentions OTA, A/B updates, update_engine, virtual A/B, snapshot, rollback → `55-ota-updates.md`
- Question mentions AVF, pKVM, crosvm, microdroid → `56-virtualization.md`
- Question mentions CTS, VTS, MTS, Tradefed, Ravenwood, atest → `57-testing.md`
- Question mentions Perfetto, atrace, simpleperf, heapprofd, dumpsys → `58-debugging-tools.md`
