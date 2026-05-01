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

## Mermaid: "No diagram type detected matching given configuration for text"

This specific error comes from `getDiagramFromText()` in Mermaid v11: the parser walks the registered diagram-type detectors and none of them match the first significant line of the block. It is *not* a syntax error inside a known diagram type — it means Mermaid never figured out *which* diagram you're declaring. Symptom on the live site: the diagram renders as a `<pre>Diagram render error: …</pre>` banner instead of an SVG.

Triggers we have seen (each is its own footgun):

1. **Block opens with a `%%` comment or `%%{init: …}%%` directive only.** The detector skips the directive line, then looks at the next line — if that next line is a blank line or another comment, detection runs out of input and throws. Always put a recognized type keyword (`graph`, `flowchart`, `sequenceDiagram`, `stateDiagram-v2`, `classDiagram`, `erDiagram`, `pie`, `gitGraph`, `journey`, `mindmap`, `timeline`, `quadrantChart`, `block-beta`, `xychart-beta`, …) on the next non-comment line, immediately after the directive.
2. **Misspelled or wrong-cased type keyword.** `Sequencediagram`, `state-diagram`, `flowChart-TB`, `Graph TB` (capital G) all detect as no-type. Type keywords are case-sensitive: `graph`, `flowchart`, `sequenceDiagram`, `stateDiagram-v2` (with the `-v2`), `classDiagram`, `erDiagram`.
3. **Markdown-style frontmatter (`---\ntitle: X\n---`) malformed or unterminated.** Mermaid v11 supports a YAML frontmatter prologue but only when the opening and closing `---` lines are exact and the type keyword follows. If the closing `---` is missing or there is text between `---` and the type, detection fails on whatever Mermaid parses next.
4. **Block fence accidentally opened twice / closed inside the diagram.** Editors sometimes paste content that contains a stray ```` ``` ```` line; the outer fence closes early and the second half becomes a new fence whose first line isn't a diagram type. Search for ` ``` ` inside the diagram body when this error appears.
5. **Empty or whitespace-only block.** ```` ```mermaid\n``` ```` with no content. Easy to introduce when stripping a malformed diagram and forgetting to delete the fence.

How to find any future occurrence: `./serve.sh png --all` (or `./serve.sh png NN-slug.md` for a single chapter) reports `errors=N` for every block whose SVG was missing from `.mermaid-cache/` after the renderer ran — that is exactly what happens when Mermaid throws a "No diagram type detected" error, because `renderer.py`'s exception handler skips writing the SVG. The error line names `<chapter>.md block #<index> (<hash>)`, which is enough to locate the offending fence.

## CI

GitHub Actions runs `mkdocs build` on push/PR (~2 min).

## Commit Rules

Do not add a `Co-Authored-By` trailer when creating commits. Commits should
have a plain author and no AI/tool attribution footer.

## Skills

- `.claude/skills/book-writer/SKILL.md` — chapter structure, content guidelines, Mermaid syntax
  - `references/mermaid-syntax.md` — detailed quoting rules and common parse errors
