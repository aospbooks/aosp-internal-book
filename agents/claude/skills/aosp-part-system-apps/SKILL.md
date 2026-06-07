---
name: aosp-part-system-apps
description: |
  AOSP Part XI — System Apps. Use when reasoning about SystemUI (status bar,
  notification shade, keyguard, Quick Settings, Monet/dynamic color),
  Launcher3 (model loader, Recents/Overview, gesture nav, all-apps,
  predictions, work profile), or the Settings app (SettingsProvider,
  SettingsLib, search index, slice surface). Chapters 47–49.
metadata:
  author: 'utzcoz'
  last-updated: '2026-06-07'
---

# AOSP Part XI — System Apps

The three privileged apps every AOSP build ships with: SystemUI, Launcher3,
and Settings.

## Chapters in this Part

- `47-systemui.md` — SystemUI process, status bar, notification shade, keyguard, Quick Settings, Monet/dynamic color
- `48-launcher3.md` — Launcher3, model loader, Recents/Overview, gesture nav, all-apps, predictions, work profile
- `49-settings-app.md` — Settings app structure, SettingsProvider, SettingsLib, search index, slice surface

## When to load which chapter

- Question mentions SystemUI, status bar, notification shade, keyguard, QS, Monet → `47-systemui.md`
- Question mentions Launcher3, Recents, Overview, gesture nav, all-apps → `48-launcher3.md`
- Question mentions Settings app, SettingsProvider, SettingsLib, slice → `49-settings-app.md`
