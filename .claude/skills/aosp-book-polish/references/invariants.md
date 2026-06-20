# Hard invariants & book conventions

These come from `book/CLAUDE.md` and `.claude/skills/book-writer/SKILL.md`. They
are the guardrails that let autonomous rewrites stay safe. Read this before
editing any chapter; re-read CLAUDE.md if anything here is ambiguous — CLAUDE.md
is the source of truth.

## Chapter identity (immutable)

- Filename `NN-slug.md` and the `# Chapter N: Title` line (number AND title)
  never change. Titles use a colon only — never `--` or `—`.
- Only body content changes: verify/correct existing prose, append new sections.

## Section structure

- Manual section numbers: `## N.1`, `### N.1.2`, matching the chapter number.
- **No duplicate full section numbers** within a chapter (watch this when
  inserting new sections — renumber the tail and any "Try It"/"Summary" headings
  to keep numbering monotonic).
- The body ends with **"Try It"** then **"Summary"** — nothing after Summary
  **except** an optional final "Key Source Files Reference" (or similarly-titled
  key-file table). Appendices/deep-dives/extras must fold into a numbered section
  above "Try It", not trail after Summary.
- **No epigraph blockquotes** under the title — the chapter goes straight into
  its intro paragraph after the `# Chapter N: Title` line.
- New feature content for the new version goes in new numbered section(s)
  appended **before** "Try It".
- Front matter (`00-frontmatter.md`) and the introduction (`01-introduction.md`)
  have no Try-It/Summary — preserve their existing terminal structure, do not
  add them. They enumerate the book's structure, so update them LAST (after any
  new chapters/Parts exist).

## Mermaid

- Descriptive heading before every ```mermaid block.
- Quote labels containing `()`, `<br/>`, or `|`.
- No `<br/>` in `participant` lines.
- **No parens in `stateDiagram-v2` transition labels** — `A --> B : foo()`
  breaks parsing; drop the parens.
- After every Mermaid edit, run `./serve.sh png <chapter>` and require
  `errors=0`. CI's `mkdocs build` does NOT validate Mermaid (the site renders it
  client-side), so a parse error ships silently as a "No diagram type detected"
  banner. Treat `errors=0` as a hard precondition.
- Parse-clean is not enough: open the PNGs under `.mermaid-png/<slug>/` and
  check labels fit their shapes, nothing overlaps, and the boxes/arrows match
  the architecture the prose describes (right components, right direction, no
  invented relationships).

## Source citations & privacy

- Every architectural claim cites a real, repo-relative AOSP path that exists in
  the new tree (e.g. `frameworks/base/services/...`). Cite line numbers where
  the book already does, but prefer function/symbol anchors over brittle line
  ranges when the tree has drifted.
- **Never** write a local absolute or home-relative path (`/home/...`,
  `/Users/...`, `~/...`) or a username into chapter text — cite repo-relative
  AOSP paths only. The AOSP source root is supplied to the skill as a parameter;
  refer to it via that parameter (or a placeholder), never hardcode it. In shell
  examples use repo-relative paths or the supplied parameter.
- Tables: a raw `|` inside a backticked code span is correct; do NOT write `\|`
  (the escape leaks visibly). Spell out terms the project insists on spelling
  out (e.g. "Computer Control", never "CC") in prose — Mermaid node *ids* like
  `CC[...]` are fine since the rendered label is what readers see.

## Backups

- Before rewriting a chapter, copy it to
  `.superpowers/book-polish/backups/<slug>.bak.md` — once, never overwriting an
  existing `.bak`. This is the diff base and the restore point if a rewrite is
  judged worse than the original.

## Regeneration coupling (why Phase D exists)

- The 16+ Part-skills under `agents/<claude|gemini|codex|copilot>/` are generated
  from the root chapters by `agents/build.py`. ANY chapter content change stales
  them — regenerate and let `build.py --check` pass (CI enforces it). See
  `references/bookkeeping.md`.
