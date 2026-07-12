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

Every feature is classified `user` or `dev` in `patches/categories.toml`, and
**`patch` applies only the `user` ones by default**:

- **`user`** — needed by the user-facing systems. On Isabelle2025-2 that is now
  only the SIMD FFI of Semantic_Embedding: **Isabelle-MCP no longer needs any
  patch** (it ships its own `isabelle mcp_server` component and cancels via a
  `use_prelude`-injected ML prelude built on the public `EXECUTION` API).
- **`dev`** — needed only by developer/experiment infrastructure (Isa-REPL;
  Isa-Mini's translator and AoA agent injector). These are *compile-time*
  dependencies of that stack — without them `Thy_Info.register_thy`,
  `Printer.show_types_nv` and `Sign.map_syn` do not exist and the ML fails to
  compile. **Working on that stack? Use `my-better-isabelle patch --category
  all`.**

Features shipping today:
- **`pide_control`** — *user* — **Isabelle2024 only; RETIRED on Isabelle2025-2**
  (reversed from that distribution, patch files deleted). Adds LSP requests the
  stock `vscode_server` does not expose. The surviving Isabelle2024 feature has
  five: `PIDE/theory_status`, `PIDE/cancel_execution`, `PIDE/command_at_position`,
  `PIDE/output_at_position`, `PIDE/symbols`. (`PIDE/find_theorems_*` existed only
  in the Isabelle2025-2 patch and went away with it — do not expect it on 2024.)
  Isabelle-MCP now carries these in its own `isabelle mcp_server` component, and
  got the ML half (global cancel) back from a `use_prelude`-injected prelude over
  the public `EXECUTION` API — which also removed this feature's worst cost,
  invalidating every heap by patching Pure ML.
- **`perspective_eof_clamp`** — *user* — **Isabelle2024 only; RETIRED on
  Isabelle2025-2**. Clamped the caret perspective window's lower bound to EOF; now
  in Isabelle-MCP's own `vscode_model.scala`.
- **`expose_foreign`** — *user* (Isabelle2025-2 only) — stops the Pure bootstrap
  from hiding Poly/ML's `Foreign` / `RunCall` / `CInterface` structures, without
  which ML using the FFI cannot compile. Pure ML → no scala rebuild (takes effect
  on Pure heap rebuild).
- **`register_thy`** — *dev* (Isabelle2025-2 only) — restores
  `Thy_Info.register_thy`, removed by the 2025-2 loader refactoring. Pure ML → no
  rebuild.
- **`show_types_nv`** — *dev* (Isabelle2024, Isabelle2025-2) — custom
  `show_types_nv` printing option that suppresses type annotations on free/fixed
  variables only. Pure ML + `etc/options` → no scala rebuild (takes effect on Pure
  heap rebuild).
- **`expose_map_syn`** — *dev* (Isabelle2024, Isabelle2025-2) — exports the private
  `Sign.map_syn` so ML can wholesale replace/clear a theory's inner syntax. Pure
  ML → no rebuild.

It is a thin, dependency-free wrapper around the system `patch` tool. Apart from
the category table, everything is driven from the `.patch` files on disk.

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

# 2. Apply the `user` patches for the detected version, then rebuild Scala.
my-better-isabelle patch

# 2b. ... or everything, including the `dev` patches Isa-REPL / Isa-Mini need.
my-better-isabelle patch --category all

# 3. Reverse them all (undone in reverse apply order).
my-better-isabelle unpatch

# 4. Rebuild Scala on its own (e.g. after `patch --no-build`).
my-better-isabelle build
```

Useful flags (full list in [reference.md](reference.md)):
- `--isabelle-bin PATH` — target a specific Isabelle when several are installed.
- `--category user|dev|all` — which category to act on. Defaults differ per
  command: `patch` → `user`, `unpatch` → `all`, `status` → `user` (there it gates
  the exit code only).
- `--feature NAME` — limit to one feature (see `status` for the full list).
  Overrides `--category`.
- `--dry-run` — check without modifying any file. **Prefer this first** when
  unsure.
- `--no-build` — skip `isabelle scala_build`. Rarely needed: a selection that
  touches no `.scala` source already skips it.
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
- **`status` shows everything, judges only the selection.** It always lists every
  feature — including `dev` ones you did not ask for, which on a default install
  legitimately read `not-applied`. The **exit code** reflects only the selected
  category (`user` by default). So do not conclude an install is broken because
  `not-applied` appears in the output.
- **Exit codes.** `0` success (or nothing to do); `1` setup error / patch
  conflict / `status` found a *selected* patch not applied or in conflict; `2`
  patching succeeded but `scala_build` failed; `3` broken patch repository (a
  feature directory not registered in `categories.toml`). **Check these rather
  than parsing stdout.**

## When changing patches

Do **not** hand-edit Isabelle source in place to "fix" things. Author a diff
against pristine source, drop it under the right
`patches/<version>/<feature>/` directory, **register its category in
`patches/categories.toml`** (an unregistered feature makes every command exit
`3`), and verify with `my-better-isabelle status --feature <name>`. Full
procedure in [develop.md](develop.md).

## Project rules

Honor the repository's `CLAUDE.md`: never act on assumptions — ask when anything
is ambiguous; never run `git clean`, `git stash`, `git checkout`, `git reset
--hard`, or anything that discards uncommitted work in this shared directory.
