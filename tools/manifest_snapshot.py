"""Capture and compare pinned AOSP repo manifests.

Subcommands:
    snap     Take a snapshot of the current `.repo` manifest with all
             projects pinned to their current HEAD SHAs.
    compare  Diff two snapshots, producing a Markdown report with per-project
             commit lists grouped by module group.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


def resolve_aosp_root(flag: str | None, env: str | None, start: Path) -> Path:
    """Locate the AOSP checkout root by flag > env > walking parents.

    Returns the directory containing `.repo/manifests/default.xml`.
    Raises FileNotFoundError if no candidate is valid.
    """
    candidates: list[Path] = []
    if flag:
        candidates.append(Path(flag))
    if env:
        candidates.append(Path(env))
    for cand in candidates:
        if (cand / ".repo" / "manifests" / "default.xml").is_file():
            return cand.resolve()
        raise FileNotFoundError(
            f"AOSP root {cand!s} has no .repo/manifests/default.xml"
        )
    cur = Path(start).resolve()
    while True:
        if (cur / ".repo" / "manifests" / "default.xml").is_file():
            return cur
        if cur.parent == cur:
            raise FileNotFoundError(
                "Couldn't locate the AOSP .repo/ tree. "
                "Pass --aosp-root PATH or set AOSP_ROOT."
            )
        cur = cur.parent


def parse_default_xml(xml_text: str) -> tuple[str, str]:
    """Return (default_revision, default_remote) from a repo manifest XML."""
    root = ET.fromstring(xml_text)
    default = root.find("default")
    if default is None:
        raise ValueError("manifest has no <default> element")
    rev = default.get("revision")
    remote = default.get("remote")
    if not rev:
        raise ValueError("<default> has no 'revision' attribute")
    if not remote:
        raise ValueError("<default> has no 'remote' attribute")
    return rev, remote


METADATA_REQUIRED_KEYS = (
    "schema_version", "captured_at", "captured_at_unix",
    "default_revision", "default_remote", "manifest_branch",
    "repo_version", "label", "notes",
)
METADATA_FORBIDDEN_KEYS = ("aosp_root", "host", "hostname", "user", "cwd")
METADATA_SCHEMA_VERSION = 1


def validate_metadata(meta: dict) -> None:
    """Raise ValueError if metadata is missing required keys, has forbidden
    machine-local keys, or has an unsupported schema_version.
    """
    for k in METADATA_REQUIRED_KEYS:
        if k not in meta:
            raise ValueError(f"metadata missing required key: {k!r}")
    for k in METADATA_FORBIDDEN_KEYS:
        if k in meta:
            raise ValueError(
                f"metadata contains machine-local key {k!r}; "
                f"these leak local paths into committed snapshots"
            )
    if meta["schema_version"] != METADATA_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported metadata schema_version {meta['schema_version']!r}; "
            f"expected {METADATA_SCHEMA_VERSION}"
        )


@dataclass(frozen=True)
class Project:
    name: str
    path: str
    revision: str
    groups: tuple[str, ...]
    remote: str


@dataclass(frozen=True)
class Snapshot:
    snap_dir: Path
    manifest_xml: Path
    metadata: dict
    default_revision: str
    default_remote: str
    projects: dict[str, Project]


def parse_manifest(xml_text: str) -> tuple[str, str, dict[str, Project]]:
    """Parse a (pinned) repo manifest XML.

    Returns (default_revision, default_remote, projects_by_name).
    """
    default_rev, default_remote = parse_default_xml(xml_text)
    root = ET.fromstring(xml_text)
    projects: dict[str, Project] = {}
    for el in root.findall("project"):
        name = el.get("name")
        if not name:
            raise ValueError("<project> missing 'name' attribute")
        path = el.get("path") or name
        revision = el.get("revision") or default_rev
        remote = el.get("remote") or default_remote
        groups_raw = el.get("groups") or ""
        groups = tuple(g for g in (s.strip() for s in groups_raw.split(",")) if g)
        projects[name] = Project(
            name=name, path=path, revision=revision,
            groups=groups, remote=remote,
        )
    return default_rev, default_remote, projects


def classify(a: dict[str, Project], b: dict[str, Project]) -> dict[str, list[str]]:
    """Bucket project names into added / removed / moved / unchanged."""
    a_names, b_names = set(a), set(b)
    added = sorted(b_names - a_names)
    removed = sorted(a_names - b_names)
    both = a_names & b_names
    moved = sorted(n for n in both if a[n].revision != b[n].revision)
    unchanged = sorted(n for n in both if a[n].revision == b[n].revision)
    return {"added": added, "removed": removed,
            "moved": moved, "unchanged": unchanged}


UNGROUPED = "_ungrouped"


def group_projects(names: list[str], projects: dict[str, Project]) -> dict[str, list[str]]:
    """Bucket project names by every group they list. Projects with no groups
    land under UNGROUPED. Output dict has groups sorted alphabetically;
    within each group, names sorted by project path.
    """
    buckets: dict[str, list[str]] = {}
    for name in names:
        proj = projects[name]
        targets = list(proj.groups) if proj.groups else [UNGROUPED]
        for g in targets:
            buckets.setdefault(g, []).append(name)
    return {
        g: sorted(buckets[g], key=lambda n: projects[n].path)
        for g in sorted(buckets)
    }


def commits_between(git_dir: Path, old: str, new: str) -> list[str] | None:
    """Return `git log --oneline --no-merges <old>..<new>` as a list of lines,
    or None if the git dir is missing or either SHA is unreachable.

    Strictly read-only: only invokes `git log`.
    """
    git_dir = Path(git_dir)
    if not git_dir.exists():
        return None
    proc = subprocess.run(
        ["git", f"--git-dir={git_dir}", "log", "--oneline", "--no-merges",
         f"{old}..{new}"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return None
    return [line for line in proc.stdout.split("\n") if line.strip()]


GOOGLESOURCE = "https://android.googlesource.com"


def googlesource_url(project_name: str, old: str | None, new: str | None) -> str:
    """Build a Googlesource compare URL from project name and old/new SHAs.

    Returns a URL to view commits between old and new revisions, or a single
    revision if only one is provided.
    """
    if old and new:
        return f"{GOOGLESOURCE}/{project_name}/+log/{old}..{new}"
    if new:
        return f"{GOOGLESOURCE}/{project_name}/+/{new}"
    if old:
        return f"{GOOGLESOURCE}/{project_name}/+/{old}"
    raise ValueError("googlesource_url needs at least one of old/new")


REPO_VERSION_RE = re.compile(r"(?:repo launcher version|repo version)\s+(\S+)")


def _parse_repo_version(text: str) -> str:
    m = REPO_VERSION_RE.search(text)
    return m.group(1) if m else "unknown"


def _prompt_label(stdin) -> str:
    print("Label (optional, press Enter to skip):", end=" ", flush=True)
    return stdin.readline().rstrip("\n")


def _prompt_notes(stdin) -> str:
    print("Notes (optional, end with a blank line):", flush=True)
    lines: list[str] = []
    while True:
        line = stdin.readline()
        if not line:
            break
        stripped = line.rstrip("\n")
        if stripped == "":
            break
        lines.append(stripped)
    return "\n".join(lines)


def cmd_snap(args, *, stdin=None, now=None) -> int:
    stdin = stdin if stdin is not None else sys.stdin
    now = now if now is not None else _dt.datetime.now(_dt.timezone.utc)

    out_base = Path(getattr(args, "out_base", "manifest-snapshots"))
    aosp_root = resolve_aosp_root(
        flag=args.aosp_root, env=os.environ.get("AOSP_ROOT"), start=Path.cwd(),
    )

    default_xml = aosp_root / ".repo" / "manifests" / "default.xml"
    default_rev, default_remote = parse_default_xml(default_xml.read_text())

    today = now.date().isoformat()
    target_dir = out_base / default_rev / today
    if target_dir.exists():
        if not args.force:
            print(
                f"Snapshot already exists for today at {target_dir!s}; "
                f"use --force to overwrite.",
                file=sys.stderr,
            )
            return 2
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True)

    # Run `repo manifest -r --pretty -o <target>/manifest.xml`
    if shutil.which("repo") is None:
        print("`repo` command not found. Install the AOSP repo launcher and re-run.",
              file=sys.stderr)
        shutil.rmtree(target_dir, ignore_errors=True)
        return 3
    manifest_path = target_dir / "manifest.xml"
    try:
        proc = subprocess.run(
            ["repo", "manifest", "-r", "--pretty", "-o", str(manifest_path.absolute())],
            cwd=str(aosp_root), capture_output=True, text=True,
        )
    except FileNotFoundError as e:
        shutil.rmtree(target_dir, ignore_errors=True)
        print(f"failed to run repo: {e}", file=sys.stderr)
        return 3
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
        print("`repo manifest -r` failed; partial snapshot dir removed.",
              file=sys.stderr)
        shutil.rmtree(target_dir, ignore_errors=True)
        return 4

    # Count projects (also validates the XML was written).
    captured = manifest_path.read_text()
    _, _, projects = parse_manifest(captured)

    # repo --version
    try:
        ver_proc = subprocess.run(
            ["repo", "--version"], capture_output=True, text=True, cwd=str(aosp_root),
        )
        repo_version = _parse_repo_version(ver_proc.stdout + ver_proc.stderr)
    except Exception:
        repo_version = "unknown"

    # Resolve label / notes (flags > prompt > "").
    if args.label is not None:
        label = args.label
    elif args.no_prompt:
        label = ""
    else:
        label = _prompt_label(stdin)
    if args.notes is not None:
        notes = args.notes
    elif args.no_prompt:
        notes = ""
    else:
        notes = _prompt_notes(stdin)

    metadata = {
        "schema_version": METADATA_SCHEMA_VERSION,
        "captured_at": now.isoformat(),
        "captured_at_unix": int(now.timestamp()),
        "default_revision": default_rev,
        "default_remote": default_remote,
        "manifest_branch": default_rev,
        "repo_version": repo_version,
        "label": label,
        "notes": notes,
    }
    validate_metadata(metadata)
    (target_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n"
    )

    print(f"Wrote {target_dir!s} ({len(projects)} projects pinned)")
    return 0


def _short(sha: str) -> str:
    return sha[:12] if sha else "<missing>"


def render_compare(a: Snapshot, b: Snapshot, cls: dict, commit_data: dict,
                   a_key: str, b_key: str) -> str:
    """Render the Markdown comparison report.

    commit_data[name] is a tuple `(commits, fallback_url)`:
      - commits: list[str] | None  (None means no local data; use fallback_url)
      - fallback_url: str | None
    Present only for `moved` projects.
    """
    lines: list[str] = []
    now = _dt.datetime.now(_dt.timezone.utc).isoformat()
    lines.append(f"# Manifest comparison: {a.default_revision} @ {a.snap_dir.name}  →  "
                 f"{b.default_revision} @ {b.snap_dir.name}")
    lines.append("")
    lines.append(f"Generated: {now}")
    lines.append("")
    lines.append("| Side | Snapshot | Label | Notes |")
    lines.append("|---|---|---|---|")
    for side, snap in (("A", a), ("B", b)):
        label = snap.metadata.get("label") or "—"
        notes = (snap.metadata.get("notes") or "").splitlines()
        notes_first = notes[0] if notes else "—"
        lines.append(f"| {side} | `{snap.snap_dir}` | {label} | {notes_first} |")
    lines.append("")

    # Summary.
    total_commits = sum(
        len(commit_data.get(n, (None, None))[0] or [])
        for n in cls["moved"]
    )
    lines.append("## Summary")
    lines.append("| Category | Count |")
    lines.append("|---|---|")
    lines.append(f"| Added projects | {len(cls['added'])} |")
    lines.append(f"| Removed projects | {len(cls['removed'])} |")
    lines.append(f"| Moved projects (SHA changed) | {len(cls['moved'])} |")
    lines.append(f"| Unchanged projects | {len(cls['unchanged'])} |")
    lines.append(f"| Total commits across all moved projects (deduplicated) | {total_commits} |")
    lines.append("")

    # By module group: every moved project appears under every group it lists.
    lines.append("## By module group")
    lines.append("")
    grouped = group_projects(cls["moved"], b.projects)  # use B-side groups
    for group_name, names in grouped.items():
        lines.append(f"### Group: {group_name}")
        lines.append(f"*{len(names)} project(s) changed in this group.*")
        lines.append("")
        for name in names:
            proj_b = b.projects[name]
            proj_a = a.projects.get(name)
            other_groups = tuple(g for g in proj_b.groups if g != group_name)
            also = (", ".join(other_groups) or "<none>")
            lines.append(f"#### {name}  (also in: {also})")
            old_rev = proj_a.revision if proj_a else None
            new_rev = proj_b.revision
            commits, fallback_url = commit_data.get(name, (None, None))
            lines.append(f"- path: `{proj_b.path}`")
            n_commits = len(commits) if commits is not None else 0
            lines.append(f"- old: `{_short(old_rev or '')}`  →  new: `{_short(new_rev)}`"
                         f"  ({n_commits} commit{'s' if n_commits != 1 else ''})")
            compare = googlesource_url(name, old_rev, new_rev)
            lines.append(f"- Compare: <{compare}>")
            if commits is None:
                lines.append(f"- [local git missing one or both SHAs; see compare link]")
                if fallback_url:
                    lines.append(f"- Fallback: <{fallback_url}>")
            else:
                lines.append("")
                lines.append("  ```")
                for c in commits:
                    lines.append(f"  {c}")
                lines.append("  ```")
            lines.append("")

    # Added / Removed tables.
    def _row(p: Project, sha: str) -> str:
        groups = ", ".join(p.groups) if p.groups else "—"
        return f"| {p.name} | `{p.path}` | `{_short(sha)}` | {groups} |"

    lines.append("## Added projects")
    lines.append("| Name | Path | At SHA | Groups |")
    lines.append("|---|---|---|---|")
    for n in cls["added"]:
        p = b.projects[n]
        lines.append(_row(p, p.revision))
    lines.append("")
    lines.append("## Removed projects")
    lines.append("| Name | Path | Was at SHA | Groups |")
    lines.append("|---|---|---|---|")
    for n in cls["removed"]:
        p = a.projects[n]
        lines.append(_row(p, p.revision))
    lines.append("")

    return "\n".join(lines)


def load_snapshot(snap_dir: Path) -> Snapshot:
    snap_dir = Path(snap_dir)
    manifest_xml = snap_dir / "manifest.xml"
    metadata_path = snap_dir / "metadata.json"
    if not manifest_xml.is_file() or not metadata_path.is_file():
        raise FileNotFoundError(
            f"{snap_dir!s} is not a snapshot dir "
            f"(missing manifest.xml or metadata.json)"
        )
    metadata = json.loads(metadata_path.read_text())
    validate_metadata(metadata)
    rev, remote, projects = parse_manifest(manifest_xml.read_text())
    return Snapshot(
        snap_dir=snap_dir, manifest_xml=manifest_xml, metadata=metadata,
        default_revision=rev, default_remote=remote, projects=projects,
    )


def _snap_key(snap: Snapshot) -> str:
    return f"{snap.default_revision}_{snap.snap_dir.name}"


def cmd_compare(args) -> int:
    a = load_snapshot(Path(args.a))
    b = load_snapshot(Path(args.b))
    aosp_root = resolve_aosp_root(
        flag=args.aosp_root, env=os.environ.get("AOSP_ROOT"), start=Path.cwd(),
    )
    cls = classify(a.projects, b.projects)

    commit_data: dict[str, tuple[list[str] | None, str | None]] = {}
    for name in cls["moved"]:
        proj_b = b.projects[name]
        proj_a = a.projects[name]
        git_dir = aosp_root / ".repo" / "projects" / f"{proj_b.path}.git"
        commits = commits_between(git_dir, proj_a.revision, proj_b.revision)
        fallback = googlesource_url(name, proj_a.revision, proj_b.revision)
        commit_data[name] = (commits, fallback if commits is None else None)

    a_key = _snap_key(a)
    b_key = _snap_key(b)
    report = render_compare(a, b, cls, commit_data, a_key=a_key, b_key=b_key)

    if args.out:
        out_path = Path(args.out)
    else:
        out_path = Path("manifest-snapshots") / "_compare" / f"{a_key}__vs__{b_key}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report)
    print(f"Wrote {out_path!s}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="manifest_snapshot",
        description="Capture and compare pinned AOSP repo manifests.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    snap = sub.add_parser("snap", help="capture a pinned manifest snapshot")
    snap.add_argument("--aosp-root", default=None,
                      help="path to AOSP checkout (containing .repo/)")
    snap.add_argument("--label", default=None,
                      help="short label (skips interactive label prompt)")
    snap.add_argument("--notes", default=None,
                      help="free-form notes (skips interactive notes prompt)")
    snap.add_argument("--no-prompt", action="store_true",
                      help="don't prompt; use empty strings for any unset field")
    snap.add_argument("--force", action="store_true",
                      help="overwrite an existing snapshot for today")
    snap.add_argument("--out-base", default="manifest-snapshots",
                      help="snapshot root directory (default: manifest-snapshots/)")

    cmp = sub.add_parser("compare", help="diff two snapshots")
    cmp.add_argument("a", help="path or shorthand of snapshot A")
    cmp.add_argument("b", help="path or shorthand of snapshot B")
    cmp.add_argument("--aosp-root", default=None,
                     help="path to AOSP checkout (containing .repo/projects/)")
    cmp.add_argument(
        "--out", default=None,
        help="path to write the Markdown report "
             "(default: manifest-snapshots/_compare/<A>__vs__<B>.md)",
    )

    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.cmd == "snap":
        return cmd_snap(args)
    if args.cmd == "compare":
        return cmd_compare(args)
    parser.error(f"unknown command: {args.cmd}")


if __name__ == "__main__":
    sys.exit(main())
