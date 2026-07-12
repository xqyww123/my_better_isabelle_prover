# my-better-isabelle-prover

A patch manager for Isabelle installations.

GitHub: <https://github.com/xqyww123/my_better_isabelle_prover>

It carries the patches that the surrounding Isabelle/ML research stack needs: the
SIMD FFI of `Semantic_Embedding`, and — for development —
[`Isa-REPL`](https://github.com/xqyww123/Isa-REPL) and Isa-Mini, notably an ML
loader function that Isabelle2025-2 removed. This tool keeps those edits as
version-keyed unified diffs and applies, reverses, and checks them idempotently,
then rebuilds the affected Scala when needed.

> [!NOTE]
> **[Isabelle-MCP](https://github.com/xqyww123/Isabelle-MCP) no longer needs any
> patch.** It used to: `pide_control` gave `vscode_server` the PIDE requests it
> lacked, and its ML half gave PIDE a global-cancel command. Isabelle-MCP now
> ships its own `isabelle mcp_server` Scala component (which carries those
> requests as its own code) and cancels through an ML prelude injected at prover
> startup, built from the public `EXECUTION` API alone. Both `pide_control` and
> `perspective_eof_clamp` are therefore **retired on Isabelle2025-2**; they remain
> only for Isabelle2024, which Isabelle-MCP no longer targets. See the
> `last-isabelle2024-support` tag in both repositories.

> [!IMPORTANT]
> **Developing against Isa-REPL or Isa-Mini needs
> `my-better-isabelle patch --category all`** (see [Categories](#categories)).
>
> Before using this tool, make sure the `isabelle` command is available — on
> your `PATH`, or passed explicitly via `--isabelle-bin PATH`. Every command
> needs it (to detect the version and locate `ISABELLE_HOME`) and aborts with an
> error if it cannot be found. The system `patch` command must likewise be
> installed.

```bash
pip install -e .
my-better-isabelle patch          # apply the `user` patches for the detected version
my-better-isabelle patch --category all   # ... plus the `dev` ones
my-better-isabelle status         # show what is applied
my-better-isabelle unpatch        # reverse them all
```

The Python version constraint is declared in `pyproject.toml`. See
**[reference.md](reference.md)** for the full list of prerequisites and CLI
options.

## Features

A *feature* is one self-consistent bundle of patches, stored per Isabelle
version. Run `my-better-isabelle status` to see which are applied.

| Feature | Category | Isabelle2024 | Isabelle2025-2 | What it adds |
|---------|:---:|:---:|:---:|--------------|
| [`pide_control`](my_better_isabelle_prover/patches/pide_control.md) | user | ✓ | **retired** | PIDE LSP control requests the stock `vscode_server` does not expose. Isabelle-MCP now carries them in its own component — see the note above |
| `perspective_eof_clamp` | user | ✓ | **retired** | Clamp the caret-perspective window's lower bound to EOF (avoids an out-of-range `Text.Range` past the last line). Likewise now in Isabelle-MCP's own `vscode_model.scala` |
| [`expose_foreign`](my_better_isabelle_prover/patches/expose_foreign.md) | user | native | ✓ | Stop hiding Poly/ML's `Foreign`/`RunCall`/`CInterface` FFI structures, which 2025-2 forgets during the Pure bootstrap |
| [`register_thy`](my_better_isabelle_prover/patches/Isabelle2025-2/register_thy.md) | dev | native | ✓ | Restores `Thy_Info.register_thy`, removed in 2025-2 |
| [`show_types_nv`](my_better_isabelle_prover/patches/show_types_nv.md) | dev | ✓ | ✓ | Custom `show_types_nv` option: suppress type annotations on free/fixed variables only |
| [`expose_map_syn`](my_better_isabelle_prover/patches/expose_map_syn.md) | dev | ✓ | ✓ | Export the private `Sign.map_syn` so ML can wholesale replace/clear a theory's inner syntax |

## Categories

Each feature is either `user` or `dev`, and `my-better-isabelle patch` applies
**only the `user` ones by default**.

- **`user`** — needed by the user-facing systems. On Isabelle2025-2 that is now
  only the SIMD FFI of `Semantic_Embedding` (`expose_foreign`); the two
  Isabelle-MCP features are retired there and survive for Isabelle2024 alone.
- **`dev`** — needed only by developer/experiment infrastructure: **Isa-REPL**,
  and Isa-Mini's translator and AoA agent injector.

> [!WARNING]
> The three `dev` patches are **compile-time** dependencies of that stack —
> `Thy_Info.register_thy`, `Printer.show_types_nv`, `Sign.map_syn` simply do not
> exist without them, so the ML fails to compile. If you are building or running
> Isa-REPL / Isa-Mini, apply everything:
>
> ```bash
> my-better-isabelle patch --category all
> ```

`status` always lists every feature regardless of category; its *exit code*
reflects only the selected category (`user` by default). Categories live in
[`patches/categories.toml`](my_better_isabelle_prover/patches/categories.toml).

### `pide_control` — PIDE LSP control extensions (Isabelle2024 only; retired on 2025-2)

> [!NOTE]
> **Retired on Isabelle2025-2** and reversed from that distribution. Isabelle-MCP
> forked the `vscode_server` sources into its own `isabelle mcp_server` component,
> so the five LSP requests below are now that component's own code; and it replaced
> the ML half (`Execution.cancel_execution` + the `Document.cancel_execution`
> protocol command) with an ML prelude injected at prover startup via
> `use_prelude`, built from `Execution.discontinue` + `Execution.cancel` — public
> API, no patch. That removes this feature's worst cost: patching `src/Pure/**.ML`
> invalidated every session heap on the machine.
>
> It survives for Isabelle2024, whose VSCode sources the fork does not target
> (three of its files do not exist there and the Pure Scala API differs).

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
  runtime-tested; still applied there. `register_thy` ships natively, so no patch
  is needed.
- **Isabelle2025-2** — `pide_control` and `perspective_eof_clamp` were applied,
  compiled and runtime-tested here, and have now been **reversed and retired**
  (see the note above). The reversal was verified byte-for-byte against the
  pristine sources and `isabelle scala_build -f` was re-run, so this distribution's
  Scala is stock again. `register_thy` applies and reverse-detects cleanly.
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
  [`expose_foreign.md`](my_better_isabelle_prover/patches/expose_foreign.md),
  [`register_thy.md`](my_better_isabelle_prover/patches/Isabelle2025-2/register_thy.md),
  [`show_types_nv.md`](my_better_isabelle_prover/patches/show_types_nv.md),
  [`expose_map_syn.md`](my_better_isabelle_prover/patches/expose_map_syn.md).
