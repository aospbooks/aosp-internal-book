# AOSP Internals

**A Developer's Guide to the Android Open Source Project**

A comprehensive technical book covering the full AOSP stack — from kernel to apps — with every claim referencing real source code file paths and line numbers.

**Read online:** <https://aospbooks.github.io/aosp-internal-book/>

**Using AI?** Point your assistant at <https://aospbooks.github.io/aosp-internal-book/llms.txt> — an [llmstxt.org](https://llmstxt.org/)-style index that lets the model find the right chapter for any AOSP subsystem without crawling the whole site.

> If you spot errors, missing details, or have suggestions, please [open an issue](https://github.com/aospbooks/aosp-internal-book/issues) or submit a pull request — feedback from AOSP developers and enthusiasts is very welcome.

<!-- --8<-- [start:coverage] -->
## What This Book Covers

69 chapters organized bottom-to-top through the Android architecture:

| Part | Ch. | Topics |
|------|-----|--------|
| I | 0 | Frontmatter |
| I | 1 | Introduction |
| I | 2 | Source Code & Build System (Soong/Bazel/Kleaf) |
| I | 3 | Feature Flags (aconfig) |
| II | 4 | Boot and Init |
| II | 5 | Kernel (GKI) |
| II | 6 | System Properties |
| III | 7 | Bionic & Linker |
| III | 8 | Memory Management |
| III | 9 | Binder IPC |
| III | 10 | HAL (HIDL/AIDL) |
| III | 11 | NDK |
| IV | 12 | Native Services |
| IV | 13 | Graphics & Render Pipeline (OpenGL ES/Vulkan/Skia/HWUI) |
| IV | 14 | Animation System |
| IV | 15 | Audio System (Spatial) |
| IV | 16 | Media & Camera |
| IV | 17 | Sensors |
| V | 18 | ART Runtime |
| V | 19 | Native Bridge (Berberis) |
| VI | 20 | system_server |
| VI | 21 | Intent System |
| VI | 22 | Activity & Window Management |
| VI | 23 | Window System |
| VI | 24 | Display System |
| VI | 25 | View System |
| VII | 26 | Package Manager |
| VII | 27 | Content Providers |
| VII | 28 | Notifications |
| VII | 29 | Power Management |
| VII | 30 | Background Tasks |
| VII | 31 | Multi-User |
| VII | 32 | Account & Sync |
| VII | 33 | Location |
| VII | 34 | Storage |
| VIII | 35 | Networking (VCN/Thread) |
| VIII | 36 | Telephony (IMS) |
| VIII | 37 | Bluetooth |
| VIII | 38 | NFC |
| VIII | 39 | USB & ADB |
| IX | 40 | Security (TEE/Trusty) |
| IX | 41 | Credential Manager |
| IX | 42 | DRM |
| IX | 68 | LFI In-Process Sandbox |
| X | 43 | Widgets & RemoteViews (RemoteCompose) |
| X | 44 | WebView |
| X | 45 | Accessibility |
| X | 46 | Internationalization |
| XI | 47 | SystemUI (Monet/Keyguard) |
| XI | 48 | Launcher3 |
| XI | 49 | Settings |
| XII | 50 | AI & AppFunctions (Computer Control) |
| XII | 51 | Companion & Virtual Devices |
| XII | 67 | NPU Manager |
| XIII | 52 | Mainline Modules (APEX) |
| XIII | 53 | OTA Updates |
| XIII | 54 | Virtualization (pKVM/crosvm) |
| XIII | 55 | Testing (CTS/VTS/Ravenwood) |
| XIII | 56 | Debugging Tools (Perfetto) |
| XIV | 57 | Architecture Support (ARM/x86/RISC-V) |
| XIV | 58 | Emulator |
| XIV | 59 | Device Policy |
| XIV | 60 | Automotive/TV/Wear |
| XIV | 61 | Print Services |
| XIV | 62 | Camera2 Pipeline |
| XV | 63 | Custom ROM Guide (step-by-step) |
| XV | 64 | Running Windows Games on Android |
| XVI | 65 | Software Defined Vehicle |
| XVI | 66 | SDV Middleware & Vehicle Communication |
| App. | A | Key Files Reference |
| App. | B | Glossary |
| App. | C | Why Kotlin Isn't on the Public API |
| App. | D | Android 17 Updates |
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

The `pdf` command stops any running server, then builds all 69 chapters into a
single PDF with rendered Mermaid diagrams (takes a while — uses Playwright/Chromium).

The `epub` command works the same way, producing an EPUB3 file with rendered
Mermaid diagrams suitable for Apple Books, Google Play Books, and other readers.

### Without Docker

```bash
# Install (one-time)
pip install mkdocs-material pymdown-extensions

# Create symlinks (one-time)
mkdir -p docs
for f in [0-9]*.md [A-Z]-*.md index.md; do ln -sf "../$f" "docs/$f"; done

# Start
mkdocs serve                       # http://127.0.0.1:8000

# Build static site
mkdocs build                       # output in site/
```

Open **http://localhost:8000** — chapters in the sidebar, Mermaid renders live, hot-reload on edits.

## AOSP Manifest Snapshots

A companion tool captures point-in-time, fully-pinned `repo manifest` snapshots of the AOSP source tree and diffs two of them into four branch-named files: a Markdown navigator, a kernel-changelog of per-repository commits, an added/removed-projects file with full history, and an LLM analysis prompt. Shallow (`clone-depth`) and ignore-globbed projects are skipped. Useful for "what changed between two AOSP releases."

```bash
# Take a snapshot (resolves every <project> to a HEAD SHA, prompts for label/notes)
python3 tools/manifest_snapshot.py snap --aosp-root /path/to/aosp

# Compare two snapshots → manifest-snapshots/_compare/<oldrev>-to-<newrev>/{report.md,changes.txt,added-removed.txt,analysis-prompt.txt}
python3 tools/manifest_snapshot.py compare \
    manifest-snapshots/<branch>/<date-A> \
    manifest-snapshots/<branch>/<date-B> \
    --aosp-root /path/to/aosp
```

The tool is read-only against `.repo/` — it never writes inside the AOSP checkout. See [`manifest-snapshots/README.md`](manifest-snapshots/README.md) for the full guide, flag reference, and the read-only guarantee.

## GitHub Actions

Tests `mkdocs build` on push to `main` and PRs (~2 min).

## Project Structure

```
[0-9]*.md                  69 chapter files
[A-D]-appendix-*.md        4 appendix files
index.md                   Website homepage
mkdocs.yml                 MkDocs config (Material theme + Mermaid)
docs/                      Symlinks for MkDocs (gitignored)
mkdocs-mermaid-renderer/   Shared Mermaid SVG renderer (Playwright + cache)
mkdocs-pdf-generate/       MkDocs plugin: PDF export
mkdocs-epub-generate/      MkDocs plugin: EPUB export
Dockerfile                 python:3.12-slim + Playwright + MkDocs plugins
docker-compose.yml         serve / build-site / build-pdf / build-epub
tools/                     Helper scripts (manifest_snapshot.py + tests)
manifest-snapshots/        Pinned AOSP manifests by branch/date + comparison reports
CLAUDE.md                  Project rules for AI agents
.claude/skills/            book-writer
.github/workflows/         CI: mkdocs build test
```

## License

This project is licensed under the [Apache License 2.0](LICENSE), matching the license of the Android Open Source Project it analyzes.
