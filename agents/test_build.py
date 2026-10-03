"""Tests for agents/build.py.

Run from the repo root:
    python3 -m pytest agents/test_build.py -v
or with the stdlib unittest runner:
    python3 -m unittest agents.test_build -v
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import load_manifest, REPO_ROOT, CONTENT_DIR


class TestManifestParsing(unittest.TestCase):
    def test_load_manifest_returns_16_parts(self):
        m = load_manifest()
        self.assertEqual(len(m.parts), 16, f"expected 16 parts, got {len(m.parts)}")

    def test_load_manifest_total_chapter_count(self):
        m = load_manifest()
        total = sum(len(p.chapters) for p in m.parts)
        # 66 numbered chapters (01..66) + 4 lettered appendices (A, B, C, D).
        self.assertEqual(total, 70, f"expected 70 chapter slugs, got {total}")

    def test_part_ids_are_kebab_case_slugs_without_numeric_prefix(self):
        m = load_manifest()
        for p in m.parts:
            self.assertRegex(
                p.id, r"^[a-z][a-z0-9-]*$",
                f"Part {p.id!r}: id should be a lowercase kebab-case slug with no numeric prefix",
            )
            self.assertFalse(
                p.id[:1].isdigit(),
                f"Part {p.id!r}: id should not start with a digit",
            )


class TestChapterValidation(unittest.TestCase):
    def test_every_manifest_chapter_has_a_real_file(self):
        from build import validate_chapters, load_manifest
        m = load_manifest()
        # Should not raise.
        validate_chapters(m)

    def test_validate_chapters_raises_on_missing_chapter(self):
        from build import validate_chapters, Manifest, Part
        bogus = Manifest(
            name="x", version="0", repo_url="", site_url="", description="",
            parts=[Part(id="x", roman="I", title="X",
                        chapters=["99-does-not-exist"])],
        )
        with self.assertRaises(FileNotFoundError):
            validate_chapters(bogus)


class TestSkillParsing(unittest.TestCase):
    SAMPLE = """---
name: aosp-kernel-and-boot
description: |
  AOSP Part II — Kernel & Boot. Use when reasoning about Android's bootloader
  handoff, init.rc / first-stage init / second-stage init.
---

# AOSP Part II — Kernel & Boot

Body content here.
"""

    def test_parse_skill_extracts_name_and_description(self):
        from build import parse_skill
        meta, body = parse_skill(self.SAMPLE)
        self.assertEqual(meta["name"], "aosp-kernel-and-boot")
        self.assertIn("init.rc", meta["description"])
        self.assertTrue(meta["description"].startswith("AOSP Part II"))
        self.assertTrue(body.startswith("# AOSP Part II"))

    def test_parse_skill_strips_trailing_newlines_from_description(self):
        from build import parse_skill
        meta, _ = parse_skill(self.SAMPLE)
        self.assertFalse(meta["description"].endswith("\n\n"))

    SAMPLE_WITH_METADATA = """---
name: aosp-kernel-and-boot
description: |
  AOSP Part II — Kernel & Boot.
metadata:
  author: 'utzcoz'
  last-updated: '2026-05-25'
---

Body.
"""

    def test_parse_skill_extracts_metadata_block(self):
        from build import parse_skill
        meta, _ = parse_skill(self.SAMPLE_WITH_METADATA)
        self.assertEqual(meta["metadata"]["author"], "utzcoz")
        self.assertEqual(meta["metadata"]["last-updated"], "2026-05-25")

    def test_parse_skill_defaults_metadata_to_empty_dict_when_absent(self):
        from build import parse_skill
        meta, _ = parse_skill(self.SAMPLE)  # no metadata block
        self.assertEqual(meta["metadata"], {})

    def test_serialize_skill_round_trips_metadata(self):
        from build import parse_skill, serialize_skill
        meta, body = parse_skill(self.SAMPLE_WITH_METADATA)
        # serialize -> parse should yield identical metadata
        reparsed, _ = parse_skill(serialize_skill(meta, body))
        self.assertEqual(reparsed["metadata"], meta["metadata"])

    def test_load_part_skills_returns_one_per_part(self):
        from build import load_part_skills, load_manifest
        m = load_manifest()
        skills = load_part_skills(m, normalize=False)
        self.assertEqual(set(skills.keys()), {p.id for p in m.parts})
        for part_id, (meta, body) in skills.items():
            self.assertIn("name", meta, f"Part {part_id} SKILL.md missing 'name'")
            self.assertIn("description", meta, f"Part {part_id} SKILL.md missing 'description'")
            self.assertIn("metadata", meta, f"Part {part_id} SKILL.md missing 'metadata'")
            self.assertEqual(
                meta["metadata"].get("author"), "utzcoz",
                f"Part {part_id} SKILL.md metadata.author should be 'utzcoz'",
            )
            self.assertTrue(
                meta["metadata"].get("version"),
                f"Part {part_id} SKILL.md missing metadata.version",
            )
            self.assertTrue(
                meta["metadata"].get("last-updated"),
                f"Part {part_id} SKILL.md missing metadata.last-updated",
            )
            self.assertTrue(body.strip(), f"Part {part_id} SKILL.md has empty body")


import json
import os
import subprocess
import shutil
import tempfile


def _build_platform(td, generator, name):
    """Generate the shared Part bodies and one platform tree under `td`.

    Platform trees link into `_generated/` with relative paths, so the
    shared bodies must sit beside the platform directory, exactly as they
    do under agents/.
    """
    from build import generate_shared, load_manifest, load_part_skills
    m = load_manifest()
    skills = load_part_skills(m, normalize=False)
    root = Path(td)
    generate_shared(m, skills, root / "_generated")
    out = root / name
    generator(m, skills, out)
    return m, out


class TestSharedBody(unittest.TestCase):
    def test_generate_shared_writes_one_real_body_per_part(self):
        from build import generate_shared, load_manifest, load_part_skills
        m = load_manifest()
        skills = load_part_skills(m, normalize=False)
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "_generated"
            generate_shared(m, skills, out)
            files = sorted((out / "parts").iterdir())
            self.assertEqual(len(files), 16)
            for part in m.parts:
                f = out / "parts" / f"{part.id}.md"
                self.assertTrue(f.is_file() and not f.is_symlink(),
                                f"{f.name} must be a real file, the one copy")
                txt = f.read_text()
                # Copilot reads applyTo from the front matter of this file.
                self.assertIn("applyTo:", txt.split("---\n")[1])
                self.assertIn(f"# Part {part.roman}: {part.title}", txt)
                for chapter in part.chapters:
                    self.assertIn(f"<!-- chapter:{chapter} -->", txt)


class TestClaudeGenerator(unittest.TestCase):
    def test_generate_claude_writes_plugin_json_and_16_skills(self):
        from build import generate_claude
        with tempfile.TemporaryDirectory() as td:
            m, out = _build_platform(td, generate_claude, "claude")

            # plugin.json present and well-formed
            plugin_json = out / ".claude-plugin" / "plugin.json"
            self.assertTrue(plugin_json.is_file())
            data = json.loads(plugin_json.read_text())
            self.assertEqual(data["name"], "aosp-internals")
            self.assertEqual(data["version"], m.version)

            # one skill dir per Part
            skill_dirs = sorted((out / "skills").iterdir())
            self.assertEqual(len(skill_dirs), 16)

            # each skill dir links to the Part's SKILL.md source and to the
            # root chapters; nothing is copied
            for part in m.parts:
                slug = f"aosp-{part.id}"
                d = out / "skills" / slug
                skill = d / "SKILL.md"
                self.assertTrue(skill.is_symlink(), f"SKILL.md in {slug} must be a symlink")
                self.assertEqual(os.readlink(skill),
                                 f"../../../_content/parts/{part.id}/SKILL.md")
                for chapter in part.chapters:
                    link = d / f"{chapter}.md"
                    self.assertTrue(link.is_symlink(), f"{chapter}.md in {slug} must be a symlink")
                    self.assertEqual(os.readlink(link), f"../../../../{chapter}.md")


class TestGeminiGenerator(unittest.TestCase):
    def test_generate_gemini_writes_extension_manifest_routing_and_part_files(self):
        from build import generate_gemini
        with tempfile.TemporaryDirectory() as td:
            m, out = _build_platform(td, generate_gemini, "gemini")

            # gemini-extension.json is well-formed
            ext = out / "gemini-extension.json"
            self.assertTrue(ext.is_file())
            data = json.loads(ext.read_text())
            self.assertEqual(data["name"], "aosp-internals")
            self.assertEqual(data["version"], m.version)

            # GEMINI.md exists and lists every Part
            gemini_md = (out / "GEMINI.md").read_text()
            for p in m.parts:
                self.assertIn(p.id, gemini_md, f"GEMINI.md missing Part id {p.id!r}")

            # parts/<part-id>.md links to the shared body, which holds each chapter
            for p in m.parts:
                pf = out / "parts" / f"{p.id}.md"
                self.assertTrue(pf.is_symlink(), f"parts/{p.id}.md must be a symlink")
                self.assertEqual(os.readlink(pf), f"../../_generated/parts/{p.id}.md")
                pf_text = pf.read_text()
                for chapter in p.chapters:
                    # Each chapter is delimited by an HTML anchor we add at concatenation.
                    self.assertIn(f"<!-- chapter:{chapter} -->", pf_text)


class TestCodexGenerator(unittest.TestCase):
    def test_generate_codex_writes_agents_md_and_part_files(self):
        from build import generate_codex
        with tempfile.TemporaryDirectory() as td:
            m, out = _build_platform(td, generate_codex, "codex")

            agents_md = (out / "AGENTS.md").read_text()
            # Must mention each Part id so an AGENTS.md-aware tool can route by id.
            for p in m.parts:
                self.assertIn(p.id, agents_md, f"AGENTS.md missing Part id {p.id!r}")
            # Version stamp surface
            self.assertIn(m.version, agents_md)

            for p in m.parts:
                pf = out / "parts" / f"{p.id}.md"
                self.assertTrue(pf.is_symlink(), f"parts/{p.id}.md must be a symlink")
                self.assertEqual(os.readlink(pf), f"../../_generated/parts/{p.id}.md")
                txt = pf.read_text()
                for chapter in p.chapters:
                    self.assertIn(f"<!-- chapter:{chapter} -->", txt)


class TestCopilotGenerator(unittest.TestCase):
    def test_generate_copilot_writes_top_level_pointer_and_per_part_instructions(self):
        from build import generate_copilot
        with tempfile.TemporaryDirectory() as td:
            m, out = _build_platform(td, generate_copilot, "copilot")

            # Top-level pointer
            top = out / ".github" / "copilot-instructions.md"
            self.assertTrue(top.is_file())
            top_txt = top.read_text()
            self.assertIn(m.version, top_txt)

            # 16 .instructions.md files, one per Part
            inst_dir = out / ".github" / "instructions"
            inst_files = sorted(inst_dir.iterdir())
            self.assertEqual(len(inst_files), 16)

            for part in m.parts:
                f = inst_dir / f"aosp-{part.id}.instructions.md"
                self.assertTrue(f.is_symlink(), f"{f.name} must be a symlink")
                self.assertEqual(os.readlink(f), f"../../../_generated/parts/{part.id}.md")
                txt = f.read_text()
                # Front matter must include applyTo (Copilot's targeting key).
                self.assertIn("applyTo:", txt.split("---\n")[1])
                # Each chapter's content must be embedded.
                for chapter in part.chapters:
                    self.assertIn(f"<!-- chapter:{chapter} -->", txt)


class TestCommittedTree(unittest.TestCase):
    """The trees under agents/ as they sit in the repository."""

    AGENTS = Path(__file__).resolve().parent

    def test_no_symlink_dangles(self):
        dangling = [str(p.relative_to(self.AGENTS))
                    for p in self.AGENTS.rglob("*")
                    if p.is_symlink() and not p.exists()]
        self.assertEqual(dangling, [], "every generated link must resolve")

    def test_each_part_is_stored_once(self):
        from build import load_manifest
        for part in load_manifest().parts:
            shared = (self.AGENTS / "_generated" / "parts" / f"{part.id}.md").resolve()
            for link in (
                self.AGENTS / "gemini" / "parts" / f"{part.id}.md",
                self.AGENTS / "codex" / "parts" / f"{part.id}.md",
                self.AGENTS / "copilot" / ".github" / "instructions"
                / f"aosp-{part.id}.instructions.md",
            ):
                self.assertEqual(link.resolve(), shared,
                                 f"{link} must resolve to the one shared body")


class TestLastUpdated(unittest.TestCase):
    """`last-updated` records when a Part changed, not when the build ran."""

    def test_unchanged_parts_are_not_redated_by_a_rebuild(self):
        from build import load_manifest, load_part_skills, part_content_changed
        repo = Path(__file__).resolve().parent.parent
        subprocess.run([sys.executable, "agents/build.py"], cwd=repo, check=True)
        m = load_manifest()
        skills = load_part_skills(m, normalize=False)
        changed = [p.id for p in m.parts if part_content_changed(p, skills[p.id][0])]
        self.assertEqual(changed, [], "a rebuild must leave unchanged Parts alone")

    def test_a_part_whose_body_differs_is_detected(self):
        from build import load_manifest, load_part_skills, part_content_changed
        repo = Path(__file__).resolve().parent.parent
        subprocess.run([sys.executable, "agents/build.py"], cwd=repo, check=True)
        m = load_manifest()
        skills = load_part_skills(m, normalize=False)
        part = m.parts[0]
        shared = repo / "agents" / "_generated" / "parts" / f"{part.id}.md"
        original = shared.read_text()
        try:
            shared.write_text(original + "\nstale\n")
            self.assertTrue(part_content_changed(part, skills[part.id][0]))
        finally:
            shared.write_text(original)


class TestCheckMode(unittest.TestCase):
    def test_check_mode_passes_after_full_build(self):
        # Run a full build, then immediately --check; --check must exit 0.
        repo = Path(__file__).resolve().parent.parent
        subprocess.run(
            [sys.executable, "agents/build.py"], cwd=repo, check=True
        )
        result = subprocess.run(
            [sys.executable, "agents/build.py", "--check"], cwd=repo
        )
        self.assertEqual(result.returncode, 0,
                         "agents/build.py --check should exit 0 immediately after a full build")

    def test_check_mode_fails_when_output_is_stale(self):
        repo = Path(__file__).resolve().parent.parent
        subprocess.run(
            [sys.executable, "agents/build.py"], cwd=repo, check=True
        )
        # Touch the generated plugin.json to introduce drift.
        plugin_json = repo / "agents" / "claude" / ".claude-plugin" / "plugin.json"
        original = plugin_json.read_text()
        try:
            plugin_json.write_text(original + "\n# stale comment\n")
            result = subprocess.run(
                [sys.executable, "agents/build.py", "--check"], cwd=repo
            )
            self.assertNotEqual(result.returncode, 0,
                                "--check should exit nonzero when output drifts")
        finally:
            plugin_json.write_text(original)


if __name__ == "__main__":
    unittest.main()
