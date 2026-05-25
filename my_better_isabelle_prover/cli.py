"""CLI entry point for my-better-isabelle."""

import argparse
import logging
import sys

from my_better_isabelle_prover import isabelle, patcher
from my_better_isabelle_prover.patches import available_features, available_versions, discover_patches


def _resolve(args) -> tuple:
    """Resolve isabelle binary, version, home, and patches from CLI args."""
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

    patches = discover_patches(version, feature)
    if not patches:
        print(f"No patches found for {version}" + (f" feature={feature}" if feature else ""))
        sys.exit(0)

    return isa_bin, version, home, patches


def cmd_patch(args) -> None:
    isa_bin, version, home, patches = _resolve(args)
    ok = patcher.apply_all(home, patches, dry_run=args.dry_run, force=args.force)
    if not ok:
        sys.exit(1)
    if not args.dry_run and not args.no_build:
        if not isabelle.scala_build(isa_bin):
            sys.exit(2)


def cmd_unpatch(args) -> None:
    isa_bin, version, home, patches = _resolve(args)
    ok = patcher.apply_all(home, patches, dry_run=args.dry_run, reverse=True, force=args.force)
    if not ok:
        sys.exit(1)
    if not args.dry_run and not args.no_build:
        if not isabelle.scala_build(isa_bin):
            sys.exit(2)


def cmd_status(args) -> None:
    _isa_bin, version, home, patches = _resolve(args)
    print(f"Patch status for {version}:")
    all_clean = patcher.print_status(home, patches)
    if not all_clean:
        sys.exit(1)


def cmd_build(args) -> None:
    isa_bin = isabelle.resolve_isabelle_bin(getattr(args, "isabelle_bin", None))
    if not isabelle.scala_build(isa_bin):
        sys.exit(2)


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
    p_patch.add_argument("--no-build", action="store_true", help="Skip isabelle scala_build after patching")
    p_patch.add_argument("--force", action="store_true", help="Continue past conflicts/failures")

    p_unpatch = subs.add_parser("unpatch", help="Reverse patches")
    p_unpatch.add_argument("--dry-run", action="store_true", help="Check without modifying files")
    p_unpatch.add_argument("--feature", metavar="NAME", help="Only reverse patches for this feature")
    p_unpatch.add_argument("--no-build", action="store_true", help="Skip isabelle scala_build after unpatching")
    p_unpatch.add_argument("--force", action="store_true", help="Continue past conflicts/failures")

    p_status = subs.add_parser("status", help="Show patch status")
    p_status.add_argument("--feature", metavar="NAME", help="Only show status for this feature")

    subs.add_parser("build", help="Run isabelle scala_build -f")

    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.WARNING if args.quiet else logging.INFO
    logging.basicConfig(format="%(message)s", level=level)

    dispatch = {
        "patch": cmd_patch,
        "unpatch": cmd_unpatch,
        "status": cmd_status,
        "build": cmd_build,
    }
    dispatch[args.command](args)
