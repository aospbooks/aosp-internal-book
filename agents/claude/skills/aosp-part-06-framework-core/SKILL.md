---
name: aosp-part-06-framework-core
description: |
  AOSP Part VI — Framework Core. Use when reasoning about system_server's
  boot sequence (the four boot phases, service registration, Watchdog),
  the Intent system (Intent matching, IntentFilter, IntentResolver, package
  visibility, intent verification), Activity & Window Management
  (ActivityTaskManagerService, WindowManagerService, activity lifecycle,
  task/stack model, splash screens), the window system (WindowState,
  SurfaceControl, input dispatching, focus, IME insets, transitions), the
  display system (DisplayManagerService, logical vs. physical displays,
  HDR, brightness, refresh-rate switching), or the View system (View
  hierarchy, measure/layout/draw, Canvas/RenderNode, hardware acceleration).
  Chapters 20–25.
---

# AOSP Part VI — Framework Core

The Java/Kotlin layer running inside system_server that manages activities,
windows, displays, and the View tree apps render into.

## Chapters in this Part

- `20-system-server.md` — SystemServer.java, the four boot phases, service registration, Watchdog, lifecycle management, shutdown sequence
- `21-intent-system.md` — Intent matching, IntentFilter, IntentResolver, PackageManager queries, package visibility, intent verification
- `22-activity-and-window.md` — ActivityTaskManagerService, WindowManagerService, activity lifecycle state machine, task/stack model, splash screens
- `23-window-system.md` — WindowState, SurfaceControl, input dispatching, focus tracking, IME insets, transitions
- `24-display-system.md` — DisplayManagerService, logical vs. physical displays, color modes, HDR, brightness curves, refresh-rate switching
- `25-view-system.md` — View hierarchy, measure/layout/draw, Canvas/RenderNode, hardware acceleration, accessibility hooks

## When to load which chapter

- Question mentions system_server, boot phases, ServiceManager, Watchdog → `20-system-server.md`
- Question mentions Intent matching, IntentFilter, IntentResolver, package visibility → `21-intent-system.md`
- Question mentions ATM, WMS, activity lifecycle, splash screen, task/stack → `22-activity-and-window.md`
- Question mentions WindowState, SurfaceControl, input dispatch, focus, IME → `23-window-system.md`
- Question mentions DisplayManager, displays, HDR, refresh rate, brightness → `24-display-system.md`
- Question mentions View, ViewGroup, measure/layout/draw, Canvas, RenderNode → `25-view-system.md`
