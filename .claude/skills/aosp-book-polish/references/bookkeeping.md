# Phase D — Bookkeeping & gates

Run after chapters reach convergence, and after any new chapter/Part. Two tiers:
**every-change regeneration + gates** (always), and **new-chapter/Part wiring**
(only when Phase C added one).

## Always (any chapter content changed)

1. **Regenerate Part-skills** (CLAUDE.md rule 12): `python3 agents/build.py`.
   Then `python3 agents/build.py --check` must exit 0 — CI's
   `agents/build.py --check` fails the build if the `agents/<platform>/` trees
   are stale. Do this even for prose/typo/Mermaid-only edits.
2. **Mermaid gate:** every touched chapter `./serve.sh png <chapter>` →
   `errors=0` (already enforced per-wave in the loop; re-confirm here).
3. **`mkdocs build` in Docker:**
   ```bash
   docker compose run --rm --no-deps --entrypoint sh serve -c "mkdocs build"
   ```
   Local `mkdocs build` fails parsing `!!python/name:` / `!ENV` tags — that is an
   environmental loader issue, not your change. The Docker image (or CI) has the
   right loader. A clean "Documentation built in N seconds" = pass.
4. **Leak sweep:** `grep -rlnE "/home/[a-z]+|~/[a-z]|/Users/[a-z]|<username>"`
   across the touched `*.md` and the regenerated `agents/_content` — expect none.
5. **`llms.txt`** (CLAUDE.md rule 11): update only when chapters are added,
   removed, renamed, significantly retitled, or a chapter's scope changed enough
   that its one-liner no longer fits. Within-scope new sections do NOT need an
   `llms.txt` change. Always confirm every `llms.txt` URL still resolves to a
   real `<slug>.md`.

## New chapter (Phase C added one)

A new chapter gets an **appended number** (continue past the last one,
regardless of which Part it joins). Then wire it everywhere:

- **Create the file** from the book-writer template: first line exactly
  `# Chapter N: Title`, intro paragraph (no epigraph), numbered sections, ending
  "Try It" then "Summary" (optional key-files table after). Run it through the
  Phase B convergent loop.
- **`agents/_content/manifest.toml`** — add the slug to the correct Part's
  `chapters = [...]` list. Update the top-of-file `description` count
  (`N chapters + M appendices ... K Part-skills`).
- **`mkdocs.yml`** — add `- "N. Title": <slug>.md` under the right Part in `nav`.
- **`docs/` symlink** — `ln -sf ../<slug>.md docs/<slug>.md` (docs/ is gitignored
  and CI regenerates it, but it must exist locally for `mkdocs build`).
- **`README.md`** — add a row to the "What This Book Covers" table; bump the
  chapter count in surrounding prose and the `./serve.sh pdf` line.
- **`agents/README.md`** — bump the `N chapters + M appendices ... K Part-skills`
  count, the example chapter range, and the per-Part chapter listing table.
- **`llms.txt`** — add a `- [Chapter N: Title](https://.../<slug>/): one-line
  description` entry under the right Part heading.
- Regenerate (`agents/build.py`) and run all the gates above.

## New Part (Phase C added a domain cluster)

A new Part is **appended after the last numbered Part, before Appendices**
(respecting the no-renumber invariant — existing Parts keep their roman numerals).

- **`agents/_content/manifest.toml`** — add a `[[parts]]` block (`id`, next
  `roman`, `title`, `chapters`) before the `appendices` block.
- **Hand-author `agents/_content/parts/<id>/SKILL.md`** — `build.py` errors with
  "Missing SKILL.md for part <id>" until this exists. Copy an existing Part's
  template as a model: frontmatter (`name: aosp-<id>`, a pushy `description`,
  `metadata.author`/`last-updated`), a short intro, a "Chapters in this Part"
  list, and "When to load which chapter" hints. Keep its hint lists in sync when
  you fold modules into other Parts' chapters too.
- **`mkdocs.yml`** — add a `- "Part <roman>: Title":` nav group before
  `Appendices`.
- Update `README.md` + `agents/README.md` Part tables/counts, then regenerate
  and gate.

## Renumbering chapters (inserting a chapter at its logical position)

By default new chapters are *appended* (next free number) — no renumber needed.
Only when the user explicitly wants logical ordering do you renumber. It is a
single all-or-nothing cascade; a half-applied renumber silently breaks
cross-references. Treat it as its own task, separate from polish.

**1. Compute the mapping first, and confirm it.** Decide each new chapter's
target position (usually the end of its `manifest.toml` Part), then walk the
Parts in order assigning sequential numbers to produce a complete `old → new`
table. Insertions cascade: every chapter at or after the lowest insertion point
shifts up. The user's example number may be approximate — show them the exact
computed table and get sign-off before touching files (the blast radius is every
file from the first moved chapter onward plus every cross-reference book-wide).

**2. Rename in an order that never collides.** Renaming `NN-slug.md` upward
(e.g. 52→54, 53→55) must go highest-first (or via temp names) so you never
overwrite a not-yet-moved file. `git mv` each file.

**3. For each MOVED chapter, rewrite its own numbers.** Change the
`# Chapter OLD:` heading to `# Chapter NEW:` and rewrite EVERY internal section
number: `## OLD.x` → `## NEW.x`, `### OLD.x.y` → `### NEW.x.y`, and any in-prose
`OLD.x` / `§OLD.x` self-references. Anchor on the line-leading number so you do
not clobber unrelated digits (e.g. version numbers). Re-run `./serve.sh png` —
Mermaid diagrams that referenced the old section numbers in labels also change.

**4. Fix every cross-reference book-wide.** Across ALL chapters (moved and not),
update references to a moved chapter/section: "Chapter OLD" → "Chapter NEW",
"ch OLD", "§OLD.x", "(see OLD.x)", and the `[Chapter OLD: …](…/OLD-slug/)` links
in prose. Do this as a mapping-driven pass (highest old-number first to avoid
double-rewrites) and grep afterward for any stale "Chapter OLD" left behind.
This is the step most likely to leave silent breakage — verify with a final
grep that no reference points to a number that moved.

**5. Bookkeeping.** Update `manifest.toml` (chapter slugs keep their names; only
their `NN-` filename prefixes changed — fix the slugs in the Part `chapters`
lists), `mkdocs.yml` nav (numbers + filenames), the `docs/` symlinks (remove old,
add new), `README.md` + `agents/README.md` (the coverage table + per-Part ranges
+ counts), and `llms.txt` (the `Chapter N` text and `<slug>` URLs). Then
regenerate `agents/build.py` and run `--check`.

**6. Gate.** `mkdocs build` in Docker; `serve.sh png errors=0` on every renamed
chapter; a book-wide grep proving no cross-reference points at a stale number;
`build.py --check` exit 0.

## The `git checkout -- agents/` trap

To clear a subagent's stray `build.py` regen between waves, people reach for
`git checkout -- agents/`. **It also reverts `agents/_content/manifest.toml` and
your `agents/_content/parts/*/SKILL.md` edits**, because those are tracked files
under `agents/`. Either (a) revert only the generated platform subtrees
(`agents/claude agents/gemini agents/codex agents/copilot`), or (b) just
re-apply the manifest/template edits and re-run `build.py` at the end. After any
such checkout, re-run `build.py` and `--check` before declaring Phase D done.

## Commit (only when the user asks)

Keep everything local on the current branch — no branch, no push, no auto-commit.
When the user says to commit:

```bash
git add -A
git diff --cached --name-only | grep -E '^\.superpowers/|^docs/'   # MUST be empty
python3 agents/build.py --check                                     # MUST exit 0
git commit -F <message-file>                                        # plain author, NO Co-Authored-By trailer
```

`.superpowers/` and `docs/` are gitignored — confirm they are not staged. The
commit body should summarize the version, the chapters touched, any new
chapters/Parts, and that the gates are green.
