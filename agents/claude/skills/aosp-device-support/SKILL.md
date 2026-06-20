---
name: aosp-device-support
description: |
  AOSP Part XIV — Device Support. Use when reasoning about per-architecture
  support (ARM 32/64, x86_64, RISC-V, ABI matrix, toolchains), the QEMU-based
  Android emulator (AVD format, hardware acceleration, guest kernel),
  DevicePolicyManager (work profiles, fully-managed devices, COPE,
  enrollment), Android Automotive / TV / Wear (CarService, vehicle HAL,
  Leanback, TIF, Wear OS specifics), Print Services (PrintManager, IPP,
  PDF generation), or the Camera2 pipeline (Camera2 API, CaptureRequest/Result,
  camera HAL3). Chapters 57–62.
metadata:
  author: 'utzcoz'
  last-updated: '2026-06-20'
---

# AOSP Part XIV — Device Support

How AOSP supports different CPU architectures, the emulator stack, enterprise
device policy, and the form-factor-specific stacks (Auto, TV, Wear, Print).

## Chapters in this Part

- `57-architecture-support.md` — ARM (32/64), x86_64, RISC-V port, ABI matrix, per-arch toolchain and runtime considerations
- `58-emulator.md` — QEMU-based Android emulator, AVD format, hardware acceleration (KVM/HAXM/HVF), guest kernel, Studio integration
- `59-device-policy.md` — DevicePolicyManager, work profiles, fully-managed devices, COPE, restrictions, enrollment flows
- `60-automotive-tv-wear.md` — Android Automotive (CarService, vehicle HAL), Android TV (Leanback, TIF), Wear OS specifics
- `61-print-services.md` — PrintManager, print services, IPP, default printer service, PDF generation
- `62-camera2-pipeline.md` — Camera2 API, CameraDeviceImpl, CaptureRequest/Result, capture pipeline, camera HAL3

## When to load which chapter

- Question mentions ARM, x86_64, RISC-V, ABI, toolchains → `57-architecture-support.md`
- Question mentions emulator, AVD, KVM/HAXM/HVF, guest kernel → `58-emulator.md`
- Question mentions DevicePolicyManager, work profile, COPE, enrollment → `59-device-policy.md`
- Question mentions CarService, vehicle HAL, Leanback, TIF, Wear OS → `60-automotive-tv-wear.md`
- Question mentions PrintManager, IPP, print service → `61-print-services.md`
- Question mentions Camera2, CaptureRequest, camera HAL3 → `62-camera2-pipeline.md`
