# AGENTS.md

Orientation for an AI agent operating in this package. For human-facing detail
see [README.md](README.md), [reference.md](reference.md), and [develop.md](develop.md).

## What this is

`my-better-isabelle-prover`
(<https://github.com/xqyww123/my_better_isabelle_prover>) is a **patch manager
for Isabelle installations**. It stores edits to *vendored* Isabelle source (the
Pure ML loader and the `vscode_server` Scala) as version-keyed unified diffs, and
applies, reverses, and checks them idempotently — then rebuilds the affected
Scala.

Two features ship today:
- **`pide_control`** (Isabelle2024, Isabelle2025-2) — adds LSP requests the stock
  `vscode_server` does not expose: `PIDE/theory_status`, `PIDE/cancel_execution`,
  `PIDE/command_at_position`, `PIDE/output_at_position`, `PIDE/symbols`. Edits
  Scala → needs a rebuild.
- **`register_thy`** (Isabelle2025-2 only) — restores `Thy_Info.register_thy`,
  removed by the 2025-2 loader refactoring. Pure ML → no rebuild.

It is a thin, dependency-free wrapper around the system `patch` tool. There is no
per-patch config; everything is driven from the `.patch` files on disk.

## Prerequisites (verify before doing anything)

- **`isabelle`** on `PATH`, or pass `--isabelle-bin PATH`. **Required by every
  command** — used to detect the version and locate `ISABELLE_HOME`. The tool
  aborts with a clear error if it is missing, so confirm it first.
- **`patch`** — the system patch tool must be installed.
- Patches are selected by the exact `isabelle version` string (e.g.
  `Isabelle2024`). If there is no `patches/<that-version>/` directory, there is
  nothing to do for that install.

## How to use

The package installs a `my-better-isabelle` console script; equivalently
`python -m my_better_isabelle_prover`.

```bash
# 1. Inspect current state first — non-destructive, tells you what is applied.
my-better-isabelle status

# 2. Apply all patches for the detected version, then rebuild Scala.
my-better-isabelle patch

# 3. Reverse them (undone in reverse apply order).
my-better-isabelle unpatch

# 4. Rebuild Scala on its own (e.g. after `patch --no-build`).
my-better-isabelle build
```

Useful flags (full list in [reference.md](reference.md)):
- `--isabelle-bin PATH` — target a specific Isabelle when several are installed.
- `--feature NAME` — limit to one feature (`pide_control` or `register_thy`).
- `--dry-run` — check without modifying any file. **Prefer this first** when
  unsure.
- `--no-build` — skip `isabelle scala_build`; correct for pure-ML patches like
  `register_thy`.
- `--force` — continue past conflicts / re-apply. Use sparingly; a `CONFLICT`
  usually means the target source does not match what the patch expects.

## Behaviour an agent should rely on

- **Idempotent.** Re-running `patch` / `unpatch` is safe: an already-applied (or
  already-reversed) patch is skipped. Status is decided by asking `patch` itself
  (`patch -R --dry-run`), not by a heuristic.
- **Strict matching (`-F0`, no fuzz).** A patch that does not match its context
  exactly is reported `CONFLICT` rather than force-fitted. Do not work around a
  `CONFLICT` with `--force` without understanding why the source diverged.
- **Read-only safe.** Distribution files are made writable for the apply and
  restored afterward.
- **Exit codes.** `0` success (or nothing to do); `1` setup error / patch
  conflict / `status` found a patch not applied or in conflict; `2` patching
  succeeded but `scala_build` failed. Check these rather than parsing stdout.

## When changing patches

Do **not** hand-edit Isabelle source in place to "fix" things. Author a diff
against pristine source, drop it under the right
`patches/<version>/<feature>/` directory, and verify with
`my-better-isabelle status`. Full procedure in [develop.md](develop.md).

## Project rules

Honor the repository's `CLAUDE.md`: never act on assumptions — ask when anything
is ambiguous; never run `git clean`, `git stash`, `git checkout`, `git reset
--hard`, or anything that discards uncommitted work in this shared directory.
