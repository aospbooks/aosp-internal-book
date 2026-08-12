# AOSP Internals Book

65 chapters + 3 appendices, ~227,000 lines, ~1,500 Mermaid diagrams.

## Quick Start

```bash
docker compose build
docker compose up -d serve         # http://localhost:8000
```

## Writing Rules

1. Chapters: `NN-slug.md`, titles: `# Chapter N: Title` — colon only, never `--` or `—`
2. Section numbers: manual `## N.1`, `### N.1.2` matching filename
3. No duplicate section numbers within a chapter (watch for this when inserting new sections)
4. Mermaid: quote labels with `()`, `<br/>`, `|`; no `<br/>` in `participant` lines; **no parens in `stateDiagram-v2` transition labels** (`State1 --> State2 : foo()` breaks parsing — drop the parens)
5. Descriptive heading before each mermaid block
6. Source refs: real AOSP paths with line numbers
7. The body of every chapter ends with "Try It" then "Summary" — nothing else comes after Summary, **except** an optional final "Key Source Files Reference" (or similarly-titled key-file-paths) table, which may sit after Summary as a final reference. Appendices, extras, deep dives, etc. still must move above Try It / fold into a numbered section.
8. **Do not add epigraph blockquotes at the top of chapters.** No `> *"quote"*` / `> -- Author` blocks between the `# Chapter N: Title` line and the first `## N.1` section. The chapter goes straight into its introductory paragraph after the title. (We removed all of these in a cleanup pass; do not re-introduce them when editing or writing new chapters.)
9. **Verify mermaid format parses after every edit.** Run `./serve.sh png NN-slug.md` on every chapter whose Mermaid blocks you touched and confirm the output reports `errors=0`. The CI `properdocs build` does NOT validate Mermaid (the live site renders it client-side in the browser), so a parse error reaches readers as a "No diagram type detected" / "Syntax error" banner with no build-time signal. Treat `errors=0` as a hard precondition — do not declare the edit done, commit, or move to visual review until the format check is clean. If `errors>0`, fix the offending block (the script names which file/index failed) and re-run until clean.
10. **Visually verify mermaid diagrams after writing or editing them.** Parse-clean is not enough — diagrams can render with text overflowing rectangles, overlapping nodes, or unreadable arrows, and they can also be parse-clean but factually wrong about the architecture. After rule 9 passes, inspect each PNG under `.mermaid-png/<slug>/`. Check: (a) every label fits inside its shape with no overflow; (b) no nodes or edge labels overlap; (c) the boxes, arrows, and grouping match the architecture the prose describes (right components, right direction of arrows, no missing or invented relationships). Re-render after every mermaid edit.
11. **Keep `llms.txt` in sync with chapter content.** `llms.txt` (root of repo, symlinked into `docs/`) is the [llmstxt.org](https://llmstxt.org/)-style index that AI tools fetch to learn what's in this book and where to find each subsystem. Update it when chapters are **added, removed, renamed, or significantly retitled**, and when a chapter's scope changes enough that its one-line description no longer fits. Each chapter entry has the form `- [Chapter N: Title](https://aospbooks.github.io/aosp-internal-book/<slug>/): one-line description of what the chapter covers and the key components it walks through`. Do *not* update `llms.txt` for routine edits inside a chapter (typo fixes, mermaid tweaks, prose rewrites that don't change the chapter's scope). When editing, also confirm every URL still resolves to a real `<slug>.md` in the repo root.
12. **Re-run `python3 agents/build.py` after any change to chapter content.** The 16 Part-skills under `agents/<claude|gemini|codex|copilot>/` are generated from chapters at the repo root, so any chapter edit can stale them. Always regenerate after a chapter edit — including prose tweaks, typo fixes, and mermaid changes, not just headings or structural edits — and commit the regenerated files if the regeneration produces a diff. The CI `agents/build.py --check` step in `build-test.yml` will fail if they're stale. See `agents/SPEC.md` for the full design.
13. **Update `agents/README.md` (and the top-level `README.md`) when chapters are added, removed, renamed, or reordered.** `agents/build.py` regenerates the per-platform Part-skill *content* but does not touch either README. When the chapter set changes, hand-edit (a) `agents/README.md` — both the `64 chapters + 2 appendices` count near the top, the example chapter range (`./00-frontmatter.md` … `./63-custom-rom.md`), and the per-Part chapter listing in the "What's in each Part" table — and (b) the top-level `README.md` chapter table under "What This Book Covers" plus the chapter count in surrounding prose. If the new/renamed chapter changes which Part it belongs to, also edit `agents/_content/manifest.toml` before regenerating.

## CI

GitHub Actions runs `properdocs build` on push/PR (~2 min). The site is built
with ProperDocs (a MkDocs fork) and the Material theme; its config lives in
`properdocs.yml`.

## Commit Rules

Do not add a `Co-Authored-By` trailer when creating commits. Commits should
have a plain author and no AI/tool attribution footer.

## Skills

- `.claude/skills/book-writer/SKILL.md` — chapter structure, content guidelines, Mermaid syntax
  - `references/mermaid-syntax.md` — detailed quoting rules and common parse errors
