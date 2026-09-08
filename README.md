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
> startup, built from the public `EXECUTION` API alone. `pide_control` and
> `perspective_eof_clamp` were therefore retired on Isabelle2025-2, and
> **removed from this repository on 2026-09-08**; the last state carrying them is
> tagged `last-isabelle2024-support` in both repositories. No remaining feature
> edits Scala, so `patch` no longer runs `scala_build` at all.

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
| [`future_assign_interrupt`](my_better_isabelle_prover/patches/future_assign_interrupt.md) | user | ✓ | ✓ | **Bug fix.** Stop `Future.assign_result` from swallowing an interrupt raised inside `Single_Assignment.assign`, which then surfaced as `exception Option` |
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

### `future_assign_interrupt` — don't turn a cancelled future into `exception Option`

The one feature here that fixes a defect rather than adding a capability.
`Future.assign_result` re-raised only `Fail` and dropped every other exception
from `Single_Assignment.assign`. An asynchronous interrupt — from
`Timeout.apply`, or from cancelling a racer's future group — could land in that
call's interruptible window, get swallowed, and leave the result unassigned; the
`the` on the next line then raised `exception Option` at `General/basics.ML:84`,
naming neither the interrupt nor its origin. The patch re-raises every exception,
restoring the invariant that code past that point depends on.

Reachable from ordinary proof work, not just from code that touches futures:
Pure takes the vulnerable path from `Lazy.force`, promise fulfilment and
proof-term construction. Diagnosed 2026-09-08 — evidence, the exposed call
paths, and the open upstream question in
**[future_assign_interrupt.md](my_better_isabelle_prover/patches/future_assign_interrupt.md)**.

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

- **Isabelle2024** — `register_thy` and `expose_foreign` ship natively, so no
  patch is needed for them.
- **Isabelle2025-2** — `register_thy` applies and reverse-detects cleanly. The
  two retired Scala features were reversed from this distribution before removal,
  verified byte-for-byte against the pristine sources with `isabelle scala_build
  -f` re-run, so its Scala is stock again.
- **`future_assign_interrupt`** — authored against pristine source for both
  versions (the same diff serves both: that region is byte-identical). Applied
  and runtime-verified on Isabelle2025-2: 15 consecutive corpus passes clean,
  against a pre-fix baseline that reproduced within 9 minutes.
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
- **[RELEASE.md](RELEASE.md)** — how a version is cut and published to PyPI.
- Feature docs (rationale / evidence):
  [`future_assign_interrupt.md`](my_better_isabelle_prover/patches/future_assign_interrupt.md),
  [`expose_foreign.md`](my_better_isabelle_prover/patches/expose_foreign.md),
  [`register_thy.md`](my_better_isabelle_prover/patches/Isabelle2025-2/register_thy.md),
  [`show_types_nv.md`](my_better_isabelle_prover/patches/show_types_nv.md),
  [`expose_map_syn.md`](my_better_isabelle_prover/patches/expose_map_syn.md).
