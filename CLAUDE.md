# AOSP Internals Book

64 chapters + 2 appendices, ~227,000 lines, ~1,500 Mermaid diagrams.

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
7. Last two `##` sections of every chapter are "Try It" then "Summary" — nothing comes after Summary, even appendices or extras (move them above, or fold into a numbered section)
8. **Verify mermaid format parses after every edit.** Run `./serve.sh png NN-slug.md` on every chapter whose Mermaid blocks you touched and confirm the output reports `errors=0`. The CI `mkdocs build` does NOT validate Mermaid (the live site renders it client-side in the browser), so a parse error reaches readers as a "No diagram type detected" / "Syntax error" banner with no build-time signal. Treat `errors=0` as a hard precondition — do not declare the edit done, commit, or move to visual review until the format check is clean. If `errors>0`, fix the offending block (the script names which file/index failed) and re-run until clean.
9. **Visually verify mermaid diagrams after writing or editing them.** Parse-clean is not enough — diagrams can render with text overflowing rectangles, overlapping nodes, or unreadable arrows, and they can also be parse-clean but factually wrong about the architecture. After rule 8 passes, inspect each PNG under `.mermaid-png/<slug>/`. Check: (a) every label fits inside its shape with no overflow; (b) no nodes or edge labels overlap; (c) the boxes, arrows, and grouping match the architecture the prose describes (right components, right direction of arrows, no missing or invented relationships). Re-render after every mermaid edit.

## CI

GitHub Actions runs `mkdocs build` on push/PR (~2 min).

## Commit Rules

Do not add a `Co-Authored-By` trailer when creating commits. Commits should
have a plain author and no AI/tool attribution footer.

## Skills

- `.claude/skills/book-writer/SKILL.md` — chapter structure, content guidelines, Mermaid syntax
  - `references/mermaid-syntax.md` — detailed quoting rules and common parse errors
