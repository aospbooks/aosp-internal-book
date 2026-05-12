"""Tests for tools/manifest_snapshot.py.

Run from the repo root:
    python3 tools/test_manifest_snapshot.py -v
"""
import argparse
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
            self.assertIn("--oneline", argv)
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


class TestRenderCompare(unittest.TestCase):
    def _make_snap(self, branch: str, date: str, projects: dict) -> "Snapshot":
        from manifest_snapshot import Snapshot
        return Snapshot(
            snap_dir=Path(f"manifest-snapshots/{branch}/{date}"),
            manifest_xml=Path(f"manifest-snapshots/{branch}/{date}/manifest.xml"),
            metadata={"label": "", "notes": ""},
            default_revision=branch, default_remote="aosp",
            projects=projects,
        )

    def _p(self, name, rev, groups):
        from manifest_snapshot import Project
        return Project(name=name, path=name, revision=rev,
                       groups=tuple(groups), remote="aosp")

    def test_summary_counts_and_dedup(self):
        from manifest_snapshot import classify, group_projects, render_compare
        a = {
            "moved-multi": self._p("moved-multi", "a1", ["pdk", "tradefed"]),
            "moved-solo":  self._p("moved-solo",  "a2", ["pdk"]),
            "unchanged":   self._p("unchanged",   "a3", ["pdk"]),
            "removed":     self._p("removed",     "a4", ["pdk"]),
            "no-groups":   self._p("no-groups",   "a5", []),
        }
        b = {
            "moved-multi": self._p("moved-multi", "b1", ["pdk", "tradefed"]),
            "moved-solo":  self._p("moved-solo",  "b2", ["pdk"]),
            "unchanged":   self._p("unchanged",   "a3", ["pdk"]),  # same revision
            "added":       self._p("added",       "b6", ["pdk"]),
            "no-groups":   self._p("no-groups",   "b5", []),
        }
        cls = classify(a, b)
        commit_data = {
            "moved-multi": (["b1 commit X", "x9 commit Y"], None),
            "moved-solo":  (["b2 lone"], None),
            "no-groups":   (None, "https://android.googlesource.com/no-groups/+log/a5..b5"),
        }
        a_snap = self._make_snap("br1", "2026-01-01", a)
        b_snap = self._make_snap("br1", "2026-02-01", b)
        out = render_compare(a_snap, b_snap, cls, commit_data,
                             a_key="br1_2026-01-01", b_key="br1_2026-02-01")

        # Summary block
        self.assertIn("| Added projects | 1 |", out)
        self.assertIn("| Removed projects | 1 |", out)
        self.assertIn("| Moved projects (SHA changed) | 3 |", out)
        self.assertIn("| Unchanged projects | 1 |", out)
        # Dedup: 2 (multi) + 1 (solo) + 0 (no-groups, fallback)  → 3 commits.
        # (no-groups has None commit list, so it contributes 0)
        self.assertIn("Total commits across all moved projects (deduplicated) | 3", out)

        # Per-group section
        self.assertIn("### Group: pdk", out)
        self.assertIn("### Group: tradefed", out)
        self.assertIn("### Group: _ungrouped", out)
        # moved-multi appears under both pdk and tradefed (the project header line).
        self.assertEqual(out.count("#### moved-multi"), 2)
        # also-in annotation present
        self.assertIn("also in: tradefed", out)

        # Graceful degradation for no-groups
        self.assertIn("[local git missing", out)
        self.assertIn("https://android.googlesource.com/no-groups/+log/a5..b5", out)

        # Added / removed tables
        self.assertIn("## Added projects", out)
        self.assertIn("| added |", out)
        self.assertIn("## Removed projects", out)
        self.assertIn("| removed |", out)


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
</manifest>
"""

    def test_compare_full_run(self):
        from manifest_snapshot import cmd_compare
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            # Build two snapshot dirs.
            sa = tdp / "manifest-snapshots" / "r1" / "2026-01-01"
            sb = tdp / "manifest-snapshots" / "r2" / "2026-02-01"
            for sdir, xml in ((sa, self.XML_A), (sb, self.XML_B)):
                sdir.mkdir(parents=True)
                (sdir / "manifest.xml").write_text(xml)
                (sdir / "metadata.json").write_text(json.dumps({
                    "schema_version": 1,
                    "captured_at": "2026-01-01T00:00:00+00:00",
                    "captured_at_unix": 0,
                    "default_revision": sdir.parent.name,
                    "default_remote": "aosp",
                    "manifest_branch": sdir.parent.name,
                    "repo_version": "v2.55", "label": "", "notes": "",
                }))
            # Fake AOSP root with read-only bare git dirs (we'll mock git log).
            aosp = tdp / "aosp"
            (aosp / ".repo" / "manifests").mkdir(parents=True)
            (aosp / ".repo" / "manifests" / "default.xml").write_text(
                '<manifest><default revision="r2" remote="aosp"/></manifest>')
            for path in ("build/make", "platform/art"):
                (aosp / ".repo" / "projects" / f"{path}.git").mkdir(parents=True)
            out = tdp / "report.md"
            args = argparse.Namespace(
                cmd="compare", a=str(sa), b=str(sb),
                aosp_root=str(aosp), out=str(out),
            )

            def fake_git(argv, **kwargs):
                argv = list(argv)
                if "log" in argv:
                    return mock.Mock(returncode=0,
                                     stdout="dddddd subject one\n", stderr="")
                return mock.Mock(returncode=0, stdout="", stderr="")

            with mock.patch("subprocess.run", side_effect=fake_git):
                rc = cmd_compare(args)
            self.assertEqual(rc, 0)
            report = out.read_text()
            self.assertIn("platform/build", report)
            self.assertIn("platform/new", report)
            self.assertIn("platform/gone", report)
            self.assertIn("### Group: pdk", report)
            self.assertIn("### Group: sysui-studio", report)


class TestCompareGracefulDegradation(unittest.TestCase):
    XML_A = TestCompareEndToEnd.XML_A
    XML_B = TestCompareEndToEnd.XML_B

    def test_missing_git_dir_emits_fallback_url(self):
        from manifest_snapshot import cmd_compare
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            sa = tdp / "manifest-snapshots" / "r1" / "2026-01-01"
            sb = tdp / "manifest-snapshots" / "r2" / "2026-02-01"
            for sdir, xml in ((sa, self.XML_A), (sb, self.XML_B)):
                sdir.mkdir(parents=True)
                (sdir / "manifest.xml").write_text(xml)
                (sdir / "metadata.json").write_text(json.dumps({
                    "schema_version": 1,
                    "captured_at": "2026-01-01T00:00:00+00:00",
                    "captured_at_unix": 0,
                    "default_revision": sdir.parent.name, "default_remote": "aosp",
                    "manifest_branch": sdir.parent.name,
                    "repo_version": "v2.55", "label": "", "notes": "",
                }))
            # AOSP root WITHOUT any .repo/projects/<path>.git/ dirs.
            aosp = tdp / "aosp"
            (aosp / ".repo" / "manifests").mkdir(parents=True)
            (aosp / ".repo" / "manifests" / "default.xml").write_text(
                '<manifest><default revision="r2" remote="aosp"/></manifest>')
            out = tdp / "report.md"
            args = argparse.Namespace(
                cmd="compare", a=str(sa), b=str(sb),
                aosp_root=str(aosp), out=str(out),
            )
            rc = cmd_compare(args)  # no mock — commits_between returns None
            self.assertEqual(rc, 0)
            report = out.read_text()
            self.assertIn("[local git missing", report)
            self.assertIn("https://android.googlesource.com/platform/build/+log/", report)


class TestReadOnlyInvariant(unittest.TestCase):
    XML_A = TestCompareEndToEnd.XML_A
    XML_B = TestCompareEndToEnd.XML_B

    def test_compare_only_invokes_git_log(self):
        from manifest_snapshot import cmd_compare
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
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
            for path in ("build/make", "platform/art"):
                (aosp / ".repo" / "projects" / f"{path}.git").mkdir(parents=True)

            calls: list[list[str]] = []
            def record(argv, **kwargs):
                calls.append(list(argv))
                return mock.Mock(returncode=0, stdout="dd subject\n", stderr="")

            args = argparse.Namespace(
                cmd="compare", a=str(sa), b=str(sb),
                aosp_root=str(aosp), out=str(tdp / "r.md"),
            )
            with mock.patch("subprocess.run", side_effect=record):
                cmd_compare(args)

            forbidden = {"fetch", "gc", "pack-refs", "update-ref", "commit",
                         "push", "checkout", "reset", "clone"}
            for argv in calls:
                if argv and argv[0] == "git":
                    self.assertFalse(
                        forbidden.intersection(argv),
                        f"compare invoked forbidden git op: {argv!r}",
                    )

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
