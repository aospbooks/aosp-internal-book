# AOSP Internals — Coding Agent Plugin

Bundled context for coding agents (Claude Code, Gemini CLI, Codex / AGENTS.md
tools, GitHub Copilot) that gives them offline access to the entire AOSP
Internals book — 64 chapters + 3 appendices, packaged as 16 Part-skills.

The chapter content lives at the repo root (`./00-frontmatter.md` …
`./63-custom-rom.md`); the four `agents/<platform>/` directories are
generated from one canonical source by `agents/build.py`.

## Install

### Claude Code

Either install the directory as a project plugin:

    git clone https://github.com/aospbooks/aosp-internal-book.git ~/aosp-internals-src
    mkdir -p .claude/plugins
    ln -s ~/aosp-internals-src/agents/claude .claude/plugins/aosp-internals

…or copy the 16 skills directly into your project's `.claude/skills/`:

    cp -r ~/aosp-internals-src/agents/claude/skills/* .claude/skills/

### Gemini CLI

    cp -r agents/gemini ~/.gemini/extensions/aosp-internals

### Codex / AGENTS.md-aware tools

Drop the `AGENTS.md` and the per-Part content into your project root:

    cp agents/codex/AGENTS.md ./AGENTS.md
    cp -r agents/codex/parts ./.aosp-internals-parts

(Adjust the path inside `AGENTS.md` if you pick a different target dir.)

### GitHub Copilot

Copy the `.github/` tree into your project root:

    cp -r agents/copilot/.github/* .github/

## What's in each Part

| Skill | Part | Title | Chapters |
|-------|------|-------|----------|
| `aosp-part-getting-started` | I | Getting Started | 0–3 |
| `aosp-part-kernel-and-boot` | II | Kernel & Boot | 4–6 |
| `aosp-part-native-foundation` | III | Native Foundation | 7–11 |
| `aosp-part-native-services-and-media` | IV | Native Services & Media | 12–17 |
| `aosp-part-runtime` | V | Runtime | 18–19 |
| `aosp-part-framework-core` | VI | Framework Core | 20–25 |
| `aosp-part-framework-services` | VII | Framework Services | 26–34 |
| `aosp-part-connectivity` | VIII | Connectivity | 35–39 |
| `aosp-part-security` | IX | Security | 40–42 |
| `aosp-part-ui-framework` | X | UI Framework | 43–46 |
| `aosp-part-system-apps` | XI | System Apps | 47–49 |
| `aosp-part-ai-and-devices` | XII | AI & Devices | 50–51 |
| `aosp-part-infrastructure` | XIII | Infrastructure | 52–56 |
| `aosp-part-device-support` | XIV | Device Support | 57–62 |
| `aosp-part-practical` | XV | Practical | 63 |
| `aosp-part-appendices` | App. | Appendices | A, B, C |

## Maintenance (for contributors to this repo)

The four `agents/<platform>/` directories are generated. If you edit a
chapter at the repo root in a way that changes its scope, structure, or
heading, regenerate them:

    python3 agents/build.py
    git add agents/claude agents/gemini agents/codex agents/copilot
    git commit -m "agents: regenerate after <chapter> edits"

CI runs `agents/build.py --check` on every push and PR; a stale
`agents/<platform>/` tree fails the build.

If you change which Part owns which chapter (or rename a chapter), edit
`agents/_content/manifest.toml` first, then regenerate.

If you add a new Part or significantly retitle one, edit the corresponding
`agents/_content/parts/<slug>/SKILL.md` (or create a new one), update
`manifest.toml`, then regenerate. `agents/build.py` enforces a few
invariants on the source SKILL.md and rewrites the file in place if any
drift:

  * the `name:` field is forced to `aosp-part-<slug>`;
  * `metadata.author` defaults to `utzcoz` when missing;
  * `metadata.last-updated` is bumped to today's date.

The `--check` mode used by CI is read-only and passes metadata through
verbatim, so verification stays deterministic across days.

See `agents/SPEC.md` for the full design and `agents/PLAN.md` for the
step-by-step implementation history.
