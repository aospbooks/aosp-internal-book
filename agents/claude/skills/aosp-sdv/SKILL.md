---
name: aosp-sdv
description: |
  AOSP Part XVI — Software Defined Vehicle. Use when reasoning about the
  Android 17 SDV platform: the headless Core VM, VSIDL-generated-Rust
  service bundles, orchestration / lifecycle / health monitoring, the
  service-bundles registry, update manager, vehicle power-state manager,
  display safety, and the SDV gateway that bridges Android Automotive (AAOS)
  and cross-ECU traffic over SOME/IP. Chapters 65–66.
metadata:
  author: 'utzcoz'
  last-updated: '2026-06-20'
---

# AOSP Part XVI — Software Defined Vehicle

Android 17's Software Defined Vehicle stack: a headless, service-oriented
vehicle platform that runs alongside Android Automotive. Services are
described in VSIDL, generated as Rust service bundles, orchestrated against a
desired-state model, and reached across VM and ECU boundaries through a
SOME/IP-based middleware fabric and the SDV gateway.

## Chapters in this Part

- `65-software-defined-vehicle.md` — the SDV architecture overview: headless Core VM, the VSIDL-generated-Rust service-bundle model, orchestration/lifecycle/health monitoring, the service-bundles registry, update manager, vehicle power-state manager, display safety, and AAOS integration via the SDV gateway
- `66-sdv-middleware-and-communication.md` — the SDV communication fabric: VSIDL and its Rust codegen, service discovery / data tunnel / RPC agent, the SOME/IP stack and broker, the SDV gateway with VHAL proxy, and the automotive_services domain catalog (diagnostics, configuration, calibration)

## When to load which chapter

- SDV architecture, Core VM, service bundles, orchestration, lifecycle, health monitoring, registry, update manager, power-state manager, display safety, AAOS integration → `65-software-defined-vehicle.md`
- The middleware fabric: VSIDL codegen, service discovery / data tunnel / RPC, SOME/IP stack and broker, the gateway's VHAL proxy, automotive diagnostics/configuration/calibration services → `66-sdv-middleware-and-communication.md`
