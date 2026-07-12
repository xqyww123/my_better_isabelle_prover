"""CLI entry point for my-better-isabelle."""

import argparse
import logging
import sys
from pathlib import Path

from my_better_isabelle_prover import isabelle, patcher
from my_better_isabelle_prover.patches import (
    CATEGORIES,
    PatchInfo,
    available_features,
    available_versions,
    discover_patches,
)


def _resolve_isabelle(args) -> tuple:
    """Resolve the isabelle binary, its version, and ISABELLE_HOME."""
    isa_bin = isabelle.resolve_isabelle_bin(getattr(args, "isabelle_bin", None))
    version = isabelle.get_version(isa_bin)
    home = isabelle.get_home(isa_bin)
    logging.getLogger(__name__).info("Isabelle %s at %s", version, home)

    versions = available_versions()
    if version not in versions:
        print(
            f"Error: no patches available for {version}.\n"
            f"  Available versions: {', '.join(versions) or '(none)'}",
            file=sys.stderr,
        )
        sys.exit(1)

    feature = getattr(args, "feature", None)
    if feature:
        feats = available_features(version)
        if feature not in feats:
            print(
                f"Error: unknown feature '{feature}' for {version}.\n"
                f"  Available features: {', '.join(feats) or '(none)'}",
                file=sys.stderr,
            )
            sys.exit(1)

    return isa_bin, version, home


def _select(patches: list[PatchInfo], args) -> list[PatchInfo]:
    """The patches this invocation acts on. An explicit --feature names exactly what
    the caller wants, so it wins over --category."""
    feature = getattr(args, "feature", None)
    if feature:
        return [p for p in patches if p.feature == feature]
    category = getattr(args, "category", "all")
    if category == "all":
        return list(patches)
    return [p for p in patches if p.category == category]


def _resolve(args) -> tuple:
    """Resolve isabelle, version, home, and the selected patches."""
    isa_bin, version, home = _resolve_isabelle(args)
    patches = _select(discover_patches(version), args)
    if not patches:
        scope = getattr(args, "feature", None) or getattr(args, "category", None)
        print(f"No patches found for {version}" + (f" ({scope})" if scope else ""))
        sys.exit(0)
    return isa_bin, version, home, patches


def _build_scala(isa_bin: Path, patches: list[PatchInfo], args) -> None:
    """Rebuild Scala, but only if this run actually touched a Scala source."""
    if args.dry_run or args.no_build:
        return
    if not any(p.target_relative.endswith(".scala") for p in patches):
        logging.getLogger(__name__).info(
            "No Scala sources touched; skipping isabelle scala_build.")
        return
    if not isabelle.scala_build(isa_bin):
        sys.exit(2)


def cmd_patch(args) -> None:
    isa_bin, _version, home, patches = _resolve(args)
    ok = patcher.apply_all(home, patches, dry_run=args.dry_run, force=args.force)
    if not ok:
        sys.exit(1)
    _build_scala(isa_bin, patches, args)


def cmd_unpatch(args) -> None:
    isa_bin, _version, home, patches = _resolve(args)
    ok = patcher.apply_all(home, patches, dry_run=args.dry_run, reverse=True, force=args.force)
    if not ok:
        sys.exit(1)
    _build_scala(isa_bin, patches, args)


def cmd_status(args) -> None:
    _isa_bin, version, home = _resolve_isabelle(args)
    patches = discover_patches(version)
    if not patches:
        print(f"No patches found for {version}")
        sys.exit(0)
    print(f"Patch status for {version}:")
    # Show every feature; gate the exit code on the selected ones only.
    all_applied = patcher.print_status(home, patches, _select(patches, args))
    if not all_applied:
        sys.exit(1)


def cmd_build(args) -> None:
    isa_bin = isabelle.resolve_isabelle_bin(getattr(args, "isabelle_bin", None))
    if not isabelle.scala_build(isa_bin):
        sys.exit(2)


def cmd_help(args) -> None:
    """Print the bundled agent/usage guide (AGENTS.md)."""
    guide = Path(__file__).parent / "AGENTS.md"
    print(guide.read_text(encoding="utf-8"), end="")


def _add_category(parser, default: str, action: str) -> None:
    parser.add_argument(
        "--category", choices=[*CATEGORIES, "all"], default=default,
        help=f"Which category to {action} (default: {default}). "
             "Ignored when --feature is given.",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="my-better-isabelle",
        description="Patch manager for Isabelle installations",
    )
    parser.add_argument(
        "--isabelle-bin", metavar="PATH",
        help="Path to isabelle binary (default: from PATH)",
    )
    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    verbosity.add_argument("-q", "--quiet", action="store_true", help="Only warnings and errors")

    subs = parser.add_subparsers(dest="command", required=True)

    p_patch = subs.add_parser("patch", help="Apply patches")
    p_patch.add_argument("--dry-run", action="store_true", help="Check without modifying files")
    p_patch.add_argument("--feature", metavar="NAME", help="Only apply patches for this feature")
    _add_category(p_patch, "user", "apply")
    p_patch.add_argument("--no-build", action="store_true", help="Skip isabelle scala_build after patching")
    p_patch.add_argument("--force", action="store_true", help="Continue past conflicts/failures")

    p_unpatch = subs.add_parser("unpatch", help="Reverse patches")
    p_unpatch.add_argument("--dry-run", action="store_true", help="Check without modifying files")
    p_unpatch.add_argument("--feature", metavar="NAME", help="Only reverse patches for this feature")
    _add_category(p_unpatch, "all", "reverse")
    p_unpatch.add_argument("--no-build", action="store_true", help="Skip isabelle scala_build after unpatching")
    p_unpatch.add_argument("--force", action="store_true", help="Continue past conflicts/failures")

    p_status = subs.add_parser("status", help="Show patch status")
    p_status.add_argument("--feature", metavar="NAME", help="Gate the exit code on this feature")
    _add_category(p_status, "user", "gate the exit code on")

    subs.add_parser("build", help="Run isabelle scala_build -f")

    subs.add_parser("help", help="Print the agent/usage guide (AGENTS.md)")

    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.WARNING if args.quiet else logging.INFO
    logging.basicConfig(format="%(message)s", level=level)

    dispatch = {
        "patch": cmd_patch,
        "unpatch": cmd_unpatch,
        "status": cmd_status,
        "build": cmd_build,
        "help": cmd_help,
    }
    dispatch[args.command](args)
