# CLI reference

The package installs a `my-better-isabelle` console script; the same entry point
is reachable as `python -m my_better_isabelle_prover`.

```
my-better-isabelle [global options] <command> [command options]
```

## Prerequisites

- **Python** — version per `pyproject.toml` (`requires-python`).
- **`patch`** — the system patch tool must be on `PATH` (e.g. `apt install
  patch`). The manager shells out to it for all apply / reverse / status checks.
- **`isabelle`** — an Isabelle launcher on `PATH`, or passed via
  `--isabelle-bin`. Used to detect the version (`isabelle version`), locate
  `ISABELLE_HOME` (`isabelle getenv -b ISABELLE_HOME`), and run the Scala build.

The detected version (the exact `isabelle version` string, e.g. `Isabelle2024`)
selects which patch set under `patches/<version>/` applies. If no patches exist
for that version the command stops with an explanatory message.

## Features

A *feature* is a named bundle of patches, applied, reversed, and queried as a
unit (`--feature NAME`). Which features exist depends on the detected Isabelle
version.

| Feature | Category | Versions | Needed by | What it adds |
|---------|----------|----------|-----------|--------------|
| `pide_control` | user | Isabelle2024, Isabelle2025-2 | Isabelle-MCP | PIDE/LSP control requests the stock `vscode_server` does not expose (`theory_status`, `cancel_execution`, `command_at_position`, `output_at_position`, `symbols`). Edits Scala, so it triggers a `scala_build`. |
| `perspective_eof_clamp` | user | Isabelle2024, Isabelle2025-2 | Isabelle-MCP | Clamps the caret-perspective window's lower bound to EOF, avoiding an out-of-range `Text.Range` past the last line. Edits Scala, so it triggers a `scala_build`. |
| `expose_foreign` | user | Isabelle2025-2 only | Semantic_Embedding | Stops the Pure bootstrap from hiding Poly/ML's `Foreign` / `RunCall` / `CInterface` structures, without which ML that uses the FFI cannot compile (Isabelle2024 does not hide them, so no patch is needed there). Pure ML, so no `scala_build`. |
| `register_thy` | dev | Isabelle2025-2 only | Isa-REPL | Restores `Thy_Info.register_thy`, removed by the 2025-2 loader refactoring (native in Isabelle2024, so no patch is needed there). Pure ML, so no `scala_build`. |
| `show_types_nv` | dev | Isabelle2024, Isabelle2025-2 | Isa-Mini | Adds the `show_types_nv` printing option, which suppresses type annotations on free/fixed variables only. Pure ML + `etc/options`, so no `scala_build`. |
| `expose_map_syn` | dev | Isabelle2024, Isabelle2025-2 | Isa-Mini | Exports the private `Sign.map_syn`, letting ML wholesale replace or clear a theory's inner syntax. Pure ML, so no `scala_build`. |

## Categories

Every feature is either `user` or `dev`; the mapping lives in
`patches/categories.toml`, and a feature directory that is not registered there
is a hard error (exit `3`).

- **`user`** — needed by the user-facing systems (Isabelle-MCP; the SIMD FFI of
  Semantic_Embedding). `patch` applies these **by default**.
- **`dev`** — needed only by developer/experiment infrastructure (Isa-REPL;
  Isa-Mini's translator and AoA agent injector). These are **compile-time**
  dependencies of that stack: without them `Thy_Info.register_thy`,
  `Printer.show_types_nv` and `Sign.map_syn` do not exist and the ML fails to
  compile. Opt in with `patch --category all`.

`--category user|dev|all` selects which features a command acts on. The defaults
differ per command (`patch`: `user`; `unpatch`: `all`; `status`: `user`) — see
each command below. An explicit `--feature NAME` names exactly what the caller
wants, so it takes precedence and `--category` is ignored.

## Global options

| Option | Description |
|--------|-------------|
| `--isabelle-bin PATH` | Path to the `isabelle` binary. Default: found on `PATH`. |
| `-v`, `--verbose` | Debug logging. |
| `-q`, `--quiet` | Only warnings and errors. |

`--verbose` and `--quiet` are mutually exclusive; the default level is info.

## Commands

### `patch` — apply patches

Applies the selected patches for the detected version (in dependency order), then
runs `isabelle scala_build -f` — but only if the applied patches actually touched
a `.scala` source, and not if `--no-build` is given.

| Option | Description |
|--------|-------------|
| `--category user\|dev\|all` | Which category to apply. **Default: `user`.** |
| `--feature NAME` | Only apply patches for this feature (overrides `--category`). |
| `--dry-run` | Check without modifying any files. |
| `--no-build` | Skip `isabelle scala_build` after patching. |
| `--force` | Continue past conflicts/failures. |

Patching is idempotent: an already-applied patch is skipped (reported `[skip]`)
unless `--force`. Each target file is made writable for the duration of the apply
and its original mode is restored afterward.

```bash
# apply the `user` patches for the detected version, then rebuild Scala
my-better-isabelle patch

# everything, including the `dev` patches Isa-REPL / Isa-Mini need
my-better-isabelle patch --category all

# preview only, no changes
my-better-isabelle patch --dry-run

# just one feature, against an explicit Isabelle, without rebuilding
my-better-isabelle --isabelle-bin /opt/Isabelle2024/bin/isabelle \
    patch --feature pide_control --no-build
```

### `unpatch` — reverse patches

Reverses the patches, undoing them in the reverse of the apply order. Same
options as `patch`, except that `--category` **defaults to `all`**: reversing
leaves nothing behind unless you narrow it explicitly. A patch that is already
not applied is skipped unless `--force`.

```bash
my-better-isabelle unpatch
my-better-isabelle unpatch --feature pide_control --dry-run
```

### `status` — show patch status

Prints, per patch, one of `applied` / `not-applied` / `CONFLICT`, the feature's
category, and the target file, followed by a per-category summary. `CONFLICT`
means the target has modifications that are incompatible with the patch (the
patch neither applies forward nor reverses cleanly).

Display and verdict are decoupled: `status` **always lists every feature**
(hiding the opted-out ones would misrepresent the install), while the **exit code
speaks only for the selected category** — `0` when every selected patch reports
`applied`, `1` otherwise. So on a default (`user`-only) install, a bare `status`
exits `0` even though the `dev` patches are listed as `not-applied`.

| Option | Description |
|--------|-------------|
| `--category user\|dev\|all` | Which category the exit code gates on. **Default: `user`.** |
| `--feature NAME` | Gate the exit code on this feature (overrides `--category`). |

```bash
my-better-isabelle status                        # is this Isabelle ready for Isabelle-MCP?
my-better-isabelle status --category all         # ... and for the Isa-REPL / Isa-Mini stack?
my-better-isabelle status --feature register_thy # ... and for just that one feature?
```

### `build` — rebuild Scala

Runs `isabelle scala_build -f` on its own (no patching). Useful after a manual
edit, or after `patch --no-build`.

```bash
my-better-isabelle build
```

### `help` — print the agent/usage guide

Prints the bundled `AGENTS.md` (agent-oriented orientation: what the tool is,
prerequisites, usage, and behaviour) to stdout. Needs no Isabelle and touches
nothing.

```bash
my-better-isabelle help
```

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success (also: no patches found for the version/selection — nothing to do). |
| `1` | Setup error (no `isabelle`/`patch`, unknown version or feature, bad `ISABELLE_HOME`), a patch conflict/failure, or `status` found a *selected* patch `not-applied` or in `CONFLICT`. |
| `2` | Patching succeeded but the subsequent `isabelle scala_build` failed. |
| `3` | Broken patch repository: a feature directory is not registered in `patches/categories.toml`, or is registered with an unknown category. |
