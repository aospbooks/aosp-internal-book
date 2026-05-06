# AOSP Internals

**A Developer's Guide to the Android Open Source Project**

A comprehensive technical book covering the full AOSP stack — from kernel to apps — with every claim referencing real source code file paths and line numbers.

**Read online:** <https://aospbooks.github.io/aosp-internal-book/>

> **Status: Under Review**
> All chapters are currently being reviewed for technical accuracy, completeness, and clarity. Content may change. If you spot errors, missing details, or have suggestions, please [open an issue](https://github.com/nicewook/aosp-knowledge/issues) or submit a pull request — feedback from AOSP developers and enthusiasts is very welcome.

<!-- --8<-- [start:coverage] -->
## What This Book Covers

64 chapters organized bottom-to-top through the Android architecture:

| Part | Ch. | Topics | Status |
|------|-----|--------|--------|
| I | 0 | Frontmatter | REVIEWED |
| I | 1 | Introduction | REVIEWED |
| I | 2 | Source Code & Build System (Soong/Bazel/Kleaf) | REVIEWED |
| I | 3 | Feature Flags (aconfig) | REVIEWED |
| II | 4 | Boot and Init | REVIEWED |
| II | 5 | Kernel (GKI) | REVIEWED |
| II | 6 | System Properties | REVIEWED |
| III | 7 | Bionic & Linker | REVIEWED |
| III | 8 | Memory Management | REVIEWED |
| III | 9 | Binder IPC | REVIEWED |
| III | 10 | HAL (HIDL/AIDL) | REVIEWED |
| III | 11 | NDK | REVIEWED |
| IV | 12 | Native Services | REVIEWED |
| IV | 13 | Graphics & Render Pipeline (OpenGL ES/Vulkan/Skia/HWUI) | REVIEWED |
| IV | 14 | Animation System | REVIEWED |
| IV | 15 | Audio System (Spatial) | REVIEWED |
| IV | 16 | Media & Camera | UNDER REVIEW |
| IV | 17 | Sensors | UNDER REVIEW |
| V | 18 | ART Runtime | UNDER REVIEW |
| V | 19 | Native Bridge (Berberis) | UNDER REVIEW |
| VI | 20 | system_server | UNDER REVIEW |
| VI | 21 | Intent System | UNDER REVIEW |
| VI | 22 | Activity & Window Management | UNDER REVIEW |
| VI | 23 | Window System | UNDER REVIEW |
| VI | 24 | Display System | UNDER REVIEW |
| VI | 25 | View System | UNDER REVIEW |
| VII | 26 | Package Manager | UNDER REVIEW |
| VII | 27 | Content Providers | UNDER REVIEW |
| VII | 28 | Notifications | UNDER REVIEW |
| VII | 29 | Power Management | UNDER REVIEW |
| VII | 30 | Background Tasks | UNDER REVIEW |
| VII | 31 | Multi-User | UNDER REVIEW |
| VII | 32 | Account & Sync | UNDER REVIEW |
| VII | 33 | Location | UNDER REVIEW |
| VII | 34 | Storage | UNDER REVIEW |
| VIII | 35 | Networking (VCN/Thread) | UNDER REVIEW |
| VIII | 36 | Telephony (IMS) | UNDER REVIEW |
| VIII | 37 | Bluetooth | UNDER REVIEW |
| VIII | 38 | NFC | UNDER REVIEW |
| VIII | 39 | USB & ADB | UNDER REVIEW |
| IX | 40 | Security (TEE/Trusty) | UNDER REVIEW |
| IX | 41 | Credential Manager | UNDER REVIEW |
| IX | 42 | DRM | UNDER REVIEW |
| X | 43 | Widgets & RemoteViews (RemoteCompose) | REVIEWED |
| X | 44 | WebView | REVIEWED |
| X | 45 | Accessibility | REVIEWED |
| X | 46 | Internationalization | REVIEWED |
| XI | 47 | SystemUI (Monet/Keyguard) | REVIEWED |
| XI | 48 | Launcher3 | REVIEWED |
| XI | 49 | Settings | REVIEWED |
| XII | 50 | AI & AppFunctions (Computer Control) | REVIEWED |
| XII | 51 | Companion & Virtual Devices | REVIEWED |
| XIII | 52 | Mainline Modules (APEX) | UNDER REVIEW |
| XIII | 53 | OTA Updates | REVIEWED |
| XIII | 54 | Virtualization (pKVM/crosvm) | REVIEWED |
| XIII | 55 | Testing (CTS/VTS/Ravenwood) | REVIEWED |
| XIII | 56 | Debugging Tools (Perfetto) | REVIEWED |
| XIV | 57 | Architecture Support (ARM/x86/RISC-V) | REVIEWED |
| XIV | 58 | Emulator | REVIEWED |
| XIV | 59 | Device Policy | REVIEWED |
| XIV | 60 | Automotive/TV/Wear | REVIEWED |
| XIV | 61 | Print Services | REVIEWED |
| XIV | 62 | Camera2 Pipeline | REVIEWED |
| XV | 63 | Custom ROM Guide (step-by-step) | REVIEWED |
| App. | A | Key Files Reference | UNDER REVIEW |
| App. | B | Glossary | UNDER REVIEW |
<!-- --8<-- [end:coverage] -->

## How to Give Feedback

- **Found an error?** Open an issue describing the chapter, section, and what's wrong.
- **Have a suggestion?** Pull requests are welcome — even small fixes like typos or broken source paths.
- **Know a topic deeply?** We especially value feedback from engineers who work on specific AOSP subsystems.

## Quick Start

### Docker

```bash
./serve.sh           # start (http://localhost:8000)
./serve.sh off       # stop
./serve.sh status    # check if running
./serve.sh pdf       # build PDF → site/aosp-internals.pdf
./serve.sh epub      # build EPUB → site/aosp-internals.epub
```

The `pdf` command stops any running server, then builds all 64 chapters into a
single PDF with rendered Mermaid diagrams (takes a while — uses Playwright/Chromium).

The `epub` command works the same way, producing an EPUB3 file with rendered
Mermaid diagrams suitable for Apple Books, Google Play Books, and other readers.

### Without Docker

```bash
# Install (one-time)
pip install mkdocs-material pymdown-extensions

# Create symlinks (one-time)
mkdir -p docs
for f in [0-9]*.md A-*.md B-*.md index.md; do ln -sf "../$f" "docs/$f"; done

# Start
mkdocs serve                       # http://127.0.0.1:8000

# Build static site
mkdocs build                       # output in site/
```

Open **http://localhost:8000** — chapters in the sidebar, Mermaid renders live, hot-reload on edits.

## GitHub Actions

Tests `mkdocs build` on push to `main` and PRs (~2 min).

## Project Structure

```
[0-9]*.md                  64 chapter files
A-appendix-key-files.md    Appendix A
B-appendix-glossary.md     Appendix B
index.md                   Website homepage
mkdocs.yml                 MkDocs config (Material theme + Mermaid)
docs/                      Symlinks for MkDocs (gitignored)
mkdocs-mermaid-renderer/   Shared Mermaid SVG renderer (Playwright + cache)
mkdocs-pdf-generate/       MkDocs plugin: PDF export
mkdocs-epub-generate/      MkDocs plugin: EPUB export
Dockerfile                 python:3.12-slim + Playwright + MkDocs plugins
docker-compose.yml         serve / build-site / build-pdf / build-epub
CLAUDE.md                  Project rules for AI agents
.claude/skills/            book-writer
.github/workflows/         CI: mkdocs build test
```

## License

This project is licensed under the [Apache License 2.0](LICENSE), matching the license of the Android Open Source Project it analyzes.
