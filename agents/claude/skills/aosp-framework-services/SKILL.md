---
name: aosp-framework-services
description: |
  AOSP Part VII — Framework Services. Use when reasoning about
  PackageManagerService (install/uninstall, APK parsing, permissions,
  package visibility), ContentProviders (ContentResolver, URI permissions,
  observers, FileProvider, MediaStore), Notifications (NMS, channels,
  ranker, posting/delivery, listener services, conversations, bubbles),
  Power Management (PowerManagerService, wake locks, Doze, App Standby,
  battery saver, BatteryStats), Background Tasks (JobScheduler, WorkManager,
  AlarmManager, foreground services, exact alarm policy), Multi-User
  (UserManagerService, profiles, restrictions, cross-user calls), Account
  & Sync (AccountManagerService, authenticator, syncadapter, SyncManager),
  Location (LocationManagerService, GPS/network/fused providers, GNSS HAL,
  geofencing), or Storage (vold, StorageManagerService, scoped storage,
  FUSE/sdcardfs, MediaProvider, SAF, FBE, adoptable storage, SQLite,
  SharedPreferences). Chapters 26–34.
metadata:
  author: 'utzcoz'
  last-updated: '2026-06-22'
---

# AOSP Part VII — Framework Services

Java system services that own per-app and per-user state: package install,
content sharing, notifications, power, background work, multi-user, accounts,
location, and storage.

## Chapters in this Part

- `26-package-manager.md` — PMS, install/uninstall flow, APK parsing, permissions, app components, package visibility
- `27-content-providers.md` — ContentProvider, ContentResolver, URI permissions, observers, FileProvider, MediaStore worked example
- `28-notifications.md` — NotificationManagerService, channels, ranker, posting/delivery, listener services, conversations, bubbles
- `29-power-management.md` — PowerManagerService, wake locks, Doze, App Standby, battery saver, screen on/off, BatteryStats
- `30-background-tasks.md` — JobScheduler, WorkManager, AlarmManager, foreground services, exact alarm policy, restrictions and quotas
- `31-multi-user.md` — UserManagerService, user types (full/profile/system), creation/start/stop, restrictions, cross-user calls
- `32-account-sync.md` — AccountManagerService, authenticator/syncadapter, token caching, SyncManager, periodic sync scheduling
- `33-location.md` — LocationManagerService, providers (GPS/network/fused), GNSS HAL, mock providers, geofencing
- `34-storage.md` — vold, StorageManagerService, scoped storage, FUSE/sdcardfs, MediaProvider, SAF, FBE, adoptable storage, SQLite/SharedPreferences

## When to load which chapter

- Question mentions PackageManager, install/uninstall, APK parsing, permissions, package visibility → `26-package-manager.md`
- Question mentions ContentProvider, ContentResolver, URI grant, FileProvider, MediaStore → `27-content-providers.md`
- Question mentions notifications, NMS, channels, ranker, conversations, bubbles → `28-notifications.md`
- Question mentions PowerManager, wake locks, Doze, App Standby, BatteryStats → `29-power-management.md`
- Question mentions JobScheduler, WorkManager, AlarmManager, foreground service, exact alarm → `30-background-tasks.md`
- Question mentions UserManager, work profile, multi-user, user restrictions → `31-multi-user.md`
- Question mentions AccountManager, authenticator, SyncAdapter, SyncManager → `32-account-sync.md`
- Question mentions LocationManager, GNSS, fused location, geofencing → `33-location.md`
- Question mentions vold, StorageManager, scoped storage, FUSE, MediaProvider, SAF, FBE, adoptable storage, SQLite, SharedPreferences → `34-storage.md`
