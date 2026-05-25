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
        # 64 numbered chapters (00..63) + 3 lettered appendices (A, B, C).
        self.assertEqual(total, 67, f"expected 67 chapter slugs, got {total}")

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
name: aosp-part-kernel-and-boot
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
        self.assertEqual(meta["name"], "aosp-part-kernel-and-boot")
        self.assertIn("init.rc", meta["description"])
        self.assertTrue(meta["description"].startswith("AOSP Part II"))
        self.assertTrue(body.startswith("# AOSP Part II"))

    def test_parse_skill_strips_trailing_newlines_from_description(self):
        from build import parse_skill
        meta, _ = parse_skill(self.SAMPLE)
        self.assertFalse(meta["description"].endswith("\n\n"))

    def test_load_part_skills_returns_one_per_part(self):
        from build import load_part_skills, load_manifest
        m = load_manifest()
        skills = load_part_skills(m, normalize=False)
        self.assertEqual(set(skills.keys()), {p.id for p in m.parts})
        for part_id, (meta, body) in skills.items():
            self.assertIn("name", meta, f"Part {part_id} SKILL.md missing 'name'")
            self.assertIn("description", meta, f"Part {part_id} SKILL.md missing 'description'")
            self.assertTrue(body.strip(), f"Part {part_id} SKILL.md has empty body")


import json
import shutil
import tempfile


class TestClaudeGenerator(unittest.TestCase):
    def test_generate_claude_writes_plugin_json_and_16_skills(self):
        from build import generate_claude, load_manifest, load_part_skills
        m = load_manifest()
        skills = load_part_skills(m, normalize=False)
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            generate_claude(m, skills, out)

            # plugin.json present and well-formed
            plugin_json = out / ".claude-plugin" / "plugin.json"
            self.assertTrue(plugin_json.is_file())
            data = json.loads(plugin_json.read_text())
            self.assertEqual(data["name"], "aosp-internals")
            self.assertEqual(data["version"], m.version)

            # one skill dir per Part
            skill_dirs = sorted((out / "skills").iterdir())
            self.assertEqual(len(skill_dirs), 16)

            # each skill dir contains SKILL.md plus the chapter copies
            for part in m.parts:
                slug = f"aosp-part-{part.id}"
                d = out / "skills" / slug
                self.assertTrue((d / "SKILL.md").is_file(),
                                f"missing SKILL.md in {slug}")
                for chapter in part.chapters:
                    self.assertTrue((d / f"{chapter}.md").is_file(),
                                    f"missing {chapter}.md in {slug}")


class TestGeminiGenerator(unittest.TestCase):
    def test_generate_gemini_writes_extension_manifest_routing_and_part_files(self):
        from build import generate_gemini, load_manifest, load_part_skills
        m = load_manifest()
        skills = load_part_skills(m, normalize=False)
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            generate_gemini(m, skills, out)

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

            # parts/<part-id>.md exists for every Part and includes each chapter's content
            for p in m.parts:
                pf = out / "parts" / f"{p.id}.md"
                self.assertTrue(pf.is_file(), f"missing parts/{p.id}.md")
                pf_text = pf.read_text()
                for chapter in p.chapters:
                    # Each chapter is delimited by an HTML anchor we add at concatenation.
                    self.assertIn(f"<!-- chapter:{chapter} -->", pf_text)


class TestCodexGenerator(unittest.TestCase):
    def test_generate_codex_writes_agents_md_and_part_files(self):
        from build import generate_codex, load_manifest, load_part_skills
        m = load_manifest()
        skills = load_part_skills(m, normalize=False)
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            generate_codex(m, skills, out)

            agents_md = (out / "AGENTS.md").read_text()
            # Must mention each Part id so an AGENTS.md-aware tool can route by id.
            for p in m.parts:
                self.assertIn(p.id, agents_md, f"AGENTS.md missing Part id {p.id!r}")
            # Version stamp surface
            self.assertIn(m.version, agents_md)

            for p in m.parts:
                pf = out / "parts" / f"{p.id}.md"
                self.assertTrue(pf.is_file())
                txt = pf.read_text()
                for chapter in p.chapters:
                    self.assertIn(f"<!-- chapter:{chapter} -->", txt)


class TestCopilotGenerator(unittest.TestCase):
    def test_generate_copilot_writes_top_level_pointer_and_per_part_instructions(self):
        from build import generate_copilot, load_manifest, load_part_skills
        m = load_manifest()
        skills = load_part_skills(m, normalize=False)
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            generate_copilot(m, skills, out)

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
                f = inst_dir / f"aosp-part-{part.id}.instructions.md"
                self.assertTrue(f.is_file(), f"missing {f.name}")
                txt = f.read_text()
                # Front matter must include applyTo (Copilot's targeting key).
                self.assertIn("applyTo:", txt.split("---\n")[1])
                # Each chapter's content must be embedded.
                for chapter in part.chapters:
                    self.assertIn(f"<!-- chapter:{chapter} -->", txt)


import subprocess


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
