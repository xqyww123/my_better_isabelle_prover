# Patch: `Thy_Info.register_thy` — Restore Removed Theory Registration

## Problem

`Thy_Info.register_thy: theory -> unit` existed in Isabelle2024
(`src/Pure/Thy/thy_info.ML`) but was **removed** in Isabelle2025-2 as part of
Makarius's theory-loader refactoring (the same change renamed `use_thy` to
`use_thy_legacy`; see `NEWS` around the "isabelle ML_process" entry). The
official direction is to process individual theories via the Scala-side
`isabelle process_theories` / headless PIDE, not the low-level ML loader.

`Isa-REPL` depends on `register_thy` to inject an **already-built, in-memory**
`theory` value into the global loader database (`Thy_Info`'s private
`global_thys`), so that the theory becomes visible to **Isabelle-internal**
name resolution — e.g. a later `theory Foo imports T` resolved through
`Thy_Info.get_theory` / `check_theory`, disk `.thy` files loaded via
`use_theories`, and PIDE.

There is no non-invasive replacement:

- The only public `Thy_Info` writer that inserts a given theory value
  (`update_thy`) is **private** to the structure; the exported signature only
  offers the file-based `use_theories` / `use_thy_legacy` / `remove_thy` /
  `finish`.
- **Isabelle/Scala cannot help**: the ML↔Scala bridge (`Scala.function`)
  marshals only `Bytes`/strings, so a live ML `theory` value can neither cross
  it nor be injected into ML-side `global_thys`. The Scala-populated
  `Resources` `global_theories` field is a `name → session-qualifier` string
  map, not theory storage.
- The REPL's own `REPL.global_theories` registry only governs the REPL's own
  `thy_loader` import resolution — it is invisible to Isabelle internals.

So restoring `register_thy` requires editing vendored Pure. This patch does
exactly that.

## Solution

Re-add `register_thy` to `src/Pure/Thy/thy_info.ML`, restored verbatim from the
Isabelle2024 source, with a **single adaptation** for the new node type.

In 2025-2 the loader graph node changed to
`deps option * (theory * Document_Output.segment list) option`
(was `deps option * theory option` in 2024), so the internal `update` now takes
a `(theory, segments)` pair. The restored function therefore passes
`(theory, [])` instead of `theory`:

```ml
fun register_thy theory =
  let
    val name = Context.theory_long_name theory;
    val {master, ...} = Resources.check_thy (Resources.master_directory theory) name;
    val imports = Resources.imports_of theory;
  in
    change_thys (fn thys =>
      let
        val thys' = remove name thys;
        val _ = writeln ("Registering theory " ^ quote name);
      in update (make_deps master imports) (theory, []) thys' end)  (* 2024: theory *)
  end;
```

All dependencies (`Resources.check_thy`, `Resources.imports_of`, `make_deps`,
`update`, `remove`, `change_thys`) still exist in the 2025-2 structure.

### Behaviour note (inherited from 2024, not introduced here)

`register_thy` calls `Resources.check_thy`, which does `File.read` of the
theory's master `.thy` file. So registration only works for theories that have
a backing file on disk. In `Isa-REPL` this is satisfied by the existing
`write_thy` path (`REPL.ML`, `parse_text`), which writes the evaluated source
to `<master_dir>/<name>.thy` and is gated by the same `register_theory'` flag.
Registering a purely in-memory, never-written theory will raise a
file-not-found error — exactly as it would have in 2024. Lifting that
restriction would be a separate change (bypassing the `check_thy` master-file
dependency) and is out of scope here.

`Isa-REPL` consumers (`library/REPL.ML` call site, `repl_server.sh` `fun reg`)
need **no changes** — the symbol they call simply exists again.

## Patch files

```
patches/Isabelle2025-2/register_thy/
└── thy_info.ML.patch
```

Apply from the Isabelle2025-2 root:
```bash
cd $ISABELLE2025_HOME
patch -p1 < patches/Isabelle2025-2/register_thy/thy_info.ML.patch
```

No `bin/isabelle scala_build` needed — this is a pure ML change (it takes
effect when the Pure heap is rebuilt).

### Difference between versions

Isabelle2024 still ships `register_thy` natively, so **no patch is required for
2024**. The 2025-2 patch is the 2024 function with the single `(theory, [])`
node-type adaptation described above.

## Verification status

The patch was checked to:

- apply cleanly with `patch -p1` (forward), and
- reverse-detect cleanly (`patch -R --dry-run -p1`), so the `patcher.py`
  status logic reports `APPLIED`/`NOT_APPLIED` correctly rather than `CONFLICT`,
- be discovered by `patches.discover_patches("Isabelle2025-2", "register_thy")`
  with `target_relative = src/Pure/Thy/thy_info.ML`.

**Not yet done:** rebuilding the Pure/HOL heap with the patch applied and
exercising `Thy_Info.register_thy` from a running REPL. Run a REPL round-trip
(evaluate a theory with `register_theory'` + `write_thy` on, then import it from
a second evaluation) before relying on it.
