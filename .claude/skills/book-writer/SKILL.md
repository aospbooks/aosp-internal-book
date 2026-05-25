---
name: book-writer
description: Patterns for writing technical book chapters in Markdown with Mermaid diagrams, served via MkDocs. Use this skill whenever writing, editing, reviewing, adding, removing, or renaming book chapters, organizing multi-chapter content, fixing Mermaid rendering issues, or changing the book's structure. Also triggers when updating mkdocs.yml, docs/ symlinks, or navigation — even if the user just says "add a chapter" or "reorganize sections" without mentioning MkDocs.
metadata:
  author: 'utzcoz'
  last-updated: '2026-05-25'
---

# Book Writer

Write source-code-referenced technical books in Markdown with Mermaid diagrams, served as a MkDocs website. Covers chapter structure, content flow, diagram syntax, and keeping the MkDocs site in sync with content changes.

## MkDocs Site Maintenance

The book is served via MkDocs Material. When chapter content changes, the site configuration must stay in sync. Forgetting this breaks navigation or hides new chapters from readers.

### When you add a new chapter

1. Create `NN-slug.md` with the chapter template below
2. Add a nav entry to `mkdocs.yml` in the correct Part section:
   ```yaml
   - "N. Chapter Title": NN-slug.md
   ```
3. Create a symlink in `docs/`:
   ```bash
   ln -sf "../NN-slug.md" "docs/NN-slug.md"
   ```
4. Add a chapter entry to `llms.txt` in the correct Part section, in chapter order:
   ```markdown
   - [Chapter N: Title](https://aospbooks.github.io/aosp-internal-book/NN-slug/): one-line description of what the chapter covers
   ```
5. If the chapter number changes existing chapters, renumber the affected `mkdocs.yml` entries and `llms.txt` URLs too
6. Add the new chapter slug to `agents/_content/manifest.toml` under the right Part (and create a new Part entry there + `agents/_content/parts/<slug>/SKILL.md` if the chapter belongs to a brand-new Part), then run `python3 agents/build.py` and commit the regenerated `agents/<platform>/` trees.

### When you remove a chapter

1. Delete the `.md` file
2. Remove its entry from `mkdocs.yml` nav
3. Remove the symlink from `docs/`
4. Remove the matching `llms.txt` entry
5. Renumber subsequent chapters if needed (in filenames, `mkdocs.yml`, `llms.txt`, and section headings inside the files)
6. Remove the chapter slug from `agents/_content/manifest.toml`, then run `python3 agents/build.py` and commit the regenerated `agents/<platform>/` trees.

### When you rename or reorder chapters

1. Rename the `.md` file
2. Update the `mkdocs.yml` nav entry (both the label and the filename)
3. Update the `docs/` symlink
4. Update the `llms.txt` entry (label, URL slug, and the one-line description if scope changed)
5. Update all `## N.x` section headings inside the file to match the new chapter number
6. Update the chapter slug in `agents/_content/manifest.toml` (and the relevant Part's `SKILL.md` description if scope shifted), then run `python3 agents/build.py` and commit the regenerated `agents/<platform>/` trees.

### mkdocs.yml nav structure

The nav groups chapters into Parts. Each Part is a collapsible section in the sidebar:

```yaml
nav:
  - Introduction: index.md
  - "Part I: Getting Started":
    - "Frontmatter": 00-frontmatter.md
    - "1. Introduction": 01-introduction.md
  - "Part II: Kernel & Boot":
    - "4. Boot and Init": 04-boot-and-init.md
```

The label format is `"N. Short Title": NN-slug.md`. Keep labels short — they appear in the sidebar.

### docs/ symlinks

MkDocs reads from `docs/` which contains symlinks to the actual chapter files in the repo root. This indirection exists because MkDocs requires `docs_dir` to be a child directory, but chapters live at the repo root for simplicity.

When creating symlinks, always use relative paths (`../filename.md`) so they work regardless of absolute path. Also symlink any static assets the chapters reference.

## Chapter Structure

Use this template for every chapter:

```markdown
# Chapter N: Title

> *Optional opening quote*

Introduction paragraph (no heading).

---

## N.1 First Major Section
### N.1.1 Subsection

## N.X Try It
Hands-on exercises with real commands.

## Summary
Key takeaways as bullets.

### Key Source Files
| File | Purpose |
```

**Example:**
```markdown
# Chapter 9: Binder IPC

> *"Binder is the heart of Android's inter-process communication."*

Android's IPC mechanism enables type-safe, identity-aware communication...

---

## 9.1 Why Binder?
### 9.1.1 One-Copy Semantics

## 9.7 Try It
- Run `adb shell service list` to see all registered Binder services

## Summary
- Binder provides one-copy IPC with caller identity
```

## Content Guidelines

**Reference real source code.** Every architectural claim should point to a specific file and line — this is what makes the book valuable beyond a generic overview.

```java
// Source: frameworks/base/services/core/.../PowerManagerService.java:202
private static final int DIRTY_WAKE_LOCKS = 1 << 0;
```

**Match code block language to source file extension.** AOSP has Go code (`.go` files in `build/soong/`) alongside Java. Use ` ```go ` for Go code, ` ```java ` for Java — never mark Go as Java. Key tells: Go uses `:=`, `func (c *config)`, `[]string{}`, no semicolons. Java uses `;` line endings, `public class`, `@Override`.

```go
// Source: build/soong/android/config.go:2402
func (c *config) UseHostMusl() bool {
    return Bool(c.productVariables.HostMusl)
}
```

**Use manual section numbers** matching the chapter (`## 5.1` for chapter 5). MkDocs doesn't auto-number, and if you ever generate PDF, Pandoc's auto-numbering doubles manual numbers.

**Title format:** `# Chapter N: Title` with colon separator. Not `--`, not `—` (em-dash) — those slip in from autocomplete and routine editing and have to be fixed in audit passes.

**End every chapter** with "Try It" (hands-on exercises) immediately followed by "Summary" (key takeaways). **Summary is the last `##` section, full stop.** Don't append more sections after Summary — not "Appendix", not "Deep Dive", not a new feature you forgot about. If you have extra material, fold it into a numbered section before Try It, or extract it into the standalone appendix file. Reviewers found this drift in 5+ chapters during a single audit pass; it always starts as "just one more section" and degrades the chapter shape.

**Watch for duplicate section numbers when inserting new content.** Adding a new `## 9.10` between existing sections requires renumbering everything that follows — or you end up with two `## 9.11` headings later in the chapter (real bug found in chapter 9). Skim the full heading sequence after any insertion.

## Content Organization

Bottom-to-top for system books — each layer builds on the one below:

Build system → Kernel/boot → Native foundation → HAL → Native services → Runtime → Framework core → Framework features → Connectivity → Security → UI → Apps → Infrastructure → Device support → Practical guide

## Mermaid Diagrams

Place a descriptive heading before every mermaid block — it helps readers navigate and becomes the figure caption if you ever generate PDF.

For syntax rules (quoting, special characters, parse errors), read `references/mermaid-syntax.md`. The short version: quote any node label containing `()`, `<br/>`, or `|`.

### Visually verify every mermaid edit

Parse-clean is not enough. Mermaid will happily render a diagram with text overflowing its rectangle, nodes overlapping, or arrows crossing into illegibility — and it will also render diagrams that are syntactically valid but factually wrong about the architecture (missing components, reversed arrow direction, made-up relationships). The build pipeline doesn't catch any of that.

After writing or editing any mermaid block, render it to PNG and look at the result:

```bash
./serve.sh png NN-slug.md          # one chapter
./serve.sh png --all               # every chapter (slow)
```

PNGs land in `.mermaid-png/<slug>/NN-<sha16>.png` (one file per block, indexed in chapter order). The wrapper runs `tools/render_mermaid_png.py` inside the `book-serve` Docker image, reusing the same Playwright + Chromium that the SVG cache already uses. PNGs are content-addressed by the same hash as the SVG cache, so reruns skip unchanged diagrams.

The script also refreshes `.mermaid-cache/<sha16>.svg` for any block whose hash isn't there yet — that's the same cache the pdf/epub plugins read, so editing a diagram and running `./serve.sh png` leaves the next `serve.sh pdf` or `serve.sh epub` build with full cache hits and no Mermaid re-render. One command keeps both caches in sync.

What to check on each PNG:

1. **Layout.** Every label sits inside its shape. No text spills past a rectangle's edge. No two nodes or edge labels overlap. Long labels use `<br/>` breaks (in quoted node labels — never in transition labels).
2. **Architectural accuracy.** Open the chapter alongside the PNG. Every box in the diagram corresponds to a component the prose actually mentions. Arrow direction matches the described data/control flow. Subgraph groupings reflect the real process / package boundaries (e.g. `system_server` boxes only contain things that live in `system_server`). No invented relationships.
3. **Readability at zoom-1.** Open the PNG at native size — if you have to squint, the diagram has too many nodes and should be split.

Don't ship a chapter without re-rendering the diagrams you touched.

## Parallel Writing

For 20+ chapters, launch 5 agents per batch. Review after each batch — then update `mkdocs.yml` nav and `docs/` symlinks for all new chapters before starting the next batch.

## Lists

Markdown lists silently break when you forget the blank line before them — they render as inline text instead of a proper list. This is the single most common formatting issue in the book (we fixed 1,268 instances).

**Always leave a blank line before any numbered or bullet list:**

```markdown
BAD — renders on one line:
Services are started in four phases:
1. Bootstrap services
2. Core services

GOOD — renders as proper list:
Services are started in four phases:

1. Bootstrap services
2. Core services
```

**Match counts to list items.** If you write "three phases:" make sure exactly three items follow. Readers notice when the prose says "three" but the list has four items — it undermines trust in the technical accuracy of the entire chapter.

## Quick Reference

| Do | Don't | Why |
|----|-------|-----|
| Blank line before every list | List right after text | Renders inline instead of as a list |
| "four phases:" with 4 items | "three phases:" with 4 items | Count mismatch erodes reader trust |
| Update `mkdocs.yml` when adding/removing chapters | Add a chapter file without a nav entry | Readers won't find it in the sidebar |
| Create `docs/` symlink for every new chapter | Forget the symlink | MkDocs can't serve files outside `docs/` |
| `## 5.1 Title` in chapter 5 | `## 3.1 Title` (wrong chapter) | Readers use the number to locate content |
| `# Chapter 5: Title` | `# Chapter 5 -- Title` or `# Chapter 5 — Title` | Pick `:`, stick with it (em-dash creeps in from autocomplete) |
| Summary as the last `##` section | Any section after `## Summary` | Readers stop at Summary; trailing sections get lost |
| Heading before each mermaid block | Two mermaid blocks in a row | Each diagram needs its own context |
| ` ```go ` for `.go` files | ` ```java ` for Go code | Wrong syntax highlighting, misleads readers |
| `NODE["text(stuff)"]` | `NODE[text(stuff)]` | Unquoted parens break Mermaid parser |
| `Idle --> Running : start` | `Idle --> Running : start()` | Parens in stateDiagram-v2 transition labels are a hard parse error — strip them, don't quote |
| `subgraph HS["Home Screen"]` | `subgraph Home Screen` | Multi-word subgraph names need explicit IDs |
| `<br/>` in stateDiagram/sequenceDiagram labels | `\n` in stateDiagram/sequenceDiagram labels | `\n` renders literally in those contexts (silently); flowchart labels are the exception |
| `{placeholder}` in flowchart labels | `<placeholder>` in flowchart labels | SVG renderer strips angle-bracket placeholders as HTML tags — text vanishes silently |
| Source path + line number | "The framework does X" | Unverifiable claims undermine the book |
