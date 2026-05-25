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


def discover_patches(version: str, feature: str | None = None) -> list[PatchInfo]:
    version_dir = PATCHES_DIR / version
    if not version_dir.is_dir():
        return []
    features = [feature] if feature else available_features(version)
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
