# AOSP Internals book content (67 chapters + 4 appendices) packaged as 16 Part-skills.

> AOSP Internals plugin, packaged version 2026.05.25.
> Source: https://github.com/aospbooks/aosp-internal-book

## When to read which Part

When the user asks about an AOSP subsystem, identify the matching Part below and read `parts/<part-id>.md` for the full chapter content.

### Part I — Getting Started (`parts/getting-started.md`)

AOSP Part I — Getting Started. Use when reasoning about the AOSP source
tree at a high level, the repo/manifest workflow, the Soong (Android.bp)
and Bazel/Kleaf build systems, lunch targets, the m build entry point, or
aconfig feature flags (build-time vs. runtime, release configs, ramp/cleanup
workflows). Chapters 0–3 (Frontmatter, Introduction, Source Code & Build
System, Feature Flags).

### Part II — Kernel & Boot (`parts/kernel-and-boot.md`)

AOSP Part II — Kernel & Boot. Use when reasoning about Android's bootloader
handoff, init.rc / first-stage init / second-stage init, the Generic Kernel
Image (GKI) and KMI stability, dm-verity / Android Verified Boot, the kernel's
Android-specific subsystems (binder driver, ashmem→memfd, low-memory killer,
PSI), vendor modules, or system properties (property_service, property
contexts, ro/persist/sys/build prefixes). Chapters 4–6.

### Part III — Native Foundation (`parts/native-foundation.md`)

AOSP Part III — Native Foundation. Use when reasoning about Bionic (Android's
libc/libm/libdl) and the dynamic linker, linker namespaces, GWP-ASan / MTE,
memory management (jemalloc/scudo, ashmem/memfd, ION/dma-buf, lmkd, PSI),
Binder IPC (transactions, parcels, one-copy semantics, AIDL/HIDL/NDK Binder,
servicemanager, threadpool, death recipients), the HAL (Treble, HIDL→AIDL HAL
migration, vendor/system split, hwservicemanager, VINTF), or the NDK (libandroid,
JNI bindings, ABI compatibility). Chapters 7–11.

### Part IV — Native Services & Media (`parts/native-services-and-media.md`)

AOSP Part IV — Native Services & Media. Use when reasoning about
surfaceflinger, audioserver, mediaserver, cameraserver, the graphics
pipeline (BufferQueue, GraphicBuffer, OpenGL ES / Vulkan / Skia / HWUI,
RenderThread, layer composition), the animation system (Choreographer,
ValueAnimator, RenderNode animations, dynamic spring/fling), the audio
stack (AudioFlinger, AudioPolicyManager, AAudio, OpenSL ES, Spatializer),
the media pipeline (MediaCodec, MediaExtractor, NuPlayer, codec2 HAL),
or the sensor stack (SensorService, sensor HAL, batching, wake-up sensors).
Chapters 12–17.

### Part V — Runtime (`parts/runtime.md`)

AOSP Part V — Runtime. Use when reasoning about ART (dex2oat, AOT/JIT,
baseline profiles, GC, oat/vdex/odex files, class loaders, JNI bridge) or
the Native Bridge (Berberis, Houdini, cross-architecture native code
execution, intercepting libc/JNI calls). Chapters 18–19.

### Part VI — Framework Core (`parts/framework-core.md`)

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

### Part VII — Framework Services (`parts/framework-services.md`)

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

### Part VIII — Connectivity (`parts/connectivity.md`)

AOSP Part VIII — Connectivity. Use when reasoning about Networking
(ConnectivityService, Wi-Fi framework, netd, DNS resolver, VPN, tethering,
NetworkSecurityConfig, VCN, Thread mesh), Telephony (TelephonyManager,
PhoneInterfaceManager, RIL/RILD, modem AIDL, IMS framework, emergency
calling), Bluetooth (Bluetooth Mainline module, BTA, GATT, A2DP/HFP/AVDTP,
LE Audio, pairing, scanning, advertising), NFC (NfcAdapter/NfcService,
NCI, tag dispatch, HCE, secure element, reader mode, NFC-F/V), or USB &
ADB (USB gadget framework, host-mode USB, MTP/PTP, RNDIS tethering, adb
daemon, adb over Wi-Fi). Chapters 35–39.

### Part IX — Security (`parts/security.md`)

AOSP Part IX — Security. Use when reasoning about SELinux on Android,
Keystore/Keymint, Trusty TEE, gatekeeper/weaver, Android Verified Boot,
dm-verity, hardware-backed attestation, Credential Manager (CredentialManagerService,
credential providers, passkeys/FIDO2, password and autofill integration,
digital credentials), or DRM (MediaDrm framework, Widevine L1/L2/L3,
OEMCrypto, license acquisition, secure decoder/display path), or the LFI
in-process sandbox (Lightweight Fault Isolation for untrusted code such as
software codecs). Chapters 40–42, 68.

### Part X — UI Framework (`parts/ui-framework.md`)

AOSP Part X — UI Framework. Use when reasoning about Widgets and
RemoteViews (AppWidget framework, RemoteViews, RemoteCompose, host/provider
model), WebView (WebView Mainline module, Chromium content layer, renderer
process, JS bridges, sandboxing), Accessibility (AccessibilityService,
AccessibilityNodeInfo, TalkBack, magnification, Switch Access), or
Internationalization (ICU, locale resolution, resource qualifier matching,
RTL support, Unicode in AOSP). Chapters 44–46.

### Part XI — System Apps (`parts/system-apps.md`)

AOSP Part XI — System Apps. Use when reasoning about SystemUI (status bar,
notification shade, keyguard, Quick Settings, Monet/dynamic color),
Launcher3 (model loader, Recents/Overview, gesture nav, all-apps,
predictions, work profile), or the Settings app (SettingsProvider,
SettingsLib, search index, slice surface). Chapters 48–49.

### Part XII — AI & Devices (`parts/ai-and-devices.md`)

AOSP Part XII — AI & Devices. Use when reasoning about on-device ML in
AOSP, NNAPI, the AppFunctions framework for assistant integration, the
Computer Control flow, CompanionDeviceManager, or virtual devices
(virtual displays/inputs/cameras for cross-device experiences), or the
NpuManager module for on-device neural accelerators (model-load admission
control, the NDK ANpuBuffer surface, the android.hardware.npu HAL).
Chapters 51–51, 67.

### Part XIII — Infrastructure (`parts/infrastructure.md`)

AOSP Part XIII — Infrastructure. Use when reasoning about Mainline
modules / APEX (Project Mainline, APEX format/manifest/signing, apexd,
module catalog, SDK Extensions, module boundaries), OTA updates (A/B
updates, update_engine, payload format, Virtual A/B with snapshots,
rollback protection), Virtualization (Android Virtualization Framework,
pKVM, crosvm, microdroid), Testing (CTS/VTS/MTS, Tradefed, Ravenwood,
atest, presubmit), or Debugging (Perfetto, atrace, simpleperf, heapprofd,
logcat, dumpsys). Chapters 54–56.

### Part XIV — Device Support (`parts/device-support.md`)

AOSP Part XIV — Device Support. Use when reasoning about per-architecture
support (ARM 32/64, x86_64, RISC-V, ABI matrix, toolchains), the QEMU-based
Android emulator (AVD format, hardware acceleration, guest kernel),
DevicePolicyManager (work profiles, fully-managed devices, COPE,
enrollment), Android Automotive / TV / Wear (CarService, vehicle HAL,
Leanback, TIF, Wear OS specifics), Print Services (PrintManager, IPP,
PDF generation), or the Camera2 pipeline (Camera2 API, CaptureRequest/Result,
camera HAL3). Chapters 59–62.

### Part XV — Practical (`parts/practical.md`)

AOSP Part XV — Practical. Use when reasoning about building a custom AOSP
ROM end-to-end: picking a target device, syncing source, applying vendor
blobs, branding, building, flashing the resulting images, and shipping
OTA updates on your own channel. Chapter 65 (Custom ROM Guide).

### Part App. — Appendices (`parts/appendices.md`)

AOSP Internals — Appendices. Use when looking up a key file path
(per-chapter table of the most important AOSP source files: build, init,
kernel, HAL, framework services, system apps, infrastructure) or the
meaning of an AOSP-specific acronym/term (Treble, VINTF, GKI, APEX, AIDL,
HIDL, etc.), why Kotlin is absent from the public API, or what changed from
Android 16 to Android 17. Reference material — load when you need a concrete
path, a definition, or a changelog rather than narrative explanation.

