---
name: aosp-kernel-and-boot
description: |
  AOSP Part II — Kernel & Boot. Use when reasoning about Android's bootloader
  handoff, init.rc / first-stage init / second-stage init, the Generic Kernel
  Image (GKI) and KMI stability, dm-verity / Android Verified Boot, the kernel's
  Android-specific subsystems (binder driver, ashmem→memfd, low-memory killer,
  PSI), vendor modules, or system properties (property_service, property
  contexts, ro/persist/sys/build prefixes). Chapters 4–6.
metadata:
  author: 'utzcoz'
  last-updated: '2026-06-16'
---

# AOSP Part II — Kernel & Boot

How an Android device boots, how the Generic Kernel Image keeps vendor and
platform decoupled, and how system properties fan out across the early-boot
trust chain.

## Chapters in this Part

- `04-boot-and-init.md` — bootloader handoff, first/second-stage init, init.rc parsing, services and triggers, early-mount, Zygote startup
- `05-kernel.md` — Generic Kernel Image, vendor modules, KMI stability, dm-verity / AVB, Android-specific subsystems
- `06-system-properties.md` — property_service, property contexts/SELinux, persistent properties, ro/persist/sys/build prefixes, getprop/setprop plumbing

## When to load which chapter

- Question mentions init, init.rc, services, triggers, Zygote startup, bootloader → `04-boot-and-init.md`
- Question mentions GKI, KMI, kernel modules, dm-verity, AVB, LMK, PSI, ashmem, memfd → `05-kernel.md`
- Question mentions getprop/setprop, system properties, ro./persist./sys./build. prefixes → `06-system-properties.md`
