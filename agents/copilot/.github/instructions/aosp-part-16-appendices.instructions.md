---
applyTo: '**'
description: 'AOSP Internals — Appendices. Use when looking up a key file path'
---

# Part App.: Appendices

AOSP Internals — Appendices. Use when looking up a key file path
(per-chapter table of the most important AOSP source files: build, init,
kernel, HAL, framework services, system apps, infrastructure) or the
meaning of an AOSP-specific acronym/term (Treble, VINTF, GKI, APEX, AIDL,
HIDL, etc.). Reference material — load when you need a concrete path or
a definition rather than narrative explanation.

## Chapter content

<!-- chapter:A-appendix-key-files -->
# Appendix A: Key Files Reference

This appendix provides a quick-reference table of the most important source files
in AOSP, organized by subsystem and cross-referenced to the chapter where each
file is discussed. Paths are relative to the AOSP root (`$AOSP/`).

---

## Build System (Chapter 2)

| File Path | Purpose |
|-----------|---------|
| `build/make/core/main.mk` | Top-level build entry point; includes all other makefiles |
| `build/make/core/Makefile` | Legacy build rules for images, OTA, packaging |
| `build/make/core/definitions.mk` | Common macro definitions used across the build |
| `build/make/core/envsetup.mk` | Environment variable setup for build configuration |
| `build/make/core/product.mk` | Product-level build variable definitions |
| `build/make/core/product_config.mk` | Product configuration loading and validation |
| `build/make/core/board_config.mk` | Board-level hardware configuration |
| `build/make/core/binary.mk` | Shared rules for building native binaries |
| `build/make/core/tasks/berberis_test.mk` | Build configuration for native bridge testing |
| `build/make/envsetup.sh` | Shell environment setup; defines `lunch`, `m`, `mm`, `mmm` |
| `build/soong/cmd/soong_build/main.go` | Soong build system entry point |
| `build/soong/android/module.go` | Base module type definitions for Soong |
| `build/soong/android/androidmk.go` | Android.mk to Soong conversion logic |
| `build/soong/cc/cc.go` | C/C++ module build rules for Soong |
| `build/soong/cc/library.go` | Shared/static library build rules |
| `build/soong/cc/binary.go` | Native binary build rules |
| `build/soong/cc/config/riscv64_device.go` | RISC-V 64-bit device configuration |
| `build/soong/java/java.go` | Java module build rules for Soong |
| `build/soong/java/app.go` | Android application build rules |
| `build/soong/apex/apex.go` | APEX module build rules |
| `build/blueprint/context.go` | Blueprint core context and dependency resolution |
| `build/blueprint/module_ctx.go` | Module context interface for Blueprint |
| `device/generic/goldfish/board/BoardConfigCommon.mk` | Emulator board configuration (common) |
| `device/google/cuttlefish/vsoc_x86_64/BoardConfig.mk` | Cuttlefish virtual device board config (x86_64) |

## Boot and Init (Chapter 4)

| File Path | Purpose |
|-----------|---------|
| `system/core/init/init.cpp` | PID-1 init process main entry point |
| `system/core/init/service.cpp` | Service lifecycle management (start/stop/restart) |
| `system/core/init/service_parser.cpp` | Parsing of service definitions in .rc files |
| `system/core/init/action.cpp` | Action and trigger execution engine |
| `system/core/init/action_parser.cpp` | Parsing of action blocks in .rc files |
| `system/core/init/property_service.cpp` | System property daemon and persistence |
| `system/core/init/first_stage_init.cpp` | First-stage init before mounting partitions |
| `system/core/init/first_stage_mount.cpp` | Early partition mounting logic |
| `system/core/init/selinux.cpp` | SELinux policy loading during init |
| `system/core/init/ueventd.cpp` | Device node creation daemon |
| `system/core/init/reboot.cpp` | Shutdown and reboot sequencing |
| `system/core/rootdir/init.rc` | Root init script; defines core services and triggers |
| `system/core/rootdir/init.zygote64_32.rc` | Zygote startup configuration (64+32-bit) |
| `system/core/fastboot/fastboot.cpp` | Fastboot protocol host-side implementation |
| `bootable/recovery/recovery.cpp` | Recovery mode main entry point |

## Kernel (Chapter 5)

| File Path | Purpose |
|-----------|---------|
| `kernel/common/Makefile` | Top-level kernel Makefile |
| `kernel/common/arch/arm64/configs/gki_defconfig` | GKI default kernel configuration |
| `kernel/common/drivers/android/binder.c` | Binder kernel driver implementation |
| `kernel/common/drivers/android/binder_alloc.c` | Binder memory allocation |
| `kernel/common/drivers/staging/android/ion/` | ION memory allocator (legacy) |
| `kernel/common/drivers/dma-buf/` | DMA-BUF framework for buffer sharing |
| `kernel/common/drivers/gpu/drm/` | DRM/KMS graphics driver framework |
| `kernel/common/include/uapi/linux/android/binder.h` | Binder UAPI header |
| `kernel/common/fs/fuse/dev.c` | FUSE device implementation (for scoped storage) |
| `kernel/build/build.sh` | Kernel build wrapper script |
| `kernel/build/kleaf/` | Kleaf (Bazel-based) kernel build system |

## Bionic and the Dynamic Linker (Chapter 7)

| File Path | Purpose |
|-----------|---------|
| `bionic/libc/bionic/malloc_common.cpp` | malloc dispatch (jemalloc/scudo selection) |
| `bionic/libc/bionic/pthread_create.cpp` | POSIX thread creation |
| `bionic/libc/bionic/libc_init_dynamic.cpp` | Dynamic-linked process startup |
| `bionic/libc/bionic/libc_init_static.cpp` | Static-linked process startup |
| `bionic/libc/bionic/system_property_api.cpp` | System property client API |
| `bionic/libc/arch-arm64/` | ARM64 architecture-specific code |
| `bionic/libc/include/` | Public C library headers |
| `bionic/linker/linker.cpp` | Dynamic linker main logic |
| `bionic/linker/linker_phdr.cpp` | ELF program header parsing and loading |
| `bionic/linker/linker_namespaces.cpp` | Linker namespace implementation |
| `bionic/linker/linker_soinfo.cpp` | Shared object info management |
| `bionic/linker/linker_config.cpp` | Linker configuration file parsing |
| `system/core/rootdir/etc/ld.config.txt` | Default linker namespace configuration |
| `bionic/libm/` | Math library implementation |
| `bionic/libdl/libdl.cpp` | dlopen/dlsym implementation |

## Binder IPC (Chapter 9)

| File Path | Purpose |
|-----------|---------|
| `frameworks/native/libs/binder/IPCThreadState.cpp` | Per-thread Binder transaction processing |
| `frameworks/native/libs/binder/ProcessState.cpp` | Per-process Binder driver state |
| `frameworks/native/libs/binder/Binder.cpp` | BBinder (local) base class |
| `frameworks/native/libs/binder/BpBinder.cpp` | BpBinder (proxy) base class |
| `frameworks/native/libs/binder/Parcel.cpp` | Data serialization for Binder transactions |
| `frameworks/native/libs/binder/IServiceManager.cpp` | Service manager client interface |
| `frameworks/native/cmds/servicemanager/ServiceManager.cpp` | Service manager daemon |
| `frameworks/native/cmds/servicemanager/main.cpp` | Service manager entry point |
| `frameworks/base/core/java/android/os/Binder.java` | Java-side Binder base class |
| `frameworks/base/core/java/android/os/BinderProxy.java` | Java-side Binder proxy |
| `frameworks/base/core/java/android/os/Parcel.java` | Java-side Parcel |
| `frameworks/base/core/java/android/os/ServiceManager.java` | Java service manager client |
| `frameworks/base/core/jni/android_util_Binder.cpp` | Binder JNI bridge |

## HAL -- Hardware Abstraction Layer (Chapter 10)

| File Path | Purpose |
|-----------|---------|
| `hardware/interfaces/` | Top-level HIDL/AIDL HAL interface directory |
| `hardware/interfaces/audio/aidl/` | Audio HAL AIDL interface definitions |
| `hardware/interfaces/camera/provider/aidl/` | Camera provider HAL interface |
| `hardware/interfaces/graphics/composer/aidl/` | HWC (Hardware Composer) HAL interface |
| `hardware/interfaces/graphics/allocator/aidl/` | Gralloc allocator HAL interface |
| `hardware/interfaces/graphics/mapper/stable-c/` | Gralloc mapper stable-C HAL interface |
| `hardware/interfaces/health/aidl/` | Battery/health HAL interface |
| `hardware/interfaces/sensors/aidl/` | Sensors HAL interface |
| `hardware/interfaces/neuralnetworks/aidl/` | NNAPI HAL interface |
| `hardware/interfaces/power/aidl/` | Power HAL interface |
| `hardware/interfaces/thermal/aidl/` | Thermal HAL interface |
| `hardware/interfaces/bluetooth/aidl/` | Bluetooth HAL interface |
| `hardware/interfaces/wifi/aidl/` | Wi-Fi HAL interface |
| `hardware/interfaces/vibrator/aidl/` | Vibrator HAL interface |
| `hardware/libhardware/include/hardware/hardware.h` | Legacy HAL module interface (hw_module_t) |
| `system/libhidl/transport/HidlTransportSupport.cpp` | HIDL transport initialization |
| `system/tools/hidl/` | HIDL compiler (hidl-gen) |
| `system/tools/aidl/` | AIDL compiler for HAL interfaces |

## NDK -- Native Development Kit (Chapter 11)

| File Path | Purpose |
|-----------|---------|
| `frameworks/native/include/android/` | Public NDK native headers |
| `frameworks/native/libs/nativewindow/include/android/native_window.h` | ANativeWindow API |
| `frameworks/native/include/android/native_activity.h` | NativeActivity API |
| `frameworks/native/include/android/sensor.h` | Sensor NDK API |
| `frameworks/native/include/android/asset_manager.h` | Asset manager NDK API |
| `frameworks/av/media/ndk/` | Media NDK implementation (AMediaCodec, etc.) |
| `packages/modules/NeuralNetworks/runtime/` | NNAPI runtime implementation |
| `frameworks/native/libs/nativewindow/` | ANativeWindow implementation |

## Native Services (Chapter 12)

| File Path | Purpose |
|-----------|---------|
| `frameworks/native/services/inputflinger/InputDispatcher.cpp` | Input event dispatch to windows |
| `frameworks/native/services/inputflinger/InputReader.cpp` | Input device event reading |
| `frameworks/native/services/inputflinger/InputManager.cpp` | Input subsystem coordinator |
| `frameworks/native/services/sensorservice/SensorService.cpp` | Sensor event multiplexing |
| `frameworks/native/services/surfaceflinger/main_surfaceflinger.cpp` | SurfaceFlinger process entry point |
| `system/logging/logd/SerializedLogBuffer.cpp` | System log ring buffer |
| `system/memory/lmkd/lmkd.cpp` | Low memory killer daemon |
| `system/memory/lmkd/` | Modern LMKD implementation |
| `system/core/healthd/` | Battery/health daemon |
| `system/netd/server/NetdNativeService.cpp` | Network daemon native service |

## Graphics and Render Pipeline (Chapter 13)

| File Path | Purpose |
|-----------|---------|
| `frameworks/native/services/surfaceflinger/SurfaceFlinger.cpp` | Compositor main class |
| `frameworks/native/services/surfaceflinger/SurfaceFlinger.h` | SurfaceFlinger declarations |
| `frameworks/native/services/surfaceflinger/Scheduler/Scheduler.cpp` | VSYNC scheduling and frame pacing |
| `frameworks/native/services/surfaceflinger/Scheduler/VsyncController.cpp` | VSYNC signal generation |
| `frameworks/native/services/surfaceflinger/CompositionEngine/` | Composition strategy engine |
| `frameworks/native/services/surfaceflinger/DisplayHardware/HWComposer.cpp` | HWC abstraction layer |
| `frameworks/native/services/surfaceflinger/DisplayHardware/PowerAdvisor.cpp` | Power hint integration |
| `frameworks/native/services/surfaceflinger/Layer.cpp` | Individual surface/layer management |
| `frameworks/native/services/surfaceflinger/BufferLayer.cpp` | Buffer-backed layer implementation |
| `frameworks/native/services/surfaceflinger/FrontEnd/LayerLifecycleManager.cpp` | Layer lifecycle tracking |
| `frameworks/native/services/surfaceflinger/Tracing/TransactionTracing.cpp` | Transaction trace capture |
| `frameworks/native/libs/gui/Surface.cpp` | Client-side Surface implementation |
| `frameworks/native/libs/gui/BufferQueue.cpp` | Producer-consumer buffer queue |
| `frameworks/native/libs/gui/BufferQueueProducer.cpp` | Buffer queue producer side |
| `frameworks/native/libs/gui/BufferQueueConsumer.cpp` | Buffer queue consumer side |
| `frameworks/native/libs/gui/SurfaceComposerClient.cpp` | SurfaceFlinger client interface |
| `frameworks/native/libs/gui/BLASTBufferQueue.cpp` | BLAST buffer queue (modern path) |
| `frameworks/native/libs/renderengine/skia/SkiaGLRenderEngine.cpp` | Skia-based GPU composition |
| `frameworks/native/libs/renderengine/skia/SkiaVkRenderEngine.cpp` | Skia Vulkan render engine |
| `frameworks/native/opengl/libs/EGL/eglApi.cpp` | EGL API entry points |
| `frameworks/native/opengl/libs/EGL/Loader.cpp` | EGL driver loader |
| `frameworks/native/vulkan/libvulkan/driver.cpp` | Vulkan loader/driver interface |
| `frameworks/native/vulkan/libvulkan/api.cpp` | Vulkan API dispatch |
| `external/skia/src/gpu/ganesh/GrDirectContext.cpp` | Skia GPU context |
| `external/skia/src/gpu/graphite/` | Skia Graphite (next-gen GPU backend) |
| `frameworks/base/libs/hwui/renderthread/RenderThread.cpp` | HWUI render thread |
| `frameworks/base/libs/hwui/renderthread/CanvasContext.cpp` | Per-window render context |
| `frameworks/base/libs/hwui/pipeline/skia/SkiaOpenGLPipeline.cpp` | Skia GL rendering pipeline |
| `frameworks/base/libs/hwui/pipeline/skia/SkiaVulkanPipeline.cpp` | Skia Vulkan rendering pipeline |
| `frameworks/base/libs/hwui/RenderNode.cpp` | Display list render node |
| `frameworks/base/libs/hwui/RecordingCanvas.cpp` | Display list recording canvas |
| `frameworks/base/libs/hwui/DamageAccumulator.cpp` | Dirty region tracking |
| `frameworks/base/libs/hwui/JankTracker.cpp` | Frame jank detection and reporting |
| `frameworks/base/graphics/java/android/graphics/Canvas.java` | Java Canvas API |
| `frameworks/base/graphics/java/android/graphics/RenderNode.java` | Java RenderNode API |
| `frameworks/base/core/java/android/view/Choreographer.java` | VSYNC-based callback scheduler |
| `frameworks/base/core/java/android/view/ViewRootImpl.java` | View hierarchy root; drives measure/layout/draw |
| `frameworks/base/core/java/android/view/ThreadedRenderer.java` | Java bridge to HWUI RenderThread |

## Animation System (Chapter 14)

| File Path | Purpose |
|-----------|---------|
| `frameworks/base/core/java/android/animation/ValueAnimator.java` | Core property animation engine |
| `frameworks/base/core/java/android/animation/ObjectAnimator.java` | Property-targeted animation |
| `frameworks/base/core/java/android/animation/AnimatorSet.java` | Coordinated animation sequencing |
| `frameworks/base/core/java/android/view/animation/Animation.java` | Legacy view animation base class |
| `frameworks/base/core/java/android/transition/TransitionManager.java` | Scene transition framework |
| `frameworks/base/core/java/android/window/TransitionInfo.java` | Shell transition metadata |
| `frameworks/libs/systemui/animationlib/src/` | SystemUI shared animation library |

## Audio System (Chapter 15)

| File Path | Purpose |
|-----------|---------|
| `frameworks/av/services/audioflinger/AudioFlinger.cpp` | Audio mixing daemon main class |
| `frameworks/av/services/audioflinger/Threads.cpp` | Playback and record thread implementations |
| `frameworks/av/services/audioflinger/Tracks.cpp` | Audio track management |
| `frameworks/av/services/audioflinger/Effects.cpp` | Audio effects chain processing |
| `frameworks/av/services/audiopolicy/managerdefault/AudioPolicyManager.cpp` | Audio routing policy |
| `frameworks/av/services/audiopolicy/common/managerdefinitions/src/AudioPort.cpp` | Audio port abstraction |
| `frameworks/av/media/libaudioclient/AudioTrack.cpp` | Client-side audio playback |
| `frameworks/av/media/libaudioclient/AudioRecord.cpp` | Client-side audio recording |
| `frameworks/av/media/libaudioclient/AudioSystem.cpp` | Audio system client interface |
| `frameworks/av/media/libaudiohal/impl/DeviceHalAidl.cpp` | Audio device HAL AIDL adapter |
| `frameworks/base/media/java/android/media/AudioTrack.java` | Java audio playback API |
| `frameworks/base/services/core/java/com/android/server/audio/AudioService.java` | Audio service (volume, routing) |

## Media and Video Pipeline (Chapter 16)

| File Path | Purpose |
|-----------|---------|
| `frameworks/av/media/libmediaplayerservice/MediaPlayerService.cpp` | Media player daemon |
| `frameworks/av/media/codec2/sfplugin/CCodec.cpp` | Codec2 framework plugin |
| `frameworks/av/media/codec2/sfplugin/CCodecBufferChannel.cpp` | Codec2 buffer management |
| `frameworks/av/media/codec2/components/` | Software codec implementations |
| `frameworks/av/media/libstagefright/MediaCodec.cpp` | MediaCodec native implementation |
| `frameworks/av/media/libstagefright/ACodec.cpp` | Legacy OMX codec adapter |
| `frameworks/av/media/libstagefright/NuPlayer/NuPlayer.cpp` | Media playback engine |
| `frameworks/av/media/module/extractors/` | Media file format extractors (MP4, MKV, etc.) |
| `frameworks/av/services/camera/libcameraservice/CameraService.cpp` | Camera service daemon |
| `frameworks/av/drm/mediadrm/plugins/clearkey/` | ClearKey DRM reference implementation |
| `frameworks/base/media/java/android/media/MediaCodec.java` | Java MediaCodec API |
| `frameworks/base/media/java/android/media/MediaPlayer.java` | Java MediaPlayer API |

## ART Runtime (Chapter 18)

| File Path | Purpose |
|-----------|---------|
| `art/runtime/runtime.cc` | ART runtime initialization |
| `art/runtime/class_linker.cc` | Class loading and linking |
| `art/runtime/interpreter/interpreter.cc` | Bytecode interpreter entry point |
| `art/runtime/jit/jit.cc` | JIT compiler coordinator |
| `art/runtime/jit/jit_code_cache.cc` | JIT compiled code cache |
| `art/runtime/gc/heap.cc` | Garbage collector heap management |
| `art/runtime/gc/collector/concurrent_copying.cc` | Concurrent copying GC |
| `art/runtime/thread.cc` | Thread management |
| `art/runtime/oat/oat_file.cc` | OAT file format handling |
| `art/runtime/mirror/object.h` | Root object type for managed heap |
| `art/runtime/mirror/class.h` | Class metadata representation |
| `art/compiler/optimizing/optimizing_compiler.cc` | AOT/JIT optimizing compiler |
| `art/compiler/optimizing/code_generator_arm64.cc` | ARM64 code generation backend |
| `art/compiler/optimizing/register_allocator_linear_scan.cc` | Register allocation |
| `art/dex2oat/dex2oat.cc` | Ahead-of-time compilation tool |
| `art/dex2oat/dex2oat_options.cc` | DEX-to-OAT compilation options |
| `art/libdexfile/dex/dex_file.h` | DEX file format definitions |
| `art/runtime/native_bridge_art_interface.cc` | ART-side native bridge integration |

## Native Bridge and Binary Translation (Chapter 19)

| File Path | Purpose |
|-----------|---------|
| `frameworks/libs/binary_translation/native_bridge/native_bridge.h` | NativeBridgeCallbacks interface (v3-v8) |
| `frameworks/libs/binary_translation/native_bridge/native_bridge.cc` | Native bridge framework implementation |
| `frameworks/libs/binary_translation/guest_loader/` | Guest library loading and linking |
| `frameworks/libs/binary_translation/guest_abi/` | ABI conversion between host and guest |
| `frameworks/libs/binary_translation/guest_state/` | Guest CPU state abstraction |
| `frameworks/libs/binary_translation/jni/` | JNI trampoline generation |
| `frameworks/libs/binary_translation/interpreter/` | Guest instruction interpreter |
| `frameworks/libs/binary_translation/decoder/` | Guest instruction decoder |
| `frameworks/libs/binary_translation/backend/` | Host code generation backend |
| `frameworks/libs/binary_translation/assembler/` | Host instruction assembler |
| `frameworks/libs/binary_translation/android_api/` | Android framework proxy stubs |
| `frameworks/libs/native_bridge_support/native_bridge_support.mk` | Build synchronization for bridge support |
| `art/libnativebridge/native_bridge.cc` | System-side native bridge loading |

## system_server (Chapter 20)

| File Path | Purpose |
|-----------|---------|
| `frameworks/base/services/java/com/android/server/SystemServer.java` | system_server boot sequence |
| `frameworks/base/services/core/java/com/android/server/SystemServiceManager.java` | Service lifecycle manager |
| `frameworks/base/services/core/java/com/android/server/am/ActivityManagerService.java` | Activity Manager Service |
| `frameworks/base/services/core/java/com/android/server/wm/WindowManagerService.java` | Window Manager Service |
| `frameworks/base/services/core/java/com/android/server/wm/ActivityTaskManagerService.java` | Activity Task Manager Service |
| `frameworks/base/services/core/java/com/android/server/pm/PackageManagerService.java` | Package Manager Service |
| `frameworks/base/services/core/java/com/android/server/power/PowerManagerService.java` | Power management |
| `frameworks/base/services/core/java/com/android/server/display/DisplayManagerService.java` | Display management |
| `frameworks/base/services/core/java/com/android/server/input/InputManagerService.java` | Input management bridge |
| `frameworks/base/core/java/com/android/internal/os/ZygoteInit.java` | Zygote process initialization |
| `frameworks/base/core/java/com/android/internal/os/ZygoteConnection.java` | Zygote fork request handling |
| `frameworks/base/core/java/com/android/internal/os/Zygote.java` | Zygote fork mechanics |
| `frameworks/base/core/java/com/android/internal/os/RuntimeInit.java` | App process runtime initialization |

## Activity and Window Management (Chapter 22)

| File Path | Purpose |
|-----------|---------|
| `frameworks/base/services/core/java/com/android/server/wm/Task.java` | Task (back stack) container |
| `frameworks/base/services/core/java/com/android/server/wm/ActivityRecord.java` | Per-activity state tracking |
| `frameworks/base/services/core/java/com/android/server/wm/ActivityStarter.java` | Intent resolution and activity start |
| `frameworks/base/services/core/java/com/android/server/wm/ActivityClientController.java` | Activity lifecycle IPC handler |
| `frameworks/base/services/core/java/com/android/server/wm/RootWindowContainer.java` | Root of the window hierarchy |
| `frameworks/base/services/core/java/com/android/server/wm/TaskFragment.java` | Activity embedding container |
| `frameworks/base/core/java/android/app/Activity.java` | Application-side activity base class |
| `frameworks/base/core/java/android/app/ActivityThread.java` | Main thread of every Android app |
| `frameworks/base/core/java/android/app/Instrumentation.java` | Activity lifecycle instrumentation hooks |

## Window System (Chapter 23)

| File Path | Purpose |
|-----------|---------|
| `frameworks/base/services/core/java/com/android/server/wm/WindowState.java` | Per-window server state |
| `frameworks/base/services/core/java/com/android/server/wm/WindowToken.java` | Window grouping token |
| `frameworks/base/services/core/java/com/android/server/wm/Session.java` | Per-app WMS session |
| `frameworks/base/services/core/java/com/android/server/wm/WindowSurfaceController.java` | Window-to-Surface bridge |
| `frameworks/base/services/core/java/com/android/server/wm/WindowAnimator.java` | Window animation coordinator |
| `frameworks/base/services/core/java/com/android/server/wm/InsetsStateController.java` | System insets management |
| `frameworks/base/services/core/java/com/android/server/wm/InsetsPolicy.java` | Insets visibility policy |
| `frameworks/base/core/java/android/view/WindowManager.java` | Client window manager interface |
| `frameworks/base/core/java/android/view/WindowManagerImpl.java` | Window manager implementation |
| `frameworks/base/core/java/android/view/View.java` | Base UI component (measure/layout/draw) |
| `frameworks/base/core/java/android/view/ViewGroup.java` | Container for child views |
| `frameworks/base/core/java/android/view/SurfaceView.java` | Separate-surface view component |

## Display System (Chapter 24)

| File Path | Purpose |
|-----------|---------|
| `frameworks/base/services/core/java/com/android/server/wm/DisplayContent.java` | Per-display window container |
| `frameworks/base/services/core/java/com/android/server/wm/DisplayPolicy.java` | Per-display window policy (bars, cutouts) |
| `frameworks/base/services/core/java/com/android/server/wm/DisplayRotation.java` | Display rotation handling |
| `frameworks/base/services/core/java/com/android/server/display/LogicalDisplay.java` | Logical display abstraction |
| `frameworks/base/services/core/java/com/android/server/display/DisplayDeviceInfo.java` | Physical display properties |
| `frameworks/base/services/core/java/com/android/server/display/LocalDisplayAdapter.java` | Built-in display adapter |

## PackageManagerService (Chapter 26)

| File Path | Purpose |
|-----------|---------|
| `frameworks/base/services/core/java/com/android/server/pm/PackageManagerService.java` | Package management core |
| `frameworks/base/services/core/java/com/android/server/pm/Settings.java` | Package settings persistence |
| `frameworks/base/services/core/java/com/android/server/pm/InstallPackageHelper.java` | Package installation logic |
| `frameworks/base/services/core/java/com/android/server/pm/PackageInstallerService.java` | Installer session management |
| `frameworks/base/services/core/java/com/android/server/pm/permission/PermissionManagerService.java` | Runtime permission management |
| `frameworks/base/services/core/java/com/android/server/pm/pkg/parsing/ParsingPackageUtils.java` | APK manifest parsing |
| `frameworks/base/services/core/java/com/android/server/pm/resolution/ComponentResolver.java` | Intent filter resolution |
| `frameworks/base/services/core/java/com/android/server/pm/dex/DexManager.java` | DEX file optimization tracking |
| `frameworks/base/core/java/android/content/pm/PackageManager.java` | Public PackageManager API |

## Security (Chapter 40)

| File Path | Purpose |
|-----------|---------|
| `system/sepolicy/public/` | Public SELinux policy definitions |
| `system/sepolicy/private/` | Private (platform) SELinux policy |
| `system/sepolicy/vendor/` | Vendor SELinux policy |
| `system/security/keystore2/` | Keystore2 service (Rust) |
| `system/security/identity/` | Identity credential service |
| `external/selinux/` | SELinux userspace tools |
| `system/extras/verity/` | dm-verity tools |
| `system/core/fs_mgr/libfs_avb/` | AVB (Android Verified Boot) integration |
| `frameworks/base/services/core/java/com/android/server/biometrics/` | Biometric authentication |
| `frameworks/base/keystore/java/android/security/keystore2/` | Keystore Java API |

## SystemUI (Chapter 47)

| File Path | Purpose |
|-----------|---------|
| `frameworks/base/packages/SystemUI/src/com/android/systemui/SystemUIApplication.java` | SystemUI application entry |
| `frameworks/base/packages/SystemUI/src/com/android/systemui/statusbar/phone/CentralSurfacesImpl.java` | Status bar + notification shade |
| `frameworks/base/packages/SystemUI/src/com/android/systemui/qs/QSPanelController.java` | Quick Settings panel controller |
| `frameworks/base/packages/SystemUI/src/com/android/systemui/recents/OverviewProxyService.java` | Recents/overview proxy to Launcher |
| `frameworks/base/packages/SystemUI/src/com/android/systemui/keyguard/KeyguardViewMediator.java` | Lock screen coordinator |
| `frameworks/base/packages/SystemUI/src/com/android/systemui/navigationbar/NavigationBar.java` | Navigation bar |
| `frameworks/base/packages/SystemUI/src/com/android/systemui/volume/VolumeDialogControllerImpl.java` | Volume dialog logic |
| `frameworks/base/packages/SystemUI/src/com/android/systemui/shade/NotificationPanelViewController.java` | Notification panel controller |

## Launcher3 (Chapter 48)

| File Path | Purpose |
|-----------|---------|
| `packages/apps/Launcher3/src/com/android/launcher3/Launcher.java` | Main Launcher activity |
| `packages/apps/Launcher3/src/com/android/launcher3/Workspace.java` | Home screen workspace |
| `packages/apps/Launcher3/src/com/android/launcher3/allapps/AllAppsContainerView.java` | All-apps drawer |
| `packages/apps/Launcher3/src/com/android/launcher3/model/LoaderTask.java` | App list loading |
| `packages/apps/Launcher3/src/com/android/launcher3/dragndrop/DragController.java` | Drag-and-drop coordinator |
| `packages/apps/Launcher3/quickstep/src/com/android/quickstep/RecentsActivity.java` | Recents (overview) activity |
| `packages/apps/Launcher3/quickstep/src/com/android/quickstep/TouchInteractionService.java` | Gesture navigation service |

## Settings App (Chapter 49)

| File Path | Purpose |
|-----------|---------|
| `packages/apps/Settings/src/com/android/settings/Settings.java` | Main Settings activity |
| `packages/apps/Settings/src/com/android/settings/dashboard/DashboardFragment.java` | Preference dashboard base |
| `packages/apps/Settings/src/com/android/settings/search/SearchFeatureProvider.java` | Settings search |
| `packages/apps/Settings/src/com/android/settings/biometrics/` | Biometrics enrollment |

## CompanionDeviceManager and Virtual Devices (Chapter 51)

| File Path | Purpose |
|-----------|---------|
| `frameworks/base/services/companion/java/com/android/server/companion/CompanionDeviceManagerService.java` | CDM service |
| `frameworks/base/services/companion/java/com/android/server/companion/virtual/VirtualDeviceManagerService.java` | VDM service |

## Mainline Modules (Chapter 52)

| File Path | Purpose |
|-----------|---------|
| `packages/modules/Wifi/` | Wi-Fi Mainline module |
| `packages/modules/Bluetooth/` | Bluetooth Mainline module |
| `packages/modules/NetworkStack/` | Network stack Mainline module |
| `packages/modules/Permission/` | Permission controller module |
| `packages/modules/MediaProvider/` | Media storage provider module |
| `packages/modules/adb/` | ADB Mainline module |
| `packages/modules/common/` | Shared Mainline module infrastructure |
| `system/apex/apexd/` | APEX daemon (module installer) |
| `system/apex/apexd/apexd.cpp` | APEX installation and activation |
| `system/apex/libs/libapexutil/` | APEX utility library |

## Virtualization Framework (Chapter 54)

| File Path | Purpose |
|-----------|---------|
| `packages/modules/Virtualization/` | Android Virtualization Framework top-level |
| `packages/modules/Virtualization/android/virtualizationservice/` | VM lifecycle management |
| `packages/modules/Virtualization/build/microdroid/` | Minimal guest OS (Microdroid) build files |
| `packages/modules/Virtualization/guest/pvmfw/` | Protected VM firmware |
| `packages/modules/Virtualization/libs/libvm_payload/` | Guest payload interface |

## Testing (Chapter 55)

| File Path | Purpose |
|-----------|---------|
| `test/vts/` | Vendor Test Suite top-level |
| `cts/tests/` | Compatibility Test Suite tests |
| `tools/tradefederation/core/` | Trade Federation test harness core |
| `tools/tradefederation/core/src/com/android/tradefed/` | TradeFed framework classes |
| `platform_testing/tests/` | Platform integration tests |
| `frameworks/base/core/tests/` | Framework core unit tests |
| `frameworks/base/test-runner/` | Android test runner framework |

## Architecture Support (Chapter 57)

| File Path | Purpose |
|-----------|---------|
| `build/soong/cc/config/arm64_device.go` | ARM64 toolchain: arch variants, CPU tuning, PAC/BTI |
| `build/soong/cc/config/arm_device.go` | ARM 32-bit toolchain: Thumb/ARM, errata workarounds |
| `build/soong/cc/config/x86_device.go` | x86 32-bit toolchain: SSE, stack realignment |
| `build/soong/cc/config/x86_64_device.go` | x86_64 toolchain: microarchitecture variants |
| `build/soong/cc/config/riscv64_device.go` | RISC-V 64-bit toolchain: ISA extensions |
| `build/soong/cc/config/toolchain.go` | Toolchain interface and factory registry |
| `build/soong/cc/config/global.go` | Global compiler/linker flags for all architectures |
| `build/soong/cc/config/bionic.go` | Bionic CRT objects and default shared libraries |
| `build/soong/cc/config/clang.go` | Clang unknown-flags filter |
| `build/soong/android/arch.go` | Arch struct, ArchType, multilib decode logic |
| `bionic/libc/arch-arm64/ifuncs.cpp` | ARM64 ifunc dispatchers (MTE, SVE selection) |
| `art/runtime/arch/riscv64/instruction_set_features_riscv64.h` | ART RISC-V feature detection |
| `art/runtime/arch/arm64/instruction_set_features_arm64.h` | ART ARM64 feature bitmap and errata |

## Emulator (Chapter 58)

| File Path | Purpose |
|-----------|---------|
| `external/qemu/android/emulation/` | Emulator core emulation logic |
| `external/qemu/android/android-emu/android/emulation/` | Emulator hardware emulation |
| `device/generic/goldfish/` | Goldfish virtual device definitions |
| `device/google/cuttlefish/` | Cuttlefish virtual device definitions |
| `device/google/cuttlefish/host/commands/run_cvd/` | Cuttlefish launcher |
| `external/crosvm/` | CrosVM virtual machine monitor |
| `external/qemu/android/android-grpc/` | Emulator gRPC control interface |

## Automotive, TV, and Wear (Chapter 60)

| File Path | Purpose |
|-----------|---------|
| `packages/services/Car/` | Android Automotive service layer |
| `packages/services/Car/service/src/com/android/car/CarServiceImpl.java` | Automotive car service |
| `packages/apps/Car/Launcher/` | Automotive launcher |
| `device/google/atv/` | Android TV device configuration |
| `packages/apps/TvSettings/` | TV settings application |
| `prebuilts/sdk/opt/wear/` | Wear OS SDK prebuilts |

---

> **Note**: Paths may shift between AOSP branches. The paths above target AOSP
> `main` as of early 2026. Use `find` or `cs.android.com` to verify against your
> checked-out branch.

<!-- chapter:B-appendix-glossary -->
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

