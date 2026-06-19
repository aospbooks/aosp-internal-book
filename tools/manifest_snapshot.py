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
import fnmatch
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
    clone_depth: str | None = None


@dataclass(frozen=True)
class Snapshot:
    snap_dir: Path
    manifest_xml: Path
    metadata: dict
    default_revision: str
    default_remote: str
    projects: dict[str, Project]


@dataclass(frozen=True)
class CompareCtx:
    a_branch: str
    a_date: str
    b_branch: str
    b_date: str
    generated: str
    changes_file: str = ""
    added_removed_file: str = ""


@dataclass(frozen=True)
class MovedEntry:
    name: str
    path: str
    groups: tuple[str, ...]
    old_sha: str
    new_sha: str
    commits: list[str] | None   # None => SHAs unreachable locally
    url: str                    # googlesource +log/old..new


@dataclass(frozen=True)
class SkippedEntry:
    name: str
    path: str
    old_sha: str | None
    new_sha: str | None
    reason: str


@dataclass(frozen=True)
class SideEntry:                # an added or removed project
    name: str
    path: str
    groups: tuple[str, ...]
    sha: str
    side: str                   # "added" or "removed"
    history: list[str] | None   # None => unreachable; ignored if reason set
    url: str
    reason: str | None          # skip reason, or None


@dataclass(frozen=True)
class HistoryEntry:              # one repo's full history for a single version
    name: str
    path: str
    groups: tuple[str, ...]
    sha: str
    commits: list[str] | None    # None => SHA unreachable locally
    url: str


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
        clone_depth = el.get("clone-depth")
        projects[name] = Project(
            name=name, path=path, revision=revision,
            groups=groups, remote=remote, clone_depth=clone_depth,
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
    """Return `git log --no-merges --pretty=oneline <old>..<new>` as a list of
    lines (full SHA + subject), or None if the git dir is missing or either SHA
    is unreachable.

    Strictly read-only: only invokes `git log`.
    """
    git_dir = Path(git_dir)
    if not git_dir.exists():
        return None
    proc = subprocess.run(
        ["git", f"--git-dir={git_dir}", "log", "--no-merges",
         "--pretty=oneline", f"{old}..{new}"],
        capture_output=True, text=True, errors="replace",
    )
    if proc.returncode != 0:
        return None
    return [line for line in proc.stdout.split("\n") if line.strip()]


def full_history(git_dir: Path, sha: str) -> list[str] | None:
    """Return `git log --no-merges --pretty=oneline <sha>` lines (full history
    reachable from `sha`), or None if the git dir is missing or `sha` is
    unreachable. Strictly read-only: only invokes `git log`."""
    git_dir = Path(git_dir)
    if not git_dir.exists():
        return None
    proc = subprocess.run(
        ["git", f"--git-dir={git_dir}", "log", "--no-merges",
         "--pretty=oneline", sha],
        capture_output=True, text=True, errors="replace",
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


def googlesource_log_url(project_name: str, sha: str) -> str:
    """Googlesource +log link for browsing a project's history up to one SHA."""
    return f"{GOOGLESOURCE}/{project_name}/+log/{sha}"


def load_ignore_globs(ignore_file: Path | None, cli_globs: list[str]) -> list[str]:
    """Merge ignore globs from a file (one per line, '#' comments and blank
    lines skipped, surrounding whitespace stripped) with CLI-supplied globs.
    Order is preserved (file first, then CLI); duplicates removed."""
    globs: list[str] = []
    if ignore_file and Path(ignore_file).is_file():
        for raw in Path(ignore_file).read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line and not line.startswith("#"):
                globs.append(line)
    globs.extend(cli_globs or [])
    seen: set[str] = set()
    out: list[str] = []
    for g in globs:
        if g not in seen:
            seen.add(g)
            out.append(g)
    return out


def skip_reason(
    proj_a: "Project | None",
    proj_b: "Project | None",
    aosp_root: Path,
    ignore_globs: list[str],
    skip_shallow: bool = True,
) -> str | None:
    """Return a reason string if this project should be skipped, else None.

    Order (first match wins): ignore-glob on the project path; then, when
    `skip_shallow`, a `clone-depth` attribute on either snapshot's entry; then
    a live `.repo/projects/<path>.git/shallow` marker."""
    proj = proj_b or proj_a
    if proj is None:
        return None
    path = proj.path
    for pat in ignore_globs:
        if fnmatch.fnmatch(path, pat):
            return f"glob:{pat}"
    if skip_shallow:
        for p in (proj_a, proj_b):
            if p is not None and p.clone_depth:
                return f"clone-depth={p.clone_depth}"
        marker = Path(aosp_root) / ".repo" / "projects" / f"{path}.git" / "shallow"
        if marker.is_file():
            return "shallow-marker"
    return None


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


_SEP = "=" * 64
_SUB = "-" * 64


def render_changes_txt(ctx: CompareCtx, moved: list[MovedEntry], counts: dict) -> str:
    """Kernel-changelog-style aggregate of every moved project's commits."""
    lines: list[str] = [
        f"AOSP changes: {ctx.a_branch} @ {ctx.a_date}  ->  {ctx.b_branch} @ {ctx.b_date}",
        f"Generated: {ctx.generated}",
        (f"Moved: {counts['moved']}   Skipped (shallow/ignored): {counts['skipped']}"
         f"   Added: {counts['added']}   Removed: {counts['removed']}"),
        "",
    ]
    for m in moved:
        lines.append(_SEP)
        lines.append(f"{m.path}   ({m.name})")
        if m.commits is None:
            lines.append(f"old {m.old_sha}  ->  new {m.new_sha}")
            lines.append(_SUB)
            lines.append(f"# unreachable locally; see {m.url}")
        else:
            n = len(m.commits)
            lines.append(f"old {m.old_sha}  ->  new {m.new_sha}"
                         f"   ({n} commit{'s' if n != 1 else ''})")
            lines.append(_SUB)
            lines.extend(m.commits)
        lines.append("")
    return "\n".join(lines) + "\n"


def render_added_removed_txt(ctx: CompareCtx, added: list[SideEntry],
                             removed: list[SideEntry]) -> str:
    """Added/removed projects, each with full inline history (or a reason /
    fallback line). One file covering both sides."""
    lines: list[str] = [
        f"AOSP added/removed projects: {ctx.a_branch} @ {ctx.a_date}"
        f"  ->  {ctx.b_branch} @ {ctx.b_date}",
        f"Generated: {ctx.generated}",
        "",
    ]
    for title, entries in (("ADDED", added), ("REMOVED", removed)):
        lines.append("#" * 64)
        lines.append(f"## {title} ({len(entries)})")
        lines.append("#" * 64)
        lines.append("")
        for e in entries:
            groups = ", ".join(e.groups) if e.groups else "<none>"
            lines.append(_SEP)
            lines.append(f"{e.path}   ({e.name})")
            lines.append(f"side: {e.side}   sha: {e.sha}   groups: {groups}")
            lines.append(f"link: {e.url}")
            if e.reason:
                lines.append(f"skipped ({e.reason}); history omitted")
            elif e.history is None:
                lines.append(f"# unreachable locally; see {e.url}")
            else:
                lines.append(_SUB)
                lines.extend(e.history)
            lines.append("")
    return "\n".join(lines) + "\n"


def _group_moved(moved: list[MovedEntry]) -> dict[str, list[MovedEntry]]:
    """Bucket moved entries under every group they declare (UNGROUPED if none).
    Groups sorted alphabetically; entries within a group sorted by path."""
    buckets: dict[str, list[MovedEntry]] = {}
    for m in moved:
        for g in (list(m.groups) if m.groups else [UNGROUPED]):
            buckets.setdefault(g, []).append(m)
    return {g: sorted(buckets[g], key=lambda e: e.path) for g in sorted(buckets)}


def render_report_md(ctx: CompareCtx, moved: list[MovedEntry],
                     skipped: list[SkippedEntry], added: list[SideEntry],
                     removed: list[SideEntry], counts: dict) -> str:
    """Human navigator: summary, moved-by-group (counts + links, no inline
    commits), skipped list, and added/removed summary tables."""
    lines: list[str] = [
        f"# Manifest comparison: {ctx.a_branch} @ {ctx.a_date}"
        f"  ->  {ctx.b_branch} @ {ctx.b_date}",
        "",
        f"Generated: {ctx.generated}",
        "",
        "## Summary",
        "| Category | Count |",
        "|---|---|",
        f"| Moved (SHA changed) | {counts['moved']} |",
        f"| Added | {counts['added']} |",
        f"| Removed | {counts['removed']} |",
        f"| Unchanged | {counts['unchanged']} |",
        f"| Skipped (shallow/ignored) | {counts['skipped']} |",
        f"| Total commits across moved projects | {counts['total_commits']} |",
        "",
        f"Per-project commit lists: `{ctx.changes_file}`. "
        f"Added/removed histories: `{ctx.added_removed_file}`.",
        "",
        "## Moved projects by module group",
        "",
    ]
    for group_name, entries in _group_moved(moved).items():
        lines.append(f"### Group: {group_name}")
        lines.append(f"*{len(entries)} project(s) changed in this group.*")
        lines.append("")
        lines.append("| Project | Path | old to new | Commits | Compare |")
        lines.append("|---|---|---|---|---|")
        for m in entries:
            ncol = str(len(m.commits)) if m.commits is not None else "unreachable"
            lines.append(
                f"| {m.name} | `{m.path}` | `{_short(m.old_sha)}` to "
                f"`{_short(m.new_sha)}` | {ncol} | <{m.url}> |")
        lines.append("")

    lines.append("## Skipped projects (shallow / ignored)")
    lines.append("| Project | Path | old to new | Reason |")
    lines.append("|---|---|---|---|")
    for s in skipped:
        lines.append(
            f"| {s.name} | `{s.path}` | `{_short(s.old_sha or '')}` to "
            f"`{_short(s.new_sha or '')}` | {s.reason} |")
    lines.append("")

    for title, entries in (("Added", added), ("Removed", removed)):
        lines.append(f"## {title} projects")
        lines.append("| Project | Path | SHA | Groups |")
        lines.append("|---|---|---|---|")
        for e in entries:
            groups = ", ".join(e.groups) if e.groups else "-"
            lines.append(f"| {e.name} | `{e.path}` | `{_short(e.sha)}` | {groups} |")
        lines.append("")
    return "\n".join(lines) + "\n"


def render_analysis_prompt(ctx: CompareCtx, counts: dict) -> str:
    """A ready-to-paste prompt that frames the changelog files for an LLM."""
    return (
        "You are analyzing what changed in AOSP between two release snapshots.\n"
        f"  A: {ctx.a_branch} @ {ctx.a_date}\n"
        f"  B: {ctx.b_branch} @ {ctx.b_date}\n\n"
        f"Scope: {counts['moved']} projects changed "
        f"({counts['total_commits']} commits total), {counts['added']} added, "
        f"{counts['removed']} removed, {counts['skipped']} skipped "
        "(shallow/vendored, not analyzable).\n\n"
        "Inputs (read these sibling files):\n"
        f"  - {ctx.changes_file}: per-repository commit lists (full SHA + subject),\n"
        "    one section per project, ordered by path.\n"
        f"  - {ctx.added_removed_file}: full history of added and removed projects.\n\n"
        "Task:\n"
        "  1. Summarize the notable changes per subsystem / module group.\n"
        "  2. Call out new capabilities, removed or deprecated components, and any\n"
        "     large refactors (projects with unusually high commit counts).\n"
        "  3. List the added and removed projects and infer why they appeared or\n"
        "     disappeared between the two versions.\n"
        "Cite the project paths and commit subjects you rely on.\n"
    )


def render_history_txt(branch: str, date: str, generated: str,
                       entries: list[HistoryEntry], skipped: list[SkippedEntry],
                       counts: dict) -> str:
    """Kernel-changelog-style full per-repo history for a single version."""
    lines: list[str] = [
        f"AOSP history: {branch} @ {date}",
        f"Generated: {generated}",
        (f"Repositories: {counts['repos']}   "
         f"Skipped (shallow/ignored): {counts['skipped']}   "
         f"Total commits: {counts['total_commits']}"),
        "",
    ]
    if skipped:
        lines.append("## Skipped (shallow/ignored)")
        for s in skipped:
            lines.append(f"{s.path}   {s.reason}")
        lines.append("")
    for e in entries:
        lines.append(_SEP)
        lines.append(f"{e.path}   ({e.name})")
        if e.commits is None:
            lines.append(f"sha {e.sha}")
            lines.append(_SUB)
            lines.append(f"# unreachable locally; see {e.url}")
        else:
            n = len(e.commits)
            lines.append(f"sha {e.sha}   ({n} commit{'s' if n != 1 else ''})")
            lines.append(_SUB)
            lines.extend(e.commits)
        lines.append("")
    return "\n".join(lines) + "\n"


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


def compare_key(a: Snapshot, b: Snapshot) -> str:
    """Filename-safe key identifying a comparison: <A>__vs__<B> where each side
    is `<branch>_<snapshot-date>`."""
    return f"{_snap_key(a)}__vs__{_snap_key(b)}"


def emit_progress(enabled: bool, i: int, total: int, label: str) -> None:
    """Print a one-line `[ i/total ] label` progress message to stderr (flushed),
    or nothing when disabled. Progress never touches stdout or output files."""
    if enabled:
        print(f"[ {i}/{total} ] {label}", file=sys.stderr, flush=True)


def _side_entries(names: list[str], snap: Snapshot, aosp_root: Path,
                  ignore_globs: list[str], skip_shallow: bool,
                  side: str, *, progress: bool = False) -> list[SideEntry]:
    """Build SideEntry records (full history unless skipped/unreachable) for the
    added (side='added', uses B snapshot) or removed (side='removed', uses A)
    projects."""
    out: list[SideEntry] = []
    total = len(names)
    for i, name in enumerate(names, start=1):
        p = snap.projects[name]
        url = googlesource_log_url(name, p.revision)
        reason = skip_reason(p, p, aosp_root, ignore_globs, skip_shallow)
        history = None
        if reason is None:
            git_dir = aosp_root / ".repo" / "projects" / f"{p.path}.git"
            history = full_history(git_dir, p.revision)
        if reason:
            detail = f"skipped: {reason}"
        elif history is None:
            detail = "unreachable"
        else:
            detail = f"{len(history)} commits"
        emit_progress(progress, i, total, f"{p.path}  ({detail}) ({side})")
        out.append(SideEntry(name=name, path=p.path, groups=p.groups,
                             sha=p.revision, side=side, history=history,
                             url=url, reason=reason))
    out.sort(key=lambda e: e.path)
    return out


def cmd_compare(args) -> int:
    a = load_snapshot(Path(args.a))
    b = load_snapshot(Path(args.b))
    aosp_root = resolve_aosp_root(
        flag=args.aosp_root, env=os.environ.get("AOSP_ROOT"), start=Path.cwd(),
    )
    cls = classify(a.projects, b.projects)
    ignore_globs = load_ignore_globs(
        Path(args.ignore_file) if args.ignore_file else None,
        args.ignore_glob or [],
    )
    skip_shallow = not args.no_skip_shallow

    moved: list[MovedEntry] = []
    skipped: list[SkippedEntry] = []
    total_commits = 0
    progress = not args.no_progress
    moved_total = len(cls["moved"])
    for i, name in enumerate(cls["moved"], start=1):
        pa, pb = a.projects[name], b.projects[name]
        reason = skip_reason(pa, pb, aosp_root, ignore_globs, skip_shallow)
        if reason:
            skipped.append(SkippedEntry(name, pb.path, pa.revision,
                                        pb.revision, reason))
            emit_progress(progress, i, moved_total, f"{pb.path}  (skipped: {reason})")
            continue
        git_dir = aosp_root / ".repo" / "projects" / f"{pb.path}.git"
        commits = commits_between(git_dir, pa.revision, pb.revision)
        if commits is None:
            emit_progress(progress, i, moved_total, f"{pb.path}  (unreachable)")
        else:
            total_commits += len(commits)
            emit_progress(progress, i, moved_total, f"{pb.path}  ({len(commits)} commits)")
        moved.append(MovedEntry(
            name=name, path=pb.path, groups=pb.groups,
            old_sha=pa.revision, new_sha=pb.revision, commits=commits,
            url=googlesource_url(name, pa.revision, pb.revision),
        ))
    moved.sort(key=lambda m: m.path)
    skipped.sort(key=lambda s: s.path)

    added = _side_entries(cls["added"], b, aosp_root, ignore_globs,
                          skip_shallow, "added", progress=progress)
    removed = _side_entries(cls["removed"], a, aosp_root, ignore_globs,
                            skip_shallow, "removed", progress=progress)

    counts = {
        "moved": len(moved), "skipped": len(skipped),
        "added": len(added), "removed": len(removed),
        "unchanged": len(cls["unchanged"]), "total_commits": total_commits,
    }

    key = compare_key(a, b)
    out_dir = (Path(args.out_dir) if args.out_dir
               else Path("manifest-snapshots") / "_compare")
    out_dir.mkdir(parents=True, exist_ok=True)
    ctx = CompareCtx(
        a_branch=a.default_revision, a_date=a.snap_dir.name,
        b_branch=b.default_revision, b_date=b.snap_dir.name,
        generated=_dt.datetime.now(_dt.timezone.utc).isoformat(),
        changes_file=f"{key}.changes.txt",
        added_removed_file=f"{key}.added-removed.txt",
    )
    (out_dir / f"{key}.report.md").write_text(
        render_report_md(ctx, moved, skipped, added, removed, counts))
    (out_dir / f"{key}.changes.txt").write_text(
        render_changes_txt(ctx, moved, counts))
    (out_dir / f"{key}.added-removed.txt").write_text(
        render_added_removed_txt(ctx, added, removed))
    (out_dir / f"{key}.analysis-prompt.txt").write_text(
        render_analysis_prompt(ctx, counts))
    print(f"Wrote 4 files to {out_dir!s} (prefix {key})")
    return 0


def cmd_history(args, *, now=None) -> int:
    now = now if now is not None else _dt.datetime.now(_dt.timezone.utc)
    aosp_root = resolve_aosp_root(
        flag=args.aosp_root, env=os.environ.get("AOSP_ROOT"), start=Path.cwd(),
    )
    if shutil.which("repo") is None:
        print("`repo` command not found. Install the AOSP repo launcher and re-run.",
              file=sys.stderr)
        return 3
    try:
        proc = subprocess.run(
            ["repo", "manifest", "-r", "--pretty"],
            cwd=str(aosp_root), capture_output=True, text=True,
        )
    except FileNotFoundError as e:
        print(f"failed to run repo: {e}", file=sys.stderr)
        return 3
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
        print("`repo manifest -r` failed.", file=sys.stderr)
        return 4
    default_rev, _remote, projects = parse_manifest(proc.stdout)

    ignore_globs = load_ignore_globs(
        Path(args.ignore_file) if args.ignore_file else None,
        args.ignore_glob or [],
    )
    skip_shallow = not args.no_skip_shallow

    entries: list[HistoryEntry] = []
    skipped: list[SkippedEntry] = []
    total_commits = 0
    progress = not args.no_progress
    names = sorted(projects, key=lambda n: projects[n].path)
    total = len(names)
    for i, name in enumerate(names, start=1):
        p = projects[name]
        reason = skip_reason(p, p, aosp_root, ignore_globs, skip_shallow)
        if reason:
            skipped.append(SkippedEntry(name, p.path, p.revision, None, reason))
            emit_progress(progress, i, total, f"{p.path}  (skipped: {reason})")
            continue
        git_dir = aosp_root / ".repo" / "projects" / f"{p.path}.git"
        commits = full_history(git_dir, p.revision)
        if commits is None:
            emit_progress(progress, i, total, f"{p.path}  (unreachable)")
        else:
            total_commits += len(commits)
            emit_progress(progress, i, total, f"{p.path}  ({len(commits)} commits)")
        entries.append(HistoryEntry(
            name=name, path=p.path, groups=p.groups, sha=p.revision,
            commits=commits, url=googlesource_log_url(name, p.revision),
        ))
    skipped.sort(key=lambda s: s.path)

    counts = {"repos": len(projects), "skipped": len(skipped),
              "total_commits": total_commits}
    date = now.date().isoformat()
    out_dir = (Path(args.out_dir) if args.out_dir
               else Path("manifest-snapshots") / "_history")
    out_dir.mkdir(parents=True, exist_ok=True)
    # The manifest default revision can be a full ref (e.g.
    # refs/tags/android-16.0.0_r4); strip ref prefixes and flatten any
    # remaining slashes so it forms a single safe filename, not nested dirs.
    slug = (default_rev.removeprefix("refs/heads/").removeprefix("refs/tags/")
            .replace("/", "-"))
    out_path = out_dir / f"{slug}_{date}.history.txt"
    out_path.write_text(render_history_txt(
        default_rev, date, now.isoformat(), entries, skipped, counts))
    print(f"Wrote {out_path!s} ({len(entries)} repos logged, {len(skipped)} skipped)")
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
        "--out-dir", default=None,
        help="directory for the four <KEY>.* output files "
             "(default: manifest-snapshots/_compare/)",
    )
    cmp.add_argument(
        "--ignore-glob", action="append", default=[], metavar="GLOB",
        help="path glob for projects to skip; repeatable",
    )
    cmp.add_argument(
        "--ignore-file", default="manifest-snapshots/ignore-globs.txt",
        help="file of ignore globs (one per line, '#' comments); "
             "missing file is fine",
    )
    cmp.add_argument(
        "--no-skip-shallow", action="store_true",
        help="don't auto-skip clone-depth / shallow-marker projects",
    )
    cmp.add_argument(
        "--no-progress", action="store_true",
        help="suppress per-repo progress on stderr",
    )

    hist = sub.add_parser(
        "history", help="dump full per-repo commit history of one version")
    hist.add_argument("--aosp-root", default=None,
                      help="path to AOSP checkout (containing .repo/)")
    hist.add_argument("--out-dir", default=None,
                      help="directory for the <branch>_<date>.history.txt file "
                           "(default: manifest-snapshots/_history/)")
    hist.add_argument("--ignore-glob", action="append", default=[], metavar="GLOB",
                      help="path glob for projects to skip; repeatable")
    hist.add_argument("--ignore-file", default="manifest-snapshots/ignore-globs.txt",
                      help="file of ignore globs (one per line, '#' comments); "
                           "missing file is fine")
    hist.add_argument("--no-skip-shallow", action="store_true",
                      help="don't auto-skip clone-depth / shallow-marker projects")
    hist.add_argument("--no-progress", action="store_true",
                      help="suppress per-repo progress on stderr")

    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.cmd == "snap":
        return cmd_snap(args)
    if args.cmd == "compare":
        return cmd_compare(args)
    if args.cmd == "history":
        return cmd_history(args)
    parser.error(f"unknown command: {args.cmd}")


if __name__ == "__main__":
    sys.exit(main())
