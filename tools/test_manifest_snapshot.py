"""Tests for tools/manifest_snapshot.py.

Run from the repo root:
    python3 tools/test_manifest_snapshot.py -v
"""
import argparse
import contextlib
import datetime as _dt
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))


def make_git_dir(git_dir: Path, subjects: list[str]) -> list[str]:
    """Create a real git repo whose git-dir is exactly `git_dir` and add one
    empty commit per subject (oldest first). Returns full SHAs in that order.
    Used to exercise the read-only `git log` helpers offline."""
    git_dir = Path(git_dir)
    work = git_dir.parent / (git_dir.name + ".work")
    git_dir.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@t",
    }
    def git(*a):
        return subprocess.run(
            ["git", f"--git-dir={git_dir}", f"--work-tree={work}", *a],
            check=True, env=env, capture_output=True, text=True,
        )
    git("init", "-q", "-b", "main")
    shas: list[str] = []
    for subj in subjects:
        git("commit", "--allow-empty", "-q", "-m", subj)
        shas.append(git("rev-parse", "HEAD").stdout.strip())
    return shas


class TestCLIScaffolding(unittest.TestCase):
    def test_module_imports(self):
        import manifest_snapshot  # noqa: F401

    def test_main_help_returns_zero(self):
        import manifest_snapshot
        with self.assertRaises(SystemExit) as cm:
            manifest_snapshot.main(["--help"])
        self.assertEqual(cm.exception.code, 0)

    def test_subcommands_exist(self):
        import manifest_snapshot
        with self.assertRaises(SystemExit) as cm:
            manifest_snapshot.main(["snap", "--help"])
        self.assertEqual(cm.exception.code, 0)
        with self.assertRaises(SystemExit) as cm:
            manifest_snapshot.main(["compare", "--help"])
        self.assertEqual(cm.exception.code, 0)


class TestAospRootResolution(unittest.TestCase):
    def _make_fake_aosp(self, parent: Path) -> Path:
        root = parent / "aosp"
        (root / ".repo" / "manifests").mkdir(parents=True)
        (root / ".repo" / "manifests" / "default.xml").write_text("<manifest/>")
        return root

    def test_flag_wins(self):
        from manifest_snapshot import resolve_aosp_root
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            root_a = self._make_fake_aosp(tdp / "a")
            root_b = self._make_fake_aosp(tdp / "b")
            got = resolve_aosp_root(flag=str(root_a), env=str(root_b), start=tdp)
            self.assertEqual(got, root_a)

    def test_env_used_when_no_flag(self):
        from manifest_snapshot import resolve_aosp_root
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            root = self._make_fake_aosp(tdp)
            got = resolve_aosp_root(flag=None, env=str(root), start=tdp)
            self.assertEqual(got, root)

    def test_walk_finds_parent_with_dot_repo(self):
        from manifest_snapshot import resolve_aosp_root
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            root = self._make_fake_aosp(tdp)
            deep = root / "sub" / "deeper"
            deep.mkdir(parents=True)
            got = resolve_aosp_root(flag=None, env=None, start=deep)
            self.assertEqual(got, root)

    def test_error_when_no_repo_found(self):
        from manifest_snapshot import resolve_aosp_root
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(FileNotFoundError):
                resolve_aosp_root(flag=None, env=None, start=Path(td))

    def test_flag_to_nonexistent_path_errors(self):
        from manifest_snapshot import resolve_aosp_root
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(FileNotFoundError):
                resolve_aosp_root(flag=str(Path(td) / "nope"), env=None, start=Path(td))


class TestParseDefaultXml(unittest.TestCase):
    SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<manifest>
  <remote name="aosp" fetch=".."/>
  <default revision="android16-qpr2-release" remote="aosp" sync-j="4"/>
  <project path="build/make" name="platform/build"/>
</manifest>
"""

    def test_returns_revision_and_remote(self):
        from manifest_snapshot import parse_default_xml
        rev, remote = parse_default_xml(self.SAMPLE)
        self.assertEqual(rev, "android16-qpr2-release")
        self.assertEqual(remote, "aosp")

    def test_missing_default_element_raises(self):
        from manifest_snapshot import parse_default_xml
        with self.assertRaises(ValueError):
            parse_default_xml("<manifest/>")

    def test_missing_revision_attr_raises(self):
        from manifest_snapshot import parse_default_xml
        with self.assertRaises(ValueError):
            parse_default_xml('<manifest><default remote="aosp"/></manifest>')


class TestParseManifest(unittest.TestCase):
    SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<manifest>
  <remote name="aosp" fetch=".."/>
  <remote name="other" fetch="https://other.example/"/>
  <default revision="android16-qpr2-release" remote="aosp"/>
  <project path="build/make" name="platform/build" groups="pdk,sysui-studio"
           revision="abc1234abc1234abc1234abc1234abc1234abc12"/>
  <project name="platform/art" groups="pdk"
           revision="def5678def5678def5678def5678def5678def56"/>
  <project path="custom" name="other/custom" remote="other"
           revision="0011001100110011001100110011001100110011"/>
  <project path="nogroups" name="platform/nogroups"
           revision="2222222222222222222222222222222222222222"/>
</manifest>
"""

    def test_returns_default_and_projects(self):
        from manifest_snapshot import parse_manifest
        rev, remote, projects = parse_manifest(self.SAMPLE)
        self.assertEqual(rev, "android16-qpr2-release")
        self.assertEqual(remote, "aosp")
        self.assertEqual(set(projects.keys()),
                         {"platform/build", "platform/art", "other/custom", "platform/nogroups"})

    def test_project_path_defaults_to_name(self):
        from manifest_snapshot import parse_manifest
        _, _, projects = parse_manifest(self.SAMPLE)
        self.assertEqual(projects["platform/art"].path, "platform/art")
        self.assertEqual(projects["platform/build"].path, "build/make")

    def test_project_groups_split(self):
        from manifest_snapshot import parse_manifest
        _, _, projects = parse_manifest(self.SAMPLE)
        self.assertEqual(projects["platform/build"].groups, ("pdk", "sysui-studio"))
        self.assertEqual(projects["platform/nogroups"].groups, ())

    def test_project_remote_defaults_to_default_remote(self):
        from manifest_snapshot import parse_manifest
        _, _, projects = parse_manifest(self.SAMPLE)
        self.assertEqual(projects["platform/build"].remote, "aosp")
        self.assertEqual(projects["other/custom"].remote, "other")

    def test_project_revision_preserved(self):
        from manifest_snapshot import parse_manifest
        _, _, projects = parse_manifest(self.SAMPLE)
        self.assertEqual(projects["platform/build"].revision,
                         "abc1234abc1234abc1234abc1234abc1234abc12")

    def test_clone_depth_parsed(self):
        from manifest_snapshot import parse_manifest
        xml = (
            '<manifest>'
            '  <remote name="aosp" fetch=".."/>'
            '  <default revision="r" remote="aosp"/>'
            '  <project name="full" path="full" revision="1111111111111111111111111111111111111111"/>'
            '  <project name="shallow" path="shallow" clone-depth="1"'
            '           revision="2222222222222222222222222222222222222222"/>'
            '</manifest>'
        )
        _, _, projects = parse_manifest(xml)
        self.assertIsNone(projects["full"].clone_depth)
        self.assertEqual(projects["shallow"].clone_depth, "1")


class TestValidateMetadata(unittest.TestCase):
    GOOD = {
        "schema_version": 1,
        "captured_at": "2026-05-12T14:32:01+00:00",
        "captured_at_unix": 1747058321,
        "default_revision": "android16-qpr2-release",
        "default_remote": "aosp",
        "manifest_branch": "android16-qpr2-release",
        "repo_version": "v2.55",
        "label": "",
        "notes": "",
    }

    def test_good_metadata_passes(self):
        from manifest_snapshot import validate_metadata
        validate_metadata(self.GOOD)  # must not raise

    def test_missing_required_field_raises(self):
        from manifest_snapshot import validate_metadata
        bad = dict(self.GOOD)
        del bad["captured_at"]
        with self.assertRaises(ValueError):
            validate_metadata(bad)

    def test_forbidden_aosp_root_key_raises(self):
        from manifest_snapshot import validate_metadata
        bad = dict(self.GOOD)
        bad["aosp_root"] = "/some/local/aosp-checkout"
        with self.assertRaises(ValueError) as cm:
            validate_metadata(bad)
        self.assertIn("aosp_root", str(cm.exception))

    def test_forbidden_host_key_raises(self):
        from manifest_snapshot import validate_metadata
        bad = dict(self.GOOD)
        bad["host"] = "claude-fleet-abc"
        with self.assertRaises(ValueError):
            validate_metadata(bad)

    def test_schema_version_must_be_one(self):
        from manifest_snapshot import validate_metadata
        bad = dict(self.GOOD)
        bad["schema_version"] = 2
        with self.assertRaises(ValueError):
            validate_metadata(bad)


def _make_repo_init_files(aosp_root: Path, revision: str = "android16-qpr2-release",
                          remote: str = "aosp") -> None:
    """Create the .repo/manifests/default.xml the resolver looks for."""
    md = aosp_root / ".repo" / "manifests"
    md.mkdir(parents=True)
    (md / "default.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<manifest>\n'
        f'  <remote name="{remote}" fetch=".."/>\n'
        f'  <default revision="{revision}" remote="{remote}"/>\n'
        f'</manifest>\n'
    )


class TestSnapHappyPath(unittest.TestCase):
    def _fake_repo_manifest(self, argv, **kwargs):
        """subprocess.run side-effect: write a pinned manifest XML to the -o path."""
        argv = list(argv)
        if "manifest" in argv and "-r" in argv:
            out_idx = argv.index("-o")
            out_path = Path(argv[out_idx + 1])
            out_path.write_text(
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<manifest>\n'
                '  <remote name="aosp" fetch=".."/>\n'
                '  <default revision="android16-qpr2-release" remote="aosp"/>\n'
                '  <project path="build/make" name="platform/build" groups="pdk"\n'
                '           revision="abc1234abc1234abc1234abc1234abc1234abc12"/>\n'
                '  <project name="platform/art" groups="pdk"\n'
                '           revision="def5678def5678def5678def5678def5678def56"/>\n'
                '</manifest>\n'
            )
            return mock.Mock(returncode=0, stdout="", stderr="")
        if "--version" in argv:
            return mock.Mock(returncode=0,
                             stdout="repo launcher version 2.55\n...", stderr="")
        return mock.Mock(returncode=0, stdout="", stderr="")

    def test_writes_xml_and_metadata(self):
        from manifest_snapshot import cmd_snap, validate_metadata
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            aosp = tdp / "aosp"
            aosp.mkdir()
            _make_repo_init_files(aosp)
            outbase = tdp / "manifest-snapshots"
            args = argparse.Namespace(
                cmd="snap", aosp_root=str(aosp), label="test-label",
                notes="test-notes", no_prompt=True, force=False,
                out_base=outbase,
            )
            with mock.patch("subprocess.run", side_effect=self._fake_repo_manifest), \
                 mock.patch("manifest_snapshot.shutil.which", return_value="/usr/bin/repo"):
                rc = cmd_snap(args, now=_dt.datetime(2026, 5, 12, 14, 32, 1,
                                                    tzinfo=_dt.timezone.utc))
            self.assertEqual(rc, 0)
            target = outbase / "android16-qpr2-release" / "2026-05-12"
            self.assertTrue((target / "manifest.xml").is_file())
            meta = json.loads((target / "metadata.json").read_text())
            validate_metadata(meta)
            self.assertEqual(meta["label"], "test-label")
            self.assertEqual(meta["notes"], "test-notes")
            self.assertEqual(meta["default_revision"], "android16-qpr2-release")
            self.assertEqual(meta["repo_version"], "2.55")
            self.assertNotIn("aosp_root", meta)
            self.assertNotIn("host", meta)


class TestSnapPrompts(unittest.TestCase):
    def _fake_repo_manifest(self, argv, **kwargs):
        argv = list(argv)
        if "manifest" in argv and "-r" in argv:
            out_path = Path(argv[argv.index("-o") + 1])
            out_path.write_text(
                '<manifest><default revision="r" remote="aosp"/></manifest>'
            )
            return mock.Mock(returncode=0, stdout="", stderr="")
        return mock.Mock(returncode=0, stdout="repo version 2.55", stderr="")

    def _run_with_stdin(self, stdin_text: str, *, label=None, notes=None,
                       no_prompt=False) -> dict:
        from manifest_snapshot import cmd_snap
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            aosp = tdp / "aosp"
            aosp.mkdir()
            _make_repo_init_files(aosp, revision="r")
            outbase = tdp / "snaps"
            args = argparse.Namespace(
                cmd="snap", aosp_root=str(aosp), label=label, notes=notes,
                no_prompt=no_prompt, force=False, out_base=outbase,
            )
            stdin = io.StringIO(stdin_text)
            with mock.patch("subprocess.run", side_effect=self._fake_repo_manifest), \
                 mock.patch("manifest_snapshot.shutil.which", return_value="/usr/bin/repo"):
                rc = cmd_snap(args, stdin=stdin,
                              now=_dt.datetime(2026, 5, 12, tzinfo=_dt.timezone.utc))
            self.assertEqual(rc, 0)
            return json.loads((outbase / "r" / "2026-05-12" / "metadata.json").read_text())

    def test_no_prompt_with_no_flags_writes_empty_label_and_notes(self):
        meta = self._run_with_stdin("", no_prompt=True)
        self.assertEqual(meta["label"], "")
        self.assertEqual(meta["notes"], "")

    def test_flags_skip_prompts(self):
        meta = self._run_with_stdin("should-not-be-read", label="L", notes="N")
        self.assertEqual(meta["label"], "L")
        self.assertEqual(meta["notes"], "N")

    def test_interactive_reads_label_then_multiline_notes(self):
        # "my label\nline 1\nline 2\n\n"  → label="my label", notes="line 1\nline 2"
        meta = self._run_with_stdin("my label\nline 1\nline 2\n\n")
        self.assertEqual(meta["label"], "my label")
        self.assertEqual(meta["notes"], "line 1\nline 2")

    def test_empty_label_prompt(self):
        meta = self._run_with_stdin("\n\n")
        self.assertEqual(meta["label"], "")
        self.assertEqual(meta["notes"], "")


class TestSnapErrors(unittest.TestCase):
    def _ok_repo_manifest(self, argv, **kwargs):
        argv = list(argv)
        if "manifest" in argv and "-o" in argv:
            Path(argv[argv.index("-o") + 1]).write_text(
                '<manifest><default revision="r" remote="aosp"/></manifest>'
            )
            return mock.Mock(returncode=0, stdout="", stderr="")
        return mock.Mock(returncode=0, stdout="repo version 2.55", stderr="")

    def test_refuses_to_overwrite_existing_snapshot(self):
        from manifest_snapshot import cmd_snap
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            aosp = tdp / "aosp"
            aosp.mkdir()
            _make_repo_init_files(aosp, revision="r")
            outbase = tdp / "snaps"
            target = outbase / "r" / "2026-05-12"
            target.mkdir(parents=True)
            (target / "marker").write_text("preserved")
            args = argparse.Namespace(
                cmd="snap", aosp_root=str(aosp), label="", notes="",
                no_prompt=True, force=False, out_base=outbase,
            )
            with mock.patch("subprocess.run", side_effect=self._ok_repo_manifest), \
                 mock.patch("manifest_snapshot.shutil.which", return_value="/usr/bin/repo"):
                rc = cmd_snap(args, stdin=io.StringIO(""),
                              now=_dt.datetime(2026, 5, 12, tzinfo=_dt.timezone.utc))
            self.assertEqual(rc, 2)
            self.assertTrue((target / "marker").is_file(),
                            "must not destroy existing dir without --force")

    def test_force_overwrites(self):
        from manifest_snapshot import cmd_snap
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            aosp = tdp / "aosp"
            aosp.mkdir()
            _make_repo_init_files(aosp, revision="r")
            outbase = tdp / "snaps"
            target = outbase / "r" / "2026-05-12"
            target.mkdir(parents=True)
            (target / "marker").write_text("old")
            args = argparse.Namespace(
                cmd="snap", aosp_root=str(aosp), label="", notes="",
                no_prompt=True, force=True, out_base=outbase,
            )
            with mock.patch("subprocess.run", side_effect=self._ok_repo_manifest), \
                 mock.patch("manifest_snapshot.shutil.which", return_value="/usr/bin/repo"):
                rc = cmd_snap(args, stdin=io.StringIO(""),
                              now=_dt.datetime(2026, 5, 12, tzinfo=_dt.timezone.utc))
            self.assertEqual(rc, 0)
            self.assertFalse((target / "marker").exists())
            self.assertTrue((target / "manifest.xml").is_file())

    def test_repo_command_failure_cleans_up(self):
        from manifest_snapshot import cmd_snap
        def fail(argv, **kwargs):
            return mock.Mock(returncode=1, stdout="", stderr="boom\n")
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            aosp = tdp / "aosp"
            aosp.mkdir()
            _make_repo_init_files(aosp, revision="r")
            outbase = tdp / "snaps"
            args = argparse.Namespace(
                cmd="snap", aosp_root=str(aosp), label="", notes="",
                no_prompt=True, force=False, out_base=outbase,
            )
            with mock.patch("subprocess.run", side_effect=fail), \
                 mock.patch("manifest_snapshot.shutil.which", return_value="/usr/bin/repo"):
                rc = cmd_snap(args, stdin=io.StringIO(""),
                              now=_dt.datetime(2026, 5, 12, tzinfo=_dt.timezone.utc))
            self.assertEqual(rc, 4)
            self.assertFalse((outbase / "r" / "2026-05-12").exists())

    def test_aosp_root_missing_returns_error(self):
        from manifest_snapshot import cmd_snap
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            outbase = tdp / "snaps"
            args = argparse.Namespace(
                cmd="snap", aosp_root=str(tdp / "nope"), label="", notes="",
                no_prompt=True, force=False, out_base=outbase,
            )
            with self.assertRaises(FileNotFoundError):
                cmd_snap(args, stdin=io.StringIO(""))


class TestClassify(unittest.TestCase):
    def _p(self, name, rev, groups=()):
        from manifest_snapshot import Project
        return Project(name=name, path=name, revision=rev, groups=groups, remote="aosp")

    def test_categories(self):
        from manifest_snapshot import classify
        a = {
            "kept-same":    self._p("kept-same",    "111"),
            "moved":        self._p("moved",        "aaa"),
            "removed-only": self._p("removed-only", "ddd"),
        }
        b = {
            "kept-same": self._p("kept-same", "111"),
            "moved":     self._p("moved",     "bbb"),
            "added-new": self._p("added-new", "ccc"),
        }
        cls = classify(a, b)
        self.assertEqual(set(cls["unchanged"]), {"kept-same"})
        self.assertEqual(set(cls["moved"]),     {"moved"})
        self.assertEqual(set(cls["added"]),     {"added-new"})
        self.assertEqual(set(cls["removed"]),   {"removed-only"})


class TestGroupProjects(unittest.TestCase):
    def _p(self, name, groups):
        from manifest_snapshot import Project
        return Project(name=name, path=name, revision="x",
                       groups=tuple(groups), remote="aosp")

    def test_each_project_under_every_group(self):
        from manifest_snapshot import group_projects
        projects = {
            "multi": self._p("multi", ["pdk", "tradefed"]),
            "single": self._p("single", ["pdk"]),
            "none": self._p("none", []),
        }
        g = group_projects(["multi", "single", "none"], projects)
        self.assertEqual(set(g["pdk"]), {"multi", "single"})
        self.assertEqual(set(g["tradefed"]), {"multi"})
        self.assertEqual(set(g["_ungrouped"]), {"none"})

    def test_sorted_by_path(self):
        from manifest_snapshot import group_projects
        projects = {
            "zzz": self._p("zzz", ["g"]),
            "aaa": self._p("aaa", ["g"]),
            "mmm": self._p("mmm", ["g"]),
        }
        g = group_projects(["zzz", "mmm", "aaa"], projects)
        self.assertEqual(g["g"], ["aaa", "mmm", "zzz"])

    def test_groups_sorted_alphabetically_in_result_keys(self):
        from manifest_snapshot import group_projects
        projects = {
            "x": self._p("x", ["zzz", "aaa"]),
        }
        g = group_projects(["x"], projects)
        self.assertEqual(list(g.keys()), ["aaa", "zzz"])  # _ungrouped absent here


class TestCommitsBetween(unittest.TestCase):
    def test_parses_oneline_output(self):
        from manifest_snapshot import commits_between
        def fake_run(argv, **kwargs):
            argv = list(argv)
            self.assertIn("log", argv)
            self.assertIn("--pretty=oneline", argv)
            self.assertIn("--no-merges", argv)
            return mock.Mock(returncode=0,
                             stdout="ccc333 Third\nbbb222 Second\naaa111 First\n",
                             stderr="")
        with mock.patch("subprocess.run", side_effect=fake_run):
            # Use a real existing path so commits_between doesn't bail early.
            with tempfile.TemporaryDirectory() as td:
                got = commits_between(Path(td), "abc", "def")
        self.assertEqual(got, ["ccc333 Third", "bbb222 Second", "aaa111 First"])

    def test_returns_none_when_sha_missing(self):
        from manifest_snapshot import commits_between
        def fake_run(argv, **kwargs):
            return mock.Mock(returncode=128, stdout="",
                             stderr="fatal: bad revision 'abc..def'\n")
        with mock.patch("subprocess.run", side_effect=fake_run):
            with tempfile.TemporaryDirectory() as td:
                got = commits_between(Path(td), "abc", "def")
        self.assertIsNone(got)

    def test_returns_none_when_git_dir_missing(self):
        from manifest_snapshot import commits_between
        with tempfile.TemporaryDirectory() as td:
            got = commits_between(Path(td) / "no-such.git", "a", "b")
        self.assertIsNone(got)

    def test_integration_with_real_git(self):
        """Build a tiny git repo and ask for the log between two commits."""
        from manifest_snapshot import commits_between
        if shutil.which("git") is None:
            self.skipTest("git not available")
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "r"
            repo.mkdir()
            env = {
                **os.environ,
                "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@t",
                "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@t",
            }
            subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo,
                           check=True, env=env)
            (repo / "a").write_text("1"); subprocess.run(
                ["git", "add", "a"], cwd=repo, check=True, env=env)
            subprocess.run(["git", "commit", "-q", "-m", "first"], cwd=repo,
                           check=True, env=env)
            old = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                                 check=True, env=env, capture_output=True,
                                 text=True).stdout.strip()
            (repo / "a").write_text("2"); subprocess.run(
                ["git", "add", "a"], cwd=repo, check=True, env=env)
            subprocess.run(["git", "commit", "-q", "-m", "second"], cwd=repo,
                           check=True, env=env)
            new = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                                 check=True, env=env, capture_output=True,
                                 text=True).stdout.strip()
            got = commits_between(repo / ".git", old, new)
            self.assertIsNotNone(got)
            self.assertEqual(len(got), 1)
            self.assertIn("second", got[0])

    def test_invocation_is_read_only(self):
        """The only git subcommand we ever invoke is `log`."""
        from manifest_snapshot import commits_between
        seen: list[list[str]] = []
        def record(argv, **kwargs):
            seen.append(list(argv))
            return mock.Mock(returncode=0, stdout="", stderr="")
        with mock.patch("subprocess.run", side_effect=record):
            with tempfile.TemporaryDirectory() as td:
                commits_between(Path(td), "a", "b")
        self.assertEqual(len(seen), 1)
        self.assertIn("log", seen[0])
        forbidden = {"fetch", "gc", "pack-refs", "update-ref", "commit", "push",
                     "checkout", "reset"}
        self.assertFalse(forbidden.intersection(seen[0]),
                         f"forbidden git subcommand in {seen[0]!r}")


class TestCommitsBetweenFullSha(unittest.TestCase):
    def test_lines_start_with_40_char_sha(self):
        from manifest_snapshot import commits_between
        if shutil.which("git") is None:
            self.skipTest("git not available")
        with tempfile.TemporaryDirectory() as td:
            gd = Path(td) / "r.git"
            shas = make_git_dir(gd, ["c1", "c2", "c3"])
            out = commits_between(gd, shas[0], shas[2])
            self.assertEqual(len(out), 2)  # c2, c3 (old excluded)
            for line in out:
                sha, _, subj = line.partition(" ")
                self.assertEqual(len(sha), 40, f"not a full sha: {line!r}")
                self.assertTrue(subj)
            self.assertTrue(any(l.endswith("c3") for l in out))


class TestGooglesourceUrl(unittest.TestCase):
    def test_moved(self):
        from manifest_snapshot import googlesource_url
        self.assertEqual(
            googlesource_url("platform/frameworks/base", "abc1234", "def5678"),
            "https://android.googlesource.com/platform/frameworks/base/+log/abc1234..def5678",
        )

    def test_added_uses_log_at_new(self):
        from manifest_snapshot import googlesource_url
        self.assertEqual(
            googlesource_url("platform/new", None, "def5678"),
            "https://android.googlesource.com/platform/new/+/def5678",
        )

    def test_removed_uses_log_at_old(self):
        from manifest_snapshot import googlesource_url
        self.assertEqual(
            googlesource_url("platform/gone", "abc1234", None),
            "https://android.googlesource.com/platform/gone/+/abc1234",
        )


class TestFullHistory(unittest.TestCase):
    def test_lists_all_reachable_commits(self):
        from manifest_snapshot import full_history
        if shutil.which("git") is None:
            self.skipTest("git not available")
        with tempfile.TemporaryDirectory() as td:
            gd = Path(td) / "r.git"
            shas = make_git_dir(gd, ["a", "b", "c"])
            out = full_history(gd, shas[2])
            self.assertEqual(len(out), 3)
            for line in out:
                self.assertEqual(len(line.partition(" ")[0]), 40)

    def test_none_for_missing_dir(self):
        from manifest_snapshot import full_history
        self.assertIsNone(full_history(Path("/no/such.git"), "deadbeef"))

    def test_none_for_bad_sha(self):
        from manifest_snapshot import full_history
        if shutil.which("git") is None:
            self.skipTest("git not available")
        with tempfile.TemporaryDirectory() as td:
            gd = Path(td) / "r.git"
            make_git_dir(gd, ["a"])
            self.assertIsNone(full_history(gd, "f" * 40))


class TestNonUtf8GitOutput(unittest.TestCase):
    """git log output is arbitrary bytes (commit subjects may be Latin-1, etc.),
    so the helpers must not crash on non-UTF-8."""

    def _repo_with_raw_byte_commit(self, gd):
        """Build a bare repo whose HEAD commit subject contains a raw, non-UTF-8
        byte (0xf6). Porcelain `git commit` re-encodes such messages, so we write
        the commit objects verbatim with `hash-object --literally` (mirrors old /
        imported AOSP commits that carry raw Latin-1 bytes). Returns (base, head)."""
        subprocess.run(["git", "init", "-q", "--bare", str(gd)],
                       check=True, capture_output=True)
        def git(args, inp=None):
            return subprocess.run(["git", f"--git-dir={gd}", *args],
                                  input=inp, capture_output=True, check=True)
        empty_tree = git(["hash-object", "-w", "-t", "tree", "--stdin"],
                         inp=b"").stdout.decode().strip()
        base_obj = (f"tree {empty_tree}\n"
                    "author T <t@t> 0 +0000\ncommitter T <t@t> 0 +0000\n\n"
                    "base\n").encode()
        base = git(["hash-object", "-w", "-t", "commit", "--literally", "--stdin"],
                   inp=base_obj).stdout.decode().strip()
        head_obj = (f"tree {empty_tree}\nparent {base}\n"
                    "author T <t@t> 0 +0000\ncommitter T <t@t> 0 +0000\n\n"
                    ).encode() + b"caf\xf6 latin-1 subject\n"
        head = git(["hash-object", "-w", "-t", "commit", "--literally", "--stdin"],
                   inp=head_obj).stdout.decode().strip()
        git(["update-ref", "refs/heads/main", head])
        return base, head

    def test_full_history_tolerates_non_utf8(self):
        from manifest_snapshot import full_history
        if shutil.which("git") is None:
            self.skipTest("git not available")
        with tempfile.TemporaryDirectory() as td:
            gd = Path(td) / "r.git"
            _base, head = self._repo_with_raw_byte_commit(gd)
            out = full_history(gd, head)  # must NOT raise UnicodeDecodeError
            self.assertEqual(len(out), 2)
            self.assertTrue(any("latin-1 subject" in l for l in out))

    def test_commits_between_tolerates_non_utf8(self):
        from manifest_snapshot import commits_between
        if shutil.which("git") is None:
            self.skipTest("git not available")
        with tempfile.TemporaryDirectory() as td:
            gd = Path(td) / "r.git"
            base, head = self._repo_with_raw_byte_commit(gd)
            out = commits_between(gd, base, head)  # must NOT raise
            self.assertEqual(len(out), 1)
            self.assertTrue(any("latin-1 subject" in l for l in out))


class TestGooglesourceLogUrl(unittest.TestCase):
    def test_builds_log_url(self):
        from manifest_snapshot import googlesource_log_url
        self.assertEqual(
            googlesource_log_url("platform/new", "abc123"),
            "https://android.googlesource.com/platform/new/+log/abc123",
        )


class TestLoadIgnoreGlobs(unittest.TestCase):
    def test_merges_file_and_cli_dedup_order_preserved(self):
        from manifest_snapshot import load_ignore_globs
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "ig.txt"
            f.write_text("# comment line\nprebuilts/*\n\n  */toolchain/*  \n")
            out = load_ignore_globs(f, ["extra/*", "prebuilts/*"])
            self.assertEqual(out, ["prebuilts/*", "*/toolchain/*", "extra/*"])

    def test_missing_file_returns_cli_only(self):
        from manifest_snapshot import load_ignore_globs
        self.assertEqual(load_ignore_globs(Path("/no/such.txt"), ["a/*"]), ["a/*"])

    def test_none_file_and_no_cli_returns_empty(self):
        from manifest_snapshot import load_ignore_globs
        self.assertEqual(load_ignore_globs(None, []), [])


class TestSkipReason(unittest.TestCase):
    def _p(self, path, clone_depth=None):
        from manifest_snapshot import Project
        return Project(name=path, path=path, revision="r", groups=(),
                       remote="aosp", clone_depth=clone_depth)

    def test_glob_match_wins(self):
        from manifest_snapshot import skip_reason
        p = self._p("prebuilts/clang")
        self.assertEqual(
            skip_reason(p, p, Path("/tmp"), ["prebuilts/*"]), "glob:prebuilts/*")

    def test_clone_depth_either_side(self):
        from manifest_snapshot import skip_reason
        a = self._p("x", clone_depth="1")
        b = self._p("x")
        self.assertEqual(skip_reason(a, b, Path("/tmp"), []), "clone-depth=1")
        self.assertEqual(skip_reason(b, a, Path("/tmp"), []), "clone-depth=1")

    def test_shallow_marker(self):
        from manifest_snapshot import skip_reason
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            marker = root / ".repo" / "projects" / "x.git" / "shallow"
            marker.parent.mkdir(parents=True)
            marker.write_text("")
            p = self._p("x")
            self.assertEqual(skip_reason(None, p, root, []), "shallow-marker")

    def test_none_when_full_depth_and_no_glob(self):
        from manifest_snapshot import skip_reason
        p = self._p("x")
        self.assertIsNone(skip_reason(p, p, Path("/tmp"), []))

    def test_no_skip_shallow_disables_depth_and_marker(self):
        from manifest_snapshot import skip_reason
        p = self._p("x", clone_depth="1")
        self.assertIsNone(skip_reason(p, p, Path("/tmp"), [], skip_shallow=False))


class TestCompareKey(unittest.TestCase):
    def _snap(self, branch, date):
        from manifest_snapshot import Snapshot
        return Snapshot(
            snap_dir=Path(f"manifest-snapshots/{branch}/{date}"),
            manifest_xml=Path("m.xml"), metadata={},
            default_revision=branch, default_remote="aosp", projects={},
        )

    def test_encodes_both_branches_and_dates(self):
        from manifest_snapshot import compare_key
        a = self._snap("android16-qpr2-release", "2026-05-12")
        b = self._snap("android17-release", "2026-09-01")
        self.assertEqual(
            compare_key(a, b),
            "android16-qpr2-release_2026-05-12__vs__android17-release_2026-09-01",
        )


class TestRenderChangesTxt(unittest.TestCase):
    def _ctx(self):
        from manifest_snapshot import CompareCtx
        return CompareCtx(
            a_branch="android16", a_date="2026-05-12",
            b_branch="android17", b_date="2026-09-01",
            generated="2026-06-17T00:00:00+00:00",
        )

    def test_renders_sections_counts_and_commits(self):
        from manifest_snapshot import render_changes_txt, MovedEntry
        m = MovedEntry(
            name="platform/frameworks/base", path="frameworks/base",
            groups=("pdk",), old_sha="a" * 40, new_sha="b" * 40,
            commits=["1" * 40 + " Fix a thing", "2" * 40 + " Do another"],
            url="https://gs/x",
        )
        out = render_changes_txt(self._ctx(), [m],
                                 {"moved": 1, "skipped": 0, "added": 0, "removed": 0})
        self.assertIn("android16 @ 2026-05-12", out)
        self.assertIn("frameworks/base   (platform/frameworks/base)", out)
        self.assertIn("(2 commits)", out)
        self.assertIn("Fix a thing", out)

    def test_unreachable_emits_comment_line(self):
        from manifest_snapshot import render_changes_txt, MovedEntry
        m = MovedEntry(name="n", path="p", groups=(), old_sha="a" * 40,
                       new_sha="b" * 40, commits=None, url="https://gs/log")
        out = render_changes_txt(self._ctx(), [m],
                                 {"moved": 1, "skipped": 0, "added": 0, "removed": 0})
        self.assertIn("# unreachable locally; see https://gs/log", out)


class TestRenderAddedRemovedTxt(unittest.TestCase):
    def _ctx(self):
        from manifest_snapshot import CompareCtx
        return CompareCtx("android16", "2026-05-12", "android17", "2026-09-01",
                          "2026-06-17T00:00:00+00:00")

    def test_added_full_history_and_removed_and_skipped(self):
        from manifest_snapshot import render_added_removed_txt, SideEntry
        added = [
            SideEntry("platform/new", "new", ("pdk",), "n" * 40, "added",
                      ["1" * 40 + " initial commit", "2" * 40 + " more"],
                      "https://gs/new/+log/nnn", None),
            SideEntry("prebuilts/x", "prebuilts/x", (), "p" * 40, "added",
                      None, "https://gs/x/+log/ppp", "clone-depth=1"),
        ]
        removed = [
            SideEntry("platform/gone", "gone", ("pdk",), "g" * 40, "removed",
                      None, "https://gs/gone/+log/ggg", None),  # unreachable
        ]
        out = render_added_removed_txt(self._ctx(), added, removed)
        self.assertIn("## ADDED (2)", out)
        self.assertIn("## REMOVED (1)", out)
        self.assertIn("initial commit", out)                      # full history
        self.assertIn("skipped (clone-depth=1); history omitted", out)
        self.assertIn("# unreachable locally; see https://gs/gone/+log/ggg", out)


class TestRenderReportMd(unittest.TestCase):
    def _ctx(self):
        from manifest_snapshot import CompareCtx
        return CompareCtx("android16", "2026-05-12", "android17", "2026-09-01",
                          "2026-06-17T00:00:00+00:00",
                          changes_file="K.changes.txt",
                          added_removed_file="K.added-removed.txt")

    def test_summary_groups_skipped_and_addremoved(self):
        from manifest_snapshot import (render_report_md, MovedEntry,
                                       SkippedEntry, SideEntry)
        moved = [
            MovedEntry("platform/build", "build/make", ("pdk", "sysui-studio"),
                       "a" * 40, "d" * 40, ["x" * 40 + " c1"], "https://gs/b"),
        ]
        skipped = [SkippedEntry("prebuilts/x", "prebuilts/x", "a" * 40, "b" * 40,
                                "clone-depth=1")]
        added = [SideEntry("platform/new", "new", ("pdk",), "n" * 40, "added",
                           ["1" * 40 + " init"], "https://gs/new", None)]
        removed = [SideEntry("platform/gone", "gone", ("pdk",), "g" * 40,
                             "removed", None, "https://gs/gone", None)]
        counts = {"moved": 1, "added": 1, "removed": 1, "unchanged": 4,
                  "skipped": 1, "total_commits": 1}
        out = render_report_md(self._ctx(), moved, skipped, added, removed, counts)
        self.assertIn("# Manifest comparison: android16 @ 2026-05-12", out)
        self.assertIn("| Moved (SHA changed) | 1 |", out)
        self.assertIn("| Skipped (shallow/ignored) | 1 |", out)
        self.assertIn("### Group: pdk", out)
        self.assertIn("### Group: sysui-studio", out)
        self.assertIn("K.changes.txt", out)                 # pointer to commit lists
        self.assertIn("## Skipped projects", out)
        self.assertIn("clone-depth=1", out)
        self.assertIn("## Added projects", out)
        self.assertIn("## Removed projects", out)
        # moved project commit COUNT shown, not the commit text
        self.assertNotIn(" c1", out)


class TestRenderAnalysisPrompt(unittest.TestCase):
    def test_frames_inputs_and_counts(self):
        from manifest_snapshot import render_analysis_prompt, CompareCtx
        ctx = CompareCtx("android16", "2026-05-12", "android17", "2026-09-01",
                         "2026-06-17T00:00:00+00:00",
                         changes_file="K.changes.txt",
                         added_removed_file="K.added-removed.txt")
        counts = {"moved": 12, "added": 3, "removed": 1, "skipped": 90,
                  "unchanged": 800, "total_commits": 4567}
        out = render_analysis_prompt(ctx, counts)
        self.assertIn("android16 @ 2026-05-12", out)
        self.assertIn("android17 @ 2026-09-01", out)
        self.assertIn("K.changes.txt", out)
        self.assertIn("K.added-removed.txt", out)
        self.assertIn("12 projects changed", out)


class TestRenderHistoryTxt(unittest.TestCase):
    def test_renders_header_skipped_and_full_history(self):
        from manifest_snapshot import render_history_txt, HistoryEntry, SkippedEntry
        entries = [
            HistoryEntry("platform/build", "build/make", ("pdk",), "b" * 40,
                         ["1" * 40 + " first", "2" * 40 + " second"], "https://gs/b"),
            HistoryEntry("platform/art", "art", ("pdk",), "c" * 40, None,
                         "https://gs/art/+log/ccc"),
        ]
        skipped = [SkippedEntry("prebuilts/clang", "prebuilts/clang",
                                "p" * 40, None, "clone-depth=1")]
        counts = {"repos": 3, "skipped": 1, "total_commits": 2}
        out = render_history_txt("android16-qpr2-release", "2026-06-17",
                                 "2026-06-17T00:00:00+00:00", entries, skipped, counts)
        self.assertIn("AOSP history: android16-qpr2-release @ 2026-06-17", out)
        self.assertIn("Repositories: 3", out)
        self.assertIn("Total commits: 2", out)
        self.assertIn("## Skipped (shallow/ignored)", out)
        self.assertIn("prebuilts/clang   clone-depth=1", out)
        self.assertIn("build/make   (platform/build)", out)
        self.assertIn("(2 commits)", out)
        self.assertIn("first", out)
        self.assertIn("# unreachable locally; see https://gs/art/+log/ccc", out)


class TestIndexHistory(unittest.TestCase):
    SAMPLE = (
        "AOSP history: android16-test @ 2026-06-18\n"
        "Generated: 2026-06-18T00:00:00+00:00\n"
        "Repositories: 3   Skipped (shallow/ignored): 1   Total commits: 3\n"
        "\n"
        "## Skipped (shallow/ignored)\n"
        "prebuilts/clang   clone-depth=1\n"
        "\n"
        + ("=" * 64) + "\n"
        "art   (platform/art)\n"
        "sha " + "a" * 40 + "   (2 commits)\n"
        + ("-" * 64) + "\n"
        + "1" * 40 + " first art\n"
        + "2" * 40 + " second art\n"
        "\n"
        + ("=" * 64) + "\n"
        "frameworks/base   (platform/frameworks/base)\n"
        "sha " + "b" * 40 + "\n"
        + ("-" * 64) + "\n"
        "# unreachable locally; see https://gs/fb\n"
        "\n"
    )

    def test_indexes_logged_and_skipped(self):
        from manifest_snapshot import index_history, read_history_header
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "h.txt"
            p.write_text(self.SAMPLE, encoding="utf-8")
            self.assertEqual(read_history_header(p), ("android16-test", "2026-06-18"))
            idx = index_history(p)
            self.assertEqual(set(idx), {"art", "frameworks/base", "prebuilts/clang"})
            self.assertEqual(idx["art"].name, "platform/art")
            self.assertEqual(idx["art"].sha, "a" * 40)
            self.assertIsNotNone(idx["art"].commits_start)
            self.assertEqual(idx["prebuilts/clang"].reason, "clone-depth=1")
            self.assertIsNone(idx["prebuilts/clang"].sha)
            # unreachable logged repo: has sha + a body range (the body is the
            # '# unreachable' line, which yields no commits when read)
            self.assertEqual(idx["frameworks/base"].sha, "b" * 40)
            self.assertIsNotNone(idx["frameworks/base"].commits_start)


class TestHistoryCommitDiff(unittest.TestCase):
    def test_read_pairs_and_diff(self):
        from manifest_snapshot import (index_history, read_repo_commit_pairs,
                                       diff_commit_lists)
        a_text = (
            "AOSP history: a @ 2026-01-01\nGenerated: x\nRepositories: 1   "
            "Skipped (shallow/ignored): 0   Total commits: 2\n\n"
            + ("=" * 64) + "\nart   (platform/art)\nsha " + "a" * 40
            + "   (2 commits)\n" + ("-" * 64) + "\n"
            + "11" * 20 + " keep one\n" + "22" * 20 + " dropped two\n\n"
        )
        b_text = (
            "AOSP history: b @ 2026-02-01\nGenerated: x\nRepositories: 1   "
            "Skipped (shallow/ignored): 0   Total commits: 2\n\n"
            + ("=" * 64) + "\nart   (platform/art)\nsha " + "b" * 40
            + "   (2 commits)\n" + ("-" * 64) + "\n"
            + "33" * 20 + " new three\n" + "11" * 20 + " keep one\n\n"
        )
        with tempfile.TemporaryDirectory() as td:
            ap = Path(td) / "a.txt"; ap.write_text(a_text, encoding="utf-8")
            bp = Path(td) / "b.txt"; bp.write_text(b_text, encoding="utf-8")
            ai = index_history(ap); bi = index_history(bp)
            a_pairs = read_repo_commit_pairs(ap, ai["art"])
            b_pairs = read_repo_commit_pairs(bp, bi["art"])
            self.assertEqual(len(a_pairs), 2)
            self.assertEqual(len(b_pairs), 2)
            new, dropped = diff_commit_lists(a_pairs, b_pairs)
            self.assertEqual([s for s, _ in new], ["33" * 20])      # new in B
            self.assertEqual([s for s, _ in dropped], ["22" * 20])  # gone from A

    def test_unreachable_body_returns_none(self):
        from manifest_snapshot import index_history, read_repo_commit_pairs
        text = (
            "AOSP history: a @ 2026-01-01\nGenerated: x\nRepositories: 1   "
            "Skipped (shallow/ignored): 0   Total commits: 0\n\n"
            + ("=" * 64) + "\nart   (platform/art)\nsha " + "a" * 40 + "\n"
            + ("-" * 64) + "\n# unreachable locally; see https://gs/art\n\n"
        )
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "a.txt"; p.write_text(text, encoding="utf-8")
            idx = index_history(p)
            self.assertIsNone(read_repo_commit_pairs(p, idx["art"]))


class TestEmitProgress(unittest.TestCase):
    def test_enabled_writes_line_to_stderr(self):
        import contextlib, io
        from manifest_snapshot import emit_progress
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            emit_progress(True, 3, 10, "frameworks/base  (5 commits)")
        self.assertEqual(buf.getvalue(), "[ 3/10 ] frameworks/base  (5 commits)\n")

    def test_disabled_writes_nothing(self):
        import contextlib, io
        from manifest_snapshot import emit_progress
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            emit_progress(False, 3, 10, "x")
        self.assertEqual(buf.getvalue(), "")


class TestCmdHistory(unittest.TestCase):
    PINNED = """<?xml version="1.0"?>
<manifest>
  <remote name="aosp" fetch=".."/>
  <default revision="android16-qpr2-release" remote="aosp"/>
  <project path="build/make" name="platform/build" groups="pdk"
           revision="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"/>
  <project path="art" name="platform/art" groups="pdk"
           revision="cccccccccccccccccccccccccccccccccccccccc"/>
  <project path="prebuilts/clang" name="prebuilts/clang" groups="pdk"
           clone-depth="1"
           revision="dddddddddddddddddddddddddddddddddddddddd"/>
</manifest>
"""

    def _scaffold(self, tdp):
        aosp = tdp / "aosp"
        (aosp / ".repo" / "manifests").mkdir(parents=True)
        (aosp / ".repo" / "manifests" / "default.xml").write_text(
            '<manifest><default revision="android16-qpr2-release" remote="aosp"/></manifest>')
        # git dirs must exist so full_history() does not bail early.
        for path in ("build/make", "art"):
            (aosp / ".repo" / "projects" / f"{path}.git").mkdir(parents=True)
        return aosp

    def _fake_run(self, argv, **kwargs):
        argv = list(argv)
        if "manifest" in argv and "-r" in argv:
            return mock.Mock(returncode=0, stdout=self.PINNED, stderr="")
        if "log" in argv:
            return mock.Mock(returncode=0,
                             stdout="aaaaaaaa one subject\n", stderr="")
        return mock.Mock(returncode=0, stdout="", stderr="")

    def _args(self, aosp, out_dir):
        return argparse.Namespace(
            cmd="history", aosp_root=str(aosp), out_dir=str(out_dir),
            ignore_glob=[], ignore_file=None, no_skip_shallow=False,
            no_progress=True,
        )

    def test_writes_history_file(self):
        from manifest_snapshot import cmd_history
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            aosp = self._scaffold(tdp)
            out_dir = tdp / "out"
            with mock.patch("subprocess.run", side_effect=self._fake_run), \
                 mock.patch("manifest_snapshot.shutil.which",
                            return_value="/usr/bin/repo"):
                rc = cmd_history(self._args(aosp, out_dir),
                                 now=_dt.datetime(2026, 6, 17, tzinfo=_dt.timezone.utc))
            self.assertEqual(rc, 0)
            out_path = out_dir / "android16-qpr2-release_2026-06-17.history.txt"
            self.assertTrue(out_path.is_file())
            text = out_path.read_text()
            self.assertIn("build/make   (platform/build)", text)
            self.assertIn("art   (platform/art)", text)
            self.assertIn("one subject", text)
            # shallow repo skipped, not logged
            self.assertIn("prebuilts/clang   clone-depth=1", text)
            self.assertNotIn("prebuilts/clang   (prebuilts/clang)", text)

    def test_history_is_read_only(self):
        from manifest_snapshot import cmd_history
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            aosp = self._scaffold(tdp)
            calls: list[list[str]] = []
            def record(argv, **kwargs):
                calls.append(list(argv))
                return self._fake_run(argv, **kwargs)
            with mock.patch("subprocess.run", side_effect=record), \
                 mock.patch("manifest_snapshot.shutil.which",
                            return_value="/usr/bin/repo"):
                cmd_history(self._args(aosp, tdp / "out"),
                            now=_dt.datetime(2026, 6, 17, tzinfo=_dt.timezone.utc))
            forbidden = {"fetch", "gc", "pack-refs", "update-ref", "commit",
                         "push", "checkout", "reset", "clone"}
            for argv in calls:
                self.assertFalse(forbidden.intersection(argv),
                                 f"history invoked forbidden op: {argv!r}")
                if argv and argv[0] == "git":
                    self.assertIn("log", argv)
                if argv and argv[0] == "repo":
                    self.assertIn("manifest", argv)

    def test_missing_repo_returns_3(self):
        from manifest_snapshot import cmd_history
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            aosp = self._scaffold(tdp)
            with mock.patch("manifest_snapshot.shutil.which", return_value=None):
                rc = cmd_history(self._args(aosp, tdp / "out"),
                                 now=_dt.datetime(2026, 6, 17, tzinfo=_dt.timezone.utc))
            self.assertEqual(rc, 3)

    def test_progress_lines_on_stderr(self):
        from manifest_snapshot import cmd_history
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            aosp = self._scaffold(tdp)
            args = argparse.Namespace(
                cmd="history", aosp_root=str(aosp), out_dir=str(tdp / "out"),
                ignore_glob=[], ignore_file=None, no_skip_shallow=False,
                no_progress=False,
            )
            buf = io.StringIO()
            with mock.patch("subprocess.run", side_effect=self._fake_run), \
                 mock.patch("manifest_snapshot.shutil.which",
                            return_value="/usr/bin/repo"), \
                 contextlib.redirect_stderr(buf):
                rc = cmd_history(args,
                                 now=_dt.datetime(2026, 6, 18, tzinfo=_dt.timezone.utc))
            self.assertEqual(rc, 0)
            err = buf.getvalue()
            self.assertIn("[ 1/3 ]", err)
            self.assertIn("art", err)
            self.assertIn("(skipped: clone-depth=1)", err)  # shallow repo line

    def test_no_progress_keeps_stderr_empty(self):
        from manifest_snapshot import cmd_history
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            aosp = self._scaffold(tdp)
            buf = io.StringIO()
            with mock.patch("subprocess.run", side_effect=self._fake_run), \
                 mock.patch("manifest_snapshot.shutil.which",
                            return_value="/usr/bin/repo"), \
                 contextlib.redirect_stderr(buf):
                cmd_history(self._args(aosp, tdp / "out"),
                            now=_dt.datetime(2026, 6, 18, tzinfo=_dt.timezone.utc))
            self.assertEqual(buf.getvalue(), "")

    def test_slashy_default_revision_sanitized(self):
        # repo manifest can pin to a tag, e.g. revision="refs/tags/android-16.0.0_r4";
        # slashes must not become directories in the output filename.
        from manifest_snapshot import cmd_history
        pinned_tag = self.PINNED.replace(
            'revision="android16-qpr2-release"',
            'revision="refs/tags/android-16.0.0_r4"')
        def fake(argv, **kwargs):
            argv = list(argv)
            if "manifest" in argv and "-r" in argv:
                return mock.Mock(returncode=0, stdout=pinned_tag, stderr="")
            if "log" in argv:
                return mock.Mock(returncode=0, stdout="aaaaaaaa s\n", stderr="")
            return mock.Mock(returncode=0, stdout="", stderr="")
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            aosp = self._scaffold(tdp)
            out_dir = tdp / "out"
            with mock.patch("subprocess.run", side_effect=fake), \
                 mock.patch("manifest_snapshot.shutil.which",
                            return_value="/usr/bin/repo"):
                rc = cmd_history(self._args(aosp, out_dir),
                                 now=_dt.datetime(2026, 6, 18, tzinfo=_dt.timezone.utc))
            self.assertEqual(rc, 0)
            self.assertTrue(
                (out_dir / "android-16.0.0_r4_2026-06-18.history.txt").is_file())
            self.assertFalse((out_dir / "refs").exists())  # no nested dirs


class TestRenderHCChanges(unittest.TestCase):
    def _ctx(self):
        from manifest_snapshot import HCCtx
        return HCCtx("android-16.0.0_r4", "2026-06-18", "android17-release",
                     "2026-06-19", "2026-06-19T00:00:00+00:00")

    def test_new_and_dropped_blocks(self):
        from manifest_snapshot import render_history_compare_changes_txt, HCMoved
        m = HCMoved(path="frameworks/base", name="platform/frameworks/base",
                    groups=("pdk",), a_sha="a" * 40, b_sha="b" * 40,
                    new=[("1" * 40, "add feature")],
                    dropped=[("2" * 40, "revert old")],
                    url="https://gs/fb/+log/aaa..bbb")
        out = render_history_compare_changes_txt(
            self._ctx(), [m],
            {"moved": 1, "added": 0, "removed": 0, "new_total": 1,
             "dropped_total": 1, "unavailable": 0})
        self.assertIn("android-16.0.0_r4 @ 2026-06-18", out)
        self.assertIn("frameworks/base   (platform/frameworks/base)", out)
        self.assertIn("NEW (1):", out)
        self.assertIn("add feature", out)
        self.assertIn("DROPPED (1):", out)
        self.assertIn("revert old", out)

    def test_unavailable_repo_notes_link(self):
        from manifest_snapshot import render_history_compare_changes_txt, HCMoved
        m = HCMoved(path="p", name="n", groups=(), a_sha="a" * 40, b_sha="b" * 40,
                    new=None, dropped=None, url="https://gs/p/+log/aaa..bbb")
        out = render_history_compare_changes_txt(
            self._ctx(), [m],
            {"moved": 1, "added": 0, "removed": 0, "new_total": 0,
             "dropped_total": 0, "unavailable": 1})
        self.assertIn("commits unavailable", out)
        self.assertIn("https://gs/p/+log/aaa..bbb", out)


class TestRenderHCReport(unittest.TestCase):
    def _ctx(self):
        from manifest_snapshot import HCCtx
        return HCCtx("android-16.0.0_r4", "2026-06-18", "android17-release",
                     "2026-06-19", "2026-06-19T00:00:00+00:00",
                     changes_file="K.changes.txt",
                     added_removed_file="K.added-removed.txt")

    def test_summary_groups_and_tables(self):
        from manifest_snapshot import (render_history_compare_report_md, HCMoved)
        moved = [HCMoved("frameworks/base", "platform/frameworks/base", ("pdk",),
                         "a" * 40, "b" * 40, [("1" * 40, "c1")], [], "https://gs/fb")]
        added = [("platform/new", "new", ("pdk",), "n" * 40)]
        removed = [("platform/gone", "gone", ("pdk",), "g" * 40)]
        unclassifiable = [("prebuilts/x", "skipped in 16 history")]
        counts = {"moved": 1, "added": 1, "removed": 1, "unchanged": 5,
                  "unclassifiable": 1, "new_total": 1, "dropped_total": 0,
                  "unavailable": 0}
        out = render_history_compare_report_md(
            self._ctx(), moved, added, removed, unclassifiable, counts)
        self.assertIn("# AOSP version diff: android-16.0.0_r4 @ 2026-06-18", out)
        self.assertIn("| Moved | 1 |", out)
        self.assertIn("| Added | 1 |", out)
        self.assertIn("### Group: pdk", out)
        self.assertIn("K.changes.txt", out)
        self.assertIn("## Added projects", out)
        self.assertIn("platform/new", out)
        self.assertIn("## Removed projects", out)
        self.assertIn("## Unclassifiable", out)
        self.assertIn("prebuilts/x", out)
        self.assertNotIn(" c1", out)   # counts, not commit text


class TestRenderHCAddedRemoved(unittest.TestCase):
    def _ctx(self):
        from manifest_snapshot import HCCtx
        return HCCtx("a16", "2026-06-18", "a17", "2026-06-19",
                     "2026-06-19T00:00:00+00:00")

    def test_added_with_history_and_removed_note(self):
        from manifest_snapshot import render_history_compare_added_removed_txt
        # rows: (name, path, groups, sha, history) where history is
        # list[(sha,subject)] | None
        added = [("platform/new", "new", ("pdk",), "n" * 40,
                  [("1" * 40, "init new")])]
        removed = [("platform/gone", "gone", ("pdk",), "g" * 40, None)]
        out = render_history_compare_added_removed_txt(self._ctx(), added, removed)
        self.assertIn("## ADDED (1)", out)
        self.assertIn("new   (platform/new)", out)
        self.assertIn("init new", out)
        self.assertIn("## REMOVED (1)", out)
        self.assertIn("gone   (platform/gone)", out)
        self.assertIn("# history unavailable", out)


class TestCmdCompareHistory(unittest.TestCase):
    def _hist(self, branch, date, repos):
        # repos: list of (path, name, sha, [(commit_sha, subject), ...])
        parts = [f"AOSP history: {branch} @ {date}",
                 "Generated: x",
                 f"Repositories: {len(repos)}   Skipped (shallow/ignored): 0   "
                 "Total commits: 0", ""]
        for path, name, sha, commits in repos:
            parts.append("=" * 64)
            parts.append(f"{path}   ({name})")
            parts.append(f"sha {sha}   ({len(commits)} commits)")
            parts.append("-" * 64)
            parts.extend(f"{c} {sub}" for c, sub in commits)
            parts.append("")
        return "\n".join(parts) + "\n"

    def _snapshot(self, d, revision, projects):
        # projects: list of (name, path, groups, revision)
        d.mkdir(parents=True)
        proj_xml = "\n".join(
            f'  <project path="{p}" name="{n}" groups="{",".join(g)}" '
            f'revision="{r}"/>' for n, p, g, r in projects)
        (d / "manifest.xml").write_text(
            '<?xml version="1.0"?>\n<manifest>\n'
            '  <remote name="aosp" fetch=".."/>\n'
            f'  <default revision="{revision}" remote="aosp"/>\n'
            f'{proj_xml}\n</manifest>\n')
        (d / "metadata.json").write_text(json.dumps({
            "schema_version": 1, "captured_at": "2026-06-19T00:00:00+00:00",
            "captured_at_unix": 0, "default_revision": revision,
            "default_remote": "aosp", "manifest_branch": revision,
            "repo_version": "v2.55", "label": "", "notes": ""}))

    def test_end_to_end(self):
        from manifest_snapshot import cmd_compare_history
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            SHA16, SHA17 = "a" * 40, "b" * 40
            keep, dropped, new = "1" * 40, "2" * 40, "3" * 40
            ha = tdp / "a16.txt"
            ha.write_text(self._hist("android-16.0.0_r4", "2026-06-18", [
                ("frameworks/base", "platform/frameworks/base", SHA16,
                 [(keep, "keep"), (dropped, "drop me")]),
                ("platform/gone", "platform/gone", "c" * 40, [("9" * 40, "old")]),
            ]))
            hb = tdp / "a17.txt"
            hb.write_text(self._hist("android17-release", "2026-06-19", [
                ("frameworks/base", "platform/frameworks/base", SHA17,
                 [(new, "shiny new"), (keep, "keep")]),
                ("platform/added", "platform/added", "d" * 40, [("8" * 40, "born")]),
            ]))
            snap_b = tdp / "android17-release" / "2026-06-19"
            self._snapshot(snap_b, "android17-release", [
                ("platform/frameworks/base", "frameworks/base", ("pdk",), SHA17),
                ("platform/added", "platform/added", ("pdk",), "d" * 40),
            ])
            out_dir = tdp / "out"
            args = argparse.Namespace(
                cmd="compare-history", history_a=str(ha), snapshot_b=str(snap_b),
                history_b=str(hb), out_dir=str(out_dir), no_progress=True)
            rc = cmd_compare_history(args)
            self.assertEqual(rc, 0)
            key = "android-16.0.0_r4_2026-06-18__vs__android17-release_2026-06-19"
            changes = (out_dir / f"{key}.changes.txt").read_text()
            report = (out_dir / f"{key}.report.md").read_text()
            addrem = (out_dir / f"{key}.added-removed.txt").read_text()
            # frameworks/base moved: new=shiny new, dropped=drop me
            self.assertIn("shiny new", changes)   # new in 17
            self.assertIn("drop me", changes)     # dropped from 16
            # 'keep' is common to both sides -> neither new nor dropped -> absent
            self.assertNotIn("keep", changes)
            # platform/added is added (in 17 snapshot, not in 16); platform/gone removed
            self.assertIn("platform/added", addrem)
            self.assertIn("born", addrem)            # added repo full history
            self.assertIn("platform/gone", addrem)
            self.assertIn("| Moved | 1 |", report)
            self.assertIn("| Added | 1 |", report)
            self.assertIn("| Removed | 1 |", report)


class TestCompareEndToEnd(unittest.TestCase):
    XML_A = """<?xml version="1.0"?>
<manifest>
  <remote name="aosp" fetch=".."/>
  <default revision="r1" remote="aosp"/>
  <project path="build/make" name="platform/build" groups="pdk,sysui-studio"
           revision="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"/>
  <project name="platform/art" groups="pdk"
           revision="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"/>
  <project name="platform/gone" groups="pdk"
           revision="cccccccccccccccccccccccccccccccccccccccc"/>
  <project name="prebuilts/clang" path="prebuilts/clang" groups="pdk"
           clone-depth="1"
           revision="9999999999999999999999999999999999999999"/>
</manifest>
"""
    XML_B = """<?xml version="1.0"?>
<manifest>
  <remote name="aosp" fetch=".."/>
  <default revision="r2" remote="aosp"/>
  <project path="build/make" name="platform/build" groups="pdk,sysui-studio"
           revision="dddddddddddddddddddddddddddddddddddddddd"/>
  <project name="platform/art" groups="pdk"
           revision="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"/>
  <project name="platform/new" groups="pdk"
           revision="eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"/>
  <project name="prebuilts/clang" path="prebuilts/clang" groups="pdk"
           clone-depth="1"
           revision="8888888888888888888888888888888888888888"/>
</manifest>
"""

    def _scaffold(self, tdp):
        sa = tdp / "manifest-snapshots" / "r1" / "2026-01-01"
        sb = tdp / "manifest-snapshots" / "r2" / "2026-02-01"
        for sdir, xml in ((sa, self.XML_A), (sb, self.XML_B)):
            sdir.mkdir(parents=True)
            (sdir / "manifest.xml").write_text(xml)
            (sdir / "metadata.json").write_text(json.dumps({
                "schema_version": 1,
                "captured_at": "2026-01-01T00:00:00+00:00", "captured_at_unix": 0,
                "default_revision": sdir.parent.name, "default_remote": "aosp",
                "manifest_branch": sdir.parent.name,
                "repo_version": "v2.55", "label": "", "notes": "",
            }))
        aosp = tdp / "aosp"
        (aosp / ".repo" / "manifests").mkdir(parents=True)
        (aosp / ".repo" / "manifests" / "default.xml").write_text(
            '<manifest><default revision="r2" remote="aosp"/></manifest>')
        return sa, sb, aosp

    def _args(self, sa, sb, aosp, out_dir):
        return argparse.Namespace(
            cmd="compare", a=str(sa), b=str(sb), aosp_root=str(aosp),
            out_dir=str(out_dir), ignore_glob=[], ignore_file=None,
            no_skip_shallow=False, no_progress=True,
        )

    def test_writes_four_keyed_files(self):
        from manifest_snapshot import cmd_compare
        if shutil.which("git") is None:
            self.skipTest("git not available")
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            sa, sb, aosp = self._scaffold(tdp)
            # Real git dirs for the moved project so commits_between succeeds.
            gd = aosp / ".repo" / "projects" / "build/make.git"
            shas = make_git_dir(gd, ["base", "feature one", "feature two"])
            # Rewrite revisions so old..new is reachable in this repo.
            xml_a = (sa / "manifest.xml").read_text().replace("a" * 40, shas[0])
            (sa / "manifest.xml").write_text(xml_a)
            xml_b = (sb / "manifest.xml").read_text().replace("d" * 40, shas[2])
            (sb / "manifest.xml").write_text(xml_b)
            # New project's git dir for its full history.
            gd_new = aosp / ".repo" / "projects" / "platform/new.git"
            new_shas = make_git_dir(gd_new, ["new init", "new more"])
            xml_b = (sb / "manifest.xml").read_text().replace("e" * 40, new_shas[1])
            (sb / "manifest.xml").write_text(xml_b)

            out_dir = tdp / "out"
            rc = cmd_compare(self._args(sa, sb, aosp, out_dir))
            self.assertEqual(rc, 0)

            key = "r1_2026-01-01__vs__r2_2026-02-01"
            report = (out_dir / f"{key}.report.md").read_text()
            changes = (out_dir / f"{key}.changes.txt").read_text()
            addrem = (out_dir / f"{key}.added-removed.txt").read_text()
            prompt = (out_dir / f"{key}.analysis-prompt.txt").read_text()

            # Moved project present with its commits in changes.txt.
            self.assertIn("build/make", changes)
            self.assertIn("feature two", changes)
            # report.md shows counts + groups, not the commit text.
            self.assertIn("### Group: sysui-studio", report)
            self.assertNotIn("feature two", report)
            # Shallow prebuilts/clang skipped (clone-depth), surfaced in report.
            self.assertIn("clone-depth=1", report)
            self.assertNotIn("prebuilts/clang", changes)
            # Added/removed file: new project history + removed project listed.
            self.assertIn("## ADDED", addrem)
            self.assertIn("new init", addrem)
            self.assertIn("## REMOVED", addrem)
            self.assertIn("platform/gone", addrem)
            # Prompt references the sibling files.
            self.assertIn(f"{key}.changes.txt", prompt)

    def test_progress_lines_on_stderr(self):
        from manifest_snapshot import cmd_compare
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            sa, sb, aosp = self._scaffold(tdp)
            # git dirs so commits_between/full_history return (not None)
            for path in ("build/make", "platform/new", "platform/gone"):
                (aosp / ".repo" / "projects" / f"{path}.git").mkdir(parents=True)
            args = argparse.Namespace(
                cmd="compare", a=str(sa), b=str(sb), aosp_root=str(aosp),
                out_dir=str(tdp / "out"), ignore_glob=[], ignore_file=None,
                no_skip_shallow=False, no_progress=False,
            )
            def fake_git(argv, **kwargs):
                argv = list(argv)
                if "log" in argv:
                    return mock.Mock(returncode=0, stdout="dd subject\n", stderr="")
                return mock.Mock(returncode=0, stdout="", stderr="")
            buf = io.StringIO()
            with mock.patch("subprocess.run", side_effect=fake_git), \
                 contextlib.redirect_stderr(buf):
                rc = cmd_compare(args)
            self.assertEqual(rc, 0)
            err = buf.getvalue()
            self.assertIn("[ 1/", err)            # at least one counter line
            self.assertIn("(added)", err)         # added phase labelled
            self.assertIn("(removed)", err)       # removed phase labelled


class TestCompareGracefulDegradation(unittest.TestCase):
    XML_A = TestCompareEndToEnd.XML_A
    XML_B = TestCompareEndToEnd.XML_B

    def test_unreachable_moved_project_falls_back_to_link(self):
        from manifest_snapshot import cmd_compare
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            sa, sb, aosp = TestCompareEndToEnd._scaffold(self, tdp)
            # No .repo/projects/*.git dirs at all -> commits_between returns None.
            out_dir = tdp / "out"
            args = argparse.Namespace(
                cmd="compare", a=str(sa), b=str(sb), aosp_root=str(aosp),
                out_dir=str(out_dir), ignore_glob=[], ignore_file=None,
                no_skip_shallow=False, no_progress=True,
            )
            rc = cmd_compare(args)
            self.assertEqual(rc, 0)
            key = "r1_2026-01-01__vs__r2_2026-02-01"
            changes = (out_dir / f"{key}.changes.txt").read_text()
            self.assertIn("# unreachable locally; see "
                          "https://android.googlesource.com/platform/build/+log/",
                          changes)


class TestReadOnlyInvariant(unittest.TestCase):
    XML_A = TestCompareEndToEnd.XML_A
    XML_B = TestCompareEndToEnd.XML_B

    def test_compare_only_invokes_git_log(self):
        from manifest_snapshot import cmd_compare
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            sa, sb, aosp = TestCompareEndToEnd._scaffold(self, tdp)
            for path in ("build/make", "platform/art"):
                (aosp / ".repo" / "projects" / f"{path}.git").mkdir(parents=True)
            calls: list[list[str]] = []
            def record(argv, **kwargs):
                calls.append(list(argv))
                return mock.Mock(returncode=0, stdout="dd subject\n", stderr="")
            args = argparse.Namespace(
                cmd="compare", a=str(sa), b=str(sb), aosp_root=str(aosp),
                out_dir=str(tdp / "out"), ignore_glob=[], ignore_file=None,
                no_skip_shallow=False, no_progress=True,
            )
            with mock.patch("subprocess.run", side_effect=record):
                cmd_compare(args)
            forbidden = {"fetch", "gc", "pack-refs", "update-ref", "commit",
                         "push", "checkout", "reset", "clone"}
            for argv in calls:
                if argv and argv[0] == "git":
                    self.assertFalse(forbidden.intersection(argv),
                                     f"compare invoked forbidden git op: {argv!r}")

    def test_snap_writes_only_under_out_base(self):
        from manifest_snapshot import cmd_snap
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            aosp = tdp / "aosp"
            aosp.mkdir()
            _make_repo_init_files(aosp, revision="r")
            outbase = tdp / "snaps"

            opened: list[str] = []
            real_open = open
            def trace_open(file, mode="r", *a, **kw):
                if any(c in mode for c in "wxa"):
                    opened.append(str(file))
                return real_open(file, mode, *a, **kw)

            def fake_repo(argv, **kwargs):
                argv = list(argv)
                if "manifest" in argv and "-o" in argv:
                    Path(argv[argv.index("-o") + 1]).write_text(
                        '<manifest><default revision="r" remote="aosp"/></manifest>'
                    )
                    return mock.Mock(returncode=0, stdout="", stderr="")
                return mock.Mock(returncode=0, stdout="repo version 2.55", stderr="")

            args = argparse.Namespace(
                cmd="snap", aosp_root=str(aosp), label="", notes="",
                no_prompt=True, force=False, out_base=outbase,
            )
            with mock.patch("subprocess.run", side_effect=fake_repo), \
                 mock.patch("manifest_snapshot.shutil.which", return_value="/usr/bin/repo"), \
                 mock.patch("builtins.open", side_effect=trace_open):
                rc = cmd_snap(args, stdin=io.StringIO(""),
                              now=_dt.datetime(2026, 5, 12, tzinfo=_dt.timezone.utc))
            self.assertEqual(rc, 0)
            for p in opened:
                self.assertFalse(
                    str(aosp / ".repo") in p,
                    f"snap wrote into .repo: {p!r}",
                )


if __name__ == "__main__":
    unittest.main()
