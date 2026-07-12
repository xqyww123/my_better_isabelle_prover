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

- **Feature categories** — every feature is `user` or `dev`, declared in
  `patches/categories.toml`. `patch` applies only `user` by default. The table is
  version-independent, and validation runs in one direction only: a feature
  *directory* with no entry is a hard error (exit `3`), while an *entry* with no
  directory is normal — `register_thy` and `expose_foreign` ship natively on
  Isabelle2024 and have no patch directory there.

- **Scala rebuild** — `patch` / `unpatch` run `isabelle scala_build -f`
  afterward, but only when the patches they actually touched include a `.scala`
  target; a pure-ML selection (e.g. `--category dev`, or `--feature
  register_thy`) skips the rebuild by itself. `--no-build` forces the skip, and
  the standalone `build` command runs it on its own.

## Patch-repository layout

```
my_better_isabelle_prover/patches/
├── __init__.py                 # discovery logic (versions, features, categories, ordering)
├── categories.toml             # feature -> user | dev
├── pide_control.md             # feature doc (cross-version location, 2024-only feature)
├── Isabelle2024/
│   └── pide_control/
│       ├── execution.ML.patch
│       ├── protocol.ML.patch
│       ├── protocol.scala.patch
│       ├── lsp.scala.patch
│       └── language_server.scala.patch
└── Isabelle2025-2/
    ├── expose_foreign/          # no pide_control here: retired on 2025-2
    │   └── ml_name_space.ML.patch
    ├── register_thy/
    │   └── thy_info.ML.patch
    └── register_thy.md          # version-specific feature doc
```

A feature exists for a version only if it has a directory there. The two are
independent: `expose_foreign` and `register_thy` ship natively on Isabelle2024,
while `pide_control` and `perspective_eof_clamp` were *retired* on Isabelle2025-2
(Isabelle-MCP now carries them in its own `isabelle mcp_server` component). Both
cases look the same on disk — no directory — and both are fine.

- **`patches/<version>/`** — one directory per Isabelle version. The directory
  name must equal the `isabelle version` string exactly. Names starting with `_`
  are ignored by version discovery.
- **`<version>/<feature>/`** — one directory per feature; every `*.patch` in it
  belongs to that feature. Patches within a feature are applied in filename
  (sorted) order. Names starting with `_` or `.` are ignored, so a scratch
  directory does not become an accidental feature.
- **`categories.toml`** — the `[features]` table maps every feature name to
  `user` or `dev`. Shared across versions.
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

3. **Register its category** — add the feature to the `[features]` table in
   `patches/categories.toml` as `user` or `dev`. This is **not optional**: an
   unregistered feature directory makes *every* command exit `3`, deliberately,
   so that a new patch can neither be shipped to users unvetted nor be silently
   withheld from the stack that needs it. Ask which category it belongs in if it
   is not obvious — `user` means a *user-facing* system needs it (today:
   Semantic_Embedding's SIMD FFI), while `dev` means only the
   developer/experiment stack does (Isa-REPL, Isa-Mini).

4. **Verify discovery and clean status** — run `my-better-isabelle status
   --feature <name>`. A correctly authored patch on pristine source reports
   `not-applied` (and, because you selected it, exit code `1`); after `patch
   --feature <name>` it reports `applied` and exits `0`; `unpatch --feature
   <name>` returns it to `not-applied`. Anything reporting `CONFLICT` on pristine
   source means the context does not match (wrong version, wrong `-p` level, or
   stale diff).

5. **Check the build step.** A `.scala` target triggers `scala_build`
   automatically; a pure-ML feature skips it on its own. Note in the feature doc
   whether it instead needs a Pure/HOL **heap** rebuild to take effect — the tool
   never does that for you.

6. **Document it.** Add or update the feature's `.md` file, and the feature tables
   in `README.md` and `reference.md`.
