---
name: aosp-part-01-getting-started
description: |
  AOSP Part I — Getting Started. Use when reasoning about the AOSP source
  tree at a high level, the repo/manifest workflow, the Soong (Android.bp)
  and Bazel/Kleaf build systems, lunch targets, the m build entry point, or
  aconfig feature flags (build-time vs. runtime, release configs, ramp/cleanup
  workflows). Chapters 0–3 (Frontmatter, Introduction, Source Code & Build
  System, Feature Flags).
---

# AOSP Part I — Getting Started

Foundational chapters that orient a reader to AOSP, its source tree, how to
sync and build it, and how feature gating works across the platform.

## Chapters in this Part

- `00-frontmatter.md` — preface, target audience, conventions, AOSP version targeted
- `01-introduction.md` — what AOSP is vs. Android, the layer-cake architecture, source-tree tour, who maintains what, version history
- `02-source-and-build.md` — repo/manifest, Soong (`Android.bp`), Bazel-from-Soong, Kleaf for the kernel, lunch targets, the `m` workflow
- `03-feature-flags.md` — aconfig declarations, generated Java/C++ accessors, build-time vs. runtime flags, release configs, ramp-and-cleanup workflow

## When to load which chapter

- Question is "what is AOSP / where do I start" → `00-frontmatter.md` + `01-introduction.md`
- Question mentions Soong, Bazel, Kleaf, repo, manifest, lunch, or m → `02-source-and-build.md`
- Question mentions feature flags, aconfig, release configs, or `read_only` flags → `03-feature-flags.md`
