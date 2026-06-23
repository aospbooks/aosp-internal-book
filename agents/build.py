#!/usr/bin/env python3
"""Generate per-platform plugin packages for the AOSP Internals book.

Reads canonical metadata from agents/_content/manifest.toml + per-Part
SKILL.md files, copies chapter Markdown from the repo root, and writes
the four agents/<platform>/ trees (claude, gemini, codex, copilot).

Stdlib only. Requires Python 3.11+ for tomllib. See agents/SPEC.md for
the full design.
"""
from __future__ import annotations

import argparse
import datetime
import filecmp
import json
import re
import shutil
import sys
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path

# Path constants (resolved relative to this script's location).
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
CONTENT_DIR = SCRIPT_DIR / "_content"
MANIFEST_PATH = CONTENT_DIR / "manifest.toml"

# Default author written into a SKILL.md frontmatter when the source file
# does not specify one. New Part SKILL.md files inherit this on the first
# normal build.
DEFAULT_AUTHOR = "utzcoz"


def today_iso() -> str:
    """Return today's date as YYYY-MM-DD (used for SKILL.md last-updated)."""
    return datetime.date.today().isoformat()


@dataclass(frozen=True)
class Part:
    """One Part-skill entry from the manifest."""
    id: str          # e.g. "kernel-and-boot"
    roman: str       # e.g. "II"
    title: str       # e.g. "Kernel & Boot"
    chapters: list[str]  # chapter slugs, e.g. ["04-boot-and-init", ...]


@dataclass(frozen=True)
class Manifest:
    """Top-level manifest data."""
    name: str
    version: str
    repo_url: str
    site_url: str
    description: str
    parts: list[Part]


def load_manifest(path: Path = MANIFEST_PATH) -> Manifest:
    """Parse manifest.toml into a Manifest dataclass."""
    with path.open("rb") as f:
        data = tomllib.load(f)
    parts = [
        Part(
            id=p["id"],
            roman=p["roman"],
            title=p["title"],
            chapters=list(p["chapters"]),
        )
        for p in data["parts"]
    ]
    return Manifest(
        name=data["name"],
        version=data["version"],
        repo_url=data["repo_url"],
        site_url=data["site_url"],
        description=data["description"],
        parts=parts,
    )


def chapter_path(slug: str) -> Path:
    """Return the absolute path to the canonical chapter Markdown at the repo root."""
    return REPO_ROOT / f"{slug}.md"


def validate_chapters(manifest: Manifest) -> None:
    """Raise FileNotFoundError if any chapter slug doesn't have a matching file."""
    missing: list[str] = []
    for part in manifest.parts:
        for slug in part.chapters:
            if not chapter_path(slug).is_file():
                missing.append(slug)
    if missing:
        raise FileNotFoundError(
            f"Manifest references {len(missing)} chapter(s) with no .md file at the repo root: "
            + ", ".join(missing)
        )


_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def parse_skill(text: str) -> tuple[dict, str]:
    """Parse a SKILL.md file with YAML-style frontmatter.

    Supported frontmatter keys:
      name: <single-line value>
      description: |
        <indented multi-line block scalar>
      metadata:                       (optional)
        author: <string>
        version: '<YYYY.MM.DD>'
        last-updated: '<YYYY-MM-DD>'

    `name` and `description` are required. `metadata` is optional; when
    present its sub-keys are read verbatim and any surrounding quotes
    are stripped.

    Returns ({"name": ..., "description": ..., "metadata": {...}}, body).
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError("SKILL.md is missing YAML frontmatter (--- ... ---)")
    fm = m.group(1)
    body = text[m.end():].lstrip("\n")

    meta: dict = {"metadata": {}}
    lines = fm.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.startswith("name:"):
            meta["name"] = line.split(":", 1)[1].strip()
            i += 1
        elif line.startswith("description:"):
            after_colon = line.split(":", 1)[1].strip()
            if after_colon == "|":
                # Block scalar: subsequent indented lines belong to the value.
                desc_lines: list[str] = []
                i += 1
                while i < len(lines) and (lines[i].startswith("  ") or lines[i] == ""):
                    desc_lines.append(lines[i][2:] if lines[i].startswith("  ") else "")
                    i += 1
                meta["description"] = "\n".join(desc_lines).rstrip()
            else:
                meta["description"] = after_colon
                i += 1
        elif line.startswith("metadata:"):
            i += 1
            md: dict[str, str] = {}
            while i < len(lines) and (lines[i].startswith("  ") or lines[i] == ""):
                if not lines[i].strip():
                    i += 1
                    continue
                sub = lines[i][2:]  # strip 2-space block indent
                if ":" not in sub:
                    raise ValueError(f"Unexpected metadata line: {lines[i]!r}")
                k, v = sub.split(":", 1)
                v = v.strip()
                if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
                    v = v[1:-1]
                md[k.strip()] = v
                i += 1
            meta["metadata"] = md
        else:
            raise ValueError(f"Unexpected SKILL.md frontmatter line: {line!r}")
    if "name" not in meta:
        raise ValueError("SKILL.md frontmatter missing required 'name' field")
    if "description" not in meta:
        raise ValueError("SKILL.md frontmatter missing required 'description' field")
    return meta, body


def serialize_skill(meta: dict, body: str) -> str:
    """Serialize parsed SKILL.md frontmatter + body back to text.

    Emits frontmatter in a canonical order: `name`, `description` (block
    scalar), then a `metadata:` block if any metadata keys are set. The
    metadata block sorts `author`, `version`, and `last-updated` first
    (for stable diffs), then any remaining keys in insertion order. Mirrors
    the format produced by generate_claude so that source files rewritten by
    normalization stay byte-identical to freshly generated output.
    """
    md = meta.get("metadata") or {}
    parts: list[str] = [
        "---\n",
        f"name: {meta['name']}\n",
        "description: |\n",
    ]
    for line in meta["description"].split("\n"):
        parts.append(f"  {line}\n" if line else "\n")
    if md:
        parts.append("metadata:\n")
        ordered_keys: list[str] = []
        for k in ("author", "version", "last-updated"):
            if k in md:
                ordered_keys.append(k)
        for k in md:
            if k not in ordered_keys:
                ordered_keys.append(k)
        for k in ordered_keys:
            parts.append(f"  {k}: '{md[k]}'\n")
    parts.append("---\n\n")
    parts.append(body)
    return "".join(parts)


def part_skill_path(part_id: str) -> Path:
    """Path to a Part's hand-written SKILL.md."""
    return CONTENT_DIR / "parts" / part_id / "SKILL.md"


def normalize_skill_metadata(
    meta: dict,
    part_id: str,
    normalize: bool,
    version: str,
) -> tuple[dict, bool]:
    """Normalize SKILL.md frontmatter against canonical conventions.

    Always enforces `meta['name'] = aosp-<part_id>` regardless of
    `normalize`, so the source slug, generated skill directory, and
    frontmatter never drift apart.

    When `normalize` is True (normal build):
      * fills in `metadata.author = DEFAULT_AUTHOR` (utzcoz) if missing;
      * sets `metadata.version` to the manifest's packaged version;
      * bumps `metadata.last-updated` to today's date.

    When `normalize` is False (--check), metadata is passed through
    verbatim so verification stays deterministic across days.

    Returns (new_meta, changed) where `changed` is True if any field was
    added or modified relative to the input.
    """
    new_meta = dict(meta)
    changed = False
    expected_name = claude_skill_slug(part_id)
    if new_meta.get("name") != expected_name:
        new_meta["name"] = expected_name
        changed = True
    if normalize:
        md = dict(meta.get("metadata") or {})
        if not md.get("author"):
            md["author"] = DEFAULT_AUTHOR
            changed = True
        if md.get("version") != version:
            md["version"] = version
            changed = True
        today = today_iso()
        if md.get("last-updated") != today:
            md["last-updated"] = today
            changed = True
        new_meta["metadata"] = md
    else:
        new_meta["metadata"] = meta.get("metadata") or {}
    return new_meta, changed


def load_part_skills(
    manifest: Manifest,
    normalize: bool = True,
) -> dict[str, tuple[dict, str]]:
    """Load every Part's SKILL.md, returning {part_id: (frontmatter, body)}.

    When normalize is True (normal build), the source SKILL.md is
    rewritten in place with the canonical `name:` field, the default
    author, and today's `last-updated` whenever any of those differ from
    what's on disk. When normalize is False (--check), source files are
    read but never modified.
    """
    out: dict[str, tuple[dict, str]] = {}
    for part in manifest.parts:
        path = part_skill_path(part.id)
        if not path.is_file():
            raise FileNotFoundError(f"Missing SKILL.md for part {part.id}: {path}")
        original = path.read_text(encoding="utf-8")
        meta, body = parse_skill(original)
        meta, changed = normalize_skill_metadata(
            meta, part.id, normalize=normalize, version=manifest.version
        )
        if normalize and changed:
            path.write_text(serialize_skill(meta, body), encoding="utf-8")
        out[part.id] = (meta, body)
    return out


def _reset_dir(path: Path) -> None:
    """Remove `path` (if it exists) and re-create it empty."""
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def claude_skill_slug(part_id: str) -> str:
    """Skill directory name for a Part inside the Claude plugin."""
    return f"aosp-{part_id}"


def generate_claude(
    manifest: Manifest,
    skills: dict[str, tuple[dict[str, str], str]],
    out_root: Path,
) -> None:
    """Write the Claude plugin tree to `out_root`."""
    _reset_dir(out_root)

    # .claude-plugin/plugin.json
    plugin_dir = out_root / ".claude-plugin"
    plugin_dir.mkdir()
    plugin = {
        "name": manifest.name,
        "version": manifest.version,
        "description": manifest.description,
        "homepage": manifest.site_url,
        "repository": manifest.repo_url,
    }
    (plugin_dir / "plugin.json").write_text(
        json.dumps(plugin, indent=2) + "\n", encoding="utf-8"
    )

    # skills/<slug>/SKILL.md + chapter copies
    skills_root = out_root / "skills"
    skills_root.mkdir()
    for part in manifest.parts:
        slug = claude_skill_slug(part.id)
        d = skills_root / slug
        d.mkdir()
        meta, body = skills[part.id]
        (d / "SKILL.md").write_text(serialize_skill(meta, body), encoding="utf-8")
        for chapter in part.chapters:
            shutil.copyfile(chapter_path(chapter), d / f"{chapter}.md")


def _concat_part(part: Part) -> str:
    """Concatenate a Part's chapters into one Markdown blob with HTML anchors."""
    out: list[str] = []
    for chapter in part.chapters:
        out.append(f"<!-- chapter:{chapter} -->\n")
        text = chapter_path(chapter).read_text(encoding="utf-8")
        out.append(text)
        if not text.endswith("\n"):
            out.append("\n")
        out.append("\n")
    return "".join(out)


def generate_gemini(
    manifest: Manifest,
    skills: dict[str, tuple[dict[str, str], str]],
    out_root: Path,
) -> None:
    """Write the Gemini CLI extension tree to `out_root`."""
    _reset_dir(out_root)

    # gemini-extension.json
    ext = {
        "name": manifest.name,
        "version": manifest.version,
        "description": manifest.description,
        "homepage": manifest.site_url,
    }
    (out_root / "gemini-extension.json").write_text(
        json.dumps(ext, indent=2) + "\n", encoding="utf-8"
    )

    # GEMINI.md: routing table — each Part's description points to its parts/<id>.md
    md: list[str] = [
        f"# {manifest.description}\n\n",
        f"Source: {manifest.repo_url}\n",
        f"Version: {manifest.version}\n\n",
        "## How to use this extension\n\n",
        "When the user asks about an AOSP subsystem, identify the matching Part below "
        "and read the file at `parts/<part-id>.md` for the full chapter content.\n\n",
        "## Parts\n\n",
    ]
    for part in manifest.parts:
        meta, _body = skills[part.id]
        md.append(f"### {part.id} — Part {part.roman}: {part.title}\n\n")
        md.append(f"**File:** `parts/{part.id}.md`\n\n")
        md.append(f"{meta['description']}\n\n")
    (out_root / "GEMINI.md").write_text("".join(md), encoding="utf-8")

    # parts/<part-id>.md — concatenated chapter content
    parts_dir = out_root / "parts"
    parts_dir.mkdir()
    for part in manifest.parts:
        (parts_dir / f"{part.id}.md").write_text(_concat_part(part), encoding="utf-8")


def generate_codex(
    manifest: Manifest,
    skills: dict[str, tuple[dict[str, str], str]],
    out_root: Path,
) -> None:
    """Write the Codex / AGENTS.md tree to `out_root`."""
    _reset_dir(out_root)

    md: list[str] = [
        f"# {manifest.description}\n\n",
        f"> AOSP Internals plugin, packaged version {manifest.version}.\n",
        f"> Source: {manifest.repo_url}\n\n",
        "## When to read which Part\n\n",
        "When the user asks about an AOSP subsystem, identify the matching "
        "Part below and read `parts/<part-id>.md` for the full chapter content.\n\n",
    ]
    for part in manifest.parts:
        meta, _body = skills[part.id]
        md.append(f"### Part {part.roman} — {part.title} (`parts/{part.id}.md`)\n\n")
        md.append(f"{meta['description']}\n\n")
    (out_root / "AGENTS.md").write_text("".join(md), encoding="utf-8")

    parts_dir = out_root / "parts"
    parts_dir.mkdir()
    for part in manifest.parts:
        (parts_dir / f"{part.id}.md").write_text(_concat_part(part), encoding="utf-8")


def generate_copilot(
    manifest: Manifest,
    skills: dict[str, tuple[dict[str, str], str]],
    out_root: Path,
) -> None:
    """Write the Copilot tree to `out_root`."""
    _reset_dir(out_root)
    gh = out_root / ".github"
    gh.mkdir()

    # Top-level repo-wide instructions (pointer to per-Part files).
    top: list[str] = [
        f"# {manifest.description}\n\n",
        f"> AOSP Internals Copilot bundle, packaged version {manifest.version}.\n",
        f"> Source: {manifest.repo_url}\n\n",
        "Per-Part background lives in `.github/instructions/aosp-<slug>.instructions.md`. ",
        "Copilot loads each one based on its `applyTo` glob; the descriptions "
        "in those files mark which AOSP subsystem they cover.\n\n",
        "When asked about an AOSP subsystem, consult the Part whose description "
        "matches your question.\n",
    ]
    (gh / "copilot-instructions.md").write_text("".join(top), encoding="utf-8")

    # Per-Part .instructions.md files.
    inst_dir = gh / "instructions"
    inst_dir.mkdir()
    for part in manifest.parts:
        meta, _body = skills[part.id]
        front = (
            "---\n"
            "applyTo: '**'\n"
            f"description: '{meta['description'].splitlines()[0].rstrip()}'\n"
            "---\n\n"
        )
        body = (
            f"# Part {part.roman}: {part.title}\n\n"
            f"{meta['description']}\n\n"
            f"## Chapter content\n\n"
            f"{_concat_part(part)}"
        )
        (inst_dir / f"aosp-{part.id}.instructions.md").write_text(
            front + body, encoding="utf-8"
        )


PLATFORMS = ("claude", "gemini", "codex", "copilot")
GENERATORS = {
    "claude": "generate_claude",
    "gemini": "generate_gemini",
    "codex": "generate_codex",
    "copilot": "generate_copilot",
}


def _build_into(out_parent: Path, manifest: Manifest, skills) -> dict[str, Path]:
    """Run all four generators into out_parent/<platform>/."""
    written: dict[str, Path] = {}
    for plat in PLATFORMS:
        target = out_parent / plat
        globals()[GENERATORS[plat]](manifest, skills, target)
        written[plat] = target
    return written


def _dirs_match(a: Path, b: Path) -> tuple[bool, list[str]]:
    """Return (match?, list of differing paths) for a recursive comparison of two dirs."""
    diff = filecmp.dircmp(a, b)
    differing: list[str] = []

    def walk(d: filecmp.dircmp, prefix: str = "") -> None:
        for f in d.left_only:
            differing.append(f"{prefix}{f} (only in {a})")
        for f in d.right_only:
            differing.append(f"{prefix}{f} (only in {b})")
        for f in d.diff_files:
            differing.append(f"{prefix}{f} (contents differ)")
        for f in d.funny_files:
            differing.append(f"{prefix}{f} (could not be compared)")
        for sub_name, sub in d.subdirs.items():
            walk(sub, f"{prefix}{sub_name}/")

    walk(diff)
    return (not differing, differing)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify generated trees are in sync with chapters; exit nonzero if stale",
    )
    args = parser.parse_args(argv)

    manifest = load_manifest()
    validate_chapters(manifest)
    # In --check mode the script is read-only against source SKILL.md files
    # and metadata is passed through verbatim (so the check stays
    # deterministic across days). In a normal build, source `name:` fields
    # are forced into sync with the manifest Part id (`aosp-<id>`),
    # `metadata.author` defaults to utzcoz if missing, and
    # `metadata.last-updated` is bumped to today.
    skills = load_part_skills(manifest, normalize=not args.check)

    if args.check:
        with tempfile.TemporaryDirectory() as td:
            tmp_root = Path(td)
            written = _build_into(tmp_root, manifest, skills)
            ok = True
            for plat, generated in written.items():
                committed = SCRIPT_DIR / plat
                if not committed.is_dir():
                    print(f"DRIFT: agents/{plat}/ does not exist; run agents/build.py")
                    ok = False
                    continue
                match, diffs = _dirs_match(committed, generated)
                if not match:
                    ok = False
                    print(f"DRIFT in agents/{plat}/:")
                    for d in diffs:
                        print(f"  {d}")
            if not ok:
                print("\nRun `python3 agents/build.py` and commit the regenerated files.")
                return 1
            print("agents/<platform>/ trees are in sync with chapter sources.")
            return 0

    # Normal mode: write into agents/<platform>/ and report.
    written = _build_into(SCRIPT_DIR, manifest, skills)
    for plat, target in written.items():
        print(f"  -> {target.relative_to(REPO_ROOT)}")
    print(f"Built {len(written)} platform packages from {len(manifest.parts)} Parts "
          f"({sum(len(p.chapters) for p in manifest.parts)} chapters).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
