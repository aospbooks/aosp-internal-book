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


@dataclass(frozen=True)
class Part:
    """One Part-skill entry from the manifest."""
    id: str          # e.g. "02-kernel-and-boot"
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


def parse_skill(text: str) -> tuple[dict[str, str], str]:
    """Parse a SKILL.md file with YAML-style frontmatter.

    The frontmatter is constrained to two keys:
      name: <single-line value>
      description: |
        <indented multi-line block scalar>

    Returns ({"name": ..., "description": ...}, body_after_frontmatter).
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError("SKILL.md is missing YAML frontmatter (--- ... ---)")
    fm = m.group(1)
    body = text[m.end():].lstrip("\n")

    meta: dict[str, str] = {}
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
        else:
            raise ValueError(f"Unexpected SKILL.md frontmatter line: {line!r}")
    return meta, body


def part_skill_path(part_id: str) -> Path:
    """Path to a Part's hand-written SKILL.md."""
    return CONTENT_DIR / "parts" / part_id / "SKILL.md"


def load_part_skills(manifest: Manifest) -> dict[str, tuple[dict[str, str], str]]:
    """Load every Part's SKILL.md, returning {part_id: (frontmatter, body)}."""
    out: dict[str, tuple[dict[str, str], str]] = {}
    for part in manifest.parts:
        path = part_skill_path(part.id)
        if not path.is_file():
            raise FileNotFoundError(f"Missing SKILL.md for part {part.id}: {path}")
        out[part.id] = parse_skill(path.read_text(encoding="utf-8"))
    return out


def _reset_dir(path: Path) -> None:
    """Remove `path` (if it exists) and re-create it empty."""
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def claude_skill_slug(part_id: str) -> str:
    """Skill directory name for a Part inside the Claude plugin."""
    return f"aosp-part-{part_id}"


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
        skill_md = (
            "---\n"
            f"name: {meta['name']}\n"
            "description: |\n"
            + "".join(f"  {line}\n" for line in meta["description"].split("\n"))
            + "---\n\n"
            + body
        )
        (d / "SKILL.md").write_text(skill_md, encoding="utf-8")
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
        "Per-Part background lives in `.github/instructions/aosp-part-<NN>-<slug>.instructions.md`. ",
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
        (inst_dir / f"aosp-part-{part.id}.instructions.md").write_text(
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
    skills = load_part_skills(manifest)

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
