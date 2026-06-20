---
name: aosp-native-foundation
description: |
  AOSP Part III — Native Foundation. Use when reasoning about Bionic (Android's
  libc/libm/libdl) and the dynamic linker, linker namespaces, GWP-ASan / MTE,
  memory management (jemalloc/scudo, ashmem/memfd, ION/dma-buf, lmkd, PSI),
  Binder IPC (transactions, parcels, one-copy semantics, AIDL/HIDL/NDK Binder,
  servicemanager, threadpool, death recipients), the HAL (Treble, HIDL→AIDL HAL
  migration, vendor/system split, hwservicemanager, VINTF), or the NDK (libandroid,
  JNI bindings, ABI compatibility). Chapters 7–11.
metadata:
  author: 'utzcoz'
  last-updated: '2026-06-20'
---

# AOSP Part III — Native Foundation

The C/C++ layer that everything above sits on: libc, the dynamic linker,
memory infrastructure, the IPC backbone (Binder), the vendor/system contract
(HAL/Treble), and the NDK that exposes a subset of native APIs to apps.

## Chapters in this Part

- `07-bionic-and-linker.md` — Bionic libc/libm/libdl, linker64, namespaces, GWP-ASan / MTE, app_process
- `08-memory-management.md` — jemalloc/scudo, ashmem/memfd, ION/dma-buf, lmkd, PSI, kswapd, OOM adjustments
- `09-binder-ipc.md` — /dev/binder, parcels, transactions, one-copy semantics, AIDL/HIDL/NDK Binder, servicemanager, threadpool, death recipients
- `10-hal.md` — Treble, HIDL→AIDL HAL migration, vendor/system partition split, hwservicemanager vs. servicemanager, VINTF
- `11-ndk.md` — native APIs exposed to apps, libandroid, JNI bindings, ABI compatibility, sysroot layout

## When to load which chapter

- Question mentions libc, linker, namespaces, MTE, GWP-ASan, app_process → `07-bionic-and-linker.md`
- Question mentions LMK, jemalloc, scudo, ION, dma-buf, PSI, OOM → `08-memory-management.md`
- Question mentions Binder, parcels, AIDL, HIDL, NDK Binder, servicemanager, one-copy → `09-binder-ipc.md`
- Question mentions Treble, HAL, VINTF, vendor partition, hwservicemanager → `10-hal.md`
- Question mentions NDK, libandroid, JNI, sysroot, ABI → `11-ndk.md`
