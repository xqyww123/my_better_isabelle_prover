# Developing & extending

This document covers how the patch manager works internally and how to add new
patches. For end-user CLI usage see [reference.md](reference.md).

## How it works

The manager is a thin, dependency-free wrapper around the system `patch` tool.
Everything is driven from the patch files on disk — there is no per-patch
configuration.

- **Version detection** — `isabelle version` gives the exact version string
  (e.g. `Isabelle2024`); `isabelle getenv -b ISABELLE_HOME` gives the install
  root. Patches are looked up under `patches/<version>/`. If the version has no
  directory, the command stops rather than guessing.

- **Idempotent status detection** — for each patch the manager asks `patch`
  itself, never a heuristic:
  - `patch -R --dry-run` succeeds → already **applied**.
  - else `patch --dry-run` (forward) succeeds → **not applied**.
  - else → **conflict** (target modified incompatibly).

  This makes `patch` / `unpatch` safe to re-run, and `status` accurate.

- **Strict, no-fuzz matching** — all `patch` invocations use `-F0` (zero fuzz)
  and `-p1`. A patch that does not match its expected context exactly is reported
  as `CONFLICT` rather than being force-fitted at a shifted location. This trades
  convenience for safety: a diff authored against one Isabelle point release will
  not silently misapply to another.

- **Read-only handling** — Isabelle distribution files are often read-only.
  Before applying, the target file is made writable (`chmod u+w`); its original
  mode is restored afterward, even on failure.

- **Feature ordering** — when a version's features must be applied in a specific
  order, list them one per line in `patches/<version>/order.txt` (`#` comments
  and blank lines ignored; earlier = applied earlier). Listed features come
  first, in that order; any remaining features follow alphabetically. `unpatch`
  reverses this order. Without an `order.txt`, features are simply alphabetical.

- **Scala rebuild** — `patch` / `unpatch` run `isabelle scala_build -f`
  afterward, because the `vscode_server` Scala must be recompiled to take effect.
  Pure-ML-only patches (e.g. `register_thy`) do not need it — use `--no-build`,
  or the standalone `build` command when you do.

## Patch-repository layout

```
my_better_isabelle_prover/patches/
├── __init__.py                 # discovery logic (versions, features, ordering)
├── pide_control.md             # feature doc shared across versions
├── Isabelle2024/
│   └── pide_control/
│       ├── execution.ML.patch
│       ├── protocol.ML.patch
│       ├── protocol.scala.patch
│       ├── lsp.scala.patch
│       └── language_server.scala.patch
└── Isabelle2025-2/
    ├── pide_control/            # same five patches, adapted to 2025-2 source
    │   └── ...
    ├── register_thy/
    │   └── thy_info.ML.patch
    └── register_thy.md          # version-specific feature doc
```

- **`patches/<version>/`** — one directory per Isabelle version. The directory
  name must equal the `isabelle version` string exactly. Names starting with `_`
  are ignored by version discovery.
- **`<version>/<feature>/`** — one directory per feature; every `*.patch` in it
  belongs to that feature. Patches within a feature are applied in filename
  (sorted) order.
- **Target path** — each patch's target file is read from its unified-diff
  `--- a/<path>` header, so the path is relative to `ISABELLE_HOME` and the
  filename of the `.patch` itself is just for humans.
- **`order.txt`** (optional, per version) — feature apply order, as above.
- **Docs** — feature `.md` files live next to the patches (`patches/*.md` for a
  cross-version feature, or `patches/<version>/*.md` for a version-specific one);
  they document rationale and, for `pide_control`, the full LSP protocol.

## Adding a new patch

1. **Author the diff against pristine source.** From a clean `ISABELLE_HOME`,
   edit the target file, then produce a `-p1` unified diff whose header reads
   `--- a/<path-relative-to-ISABELLE_HOME>` / `+++ b/<same>`. Keep edits minimal
   so the surrounding context survives across point releases.

2. **Drop it in the right place** — `patches/<version>/<feature>/<name>.patch`.
   Create the `<feature>/` directory if new. If the feature must apply before or
   after others, add it to `patches/<version>/order.txt`.

3. **Verify discovery and clean status** — run `my-better-isabelle status`
   (optionally `--feature <name>`). A correctly authored patch on pristine source
   reports `not-applied`; after `patch`, it reports `applied`; `unpatch` returns
   it to `not-applied`. Anything reporting `CONFLICT` on pristine source means
   the context does not match (wrong version, wrong `-p` level, or stale diff).

4. **Decide on the build step.** Scala edits need `scala_build` (the default).
   Pure-ML edits do not — note that in the feature doc and use `--no-build`.

5. **Document it.** Add or update the feature's `.md` file, and the feature table
   in the top-level `README.md`.
