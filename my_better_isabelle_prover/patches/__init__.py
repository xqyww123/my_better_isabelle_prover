"""Patch discovery for version-specific Isabelle patches."""

from dataclasses import dataclass
from pathlib import Path

PATCHES_DIR = Path(__file__).parent


@dataclass
class PatchInfo:
    feature: str
    target_relative: str
    patch_path: Path


def available_versions() -> list[str]:
    return sorted(
        d.name for d in PATCHES_DIR.iterdir()
        if d.is_dir() and not d.name.startswith("_")
    )


def available_features(version: str) -> list[str]:
    version_dir = PATCHES_DIR / version
    if not version_dir.is_dir():
        return []
    return sorted(d.name for d in version_dir.iterdir() if d.is_dir())


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


def discover_patches(version: str, feature: str | None = None) -> list[PatchInfo]:
    version_dir = PATCHES_DIR / version
    if not version_dir.is_dir():
        return []
    features = [feature] if feature else ordered_features(version)
    patches = []
    for feat in features:
        feat_dir = version_dir / feat
        if not feat_dir.is_dir():
            continue
        for patch_file in sorted(feat_dir.glob("*.patch")):
            stem = patch_file.stem  # e.g. "lsp.scala"
            header = _read_patch_target(patch_file, stem)
            patches.append(PatchInfo(
                feature=feat,
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
