---
name: aosp-runtime
description: |
  AOSP Part V — Runtime. Use when reasoning about ART (dex2oat, AOT/JIT,
  baseline profiles, GC, oat/vdex/odex files, class loaders, JNI bridge) or
  the Native Bridge (Berberis, Houdini, cross-architecture native code
  execution, intercepting libc/JNI calls). Chapters 18–19.
metadata:
  author: 'utzcoz'
  version: '2026.06.24'
  last-updated: '2026-06-24'
---

# AOSP Part V — Runtime

The Android Runtime (ART) and the binary translation layer that lets
arm-only native code run on x86_64 devices.

## Chapters in this Part

- `18-art-runtime.md` — dex2oat, AOT/JIT, baseline profiles, GC (concurrent copying), oat/vdex/odex files, class loaders, JNI bridge
- `19-native-bridge.md` — cross-architecture native code execution, Houdini → Berberis, intercepting libc/JNI calls, performance trade-offs

## When to load which chapter

- Question mentions ART, dex2oat, AOT, JIT, baseline profiles, GC, oat/vdex/odex, JNI internals → `18-art-runtime.md`
- Question mentions Berberis, Houdini, native bridge, ARM-on-x86, binary translation → `19-native-bridge.md`
