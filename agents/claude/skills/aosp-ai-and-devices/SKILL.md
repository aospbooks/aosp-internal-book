---
name: aosp-ai-and-devices
description: |
  AOSP Part XII — AI & Devices. Use when reasoning about on-device ML in
  AOSP, NNAPI, the AppFunctions framework for assistant integration, the
  Computer Control flow, CompanionDeviceManager, or virtual devices
  (virtual displays/inputs/cameras for cross-device experiences), or the
  NpuManager module for on-device neural accelerators (model-load admission
  control, the NDK ANpuBuffer surface, the android.hardware.npu HAL).
  Chapters 51–53.
metadata:
  author: 'utzcoz'
  last-updated: '2026-06-22'
---

# AOSP Part XII — AI & Devices

Newer cross-device and assistant-oriented surfaces: on-device ML wiring
and the companion-device / virtual-device frameworks.

## Chapters in this Part

- `51-ai-appfunctions.md` — on-device ML in AOSP, NNAPI, AppFunctions framework for assistant integration, Computer Control
- `52-companion-virtual-device.md` — CompanionDeviceManager, virtual displays/inputs/cameras, cross-device experiences
- `53-npu-manager.md` — the NpuManager mainline module for on-device neural accelerators: model-load admission control (budget/turn-taking policies, priorities), the Rust NDK ANpuBuffer/INpuAllocator, the android.hardware.npu HAL, and libwrapfd buffer protection

## When to load which chapter

- Question mentions NNAPI, AppFunctions, on-device ML, Computer Control → `51-ai-appfunctions.md`
- Question mentions CompanionDeviceManager, virtual display, virtual camera, virtual input → `52-companion-virtual-device.md`
- Question mentions NPU, neural accelerator, NpuManager, ANpuBuffer, model-load scheduling → `53-npu-manager.md`
