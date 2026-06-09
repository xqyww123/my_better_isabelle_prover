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

## Global options

| Option | Description |
|--------|-------------|
| `--isabelle-bin PATH` | Path to the `isabelle` binary. Default: found on `PATH`. |
| `-v`, `--verbose` | Debug logging. |
| `-q`, `--quiet` | Only warnings and errors. |

`--verbose` and `--quiet` are mutually exclusive; the default level is info.

## Commands

### `patch` — apply patches

Applies every patch for the detected version (in dependency order), then runs
`isabelle scala_build -f` unless `--no-build` is given.

| Option | Description |
|--------|-------------|
| `--feature NAME` | Only apply patches for this feature. |
| `--dry-run` | Check without modifying any files. |
| `--no-build` | Skip `isabelle scala_build` after patching. |
| `--force` | Continue past conflicts/failures (and re-apply already-applied patches). |

Patching is idempotent: an already-applied patch is skipped (reported `[skip]`)
unless `--force`. Each target file is made writable for the duration of the apply
and its original mode is restored afterward.

```bash
# apply everything for the detected version, then rebuild Scala
my-better-isabelle patch

# preview only, no changes
my-better-isabelle patch --dry-run

# just one feature, against an explicit Isabelle, without rebuilding
my-better-isabelle --isabelle-bin /opt/Isabelle2024/bin/isabelle \
    patch --feature pide_control --no-build
```

### `unpatch` — reverse patches

Reverses the patches, undoing them in the reverse of the apply order. Same
options as `patch` (`--feature`, `--dry-run`, `--no-build`, `--force`). A patch
that is already not applied is skipped unless `--force`.

```bash
my-better-isabelle unpatch
my-better-isabelle unpatch --feature pide_control --dry-run
```

### `status` — show patch status

Prints, per patch, one of `applied` / `not-applied` / `CONFLICT` and the target
file. `CONFLICT` means the target has modifications that are incompatible with
the patch (the patch neither applies forward nor reverses cleanly).

| Option | Description |
|--------|-------------|
| `--feature NAME` | Only show status for this feature. |

```bash
my-better-isabelle status
```

### `build` — rebuild Scala

Runs `isabelle scala_build -f` on its own (no patching). Useful after a manual
edit, or after `patch --no-build`.

```bash
my-better-isabelle build
```

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success (also: no patches found for the version — nothing to do). |
| `1` | Setup error (no `isabelle`/`patch`, unknown version or feature, bad `ISABELLE_HOME`), a patch conflict/failure, or `status` found a `CONFLICT`. |
| `2` | Patching succeeded but the subsequent `isabelle scala_build` failed. |
