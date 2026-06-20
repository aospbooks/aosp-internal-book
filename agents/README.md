# AOSP Internals — Coding Agent Plugin

Bundled context for coding agents (Claude Code, Gemini CLI, Codex / AGENTS.md
tools, GitHub Copilot) that gives them offline access to the entire AOSP
Internals book — 67 chapters + 4 appendices, packaged as 16 Part-skills.

The chapter content lives at the repo root (`./00-frontmatter.md` …
`./66-windows-games.md`); the four `agents/<platform>/` directories are
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
| `aosp-getting-started` | I | Getting Started | 1–3 |
| `aosp-kernel-and-boot` | II | Kernel & Boot | 4–6 |
| `aosp-native-foundation` | III | Native Foundation | 7–11 |
| `aosp-native-services-and-media` | IV | Native Services & Media | 12–17 |
| `aosp-runtime` | V | Runtime | 18–19 |
| `aosp-framework-core` | VI | Framework Core | 20–25 |
| `aosp-framework-services` | VII | Framework Services | 26–34 |
| `aosp-connectivity` | VIII | Connectivity | 35–39 |
| `aosp-security` | IX | Security | 40–43 |
| `aosp-ui-framework` | X | UI Framework | 44–47 |
| `aosp-system-apps` | XI | System Apps | 48–50 |
| `aosp-ai-and-devices` | XII | AI & Devices | 51–53 |
| `aosp-infrastructure` | XIII | Infrastructure | 54–58 |
| `aosp-device-support` | XIV | Device Support | 59–64 |
| `aosp-practical` | XV | Practical | 65–66 |
| `aosp-appendices` | App. | Appendices | A, B, C, D |

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

  * the `name:` field is forced to `aosp-<slug>`;
  * `metadata.author` defaults to `utzcoz` when missing;
  * `metadata.last-updated` is bumped to today's date.

The `--check` mode used by CI is read-only and passes metadata through
verbatim, so verification stays deterministic across days.

See `agents/SPEC.md` for the full design and `agents/PLAN.md` for the
step-by-step implementation history.
