"""Patch discovery for version-specific Isabelle patches."""

import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

PATCHES_DIR = Path(__file__).parent
CATEGORIES_FILE = PATCHES_DIR / "categories.toml"

CATEGORIES = ("user", "dev")

#: Exit code for a broken patch repository (unregistered feature, bad category).
CONFIG_ERROR = 3


@dataclass
class PatchInfo:
    feature: str
    category: str
    target_relative: str
    patch_path: Path


def _config_error(*lines: str) -> None:
    print("\n".join(lines), file=sys.stderr)
    sys.exit(CONFIG_ERROR)


def available_versions() -> list[str]:
    return sorted(
        d.name for d in PATCHES_DIR.iterdir()
        if d.is_dir() and not d.name.startswith("_")
    )


def _feature_dirs(version: str) -> list[str]:
    version_dir = PATCHES_DIR / version
    if not version_dir.is_dir():
        return []
    return sorted(
        d.name for d in version_dir.iterdir()
        if d.is_dir() and not d.name.startswith(("_", "."))
    )


def _category_table() -> dict[str, str]:
    with open(CATEGORIES_FILE, "rb") as f:
        table = tomllib.load(f).get("features", {})
    bad = sorted(f for f, c in table.items() if c not in CATEGORIES)
    if bad:
        _config_error(
            f"Error: {CATEGORIES_FILE.name} gives an unknown category to: {', '.join(bad)}.",
            f"  Valid categories: {', '.join(CATEGORIES)}",
        )
    return table


def feature_categories(version: str) -> dict[str, str]:
    """Category of every feature directory of `version`.

    A feature directory that is not registered in categories.toml is a hard error:
    guessing would silently ship an unvetted patch (or silently withhold a needed
    one). The reverse — a registered feature with no directory for this version —
    is normal: `register_thy` and `expose_foreign` are Isabelle2025-2 only.
    """
    table = _category_table()
    feats = _feature_dirs(version)
    missing = [f for f in feats if f not in table]
    if missing:
        _config_error(
            f"Error: feature(s) not registered in {CATEGORIES_FILE.name}: {', '.join(missing)}.",
            f"  Add each to the [features] table with a category ({', '.join(CATEGORIES)}).",
        )
    return {f: table[f] for f in feats}


def available_features(version: str) -> list[str]:
    return sorted(feature_categories(version))


def read_order(version: str) -> list[str]:
    """Read the optional per-version apply-order file (one feature name per line,
    '#' comments and blank lines ignored). Earlier = applied earlier."""
    order_file = PATCHES_DIR / version / "order.txt"
    if not order_file.is_file():
        return []
    order = []
    for line in order_file.read_text().splitlines():
        name = line.split("#", 1)[0].strip()
        if name:
            order.append(name)
    return order


def ordered_features(version: str) -> list[str]:
    """Features in dependency apply order: those listed in order.txt first (in that
    order), then any remaining features alphabetically. Unpatch reverses this."""
    feats = available_features(version)
    order = read_order(version)
    ranked = [f for f in order if f in feats]
    rest = sorted(f for f in feats if f not in ranked)
    return ranked + rest


def discover_patches(version: str) -> list[PatchInfo]:
    """Every patch of `version`, in apply order. Filter with `select` in the CLI."""
    categories = feature_categories(version)
    patches = []
    for feat in ordered_features(version):
        feat_dir = PATCHES_DIR / version / feat
        for patch_file in sorted(feat_dir.glob("*.patch")):
            stem = patch_file.stem  # e.g. "lsp.scala"
            header = _read_patch_target(patch_file, stem)
            patches.append(PatchInfo(
                feature=feat,
                category=categories[feat],
                target_relative=header,
                patch_path=patch_file,
            ))
    return patches


def _read_patch_target(patch_path: Path, fallback_stem: str) -> str:
    """Extract the target file path from the unified diff --- line."""
    with open(patch_path) as f:
        for line in f:
            if line.startswith("--- a/"):
                return line[6:].strip().split("\t")[0]
    return fallback_stem
