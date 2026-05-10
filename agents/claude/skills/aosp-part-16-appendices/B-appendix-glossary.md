# Appendix B: Glossary

An alphabetical reference of key terms, acronyms, and subsystem names used
throughout AOSP and this book.

---

**ABI** (Application Binary Interface)
: The low-level interface contract between compiled code and the operating
  system, specifying calling conventions, data layout, and system call numbers
  for a given architecture (e.g., arm64, x86_64, riscv64).

**ADB** (Android Debug Bridge)
: Command-line tool and daemon for communicating with Android devices over USB
  or TCP. Provides shell access, file transfer, app installation, and
  debugging capabilities.

**AIDL** (Android Interface Definition Language)
: An interface description language used to define IPC contracts between
  processes. Modern AIDL replaces HIDL for HAL interfaces starting with
  Android 12+ and supports both Java and C++ backends.

**AMS** (ActivityManagerService)
: The system service responsible for managing application processes, enforcing
  permissions, and coordinating with ATMS for activity lifecycle. Lives in
  `system_server`.

**ANR** (Application Not Responding)
: A system dialog triggered when an application's main thread is blocked for
  too long (5 seconds for input events, 10 seconds for broadcast receivers).
  AMS monitors and enforces ANR timeouts.

**AOT** (Ahead-Of-Time compilation)
: Compilation of DEX bytecode into native machine code before execution,
  performed by `dex2oat`. Produces OAT files stored on disk for faster
  cold-start times.

**APEX** (Android Pony EXpress)
: A file format and installation mechanism for updatable system components
  (Mainline modules). An APEX is a zip-like container with a filesystem image,
  manifest, and signature, managed by `apexd`.

**ART** (Android Runtime)
: The managed runtime that executes Android applications. Replaced Dalvik in
  Android 5.0. Combines AOT compilation, JIT compilation, and an interpreter
  with a concurrent garbage collector.

**ATMS** (ActivityTaskManagerService)
: The system service that manages the activity task stack, back-stack
  navigation, and multi-window modes. Split from AMS in Android 10 to
  separate task management from process management.

**AVB** (Android Verified Boot)
: A chain-of-trust mechanism that verifies the integrity of each boot
  partition using cryptographic signatures. Also known as `vbmeta`; enforced
  by the bootloader and `fs_mgr`.

**AVF** (Android Virtualization Framework)
: The framework enabling hardware-isolated virtual machines on Android.
  Comprises the virtualization service, pKVM hypervisor, and Microdroid
  guest OS. Introduced in Android 13.

**BHB** (BufferHub)
: A system for zero-copy buffer sharing between processes, used primarily by
  VR and low-latency display paths. Manages buffer lifecycle and
  synchronization.

**Binder**
: Android's primary IPC mechanism. A kernel driver (`/dev/binder`) combined
  with userspace libraries provides object-oriented, synchronous remote
  procedure calls between processes with built-in reference counting and
  death notifications.

**Bionic**
: Android's custom C library, replacing glibc. Includes `libc`, `libm`,
  `libdl`, and the dynamic linker (`linker64`). Optimized for size, security
  (MTE support), and Android-specific features (system properties).

**BLAST** (Buffer Layer Accelerated SurfaceTexture)
: The modern buffer submission path in SurfaceFlinger that replaces the
  legacy BufferQueue model. Bundles buffer submission with
  SurfaceFlinger transactions for atomic, synchronized updates.

**Blueprint**
: The build description language used by Soong. `Android.bp` files use a
  JSON-like declarative syntax to define modules (libraries, binaries, APKs,
  APEX packages).

**BufferQueue**
: A producer-consumer queue for sharing graphical buffers between processes.
  The producer (app) dequeues/queues buffers; the consumer (SurfaceFlinger)
  acquires/releases them. Being superseded by BLASTBufferQueue.

**CDM** (CompanionDeviceManager)
: System service that manages associations between an Android device and
  companion devices (watches, headphones, etc.), providing discovery,
  pairing, and permission delegation.

**Choreographer**
: A Java-side coordinator that schedules drawing, animation, and input
  callbacks in sync with the display VSYNC signal. The heartbeat of
  Android's UI rendering loop.

**CTS** (Compatibility Test Suite)
: A large test suite that device manufacturers must pass to certify Android
  compatibility. Tests cover API behavior, permissions, security, and
  platform features.

**Cuttlefish**
: Google's configurable virtual Android device, designed for cloud-based
  testing and development. Runs on Linux with KVM and provides a more
  realistic virtual device than the traditional emulator.

**DEX** (Dalvik Executable)
: The bytecode format for Android applications. `.dex` files contain
  compiled Java/Kotlin code in a register-based instruction set optimized
  for memory-constrained devices.

**DisplayContent**
: The WMS container representing all window state for a single logical
  display. Holds the display-specific window hierarchy, policy, and
  configuration.

**DMA-BUF**
: A Linux kernel framework for sharing buffers between devices and
  userspace. Used extensively in Android's graphics stack for zero-copy
  sharing between GPU, display, camera, and video hardware.

**DRM/KMS** (Direct Rendering Manager / Kernel Mode Setting)
: The Linux kernel graphics subsystem. KMS handles display mode setting
  and page flipping; DRM manages GPU command submission. HWC HAL
  typically wraps DRM/KMS.

**EGL**
: The interface between OpenGL ES and the native windowing system. Manages
  display connections, rendering contexts, and surfaces. Android's EGL
  implementation lives in `libEGL.so`.

**Fastboot**
: A protocol and tool for flashing firmware images to Android devices.
  Operates in the bootloader before the OS boots, providing low-level
  access to partitions.

**GKI** (Generic Kernel Image)
: A Google-maintained kernel binary that provides a stable ABI (KMI)
  for vendor kernel modules. Part of Project Treble's kernel
  modularization effort.

**Goldfish**
: The traditional Android emulator virtual device platform. Named after the
  original QEMU-based virtual hardware. Being progressively replaced by
  Cuttlefish for cloud testing.

**Gralloc** (Graphics Allocator)
: The HAL responsible for allocating graphical buffers in device memory.
  Split into an `allocator` (allocation) and `mapper` (CPU mapping)
  interface.

**GTS** (Google Test Suite)
: A proprietary test suite run by Google to validate GMS (Google Mobile
  Services) integration on certified devices. Distinct from the
  open-source CTS.

**HAL** (Hardware Abstraction Layer)
: A standardized interface between the Android framework and
  hardware-specific driver code. HALs isolate vendor implementations
  behind stable interfaces (AIDL or legacy HIDL).

**HIDL** (HAL Interface Definition Language)
: The interface definition language used for HALs introduced with Project
  Treble (Android 8.0). Being replaced by AIDL for HALs starting in
  Android 12+.

**HWC** (Hardware Composer)
: The HAL that drives display composition. SurfaceFlinger delegates layer
  composition to HWC, which decides whether to use dedicated hardware
  overlay planes or fall back to GPU composition.

**HWUI**
: Android's hardware-accelerated 2D rendering library. Converts
  `Canvas` drawing commands into GPU operations via a display-list
  architecture backed by Skia. Runs on the dedicated `RenderThread`.

**IME** (Input Method Editor)
: The software keyboard and text input framework. An IME is a special
  service that provides a window for text input, managed by
  `InputMethodManagerService`.

**InputFlinger**
: The native service responsible for reading input events from the kernel
  (`/dev/input/`), processing them, and dispatching them to the correct
  window via `InputDispatcher`.

**Intent**
: Android's message-passing object for requesting actions from components.
  Intents can start activities, services, or broadcast events, and are
  resolved by `PackageManagerService` against registered intent filters.

**ION**
: A legacy Android-specific memory allocator for sharing buffers between
  hardware components. Replaced by the upstream DMA-BUF heaps framework
  in modern kernels.

**JIT** (Just-In-Time compilation)
: Runtime compilation of frequently executed DEX bytecode into native
  machine code. ART's JIT compiler uses profiling data to identify
  hot methods, achieving a balance between startup speed and peak
  performance.

**JNI** (Java Native Interface)
: The standard interface for calling between Java/Kotlin managed code
  and native C/C++ code. ART implements JNI with fast-path optimizations
  and manages the transition between managed and native stacks.

**Kleaf**
: The Bazel-based kernel build system replacing the legacy shell-script
  build. Provides hermetic builds, caching, and better integration with
  the AOSP build system.

**KMI** (Kernel Module Interface)
: The stable ABI between the GKI kernel and vendor-provided kernel
  modules. Allows kernel and vendor modules to be updated independently
  without breaking compatibility.

**LLNDK** (LL-NDK)
: The set of low-level NDK libraries that are available to both the
  platform and vendor partitions. Includes `libc`, `libm`, `liblog`,
  `libbinder_ndk`, and a few others. Stable across Android releases.

**LMKD** (Low Memory Killer Daemon)
: A userspace daemon that monitors memory pressure (via PSI) and kills
  background processes to prevent OOM situations. Replaced the legacy
  in-kernel lowmemorykiller.

**Looper**
: The native event-loop mechanism underlying `Handler` and `MessageQueue`.
  A `Looper` polls file descriptors (including Binder) and dispatches
  messages. Every thread with a `Handler` has a `Looper`.

**Mainline**
: Google's initiative to deliver updates to core OS components via
  Google Play (as APEX or APK modules) independently of full OTA updates.
  Covers ~30+ modules including Wi-Fi, Bluetooth, Media, DNS, and more.

**Microdroid**
: A minimal Android-based guest OS used inside pKVM virtual machines.
  Contains a stripped-down kernel, init, and payload runtime for running
  isolated workloads within AVF.

**MTE** (Memory Tagging Extension)
: An ARM hardware feature that tags memory allocations with metadata
  to detect use-after-free and buffer overflow bugs. Bionic and the
  kernel support MTE on compatible hardware.

**NDK** (Native Development Kit)
: The set of tools, headers, and libraries that allow developers to
  write portions of Android apps in C/C++. The NDK provides a stable
  API surface guaranteed across Android versions.

**NNAPI** (Neural Networks API)
: Android's hardware-abstraction API for machine learning inference.
  Delegates computation to accelerators (GPU, DSP, NPU) via the
  `neuralnetworks` HAL.

**OAT**
: The file format produced by `dex2oat` containing AOT-compiled native
  code alongside the original DEX bytecode. An OAT file is an ELF
  binary loaded by ART at runtime.

**OTA** (Over-The-Air update)
: The mechanism for delivering system updates wirelessly. Android
  supports A/B (seamless) and Virtual A/B update strategies with
  dm-snapshot compression.

**Parcel**
: The serialization container used by Binder to marshal data across
  process boundaries. Supports primitive types, `IBinder` references,
  file descriptors, and `Parcelable` objects.

**pKVM** (Protected Kernel-based Virtual Machine)
: A hypervisor integrated into the Android kernel that provides
  hardware-isolated virtual machines. The foundation of AVF, running
  at EL2 on ARM64 to enforce memory isolation.

**PMS** (PackageManagerService)
: The system service responsible for installing, uninstalling, and
  querying packages. Maintains the package database, resolves intents,
  and manages permissions.

**PSI** (Pressure Stall Information)
: A Linux kernel mechanism that reports the percentage of time tasks
  are stalled waiting for CPU, memory, or I/O resources. LMKD uses
  PSI to make kill decisions.

**RenderEngine**
: SurfaceFlinger's GPU composition backend. Uses Skia (GL or Vulkan) to
  composite layers that HWC cannot handle in hardware. Replaces the
  legacy GLES-based RenderEngine.

**RenderThread**
: A dedicated thread in each Android process that executes GPU drawing
  commands. Decouples GPU work from the main (UI) thread, allowing
  the UI thread to start the next frame while the GPU finishes the
  current one.

**RRO** (Runtime Resource Overlay)
: A mechanism for overlaying resources (layouts, strings, drawables)
  on top of existing packages at runtime without modifying the
  original APK. Used for theming and OEM customization.

**SELinux** (Security-Enhanced Linux)
: The mandatory access control (MAC) system enforced on Android.
  Every process and file has a security context; `sepolicy` rules
  define allowed interactions. Android uses SELinux in enforcing mode.

**Skia**
: The 2D graphics library used throughout Android. Provides `Canvas`
  drawing operations, text rendering, image decoding, and PDF
  generation. Backends include OpenGL, Vulkan (Ganesh), and the
  next-generation Graphite.

**Soong**
: Android's build system that processes `Android.bp` files (Blueprint
  syntax) to generate Ninja build rules. Replaces the legacy
  Make-based build for most modules.

**SurfaceFlinger**
: Android's system compositor. Receives buffers from applications and
  system UI, composites them (via HWC and/or GPU), and presents the
  final frame to the display.

**SystemUI**
: The always-running Android system application that provides the
  status bar, notification shade, quick settings, lock screen,
  navigation bar, volume dialog, and other system chrome.

**TEE** (Trusted Execution Environment)
: A secure processing environment isolated from the main OS. Android
  uses TEE (often ARM TrustZone) for Keymaster/Keymint, Gatekeeper,
  and biometric template storage.

**Tombstone**
: A crash dump file generated when a native process crashes. Contains
  register state, backtrace, memory maps, and other diagnostic
  information. Stored in `/data/tombstones/`.

**TradeFed** (Trade Federation)
: Android's test harness framework used to run CTS, VTS, and other
  test suites. Manages device allocation, test execution, result
  collection, and reporting.

**Treble**
: Google's Android architecture initiative (Android 8.0+) to separate
  the platform framework from vendor-specific HAL implementations.
  Enables faster OS updates by decoupling the vendor partition.

**Trusty**
: Google's open-source TEE operating system. Runs alongside Android in
  a secure world and hosts trusted applications for key management,
  DRM, and secure UI.

**VDEX**
: A file format that stores the original DEX bytecode and verification
  metadata alongside OAT files. Allows ART to re-verify and
  re-optimize DEX code without the original APK.

**VDM** (VirtualDeviceManager)
: System service that creates and manages virtual devices with their
  own displays, input, sensors, and audio. Used for multi-device
  experiences and streaming.

**VINTF** (Vendor Interface)
: The compatibility framework that describes the interface between the
  vendor and platform partitions. `VINTF` manifests declare what HALs
  a device provides and what the framework requires.

**VNDK** (Vendor NDK)
: The set of framework shared libraries available to vendor HAL
  implementations. VNDK snapshots ensure vendor code runs against a
  known set of library versions.

**VSYNC** (Vertical Synchronization)
: The display refresh signal used to synchronize rendering across the
  entire graphics pipeline. Choreographer, SurfaceFlinger, and HWC all
  coordinate around VSYNC events.

**VTS** (Vendor Test Suite)
: A test suite that validates vendor HAL implementations against their
  interface contracts. Ensures Treble compatibility between the
  platform and vendor partitions.

**Vulkan**
: A low-overhead, cross-platform 3D graphics API. Android supports
  Vulkan as an alternative to OpenGL ES, providing explicit control
  over GPU resources, command buffers, and synchronization.

**WMS** (WindowManagerService)
: The system service that manages window placement, z-ordering,
  transitions, and input focus. Works closely with SurfaceFlinger to
  control what is visible on screen.

**Zygote**
: The parent process from which all Android application processes are
  forked. Pre-loads common classes and resources so that new app
  processes start quickly via copy-on-write memory sharing.

---

> **Cross-reference**: Terms are discussed in detail in the chapter indicated
> by each entry's primary topic area. See also **Appendix A** for key source
> file locations.
