# my-better-isabelle-prover

A patch manager for Isabelle installations.

GitHub: <https://github.com/xqyww123/my_better_isabelle_prover>

It exists primarily to support
[**Isabelle-MCP**](https://github.com/xqyww123/Isabelle-MCP) (Isa-LSP), an MCP
server that drives Isabelle over its LSP interface for AI agents. That server
needs PIDE/LSP requests the stock `vscode_server` does not expose, and the
[`Isa-REPL`](https://github.com/xqyww123/Isa-REPL) it builds on needs an ML
loader function that Isabelle2025-2 removed. This tool keeps the edits that add
them as
version-keyed unified diffs and applies, reverses, and checks them idempotently,
then rebuilds the affected Scala when needed.

> [!IMPORTANT]
> **Isabelle-MCP and Isa-REPL require this patch** — run `my-better-isabelle
> patch` against your Isabelle before using them.
>
> Before using this tool, make sure the `isabelle` command is available — on
> your `PATH`, or passed explicitly via `--isabelle-bin PATH`. Every command
> needs it (to detect the version and locate `ISABELLE_HOME`) and aborts with an
> error if it cannot be found. The system `patch` command must likewise be
> installed.

```bash
pip install -e .
my-better-isabelle patch          # apply all patches for the detected version
my-better-isabelle status         # show what is applied
my-better-isabelle unpatch        # reverse them
```

The Python version constraint is declared in `pyproject.toml`. See
**[reference.md](reference.md)** for the full list of prerequisites and CLI
options.

## Features

A *feature* is one self-consistent bundle of patches, stored per Isabelle
version. Run `my-better-isabelle status` to see which are applied.

| Feature | Isabelle2024 | Isabelle2025-2 | What it adds |
|---------|:---:|:---:|--------------|
| [`pide_control`](my_better_isabelle_prover/patches/pide_control.md) | ✓ | ✓ | PIDE LSP control requests the stock `vscode_server` does not expose |
| [`register_thy`](my_better_isabelle_prover/patches/Isabelle2025-2/register_thy.md) | native | ✓ | Restores `Thy_Info.register_thy`, removed in 2025-2 |
| [`show_types_nv`](my_better_isabelle_prover/patches/show_types_nv.md) | ✓ | ✓ | Custom `show_types_nv` option: suppress type annotations on free/fixed variables only |
| `perspective_eof_clamp` | ✓ | ✓ | Clamp the caret-perspective window's lower bound to EOF (avoids an out-of-range `Text.Range` past the last line) |

### `pide_control` — PIDE LSP control extensions

Edits five ML/Scala files to add these LSP requests (full request/response
protocol in **[pide_control.md](my_better_isabelle_prover/patches/pide_control.md)**):

- **`PIDE/theory_status`** — per-theory processing status for *all* loaded
  theories, including auto-loaded dependencies.
- **`PIDE/cancel_execution`** — immediately cancel all running processing,
  globally.
- **`PIDE/command_at_position`** — source text and range of the Isar command
  enclosing a position, with no caret move.
- **`PIDE/output_at_position`** — source, range, *and* rendered prover output of
  the command enclosing a position, in one request, with no caret move.
- **`PIDE/symbols`** — dump the `etc/symbols` translation table(s) so a client
  can decode/encode Isabelle symbol notation (`\<forall>` ↔ ∀).

### `register_thy` — restore removed theory registration (Isabelle2025-2)

`Thy_Info.register_thy` existed in 2024 but was removed by the 2025-2
theory-loader refactoring. `Isa-REPL` needs it to inject an already-built,
in-memory `theory` value into Isabelle's global loader database. The patch
re-adds it, restored from the 2024 source with one node-type adaptation. Pure ML
change — no `scala_build`. Details in
**[register_thy.md](my_better_isabelle_prover/patches/Isabelle2025-2/register_thy.md)**.

## Supported versions & verification status

Patch targets are keyed by the exact output of `isabelle version`
(e.g. `Isabelle2024`, `Isabelle2025-2`).

- **Isabelle2024** — `pide_control` authored, compiled (`scala_build` clean), and
  runtime-tested. `register_thy` ships natively, so no patch is needed.
- **Isabelle2025-2** — `pide_control` authored and round-trip-verified against
  pristine source, but **not yet compiled**. `register_thy` applies and
  reverse-detects cleanly, but the Pure/HOL heap has **not** yet been rebuilt
  with it. Verify before relying on either; see each feature doc for the exact
  scope tested.
- **`show_types_nv`** — recorded for Isabelle2024 (reverse-recorded from the
  existing hand edit) and ported to Isabelle2025-2. On 2025-2 it is applied, the
  Pure heap has been rebuilt, and it is runtime-verified (free-variable type
  annotation suppressed). The end-to-end consumer path
  (`Isa-Mini/.../print_formats.ML`, `show_markup=false`, HOL terms) is pending
  the HOL/Isa-Mini rebuild.

## Documentation

- **[reference.md](reference.md)** — CLI reference: subcommands, flags, examples,
  exit codes, and runtime prerequisites.
- **[develop.md](develop.md)** — how the manager works, the patch-repository
  layout, and how to add a new patch.
- Feature docs (full protocol / rationale):
  [`pide_control.md`](my_better_isabelle_prover/patches/pide_control.md),
  [`register_thy.md`](my_better_isabelle_prover/patches/Isabelle2025-2/register_thy.md),
  [`show_types_nv.md`](my_better_isabelle_prover/patches/show_types_nv.md).
