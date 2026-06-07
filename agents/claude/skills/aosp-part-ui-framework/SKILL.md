---
name: aosp-part-ui-framework
description: |
  AOSP Part X — UI Framework. Use when reasoning about Widgets and
  RemoteViews (AppWidget framework, RemoteViews, RemoteCompose, host/provider
  model), WebView (WebView Mainline module, Chromium content layer, renderer
  process, JS bridges, sandboxing), Accessibility (AccessibilityService,
  AccessibilityNodeInfo, TalkBack, magnification, Switch Access), or
  Internationalization (ICU, locale resolution, resource qualifier matching,
  RTL support, Unicode in AOSP). Chapters 43–46.
metadata:
  author: 'utzcoz'
  last-updated: '2026-06-07'
---

# AOSP Part X — UI Framework

Cross-cutting UI infrastructure: home-screen widgets, the WebView module,
the accessibility framework, and locale/i18n handling.

## Chapters in this Part

- `43-widgets-remoteviews.md` — AppWidget framework, RemoteViews, RemoteCompose, host/provider model, update flow
- `44-webview.md` — WebView Mainline module, Chromium content layer, renderer process, JS bridges, sandboxing
- `45-accessibility.md` — AccessibilityService, AccessibilityNodeInfo, TalkBack, magnification, accessibility events, Switch Access
- `46-internationalization.md` — ICU, locale resolution, resource qualifier matching, RTL support, formatters, Unicode in AOSP

## When to load which chapter

- Question mentions AppWidget, RemoteViews, RemoteCompose, widget host → `43-widgets-remoteviews.md`
- Question mentions WebView, Chromium, renderer process, JS interface → `44-webview.md`
- Question mentions AccessibilityService, AccessibilityNodeInfo, TalkBack, Switch Access → `45-accessibility.md`
- Question mentions ICU, locales, RTL, resource qualifiers → `46-internationalization.md`
