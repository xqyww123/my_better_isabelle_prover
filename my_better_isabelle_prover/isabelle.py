"""Isabelle binary detection, version querying, and build invocation."""

import logging
import shutil
import subprocess
import sys
from pathlib import Path

log = logging.getLogger(__name__)


def resolve_isabelle_bin(explicit: str | None = None) -> Path:
    if explicit:
        p = Path(explicit)
        if not p.is_file():
            print(f"Error: specified isabelle binary not found: {p}", file=sys.stderr)
            sys.exit(1)
        return p
    found = shutil.which("isabelle")
    if not found:
        print(
            "Error: 'isabelle' not found on PATH.\n"
            "  Use --isabelle-bin to specify the path, or add isabelle to your PATH.",
            file=sys.stderr,
        )
        sys.exit(1)
    return Path(found)


def get_version(isa_bin: Path) -> str:
    try:
        result = subprocess.run(
            [str(isa_bin), "version"],
            capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"Error: 'isabelle version' failed: {e.stderr.strip() or e}", file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()


def get_home(isa_bin: Path) -> Path:
    try:
        result = subprocess.run(
            [str(isa_bin), "getenv", "-b", "ISABELLE_HOME"],
            capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"Error: 'isabelle getenv' failed: {e.stderr.strip() or e}", file=sys.stderr)
        sys.exit(1)
    home = Path(result.stdout.strip())
    if not home.is_dir():
        print(f"Error: ISABELLE_HOME is not a directory: {home}", file=sys.stderr)
        sys.exit(1)
    return home


def scala_build(isa_bin: Path) -> bool:
    log.info("Running isabelle scala_build -f ...")
    proc = subprocess.run(
        [str(isa_bin), "scala_build", "-f"],
        stdout=sys.stdout, stderr=sys.stderr,
    )
    if proc.returncode != 0:
        log.error("isabelle scala_build failed (exit code %d)", proc.returncode)
        return False
    log.info("Build succeeded.")
    return True
