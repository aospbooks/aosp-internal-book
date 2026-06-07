---
applyTo: '**'
description: 'AOSP Part XV — Practical. Use when reasoning about building a custom AOSP'
---

# Part XV: Practical

AOSP Part XV — Practical. Use when reasoning about building a custom AOSP
ROM end-to-end: picking a target device, syncing source, applying vendor
blobs, branding, building, flashing the resulting images, and shipping
OTA updates on your own channel. Chapter 63 (Custom ROM Guide).

## Chapter content

<!-- chapter:63-custom-rom -->
# Chapter 63: Custom ROM Guide

This chapter is the capstone of the book. We take everything covered in the
preceding 62 chapters -- build system, init, HALs, system services, SystemUI,
the emulator, security, signing -- and weave it into a single, end-to-end
walkthrough: building, customizing, signing, and distributing a fully
functional custom ROM.

Our target device is the AOSP Goldfish emulator (`sdk_phone64_x86_64`). This is
a deliberate choice: every reader of this book has access to a laptop or
workstation that can run the emulator, no physical hardware required. Everything
we build here -- custom device trees, overlays, apps, services, boot
animations, kernel tweaks, HAL modifications -- applies equally to a physical
device; only the `BoardConfig.mk` and kernel binaries change.

Every file path, every command, and every code snippet in this chapter was
verified against the AOSP source tree.
Where we quote source files we give their full tree-relative path so you can
follow along on your own checkout.

---

## 63.1 Planning Your Custom ROM

### 63.1.1 What Is a "Custom ROM"?

A custom ROM is a modified build of Android that changes one or more of the
following layers:

| Layer | Examples | Complexity |
|-------|----------|------------|
| Product configuration | Branding, default apps, wallpapers | Low |
| Resource overlays | Status bar color, quick settings layout, config flags | Low |
| Prebuilt apps | Adding/removing bundled APKs | Low |
| Framework behavior | New system services, modified APIs | Medium |
| SystemUI | Custom status bar, navigation, theming | Medium |
| Boot animation | Custom splash screen | Low |
| Kernel | Custom modules, scheduler tuning | High |
| HAL | Custom hardware abstraction layers | High |
| Signing and distribution | Release keys, OTA packages | Medium |

The popular community ROMs (LineageOS, /e/OS, GrapheneOS, CalyxOS, PixelExperience)
each combine customizations across all of these layers. In this chapter we will
touch every layer.

### 63.1.2 Defining Your ROM's Goals

Before writing any code, answer these questions:

1. **What is the purpose?** Privacy-focused? Performance-optimized? Enterprise
   management? Learning exercise?

2. **What devices will you target?** We use the emulator (`goldfish`/`ranchu`);
   real devices require vendor blobs and kernel sources.

3. **What Android version?** We build from AOSP `main` (currently targeting
   Android 16, API level 36).

4. **What is the branding?** Custom ROM name, model string, build fingerprint.
5. **What apps ship by default?** Which AOSP apps to keep, which to remove,
   which third-party APKs to add?

6. **What framework changes?** New services, modified behavior, config changes.

### 63.1.3 The ROM We Will Build

Throughout this chapter we build **"AospBook ROM"** -- a custom ROM that
includes:

- A custom device configuration inheriting from Goldfish
- Custom branding (product name, model, build fingerprint)
- A prebuilt third-party app
- A custom-built sample app included in the system image
- A Runtime Resource Overlay changing framework and SystemUI defaults
- A custom system service accessible via AIDL
- A custom boot animation
- SystemUI theme modifications
- Custom signing keys
- An OTA update package
- A custom kernel module
- A custom HAL implementation

### 63.1.4 Architecture Overview

```mermaid
graph TD
    subgraph "AospBook ROM Architecture"
        A[device/AospBook/bookphone] --> B[AndroidProducts.mk]
        A --> C[device.mk]
        A --> D[BoardConfig.mk]
        A --> E[overlay/]
        A --> F[apps/]
        A --> G[services/]
        A --> H[bootanimation/]
        A --> I[sepolicy/]
        A --> J[hal/]

        C --> K["Inherits: device/generic/goldfish"]
        C --> L["PRODUCT_PACKAGES += ..."]
        C --> M["PRODUCT_COPY_FILES += ..."]

        D --> N["Inherits: BoardConfigCommon.mk"]

        E --> O["Framework RRO"]
        E --> P["SystemUI RRO"]

        F --> Q["Prebuilt APKs"]
        F --> R["Custom-built apps"]

        G --> S["BookService (AIDL)"]
    end
```

### 63.1.5 Directory Layout

Here is the directory tree we will create over the course of this chapter:

```
device/AospBook/bookphone/
    AndroidProducts.mk
    bookphone.mk                  # product makefile
    BoardConfig.mk
    device.mk                     # device-level config
    overlay/
        frameworks/
            base/
                core/res/res/values/config.xml
        BookSystemUIOverlay/
            AndroidManifest.xml
            Android.bp
            res/values/config.xml
    apps/
        BookSampleApp/
            Android.bp
            AndroidManifest.xml
            src/...
            res/...
        prebuilt/
            BookReader/
                Android.bp
                BookReader.apk
    services/
        BookService/
            Android.bp
            aidl/...
            src/...
    bootanimation/
        desc.txt
        part0/
        part1/
    hal/
        booklight/
            Android.bp
            aidl/...
            default/...
    sepolicy/
        vendor/
            file_contexts
            bookservice.te
            booklight.te
    keys/
        releasekey.pk8
        releasekey.x509.pem
        platform.pk8
        platform.x509.pem
        shared.pk8
        shared.x509.pem
        media.pk8
        media.x509.pem
```

---

## 63.2 Setting Up the Build Environment

### 63.2.1 Hardware Requirements

Building AOSP is resource-intensive. Here are the requirements:

| Resource | Minimum | Recommended | Our Setup |
|----------|---------|-------------|-----------|
| Disk (source) | 250 GB | 400 GB | 500 GB SSD |
| Disk (with build) | 400 GB | 600 GB+ | 1 TB NVMe |
| RAM | 32 GB | 64 GB+ | 64 GB |
| CPU cores | 4 | 16+ | 16 cores |
| OS | Ubuntu 20.04+ | Ubuntu 22.04 LTS | Ubuntu 22.04 |
| File system | ext4 (case-sensitive) | ext4 | ext4 |

The build is highly parallel. Each additional core shaves minutes off a full
build. RAM is the second most important factor -- the linker (`lld`) and
javac/d8 compilation stages can consume 2-4 GB per parallel job.

### 63.2.2 Required Packages (Ubuntu/Debian)

The AOSP build system depends on a specific set of host packages. Install
them all with:

```bash
# Update package lists
sudo apt-get update

# Essential build packages
sudo apt-get install -y \
    git-core gnupg flex bison build-essential \
    zip curl zlib1g-dev libc6-dev-i386 \
    x11proto-core-dev libx11-dev lib32z1-dev \
    libgl1-mesa-dev libxml2-utils xsltproc unzip \
    fontconfig libncurses5 procps python3 python3-pip \
    rsync libssl-dev

# For 64-bit hosts running 32-bit prebuilts
sudo apt-get install -y \
    lib32ncurses-dev lib32readline-dev lib32z1-dev

# For emulator GPU acceleration
sudo apt-get install -y \
    libvulkan-dev mesa-vulkan-drivers \
    libpulse0 libgl1

# For kernel building (if needed)
sudo apt-get install -y \
    bc cpio kmod libelf-dev

# Python dependencies (some build scripts require specific versions)
sudo apt-get install -y \
    python3-protobuf python3-setuptools
```

### 63.2.3 Installing the `repo` Tool

The `repo` tool orchestrates Git across the hundreds of AOSP repositories:

```bash
# Create a bin directory in your home directory
mkdir -p ~/bin

# Download the repo launcher
curl https://storage.googleapis.com/git-repo-downloads/repo > ~/bin/repo

# Make it executable
chmod a+x ~/bin/repo

# Add to PATH (add to ~/.bashrc for persistence)
export PATH=~/bin:$PATH

# Verify installation
repo version
```

The `repo` launcher is a Python script that bootstraps the full `repo` tool
from Google's repository. It requires Python 3.6+.

### 63.2.4 Initializing the AOSP Tree

```bash
# Create your working directory
mkdir -p ~/aosp && cd ~/aosp

# Initialize the repo with the main branch
repo init -u https://android.googlesource.com/platform/manifest \
    -b main \
    --partial-clone \
    --clone-filter=blob:limit=10M

# Sync all repositories (this takes 1-3 hours on a fast connection)
repo sync -c -j$(nproc) --no-tags --no-clone-bundle
```

Key flags explained:

| Flag | Purpose |
|------|---------|
| `-b main` | Track the `main` development branch |
| `--partial-clone` | Enable Git partial clone (saves disk) |
| `--clone-filter=blob:limit=10M` | Only download blobs under 10 MB initially |
| `-c` | Sync only the current branch |
| `-j$(nproc)` | Parallelize across all CPU cores |
| `--no-tags` | Skip Git tags (saves time/space) |
| `--no-clone-bundle` | Skip bundle files (sometimes faster) |

### 63.2.5 Complete Setup Script

Here is a complete, idempotent setup script you can run on a fresh Ubuntu 22.04
machine:

```bash
#!/bin/bash
# setup_aosp_build_env.sh -- Complete AOSP build environment setup
# Usage: sudo ./setup_aosp_build_env.sh

set -euo pipefail

echo "=== AOSP Build Environment Setup ==="

# 1. System packages
echo "[1/6] Installing system packages..."
apt-get update -qq
apt-get install -y -qq \
    git-core gnupg flex bison build-essential \
    zip curl zlib1g-dev libc6-dev-i386 \
    x11proto-core-dev libx11-dev lib32z1-dev \
    libgl1-mesa-dev libxml2-utils xsltproc unzip \
    fontconfig libncurses5 procps python3 python3-pip \
    rsync libssl-dev bc cpio kmod libelf-dev \
    lib32ncurses-dev lib32readline-dev lib32z1-dev \
    python3-protobuf python3-setuptools \
    libvulkan-dev mesa-vulkan-drivers libpulse0 libgl1 \
    openjdk-21-jdk

# 2. Set up Java
echo "[2/6] Configuring Java..."
update-alternatives --set java /usr/lib/jvm/java-21-openjdk-amd64/bin/java 2>/dev/null || true

# 3. Configure Git
echo "[3/6] Configuring Git..."
git config --global user.email "${GIT_EMAIL:-builder@example.com}"
git config --global user.name "${GIT_NAME:-AOSP Builder}"
git config --global color.ui auto

# 4. Install repo
echo "[4/6] Installing repo tool..."
REPO_BIN="/usr/local/bin/repo"
if [ ! -f "$REPO_BIN" ]; then
    curl -s https://storage.googleapis.com/git-repo-downloads/repo > "$REPO_BIN"
    chmod a+x "$REPO_BIN"
fi
echo "repo version: $(repo version 2>/dev/null | head -1)"

# 5. Set up ccache (optional but recommended)
echo "[5/6] Configuring ccache..."
apt-get install -y -qq ccache
echo 'export USE_CCACHE=1' >> /etc/profile.d/aosp.sh
echo 'export CCACHE_EXEC=/usr/bin/ccache' >> /etc/profile.d/aosp.sh
echo 'export CCACHE_DIR=$HOME/.ccache' >> /etc/profile.d/aosp.sh
ccache -M 50G

# 6. Kernel tuning for large builds
echo "[6/6] Tuning kernel parameters..."
# Increase file watcher limit (build system uses inotify)
echo 'fs.inotify.max_user_watches=524288' >> /etc/sysctl.d/99-aosp.conf
# Increase open file limit
echo '* soft nofile 65536' >> /etc/security/limits.d/99-aosp.conf
echo '* hard nofile 65536' >> /etc/security/limits.d/99-aosp.conf
sysctl -p /etc/sysctl.d/99-aosp.conf

echo ""
echo "=== Setup Complete ==="
echo "Next steps:"
echo "  1. mkdir ~/aosp && cd ~/aosp"
echo "  2. repo init -u https://android.googlesource.com/platform/manifest -b main"
echo "  3. repo sync -c -j\$(nproc)"
echo "  4. source build/envsetup.sh"
echo "  5. lunch <target>"
echo "  6. m"
```

### 63.2.6 Setting Up ccache

The compiler cache `ccache` dramatically reduces rebuild times. After the
initial full build (~2-4 hours), incremental builds that only change a few files
can complete in minutes.

```bash
# Set cache size (50 GB is reasonable for AOSP)
export USE_CCACHE=1
export CCACHE_EXEC=/usr/bin/ccache
export CCACHE_DIR=$HOME/.ccache
ccache -M 50G

# Add to ~/.bashrc for persistence
cat >> ~/.bashrc << 'EOF'
export USE_CCACHE=1
export CCACHE_EXEC=/usr/bin/ccache
export CCACHE_DIR=$HOME/.ccache
EOF
```

Check cache statistics after a build:

```bash
ccache -s
# Example output:
# cache hit (direct)                 123456
# cache hit (preprocessed)            12345
# cache miss                          23456
# cache hit rate                     84.56 %
```

### 63.2.7 Initializing the Build Environment

Every time you open a new shell, initialize the build environment:

```bash
cd ~/aosp

# Source the environment setup script
# Real file: build/make/envsetup.sh
source build/envsetup.sh

# This provides:
#   lunch    - Select a build target
#   m        - Build (make) from the tree root
#   mm       - Build from the current directory
#   mmm      - Build from a specified directory
#   croot    - cd to the tree root
#   godir    - Go to the directory containing a file
```

The `envsetup.sh` script (located at `build/make/envsetup.sh`) sets up the
shell with functions and environment variables needed for the build. It scans
all `device/*/` and `vendor/*/` directories for `vendorsetup.sh` files and
sources them, which registers additional lunch targets.

### 63.2.8 Understanding Lunch Targets

```bash
# List available targets
lunch --print-all-targets 2>/dev/null | head -20

# Select the emulator target (what we will base our ROM on)
lunch sdk_phone64_x86_64-trunk_staging-userdebug
```

A lunch target has the form `<product>-<release>-<variant>`:

| Component | Values | Description |
|-----------|--------|-------------|
| Product | `sdk_phone64_x86_64` | Defined in `AndroidProducts.mk` |
| Release | `trunk_staging` | Release configuration |
| Variant | `userdebug` | `user`, `userdebug`, or `eng` |

The three build variants control debuggability:

| Variant | `ro.debuggable` | `adb` | Root | Use Case |
|---------|-----------------|-------|------|----------|
| `user` | 0 | off by default | no | Production/release |
| `userdebug` | 1 | on | adb root | Development with prod-like behavior |
| `eng` | 1 | on | always root | Full development/debugging |

For our custom ROM, we will create our own lunch target that replaces
`sdk_phone64_x86_64`.

### 63.2.9 Build Process Overview

```mermaid
flowchart TD
    A["source build/envsetup.sh"] --> B["lunch product-release-variant"]
    B --> C["m (or make)"]
    C --> D["Soong (Android.bp)"]
    C --> E["Kati (Android.mk)"]
    D --> F["Ninja build"]
    E --> F
    F --> G["Compile C/C++ (clang)"]
    F --> H["Compile Java (javac + d8)"]
    F --> I["Compile AIDL"]
    F --> J["Process resources (aapt2)"]
    G --> K["Link shared libraries"]
    H --> L["Create DEX files"]
    K --> M["Package into partitions"]
    L --> M
    J --> M
    M --> N["system.img"]
    M --> O["vendor.img"]
    M --> P["product.img"]
    M --> Q["boot.img"]
    M --> R["super.img"]

    style A fill:#e1f5fe
    style B fill:#e1f5fe
    style C fill:#fff3e0
    style R fill:#e8f5e9
```

---

## 63.3 Creating a Device Configuration

This is the heart of a custom ROM: the device configuration directory. It tells
the build system what to build, how to build it, and what goes into each
partition.

### 63.3.1 Understanding the Goldfish Device Tree

Before creating our own, let us understand the existing emulator device tree.
The Goldfish emulator configuration lives at:

```
device/generic/goldfish/
```

Its structure is:

```
device/generic/goldfish/
    AndroidProducts.mk              # Lists all product makefiles
    64bitonly/
        product/
            sdk_phone64_x86_64.mk   # Product definition
    board/
        BoardConfigCommon.mk        # Common board configuration
        emu64x/
            BoardConfig.mk          # x86_64-specific board config
            details.mk              # Kernel and fstab setup
    product/
        phone.mk                    # Phone product configuration
        handheld.mk                 # Handheld device base
        base_handheld.mk            # Handheld base with sounds
        generic.mk                  # Vendor/generic config
        versions.mk                 # Shipping API level
    overlay/                        # Static resource overlays
    rro_overlays/                   # Runtime resource overlays
        ConnectivityOverlay/
        RanchuCommonOverlay/
        TetheringOverlay/
    hals/                           # HAL implementations
        audio/
        camera/
        sensors/
        radio/
    sepolicy/                       # SELinux policies
    init/                           # Init scripts
        init.ranchu.rc
```

The product definition chain for `sdk_phone64_x86_64` is:

```mermaid
graph TD
    A["sdk_phone64_x86_64.mk"] -->|inherits| B["phone.mk"]
    A -->|inherits| C["emu64x/details.mk"]
    B -->|inherits| D["handheld.mk"]
    B -->|inherits| E["base_phone.mk"]
    D -->|inherits| F["base_handheld.mk"]
    D -->|inherits| G["generic_system.mk"]
    D -->|inherits| H["handheld_system_ext.mk"]
    D -->|inherits| I["aosp_product.mk"]
    F -->|inherits| J["handheld_product.mk"]
    F -->|inherits| K["handheld_vendor.mk"]
    F -->|inherits| L["AllAudio.mk"]
    C -->|inherits| M["x86_64.mk kernel"]

    A2["emu64x/BoardConfig.mk"] -->|includes| N["BoardConfigCommon.mk"]
    N -->|includes| O["BoardConfigGsiCommon.mk"]

    style A fill:#fff3e0
    style A2 fill:#e1f5fe
```

Let us examine the key files in this chain.

**`device/generic/goldfish/AndroidProducts.mk`** -- lists every product
makefile:

```makefile
# device/generic/goldfish/AndroidProducts.mk
PRODUCT_MAKEFILES := \
    $(LOCAL_DIR)/64bitonly/product/sdk_phone64_x86_64.mk \
    $(LOCAL_DIR)/64bitonly/product/sdk_phone64_arm64.mk \
    ...
```

**`device/generic/goldfish/64bitonly/product/sdk_phone64_x86_64.mk`** -- the
top-level product definition:

```makefile
# device/generic/goldfish/64bitonly/product/sdk_phone64_x86_64.mk
PRODUCT_USE_DYNAMIC_PARTITIONS := true
BOARD_EMULATOR_DYNAMIC_PARTITIONS_SIZE ?= $(shell expr 1800 \* 1048576 )
BOARD_SUPER_PARTITION_SIZE := $(shell expr ... + 8388608 )

$(call inherit-product, $(SRC_TARGET_DIR)/product/core_64_bit_only.mk)
$(call inherit-product, device/generic/goldfish/board/emu64x/details.mk)
$(call inherit-product, device/generic/goldfish/product/phone.mk)

PRODUCT_BRAND := Android
PRODUCT_NAME := sdk_phone64_x86_64
PRODUCT_DEVICE := emu64x
PRODUCT_MODEL := Android SDK built for x86_64
```

These four `PRODUCT_*` variables are the identity of a build target:

| Variable | Purpose | Our Value |
|----------|---------|-----------|
| `PRODUCT_NAME` | Lunch target name | `bookphone` |
| `PRODUCT_DEVICE` | Board/device name, maps to `BoardConfig.mk` | `bookdevice` |
| `PRODUCT_BRAND` | Brand shown in Settings | `AospBook` |
| `PRODUCT_MODEL` | Model shown in Settings | `AospBook Phone` |

**`device/generic/goldfish/board/BoardConfigCommon.mk`** -- hardware-level
configuration that all Goldfish targets share:

```makefile
# device/generic/goldfish/board/BoardConfigCommon.mk (key excerpts)
include build/make/target/board/BoardConfigGsiCommon.mk

BOARD_VENDOR_SEPOLICY_DIRS += device/generic/goldfish/sepolicy/vendor
TARGET_BOOTLOADER_BOARD_NAME := goldfish_$(TARGET_ARCH)

BUILD_EMULATOR_OPENGL := true
BUILD_QEMU_IMAGES := true
USE_OPENGL_RENDERER := true

# Emulator doesn't support sparse image format
TARGET_USERIMAGES_SPARSE_EXT_DISABLED := true

# emulator is Non-A/B device
AB_OTA_UPDATER := none

# emulator needs super.img
BOARD_BUILD_SUPER_IMAGE_BY_DEFAULT := true

# 8G + 8M
BOARD_SUPER_PARTITION_SIZE ?= 8598323200
BOARD_SUPER_PARTITION_GROUPS := emulator_dynamic_partitions

BOARD_EMULATOR_DYNAMIC_PARTITIONS_PARTITION_LIST := \
  system \
  system_dlkm \
  system_ext \
  product \
  vendor
```

### 63.3.2 Creating Our Device Directory

Now we create our own device configuration. The convention is
`device/<vendor>/<device>`:

```bash
# Create the directory structure
mkdir -p device/AospBook/bookphone
```

### 63.3.3 AndroidProducts.mk

This file registers our product with the build system:

```makefile
# device/AospBook/bookphone/AndroidProducts.mk
#
# This file is read by the build system to discover our product makefiles.
# Each entry in PRODUCT_MAKEFILES becomes a valid lunch target.

PRODUCT_MAKEFILES := \
    $(LOCAL_DIR)/bookphone.mk
```

When the build system scans `device/` directories, it looks for
`AndroidProducts.mk` files. Each path listed in `PRODUCT_MAKEFILES` defines a
lunch target whose name is the `PRODUCT_NAME` set inside that makefile.

### 63.3.4 The Product Makefile: bookphone.mk

This is the top-level product definition. It inherits from Goldfish to get all
the emulator infrastructure, then overlays our customizations:

```makefile
# device/AospBook/bookphone/bookphone.mk
#
# Top-level product makefile for AospBook Phone.
# This defines the lunch target "bookphone".
#
# Inherits from the Goldfish emulator to get all emulator-specific
# packages, HALs, kernel configuration, and hardware support.

# ============================================================
# Inherit from Goldfish emulator
# ============================================================

# Use dynamic partitions, same sizing as stock emulator
PRODUCT_USE_DYNAMIC_PARTITIONS := true
BOARD_EMULATOR_DYNAMIC_PARTITIONS_SIZE ?= $(shell expr 2400 \* 1048576)
BOARD_SUPER_PARTITION_SIZE := \
    $(shell expr $(BOARD_EMULATOR_DYNAMIC_PARTITIONS_SIZE) + 8388608)

# 64-bit only configuration
$(call inherit-product, $(SRC_TARGET_DIR)/product/core_64_bit_only.mk)

# Goldfish board details (kernel, fstab, etc.)
$(call inherit-product, device/generic/goldfish/board/emu64x/details.mk)

# Goldfish phone configuration (HALs, permissions, vendor packages)
$(call inherit-product, device/generic/goldfish/product/phone.mk)

# Our device-specific configuration
$(call inherit-product, device/AospBook/bookphone/device.mk)

# ============================================================
# Product identity
# ============================================================
PRODUCT_BRAND := AospBook
PRODUCT_NAME := bookphone
PRODUCT_DEVICE := bookdevice
PRODUCT_MODEL := AospBook Phone
PRODUCT_MANUFACTURER := AospBook

# Build fingerprint (shown in Settings > About phone)
BUILD_FINGERPRINT := AospBook/bookphone/bookdevice:16/AP3A.250318.001/eng.builder:userdebug/dev-keys

# ============================================================
# Additional product properties
# ============================================================
PRODUCT_PROPERTY_OVERRIDES += \
    ro.build.display.id=AospBook-1.0 \
    ro.aospbook.version=1.0.0 \
    ro.aospbook.build.type=development \
    persist.sys.timezone=America/Los_Angeles
```

### 63.3.5 The Device Makefile: device.mk

This file contains device-specific packages, copy files, and properties:

```makefile
# device/AospBook/bookphone/device.mk
#
# Device-level configuration for AospBook Phone.
# This is where we add our custom packages, overlays, and copy files.

# ============================================================
# Custom packages
# ============================================================
PRODUCT_PACKAGES += \
    BookSampleApp \
    BookReader

# Custom system service
PRODUCT_PACKAGES += \
    BookService

# Custom overlays
PRODUCT_PACKAGES += \
    BookFrameworkOverlay \
    BookSystemUIOverlay

# Custom boot animation
PRODUCT_COPY_FILES += \
    device/AospBook/bookphone/bootanimation/bootanimation.zip:$(TARGET_COPY_OUT_PRODUCT)/media/bootanimation.zip

# ============================================================
# Custom properties
# ============================================================
PRODUCT_PRODUCT_PROPERTIES += \
    ro.aospbook.features.dark_mode_default=true \
    ro.aospbook.features.custom_qs=true

# ============================================================
# SELinux policy
# ============================================================
BOARD_VENDOR_SEPOLICY_DIRS += device/AospBook/bookphone/sepolicy/vendor

# ============================================================
# Soong namespace (allows our modules to be found)
# ============================================================
PRODUCT_SOONG_NAMESPACES += device/AospBook/bookphone
```

### 63.3.6 BoardConfig.mk

The board configuration defines hardware-level parameters. Since we are
targeting the emulator, we inherit from Goldfish's board config:

```makefile
# device/AospBook/bookphone/BoardConfig.mk
#
# Board configuration for AospBook Phone (emulator-based).
# This inherits from the Goldfish x86_64 board and customizes
# partition sizes and SELinux.

# x86_64 emulator architecture
TARGET_CPU_ABI := x86_64
TARGET_ARCH := x86_64
TARGET_ARCH_VARIANT := x86_64
TARGET_2ND_ARCH_VARIANT := x86_64

# Inherit common Goldfish board config
include device/generic/goldfish/board/BoardConfigCommon.mk

# ============================================================
# Partition sizes
# ============================================================
# Increase userdata for development (2 GB)
BOARD_USERDATAIMAGE_PARTITION_SIZE := 2147483648

# ============================================================
# SELinux
# ============================================================
BOARD_VENDOR_SEPOLICY_DIRS += device/AospBook/bookphone/sepolicy/vendor

# ============================================================
# Kernel
# ============================================================
# Use the same prebuilt kernel as Goldfish
# (See Section 63.11 for building a custom kernel)
TARGET_KERNEL_USE ?= 6.12

# ============================================================
# Recovery
# ============================================================
TARGET_NO_RECOVERY := true

# ============================================================
# Verified Boot
# ============================================================
BOARD_AVB_ENABLE := true
```

### 63.3.7 How the Build System Discovers Our Product

When you run `lunch bookphone-trunk_staging-userdebug`, the build system:

```mermaid
sequenceDiagram
    participant User
    participant envsetup.sh
    participant Build System
    participant AndroidProducts.mk
    participant bookphone.mk
    participant BoardConfig.mk

    User->>envsetup.sh: source build/envsetup.sh
    envsetup.sh->>Build System: Scan device/**/AndroidProducts.mk
    Build System->>AndroidProducts.mk: Found device/AospBook/bookphone/AndroidProducts.mk
    AndroidProducts.mk->>Build System: Register bookphone.mk

    User->>envsetup.sh: lunch bookphone-trunk_staging-userdebug
    envsetup.sh->>Build System: Set TARGET_PRODUCT=bookphone
    Build System->>bookphone.mk: Parse product makefile
    bookphone.mk->>Build System: PRODUCT_DEVICE=bookdevice
    Build System->>BoardConfig.mk: Load device/AospBook/bookphone/BoardConfig.mk
    Build System->>Build System: Resolve all inherit-product chains
    Build System->>User: Build environment configured
```

### 63.3.8 Verifying the Product Registration

After creating these files, verify that the build system recognizes your
product:

```bash
# Source the environment
source build/envsetup.sh

# Check that our target appears
lunch --print-all-targets 2>/dev/null | grep bookphone
# Expected output: bookphone-trunk_staging-userdebug
#                  bookphone-trunk_staging-eng
#                  bookphone-trunk_staging-user

# Select our target
lunch bookphone-trunk_staging-userdebug

# Verify the environment
echo "TARGET_PRODUCT=$TARGET_PRODUCT"         # bookphone
echo "TARGET_BUILD_VARIANT=$TARGET_BUILD_VARIANT" # userdebug
echo "TARGET_ARCH=$TARGET_ARCH"               # x86_64
printconfig
```

### 63.3.9 The Product Variable Namespace

The build system defines a rich set of `PRODUCT_*` variables. Here are the most
important ones for ROM building:

| Variable | Purpose | Example |
|----------|---------|---------|
| `PRODUCT_NAME` | Lunch target name | `bookphone` |
| `PRODUCT_DEVICE` | Maps to board config directory | `bookdevice` |
| `PRODUCT_BRAND` | Brand string | `AospBook` |
| `PRODUCT_MODEL` | Model string | `AospBook Phone` |
| `PRODUCT_MANUFACTURER` | Manufacturer string | `AospBook` |
| `PRODUCT_PACKAGES` | Modules to include in the build | `BookSampleApp` |
| `PRODUCT_COPY_FILES` | Files to copy into the image | `src:dest` pairs |
| `PRODUCT_PROPERTY_OVERRIDES` | System properties (`/system`) | `ro.foo=bar` |
| `PRODUCT_PRODUCT_PROPERTIES` | Product properties (`/product`) | `ro.foo=bar` |
| `PRODUCT_VENDOR_PROPERTIES` | Vendor properties (`/vendor`) | `ro.foo=bar` |
| `PRODUCT_SOONG_NAMESPACES` | Soong module search paths | directory paths |
| `PRODUCT_ENFORCE_RRO_TARGETS` | Force RRO on targets | `framework-res` |
| `PRODUCT_ENFORCE_RRO_EXCLUDED_OVERLAYS` | Exclude from RRO enforcement | overlay paths |

### 63.3.10 The Inheritance Mechanism

The `$(call inherit-product, ...)` function is the cornerstone of product
configuration. It works by appending the included makefile's variable values to
the including makefile's variables:

```makefile
# In parent.mk:
PRODUCT_PACKAGES += ParentApp

# In child.mk:
$(call inherit-product, parent.mk)
PRODUCT_PACKAGES += ChildApp

# Result: PRODUCT_PACKAGES = ParentApp ChildApp
```

This is different from a simple `include` statement. The `inherit-product`
function uses a namespace mechanism to prevent variable collisions when
multiple makefiles define the same variable.

There is also `$(call inherit-product-if-exists, ...)` which silently succeeds
if the file does not exist -- useful for optional vendor overlays.

---

## 63.4 Adding Custom Apps

### 63.4.1 Understanding PRODUCT_PACKAGES

Every module that appears in `PRODUCT_PACKAGES` is built and included in the
appropriate partition image. The module name maps to a build rule defined in
either an `Android.bp` (Soong) or `Android.mk` (Make) file.

The base system packages are defined in `build/make/target/product/base_system.mk`:

```makefile
# build/make/target/product/base_system.mk (excerpt)
PRODUCT_PACKAGES += \
    abx \
    am \
    app_process \
    atrace \
    bootanimation \
    bootstat \
    bugreport \
    cmd \
    ...
```

These are the minimum packages for a functional Android system. Our product
inherits them through the Goldfish phone configuration chain.

### 63.4.2 Adding a Prebuilt APK

Suppose you have a third-party APK (e.g., a PDF reader) that you want to
include in your ROM. Create a prebuilt module:

```
device/AospBook/bookphone/apps/prebuilt/BookReader/
    Android.bp
    BookReader.apk
```

The `Android.bp` file defines a prebuilt app:

```json
// device/AospBook/bookphone/apps/prebuilt/BookReader/Android.bp
//
// Prebuilt APK for BookReader PDF viewer.
// This is included in the system image via PRODUCT_PACKAGES += BookReader.

android_app_import {
    name: "BookReader",

    // The APK file in this directory
    apk: "BookReader.apk",

    // Install to the /product partition (not /system)
    product_specific: true,

    // Allow the app to be updated from the Play Store
    overrides: [],

    // Signature: presigned means keep the APK's existing signature
    presigned: true,

    // Optional: mark as privileged if it needs privileged permissions
    // privileged: true,

    // Optimize DEX code during build
    dex_preopt: {
        enabled: true,
    },
}
```

Key `android_app_import` properties:

| Property | Values | Description |
|----------|--------|-------------|
| `apk` | filename | Path to the APK file |
| `presigned` | `true`/`false` | Keep existing signature vs. re-sign |
| `certificate` | `"platform"`, `"shared"`, `"media"`, path | Signing key |
| `privileged` | `true`/`false` | Install to `priv-app/` |
| `product_specific` | `true`/`false` | Install to `/product` partition |
| `vendor` | `true`/`false` | Install to `/vendor` partition |
| `dex_preopt.enabled` | `true`/`false` | Pre-optimize DEX at build time |

If your APK is not already signed with the correct key, use `certificate`
instead of `presigned`:

```json
android_app_import {
    name: "BookReader",
    apk: "BookReader.apk",
    product_specific: true,
    certificate: "platform",   // Re-sign with the platform key
    dex_preopt: {
        enabled: true,
    },
}
```

The signing key names map to files in `build/make/target/product/security/`:

| Key name | Files | Used for |
|----------|-------|----------|
| `platform` | `platform.pk8`, `platform.x509.pem` | System apps with `android:sharedUserId="android.uid.system"` |
| `shared` | `shared.pk8`, `shared.x509.pem` | Apps sharing data (Contacts, Phone) |
| `media` | `media.pk8`, `media.x509.pem` | Media/download system apps |
| `testkey` | `testkey.pk8`, `testkey.x509.pem` | Default development signing key |

### 63.4.3 Building a Custom App into the Image

Now let us create a custom app from source. This app will be built as part of
the AOSP build, compiled, signed, and placed into the system image.

Create the app directory:

```
device/AospBook/bookphone/apps/BookSampleApp/
    Android.bp
    AndroidManifest.xml
    res/
        layout/
            activity_main.xml
        values/
            strings.xml
        mipmap-xxxhdpi/
            ic_launcher.png
    src/
        com/
            aospbook/
                sample/
                    MainActivity.java
```

**Android.bp** -- the Soong build definition:

```json
// device/AospBook/bookphone/apps/BookSampleApp/Android.bp
//
// Custom sample app built from source, included in the system image.

android_app {
    name: "BookSampleApp",

    // Source files
    srcs: ["src/**/*.java"],

    // Android SDK version to compile against
    sdk_version: "current",

    // Install to the /product partition
    product_specific: true,

    // Sign with the platform key
    certificate: "platform",

    // Resource directories
    resource_dirs: ["res"],

    // Static library dependencies
    static_libs: [
        "androidx.appcompat_appcompat",
        "com.google.android.material_material",
    ],

    // Optimize DEX code
    optimize: {
        enabled: true,
        shrink: true,
        optimize: true,
        proguard_flags_files: ["proguard-rules.pro"],
    },

    // DEX preoptimization
    dex_preopt: {
        enabled: true,
    },
}
```

**AndroidManifest.xml**:

```xml
<?xml version="1.0" encoding="utf-8"?>
<!-- device/AospBook/bookphone/apps/BookSampleApp/AndroidManifest.xml -->
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="com.aospbook.sample">

    <application
        android:label="@string/app_name"
        android:icon="@mipmap/ic_launcher"
        android:theme="@style/Theme.AppCompat.DayNight">

        <activity
            android:name=".MainActivity"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>

</manifest>
```

**MainActivity.java**:

```java
// device/AospBook/bookphone/apps/BookSampleApp/src/com/aospbook/sample/MainActivity.java
package com.aospbook.sample;

import android.app.Activity;
import android.os.Build;
import android.os.Bundle;
import android.widget.TextView;

/**
 * Sample app demonstrating a custom app built into an AOSP-based ROM.
 *
 * This activity displays system information to verify that the custom
 * ROM is running correctly.
 */
public class MainActivity extends Activity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        TextView textView = new TextView(this);
        textView.setPadding(32, 32, 32, 32);
        textView.setTextSize(18);
        textView.setText(buildInfoString());
        setContentView(textView);
    }

    private String buildInfoString() {
        StringBuilder sb = new StringBuilder();
        sb.append("AospBook ROM Info\n");
        sb.append("=================\n\n");
        sb.append("Brand: ").append(Build.BRAND).append("\n");
        sb.append("Model: ").append(Build.MODEL).append("\n");
        sb.append("Device: ").append(Build.DEVICE).append("\n");
        sb.append("Product: ").append(Build.PRODUCT).append("\n");
        sb.append("Build ID: ").append(Build.DISPLAY).append("\n");
        sb.append("Android Version: ").append(Build.VERSION.RELEASE).append("\n");
        sb.append("SDK Level: ").append(Build.VERSION.SDK_INT).append("\n");
        sb.append("Build Type: ").append(Build.TYPE).append("\n");
        sb.append("Fingerprint: ").append(Build.FINGERPRINT).append("\n");

        // Check for our custom property
        String romVersion = System.getProperty("ro.aospbook.version", "unknown");
        sb.append("\nROM Version: ").append(romVersion).append("\n");

        return sb.toString();
    }
}
```

**res/values/strings.xml**:

```xml
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">AospBook Sample</string>
</resources>
```

**res/layout/activity_main.xml**:

```xml
<?xml version="1.0" encoding="utf-8"?>
<LinearLayout
    xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:orientation="vertical"
    android:padding="16dp">

    <TextView
        android:id="@+id/info_text"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:textSize="16sp"
        android:fontFamily="monospace" />

</LinearLayout>
```

### 63.4.4 Removing Default Apps

To remove default AOSP apps you do not want, use `PRODUCT_PACKAGES_REMOVE`:

```makefile
# In device.mk
PRODUCT_PACKAGES_REMOVE += \
    Browser2 \
    Calendar \
    DeskClock \
    Gallery2 \
    Music
```

This removes these apps from the set inherited from parent makefiles. The apps
are still built (they may be dependencies of other modules), but they are not
installed into the image.

Alternatively, you can exclude entire AOSP app categories by not inheriting
certain makefiles. For example, if you do not want telephony apps:

```makefile
# Instead of inheriting full_base_telephony.mk, inherit full_base.mk
$(call inherit-product, $(SRC_TARGET_DIR)/product/full_base.mk)
```

### 63.4.5 Privileged Apps and Permissions

Apps installed to `/system/priv-app/` or `/product/priv-app/` can request
privileged permissions not available to regular apps. To make an app
privileged:

```json
// In Android.bp
android_app {
    name: "BookPrivilegedApp",
    privileged: true,
    product_specific: true,
    certificate: "platform",
    // ...
}
```

Privileged apps need a permissions allowlist. Create:

```xml
<!-- device/AospBook/bookphone/permissions/privapp-permissions-bookphone.xml -->
<?xml version="1.0" encoding="utf-8"?>
<permissions>
    <privapp-permissions package="com.aospbook.privileged">
        <permission name="android.permission.MANAGE_USERS" />
        <permission name="android.permission.INTERACT_ACROSS_USERS" />
    </privapp-permissions>
</permissions>
```

And copy it into the image:

```makefile
# In device.mk
PRODUCT_COPY_FILES += \
    device/AospBook/bookphone/permissions/privapp-permissions-bookphone.xml:$(TARGET_COPY_OUT_PRODUCT)/etc/permissions/privapp-permissions-bookphone.xml
```

### 63.4.6 App Installation Locations

```mermaid
graph TD
    subgraph "Partition Layout"
        A["/system/app/"] -->|Regular system apps| A1["Settings, SystemUI, ..."]
        B["/system/priv-app/"] -->|Privileged system apps| B1["Phone, Contacts, ..."]
        C["/product/app/"] -->|Product apps| C1["Custom regular apps"]
        D["/product/priv-app/"] -->|Product privileged| D1["Custom privileged apps"]
        E["/vendor/app/"] -->|Vendor apps| E1["Hardware-specific apps"]
        F["/data/app/"] -->|User-installed apps| F1["Play Store downloads"]
    end

    style C fill:#fff3e0
    style D fill:#fff3e0
```

The build system maps module properties to installation paths:

| `Android.bp` Property | Installation Path |
|------------------------|-------------------|
| (none -- default) | `/system/app/<name>/` |
| `privileged: true` | `/system/priv-app/<name>/` |
| `product_specific: true` | `/product/app/<name>/` |
| `product_specific: true` + `privileged: true` | `/product/priv-app/<name>/` |
| `vendor: true` | `/vendor/app/<name>/` |
| `system_ext_specific: true` | `/system_ext/app/<name>/` |

---

## 63.5 Modifying Framework Behavior

### 63.5.1 Runtime Resource Overlay (RRO)

Runtime Resource Overlays are the recommended way to customize framework
behavior without modifying framework source code. An RRO is a small APK
containing only resources that override the default values in a target package.

The framework's configurable behavior is defined in:

```
frameworks/base/core/res/res/values/config.xml
```

This file (7,759 lines) contains hundreds of configuration values. RROs can
override any of them.

**How RROs work:**

```mermaid
sequenceDiagram
    participant PMS as PackageManagerService
    participant OMS as OverlayManagerService
    participant RRO as RRO APK
    participant Target as Target Package (e.g., framework-res)
    participant App as Application

    PMS->>OMS: Register overlay APK
    OMS->>RRO: Parse AndroidManifest.xml
    OMS->>OMS: Match targetPackage to installed package
    OMS->>OMS: Enable overlay (if static or user-enabled)

    App->>Target: getResources().getBoolean(R.bool.config_foo)
    Target->>OMS: Check for overlaid value
    OMS->>RRO: Read overlaid resource
    RRO-->>App: Return overridden value
```

**Creating a Framework RRO:**

Create the overlay directory structure:

```
device/AospBook/bookphone/overlay/BookFrameworkOverlay/
    Android.bp
    AndroidManifest.xml
    res/
        values/
            config.xml
            bools.xml
```

**Android.bp**:

```json
// device/AospBook/bookphone/overlay/BookFrameworkOverlay/Android.bp
//
// Runtime Resource Overlay for the framework (android package).
// Overrides default configuration values.

runtime_resource_overlay {
    name: "BookFrameworkOverlay",

    // The target package this overlay applies to
    // "android" is the framework-res package
    sdk_version: "current",

    // Install to the product partition
    product_specific: true,
}
```

**AndroidManifest.xml**:

```xml
<!-- device/AospBook/bookphone/overlay/BookFrameworkOverlay/AndroidManifest.xml -->
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="com.aospbook.overlay.framework">

    <application android:hasCode="false" />

    <overlay
        android:targetPackage="android"
        android:isStatic="true"
        android:priority="10"
        />
</manifest>
```

Key manifest attributes:

| Attribute | Value | Meaning |
|-----------|-------|---------|
| `targetPackage` | `"android"` | Overlay targets the framework |
| `isStatic` | `"true"` | Always enabled, cannot be disabled by user |
| `priority` | `"10"` | Higher priority wins when multiple overlays exist |

**res/values/config.xml** -- override framework defaults:

```xml
<?xml version="1.0" encoding="utf-8"?>
<!-- Override framework configuration values -->
<resources>
    <!-- Enable dark mode by default -->
    <integer name="config_defaultNightMode">2</integer>
    <!-- 0=MODE_NIGHT_NO, 1=MODE_NIGHT_YES, 2=MODE_NIGHT_AUTO -->

    <!-- Default wallpaper component -->
    <string name="default_wallpaper_component" translatable="false">
        com.aospbook.wallpaper/.DefaultWallpaperService
    </string>

    <!-- Enable always-on display by default -->
    <bool name="config_dozeAlwaysOnDisplayAvailable">true</bool>

    <!-- Screen brightness settings -->
    <integer name="config_screenBrightnessSettingDefault">128</integer>
    <integer name="config_screenBrightnessSettingMinimum">10</integer>

    <!-- Lock screen: allow rotation -->
    <bool name="config_enableLockScreenRotation">true</bool>

    <!-- Power button behavior: long press = power menu -->
    <integer name="config_longPressOnPowerBehavior">1</integer>

    <!-- Show battery percentage in status bar by default -->
    <bool name="config_defaultBatteryPercentageSetting">true</bool>

    <!-- Haptic feedback default -->
    <bool name="config_enableHapticTextHandle">true</bool>
</resources>
```

To see all overridable framework config values, examine:

```
frameworks/base/core/res/res/values/config.xml
```

Some commonly overridden values for custom ROMs:

| Resource | Type | Default | Description |
|----------|------|---------|-------------|
| `config_defaultNightMode` | integer | 0 | Default UI mode (dark/light) |
| `config_longPressOnPowerBehavior` | integer | 1 | Power button long-press |
| `config_dozeAlwaysOnDisplayAvailable` | bool | false | Always-on display |
| `config_enableLockScreenRotation` | bool | false | Lock screen rotation |
| `config_screenBrightnessSettingDefault` | integer | varies | Default brightness |
| `config_defaultBatteryPercentageSetting` | bool | false | Battery % in status bar |
| `config_enableHapticTextHandle` | bool | false | Text selection haptics |

### 63.5.2 Verifying RRO Installation

After building, you can verify that your overlay is active:

```bash
# On the running device/emulator:
adb shell cmd overlay list
# Expected output includes:
# com.aospbook.overlay.framework
#     [x] com.aospbook.overlay.framework (targeting android, priority 10)

# Check a specific overlaid value:
adb shell cmd overlay dump com.aospbook.overlay.framework

# Or query the resource directly:
adb shell settings get system screen_brightness
```

### 63.5.3 Modifying Framework Source Code

For changes that cannot be achieved through RROs, you must modify framework
source code directly. This is the most invasive form of customization and
requires careful management (especially when rebasing on new AOSP releases).

**Example: Adding a Custom System Property to Settings**

Suppose we want to expose our ROM version in the Settings app. The About Phone
screen reads build properties from `android.os.Build`.

The Build class is defined at:

```
frameworks/base/core/java/android/os/Build.java
```

We can add a new field:

```java
// Add to frameworks/base/core/java/android/os/Build.java
// (inside the class body)

/**
 * The custom ROM version, as set by the ROM builder.
 * Read from the system property "ro.aospbook.version".
 */
public static final String AOSPBOOK_VERSION =
    SystemProperties.get("ro.aospbook.version", "unknown");
```

This property is set by our product configuration:

```makefile
# In device.mk or bookphone.mk
PRODUCT_PROPERTY_OVERRIDES += ro.aospbook.version=1.0.0
```

### 63.5.4 Adding a New System Service

A system service runs in the `system_server` process and provides an API
that apps can call via Binder IPC. This is the most powerful form of framework
customization.

**Architecture of a system service:**

```mermaid
graph TD
    subgraph "App Process"
        A[BookManager] -->|Binder proxy| B[IBookService.Stub.Proxy]
    end

    subgraph "system_server Process"
        C[BookService] -->|extends| D[IBookService.Stub]
        D -->|registered with| E[ServiceManager]
    end

    B -.->|Binder IPC| D

    subgraph "Build Artifacts"
        F[IBookService.aidl] -->|aidl compiler| G[IBookService.java]
        G --> B
        G --> D
    end

    style A fill:#e1f5fe
    style C fill:#e8f5e9
    style F fill:#fff3e0
```

**Step 1: Define the AIDL Interface**

Create the directory structure:

```
device/AospBook/bookphone/services/BookService/
    Android.bp
    aidl/
        com/aospbook/service/
            IBookService.aidl
    src/
        com/aospbook/service/
            BookService.java
            BookServiceManager.java
```

**IBookService.aidl**:

```java
// device/AospBook/bookphone/services/BookService/aidl/com/aospbook/service/IBookService.aidl
package com.aospbook.service;

/**
 * System service interface for AospBook-specific functionality.
 * This service runs in system_server and provides ROM-specific
 * APIs to applications.
 */
interface IBookService {
    /**
     * Returns the current ROM version string.
     */
    String getRomVersion();

    /**
     * Returns the ROM build timestamp (epoch seconds).
     */
    long getBuildTimestamp();

    /**
     * Sets a custom user preference stored in the service.
     * @param key Preference key
     * @param value Preference value
     */
    void setPreference(String key, String value);

    /**
     * Gets a custom user preference.
     * @param key Preference key
     * @return The stored value, or null if not set
     */
    String getPreference(String key);

    /**
     * Returns a list of enabled AospBook features.
     */
    List<String> getEnabledFeatures();
}
```

**Step 2: Implement the Service**

**BookService.java**:

```java
// device/AospBook/bookphone/services/BookService/src/com/aospbook/service/BookService.java
package com.aospbook.service;

import android.content.Context;
import android.os.RemoteException;
import android.os.SystemProperties;
import android.util.Log;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * System service implementation for AospBook ROM.
 *
 * This service is registered with ServiceManager under the name
 * "aospbook" and can be accessed by apps via BookServiceManager.
 *
 * Registration happens in SystemServer.java during the
 * startOtherServices() phase.
 */
public class BookService extends IBookService.Stub {
    private static final String TAG = "BookService";
    private static final String SERVICE_NAME = "aospbook";

    private final Context mContext;
    private final Map<String, String> mPreferences;

    public BookService(Context context) {
        mContext = context;
        mPreferences = new HashMap<>();
        Log.i(TAG, "BookService initialized");
    }

    @Override
    public String getRomVersion() throws RemoteException {
        return SystemProperties.get("ro.aospbook.version", "unknown");
    }

    @Override
    public long getBuildTimestamp() throws RemoteException {
        String timestamp = SystemProperties.get("ro.build.date.utc", "0");
        try {
            return Long.parseLong(timestamp);
        } catch (NumberFormatException e) {
            return 0;
        }
    }

    @Override
    public void setPreference(String key, String value) throws RemoteException {
        // In a production implementation, this would persist to disk
        // and enforce permission checks.
        enforceCallerPermission();
        synchronized (mPreferences) {
            mPreferences.put(key, value);
        }
        Log.d(TAG, "Preference set: " + key + " = " + value);
    }

    @Override
    public String getPreference(String key) throws RemoteException {
        synchronized (mPreferences) {
            return mPreferences.get(key);
        }
    }

    @Override
    public List<String> getEnabledFeatures() throws RemoteException {
        List<String> features = new ArrayList<>();

        if (SystemProperties.getBoolean(
                "ro.aospbook.features.dark_mode_default", false)) {
            features.add("dark_mode_default");
        }
        if (SystemProperties.getBoolean(
                "ro.aospbook.features.custom_qs", false)) {
            features.add("custom_qs");
        }

        return features;
    }

    /**
     * Returns the service name for ServiceManager registration.
     */
    public static String getServiceName() {
        return SERVICE_NAME;
    }

    private void enforceCallerPermission() {
        // In production, check a custom permission here:
        // mContext.enforceCallingOrSelfPermission(
        //     "com.aospbook.permission.MANAGE_PREFERENCES",
        //     "BookService");
    }
}
```

**Step 3: Android.bp**

```json
// device/AospBook/bookphone/services/BookService/Android.bp

// AIDL interface library
java_library {
    name: "aospbook-service-aidl",
    srcs: ["aidl/**/*.aidl"],
    sdk_version: "system_current",
    product_specific: true,
}

// Service implementation (runs in system_server)
java_library {
    name: "BookService",
    srcs: ["src/**/*.java"],
    static_libs: [
        "aospbook-service-aidl",
    ],
    libs: [
        "framework",
        "services.core",
    ],
    product_specific: true,
}
```

**Step 4: Register the Service in SystemServer**

The `SystemServer` (located at
`frameworks/base/services/java/com/android/server/SystemServer.java`) is where
all system services are started. To add our service, we modify the
`startOtherServices()` method:

```java
// In frameworks/base/services/java/com/android/server/SystemServer.java
// Add to the startOtherServices() method, near the end:

// AospBook custom service
traceBeginAndSlog("StartBookService");
try {
    ServiceManager.addService("aospbook",
        new com.aospbook.service.BookService(mSystemContext));
} catch (Throwable e) {
    reportWtf("starting BookService", e);
}
traceEnd();
```

Alternatively, for a less invasive approach, you can use a `SystemService`
subclass and register it through the `SystemServiceManager`:

```java
// Alternative: device/AospBook/bookphone/services/BookService/src/.../BookSystemService.java
package com.aospbook.service;

import android.content.Context;
import android.os.ServiceManager;

import com.android.server.SystemService;

/**
 * SystemService wrapper for BookService.
 * This approach uses the SystemServiceManager lifecycle.
 */
public class BookSystemService extends SystemService {
    private BookService mService;

    public BookSystemService(Context context) {
        super(context);
    }

    @Override
    public void onStart() {
        mService = new BookService(getContext());
        ServiceManager.addService(BookService.getServiceName(), mService);
    }

    @Override
    public void onBootPhase(int phase) {
        if (phase == PHASE_SYSTEM_SERVICES_READY) {
            // Perform initialization that requires other services
        }
    }
}
```

**Step 5: Create a Client Manager Class**

Apps use a manager class to interact with the service:

```java
// device/AospBook/bookphone/services/BookService/src/com/aospbook/service/BookServiceManager.java
package com.aospbook.service;

import android.os.IBinder;
import android.os.RemoteException;
import android.os.ServiceManager;
import android.util.Log;

import java.util.Collections;
import java.util.List;

/**
 * Client-side manager for the AospBook system service.
 *
 * Usage:
 *     BookServiceManager manager = BookServiceManager.getInstance();
 *     String version = manager.getRomVersion();
 */
public class BookServiceManager {
    private static final String TAG = "BookServiceManager";
    private static volatile BookServiceManager sInstance;

    private final IBookService mService;

    private BookServiceManager(IBookService service) {
        mService = service;
    }

    /**
     * Gets the singleton instance of BookServiceManager.
     * Returns null if the service is not available (e.g., on non-AospBook ROMs).
     */
    public static BookServiceManager getInstance() {
        if (sInstance == null) {
            synchronized (BookServiceManager.class) {
                if (sInstance == null) {
                    IBinder binder = ServiceManager.getService("aospbook");
                    if (binder != null) {
                        IBookService service =
                            IBookService.Stub.asInterface(binder);
                        sInstance = new BookServiceManager(service);
                    }
                }
            }
        }
        return sInstance;
    }

    public String getRomVersion() {
        try {
            return mService.getRomVersion();
        } catch (RemoteException e) {
            Log.e(TAG, "Failed to get ROM version", e);
            return "unknown";
        }
    }

    public long getBuildTimestamp() {
        try {
            return mService.getBuildTimestamp();
        } catch (RemoteException e) {
            Log.e(TAG, "Failed to get build timestamp", e);
            return 0;
        }
    }

    public void setPreference(String key, String value) {
        try {
            mService.setPreference(key, value);
        } catch (RemoteException e) {
            Log.e(TAG, "Failed to set preference", e);
        }
    }

    public String getPreference(String key) {
        try {
            return mService.getPreference(key);
        } catch (RemoteException e) {
            Log.e(TAG, "Failed to get preference", e);
            return null;
        }
    }

    public List<String> getEnabledFeatures() {
        try {
            return mService.getEnabledFeatures();
        } catch (RemoteException e) {
            Log.e(TAG, "Failed to get enabled features", e);
            return Collections.emptyList();
        }
    }
}
```

### 63.5.5 SELinux Policy for Custom Services

Any new system service requires SELinux policy. Without it, SELinux (which
is enforcing on all modern Android builds) will deny the service from
operating.

Create the policy file:

```
# device/AospBook/bookphone/sepolicy/vendor/bookservice.te

# Define the BookService type
type bookservice, domain;
type bookservice_exec, exec_type, file_type, system_file_type;

# Allow system_server to register and access the service
allow system_server bookservice_service:service_manager { add find };

# Allow apps to find the service
allow untrusted_app bookservice_service:service_manager find;
allow platform_app bookservice_service:service_manager find;

# Allow the service to read system properties
allow bookservice system_prop:file { read open getattr };
get_prop(bookservice, system_prop)
```

And register the service in `service_contexts`:

```
# device/AospBook/bookphone/sepolicy/vendor/service_contexts
aospbook                            u:object_r:bookservice_service:s0
```

Define the service type in `service.te`:

```
# device/AospBook/bookphone/sepolicy/vendor/service.te
type bookservice_service, service_manager_type;
```

Add file contexts:

```
# device/AospBook/bookphone/sepolicy/vendor/file_contexts
/product/lib/BookService\.jar                u:object_r:system_file:s0
```

### 63.5.6 System Service Lifecycle

Understanding when your service starts relative to other services is
important:

```mermaid
graph TD
    A["system_server starts"] --> B["Phase: PHASE_WAIT_FOR_DEFAULT_DISPLAY"]
    B --> C["Phase: PHASE_LOCK_SETTINGS_READY"]
    C --> D["Phase: PHASE_SYSTEM_SERVICES_READY"]
    D --> E["Phase: PHASE_DEVICE_SPECIFIC_SERVICES_READY"]
    E --> F["Phase: PHASE_ACTIVITY_MANAGER_READY"]
    F --> G["Phase: PHASE_THIRD_PARTY_APPS_CAN_START"]
    G --> H["Phase: PHASE_BOOT_COMPLETED"]

    D -.->|"Our service starts here"| D

    style D fill:#fff3e0
    style H fill:#e8f5e9
```

---

## 63.6 Custom Boot Animation

### 63.6.1 Boot Animation Format

The boot animation is stored as a ZIP file at one of these locations
(checked in order):

1. `/system/media/bootanimation.zip`
2. `/product/media/bootanimation.zip`
3. `/oem/media/bootanimation.zip`

The format is defined in detail in `frameworks/base/cmds/bootanimation/FORMAT.md`.

The ZIP contains:

```
bootanimation.zip (store compression, no deflate)
    desc.txt          # Animation descriptor
    part0/            # First animation part (frames)
        00000.png
        00001.png
        ...
    part1/            # Second animation part
        00000.png
        00001.png
        ...
    audio.wav         # Optional audio (per-part)
```

### 63.6.2 The desc.txt File

The first line defines global parameters:

```
WIDTH HEIGHT FPS [PROGRESS]
```

Subsequent lines define animation parts:

```
TYPE COUNT PAUSE PATH [FADE [#RGBHEX [CLOCK1 [CLOCK2]]]]
```

**Type values:**

| Type | Behavior |
|------|----------|
| `p` | Play until boot completes, then stop |
| `c` | Play to completion regardless of boot state |
| `f` | Like `p` but with fade-out when interrupted |

**Example desc.txt:**

```
1080 1920 30
c 1 0 part0
p 0 0 part1
```

This defines:

- 1080x1920 resolution at 30 FPS
- `part0`: Play once to completion (`c 1`) with no pause
- `part1`: Loop forever (`p 0`) until boot finishes

### 63.6.3 Creating a Custom Boot Animation

Let us create a simple but professional boot animation for AospBook ROM.

**Step 1: Create the frame images**

You can create frames using any image editor (GIMP, Photoshop, Inkscape) or
generate them programmatically. Each frame must be a PNG at the resolution
specified in `desc.txt`.

```bash
# Create the directory structure
mkdir -p device/AospBook/bookphone/bootanimation/part0
mkdir -p device/AospBook/bookphone/bootanimation/part1

# Example: Generate simple gradient frames using ImageMagick
# Part 0: Fade in the logo (30 frames = 1 second at 30fps)
for i in $(seq -w 0 29); do
    opacity=$(echo "scale=2; $i / 29 * 100" | bc)
    convert -size 1080x1920 xc:black \
        -fill white -gravity center \
        -pointsize 72 -annotate 0 "AospBook" \
        -channel A -evaluate set "${opacity}%" \
        "device/AospBook/bookphone/bootanimation/part0/${i}.png"
done

# Part 1: Pulsing dots (looping animation, 60 frames = 2 seconds)
for i in $(seq -w 0 59); do
    phase=$(echo "scale=4; $i / 60 * 3.14159 * 2" | bc)
    # ... generate frame with animated dots
    convert -size 1080x1920 xc:black \
        -fill white -gravity center \
        -pointsize 48 -annotate 0 "AospBook" \
        "device/AospBook/bookphone/bootanimation/part1/${i}.png"
done
```

**Step 2: Write desc.txt**

```
# device/AospBook/bookphone/bootanimation/desc.txt
1080 1920 30
c 1 10 part0
p 0 0 part1
```

Explanation:

- `1080 1920 30` -- 1080x1920 at 30 FPS
- `c 1 10 part0` -- Play part0 once to completion, pause 10 frames (0.33s)
- `p 0 0 part1` -- Loop part1 until boot completes, no pause between loops

**Step 3: Package the animation**

The ZIP must use **store** compression (no deflation), since the PNG files are
already compressed:

```bash
cd device/AospBook/bookphone/bootanimation

# Create the ZIP with store (no compression)
zip -0qry -i \*.txt \*.png \*.wav @ bootanimation.zip *.txt part*

# Verify the contents
unzip -l bootanimation.zip
```

The `-0` flag is critical. If you use default compression, the boot animation
player will fail to read the frames efficiently, causing stuttering or failure.

**Step 4: Include in the build**

In `device.mk`:

```makefile
PRODUCT_COPY_FILES += \
    device/AospBook/bookphone/bootanimation/bootanimation.zip:$(TARGET_COPY_OUT_PRODUCT)/media/bootanimation.zip
```

### 63.6.4 Testing the Boot Animation

You can test the boot animation without a full rebuild:

```bash
# Push directly to a running emulator
adb root
adb remount
adb push bootanimation.zip /product/media/bootanimation.zip

# Restart the boot animation service
adb shell setprop service.bootanim.exit 0
adb shell start bootanim

# Watch it play, then stop:
adb shell setprop service.bootanim.exit 1
```

### 63.6.5 Boot Animation with Sound

Each part directory can contain an `audio.wav` file that plays when that part
starts:

```
bootanimation.zip
    desc.txt
    part0/
        audio.wav       # Plays when part0 starts
        00000.png
        ...
    part1/
        00000.png
        ...
```

The WAV file must be:

- PCM format (uncompressed)
- 16-bit or 24-bit
- Any sample rate (44100 Hz recommended)
- Mono or stereo

### 63.6.6 Dynamic Coloring

Android 12+ supports dynamic coloring in boot animations. Add a special line
after the resolution line in `desc.txt`:

```
1080 1920 30
dynamic_colors part1 #1A73E8 #34A853 #FBBC04 #EA4335
c 1 10 part0
p 0 0 part1
```

This tells the animation player to treat the R, G, B, A channels of frames
in `part1` as masks for four dynamic colors. The end colors are read from
system properties:

- `persist.bootanim.color1`
- `persist.bootanim.color2`
- `persist.bootanim.color3`
- `persist.bootanim.color4`

### 63.6.7 Boot Animation Source Code

The boot animation player is implemented at:

```
frameworks/base/cmds/bootanimation/
    BootAnimation.cpp          # Main animation player
    BootAnimation.h
    BootAnimationUtil.cpp      # Utility functions
    bootanimation_main.cpp     # Entry point
    audioplay.cpp              # Audio playback
    bootanim.rc                # init service definition
```

The `bootanim.rc` file defines the init service:

```
# frameworks/base/cmds/bootanimation/bootanim.rc
service bootanim /system/bin/bootanimation
    class core animation
    user graphics
    group graphics audio
    disabled
    oneshot
```

---

## 63.7 Customizing SystemUI

SystemUI is the user-facing layer that draws the status bar, notification shade,
quick settings, lock screen, and navigation bar. Customizing it is one of the
most visible changes in a custom ROM.

The source lives at:

```
frameworks/base/packages/SystemUI/
```

### 63.7.1 SystemUI Architecture Overview

```mermaid
graph TD
    subgraph "SystemUI Process"
        A[SystemUIApplication] --> B[StatusBar]
        A --> C[NavigationBar]
        A --> D[NotificationShade]
        A --> E[QuickSettings]
        A --> F[LockScreen]
        A --> G[VolumeDialog]
        A --> H[PowerMenu]
        A --> I[Recents]
    end

    subgraph "Key Source Directories"
        B --> B1["statusbar/"]
        C --> C1["navigationbar/"]
        D --> D1["shade/"]
        E --> E1["qs/"]
        F --> F1["keyguard/"]
    end
```

### 63.7.2 Customizing via RRO (Non-Invasive)

The simplest way to customize SystemUI is through an RRO. SystemUI exposes
many configuration values in its own `config.xml`:

```
frameworks/base/packages/SystemUI/res/values/config.xml
```

Create a SystemUI overlay:

```
device/AospBook/bookphone/overlay/BookSystemUIOverlay/
    Android.bp
    AndroidManifest.xml
    res/
        values/
            config.xml
            dimens.xml
            colors.xml
```

**Android.bp**:

```json
// device/AospBook/bookphone/overlay/BookSystemUIOverlay/Android.bp

runtime_resource_overlay {
    name: "BookSystemUIOverlay",
    sdk_version: "current",
    product_specific: true,
}
```

**AndroidManifest.xml**:

```xml
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="com.aospbook.overlay.systemui">

    <application android:hasCode="false" />

    <overlay
        android:targetPackage="com.android.systemui"
        android:isStatic="true"
        android:priority="10"
        />
</manifest>
```

**res/values/config.xml** -- SystemUI configuration overrides:

```xml
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <!-- Quick Settings: number of columns -->
    <integer name="quick_settings_num_columns">4</integer>

    <!-- Quick Settings: maximum number of rows -->
    <integer name="quick_settings_max_rows">3</integer>

    <!-- Quick QS Panel: max tiles shown when collapsed -->
    <integer name="quick_qs_panel_max_tiles">6</integer>

    <!-- Quick QS Panel: max rows when collapsed -->
    <integer name="quick_qs_panel_max_rows">2</integer>

    <!-- Navigation bar: enable dead zone -->
    <bool name="config_useDeadZone">false</bool>

    <!-- Navigation bar: auto-dim when wallpaper not visible -->
    <bool name="config_navigation_bar_enable_auto_dim_no_visible_wallpaper">false</bool>

    <!-- Lock screen display timeout (milliseconds) -->
    <integer name="config_lockScreenDisplayTimeout">15000</integer>

    <!-- Enable custom lockscreen shortcuts -->
    <bool name="custom_lockscreen_shortcuts_enabled">true</bool>

    <!-- Enable long-press to customize lock screen -->
    <bool name="long_press_keyguard_customize_lockscreen_enabled">true</bool>
</resources>
```

**res/values/dimens.xml** -- dimension overrides:

```xml
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <!-- Status bar height (slightly taller for better touch targets) -->
    <dimen name="status_bar_height">28dp</dimen>

    <!-- Status bar padding -->
    <dimen name="status_bar_padding_start">8dp</dimen>
    <dimen name="status_bar_padding_end">8dp</dimen>
    <dimen name="status_bar_padding_top">0dp</dimen>

    <!-- Quick settings tile padding -->
    <dimen name="qs_tile_margin_horizontal">4dp</dimen>

    <!-- Rounded corner radius for QS tiles -->
    <dimen name="qs_corner_radius">16dp</dimen>
</resources>
```

**res/values/colors.xml** -- color overrides:

```xml
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <!-- Status bar icon tint in light mode -->
    <color name="light_mode_icon_color_single_tone">#FF212121</color>

    <!-- Status bar icon tint in dark mode -->
    <color name="dark_mode_icon_color_single_tone">#FFFAFAFA</color>
</resources>
```

### 63.7.3 Customizing the Status Bar Layout

The status bar layout is defined in:

```
frameworks/base/packages/SystemUI/res/layout/status_bar.xml
```

The root view is `PhoneStatusBarView` which contains:

```xml
<!-- frameworks/base/packages/SystemUI/res/layout/status_bar.xml (structure) -->
<PhoneStatusBarView>
    <ImageView android:id="@+id/notification_lights_out" />
    <LinearLayout android:id="@+id/status_bar_contents">
        <FrameLayout android:id="@+id/status_bar_start_side_container">
            <!-- Notification icons, clock -->
        </FrameLayout>
        <android.widget.Space />
        <LinearLayout android:id="@+id/status_bar_end_side_content">
            <!-- System icons (wifi, battery, etc.) -->
        </LinearLayout>
    </LinearLayout>
</PhoneStatusBarView>
```

To customize the status bar layout without modifying source:

1. **Move the clock to the center or right** -- Override the layout via RRO
2. **Add custom status bar icons** -- Add drawable overlays
3. **Change the battery icon style** -- Override `battery_percentage_view.xml`

For deeper modifications (e.g., adding a new status bar indicator), you need
to modify the SystemUI source directly.

### 63.7.4 Modifying Quick Settings Tiles

Quick Settings tiles are registered in SystemUI's Dagger dependency injection
graph. To add a custom tile:

**Step 1: Create the tile class**

```java
// frameworks/base/packages/SystemUI/src/com/android/systemui/qs/tiles/BookModeTile.java
package com.android.systemui.qs.tiles;

import android.content.Intent;
import android.os.Handler;
import android.os.Looper;
import android.service.quicksettings.Tile;
import android.view.View;

import com.android.internal.logging.MetricsLogger;
import com.android.systemui.dagger.qualifiers.Background;
import com.android.systemui.dagger.qualifiers.Main;
import com.android.systemui.plugins.qs.QSTile;
import com.android.systemui.qs.QSHost;
import com.android.systemui.qs.tileimpl.QSTileImpl;
import com.android.systemui.res.R;

import javax.inject.Inject;

/**
 * Quick Settings tile for AospBook's custom "Book Mode" feature.
 * Toggles a hypothetical reading mode that adjusts display warmth
 * and reduces blue light.
 */
public class BookModeTile extends QSTileImpl<QSTile.BooleanState> {
    private boolean mEnabled = false;

    @Inject
    public BookModeTile(
            QSHost host,
            @Background Looper backgroundLooper,
            @Main Handler mainHandler) {
        super(host, backgroundLooper, mainHandler);
    }

    @Override
    public BooleanState newTileState() {
        return new BooleanState();
    }

    @Override
    protected void handleClick(View view) {
        mEnabled = !mEnabled;
        refreshState();
    }

    @Override
    protected void handleUpdateState(BooleanState state, Object arg) {
        state.value = mEnabled;
        state.label = "Book Mode";
        state.contentDescription = "Book Mode";
        state.state = mEnabled ? Tile.STATE_ACTIVE : Tile.STATE_INACTIVE;
        state.icon = ResourceIcon.get(mEnabled
            ? R.drawable.ic_book_mode_on
            : R.drawable.ic_book_mode_off);
    }

    @Override
    public int getMetricsCategory() {
        return MetricsLogger.QS_CUSTOM;
    }

    @Override
    public Intent getLongClickIntent() {
        return new Intent("com.aospbook.action.BOOK_MODE_SETTINGS");
    }

    @Override
    public CharSequence getTileLabel() {
        return "Book Mode";
    }
}
```

**Step 2: Register the tile in the tile factory**

The tile must be added to the `QSModule` or `QSTileHost` so that it can be
instantiated. The exact mechanism depends on the AOSP version -- current AOSP
uses Dagger `@IntoMap` annotations.

### 63.7.5 Theme Overlays for SystemUI

Material You (Android 12+) uses dynamic color extraction. To set a default
color scheme for your ROM, use a theme overlay:

```xml
<!-- device/AospBook/bookphone/overlay/BookSystemUIOverlay/res/values/styles.xml -->
<resources>
    <!-- Override the default accent color seed -->
    <!-- This affects Material You theming when no wallpaper-extracted color is available -->
    <color name="system_accent1_500">#1A73E8</color>  <!-- Google Blue -->
    <color name="system_accent2_500">#5F6368</color>  <!-- Gray -->
    <color name="system_accent3_500">#34A853</color>  <!-- Green -->
</resources>
```

### 63.7.6 Customizing the Navigation Bar

The navigation bar configuration is controlled by system properties and
framework configs:

```makefile
# In device.mk -- force gesture navigation as default
PRODUCT_PRODUCT_PROPERTIES += \
    ro.boot.vendor.overlay.theme=com.android.internal.systemui.navbar.gestural

# Or force 3-button navigation:
# ro.boot.vendor.overlay.theme=com.android.internal.systemui.navbar.threebutton
```

To customize navigation bar button icons, overlay the drawables in the
navigation bar overlay packages:

```
frameworks/base/packages/overlays/NavigationBarMode*/
```

### 63.7.7 SystemUI Build Integration

SystemUI is built as a system app via:

```
frameworks/base/packages/SystemUI/Android.bp
```

To include your modifications, ensure that any new source files are added to
the `srcs` list in the build file, or placed in a directory that is already
included via a glob pattern.

---

## 63.8 Building and Flashing

### 63.8.1 The Build Command

With our device configuration in place, build the ROM:

```bash
# Source the environment (if not already done)
source build/envsetup.sh

# Select our target
lunch bookphone-trunk_staging-userdebug

# Build everything
# 'm' is the AOSP build command (wrapper around Soong/Ninja)
m

# Or with explicit parallelism:
m -j$(nproc)
```

The `m` command:

1. Runs Soong to process all `Android.bp` files
2. Runs Kati to process all `Android.mk` files
3. Generates `build.ninja` in the output directory
4. Invokes Ninja to execute the build plan

### 63.8.2 Build Output Structure

After a successful build, the output lives in `out/target/product/bookdevice/`:

```
out/target/product/bookdevice/
    android-info.txt            # Build info for fastboot
    boot.img                    # Kernel + ramdisk
    vendor_boot.img             # Vendor ramdisk
    super.img                   # Dynamic partitions container
    system.img                  # System partition image
    system_ext.img              # System extension partition
    vendor.img                  # Vendor partition image
    product.img                 # Product partition image
    userdata.img                # Empty userdata partition
    cache.img                   # Cache partition
    ramdisk.img                 # Root ramdisk
    kernel-ranchu               # Kernel binary
    system/                     # Staging directory for system partition
    vendor/                     # Staging directory for vendor partition
    product/                    # Staging directory for product partition
    obj/                        # Intermediate build objects
    symbols/                    # Unstripped binaries (for debugging)
```

### 63.8.3 Understanding Partition Images

```mermaid
graph TD
    subgraph "super.img (Dynamic Partitions)"
        A["system.img"] --> A1["Framework, apps, libraries"]
        B["system_ext.img"] --> B1["System extensions"]
        C["vendor.img"] --> C1["HALs, firmware, vendor apps"]
        D["product.img"] --> D1["Product customizations, our apps"]
        E["system_dlkm.img"] --> E1["Dynamic kernel modules"]
    end

    F["boot.img"] --> F1["Kernel + generic ramdisk"]
    G["vendor_boot.img"] --> G1["Vendor ramdisk + kernel modules"]
    H["userdata.img"] --> H1["User data (empty at build time)"]

    style D fill:#fff3e0
```

### 63.8.4 Launching the Emulator

The AOSP build system includes an `emulator` command that launches the
Android Emulator with the just-built images:

```bash
# Launch the emulator with our custom ROM
emulator

# With additional options:
emulator \
    -gpu swiftshader_indirect \   # Software GPU (works in headless VMs)
    -memory 4096 \                # 4 GB RAM
    -cores 4 \                    # 4 CPU cores
    -no-snapshot \                # Start fresh
    -verbose                      # Debug output
```

The emulator automatically picks up the images from
`$ANDROID_PRODUCT_OUT` (which is `out/target/product/bookdevice/`).

Key emulator flags:

| Flag | Description |
|------|-------------|
| `-gpu host` | Use host GPU acceleration (fastest, requires GPU) |
| `-gpu swiftshader_indirect` | Software rendering (works everywhere) |
| `-memory <MB>` | Guest RAM in MB |
| `-cores <N>` | Guest CPU cores |
| `-no-snapshot` | Don't use quickboot snapshot |
| `-wipe-data` | Reset userdata partition |
| `-writable-system` | Allow writes to system partition |
| `-show-kernel` | Show kernel log in terminal |
| `-logcat '*:V'` | Show logcat in terminal |
| `-selinux permissive` | Set SELinux to permissive (debugging) |

### 63.8.5 Flashing to a Physical Device

For physical devices, use `fastboot`:

```bash
# Reboot device into bootloader
adb reboot bootloader

# Flash all images at once
fastboot flashall

# Or flash individual partitions:
fastboot flash boot boot.img
fastboot flash vendor_boot vendor_boot.img
fastboot flash super super.img
# fastboot flash userdata userdata.img  # Warning: this wipes user data!

# Reboot
fastboot reboot
```

For devices using dynamic partitions (Android 10+), you may need to use
`fastboot flash` with the `super` image or use `fastbootd` mode:

```bash
# Enter fastbootd (userspace fastboot)
fastboot reboot fastboot

# Flash dynamic partition images
fastboot flash system system.img
fastboot flash system_ext system_ext.img
fastboot flash vendor vendor.img
fastboot flash product product.img

# Reboot
fastboot reboot
```

### 63.8.6 Incremental Builds

After the initial full build, incremental builds only rebuild changed modules.
This is dramatically faster:

```bash
# Rebuild only changed modules
m

# Rebuild a specific module
m BookSampleApp

# Rebuild SystemUI only
m SystemUI

# Rebuild the system image (after rebuilding individual modules)
m systemimage

# Rebuild the product image
m productimage

# Rebuild a specific image
make vendorimage
```

Incremental build tips:

| Operation | Time | Command |
|-----------|------|---------|
| Full build (first time) | 2-4 hours | `m` |
| Full build (with ccache) | 30-60 min | `m` |
| Rebuild after Java change | 1-5 min | `m ModuleName` |
| Rebuild after C++ change | 2-10 min | `m ModuleName` |
| Rebuild system image | 5-15 min | `m systemimage` |
| Rebuild after resource change | 1-3 min | `m ModuleName` |
| Rebuild after makefile change | 10-30 min | `m` (Soong re-analysis) |

### 63.8.7 Build Variants and Their Impact

| Variant | `ro.debuggable` | `adb` Default | Optimizations | Use |
|---------|-----------------|---------------|---------------|-----|
| `user` | 0 | Off | Full (proguard, minification) | Release |
| `userdebug` | 1 | On | Partial (some kept for debugging) | Development |
| `eng` | 1 | On, rooted | Minimal (no proguard) | Deep debugging |

The build variant affects:

- Whether `adb root` works
- Whether the system partition is writable
- Proguard/R8 optimization levels
- Inclusion of debugging tools (strace, valgrind, etc.)
- SELinux mode (eng sometimes starts permissive)

```bash
# Build a release (user) image
lunch bookphone-trunk_staging-user
m

# Build a debug (eng) image
lunch bookphone-trunk_staging-eng
m
```

### 63.8.8 Build System Troubleshooting

Common build errors and solutions:

| Error | Cause | Solution |
|-------|-------|----------|
| `No rule to make target` | Module not found | Check `PRODUCT_PACKAGES` and `Android.bp` module name |
| `ninja: error: depends on nonexistent` | Missing dependency | Add the dependency to `static_libs` or `shared_libs` |
| `SELinux denials` | Missing SELinux policy | Add `allow` rules, run `audit2allow` |
| `FAILED: out/.../module.jar` | Java compilation error | Check source code syntax and imports |
| `Insufficient disk space` | Build output exceeds disk | Free space or move `out/` to larger disk |
| `Killed (out of memory)` | OOM during linking | Reduce `-j` parallelism or add swap |

---

## 63.9 Debugging Your ROM

### 63.9.1 logcat -- The Primary Debugging Tool

`logcat` is the universal debugging tool for Android. It reads the kernel
ring buffer and the Android logging daemon.

```bash
# Basic logcat (all messages)
adb logcat

# Filter by tag
adb logcat -s BookService:V

# Filter by priority (Verbose, Debug, Info, Warn, Error, Fatal)
adb logcat '*:W'    # Only warnings and above

# Filter by multiple tags
adb logcat BookService:V BookSampleApp:D '*:S'

# Format options
adb logcat -v threadtime    # Show thread ID and timestamp
adb logcat -v color         # Colorized output
adb logcat -v long          # Detailed format

# Save to file
adb logcat -d > logcat.txt  # Dump and exit
adb logcat -f /sdcard/logcat.txt  # Write to device

# Clear the log buffer
adb logcat -c

# Show kernel log (dmesg via logcat)
adb logcat -b kernel
```

### 63.9.2 dumpsys -- Querying System Services

`dumpsys` prints the internal state of system services. Essential for debugging
service issues:

```bash
# List all available services
adb shell dumpsys -l

# Query a specific service
adb shell dumpsys activity
adb shell dumpsys window
adb shell dumpsys package com.aospbook.sample
adb shell dumpsys overlay    # RRO overlay state

# Our custom service (if we implemented dump())
adb shell dumpsys aospbook

# Query with timeout (useful for stuck services)
adb shell dumpsys -t 10 activity

# Common dumpsys targets for ROM debugging:
adb shell dumpsys activity activities  # Activity stack
adb shell dumpsys window displays      # Display information
adb shell dumpsys package              # All package info
adb shell dumpsys meminfo              # Memory usage
adb shell dumpsys battery              # Battery state
adb shell dumpsys alarm                # Scheduled alarms
adb shell dumpsys jobscheduler         # Scheduled jobs
adb shell dumpsys notification         # Notification state
```

### 63.9.3 bugreport -- Comprehensive System Snapshot

A bugreport captures the entire system state at a point in time:

```bash
# Generate a bugreport (saves to device, then pulls)
adb bugreport bugreport.zip

# The ZIP contains:
#   bugreport-<device>-<date>.txt  # Main report (huge)
#   dumpstate_board.bin            # Board-specific dump
#   FS/                            # File system snapshots
#   proto/                         # Protobuf data
```

The bugreport includes logcat, dumpsys output for all services, kernel logs,
process lists, file system information, and more. It is the primary artifact
for bug investigation.

### 63.9.4 Perfetto -- Performance Tracing

Perfetto is AOSP's modern tracing system. It replaces the older `systrace`
tool.

```bash
# Record a 10-second trace with common categories
adb shell perfetto \
    --txt \
    --config - \
    --out /data/misc/perfetto-traces/trace.perfetto-trace \
    << 'EOF'
buffers: {
    size_kb: 63488
    fill_policy: RING_BUFFER
}
data_sources: {
    config {
        name: "linux.ftrace"
        ftrace_config {
            ftrace_events: "sched/sched_switch"
            ftrace_events: "power/suspend_resume"
            ftrace_events: "sched/sched_wakeup"
            ftrace_events: "sched/sched_wakeup_new"
            ftrace_events: "sched/sched_process_exit"
            ftrace_events: "sched/sched_process_free"
            ftrace_events: "task/task_newtask"
            ftrace_events: "task/task_rename"
            atrace_categories: "am"
            atrace_categories: "wm"
            atrace_categories: "view"
            atrace_categories: "gfx"
            atrace_categories: "input"
        }
    }
}
data_sources: {
    config {
        name: "linux.process_stats"
    }
}
duration_ms: 10000
EOF

# Pull the trace
adb pull /data/misc/perfetto-traces/trace.perfetto-trace .

# Open in the Perfetto UI
# https://ui.perfetto.dev/
```

### 63.9.5 Winscope -- Window and Layer Tracing

Winscope captures window manager and surface flinger state transitions,
essential for debugging UI layout issues:

```bash
# Start window trace
adb shell cmd window tracing start

# ... reproduce the issue ...

# Stop and collect trace
adb shell cmd window tracing stop
adb pull /data/misc/wmtrace/wm_trace.winscope .

# Start layer trace (SurfaceFlinger)
adb shell su -c 'service call SurfaceFlinger 1025 i32 1'

# Stop layer trace
adb shell su -c 'service call SurfaceFlinger 1025 i32 0'
adb pull /data/misc/wmtrace/layers_trace.winscope .

# Open traces in Winscope:
# https://winscope.googleplex.com/ (internal)
# Or use the local Winscope included in the AOSP tree:
# development/tools/winscope/
```

### 63.9.6 Debugging Boot Issues

When your custom ROM fails to boot:

```mermaid
flowchart TD
    A["ROM doesn't boot"] --> B{Shows boot animation?}
    B -->|Yes| C{Animation loops forever?}
    B -->|No| D{Shows bootloader?}

    C -->|Yes| E["System server crash loop"]
    C -->|No| F["Late boot issue"]

    D -->|Yes| G["Kernel panic or init failure"]
    D -->|No| H["Bootloader/flash issue"]

    E --> E1["adb logcat -b all | grep -E 'FATAL|Crash|E System'"]
    E --> E2["Check SELinux: adb shell getenforce"]
    E --> E3["Try: adb shell setprop persist.sys.rescue_level 1"]

    F --> F1["adb logcat -s ActivityManager"]
    F --> F2["adb shell dumpsys activity"]

    G --> G1["emulator -show-kernel -verbose"]
    G --> G2["Check kernel cmdline and fstab"]

    H --> H1["Verify images: file *.img"]
    H --> H2["Re-flash with fastboot flashall -w"]

    style A fill:#ffcdd2
    style E fill:#fff3e0
    style F fill:#fff3e0
    style G fill:#ffcdd2
    style H fill:#ffcdd2
```

**Common boot issues and solutions:**

1. **Boot loop (animation never ends)**

```bash
# Check system_server logs:
adb logcat -b all | grep -E "FATAL|System.err|AndroidRuntime" | head -50

# Most common cause: missing SELinux policy
# Temporarily set permissive for debugging:
adb shell setenforce 0
# Then find the denials:
adb logcat | grep "avc: denied"
```

2. **Crash in custom service**

```bash
# Check if system_server is restarting:
adb logcat -s ActivityManager | grep "Start proc"

# Check for our service specifically:
adb logcat -s BookService

# Full exception traces:
adb logcat -s AndroidRuntime
```

3. **Missing module / library**

```bash
# Check if the module was installed:
adb shell ls /product/app/BookSampleApp/
adb shell ls /system/framework/BookService.jar

# Check the build output:
ls out/target/product/bookdevice/product/app/BookSampleApp/
```

### 63.9.7 SELinux Debugging

SELinux denials are the most common cause of issues in custom ROMs:

```bash
# Check SELinux mode
adb shell getenforce
# Expected: Enforcing

# View SELinux denials
adb logcat | grep "avc: denied"

# Example denial:
# avc: denied { add } for service=aospbook pid=1234
#   scontext=u:r:system_server:s0
#   tcontext=u:object_r:default_android_service:s0
#   tclass=service_manager

# Generate policy from denials using audit2allow:
adb logcat -d | grep "avc: denied" | audit2allow -p out/target/product/bookdevice/vendor/etc/selinux/

# This outputs allow rules you can add to your .te files
```

### 63.9.8 The Debug Toolchain

```mermaid
graph LR
    A["Issue Reported"] --> B["logcat"]
    B --> C{Type?}
    C -->|Crash| D["tombstone + stack trace"]
    C -->|ANR| E["traces.txt + dumpsys"]
    C -->|Performance| F["Perfetto trace"]
    C -->|UI Layout| G["Winscope + dump view hierarchy"]
    C -->|SELinux| H["avc: denied + audit2allow"]
    C -->|Service| I["dumpsys {service}"]

    D --> J["addr2line / ndk-stack"]
    E --> K["Analyze main/binder thread blocks"]
    F --> L["ui.perfetto.dev"]
    G --> M["Winscope viewer"]

    style A fill:#ffcdd2
    style L fill:#e8f5e9
    style M fill:#e8f5e9
```

### 63.9.9 Useful adb Commands for ROM Development

```bash
# ============================================================
# System Properties
# ============================================================
adb shell getprop ro.build.fingerprint
adb shell getprop ro.aospbook.version
adb shell getprop | grep aospbook

# ============================================================
# Package Management
# ============================================================
adb shell pm list packages | grep aospbook
adb shell pm path com.aospbook.sample
adb shell pm dump com.aospbook.sample | head -50

# ============================================================
# Service Management
# ============================================================
adb shell service list | grep aospbook
adb shell service check aospbook

# ============================================================
# Process Information
# ============================================================
adb shell ps -A | grep -E "system_server|aospbook"
adb shell dumpsys meminfo system_server

# ============================================================
# File System
# ============================================================
adb shell mount | grep -E "system|vendor|product"
adb shell df -h
adb shell ls -la /product/overlay/

# ============================================================
# RRO Overlay Status
# ============================================================
adb shell cmd overlay list
adb shell cmd overlay dump com.aospbook.overlay.framework
adb shell cmd overlay enable com.aospbook.overlay.framework
adb shell cmd overlay disable com.aospbook.overlay.framework

# ============================================================
# Boot Diagnostics
# ============================================================
adb shell dmesg | tail -100
adb shell cat /proc/bootconfig
adb shell cat /proc/cmdline
adb shell uptime
```

---

## 63.10 Distribution

### 63.10.1 Signing Overview

Android uses code signing to ensure the integrity and authenticity of every
APK and system image. There are four key types used in AOSP:

| Key | File Pair | Purpose |
|-----|-----------|---------|
| **testkey** | `testkey.pk8` / `testkey.x509.pem` | Default development signing |
| **platform** | `platform.pk8` / `platform.x509.pem` | System apps with `android.uid.system` |
| **shared** | `shared.pk8` / `shared.x509.pem` | Apps that share data (Contacts, Phone) |
| **media** | `media.pk8` / `media.x509.pem` | Media/download apps |

These default keys live at:

```
build/make/target/product/security/
```

**CRITICAL**: The keys in that directory are publicly known test keys. Any
ROM released with these keys is trivially vulnerable -- anyone can sign a
malicious APK with the same key and it will be accepted as a system update.

The `README` at `build/make/target/product/security/README` explicitly warns:

> "The test keys in this directory are used in development only and should
> NEVER be used to sign packages in publicly released images."

### 63.10.2 Generating Release Keys

Generate your own unique keys:

```bash
# Create a directory for your keys
mkdir -p device/AospBook/bookphone/keys
cd device/AospBook/bookphone/keys

# The make_key tool is provided by AOSP:
SUBJECT='/C=US/ST=California/L=Mountain View/O=AospBook/OU=ROM/CN=AospBook/emailAddress=rom@aospbook.example.com'

# Generate each key pair
# This will prompt for a password -- use a strong one for release keys
# For development, you can press Enter for no password
../../../../../../development/tools/make_key releasekey "$SUBJECT"
../../../../../../development/tools/make_key platform "$SUBJECT"
../../../../../../development/tools/make_key shared "$SUBJECT"
../../../../../../development/tools/make_key media "$SUBJECT"

# Verify the generated files
ls -la
# Expected:
#   releasekey.pk8
#   releasekey.x509.pem
#   platform.pk8
#   platform.x509.pem
#   shared.pk8
#   shared.x509.pem
#   media.pk8
#   media.x509.pem
```

Each `make_key` invocation creates two files:

- `*.pk8` -- The private key in PKCS#8 DER format
- `*.x509.pem` -- The public key certificate in X.509 PEM format

### 63.10.3 Configuring the Build to Use Release Keys

Tell the build system to use your keys instead of the test keys:

```makefile
# In device/AospBook/bookphone/bookphone.mk (or device.mk)

# Use our custom signing keys
PRODUCT_DEFAULT_DEV_CERTIFICATE := device/AospBook/bookphone/keys/releasekey

# Map APK signing to our keys
PRODUCT_CERTIFICATE_OVERRIDES := \
    testkey:device/AospBook/bookphone/keys/releasekey \
    platform:device/AospBook/bookphone/keys/platform \
    shared:device/AospBook/bookphone/keys/shared \
    media:device/AospBook/bookphone/keys/media
```

### 63.10.4 Signing the Build

There are two approaches to signing:

**Approach 1: Sign during build (development)**

With `PRODUCT_DEFAULT_DEV_CERTIFICATE` set, all APKs are automatically signed
during the build. This is the simplest approach.

**Approach 2: Sign after build (release)**

For production releases, build first, then sign separately:

```bash
# Step 1: Build target-files package
m dist

# The target-files ZIP is at:
# out/dist/bookphone-target_files-<build_id>.zip

# Step 2: Sign all APKs in the target-files
python3 build/make/tools/releasetools/sign_target_files_apks.py \
    -o \
    -d device/AospBook/bookphone/keys \
    --default_key_mappings device/AospBook/bookphone/keys \
    out/dist/bookphone-target_files-*.zip \
    out/dist/bookphone-target_files-signed.zip

# Step 3: Generate signed images from the signed target-files
python3 build/make/tools/releasetools/img_from_target_files.py \
    out/dist/bookphone-target_files-signed.zip \
    out/dist/bookphone-img-signed.zip
```

### 63.10.5 OTA Package Generation

OTA (Over The Air) packages allow you to distribute updates to existing users.

**Full OTA package** (contains the complete image):

```bash
# Generate from target-files
python3 build/make/tools/releasetools/ota_from_target_files.py \
    --package_key device/AospBook/bookphone/keys/releasekey \
    out/dist/bookphone-target_files-signed.zip \
    out/dist/bookphone-ota-full.zip
```

**Incremental OTA package** (contains only the diff from a previous build):

```bash
# Generate incremental OTA (from v1 to v2)
python3 build/make/tools/releasetools/ota_from_target_files.py \
    --package_key device/AospBook/bookphone/keys/releasekey \
    -i out/dist/bookphone-v1-target_files-signed.zip \
    out/dist/bookphone-v2-target_files-signed.zip \
    out/dist/bookphone-ota-v1-to-v2.zip
```

**OTA generation workflow:**

```mermaid
graph TD
    A["m dist"] --> B["target_files.zip"]
    B --> C["sign_target_files_apks.py"]
    C --> D["signed_target_files.zip"]
    D --> E["ota_from_target_files.py"]
    D --> F["img_from_target_files.py"]
    E --> G["Full OTA .zip"]
    F --> H["Flashable images .zip"]

    I["Previous build's target_files.zip"] --> J["ota_from_target_files.py -i"]
    D --> J
    J --> K["Incremental OTA .zip"]

    style B fill:#fff3e0
    style G fill:#e8f5e9
    style H fill:#e8f5e9
    style K fill:#e8f5e9
```

### 63.10.6 OTA Package Structure

An OTA package is a signed ZIP file containing:

```
ota_package.zip
    META-INF/
        com/
            android/
                metadata.pb        # OTA metadata (protobuf)
                metadata           # Legacy metadata
            google/
                android/
                    update-binary  # The OTA installer binary
                    updater-script # Installation script
    payload.bin                    # The actual update payload
    payload_properties.txt         # Payload metadata
    care_map.pb                    # Block mapping for dm-verity
```

### 63.10.7 Verified Boot and AVB

Android Verified Boot (AVB) ensures that boot images and partitions have not
been tampered with. For custom ROMs targeting real devices:

```bash
# Generate AVB signing key
openssl genrsa -out avb_custom_key.pem 4096

# Extract the public key for embedding in the bootloader
avbtool extract_public_key --key avb_custom_key.pem --output avb_custom_key.bin
```

Configure in `BoardConfig.mk`:

```makefile
# Use custom AVB key
BOARD_AVB_KEY_PATH := device/AospBook/bookphone/keys/avb_custom_key.pem
BOARD_AVB_ALGORITHM := SHA256_RSA4096
```

### 63.10.8 Build Fingerprint and Properties

The build fingerprint is the unique identifier for your ROM build. It follows
the format:

```
BRAND/PRODUCT/DEVICE:VERSION/BUILD_ID/BUILD_NUMBER:VARIANT/KEYS
```

Example:

```
AospBook/bookphone/bookdevice:16/AP3A.250318.001/eng.builder.20250318:userdebug/release-keys
```

Set it in your product makefile:

```makefile
# Custom build properties
PRODUCT_PROPERTY_OVERRIDES += \
    ro.build.display.id=AospBook-1.0-$(shell date +%Y%m%d) \
    ro.build.version.incremental=$(shell date +%Y%m%d%H%M%S) \
    ro.aospbook.version=1.0.0

# Build description (shown in Settings > About phone > Build number)
PRODUCT_BUILD_PROP_OVERRIDES += \
    BUILD_DISPLAY_ID=AospBook-1.0-$(shell date +%Y%m%d) \
    BUILD_VERSION_TAGS=release-keys
```

### 63.10.9 Distribution Checklist

Before releasing your custom ROM publicly:

```
[ ] Generate unique signing keys (NEVER use test keys)
[ ] Sign all APKs with release keys
[ ] Build with the "user" variant (not userdebug/eng)
[ ] Verify SELinux is enforcing: adb shell getenforce
[ ] Remove debugging tools and backdoors
[ ] Test OTA update path (both full and incremental)
[ ] Verify all apps launch and function correctly
[ ] Check that permissions work correctly
[ ] Test boot time and basic performance
[ ] Generate SHA256 checksums for all distributed files
[ ] Write release notes documenting changes
[ ] Set up a distribution server for OTA updates
```

### 63.10.10 Publishing Checksums

```bash
# Generate checksums for distribution files
sha256sum out/dist/bookphone-ota-full.zip > checksums.txt
sha256sum out/dist/bookphone-img-signed.zip >> checksums.txt

# Sign the checksums file with GPG for additional trust
gpg --sign --armor checksums.txt
```

---

## 63.11 Advanced: Kernel Customization

### 63.11.1 Kernel in AOSP

The AOSP emulator uses prebuilt Generic Kernel Image (GKI) kernels. The
kernel configuration for the x86_64 emulator is defined at:

```
device/generic/goldfish/board/kernel/x86_64.mk
```

This file shows:

```makefile
# device/generic/goldfish/board/kernel/x86_64.mk (key excerpts)
TARGET_KERNEL_USE ?= 6.12
KERNEL_ARTIFACTS_PATH := prebuilts/qemu-kernel/x86_64/$(TARGET_KERNEL_USE)
EMULATOR_KERNEL_FILE := $(KERNEL_ARTIFACTS_PATH)/kernel-$(TARGET_KERNEL_USE)
```

The prebuilt kernels live at:

```
prebuilts/qemu-kernel/x86_64/6.12/
    kernel-6.12              # The kernel binary
    gki_modules/             # GKI kernel modules
    goldfish_modules/        # Emulator-specific modules
```

### 63.11.2 GKI Architecture

Android's Generic Kernel Image (GKI) separates the kernel into:

```mermaid
graph TD
    subgraph "GKI Architecture"
        A["GKI Kernel (vmlinux)"] --> B["Core kernel"]
        A --> C["GKI modules (.ko)"]

        D["Vendor Kernel Modules"] --> E["Device-specific drivers"]
        D --> F["HAL kernel interfaces"]

        A --- G["KMI (Kernel Module Interface)"]
        D --- G
    end

    subgraph "Boot Flow"
        H["boot.img"] -->|contains| A
        I["vendor_boot.img"] -->|contains| D
        J["system_dlkm"] -->|contains| C
    end

    style G fill:#fff3e0
```

The KMI (Kernel Module Interface) is a stable ABI between the GKI kernel and
vendor modules, allowing them to be updated independently.

### 63.11.3 Building a Custom Kernel

To build a custom kernel for the emulator:

```bash
# Clone the kernel source
mkdir -p ~/kernel && cd ~/kernel
repo init -u https://android.googlesource.com/kernel/manifest \
    -b common-android-mainline
repo sync -j$(nproc)

# Build the kernel
# For x86_64 emulator:
BUILD_CONFIG=common/build.config.gki.x86_64 build/build.sh

# Or using Bazel (newer approach):
tools/bazel run //common:kernel_x86_64_dist
```

The kernel build produces:

```
out/android-mainline/dist/
    bzImage                  # Kernel binary
    vmlinux                  # Uncompressed kernel (for debugging)
    System.map               # Symbol map
    *.ko                     # Kernel modules
```

### 63.11.4 Using a Custom Kernel with the Emulator

```bash
# Option 1: Copy to prebuilts
cp out/android-mainline/dist/bzImage \
    prebuilts/qemu-kernel/x86_64/6.12/kernel-6.12

# Option 2: Specify at emulator launch
emulator -kernel /path/to/custom/bzImage

# Option 3: Set in build config
# In x86_64.mk:
# EMULATOR_KERNEL_FILE := /path/to/custom/kernel
```

### 63.11.5 Adding Custom Kernel Modules

Kernel modules extend kernel functionality without rebuilding the entire
kernel. For the emulator, vendor-specific modules are loaded from the vendor
ramdisk.

**Creating a simple kernel module:**

```c
// device/AospBook/bookphone/kernel_modules/bookmodule/bookmodule.c
#include <linux/init.h>
#include <linux/module.h>
#include <linux/kernel.h>

MODULE_LICENSE("GPL");
MODULE_AUTHOR("AospBook");
MODULE_DESCRIPTION("AospBook sample kernel module");
MODULE_VERSION("1.0");

static int __init bookmodule_init(void)
{
    printk(KERN_INFO "BookModule: Loaded (AospBook ROM kernel module)\n");
    return 0;
}

static void __exit bookmodule_exit(void)
{
    printk(KERN_INFO "BookModule: Unloaded\n");
}

module_init(bookmodule_init);
module_exit(bookmodule_exit);
```

**Makefile for out-of-tree module:**

```makefile
# device/AospBook/bookphone/kernel_modules/bookmodule/Makefile
obj-m += bookmodule.o

KERNEL_SRC ?= /path/to/kernel/source

all:
	$(MAKE) -C $(KERNEL_SRC) M=$(PWD) modules

clean:
	$(MAKE) -C $(KERNEL_SRC) M=$(PWD) clean
```

**Build and install:**

```bash
# Build the module against the emulator kernel
cd device/AospBook/bookphone/kernel_modules/bookmodule
make KERNEL_SRC=~/kernel/common ARCH=x86_64 CROSS_COMPILE=x86_64-linux-gnu-

# The module is at:
ls bookmodule.ko

# Test on the emulator:
adb root
adb push bookmodule.ko /data/local/tmp/
adb shell insmod /data/local/tmp/bookmodule.ko
adb shell dmesg | grep BookModule
# Expected: BookModule: Loaded (AospBook ROM kernel module)

# Unload:
adb shell rmmod bookmodule
```

### 63.11.6 Including Kernel Modules in the Build

To include your module in the build automatically:

```makefile
# In device.mk
PRODUCT_COPY_FILES += \
    device/AospBook/bookphone/kernel_modules/bookmodule/bookmodule.ko:$(TARGET_COPY_OUT_VENDOR)/lib/modules/bookmodule.ko

# Or add to the vendor ramdisk modules (loaded at boot):
BOARD_VENDOR_RAMDISK_KERNEL_MODULES += \
    device/AospBook/bookphone/kernel_modules/bookmodule/bookmodule.ko
```

For automatic loading at boot, add to an init script:

```
# device/AospBook/bookphone/init/init.bookphone.rc
on boot
    insmod /vendor/lib/modules/bookmodule.ko
```

### 63.11.7 Kernel Configuration Tuning

The kernel configuration (`defconfig`) controls which features are compiled
into the kernel. For the emulator:

```bash
# View current kernel config on a running device
adb shell cat /proc/config.gz | gunzip > current_config.txt

# Or from the kernel build:
cat out/android-mainline/.config
```

Common kernel configuration tweaks for custom ROMs:

| Config Option | Default | Custom | Purpose |
|---------------|---------|--------|---------|
| `CONFIG_HZ` | 250 | 1000 | Higher tick rate for responsiveness |
| `CONFIG_SCHED_AUTOGROUP` | n | y | Auto-group scheduling |
| `CONFIG_TCP_CONG_BBR` | n | y | BBR congestion control |
| `CONFIG_ZRAM` | m | y | Compressed RAM swap |
| `CONFIG_KSM` | n | y | Kernel same-page merging |
| `CONFIG_TRANSPARENT_HUGEPAGE` | n | y | Transparent huge pages |

### 63.11.8 Kernel Module Lifecycle

```mermaid
graph TD
    A["Board-level ramdisk modules"] -->|"BOARD_VENDOR_RAMDISK_KERNEL_MODULES"| B["Loaded in first_stage_init"]
    C["Vendor kernel modules"] -->|"BOARD_VENDOR_KERNEL_MODULES"| D["Loaded by init.rc"]
    E["System DLKM modules"] -->|"BOARD_SYSTEM_KERNEL_MODULES"| F["Loaded after system mount"]

    B --> G["Essential for mounting partitions"]
    D --> H["Hardware drivers, sensors, etc."]
    F --> I["Optional kernel features"]

    subgraph "Module Loading Order"
        G --> H
        H --> I
    end
```

The Goldfish emulator defines specific ramdisk modules that are essential for
early boot in `device/generic/goldfish/board/kernel/x86_64.mk`:

```makefile
RAMDISK_KERNEL_MODULES := \
    virtio_dma_buf.ko \
    virtio-rng.ko \

RAMDISK_SYSTEM_KERNEL_MODULES := \
    virtio_blk.ko \
    virtio_console.ko \
    virtio_pci.ko \
    virtio_pci_legacy_dev.ko \
    virtio_pci_modern_dev.ko \
    vmw_vsock_virtio_transport.ko \
```

These modules are loaded during first-stage init before the system partition
is even mounted, because they provide the virtual hardware drivers needed to
access the disk.

---

## 63.12 Advanced: HAL Customization

### 63.12.1 HAL Architecture in Android

The Hardware Abstraction Layer (HAL) sits between the Android framework and the
Linux kernel, providing a stable interface for hardware access:

```mermaid
graph TD
    subgraph "Application Framework"
        A["System Services (Java)"]
    end

    subgraph "HAL Layer"
        B["AIDL HAL Interface (.aidl)"]
        C["HAL Implementation (C++)"]
    end

    subgraph "Kernel"
        D["Device Drivers"]
    end

    A -->|Binder IPC| B
    B --> C
    C -->|ioctl / sysfs| D

    style B fill:#fff3e0
```

Modern Android uses AIDL HALs (replacing the older HIDL HALs). The HAL
interfaces are defined at:

```
hardware/interfaces/
```

This directory contains AIDL definitions for audio, camera, sensors, health,
graphics, and dozens of other hardware subsystems.

The Goldfish emulator provides its own HAL implementations at:

```
device/generic/goldfish/hals/
    audio/        # Audio HAL
    camera/       # Camera HAL
    fingerprint/  # Fingerprint HAL
    gnss/         # GNSS (GPS) HAL
    gralloc/      # Graphics buffer allocation
    hwc3/         # Hardware Composer 3
    radio/        # Telephony radio HAL
    sensors/      # Sensors HAL
```

### 63.12.2 Creating a Custom AIDL HAL

Let us create a custom HAL for a hypothetical "book light" hardware feature.
This demonstrates the full HAL lifecycle: interface definition, default
implementation, init service, SELinux policy, and VINTF manifest entry.

**Directory structure:**

```
device/AospBook/bookphone/hal/booklight/
    Android.bp
    aidl/
        com/aospbook/hardware/light/
            IBookLight.aidl
            BookLightState.aidl
    default/
        Android.bp
        BookLight.cpp
        BookLight.h
        booklight-default.rc
        booklight-default.xml
```

### 63.12.3 Defining the AIDL Interface

**IBookLight.aidl**:

```java
// device/AospBook/bookphone/hal/booklight/aidl/com/aospbook/hardware/light/IBookLight.aidl
package com.aospbook.hardware.light;

import com.aospbook.hardware.light.BookLightState;

/**
 * HAL interface for the AospBook reading light.
 *
 * This is a custom AIDL HAL that demonstrates how to define
 * and implement a hardware abstraction layer.
 */
@VintfStability
interface IBookLight {
    /**
     * Get the current light state.
     */
    BookLightState getState();

    /**
     * Set the light brightness (0-255).
     */
    void setBrightness(int brightness);

    /**
     * Set the color temperature in Kelvin (2700-6500).
     */
    void setColorTemperature(int kelvin);

    /**
     * Enable or disable the reading light.
     */
    void setEnabled(boolean enabled);

    /**
     * Get the supported color temperature range.
     * Returns [min, max] in Kelvin.
     */
    int[] getSupportedTemperatureRange();
}
```

**BookLightState.aidl**:

```java
// device/AospBook/bookphone/hal/booklight/aidl/com/aospbook/hardware/light/BookLightState.aidl
package com.aospbook.hardware.light;

/**
 * Parcelable representing the current state of the book light.
 */
@VintfStability
parcelable BookLightState {
    boolean enabled;
    int brightness;           // 0-255
    int colorTemperature;     // Kelvin (2700-6500)
}
```

**Android.bp for the AIDL library:**

```json
// device/AospBook/bookphone/hal/booklight/Android.bp

aidl_interface {
    name: "com.aospbook.hardware.light",
    vendor_available: true,
    srcs: ["aidl/com/aospbook/hardware/light/*.aidl"],
    stability: "vintf",
    backend: {
        cpp: {
            enabled: true,
        },
        java: {
            enabled: true,
            sdk_version: "module_current",
        },
        ndk: {
            enabled: true,
        },
    },
    versions: ["1"],
}
```

### 63.12.4 Implementing the Default HAL

**BookLight.h**:

```cpp
// device/AospBook/bookphone/hal/booklight/default/BookLight.h
#pragma once

#include <aidl/com/aospbook/hardware/light/BnBookLight.h>
#include <aidl/com/aospbook/hardware/light/BookLightState.h>

namespace aidl::com::aospbook::hardware::light {

/**
 * Default implementation of the BookLight HAL.
 *
 * For the emulator, this is a software-only implementation that
 * stores state in memory. On a real device, this would interface
 * with kernel drivers via sysfs or ioctl.
 */
class BookLight : public BnBookLight {
public:
    BookLight();

    ndk::ScopedAStatus getState(BookLightState* _aidl_return) override;
    ndk::ScopedAStatus setBrightness(int32_t brightness) override;
    ndk::ScopedAStatus setColorTemperature(int32_t kelvin) override;
    ndk::ScopedAStatus setEnabled(bool enabled) override;
    ndk::ScopedAStatus getSupportedTemperatureRange(
        std::vector<int32_t>* _aidl_return) override;

private:
    std::mutex mLock;
    BookLightState mState;

    static constexpr int32_t kMinTemperature = 2700;
    static constexpr int32_t kMaxTemperature = 6500;
    static constexpr int32_t kDefaultTemperature = 4000;
    static constexpr int32_t kMaxBrightness = 255;
};

}  // namespace aidl::com::aospbook::hardware::light
```

**BookLight.cpp**:

```cpp
// device/AospBook/bookphone/hal/booklight/default/BookLight.cpp
#include "BookLight.h"

#include <android-base/logging.h>

namespace aidl::com::aospbook::hardware::light {

BookLight::BookLight() {
    mState.enabled = false;
    mState.brightness = 0;
    mState.colorTemperature = kDefaultTemperature;
    LOG(INFO) << "BookLight HAL initialized";
}

ndk::ScopedAStatus BookLight::getState(BookLightState* _aidl_return) {
    std::lock_guard<std::mutex> lock(mLock);
    *_aidl_return = mState;
    return ndk::ScopedAStatus::ok();
}

ndk::ScopedAStatus BookLight::setBrightness(int32_t brightness) {
    if (brightness < 0 || brightness > kMaxBrightness) {
        return ndk::ScopedAStatus::fromExceptionCode(
            EX_ILLEGAL_ARGUMENT);
    }

    std::lock_guard<std::mutex> lock(mLock);
    mState.brightness = brightness;
    LOG(DEBUG) << "BookLight brightness set to " << brightness;

    // On a real device, write to hardware:
    // write_to_sysfs("/sys/class/leds/booklight/brightness", brightness);

    return ndk::ScopedAStatus::ok();
}

ndk::ScopedAStatus BookLight::setColorTemperature(int32_t kelvin) {
    if (kelvin < kMinTemperature || kelvin > kMaxTemperature) {
        return ndk::ScopedAStatus::fromExceptionCode(
            EX_ILLEGAL_ARGUMENT);
    }

    std::lock_guard<std::mutex> lock(mLock);
    mState.colorTemperature = kelvin;
    LOG(DEBUG) << "BookLight color temperature set to " << kelvin << "K";

    // On a real device, write to hardware:
    // write_to_sysfs("/sys/class/leds/booklight/color_temp", kelvin);

    return ndk::ScopedAStatus::ok();
}

ndk::ScopedAStatus BookLight::setEnabled(bool enabled) {
    std::lock_guard<std::mutex> lock(mLock);
    mState.enabled = enabled;
    LOG(DEBUG) << "BookLight " << (enabled ? "enabled" : "disabled");

    // On a real device:
    // write_to_sysfs("/sys/class/leds/booklight/enable", enabled ? 1 : 0);

    return ndk::ScopedAStatus::ok();
}

ndk::ScopedAStatus BookLight::getSupportedTemperatureRange(
        std::vector<int32_t>* _aidl_return) {
    _aidl_return->clear();
    _aidl_return->push_back(kMinTemperature);
    _aidl_return->push_back(kMaxTemperature);
    return ndk::ScopedAStatus::ok();
}

}  // namespace aidl::com::aospbook::hardware::light
```

**Service main (entry point):**

```cpp
// device/AospBook/bookphone/hal/booklight/default/service.cpp
#include "BookLight.h"

#include <android-base/logging.h>
#include <android/binder_manager.h>
#include <android/binder_process.h>

using aidl::com::aospbook::hardware::light::BookLight;

int main() {
    // Configure logging
    android::base::SetDefaultTag("booklight-hal");
    android::base::SetMinimumLogSeverity(android::base::DEBUG);

    LOG(INFO) << "BookLight HAL service starting";

    // Start the binder thread pool
    ABinderProcess_setThreadPoolMaxThreadCount(0);

    // Create the HAL instance
    std::shared_ptr<BookLight> bookLight =
        ndk::SharedRefBase::make<BookLight>();

    // Register with the service manager
    const std::string instance =
        std::string() + BookLight::descriptor + "/default";
    binder_status_t status = AServiceManager_addService(
        bookLight->asBinder().get(), instance.c_str());

    CHECK_EQ(status, STATUS_OK)
        << "Failed to register BookLight HAL service";

    LOG(INFO) << "BookLight HAL service registered: " << instance;

    // Join the binder thread pool (blocks forever)
    ABinderProcess_joinThreadPool();

    // Should never reach here
    LOG(FATAL) << "BookLight HAL service died unexpectedly";
    return EXIT_FAILURE;
}
```

**Android.bp for the default implementation:**

```json
// device/AospBook/bookphone/hal/booklight/default/Android.bp

cc_binary {
    name: "com.aospbook.hardware.light-service",
    relative_install_path: "hw",
    vendor: true,

    srcs: [
        "BookLight.cpp",
        "service.cpp",
    ],

    shared_libs: [
        "libbase",
        "libbinder_ndk",
        "liblog",
        "com.aospbook.hardware.light-V1-ndk",
    ],

    init_rc: ["booklight-default.rc"],
    vintf_fragments: ["booklight-default.xml"],
}
```

### 63.12.5 Init Service Configuration

**booklight-default.rc**:

```
# device/AospBook/bookphone/hal/booklight/default/booklight-default.rc
service vendor.booklight-default /vendor/bin/hw/com.aospbook.hardware.light-service
    class hal
    user system
    group system
    capabilities SYS_NICE
```

### 63.12.6 VINTF Manifest Fragment

The VINTF (Vendor Interface) manifest declares which HAL interfaces are
provided by this device:

**booklight-default.xml**:

```xml
<!-- device/AospBook/bookphone/hal/booklight/default/booklight-default.xml -->
<manifest version="1.0" type="device">
    <hal format="aidl">
        <name>com.aospbook.hardware.light</name>
        <version>1</version>
        <interface>
            <name>IBookLight</name>
            <instance>default</instance>
        </interface>
    </hal>
</manifest>
```

### 63.12.7 SELinux Policy for the HAL

```
# device/AospBook/bookphone/sepolicy/vendor/booklight.te

# Define the HAL domain
type hal_booklight_default, domain;
type hal_booklight_default_exec, exec_type, vendor_file_type, file_type;

# Allow init to start the HAL service
init_daemon_domain(hal_booklight_default)

# Allow the HAL to register with hwservicemanager
hal_server_domain(hal_booklight_default, hal_booklight)

# Allow the HAL to use binder
binder_use(hal_booklight_default)

# Allow system_server to find and call the HAL
binder_call(system_server, hal_booklight_default)
allow system_server hal_booklight_service:service_manager find;

# HwBinder access
hwbinder_use(hal_booklight_default)
```

Add file contexts:

```
# device/AospBook/bookphone/sepolicy/vendor/file_contexts
/vendor/bin/hw/com\.aospbook\.hardware\.light-service    u:object_r:hal_booklight_default_exec:s0
```

### 63.12.8 Including the HAL in the Build

```makefile
# In device.mk
PRODUCT_PACKAGES += \
    com.aospbook.hardware.light-service
```

### 63.12.9 Testing the HAL

```bash
# After booting, verify the HAL service is running:
adb shell ps -A | grep booklight
# Expected: vendor.booklight-default

# Check the VINTF manifest:
adb shell cat /vendor/etc/vintf/manifest.xml | grep booklight

# Test the HAL service using the AIDL test client or via a framework service
# that calls the HAL.

# Check service registration:
adb shell service list | grep booklight
```

### 63.12.10 Modifying Existing HALs

Instead of creating a new HAL from scratch, you may want to modify an existing
one. For example, to customize the sensors HAL for the emulator:

The existing sensors HAL is at:

```
device/generic/goldfish/hals/sensors/
    Android.bp
    entry.cpp               # HAL entry point
    multihal_sensors.cpp    # Multi-HAL sensors implementation
    multihal_sensors_epoll.cpp
    multihal_sensors_qemu.cpp
    sensor_list.cpp         # List of available sensors
    sensor_list.h
```

To add a custom sensor (e.g., a "reading posture" sensor):

```cpp
// Add to device/generic/goldfish/hals/sensors/sensor_list.cpp
// (or create a new file for your custom sensor)

namespace {

constexpr SensorInfo kCustomSensors[] = {
    {
        .sensorHandle = 100,
        .name = "AospBook Reading Posture Sensor",
        .vendor = "AospBook",
        .version = 1,
        .type = SensorType::ADDITIONAL_INFO,
        .typeAsString = "com.aospbook.sensor.reading_posture",
        .maxRange = 1.0f,
        .resolution = 0.1f,
        .power = 0.001f,  // mA
        .minDelay = 100000,  // microseconds (10 Hz)
        .maxDelay = 1000000,
        .fifoReservedEventCount = 0,
        .fifoMaxEventCount = 0,
        .requiredPermission = "",
        .flags = SensorFlagBits::ON_CHANGE_MODE,
    },
};

}  // namespace
```

### 63.12.11 HAL Testing with VTS

The Vendor Test Suite (VTS) validates that HAL implementations conform to
their interface contracts:

```bash
# Build VTS tests
m VtsHalBookLightTargetTest

# Run on the device
adb push out/target/product/bookdevice/data/nativetest64/VtsHalBookLightTargetTest \
    /data/local/tmp/
adb shell /data/local/tmp/VtsHalBookLightTargetTest
```

### 63.12.12 Complete HAL Architecture

```mermaid
graph TD
    subgraph "Framework (Java)"
        A["BookLightManager"] -->|Binder| B["BookLightService"]
    end

    subgraph "HAL Interface"
        C["IBookLight.aidl"]
    end

    subgraph "HAL Implementation (C++)"
        D["BookLight.cpp"] -->|Registered via| E["AServiceManager"]
    end

    subgraph "Kernel"
        F["/sys/class/leds/booklight/"]
        G["LED driver"]
    end

    subgraph "Build System"
        H["Android.bp (AIDL)"]
        I["Android.bp (impl)"]
        J["init.rc"]
        K["VINTF manifest"]
        L["SELinux policy"]
    end

    B -->|Binder IPC| C
    C --> D
    D -->|sysfs write| F
    F --> G

    H --> C
    I --> D
    J -->|starts| D
    K -->|declares| C
    L -->|allows| D

    style C fill:#fff3e0
    style D fill:#e1f5fe
```

---

## 63.13 Putting It All Together

### 63.13.1 Complete Build Walkthrough

Here is the complete sequence to build, test, and package AospBook ROM:

```bash
#!/bin/bash
# build_aospbook.sh -- Complete build script for AospBook ROM

set -euo pipefail

AOSP_ROOT=~/aosp
PRODUCT=bookphone
VARIANT=userdebug
RELEASE=trunk_staging

echo "=== Building AospBook ROM ==="
echo "Product: $PRODUCT"
echo "Variant: $VARIANT"
echo "Date: $(date)"
echo ""

# Step 1: Initialize environment
cd "$AOSP_ROOT"
source build/envsetup.sh

# Step 2: Select target
lunch "${PRODUCT}-${RELEASE}-${VARIANT}"

# Step 3: Clean (optional, for release builds)
# make clean

# Step 4: Build
echo "[BUILD] Starting full build..."
time m -j$(nproc) 2>&1 | tee build.log

# Step 5: Verify output
echo ""
echo "[VERIFY] Checking build output..."
OUT_DIR="$ANDROID_PRODUCT_OUT"

for img in boot.img vendor_boot.img super.img system.img vendor.img product.img; do
    if [ -f "$OUT_DIR/$img" ]; then
        size=$(du -sh "$OUT_DIR/$img" | cut -f1)
        echo "  OK: $img ($size)"
    else
        echo "  MISSING: $img"
    fi
done

# Step 6: Check for our custom content
echo ""
echo "[VERIFY] Checking custom content..."

if [ -d "$OUT_DIR/product/app/BookSampleApp" ]; then
    echo "  OK: BookSampleApp installed"
fi

if [ -d "$OUT_DIR/product/app/BookReader" ]; then
    echo "  OK: BookReader prebuilt installed"
fi

if [ -f "$OUT_DIR/product/media/bootanimation.zip" ]; then
    echo "  OK: Custom boot animation installed"
fi

if [ -d "$OUT_DIR/product/overlay/BookFrameworkOverlay" ]; then
    echo "  OK: Framework overlay installed"
fi

if [ -d "$OUT_DIR/product/overlay/BookSystemUIOverlay" ]; then
    echo "  OK: SystemUI overlay installed"
fi

echo ""
echo "[BUILD] Complete!"
echo "Output directory: $OUT_DIR"
echo ""
echo "To launch the emulator:"
echo "  emulator"
echo ""
echo "To generate OTA package:"
echo "  m dist"
```

### 63.13.2 Testing Checklist

After building, systematically verify each customization:

```bash
#!/bin/bash
# test_aospbook.sh -- Verify AospBook ROM on running emulator

echo "=== AospBook ROM Verification ==="
echo ""

# 1. Check build identity
echo "--- Build Identity ---"
adb shell getprop ro.build.display.id
adb shell getprop ro.product.brand
adb shell getprop ro.product.model
adb shell getprop ro.product.device
adb shell getprop ro.aospbook.version

# 2. Check custom properties
echo ""
echo "--- Custom Properties ---"
adb shell getprop ro.aospbook.features.dark_mode_default
adb shell getprop ro.aospbook.features.custom_qs

# 3. Check installed apps
echo ""
echo "--- Custom Apps ---"
adb shell pm list packages | grep aospbook
adb shell pm path com.aospbook.sample 2>/dev/null && echo "  BookSampleApp: OK" || echo "  BookSampleApp: MISSING"

# 4. Check overlays
echo ""
echo "--- RRO Overlays ---"
adb shell cmd overlay list | grep -A1 aospbook

# 5. Check custom service
echo ""
echo "--- Custom Service ---"
adb shell service list | grep aospbook && echo "  BookService: OK" || echo "  BookService: NOT FOUND"

# 6. Check boot animation
echo ""
echo "--- Boot Animation ---"
adb shell ls -la /product/media/bootanimation.zip 2>/dev/null && echo "  Custom boot animation: OK" || echo "  Custom boot animation: MISSING"

# 7. Check SELinux
echo ""
echo "--- SELinux ---"
adb shell getenforce

# 8. Check for SELinux denials related to our code
echo ""
echo "--- SELinux Denials (our code) ---"
adb logcat -d | grep "avc: denied" | grep -i "aospbook\|book" | tail -5
if [ $? -ne 0 ]; then
    echo "  No denials found (good!)"
fi

# 9. Check HAL (if implemented)
echo ""
echo "--- Custom HAL ---"
adb shell ps -A | grep booklight && echo "  BookLight HAL: RUNNING" || echo "  BookLight HAL: NOT RUNNING"

echo ""
echo "=== Verification Complete ==="
```

### 63.13.3 Release Build Pipeline

```mermaid
graph TD
    A["Source Code"] --> B["lunch bookphone-...-user"]
    B --> C["m dist"]
    C --> D["target_files.zip"]
    D --> E["sign_target_files_apks.py"]
    E --> F["signed_target_files.zip"]
    F --> G["ota_from_target_files.py"]
    F --> H["img_from_target_files.py"]
    G --> I["OTA update package"]
    H --> J["Flashable image package"]

    I --> K["SHA256 checksums"]
    J --> K
    K --> L["Distribution server"]

    style A fill:#e1f5fe
    style I fill:#e8f5e9
    style J fill:#e8f5e9
    style L fill:#fff3e0
```

### 63.13.4 Common Pitfalls and Solutions

| Pitfall | Symptom | Solution |
|---------|---------|----------|
| Forgot to add module to `PRODUCT_PACKAGES` | App/HAL not in image | Add to `device.mk` |
| Wrong signing key | App install fails | Match `certificate` to `sharedUserId` |
| Missing SELinux policy | Service crashes, `avc: denied` in logcat | Add `.te` rules, run `audit2allow` |
| Missing VINTF manifest | HAL not discovered by framework | Add `vintf_fragments` to `Android.bp` |
| Overlay targets wrong package | Resources not overridden | Check `android:targetPackage` in manifest |
| Overlay not static | User can disable overlay | Set `android:isStatic="true"` |
| Missing Soong namespace | Module not found during build | Add path to `PRODUCT_SOONG_NAMESPACES` |
| Circular dependency | Build error | Reorganize module dependencies |
| ccache miss after branch switch | Slow rebuild | Normal, ccache will repopulate |
| Test keys in release build | Security vulnerability | Generate and use release keys |

### 63.13.5 Maintaining Your ROM Across AOSP Updates

One of the biggest challenges of maintaining a custom ROM is keeping up with
upstream AOSP changes. Here are strategies:

1. **Minimize framework changes.** Use RROs and overlays wherever possible
   instead of modifying framework source. Overlays survive AOSP rebases
   cleanly.

2. **Keep device tree changes isolated.** All files under
   `device/AospBook/bookphone/` are yours and will never conflict with
   upstream.

3. **Use `repo` topic branches.** For framework changes, maintain a topic
   branch per feature:

    ```bash
    # Create a topic branch for your framework change
    cd frameworks/base
    repo start aospbook-dark-mode .
    # Make changes, commit
    git add -A && git commit -m "AospBook: default dark mode"
    ```

4. **Rebase regularly.** Sync to the latest AOSP and rebase your topic
   branches:

    ```bash
    repo sync -j$(nproc)
    repo rebase
    # Resolve any conflicts
    ```

5. **Document every framework change.** Keep a changelog that maps each
   framework modification to the business reason, so you know which changes
   to port when rebasing.

### 63.13.6 Final Directory Listing

Here is the complete directory tree for the AospBook ROM device configuration:

```
device/AospBook/bookphone/
|-- AndroidProducts.mk
|-- BoardConfig.mk
|-- bookphone.mk
|-- device.mk
|-- apps/
|   |-- BookSampleApp/
|   |   |-- Android.bp
|   |   |-- AndroidManifest.xml
|   |   |-- res/
|   |   |   |-- layout/activity_main.xml
|   |   |   |-- values/strings.xml
|   |   |   +-- mipmap-xxxhdpi/ic_launcher.png
|   |   +-- src/com/aospbook/sample/MainActivity.java
|   +-- prebuilt/BookReader/
|       |-- Android.bp
|       +-- BookReader.apk
|-- bootanimation/
|   |-- desc.txt
|   |-- bootanimation.zip
|   |-- part0/
|   |   |-- 00000.png ... 00029.png
|   +-- part1/
|       |-- 00000.png ... 00059.png
|-- hal/booklight/
|   |-- Android.bp
|   |-- aidl/com/aospbook/hardware/light/
|   |   |-- IBookLight.aidl
|   |   +-- BookLightState.aidl
|   +-- default/
|       |-- Android.bp
|       |-- BookLight.cpp
|       |-- BookLight.h
|       |-- service.cpp
|       |-- booklight-default.rc
|       +-- booklight-default.xml
|-- keys/
|   |-- releasekey.pk8
|   |-- releasekey.x509.pem
|   |-- platform.pk8
|   |-- platform.x509.pem
|   |-- shared.pk8
|   |-- shared.x509.pem
|   |-- media.pk8
|   +-- media.x509.pem
|-- overlay/
|   |-- BookFrameworkOverlay/
|   |   |-- Android.bp
|   |   |-- AndroidManifest.xml
|   |   +-- res/values/config.xml
|   +-- BookSystemUIOverlay/
|       |-- Android.bp
|       |-- AndroidManifest.xml
|       +-- res/values/
|           |-- config.xml
|           |-- dimens.xml
|           +-- colors.xml
|-- permissions/
|   +-- privapp-permissions-bookphone.xml
|-- sepolicy/vendor/
|   |-- booklight.te
|   |-- bookservice.te
|   |-- file_contexts
|   |-- service.te
|   +-- service_contexts
+-- services/BookService/
    |-- Android.bp
    |-- aidl/com/aospbook/service/IBookService.aidl
    +-- src/com/aospbook/service/
        |-- BookService.java
        |-- BookServiceManager.java
        +-- BookSystemService.java
```

---

## 63.14 Case Study: MaruOS as a Convergence Custom ROM

The thirteen sections above built up a generic "custom ROM" — a fork of AOSP
with tailored apps, framework tweaks, branded SystemUI, custom kernel, and a
release/distribution flow. To see how far this template can stretch in
practice, consider **MaruOS** (<https://github.com/maruos>), an open-source
custom ROM whose explicit goal is *"Your phone is your PC"* —
*"when you're on the go, Maru is your phone; when you're at your desk, Maru
is your desktop."* Plugging a supported Pixel or HTC 10 into a monitor over
USB-C/HDMI brings up a full Debian GNU/Linux desktop session on the external
display while the phone screen keeps running stock Android. Same kernel,
same device, two simultaneous user-facing operating systems.

![MaruOS: a single phone driving both a mobile Android UI and a Debian desktop on an attached monitor](https://maruos.com/assets/img/hero.598c5250.jpg)

MaruOS is not a typical custom ROM and is interesting precisely because of
how it departs from the template the rest of this chapter laid out. It is a
useful end-of-chapter exhibit: an unusual but production-realised demonstration
of how much *room* the AOSP overlay model actually leaves a custom-ROM author.

### 63.14.1 Why MaruOS Is an Unusual Custom ROM

A canonical custom ROM (LineageOS, GrapheneOS, /e/OS, ParanoidAndroid) keeps
the AOSP shape unchanged and varies *content*: different APKs, different
framework defaults, different SystemUI, different security posture, different
kernel hardening. The runtime model the user experiences is still
zygote → activities → SystemUI → home launcher.

MaruOS keeps that model intact for the phone surface but layers a *second*
runtime model on top: a Debian system running inside an LXC container that
the Android side starts on demand, with its own X11 desktop environment, its
own package manager, and its own boot/login flow. The README states this
explicitly:

> *"It uses lightweight OS virtualization (containers) to spin up virtual
> systems on demand"* — `maruos/maruos` README.

So in addition to the customizations a normal ROM ships (device repo,
vendor blobs, branded apps), MaruOS ships:

- An LXC container management daemon and supporting Android-side services.
- A "Perspective" layer that bridges Android's display, input, and audio
  pipelines to the container so the container can present a coherent
  desktop on the external screen.
- A build pipeline for the Debian container image, separate from the AOSP
  build.
- A device-attach hook that decides when to start the container and which
  display to put the desktop on.
- New SELinux policy to keep the container's Linux processes from
  trampling Android's domain model.

The device list is intentionally narrow — recent forks track a few Pixel
generations and the HTC 10, with device repos forked from LineageOS so the
hardware-enablement layer is borrowed rather than maintained from scratch.
See the manifest at `maruos/manifest` for the current set; supported devices
have changed across maru-0.x releases.

The license is Apache-2.0 across the org, matching AOSP itself.

### 63.14.2 The Two-Environment Model

The conceptual architecture is the single most important picture in this
case study. Both environments share the Linux kernel; everything above is
duplicated.

MaruOS two-environment runtime architecture.

```mermaid
flowchart TB
    subgraph Kernel["Single Linux kernel (Android-flavoured)"]
        K["Linux + Android kernel patches<br/>cgroups, namespaces, binder, ashmem, evdev"]
    end
    subgraph Android["Android user space (zygote + system_server)"]
        ZY["zygote"]
        SS["system_server"]
        UI["Phone SystemUI<br/>(internal display)"]
        BR["Maru bridge daemon<br/>(perspective/)"]
    end
    subgraph Container["LXC container (Debian rootfs)"]
        INIT["systemd / sysvinit"]
        X["X.org / Xfce desktop"]
        APPS["Debian apps<br/>apt-installed"]
    end
    subgraph IO["External I/O"]
        DISP["External display<br/>USB-C / HDMI"]
        KBD["BT / USB keyboard + mouse"]
    end

    K --> ZY
    K --> SS
    K --> INIT
    SS --> UI
    SS --> BR
    BR -.->|"start / stop"| INIT
    INIT --> X
    X --> APPS
    BR -.->|"display attach event"| DISP
    X --> DISP
    KBD --> K
    K -.->|"/dev/input/event* (evdev)"| SS
    K -.->|"/dev/input/event* (evdev)"| X
    BR -.->|"routes ownership via EVIOCGRAB"| K
```

Three architectural points worth pulling out:

1. **One kernel.** Both Android and Debian share `/proc/version`. The
   container runs by namespacing PIDs, mounts, network, IPC, and user IDs;
   it does not boot its own kernel image. This is the LXC bargain — much
   lower overhead than a VM, but no defence against a kernel exploit
   crossing the container boundary.
2. **The Maru bridge daemon is Android-resident.** It runs as a normal
   Android process (Java/JNI on top of native C/C++) inside the AOSP user
   space, listens for display-attach events, and uses ordinary Linux APIs
   to start the LXC container. It is *not* an in-container piece of code;
   the container only knows it's been booted.
3. **Two displays, two owners.** The phone screen continues to render
   Android's SystemUI on the internal display. The external display is
   *not* running another Android UI — it is a presentation surface that
   `SurfaceFlinger` hands off to the Linux side via mflinger (63.14.8),
   so what the user sees on the monitor is rendered entirely by X.org and
   the container's desktop environment (Xfce or whatever the Debian image
   is configured with). The user's phone keeps running stock Android the
   whole time the desktop is up.

This is qualitatively different from "desktop mode" features built into
stock Android (Samsung DeX, Android 12+'s windowing-on-external-display).
Those keep one Android runtime; MaruOS runs two operating systems on the
same kernel.

### 63.14.3 Kernel Configuration for LXC

LXC is the mechanism that lets MaruOS run a Debian rootfs alongside Android
without a second kernel, but it depends on Linux kernel features that stock
Android kernels routinely disable. A custom ROM building on LXC has to start
by making sure those features are present in the kernel image it ships.

Required kernel features for an unprivileged LXC container of the kind Maru
runs:

| Feature | Kernel config | Why MaruOS needs it |
|---------|--------------|---------------------|
| User namespaces | `CONFIG_USER_NS=y` | Maps the container's "root" UID to a high unprivileged UID on the host; the foundation of unprivileged LXC |
| PID namespaces | `CONFIG_PID_NS=y` | Lets the container's init see PID 1 inside, instead of the host's init |
| Mount namespaces | `CONFIG_NAMESPACES=y` (mount NS implied) | Per-container `/proc`, `/sys`, and root filesystem view |
| Network namespaces | `CONFIG_NET_NS=y` | Per-container network stack |
| UTS namespaces | `CONFIG_UTS_NS=y` | Per-container hostname |
| IPC namespaces | `CONFIG_IPC_NS=y` | Per-container System V IPC and POSIX message queues |
| Cgroups | `CONFIG_CGROUPS=y` with memory, cpu, devices, freezer subsystems | Resource accounting and limits inside the container |
| Seccomp | `CONFIG_SECCOMP_FILTER=y` | Lets LXC restrict the syscalls the container can make |
| uinput (optional) | `CONFIG_INPUT_UINPUT=y` | Synthetic-injection path used by the input bridge when an event has to be rescaled across displays (63.14.9); not needed for the common case where each device is routed directly to one side |
| Optional overlay FS | `CONFIG_OVERLAY_FS=y` | Layered container rootfs without full copies |

The catch is `CONFIG_USER_NS`. Android's kernel teams historically disable
this option on production kernels because user namespaces have been a
recurring source of CVEs across Linux releases — the privilege boundary
inside a user namespace has been harder to keep tight than the standard
root-vs-non-root split, and Android's security posture is to remove
attack surface where the platform itself does not need it. LineageOS device
kernels typically inherit that default. MaruOS, in order to run LXC at all,
must flip `CONFIG_USER_NS` back to `y` in its kernel build, knowingly
accepting the additional attack surface.

The other features in the table are usually already on in an Android kernel:
the Android Activity Manager uses cgroups (memory, freezer), the
low-memory killer uses cgroup v2 memory controllers, seccomp filters are
required by the Android sandbox, and namespaces are part of every modern
Linux kernel's default configuration. So the kernel customization Maru
needs is narrower than it first looks: enable `CONFIG_USER_NS`, confirm the
remaining namespace and cgroup controllers are on, optionally enable
`CONFIG_INPUT_UINPUT` if the synthetic-injection input path of 63.14.9 is
wanted, and rebuild.

This is why a Maru device build pulls a Maru-modified kernel from its
`device_*` repos rather than reusing LineageOS's kernel as-is. Section 63.11
covers the general kernel-customization workflow that MaruOS follows: a
defconfig fragment that toggles the required options, layered on top of the
device's base defconfig, and a rebuild of the boot image to flash alongside
the system image.

The trade-off is starkly stated. Enabling `CONFIG_USER_NS` opens an attack
surface that stock AOSP intentionally closes. For Maru this is an accepted
cost of the convergence model. For any custom ROM considering an LXC-based
or namespaces-based extension, the choice should be made deliberately, with
the threat model written down — there is no way to get unprivileged LXC
without this flag, and there is no way to flip this flag without expanding
the kernel attack surface.

### 63.14.4 Repository Topology

MaruOS code is spread across several repositories under the `maruos/` org.
Understanding the topology helps a reader navigate the source without
guessing.

MaruOS repository dependency graph at the `maru-0.7` line.

```mermaid
graph LR
    subgraph Org["github.com/maruos"]
        MANIFEST["manifest<br/>repo manifest (XML)"]
        MAIN["maruos<br/>root project + docs"]
        VENDOR["vendor_maruos<br/>hardware-agnostic overlay"]
        BLUE["blueprints<br/>Debian container builder"]
        DEV1["device_*<br/>per-device repos<br/>(LineageOS forks)"]
    end
    subgraph Upstream["Upstream sources"]
        AOSP["AOSP source<br/>(LineageOS-mirrored)"]
        LIN["LineageOS HAL<br/>+ device trees"]
        DEB["Debian apt<br/>(rootfs packages)"]
    end

    MANIFEST -->|"declares projects"| AOSP
    MANIFEST -->|"declares projects"| LIN
    MANIFEST -->|"includes"| VENDOR
    MANIFEST -->|"includes"| DEV1
    BLUE -->|"pulls packages"| DEB
    BLUE -->|"produces rootfs"| VENDOR
    VENDOR -->|"installs"| MAIN
```

Repos at a glance (each at the `maru-0.7` branch unless noted):

- **`maruos/manifest`** — the `repo` manifest. Branch `maru-0.7` declares
  every `<project>` a Maru tree contains. Bootstrap:
  `repo init -u https://github.com/maruos/manifest.git -b maru-0.7`.
- **`maruos/maruos`** — the project's root: README, docs, top-level scripts
  pointing users at the rest of the system. Apache-2.0.
- **`maruos/vendor_maruos`** — the hardware-agnostic overlay. This is
  where the Maru-specific Java/C++/Makefile work lives. ~50% C++, 25%
  Makefile, 15% shell, 10% C.
- **`maruos/blueprints`** — a separate, Shell-based build pipeline that
  produces the Debian rootfs the container will run. Plugin-driven with
  `blueprint/debian` as the canonical implementation.
- **`maruos/device_<vendor>_<device>`** — per-device repos forked from
  LineageOS. These supply the HAL implementations, sensor configs,
  vendor blobs, boot image configuration, and so on. Maru does not
  re-author these; it tracks Lineage's work.

The repo topology is itself a lesson. The "Maru-ness" lives in
`vendor_maruos` and `blueprints`. The "Android-ness" lives in upstream
AOSP/Lineage. The "device-ness" is delegated to forked LineageOS device
repos. Each layer can evolve at its own cadence.

### 63.14.5 The vendor_maruos Overlay Anatomy

The `vendor_maruos` tree is where MaruOS's design choices are most legible.
The top-level layout (visible on the `maru-0.7` branch of the GitHub repo):

```
vendor_maruos/
├── Android.bp
├── Android.mk
├── BoardConfigVendor.mk
├── LICENSE
├── README.md
├── container/                       -- Android-side LXC management
├── device-maru.mk                   -- Device-agnostic product definition
├── include/perspective/             -- Headers for the perspective layer
├── init.maru.rc                     -- Maru init service definitions
├── maru_build.mk                    -- Maru-specific build glue
├── mlogwrapper/                     -- Maru log wrapper utility
├── overlay/                         -- AOSP resource overlays
├── overrides/                       -- Build-time file overrides
├── perspective/                     -- The Android↔container bridge
├── prebuilts/                       -- Pre-built binaries
├── privapp-permissions-maru.xml     -- Privileged permission grants
├── scripts/                         -- Build/setup helper scripts
└── sepolicy/                        -- Maru SELinux policy
```

Each directory has a specific role in the convergence story. Walking them
in dependency order makes the overall design clearer than alphabetical:

**`perspective/`** is the conceptual centre. The name signals the
abstraction: the device has multiple "perspectives" (phone screen, desktop
screen, perhaps headphones-only) and Maru's job is to switch between them.
The C++ + Java mix in this directory is the daemon that watches for
display events, decides when the user's "desktop perspective" is active,
and orchestrates everything below.

**`container/`** holds the LXC integration: the lifecycle wrapper around
`lxc-start`, the rootfs mount logic, the cgroup setup, the bind mounts
that expose host resources to the container, and the tear-down path. It is
the layer that talks directly to LXC.

**`overlay/`** uses AOSP's standard overlay mechanism (see section 63.5)
to replace specific resources in the framework or apps. Typical targets
include the device's `config.xml` settings, locale defaults, branding
strings, and any pre-installed-app launch defaults.

**`overrides/`** sits next to `overlay/` and handles file-level overrides
that the overlay system cannot express. Where overlays patch resource
values inside an APK, `overrides/` replaces entire files or scripts.

**`sepolicy/`** is the SELinux policy delta needed to let the container
daemon talk to LXC, mount the rootfs, manipulate cgroups, forward input,
and grab a framebuffer — none of which stock AOSP policy permits, because
no stock AOSP component does any of those things.

**`prebuilts/`** carries pre-compiled artifacts that the AOSP build does
not produce on its own — typically the LXC toolchain binaries, helper
shell scripts that aren't built per device, and any third-party Debian
support pieces.

**`mlogwrapper/`** is a small utility for redirecting Maru daemon logs
into Android's logging infrastructure (`logd`/`logcat`) so a developer
debugging Maru can use the same tools they'd use for any Android service.

**`scripts/`** contains repo-level setup helpers — things invoked outside
the normal `m`/`make` flow, like fetching the Debian rootfs from the
blueprints build output and dropping it into a per-product path before
the system image is packaged.

### 63.14.6 The blueprints Container Builder

The Debian rootfs the container runs is not built by Soong. It is built by
a separate repository, `maruos/blueprints`, which is a self-contained
shell pipeline:

- `build.sh` — main build entry point. Reads a blueprint, invokes its
  per-blueprint hooks, produces an output tarball.
- `build-with-docker.sh` — wrapper that runs `build.sh` inside a Docker
  image, useful when the build host doesn't have `debootstrap` or other
  Debian tooling.
- `plugin.sh` — boilerplate any blueprint sources. It enforces that each
  blueprint provides two shell functions: `blueprint_build` and
  `blueprint_cleanup`.
- `blueprint/debian/` — the canonical blueprint. The README confirms:
  *"Image building logic is separated into standalone plugins called
  blueprints. The canonical implementation is `blueprint/debian`."*

The split is deliberate. AOSP's build system is excellent at producing
Android system images and signed boot images, but it has no idea what a
Debian rootfs is. Rather than teach Soong about `debootstrap`, Maru runs
two builds — one Soong/Make for the Android side, one Shell/`debootstrap`
for the Debian side — and a final assembly step folds the rootfs output
into the appropriate product directory.

What this means for the custom-ROM author: when your customization adds an
entirely foreign environment (a container, a VM, a different libc), the
right answer is often a *sibling* build system that exports a tarball,
not a Soong module that tries to model the foreign world.

### 63.14.7 The "Perspective" Bridge Layer

The `perspective/` and `include/perspective/` directories carry the
hardest-to-classify part of the design: the Android-resident daemon that
animates the entire convergence flow. From its structural position
(Android user space, C++/Java mix, `include/` next to source) and the role
the rest of the tree assumes it plays, it is responsible for at least the
following:

1. **Display-attach detection.** Listening for `DisplayManager`
   `onDisplayAdded` callbacks (or the equivalent at a lower level) and
   deciding when an attached display is "desktop class" — large enough
   and external enough — to warrant launching the desktop perspective.
2. **Container lifecycle.** Calling into `container/` to start the LXC
   container on first desktop attach and to stop it on the last desktop
   detach, plus quiescing it on screen-off if Maru policy says so.
3. **Input routing.** Forwarding keyboard, mouse, and possibly touch
   events from Android's input system into the container so the user
   driving an external keyboard sees the keystrokes land in Debian.
4. **Audio routing.** Negotiating audio output between the phone's
   speakers and any audio device the desktop monitor provides over HDMI.
5. **Permission and authentication.** Some way for the user to confirm
   that an attached display is allowed to host a desktop session — Maru
   is not going to expose a Debian session to anyone who plugs into the
   port.

The repository organisation suggests the perspective layer is the
"director" while `container/` is the "stagehand": one decides what
should happen, the other actually moves the LXC machinery. The split is
a useful pattern for any custom ROM author writing a long-running
Android service that drives non-Android user-space resources.

### 63.14.8 mflinger and mclient: The Graphics Bridge

When the X11 server inside the Debian container draws to its framebuffer,
those pixels live in the container's address space — a different mount
namespace, a different `/dev`, a different view of GPU memory. Android's
`SurfaceFlinger`, which owns presentation on the external display, knows
nothing about that buffer. Some piece of software has to bridge the two,
and the design Maru uses for this bridge is unusually elegant: it makes
the LXC namespace boundary effectively invisible to the GPU.

mflinger lives in its own repository at <https://github.com/maruos/mflinger>,
separate from `vendor_maruos`. The README is one line: *"Graphics buffer
bridge for Maru OS."* The codebase is C-dominant (~64% C, 21% C++) with
`src/`, `include/`, `lib/`, `tests/`, and `scripts/` directories — the
layout of a small Linux system service.

The name signals the analogy. Android's `SurfaceFlinger` is the consumer
that takes per-producer graphics buffers — from apps, the camera HAL, video
decoders, and so on — via the standard `ANativeWindow`/`BufferQueue`
producer protocol and composes them onto the display. mflinger plays the
*producer* role for the container's frames: it asks SurfaceFlinger for an
`ANativeWindow`-backed Surface, hands the underlying buffer to Linux for
direct rendering, and tells SurfaceFlinger when the buffer is ready to
present.

The mflinger architecture is split into two halves:

- **mflinger** (the daemon, Android-side) runs as an Android user-space
  service started by `init.maru.rc`. It creates an Android `Surface`
  attached to the external display and uses the standard `ANativeWindow`
  C API to dequeue `GraphicBuffer` slots. Each buffer is backed by a
  gralloc allocation — typically a **dma-buf** on modern AOSP devices —
  whose file descriptor mflinger can hand to a process in another
  namespace.
- **mclient** (the container-side client) ships inside the Debian rootfs.
  It receives the dma-buf file descriptor from mflinger over a Unix
  domain socket using `SCM_RIGHTS` ancillary data — the standard Linux
  mechanism for passing a kernel-managed fd between processes. This
  works across the LXC namespace boundary because the kernel
  reference-counts the underlying object, not the path. mclient then
  `mmap`s the dma-buf (or imports it via DRI3 as a pixmap) and exposes
  the resulting memory region to X.org as the root window's backing
  store.

The pivotal fact: **X.org renders directly into the same physical GPU
memory that SurfaceFlinger will present.** When the X server commits a
frame, mclient tells mflinger the buffer is ready; mflinger calls
`queueBuffer` on the `ANativeWindow`; SurfaceFlinger picks the buffer up,
includes it in its next composition pass on the external display, and the
user sees the desktop. There is no intermediate "container framebuffer"
that gets copied across the boundary — the fd *is* the boundary, and the
GPU memory is shared.

This is the same producer/consumer pattern Android uses internally for
every camera, codec, and OpenGL surface; mflinger generalises it by
handing the producer end to a process living in a different mount
namespace.

The graphics bridge per frame.

```mermaid
sequenceDiagram
    participant SF as SurfaceFlinger
    participant MF as mflinger (Android)
    participant MC as mclient (container)
    participant X as X.org server
    participant XA as Xfce app

    Note over MF,SF: setup: mflinger creates a Surface for the external display
    Note over MF,MC: setup: mclient connects over UDS for fd transfer

    loop per frame
        MF->>SF: dequeueBuffer via ANativeWindow
        SF-->>MF: GraphicBuffer slot + dma-buf fd
        MF->>MC: send fd over UDS (SCM_RIGHTS)
        MC->>MC: mmap fd / import as DRI3 pixmap
        MC->>X: expose as root-window backing store
        XA->>X: draw request
        X->>MC: render directly into shared buffer
        MC-->>MF: frame complete
        MF->>SF: queueBuffer
        SF->>SF: composite onto external display
    end
```

Two consequences of this design worth pulling out:

- **Zero-copy across the LXC boundary.** No pixel is ever transferred
  between Android and container address spaces. Only file descriptors and
  small protocol messages cross the bridge. The end-to-end cost is
  bounded by GPU rendering, not by RAM bandwidth or namespace-crossing
  overhead.
- **One composition per frame.** Because X.org draws directly into the
  buffer SurfaceFlinger will present, there is no separate "container
  framebuffer → host framebuffer" composition step. The same number of
  compositions happen as for any normal Android surface, which is why the
  design scales to a 1920×1080 external monitor without becoming the
  bottleneck on modest hardware.

The Android-side SELinux policy in `vendor_maruos/sepolicy/` (63.14.11) is
what permits mflinger to acquire `ANativeWindow` surfaces, talk to
SurfaceFlinger over binder, and pass file descriptors out over its UDS;
without those rules the daemon would be denied at process start. The
bind-mount that exposes the mclient↔mflinger socket across the container
boundary is set up by the container module in `vendor_maruos/container/`
(63.14.5) when LXC starts.

### 63.14.9 Input Mapping Between Linux and Android

The complement of the graphics bridge is the input bridge — but it is
much smaller than the graphics bridge, and for the same architectural
reason that the graphics bridge is small: Android and the LXC container
share the same kernel.

Keyboard, mouse, and touch hardware lives in the kernel's input subsystem
and is exposed through `/dev/input/event*` nodes. Because there is only
one kernel, there is only one set of these nodes — there is not a separate
"Linux input device" and "Android input device" pair per piece of
hardware. Android's `InputReader` (inside `system_server`, see chapter 22)
opens them through Android's `/dev/input/`. The container sees the same
nodes through its own `/dev/input/` namespace, which Maru bind-mounts from
the host at LXC startup. X.org inside the container reads them through
the evdev input driver — the same evdev path X.org would use on a stock
Debian desktop. There is no pixel copy because the GPU memory is shared,
and there is no event copy because the kernel device nodes are shared.

What the bridge actually does, then, is *route* — decide which side
"owns" each device. The mechanisms are all standard Linux:

1. **Device enumeration.** When a USB or Bluetooth keyboard, mouse, or
   touchscreen is attached, the kernel creates `/dev/input/eventN`. The
   `udev`-style hotplug events propagate to both Android's input layer
   and (via the bind-mount) to the container.
2. **Per-device ownership.** Maru's perspective daemon (63.14.7) decides
   which side owns each device based on the active "perspective":
   - The phone's internal touch panel always belongs to Android — those
     touches need to drive SystemUI and apps on the internal display,
     never the desktop.
   - Hardware buttons (power, volume) always belong to Android.
   - External USB/BT keyboards and mice typically belong to the desktop
     when one is up, and to Android otherwise.
   - An external touch monitor's input device belongs to the desktop
     while the desktop is up.
3. **Exclusivity via `EVIOCGRAB`.** When the owning side needs to be
   the *only* reader of a device, the relevant process issues
   `ioctl(fd, EVIOCGRAB, 1)` on the event node. Without that, evdev's
   read path is multicast — every open file descriptor on the same
   `/dev/input/eventN` receives every event — and Android and X.org
   would both dispatch the same keystroke. With `EVIOCGRAB`, the kernel
   delivers events only to the grabbing fd until the grab is released.
4. **Coordinate translation for cross-display touch.** Touch events use
   absolute coordinates scaled to the originating panel's resolution. A
   touch on Android's internal 1080×1920 panel is meaningless to an X
   server drawing on a 1920×1080 external monitor. The common case
   doesn't hit this — the internal panel is owned by Android, the
   external touch monitor is owned by the desktop. The uncommon case is
   "use the phone screen as a touchpad for the desktop," where the
   perspective daemon reads internal-panel events, rescales coordinates
   into the desktop's space, and synthesises new events on a virtual
   device. `CONFIG_INPUT_UINPUT` (63.14.3) is what enables this
   synthetic-injection path. The common path does not need it.

The whole pipeline is invisible to both ends. Android's `InputReader`
enumerates the devices it owns and dispatches normally; the container's
X server enumerates the devices it owns and dispatches normally; only the
perspective daemon in the middle knows which side currently owns what.

The contrast with the graphics bridge is the architectural lesson here:
when two user-space stacks share a kernel, anything the kernel already
abstracts (input events, network sockets, fds, character devices) can be
shared by routing instead of forwarding. Anything the kernel does *not*
abstract (the GPU memory backing a Surface) has to be bridged with
explicit fd-passing as in 63.14.8. Maru's input bridge stays small
because the kernel does the work; the graphics bridge stays small
because the bridge piggy-backs on the kernel's existing dma-buf
fd-passing instead of inventing its own pixel transport.

### 63.14.10 Init and Boot Integration

`init.maru.rc` is where the boot integration is declared. Android's init
processes `*.rc` files from `/system/etc/init/` and `/vendor/etc/init/`
at boot, defining services and triggers. For MaruOS the file
conceptually contains:

- A `service` entry for the perspective daemon, with the right `user`,
  `group`, and `seclabel` so that SELinux can place it in the Maru
  domain and so that init can supervise restarts.
- One or more `on` triggers — `on boot`, `on property:sys.boot_completed=1`,
  perhaps `on property:maru.container.requested=1` — that decide when the
  daemon starts and what auxiliary setup runs first.
- A `socket` or `oneshot` definition for any helper command the perspective
  daemon may invoke from outside its own process.

The boot/launch flow looks like this:

MaruOS desktop launch from cold boot to first X11 window.

```mermaid
sequenceDiagram
    participant Init as Android init (PID 1)
    participant Persp as Maru perspective daemon
    participant Disp as DisplayManagerService
    participant Cont as Maru container module
    participant LXC as lxc-start
    participant Deb as Debian systemd

    Init->>Persp: start service (on boot)
    Persp->>Disp: register DisplayListener
    Note over Persp,Disp: phone runs Android normally
    Disp->>Persp: onDisplayAdded (external)
    Persp->>Persp: classify as "desktop"
    Persp->>Cont: requestContainerStart
    Cont->>LXC: lxc-start -n maru
    LXC->>Deb: PID 1 inside container
    Deb->>Deb: bring up X.org + Xfce
    Persp->>Disp: route external display to container surface
    Persp->>Persp: route input events into container
    Note over Deb: user sees desktop on external display
```

What this diagram makes explicit is that the *user-visible event* —
plugging in a monitor — drives the whole chain. There is no scheduled
container; LXC starts on demand and shuts down when the perspective layer
decides it should. This is what the README means by *"spin up virtual
systems on demand."*

### 63.14.11 SELinux Implications

Stock AOSP SELinux policy is designed around the assumption that no
Android process needs to launch an LXC container, mount a rootfs, or
manipulate cgroups outside the ones Android's lmkd/freezer already own.
Maru's `sepolicy/` directory carries the delta:

- A new domain — call it `maru_perspective` and `maru_container` — for
  the daemon and any helper processes.
- Rules permitting that domain to `execute` the LXC toolchain, `mount`
  the container rootfs at a Maru-specific path, and write to the
  cgroups the container uses.
- Rules permitting the daemon to bind to the framebuffer (or surfaceflinger
  equivalent) on the external display, since X11 inside the container
  needs to draw somewhere visible.
- Rules permitting input pipes to cross from Android's input domain into
  the perspective domain so input forwarding works.

What an aspiring ROM author should take from this: any custom ROM that
adds new system services with elevated capabilities has to author new
SELinux policy, full stop. The cost is not in writing the `*.te` files
themselves (Maru's `sepolicy/` is small) but in *bisecting denials*
during development. Each new denial gets logged once on first hit,
silently after that, which is why fresh installs of a Maru build
on a different device often need an audit pass.

### 63.14.12 Privileged Permissions for Maru-System Apps

`privapp-permissions-maru.xml` lives at vendor-overlay scope and is
processed by Android's privileged-permission allowlist mechanism (see
section 63.4 on adding custom apps). Maru needs this file because its
perspective-daemon companion APK — the user-facing UI that confirms
desktop access, manages container settings, and surfaces the
"desktop is active" notification — sits at `/system/priv-app/` and
declares permissions that the allowlist must explicitly grant.

The shape is a familiar one for ROM authors:

```xml
<permissions>
    <privapp-permissions package="com.maruos.perspective">
        <permission name="android.permission.SYSTEM_ALERT_WINDOW"/>
        <permission name="android.permission.MANAGE_DEVICE_ADMINS"/>
        <permission name="android.permission.WRITE_SECURE_SETTINGS"/>
        <!-- ...etc... -->
    </privapp-permissions>
</permissions>
```

The exact entries are Maru's own decision; the file structure is mandated
by AOSP. Any custom ROM with a privileged system app must ship one of
these files, and a `dexopt`-time denial from `PackageManagerService`
during boot is almost always traceable to a missing entry here.

### 63.14.13 The Build Flow

Putting the pieces together, building MaruOS from source for a supported
device looks like this:

```bash
# 1. Set up the AOSP-style tree using Maru's manifest
mkdir maru && cd maru
repo init -u https://github.com/maruos/manifest.git -b maru-0.7
repo sync -j$(nproc)

# 2. Build the Debian rootfs separately (sibling build system)
cd vendor/maruos/blueprints   # (path depends on manifest layout)
./build.sh blueprint/debian
# Produces a rootfs tarball — Maru's scripts move it into the right
# product directory so it gets packaged into the system image.

# 3. Standard AOSP build flow for the chosen device
cd $TOP
source build/envsetup.sh
lunch maru_<device>-userdebug
m
```

Three things stand out compared to the build flow in section 63.8:

- **Two build systems.** The Soong/Make pipeline does not run the
  blueprints pipeline. The custom-ROM author orchestrates them by hand
  or via a wrapper script.
- **The container image is a build artefact, not source.** The Debian
  rootfs is produced once per release, signed, and shipped inside the
  Maru system image. Devices do not run `debootstrap` at install time.
- **The `lunch` combo embeds Maru.** A `maru_<device>` combo means the
  product makefile inherits `device-maru.mk` (and via it `maru_build.mk`),
  which is what pulls in `vendor_maruos` and turns on the Maru-specific
  build flags. A standard `lineage_<device>` lunch would build the same
  device without the Maru layer.

### 63.14.14 What MaruOS Teaches the Custom ROM Author

Reading MaruOS as an exemplar rather than a one-off, three lessons
generalise beyond this specific project:

1. **The overlay model is very flexible.** Sections 63.3–63.5 talked
   about overlays as a way to change resource values and ship a few
   APKs. MaruOS shows the *upper bound*: you can add an entire second
   operating system through vendor overlay + sepolicy + init.rc + a
   sibling build system, without forking the AOSP source tree itself.
   If your customization can be expressed as files that land in
   `/system/`, `/vendor/`, `/product/`, or `/system_ext/` plus init
   rules plus SELinux policy, you do not need to patch AOSP.
2. **Delegate hardware enablement.** Maru forks LineageOS device trees
   rather than maintaining its own per-device HAL forks. The result is
   that a Maru maintainer can focus on the convergence layer, and
   benefit from LineageOS's quarterly device cadence. Any custom ROM
   that picks a fight with hardware enablement is signing up for a
   never-ending workload; let upstream do it.
3. **Separate the foreign world from Soong.** The Debian container's
   build pipeline is shell-based and lives in a separate repo. Soong
   never has to know what `debootstrap` is. The two systems meet at a
   single tarball artefact. Any time your custom ROM needs to ship
   something that is *not* an Android system image — a container
   rootfs, a separately-licensed firmware blob, a Buildroot image for a
   companion microcontroller — model that artefact as a sibling build
   that hands off a file.

### 63.14.15 Limitations and Trade-Offs

MaruOS is also a useful case study in what this approach *costs*. An
honest read of the trade-offs:

- **Device support is narrow.** Maintaining the convergence layer across
  many devices means tracking each LineageOS device branch, validating
  the LXC kernel feature set on each, and re-testing display routing.
  Real Maru releases ship for a handful of devices at a time, which is
  about right for a small team but well short of any "works on every
  Android phone" promise.
- **Shared kernel, shared exposure.** LXC is much cheaper than a VM but
  shares the kernel. A kernel exploit reachable from inside the Debian
  container reaches the Android user space and the bootloader. Maru
  cannot easily compete with virtualized desktop offerings on isolation.
- **No isolation from Android's filesystem.** By default, an LXC
  container can be configured to expose much of the host's filesystem.
  Maru's container/perspective bridge has to decide carefully which
  host paths it bind-mounts and which it withholds; getting that wrong
  exposes Android user data to Debian apps.
- **Maintenance debt.** Two build systems, two userspace stacks, and a
  custom bridge layer is a lot to keep running across an AOSP version
  bump. Each yearly Android letter release ships behavioural changes in
  `DisplayManager`, input dispatching, and SELinux that the perspective
  daemon has to adapt to.
- **Upstream uncertainty.** Maru's design predates the Android Computer
  Control framework (section 50.3) and the formalisation of desktop-
  mode in stock Android. Convergent UIs are now closer to a first-class
  upstream concern, which could either obsolete Maru's approach or
  raise the floor under it. The case study above is best read as a
  *snapshot* of where one production custom ROM landed under the AOSP
  primitives available to it through Android 12-era releases.

The lesson here is symmetrical to the one in 63.14.14: the same overlay-
mechanism flexibility that lets a single small team ship a phone-to-desktop
convergence ROM also distributes the cost. Every layer of additional
ambition adds a layer of maintenance. Custom ROM authors weighing how far
to push the model should plan a realistic device list and a realistic
release cadence first.

---

## 63.15 Further Reading

| Topic | Source Location | Description |
|-------|----------------|-------------|
| Build system | `build/make/core/` | GNU Make build rules |
| Soong build | `build/soong/` | Blueprint/Soong build system |
| Product configuration | `build/make/target/product/` | Base product makefiles |
| Goldfish device | `device/generic/goldfish/` | Emulator device tree |
| Framework config | `frameworks/base/core/res/res/values/config.xml` | Overridable framework values |
| SystemUI | `frameworks/base/packages/SystemUI/` | System UI source |
| Boot animation | `frameworks/base/cmds/bootanimation/` | Boot animation player |
| HAL interfaces | `hardware/interfaces/` | AIDL HAL definitions |
| Release tools | `build/make/tools/releasetools/` | Signing and OTA tools |
| Security keys | `build/make/target/product/security/` | Default signing keys |
| SELinux policy | `system/sepolicy/` | Base SELinux policies |
| Init system | `system/core/init/` | Init process source |
| SystemServer | `frameworks/base/services/java/com/android/server/SystemServer.java` | Service startup |

---

## 63.16 Summary

This chapter walked through the entire process of building a custom Android
ROM from the ground up:

| Section | Topic | Key Outcome |
|---------|-------|-------------|
| 34.1 | Planning | Defined AospBook ROM scope and architecture |
| 34.2 | Environment Setup | Complete build host configuration |
| 34.3 | Device Configuration | `AndroidProducts.mk`, `device.mk`, `BoardConfig.mk` |
| 34.4 | Custom Apps | Prebuilt APKs and source-built apps in the image |
| 34.5 | Framework Behavior | RROs, source mods, custom system service |
| 34.6 | Boot Animation | `bootanimation.zip` creation and installation |
| 34.7 | SystemUI | Status bar, quick settings, theme overlays |
| 34.8 | Building & Flashing | `m`, emulator launch, `fastboot flash` |
| 34.9 | Debugging | logcat, dumpsys, Perfetto, Winscope, SELinux |
| 34.10 | Distribution | Key generation, signing, OTA packages |
| 34.11 | Kernel | Custom kernel builds, kernel modules |
| 34.12 | HAL | Custom AIDL HAL definition and implementation |

**Key takeaways:**

1. **Start with overlays before modifying source.** RROs and product
   configuration give you enormous customization power without touching
   framework code, making your ROM easier to maintain across AOSP updates.

2. **The device tree is your domain.** Everything under
   `device/AospBook/bookphone/` is isolated from AOSP and survives `repo
   sync` cleanly.

3. **SELinux is not optional.** Every custom service, HAL, and daemon needs
   SELinux policy. Use `audit2allow` to generate initial policies from
   denials, then refine them to be as restrictive as possible.

4. **Never ship with test keys.** Generate unique signing keys before
   distributing your ROM to anyone.

5. **The emulator is your best friend.** You can develop and test 95% of ROM
   customizations on the emulator before ever touching real hardware.

The techniques in this chapter form the foundation used by every major custom
ROM project. Whether you are building a privacy-focused ROM, an enterprise
management solution, or simply learning how Android works from the inside out,
the ability to build, customize, sign, and distribute a complete Android
system image is the ultimate expression of AOSP mastery.


<!-- chapter:64-windows-games -->
# Chapter 64: Running Windows Games on Android

A modern Android phone carries an ARM64 GPU powerful enough to run desktop
PC games, yet the games themselves are x86-64 Windows binaries that expect the
Win32 API, a glibc-flavoured Linux kernel ABI underneath Wine, and a desktop
graphics driver. None of that exists on a stock, unrooted Android device.
Projects like **GameNative**, and the **Winlator** runtime it builds on, bridge
that gap entirely in userspace: no root, no kernel patches, no custom ROM. They
stack a chain of translation layers, each solving one slice of the
impedance mismatch, on top of the same AOSP internals the rest of this book has
dissected.

This chapter takes GameNative as a worked example and walks the whole stack from
the top down: the Android app, the glibc root filesystem it ships inside an APK,
the `bionic`/glibc boundary and the redirections that cross it, the x86-64 to
AArch64 translators (**FEX** and **Box64**), **Wine** as the Windows API layer,
the Direct3D to Vulkan graphics chain that reaches the real Adreno GPU, and the
audio path that ends at **AAudio**. Every layer is a self-contained piece of
technology, so each gets its own architecture, its own rationale, and its own
map of where it plugs into the Android internals covered earlier.

A note on source references. The Android touchpoints are cited against the AOSP
tree with file path and line number, exactly as elsewhere in this book. The
translation-stack projects (GameNative, Winlator, Wine, FEX, Box64) are external
repositories that move quickly, so they are cited by repository-relative file
path only, without line numbers, which would be stale before the ink dried.

---

## 64.1 The Problem and the Layer Cake

### 64.1.1 Two Orthogonal Translations

Running a Windows game on an ARM phone is not one problem; it is two unrelated
problems that are easy to confuse:

1. **Instruction-set translation.** The game is a stream of x86-64 machine
   instructions. An ARM64 CPU cannot execute them. Something must translate
   x86-64 to AArch64, either ahead of time or just-in-time. This is the job of
   **FEX** or **Box64**, and it is *pure CPU emulation*: it knows nothing about
   windows, files, or sockets, only about opcodes, registers, and flags.

2. **API and ABI translation.** The game calls the Windows API: `CreateFileW`,
   `NtUserCreateWindowEx`, `D3D11CreateDevice`. Those functions do not exist on
   Linux. Something must implement the Windows API on top of the POSIX/Linux
   kernel. This is the job of **Wine**, and it is *not* an emulator: it contains
   no instruction translation at all, only reimplementations of Windows
   behaviour in native code.

Keeping these two jobs separate is the single most important architectural idea
in the whole stack. The performance of the entire system depends on emulating as
little as possible, ideally only the game's own code, while letting Wine, the
graphics driver, and the audio server run as native ARM64. We will return to
this theme repeatedly, because the newest designs (ARM64EC, covered in 64.5.8)
exist precisely to shrink the "emulated" box down to just the game.

### 64.1.2 The Full Stack at a Glance

The layers, from the Windows game at the top to the Android kernel at the
bottom, look like this.

#### Diagram: the Windows-game translation stack on Android

```mermaid
graph TD
    GAME["Windows game<br/>x86-64 PE binary"]
    subgraph Guest["Guest world: rootfs in app storage"]
        DXVK["DXVK / VKD3D-Proton<br/>(Direct3D to Vulkan)"]
        WINE["Wine / Proton<br/>(Win32 + NT API)"]
        EMU["FEX / Box64<br/>(x86-64 to AArch64 JIT)"]
    end
    subgraph App["GameNative app process (Android bionic)"]
        XSERVER["In-app X server<br/>+ Vortek renderer"]
        PULSE["PulseAudio server"]
        STORE["Steam / Epic / GOG client<br/>(Pluvia lineage)"]
    end
    subgraph AOSP["Android platform"]
        VKLOADER["Vulkan loader<br/>libvulkan"]
        AAUDIO["AAudio / AudioTrack"]
        SURFACE["ANativeWindow / SurfaceFlinger"]
        DRIVER["Adreno Vulkan driver"]
    end

    GAME --> WINE
    GAME -.->|"D3D calls"| DXVK
    DXVK -->|"Vulkan"| XSERVER
    WINE --> EMU
    WINE -.->|"WASAPI audio"| PULSE
    XSERVER --> VKLOADER
    VKLOADER --> DRIVER
    XSERVER --> SURFACE
    PULSE --> AAUDIO
    STORE -->|"installs game"| GAME
```

Read it as three bands. The **guest** band is a Linux x86-64 world running
inside a normal Android app's private storage. The **app** band is native ARM64
Android code: the in-app X server that receives the game's frames, the
PulseAudio server that receives its audio, and the storefront client that
downloaded the game. The **platform** band is plain AOSP: the Vulkan loader and
`ANativeWindow` from Chapter 13, AAudio from Chapter 15, and the SurfaceFlinger
compositor from Chapter 24.

Crucially, the dotted Direct3D and audio arrows *leave* the emulator early. The
game's D3D calls are handed to DXVK, which (in the fast configurations) runs as
native ARM64 code and emits Vulkan, so the heavy graphics translation is not
itself emulated. The same is true of audio. Only the solid arrow from the game
into Wine, and from Wine into the emulator, represents x86-64 code that the JIT
must actually translate.

### 64.1.3 No Root, No Kernel Changes

Everything in the guest band runs with the privileges of an ordinary
installed app. There is no `su`, no `insmod`, no SELinux policy change, no
modification to the system image. That constraint is what makes these apps
installable from a store on a locked bootloader, and it is also what forces most
of the engineering cleverness in this chapter. A desktop Wine setup can `chroot`
into a rootfs, mount filesystems, and `dlopen` the system's glibc GPU driver
directly. An Android app can do none of those things. Each missing capability is
replaced by a userspace stand-in:

| Desktop capability | Forbidden on unrooted Android | Userspace replacement |
|--------------------|-------------------------------|-----------------------|
| `chroot` into a rootfs | needs `CAP_SYS_ADMIN` | **PRoot** (ptrace path rewriting) |
| Mount the rootfs image | needs root | extract into app-private storage |
| System V shared memory | restricted by the kernel | ashmem/`memfd`-backed shim |
| `dlopen` the glibc GPU driver | driver is a `bionic` library | IPC to a native renderer, or thunks |
| Run a system PulseAudio | no system daemon access | bundle a PulseAudio server in the app |

### 64.1.4 The Unrooted-App Constraints in AOSP Terms

Three AOSP mechanisms shape what the stack can and cannot do, and all three were
introduced in earlier chapters.

**Linker namespaces (Chapter 7).** An app's native libraries are loaded in an
isolated linker namespace so they cannot see arbitrary system libraries. The
public `android_dlopen_ext` flags that govern this live in
`bionic/libc/include/android/dlext.h`; `ANDROID_DLEXT_USE_NAMESPACE`
(`bionic/libc/include/android/dlext.h:115`) lets a caller pick the namespace a
library loads into, and `ANDROID_DLEXT_USE_LIBRARY_FD`
(`bionic/libc/include/android/dlext.h:80`) lets it load a library straight from
a file descriptor, for example a `.so` stored uncompressed inside the APK. The
Vulkan loader itself uses the namespace flag when it opens the device driver, as
we will see in 64.7.4.

**W^X enforcement (Chapter 7).** A JIT must write machine code and then execute
it. Since API 26 the dynamic linker refuses to load any ELF segment that is
simultaneously writable and executable; `bionic/linker/linker_phdr.cpp:1058`
emits the `"has load segments that are both writable and executable"` diagnostic
and `bionic/linker/linker_phdr.cpp:1062` records the `W+E` warning. A translator
like FEX or Box64 therefore cannot keep a page mapped `PROT_WRITE | PROT_EXEC`;
it must map JIT pages writable, fill them, then flip them to executable with
`mprotect`, respecting the write-xor-execute rule the platform enforces on app
processes.

**App-data execution limits.** On recent Android, executing binaries from an
app's writable data directory is increasingly restricted. The translation stack
must run the guest's executables through a loader it controls (PRoot, or a
redirection library) rather than handing the kernel a path under the app's data
dir and calling `execve` directly. This is one of the jobs of GameNative's
proprietary `libredirect.so`, discussed in 64.4.4.

---

## 64.2 GameNative: the Integrated Application

GameNative is an Android app that runs Windows PC games locally, with built-in
storefront integration for Steam, Epic Games Store, GOG, and Amazon Games. It is
the most complete public example of the full stack, so it anchors this chapter.
It is licensed GPL-3.0, with the package id `app.gamenative`.

### 64.2.1 Lineage: a Pluvia and Winlator Graft

GameNative is best understood as a graft of two upstream codebases rather than a
single fork:

1. **The application and Steam-client layer comes from Pluvia**, a lightweight
   unofficial Steam client for Android. Its fingerprints are in the source: the
   `Application` subclass is `PluviaApp.kt`, the Room database is
   `PluviaDatabase.kt`, and Steam connectivity uses the **JavaSteam** library.
   Pluvia provides account login, the library view, and the SteamPipe depot
   downloader.

2. **The runtime and compatibility layer comes from Winlator.** The entire
   `com.winlator.*` Java tree is vendored under
   `app/src/main/java/com/winlator/`, with the subpackages `container`, `core`,
   `xserver`, `xenvironment`, `winhandler`, `box86_64`, `fexcore`,
   `inputcontrols`, and `renderer`. The native side under
   `app/src/main/cpp/winlator/` is Winlator's too.

So in code-provenance terms GameNative is **Pluvia (the storefront app) plus
Winlator (the Wine and emulation runtime)**, unified under GameNative's GPL-3.0
Kotlin layer. Popular write-ups that call it simply "a fork of Winlator" are
collapsing this two-source structure; the accurate statement is the one above,
and the rest of the chapter relies on the Winlator half, which is the part that
actually runs the game.

### 64.2.2 The App Architecture

The Android-facing half is Kotlin with Jetpack Compose UI and Dagger Hilt
dependency injection. Three pieces matter for our purposes:

- **`SteamService`** (a foreground `Service`) owns the Steam session;
  per-store services sit alongside it for Epic, GOG, and Amazon.
- **`XServerScreen`** is the full-screen Compose surface a game renders into,
  driven by `XServerViewModel`. This is where the in-app X server, the audio
  server, and the graphics renderer are brought up.
- **The vendored Winlator runtime** does the actual container, rootfs, Wine,
  and emulator work, orchestrated from the `com.winlator.xenvironment` package.

### 64.2.3 The Container Model

A **container** is one game's isolated Windows environment: a Wine prefix plus
its configuration (graphics driver, emulator, audio driver, DLL overrides,
environment variables). The classes `com.winlator.container.Container` and
`ContainerManager` define and manage them, and the defaults are the clearest
single statement of what "the GameNative stack" actually is. From
`app/src/main/java/com/winlator/container/Container.java`:

```java
// GameNative: app/src/main/java/com/winlator/container/Container.java
public static final String DEFAULT_EMULATOR        = "FEXCore";
public static final String DEFAULT_AUDIO_DRIVER    = "pulseaudio";
public static final String DEFAULT_DXWRAPPER       = "dxvk";
// graphics driver default resolves to "vortek"
```

The pinned component versions live alongside, in
`app/src/main/java/com/winlator/core/DefaultVersion.java`: Box64, Box86, the
FEXCore build number, Turnip (the Mesa Adreno Vulkan driver), DXVK, VKD3D, and
the rest. The default Wine is recorded in `WineInfo.java`. Reading these two
files tells you the entire default pipeline at a glance, which is why a "Try It"
exercise at the end of the chapter is simply to read them.

### 64.2.4 The Default Stack

Putting the container defaults together, a freshly created GameNative container
runs:

- **Wine / Proton** in an **ARM64EC** configuration as the Windows API layer
  (64.6), with **FEXCore** translating the game's x86-64 code and a WoW64
  helper translating any 32-bit code (64.5.8).
- **DXVK** translating Direct3D 9/10/11 to Vulkan, with **VKD3D-Proton** for
  Direct3D 12 (64.7.2).
- **Vortek** as the Vulkan path that reaches the device's Adreno driver (64.7.3),
  with **Turnip** (Mesa) available as an alternative.
- **PulseAudio** as the audio server (64.8).

Box64 with a classic glibc launch path is also bundled as the alternative
route for Wine builds that are not ARM64EC; that path is selected by a different
launcher component (64.5.6).

### 64.2.5 Packaging: How the Pieces Reach the Device

GameNative ships a remarkable amount of prebuilt native software inside one app,
through three distinct delivery mechanisms.

1. **Android-process native libraries** ship in `jniLibs/arm64-v8a/` and are
   unpacked by the platform's package manager into the app's
   `nativeLibraryDir`. These are the libraries that load into the *Android*
   (bionic) process: the PulseAudio server libraries (`libpulse.so` and
   friends), the native graphics renderers (`libvortekrenderer.so`,
   `libvirglrenderer.so`) and the in-app X server (`libwinlator.so`), and the
   proprietary `libsteambootstrap.so`.

2. **Guest components** ship as compressed tar archives in `assets/` (Zstandard
   `.tzst` and xz `.txz`) and are extracted into the rootfs at runtime by
   `com.winlator.core.TarCompressorUtils`. Wine, FEX, Box64, DXVK, VKD3D, the
   Vulkan drivers, and the Windows DLL components all arrive this way. After
   extraction their ELF interpreters and RPATHs are patched with a vendored
   `patchelf`.

3. **Large or optional payloads** are downloaded on demand. The Ubuntu rootfs is
   delivered as a separate Android **dynamic feature module** (`ubuntufs/`,
   `dist:on-demand`), and the graphics drivers, extra DXVK builds, and Proton
   container patterns are fetched from GameNative's download server per the
   `assets/*_download.json` manifests. This keeps the base APK installable while
   the multi-gigabyte Linux userland arrives only when a game is first run.

### 64.2.6 End-to-End Launch Sequence

#### Diagram: launching a game in GameNative

```mermaid
sequenceDiagram
    participant U as User
    participant SS as SteamService
    participant CM as ContainerManager
    participant IFS as ImageFsInstaller
    participant XE as XEnvironment
    participant PL as ProgramLauncher
    participant W as Wine + FEX
    participant GPU as Vortek + Adreno

    U->>SS: Pick game, Play
    SS->>SS: Authenticate, download depot
    SS->>CM: Open or create container
    CM->>IFS: Ensure rootfs (imagefs) installed
    IFS-->>CM: Wine + components extracted
    CM->>XE: Bring up environment components
    XE->>XE: Start X server, PulseAudio, Vortek
    XE->>PL: Launch guest program
    PL->>W: PRoot or bionic exec into Wine
    W->>W: Load game PE, start emulating x86-64
    W->>GPU: D3D to Vulkan frames
    GPU-->>U: Composited to the app Surface
```

The `XEnvironment` object holds an ordered list of **components**, each a small
class in `com.winlator.xenvironment.components` that starts one subsystem: the X
server, `PulseAudioComponent`, the graphics renderer (`VortekRendererComponent`
or a VirGL renderer), a System V shared-memory component, and finally a
program-launcher component that spawns Wine under the emulator. The launcher is
either `BionicProgramLauncherComponent` (the default ARM64EC/FEX path) or
`GuestProgramLauncherComponent` (the classic glibc/Box64 path).

### 64.2.7 Licensing and the GPL Aggregation Question

GameNative is GPL-3.0, as is the vendored Winlator code. Most of the bundled
runtime carries its own upstream, mostly permissive or LGPL licences: Wine and
PulseAudio are LGPL-2.1, Mesa (Turnip, Zink) is largely MIT, DXVK is
zlib-licensed, and Box64 and FEX are MIT/BSD-style. The project's
`THIRD_PARTY_NOTICES` file makes a blanket written offer of source for the
copyleft components.

Two components are deliberately closed-source, and they are the legally
interesting part:

- **`libredirect.so`** (shipped in `assets/redirect.tzst`) is loaded only into
  the Wine/Proton subprocesses through `LD_PRELOAD`, never into the Android
  app's own address space. It rewrites a legacy package identifier and adapts
  process launches to recent-Android exec-from-data restrictions.
- **`libsteambootstrap.so`** is a JNI shim that drives a real in-process Steam
  client for achievements, cloud saves, and the overlay.

The maintainer's stated position is that these run as separate
programs/subprocesses communicating only through OS interfaces, and so are mere
aggregation under GPL-3.0 section 5 rather than derivative works of the GPL app.
That is the project's argument, not an adjudicated fact; whether shipping closed
`LD_PRELOAD` and JNI shims alongside a GPL-3.0 app withstands scrutiny is a
genuine, unsettled GPL question. The app builds and runs without either library,
with reduced compatibility, which is part of the maintainer's separability
argument.

---

## 64.3 The rootfs: a glibc Linux Userland Inside an App

### 64.3.1 What Is in the rootfs

Wine, the emulator's guest libraries, and the game all expect a Linux
filesystem laid out the normal way, with `/usr/lib`, `/bin`, an `ld-linux`
dynamic loader, and above all a **glibc** C library. Android provides none of
that to an app; it provides `bionic` and an app-private data directory. So the
stack ships an entire small Linux distribution, historically called the
**imagefs** in Winlator, and extracts it into the app's private storage.

The rootfs is based on **Ubuntu** (the original Winlator uses Focal Fossa,
20.04). Inside it sit a glibc userland, the Wine installation under `/opt`, and
the per-container **Wine prefix** at `/home/xuser/.wine`. The path constants are
defined in `com.winlator.xenvironment.ImageFs`.

### 64.3.2 Shipping and Extraction

The userland is shipped compressed and unpacked on first use, never mounted (an
app cannot mount). The relevant code is `ImageFsInstaller`, which extracts the
Wine tarball into `<rootfs>/opt/<version>`, and `TarCompressorUtils`, which
handles both the Zstandard `.tzst` and xz `.txz` formats GameNative uses. Once
extracted, ELF binaries are fixed up with `patchelf` so their interpreter and
library search paths point inside the rootfs rather than at a system that does
not exist.

The size is the reason the rootfs is delivered as an on-demand dynamic-feature
module (64.2.5): a full Ubuntu-plus-Wine userland is hundreds of megabytes
to gigabytes, far too large to sit in a base APK.

### 64.3.3 Entering the rootfs: PRoot

A desktop setup would `chroot` into the rootfs. An unrooted app cannot. The
classic Winlator answer is **PRoot**, a userspace re-implementation of `chroot`
and bind-mounts built entirely on the Linux `ptrace` system call.

PRoot launches the guest program as a traced child. Every time the child makes a
system call that names a path, PRoot intercepts it at the kernel boundary,
*rewrites the path string in the tracee's memory* so that, say, `/usr/lib/...`
becomes `<app data>/imagefs/usr/lib/...`, and then lets the kernel proceed. The
guest believes it lives at `/`; in reality every path is being remapped on the
fly. The same trick is reapplied across `execve` so that child processes stay
confined. Bind-mounts like `--bind=/dev` and `--bind=/proc` are implemented the
same way, by remapping the relevant prefixes.

#### Diagram: how PRoot remaps a guest path with ptrace

```mermaid
sequenceDiagram
    participant G as Guest (Wine/box64)
    participant K as Linux kernel
    participant P as PRoot tracer

    G->>K: openat(AT_FDCWD, "/usr/lib/libc.so")
    K-->>P: ptrace stop (syscall-enter)
    P->>P: Rewrite path to<br/>/data/.../imagefs/usr/lib/libc.so
    P->>K: ptrace continue
    K-->>G: fd for the real file in app storage
```

The cost is the price of admission for going rootless: every path-bearing
syscall takes a `ptrace` stop-and-continue round trip into the PRoot process.
That overhead is the main reason the newer **bionic** designs (64.3.6) try to
eliminate PRoot entirely.

### 64.3.4 glibc Versus bionic: the Central Mismatch

The rootfs gives Wine a glibc world, which is exactly what Wine wants. But it
creates the defining problem of the whole stack: **the process now contains
glibc, while every native Android library, including the GPU driver, is built
against `bionic`.** You cannot simply `dlopen` a `bionic` `.so` into a glibc
process. The two C libraries disagree about thread-local storage layout, about
the dynamic loader's internal structures, about `errno`, about `pthread_t`,
about stack canaries. Loading one libc's shared object into the other's process
corrupts state and crashes.

This is the problem that "bionic redirections" exist to solve, and it is
important enough to get its own section (64.4). For now, note the shape of the
two answers: either keep the glibc world and reach Android services through
**inter-process communication** rather than linking (the PulseAudio server, the
Vortek renderer, and the SysV-SHM server are all separate endpoints reached over
sockets), or abandon glibc and run Wine directly on `bionic` (the newer forks).

### 64.3.5 System V Shared Memory over ashmem

The cleanest concrete example of a bionic redirection is System V shared memory.
X11, DXVK, and other components use `shmget`/`shmat` to share large buffers
between processes. Android's kernel restricts the System V SHM API. Winlator's
glibc rootfs therefore carries a **patched glibc** whose `shmget`/`shmat`/`shmdt`
family is reimplemented on top of Android's anonymous shared memory, brokered by
a small server on the Android side (`com.winlator.sysvshm`).

On the Android side, the natural primitive is `ASharedMemory_create`
(`frameworks/native/include/android/sharedmem.h:78`), the NDK entry point that
returns a file descriptor for an anonymous, refcounted shared-memory region.
Underneath, it is backed by `memfd_create`
(`bionic/libc/include/sys/mman.h:183`, available from API 30) or the older
ashmem driver. The redirection turns a System V `shmget` call inside the guest into
an `ASharedMemory`-style fd on the host, passed back across the socket. The guest
keeps using the System V API it was written for; the host satisfies it with an
Android primitive the kernel actually allows.

### 64.3.6 The bionic-Wine Alternative

The newest Winlator forks, and GameNative's default path, take the other route:
build Wine for **`bionic`** and drop PRoot. If Wine itself runs on `bionic`,
there is no libc mismatch with the Android GPU driver, and there is no per-syscall
`ptrace` tax. The price is that everything Wine relied on glibc for must now be
provided on `bionic`, which is why this path leans on ARM64EC Wine builds
(64.5.8) and a set of redirection libraries that fix up path and behaviour
differences in place of PRoot. We turn to those next.

---

## 64.4 Bionic Redirections and the libc Boundary

"Bionic redirections" is the umbrella term for the techniques that let a stack
built around glibc-flavoured Linux software cooperate with an Android system
built around `bionic`. There are several distinct problems hiding under that
phrase, and they have different solutions.

### 64.4.1 Why Two libcs Cannot Share a Process

Restating the core constraint precisely, because everything else follows from
it: a single Linux process has exactly one dynamic loader and one C library
providing the loader's internal state, the TLS block, `malloc`, and the syscall
wrappers. glibc and `bionic` are different implementations with incompatible
internal layouts. A glibc process's threads have glibc `pthread` structures and a
glibc TLS model; a `bionic` `.so` compiled to find its thread-control-block at a
`bionic` offset will read garbage. There is no flag that makes the two coexist.
The boundary between them must be crossed by *some* mechanism that does not
require linking, and there are exactly three such mechanisms in this stack:
inter-process communication, ABI thunking, or choosing one libc for the whole
process.

### 64.4.2 Linker Namespaces and dlext

Even when the stack does run native `bionic` code, it is subject to the linker
namespace isolation from Chapter 7. App native libraries load into a restricted
namespace that cannot see most system libraries. The driver-loading path uses
`android_dlopen_ext` with `ANDROID_DLEXT_USE_NAMESPACE`
(`bionic/libc/include/android/dlext.h:115`) to target a specific namespace, and
custom-driver loaders such as **adrenotools** (used to side-load a newer Turnip
build than the device ships) rely on exactly this machinery to get a chosen
`.so` loaded into a namespace that can reach the GPU kernel interfaces. The
`ANDROID_DLEXT_USE_LIBRARY_FD` flag
(`bionic/libc/include/android/dlext.h:80`) is the companion that loads a driver
straight from a file descriptor.

### 64.4.3 W^X and the JIT

The translators are JITs, and a JIT must respect the write-xor-execute rule the
platform enforces (64.1.4). The pattern every translator on Android follows is:
map a code buffer `PROT_READ | PROT_WRITE`, emit AArch64 instructions into it,
clear the instruction cache for that range, then `mprotect` it to
`PROT_READ | PROT_EXEC` before jumping in. A page is never both writable and
executable at once, satisfying the linker's W+E rejection
(`bionic/linker/linker_phdr.cpp:1058`). On devices and Android versions that
further restrict executing memory from app data, the translator must allocate
its code pages as anonymous memory it owns rather than mapping a file from the
data directory.

### 64.4.4 Path Redirection: PRoot Versus libredirect

PRoot (64.3.3) is one form of path redirection: rewrite paths in the kernel ABI
using `ptrace`. It is general but slow. The bionic path replaces it with a
preloaded library, GameNative's `libredirect.so`, injected into Wine
subprocesses with `LD_PRELOAD`. Instead of trapping every syscall through
`ptrace`, the library interposes the libc functions that take paths and rewrites
their arguments in-process, with no tracer round trip. It also adapts process
launches to recent-Android restrictions on executing from the app data
directory, standing in for the kernel mechanism that an unrooted app is not
allowed to use. The trade-off is generality for speed: a preload library only
catches calls that go through the functions it interposes, whereas PRoot catches
everything at the kernel boundary, but the preload approach avoids the
per-syscall `ptrace` cost that dominates PRoot's overhead.

### 64.4.5 The IPC Escape Hatch

The most robust redirection is to not cross the libc boundary in-process at all.
Three of the stack's services live on the Android (`bionic`) side as separate
endpoints and are reached from the guest over Unix-domain sockets:

- the **PulseAudio server**, which the guest's Wine audio backend connects to as
  an ordinary PulseAudio client (64.8);
- the **Vortek Vulkan renderer**, where the guest holds only a thin Vulkan ICD
  that serialises commands over a socket to the native renderer (64.7.3);
- the **System V SHM server** (64.3.5).

Because the boundary is a socket, the two sides can use different C libraries,
different instruction sets, and different memory models without any of it
mattering: the only contract is the wire protocol. This is the same reason
Binder works across processes with different runtimes (Chapter 9). It costs a
serialisation step and a copy, but it sidesteps the libc problem entirely, which
is why the performance-critical-but-not-hottest paths (audio, command
submission) are built this way while the truly hot path (CPU translation) is
not.

---

## 64.5 FEX and Box64: Translating x86-64 to AArch64

This is the layer that does the actual instruction-set emulation from 64.1.1.
Two projects dominate, and GameNative ships both: **FEX** (the default, via its
FEXCore engine) and **Box64**. They solve the same problem with opposite
philosophies, and understanding the difference explains most of the
compatibility-versus-speed trade-offs users encounter. This chapter complements
Chapter 19, which covered Android's *own* in-process binary translators
(Berberis and Houdini) for running x86 Android apps on ARM. FEX and Box64 are
the same idea applied to whole Linux/Windows x86-64 programs rather than Android
APKs.

### 64.5.1 What a Dynamic Recompiler Does

A dynamic recompiler, or dynarec, is a JIT for foreign machine code. It reads a
block of x86-64 instructions, translates them once into AArch64 instructions,
caches the result, and jumps to the cached translation every time the guest
reaches that address again. The translated code keeps the guest's registers in
host registers, keeps the guest's memory as ordinary host memory, and falls back
to a dispatcher only at block boundaries to decide what to run next. A dynarec is
typically five to ten times faster than an interpreter because the per-instruction
decode cost is paid once, at translation time, instead of on every execution.

Three things make x86-to-ARM specifically hard, and each one is a place where
FEX and Box64 spend their engineering effort:

1. **Flags.** Almost every x86 arithmetic instruction updates the EFLAGS
   register. Computing those flag bits on ARM after every operation is
   ruinously expensive, so a good dynarec defers and elides flag computation,
   only materialising flags when something actually reads them.
2. **Vector instructions.** SSE, AVX, and x87 floating point have to map onto
   ARM's NEON vector registers (and SVE where the host supports it), with
   careful attention to NaN handling and rounding.
3. **The memory model.** x86 has a strong memory model (Total Store Ordering);
   ARM has a weaker one. Preserving correctness here is subtle and costly enough
   to warrant its own subsection (64.5.3).

### 64.5.2 The FEXCore Pipeline

FEX is a userspace x86 and x86-64 emulator for AArch64 hosts. Its emulation
engine is a library called **FEXCore**, and its translation pipeline is a clean
four-stage design:

#### Diagram: the FEXCore translation pipeline

```mermaid
graph LR
    X86["x86-64 instruction<br/>stream"] --> DEC["Frontend decoder<br/>prefixes, REX, VEX/EVEX"]
    DEC --> DISP["OpcodeDispatcher<br/>x86 semantics to IR"]
    DISP --> IR["SSA IR"]
    IR --> PASS["PassManager<br/>optimization passes"]
    PASS --> JIT["Arm64 JIT emitter"]
    JIT --> HOST["Native AArch64<br/>code in cache"]
```

Walking the stages against the FEX source tree:

- **The frontend decoder** reads the raw byte stream and finds instruction
  boundaries, handling x86's legacy prefixes, REX prefixes, and the VEX/EVEX
  encodings used by AVX.
- **The `OpcodeDispatcher`** (`FEXCore/Source/Interface/Core/OpcodeDispatcher.cpp`,
  with vector and x87 handling split into `OpcodeDispatcher/Vector.cpp` and
  `OpcodeDispatcher/X87.cpp`) translates each decoded instruction into FEX's own
  SSA-form intermediate representation. The IR opcodes themselves are defined in
  `FEXCore/Source/Interface/IR/IR.json`.
- **The `PassManager`** (`FEXCore/Source/Interface/IR/PassManager.cpp`) runs
  optimisation passes over the IR. The most important for performance are
  register allocation (mapping IR values to ARM registers), redundant-flag
  elimination (dropping EFLAGS updates that are never read), and an x87 stack
  optimisation pass.
- **The JIT backend** (`FEXCore/Source/Interface/Core/JIT/JIT.cpp`) emits native
  AArch64 instructions from the optimised IR into the code cache. FEX uses a
  custom ARM64 emitter rather than an off-the-shelf assembler to keep code
  generation fast and compact.

FEX supports MMX, SSE through SSE4, x87, and AVX/AVX2, and it translates
multi-block regions rather than single basic blocks, dispatching between cached
translations through a lookup cache. Self-modifying code is handled by detecting
guest writes to pages that contain translated code and invalidating the affected
cached blocks.

### 64.5.3 The TSO Memory-Model Problem

This is the most important performance subtlety in the entire emulation layer.
x86 guarantees Total Store Ordering: stores from one core become visible to
other cores in program order. ARM does not; it allows stores to be reordered
unless you insert barriers or use acquire/release instructions. A multithreaded
game written for x86's strong ordering will race and crash if its memory
operations are naively translated to plain ARM loads and stores.

FEX's correct-by-default answer is to emulate TSO, using ARM's acquire/release
load and store instructions (the `FEAT_LRCPC` extensions) and atomics
(`FEAT_LSE2` for the unaligned atomics x86 permits but ARM normally forbids).
This emulation is expensive: faithfully reproducing x86 ordering on a weak model
can cost on the order of a 10x slowdown on the affected memory traffic, felt most
in vector-heavy game code.

The escape valve is **hardware TSO**. Some ARM cores can be switched into a
hardware total-store-ordering mode; Apple Silicon does this (it is how Rosetta 2
is fast), and where the host CPU exposes it, FEX requests it and relaxes its
software emulation for a large win. FEX also offers tunables to disable TSO
emulation for vector accesses or for stack memory (which is thread-private and
safe), trading a little stability for speed. The practical upshot for a phone is
that a Snapdragon's specific memory-ordering capabilities materially affect how
fast emulation runs, independent of raw clock speed.

### 64.5.4 FEX Thunks: Calling Native ARM64 Graphics

If FEX translated *every* instruction the game's process executed, including the
entire Vulkan driver, performance would be hopeless. The lever that avoids this
is **thunking**, also called library forwarding. A thunk lets emulated x86 guest
code call a **native AArch64** host library directly, so heavy libraries like
the GPU driver run as native code rather than being translated instruction by
instruction.

The design is two-sided. On the guest side, FEX provides a small x86 stub
library that presents the normal guest ABI (for example a guest `libvulkan.so`)
but, instead of containing the driver, forwards each call across the boundary. On
the host side, a native ARM64 thunk library receives the forwarded call and
invokes the real host library. The FEX source carries both halves for the key
graphics libraries: `ThunkLibs/libvulkan/Guest.cpp` and
`ThunkLibs/libvulkan/Host.cpp` for Vulkan, and `ThunkLibs/libGL/` for OpenGL.

#### Diagram: a thunked Vulkan call crossing the emulation boundary

```mermaid
graph LR
    subgraph GuestSide["Emulated x86-64 (FEX)"]
        APP["Game / DXVK"] --> GTHUNK["Guest libvulkan thunk<br/>x86-64 stub"]
    end
    subgraph HostSide["Native AArch64"]
        HTHUNK["Host vulkan thunk"] --> REAL["Real Vulkan driver"]
    end
    GTHUNK -->|"marshal args,<br/>cross ABI"| HTHUNK
```

The hard part is marshalling: the guest and host disagree on pointer size in the
32-bit case, on structure layout, and on calling convention, and callbacks (a
function pointer the host library will call back into) must be trampolined back
across the boundary in the other direction. FEX's thunking handles function
pointers in both directions and converts data-structure layouts at the boundary,
configured by a `ThunksDB.json` that maps each guest library to its host overlay.
Thunking is the single biggest reason FEX-based graphics can approach native
speed: only the game's draw-call *setup* is emulated, while the driver work runs
native.

### 64.5.5 The FEX RootFS Requirement

When FEX runs as a standalone Linux emulator, emulating a complete x86-64
*process*, it needs an x86-64 root filesystem to supply the guest glibc and base
libraries; on desktop Linux the `FEXRootFSFetcher` downloads a SquashFS or EroFS
image for exactly that. This is the everything-emulated model, and it is the
main axis on which Box64 differs, since Box64 wraps host libraries instead of
emulating a full guest userland.

In GameNative's default ARM64EC configuration, however, FEX does not run as a
Linux emulator at all. It plugs into Wine as a CPU-only module (64.5.8): the
Windows system calls are serviced by Wine rather than by a guest glibc, so the
separate x86 rootfs is no longer needed. The FEX rootfs requirement is therefore
a property of the everything-emulated path, not of the ARM64EC default, and
shedding it is one of ARM64EC's concrete wins.

### 64.5.6 Box64: Wrapped Native Libraries

Box64, by ptitSeb, is a dynarec with the same core job but a different
philosophy about system libraries. Instead of emulating the x86-64 glibc, GL,
and Vulkan from a rootfs, Box64 detects when the guest is about to call into one
of those well-known libraries and **substitutes the host's native ARM64
implementation**, wrapping each call to translate the calling convention. The
hand-written wrappers live in the Box64 source under `src/wrapped/`, for example
`src/wrapped/wrappedvulkan.c` for Vulkan and `src/wrapped/wrappedlibc.c` for the
C library.

The consequence is that Box64 does not need a full x86 rootfs for the libraries
it wraps; it borrows the host's. That makes it lighter than FEX, and it is the
historical default of classic Winlator, where the launch chain is literally
`proot` then `box64` then `wine`. GameNative's `GuestProgramLauncherComponent`
builds exactly that `box64 <guest exe>` command for the glibc path. The trade-off
is that wrapping is only as correct as the wrappers: when a wrapped library's
behaviour diverges from what the guest expected, it can break in ways a
full-emulation approach would not.

The 32-bit story is symmetric. Box64 handles x86-64; its sibling **Box86**
handles 32-bit x86, and for hosts with no 32-bit ARM environment Box64 has an
experimental `BOX32` mode that emulates a 32-bit environment within the 64-bit
one. Box64's own `docs/WINE.md` lays out the matrix of Wine variants (x86, x86-64,
x86-64 WoW64, ARM64 WoW64) and which Box combination each requires; it is the
single best primary reference for how the emulator and Wine fit together.

### 64.5.7 FEX Versus Box64

#### Diagram: the two emulation philosophies

```mermaid
graph TB
    subgraph FEXapproach["FEX: emulate the process, thunk the hot libs"]
        F1["x86-64 rootfs<br/>(guest glibc)"] --> F2["FEXCore JIT"]
        F2 -->|"thunk"| F3["Native ARM64<br/>Vulkan / GL"]
    end
    subgraph BOXapproach["Box64: emulate the app, wrap the system libs"]
        B1["Guest x86-64 app"] --> B2["Box64 dynarec"]
        B2 -->|"wrap"| B3["Host ARM64<br/>libc / GL / Vulkan"]
    end
```

| Dimension | FEX | Box64 |
|-----------|-----|-------|
| System libraries | emulated from an x86-64 rootfs | wrapped to host-native ARM64 |
| Disk footprint | heavier (full rootfs) | lighter (borrows host libs) |
| Native-lib escape | thunks (GL, Vulkan) | wrappers (libc, GL, Vulkan, more) |
| 32-bit code | same core; WoW64/ARM64EC | separate Box86, or BOX32 |
| Accuracy posture | full IR recompiler, rigorous TSO | pragmatic; depends on wrapper fidelity |
| Role in GameNative | default (FEXCore) | bundled alternative |

Neither is universally better. FEX's full-emulation accuracy helps with
heavily-modded or unusual titles; Box64's lighter footprint and mature wrappers
made it the long-time Winlator default. GameNative ships both and lets a
container pick.

### 64.5.8 ARM64EC and WoW64: Emulating Only the Game

The most important recent shift is architectural, not incremental: stop running
Wine itself through the emulator. In the "everything emulated" model, the JIT
translates the game *and* all of Wine *and* the x86 Linux libraries underneath
Wine; the emulator is on the hot path for every instruction. The **ARM64EC**
model instead builds Wine natively for ARM64 and emulates only the game's x86-64
code.

ARM64EC ("Emulation Compatible") is a Microsoft ABI, reimplemented in Wine, in
which native ARM64 code is laid out to be call-compatible with emulated x86-64
code. Wine's system DLLs are compiled in this ABI, so when the emulated game
calls a Windows API, execution transitions into *native* ARM64 Wine code instead
of continuing to emulate. The emulator is reduced to a CPU core that plugs into
Wine as a loadable module at the ABI boundary. In this configuration the
emulator ships as a Windows DLL that Wine loads: FEX as `libarm64ecfex.dll` for
64-bit code, and either `libwow64fex.dll` (FEX) or `wowbox64.dll` (Box64) for the
32-bit WoW64 path. GameNative selects between these in its
`BionicProgramLauncherComponent` based on whether the configured Wine build is
ARM64EC.

#### Diagram: shrinking the emulated region with ARM64EC

```mermaid
graph TB
    subgraph Everything["Everything emulated"]
        E1["Game (x86-64)"]
        E2["Wine (x86-64)"]
        E3["Linux libs (x86-64)"]
    end
    subgraph EC["ARM64EC hybrid"]
        H1["Game (x86-64)<br/>EMULATED"]
        H2["Wine (ARM64EC)<br/>NATIVE"]
        H3["Vulkan / audio (ARM64)<br/>NATIVE"]
    end
    Everything -->|"only the game stays emulated"| EC
```

The payoff is large: the Windows API work, the graphics translation, and the
audio path all run as native ARM64, and only the game's own instruction stream is
translated. This is the design GameNative defaults to, and it is why the stack is
fast enough to be usable on a phone at all.

---

## 64.6 Wine: Implementing the Windows API

Wine is the layer that makes the game think it is running on Windows. Where the
emulator handles instructions, Wine handles meaning: every call the game makes to
the Windows API is serviced by Wine's reimplementation of that API on top of the
Linux kernel.

### 64.6.1 Not an Emulator

The name is a recursive acronym, "Wine Is Not an Emulator," and on ARM Android
the distinction is not pedantry, it is the architecture. Wine contains no
instruction translation whatsoever. It takes a Windows PE binary, loads it into a
Linux process, and answers its Windows API and NT system calls with native code
that talks to Linux. On x86-64 Linux that native code runs directly. On ARM
Android, Wine is *itself* either emulated (the everything-emulated model) or
compiled native as ARM64EC (the hybrid model) but in neither case does Wine do
the x86-to-ARM translation; that is always FEX or Box64. The two layers are
orthogonal, exactly as 64.1.1 set out.

### 64.6.2 The PE/Unix Split

Modern Wine is organised around a hard boundary between Windows PE code and a
Unix backend. Wine's builtin DLLs (`ntdll`, `kernel32`, `kernelbase`, `user32`,
`gdi32`) are compiled as real PE files, so from the game's point of view it is
calling ordinary Windows DLLs. The subset of DLLs that must touch the host OS are
split into a PE part and a Unix part.

The canonical example is `ntdll`. The PE side (`dlls/ntdll/`) builds
`ntdll.dll`; the Unix side (`dlls/ntdll/unix/`) builds `ntdll.so`, an ELF
library `dlopen`'d at startup whose key files are `dlls/ntdll/unix/loader.c`,
`dlls/ntdll/unix/virtual.c`, and `dlls/ntdll/unix/signal_x86_64.c`. The contract
between the two halves is declared in `dlls/ntdll/unixlib.h`.

Process startup begins as a perfectly ordinary Linux process: a small loader
`dlopen`s `ntdll.so`, which builds the Windows process control structures (the
PEB and TEB), maps the PE `ntdll.dll` and the initial executable, connects to
wineserver, and finally jumps into PE-side initialization, after which control
runs "as if it were Windows."

#### Diagram: Wine's PE and Unix halves and the syscall boundary

```mermaid
graph TD
    subgraph PE["PE world (Windows binaries)"]
        GAME["Game.exe"]
        K32["kernel32.dll / user32.dll"]
        NTPE["ntdll.dll (PE)"]
    end
    subgraph UNIX["Unix world (ELF)"]
        NTSO["ntdll.so"]
        SERVER["wineserver client"]
    end
    GAME --> K32 --> NTPE
    NTPE -->|"__wine_syscall_dispatcher"| NTSO
    NTPE -->|"WINE_UNIX_CALL"| NTSO
    NTSO --> SERVER
    NTSO --> KERNEL["Linux kernel"]
```

Two mechanisms cross the boundary. NT system calls (`NtCreateFile`,
`NtUserCreateWindowEx`) funnel through a `__wine_syscall_dispatcher` set up in
`dlls/ntdll/unix/signal_x86_64.c`, which saves CPU state, switches to a Unix
stack, indexes a syscall table, and calls the Unix implementation. DLLs with a
Unix backend that bypass the NT table instead use `WINE_UNIX_CALL`. The fact that
Wine routes Windows API calls through an explicit, NT-like syscall boundary is
exactly what makes the ARM64EC and WoW64 transitions of 64.5.8 possible: the
boundary is already there to hook.

### 64.6.3 wineserver

wineserver is a separate daemon that provides Wine roughly the services the
Windows kernel provides on Windows. Every Wine process sharing a prefix shares,
through wineserver, the things NT keeps in kernel space: handles and the object
namespace, synchronization objects (events, mutexes, semaphores), processes and
threads, window-management state, and the registry.

Clients talk to it over an `AF_UNIX` socket, marshalling requests through
`wine_server_call`; the server's request handlers live in `server/request.c`.
The socket lives in a per-prefix directory keyed off the prefix's device and
inode, so each prefix gets its own server. A particularly important detail is
that the socket passes **file descriptors** between processes using the standard
`SCM_RIGHTS` ancillary-data technique, so a Windows `HANDLE` can be backed by a
real Linux fd handed over from the server.

The performance caveat matters on a phone. Games synchronize threads constantly,
and the classic "ask wineserver every time" model makes each synchronization a
socket round trip. Wine has progressively moved synchronization out of the
server: **esync** (eventfd-based), **fsync** (futex-based), and most recently
**ntsync**, a Linux kernel driver exposing `/dev/ntsync` that models NT
synchronization primitives in-kernel. Whether the faster paths are available
depends on the host kernel: an Android kernel may not expose `/dev/ntsync` at
all, in which case the stack falls back to fsync on futexes, which Android does
have.

### 64.6.4 The Prefix, the C: Drive, and the Registry

A **Wine prefix** (the `WINEPREFIX`, here `/home/xuser/.wine` inside the rootfs)
is one self-contained virtual Windows installation: its own C: drive, its own
registry, and its own wineserver. Inside, `drive_c/windows/system32` holds the
64-bit system DLLs, `drive_c/windows/syswow64` holds the 32-bit ones (the
Windows naming inversion is preserved), and `dosdevices/` holds the symlinks that
map drive letters to host paths. The registry is stored as text `.reg` files at
the prefix root (`system.reg` for HKLM, `user.reg` for HKCU) and served live by
wineserver.

This layout is why a container is portable and disposable: it is just a directory
tree. GameNative's per-game containers are exactly per-game prefixes, which is
how two games with conflicting DLL or registry needs stay isolated.

### 64.6.5 DLL Overrides: How DXVK Replaces Wine's Direct3D

Wine decides, per DLL, whether to use its own builtin implementation or a
**native** DLL placed in the prefix. The choice is driven by the
`WINEDLLOVERRIDES` environment variable and by registry entries under
`HKCU\Software\Wine\DllOverrides`. This single mechanism is how the entire
graphics fast path gets installed: DXVK and VKD3D-Proton ship PE DLLs named
exactly like Wine's builtin Direct3D DLLs (`d3d9.dll`, `d3d11.dll`, `dxgi.dll`,
`d3d12.dll`), the installer copies them into the prefix's `system32`/`syswow64`,
and sets those names to `native`. The next time the game calls
`D3D11CreateDevice`, Wine's loader resolves `d3d11.dll` to the DXVK file instead
of its own `wined3d`-backed builtin, and Direct3D is now translated to Vulkan
(64.7) rather than to OpenGL.

### 64.6.6 Where Wine Meets the Emulator

Tying 64.5 and 64.6 together: in the ARM64EC configuration, Wine is native
ARM64EC, its DLLs transition to native code at the syscall boundary, and the
emulator (`libarm64ecfex.dll` or the WoW64 helper) is invoked only to run the
game's x86-64 instruction stream. In the everything-emulated configuration, all
of Wine is x86-64 and runs on top of Box64 or FEX against the rootfs glibc. Both
configurations present the game an identical Windows; they differ only in how
much of the process below the game is emulated versus native, which is the single
biggest determinant of frame rate.

---

## 64.7 Graphics: Direct3D to the Adreno GPU

Graphics is where the stack either succeeds or visibly fails, and it is the
longest translation chain in the book: a Direct3D call made by an x86-64 game
ends up as a Vulkan command executed by the phone's Adreno driver and composited
by SurfaceFlinger. Every link in that chain is a separate technology.

### 64.7.1 The Translation Chain

#### Diagram: the full Direct3D-to-display chain

```mermaid
graph TD
    GAME["Game: Direct3D 9/11/12 calls"]
    DXVK["DXVK / VKD3D-Proton<br/>(D3D to Vulkan)"]
    GUESTVK["Guest Vulkan ICD<br/>(thunk or Vortek client)"]
    BRIDGE["Boundary cross<br/>(thunk / IPC / wrap)"]
    HOSTVK["Android Vulkan loader<br/>libvulkan"]
    DRIVER["Adreno Vulkan driver<br/>(or Turnip)"]
    SURFACE["ANativeWindow<br/>to SurfaceFlinger"]

    GAME --> DXVK --> GUESTVK --> BRIDGE --> HOSTVK --> DRIVER
    DRIVER --> SURFACE
```

The chain has two halves separated by the libc boundary from 64.4. Above the
boundary, in the Windows/guest world, Direct3D becomes Vulkan. Below it, on the
Android side, Vulkan reaches the real driver and the frame reaches the display.
The interesting engineering is entirely in how the boundary is crossed.

### 64.7.2 D3D to Vulkan: DXVK, VKD3D, and the Fallbacks

Several translators cover the Direct3D version space, all installed as Wine DLL
overrides (64.6.5):

- **DXVK** translates Direct3D 9/10/11 to Vulkan. It ships `d3d9.dll`,
  `d3d11.dll`, `dxgi.dll` and related DLLs. It is the default `DEFAULT_DXWRAPPER`
  in GameNative containers.
- **VKD3D-Proton** translates Direct3D 12 to Vulkan, shipping `d3d12.dll` and
  `d3d12core.dll`. It is the Valve-tuned fork of WineHQ's own vkd3d, optimised
  for game performance.
- **D8VK** extends DXVK down to Direct3D 8.
- **wined3d** is Wine's builtin fallback, translating Direct3D to OpenGL rather
  than Vulkan. It is slower and used only when a game is incompatible with DXVK.
- **cnc-ddraw** handles legacy DirectDraw titles.

The key architectural point is that on ARM64EC these translators are native
ARM64 code (64.5.8). Only the game's D3D *calls* originate from emulated code;
the heavy work of turning a frame's worth of draw calls into Vulkan command
buffers runs native. This is why DXVK on a phone is far faster than the alternative
of translating Direct3D inside a fully-emulated x86 Wine.

### 64.7.3 Reaching the Real GPU: Turnip and Vortek

Vulkan commands now have to reach the actual Adreno GPU, and there are two
strategies, which is the most important fork in the graphics design.

**Turnip** is Mesa's open-source Vulkan driver for Adreno GPUs. The stack ships a
Turnip build (and can side-load a newer one via adrenotools, 64.4.2) so the guest
has a real, complete Vulkan implementation that talks to the Adreno kernel
interface directly. Turnip exists because the Vulkan driver a phone ships is often
incomplete or buggy for the unusual workloads Wine and DXVK generate; a known-good
Mesa driver sidesteps that. In the FEX world, the guest reaches Turnip through the
**thunk** mechanism (64.5.4): a guest `libvulkan` stub forwards to the native
Turnip.

**Vortek** is Winlator's own Vulkan compatibility layer, and it takes the IPC
route from 64.4.5 instead of thunking. It is a client/server design: the guest
links a thin Vortek Vulkan **ICD** (shipped into the rootfs from an
`assets/.../vortek-*` archive) that serialises every Vulkan call into a command
stream and ships it over a Unix socket to a **native Android server**, the
prebuilt `libvortekrenderer.so`, driven by `VortekRendererComponent`. The server
replays the commands against the device's real Vulkan driver, and along the way
it can patch SPIR-V shaders, decode texture formats the host driver lacks, and
emulate features. Vortek is GameNative's
default graphics driver precisely because the socket boundary makes it robust to
the glibc/`bionic` mismatch: the guest and the host driver never share an address
space.

#### Diagram: Turnip (thunk) versus Vortek (IPC) to the GPU

```mermaid
graph TB
    subgraph TurnipPath["Turnip: native driver in-process via thunk"]
        TG["Guest Vulkan (DXVK)"] -->|"thunk"| TN["Turnip (Mesa) native"]
        TN --> TK["Adreno kernel DRM"]
    end
    subgraph VortekPath["Vortek: serialize over a socket"]
        VG["Guest Vortek ICD"] -->|"command stream<br/>over Unix socket"| VS["Native Vortek server"]
        VS --> VD["Device Vulkan driver"]
        VD --> VK2["Adreno kernel DRM"]
    end
```

A handful of other paths exist for non-Vulkan or low-end cases: **Zink** (Mesa's
OpenGL-on-Vulkan), **VirGL** (a virtio-gpu virtual 3D renderer with its own
client/server), and **llvmpipe** (a pure-CPU software rasteriser of last resort).

### 64.7.4 The Android Vulkan Loader

Whichever guest path is used, the bottom of the chain is the same AOSP Vulkan
loader from Chapter 13. The loader discovers and loads the device's Vulkan driver
in `frameworks/native/vulkan/libvulkan/driver.cpp`; the `LoadDriver` routine
(`frameworks/native/vulkan/libvulkan/driver.cpp:157`) opens the HAL driver
(`vulkan.<board>.so`) and, importantly, does so with `android_dlopen_ext` using
the namespace flag from 64.4.2, because the driver lives in a restricted linker
namespace. A native renderer such as Vortek's server, or a thunked Turnip, is in
the end just another client of this loader and this driver, which is why the
whole edifice works without any platform modification: the GPU is reached through
the same public Vulkan interface any Android game uses.

### 64.7.5 Presentation: the In-App Surface

Rendered frames must become pixels on screen. The game does not get a real X
display or a real window system; it gets GameNative's **in-app X server**, a
small X11 server implemented inside the app (`com.winlator.xserver`, native code
under `app/src/main/cpp/winlator/`) that receives the game's output and the
window it draws into. The X server's contents are drawn with Vulkan and presented
to an Android **Surface**.

That final step uses the native window APIs from Chapter 13. Frames reach the
compositor through `ANativeWindow`; for the CPU-access path the functions are
`ANativeWindow_lock`
(`frameworks/native/libs/nativewindow/include/android/native_window.h:179`) and
`ANativeWindow_unlockAndPost`
(`frameworks/native/libs/nativewindow/include/android/native_window.h:188`), while
the zero-copy GPU path binds an `AHardwareBuffer`
(`frameworks/native/libs/nativewindow/include/android/hardware_buffer.h:479`, via
`AHardwareBuffer_allocate`) as the Vulkan swapchain image so the GPU renders
straight into a buffer SurfaceFlinger can scan out. From SurfaceFlinger onward
(Chapter 24) the game's frame is just another layer composited to the display.

### 64.7.6 Frame Generation

As an optional final touch, GameNative can insert a Vulkan implicit layer that
performs frame generation, interpolating synthetic frames between rendered ones by
intercepting `vkQueuePresentKHR`. It is a layer in the Vulkan sense, slotting into
the loader's layer chain, and it illustrates how much of the graphics stack is
built out of standard Vulkan extension points rather than bespoke hooks.

---

## 64.8 Audio: from WASAPI to AAudio

Audio is a shorter chain than graphics but crosses the same libc boundary, and it
is solved with the IPC pattern from 64.4.5: a real audio server runs on the
Android side and the guest connects to it as a client.

### 64.8.1 Wine's Audio Backends

A Windows game emits audio through one of several front-end APIs (the modern
WASAPI via `mmdevapi`, legacy DirectSound, or the old `winmm`/`waveOut`). Wine
layers all of them onto a single backend driver chosen at runtime. The backend
that matters here is `winepulse.drv`, which targets **PulseAudio**; the
alternatives are `winealsa.drv` (ALSA) and `wineoss.drv` (OSS). Each backend is a
PE driver DLL paired with a Unix `.so` that calls the host audio client library.
In the ARM64EC configuration the backend and its client library are native ARM64,
so audio mixing and transport are not emulated; only the game's calls into the
front-end API cross the emulator.

### 64.8.2 A PulseAudio Server Inside the App

There is no system PulseAudio daemon available to an unrooted app, so the stack
ships one. GameNative's `PulseAudioComponent` starts a PulseAudio server from the
bundled native libraries (`libpulse.so` and the `libpulsecommon`/`libpulsecore`
PulseAudio 13 libraries in `jniLibs/`). Wine's `winepulse.drv` connects to this
server exactly as it would to a desktop PulseAudio, over PulseAudio's normal
socket protocol. Because the contract is the PulseAudio wire protocol, the guest
side (glibc, possibly emulated) and the server side (`bionic`, native) interoperate
across the libc boundary without sharing an address space.

#### Diagram: the audio path from game to speaker

```mermaid
graph LR
    GAME["Game: WASAPI / DirectSound"] --> WP["winepulse.drv"]
    WP -->|"PulseAudio protocol<br/>over socket"| PA["PulseAudio server<br/>(in app, native)"]
    PA --> AA["AAudio / AudioTrack"]
    AA --> HAL["Audio HAL to speaker"]
```

### 64.8.3 The ALSA Bridge

Winlator also provides a lower-level ALSA route. The rootfs carries a custom ALSA
PCM plugin (Winlator's `android_alsa`, `module_pcm_android_aserver.c`) that
exposes an "android aserver" PCM device; on the Android side
`com.winlator.alsaserver` implements the server endpoint, and a native client
(`app/src/main/cpp/winlator/` audio code) ships the PCM frames to the app. Whether
audio takes the PulseAudio route or the ALSA route, the structure is identical: a
guest audio API, a socket, and a native Android endpoint.

### 64.8.4 Reaching the Speaker via AAudio

The Android endpoint ultimately writes the decoded PCM into an Android audio
stream. The natural API is **AAudio** from Chapter 15: a stream is created with
`AAudio_createStreamBuilder`
(`frameworks/av/media/libaaudio/include/aaudio/AAudio.h:1161`), configured and
opened, and fed with `AAudioStream_write`, after which the frames flow through the
audio HAL to the speaker. (Older or `targetSdk`-constrained builds may use
`AudioTrack` or OpenSL ES instead, but AAudio is the modern low-latency path.) The
audio chain therefore ends in exactly the same AOSP subsystem any native Android
game's audio ends in.

### 64.8.5 Latency

The cost of routing audio through a guest API, a socket, and a server is latency.
The stack tunes for it: PulseAudio is configured with a deliberately large buffer
(the containers set a `PULSE_LATENCY_MSEC` on the order of a hundred-odd
milliseconds) to trade responsiveness for glitch-free playback under the jitter
that emulation and IPC introduce. It is a pragmatic choice; perfectly tight audio
latency is not achievable through this many layers, but for most games steady
playback matters more than a few tens of milliseconds of lag.

---

## 64.9 Putting It Together: Tracing Three Paths

The clearest way to consolidate the whole chapter is to follow three different
operations from the game down to the Android platform and notice how each one
takes a different route through the layers.

#### Diagram: three operations, three routes through the stack

```mermaid
graph TD
    subgraph G["Windows game (emulated x86-64)"]
        D3D["D3D11 draw call"]
        FILE["CreateFile call"]
        SND["WASAPI write"]
    end
    D3D -->|"native ARM64"| DXVKn["DXVK to Vulkan"] --> GPUn["Vortek / Turnip to Adreno"]
    FILE -->|"NT syscall"| NTDLL["ntdll syscall dispatcher"] --> WS["wineserver + Linux fd"]
    SND -->|"native ARM64"| PULSEn["winepulse to PulseAudio"] --> AAUDIOn["AAudio"]
```

1. **A Direct3D 11 draw call.** The game's `ID3D11DeviceContext::Draw` is an
   x86-64 call (emulated). It enters DXVK, which on ARM64EC is native and builds
   a Vulkan command buffer, then crosses the libc boundary by thunk (Turnip) or
   socket (Vortek) to the Adreno driver, and the result is composited by
   SurfaceFlinger. Almost none of this is emulated; only the original call site
   is.

2. **A `CreateFile` call.** The game asks to open a file. This is a Windows API
   call that becomes an NT system call, funnelled through Wine's
   `__wine_syscall_dispatcher` into `ntdll.so`, which asks wineserver to
   translate the Windows path and hand back a real Linux file descriptor over the
   socket. PRoot or `libredirect` then remaps the path into the rootfs, and the
   Linux `openat` finally lands in the app's private storage. No GPU, no audio,
   entirely different machinery from path 1.

3. **An audio buffer write.** The game's WASAPI write enters `winepulse.drv`
   (native on ARM64EC), which ships the PCM over the PulseAudio socket to the
   in-app server, which writes it into an AAudio stream that reaches the speaker.

Three operations, three completely different paths, and only the parts drawn
inside the emulated box are actually translated instruction by instruction. The
entire art of the stack is keeping that box small.

---

## 64.10 Try It

These exercises use a checkout of the GameNative source and a device or emulator
with a Winlator-class app installed. The source reading requires nothing but a
clone; the on-device steps assume you have legally installed such an app and a
game you own.

1. **Read the stack off the defaults.** Clone GameNative and open
   `app/src/main/java/com/winlator/container/Container.java` and
   `app/src/main/java/com/winlator/core/DefaultVersion.java`. Write down the
   default emulator, graphics driver, audio driver, DX wrapper, and the pinned
   versions of Wine, DXVK, VKD3D, and Turnip. You have just reconstructed the
   entire default pipeline from two files.

2. **Find the launch command.** Read
   `app/src/main/java/com/winlator/xenvironment/components/GuestProgramLauncherComponent.java`
   and locate where it assembles the `box64 <guest exe>` command, then read
   `BionicProgramLauncherComponent.java` and find where it branches on whether the
   Wine build is ARM64EC. Compare the two launch paths.

3. **Inspect the bundled components.** List `app/src/main/assets/` and identify
   the `.tzst`/`.txz` archives for FEX, Box64, DXVK, and the Vulkan drivers, and
   the `*_download.json` manifests that fetch the rest on demand. Note which
   pieces are in the APK and which are downloaded.

4. **Watch the processes on device.** With the app running a game, use
   `adb shell ps -A` and look for the Wine, wineserver, PulseAudio, and X server
   processes living under the app's UID. Then `adb shell cat /proc/<pid>/maps`
   for the Wine process and observe both the JIT's anonymous executable mappings
   and the rootfs libraries.

5. **See the sockets.** Run `adb shell ls -l /proc/<pid>/fd` on the Wine process
   and find the Unix-domain sockets connecting it to wineserver, the Vulkan
   renderer, and PulseAudio. These are the boundary crossings of 64.4.5 made
   visible.

6. **Explore the prefix.** Locate the container's Wine prefix under the app's
   data directory and examine `drive_c/windows/system32` for the DXVK DLLs that
   overrode Wine's builtin Direct3D, and `user.reg` for the
   `Software\Wine\DllOverrides` entries that put them there.

7. **Confirm the AOSP touchpoints.** In an AOSP checkout, open
   `frameworks/native/vulkan/libvulkan/driver.cpp` at the `LoadDriver` function
   (line 157) and confirm the driver is opened through `android_dlopen_ext` with
   a namespace; this is the public interface the whole graphics stack ultimately
   funnels into.

---

## 64.11 Summary

Running a Windows game on an unrooted ARM Android phone is a stack of
single-purpose translation layers, each bridging one gap between a Windows x86-64
game and the AOSP internals covered in the rest of this book.

| Layer | Problem it solves | Key technology |
|-------|-------------------|----------------|
| GameNative app | orchestration, storefronts, packaging | Pluvia + Winlator graft, GPL-3.0 |
| rootfs (imagefs) | a glibc Linux userland with no root | Ubuntu tree extracted to app storage, entered via PRoot or a bionic loader |
| bionic redirections | glibc software on a `bionic` system | path rewriting, SysV-SHM-over-ashmem, IPC servers |
| FEX / Box64 | x86-64 instructions on AArch64 | dynarec, TSO emulation, thunks vs wrapped libs |
| ARM64EC / WoW64 | emulate only the game | native ARM64 Wine, emulator as a DLL |
| Wine | the Windows API on Linux | PE/Unix split, wineserver, DLL overrides |
| DXVK / VKD3D | Direct3D on a Vulkan GPU | D3D to Vulkan, installed as native DLL overrides |
| Turnip / Vortek | Vulkan to the real Adreno GPU | Mesa driver via thunk, or client/server over a socket |
| PulseAudio | Windows audio to the speaker | in-app audio server, out via AAudio |

The recurring lessons:

1. **Two orthogonal translations.** Instruction-set translation (FEX/Box64) and
   Windows-API translation (Wine) are entirely separate problems; conflating them
   is the most common misunderstanding of how these apps work.

2. **Emulate as little as possible.** Every performance gain in the stack comes
   from moving work out of the emulated box: thunks and wrappers for the GPU
   driver, native ARM64 DXVK, and above all ARM64EC, which leaves only the game's
   own code emulated.

3. **The libc boundary is the hard part.** glibc and `bionic` cannot share a
   process, and the three ways across it (IPC, ABI thunking, or running native on
   `bionic`) shape every design decision in the stack.

4. **It is all standard AOSP underneath.** The Vulkan loader, `ANativeWindow`,
   `AHardwareBuffer`, AAudio, linker namespaces, `ASharedMemory`, and the W^X
   rules are the same platform interfaces any Android app uses. The translation
   stack invents nothing at the bottom; its genius is reaching those public
   interfaces from a Windows game many layers above.

### Key Source Files Reference

| File | Purpose |
|------|---------|
| `bionic/libc/include/android/dlext.h:115` | `ANDROID_DLEXT_USE_NAMESPACE`, loads a driver into a chosen linker namespace |
| `bionic/libc/include/android/dlext.h:80` | `ANDROID_DLEXT_USE_LIBRARY_FD`, loads a library from an fd |
| `bionic/linker/linker_phdr.cpp:1058` | rejects ELF segments that are both writable and executable (W^X) |
| `bionic/libc/include/sys/mman.h:183` | `memfd_create`, backing for anonymous shared memory |
| `frameworks/native/include/android/sharedmem.h:78` | `ASharedMemory_create`, host side of the SysV-SHM redirection |
| `frameworks/native/vulkan/libvulkan/driver.cpp:157` | `LoadDriver`, discovers and opens the device Vulkan driver |
| `frameworks/native/libs/nativewindow/include/android/native_window.h:179` | `ANativeWindow_lock`, CPU presentation path |
| `frameworks/native/libs/nativewindow/include/android/native_window.h:188` | `ANativeWindow_unlockAndPost`, posts a frame to the compositor |
| `frameworks/native/libs/nativewindow/include/android/hardware_buffer.h:479` | `AHardwareBuffer_allocate`, zero-copy GPU presentation buffer |
| `frameworks/av/media/libaaudio/include/aaudio/AAudio.h:1161` | `AAudio_createStreamBuilder`, the audio path's Android sink |

