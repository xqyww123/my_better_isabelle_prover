"""Core patching logic: apply, reverse, and status detection."""

import logging
import os
import shutil
import subprocess
import sys
from enum import Enum
from pathlib import Path

from my_better_isabelle_prover.patches import PatchInfo

log = logging.getLogger(__name__)


class PatchStatus(Enum):
    APPLIED = "applied"
    NOT_APPLIED = "not-applied"
    CONFLICT = "conflict"


def _ensure_patch_binary() -> None:
    if not shutil.which("patch"):
        print("Error: 'patch' command not found. Install it (e.g., apt install patch).", file=sys.stderr)
        sys.exit(1)


def check_status(isabelle_home: Path, patch: PatchInfo) -> PatchStatus:
    _ensure_patch_binary()
    reverse = subprocess.run(
        ["patch", "--dry-run", "-R", "-p1", "-F0", "-s", "-i", str(patch.patch_path)],
        cwd=isabelle_home, capture_output=True,
    )
    if reverse.returncode == 0:
        return PatchStatus.APPLIED
    forward = subprocess.run(
        ["patch", "--dry-run", "-p1", "-F0", "-s", "-i", str(patch.patch_path)],
        cwd=isabelle_home, capture_output=True,
    )
    if forward.returncode == 0:
        return PatchStatus.NOT_APPLIED
    return PatchStatus.CONFLICT


def _make_writable(path: Path) -> int | None:
    """chmod u+w and return the original mode, or None if the file doesn't exist."""
    if not path.exists():
        return None
    original = path.stat().st_mode
    os.chmod(path, original | 0o200)
    return original


def _restore_mode(path: Path, mode: int | None) -> None:
    if mode is not None and path.exists():
        os.chmod(path, mode)


def apply_patch(
    isabelle_home: Path,
    patch: PatchInfo,
    *,
    dry_run: bool = False,
    reverse: bool = False,
    force: bool = False,
) -> bool:
    status = check_status(isabelle_home, patch)
    action = "Reversing" if reverse else "Applying"

    if not reverse and status == PatchStatus.APPLIED and not force:
        log.info("  [skip] %s/%s — already applied", patch.feature, patch.patch_path.name)
        return True
    if reverse and status == PatchStatus.NOT_APPLIED and not force:
        log.info("  [skip] %s/%s — not applied", patch.feature, patch.patch_path.name)
        return True
    if status == PatchStatus.CONFLICT and not force:
        log.error(
            "  [CONFLICT] %s/%s — target file has conflicting modifications",
            patch.feature, patch.patch_path.name,
        )
        return False

    cmd = ["patch", "-p1", "-F0", "-i", str(patch.patch_path)]
    if reverse:
        cmd.insert(1, "-R")
    if dry_run:
        cmd.insert(1, "--dry-run")

    target_file = isabelle_home / patch.target_relative
    original_mode = None
    if not dry_run:
        original_mode = _make_writable(target_file)

    log.info("  %s %s/%s%s", action, patch.feature, patch.patch_path.name,
             " (dry-run)" if dry_run else "")
    try:
        proc = subprocess.run(cmd, cwd=isabelle_home, capture_output=True, text=True)
    finally:
        if not dry_run:
            _restore_mode(target_file, original_mode)

    if proc.returncode != 0:
        log.error("  FAILED: %s", proc.stderr.strip() or proc.stdout.strip())
        return False
    return True


def apply_all(
    isabelle_home: Path,
    patches: list[PatchInfo],
    *,
    dry_run: bool = False,
    reverse: bool = False,
    force: bool = False,
) -> bool:
    if not patches:
        log.warning("No patches to apply.")
        return True
    # patches arrive in dependency apply order; unpatch must undo in reverse.
    seq = list(reversed(patches)) if reverse else patches
    success = True
    for patch in seq:
        if not apply_patch(isabelle_home, patch, dry_run=dry_run, reverse=reverse, force=force):
            success = False
            if not force:
                log.error("Stopping. Use --force to continue past failures.")
                break
    return success


def print_status(
    isabelle_home: Path,
    patches: list[PatchInfo],
    selected: list[PatchInfo] | None = None,
) -> bool:
    """Print the status of every patch in `patches`; report whether `selected` is
    fully applied.

    Display and verdict are deliberately decoupled: `status` always lists every
    feature (hiding the opted-out ones would misrepresent the install), while the
    exit code speaks only for the patches the caller selected.
    """
    gated = {p.patch_path for p in (patches if selected is None else selected)}
    applied: dict[str, int] = {}
    total: dict[str, int] = {}
    all_applied = True

    for patch in patches:
        status = check_status(isabelle_home, patch)
        marker = {
            PatchStatus.APPLIED: "applied",
            PatchStatus.NOT_APPLIED: "not-applied",
            PatchStatus.CONFLICT: "CONFLICT",
        }[status]
        if status != PatchStatus.APPLIED and patch.patch_path in gated:
            all_applied = False
        total[patch.category] = total.get(patch.category, 0) + 1
        if status == PatchStatus.APPLIED:
            applied[patch.category] = applied.get(patch.category, 0) + 1
        target = patch.target_relative
        print(f"  [{marker:>11s}]  {patch.category:<4s}  "
              f"{patch.feature}/{patch.patch_path.name}  ({target})")

    summary = " · ".join(
        f"{cat}: {applied.get(cat, 0)}/{total[cat]} applied" for cat in sorted(total)
    )
    if summary:
        print(f"  {summary}")
    return all_applied
