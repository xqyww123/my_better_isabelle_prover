# Patch: `expose_foreign` — Stop Hiding Poly/ML's FFI Structures

## Problem

Isabelle2025-2 hides four Poly/ML structures from every ML environment:

```ml
(* src/Pure/ML/ml_name_space.ML *)
val hidden_structures = ["CInterface", "Foreign", "RunCall", "Signal"];
```

`src/Pure/ML_Bootstrap.thy` then calls
`List.app ML_Name_Space.forget_structure ML_Name_Space.hidden_structures`, which
invokes `PolyML.Compiler.forgetStructure` on the *global* name space while Pure
is bootstrapping. The removal is baked into the `Pure` heap, so every downstream
session inherits it, and any ML file touching the FFI fails to compile:

```
ML error: Structure (Foreign) has not been declared
ML error: Structure (Memory) has not been declared in structure Foreign
```

This is new. **Isabelle2024 had `hidden_structures = []`** — the FFI was
reachable, and code written against it (see below) compiled without ceremony.

## Why it matters here

`contrib/Semantic_Embedding/Tools/simd_vector.ML` dlopens the Highway SIMD kernel
(`libisabelle_vector.so`) through `Foreign.loadLibrary` / `buildCall3` /
`buildCall7`, and moves vector bytes with `Foreign.Memory` and `RunCall`:

```ml
val lib = loadLibrary (vector_library_path ())
val dot_fun = buildCall3 (dot_sym, (cWord8Vector, cWord8Vector, cSsize), ...)
val w = RunCall.loadNativeWord (src, RunCall.bytesPerWord + !j)
```

Under Isabelle2025-2 none of this compiles. There is no supported alternative:
Poly/ML's FFI *is* `Foreign`, and `RunCall` is how one reads raw words out of an
ML value without a copy.

## What the patch does

Removes `CInterface`, `Foreign` and `RunCall` from `hidden_structures`, leaving

```ml
val hidden_structures = ["Signal"];
```

`Signal` stays hidden: nothing in this tree uses it, and letting theory ML install
process signal handlers is a genuinely bad idea. `RunCall` cannot be left out —
`simd_vector.ML` needs it, so a patch exposing only `Foreign` would not help.

The list feeds two other places, and both follow correctly:

- `ML_Bootstrap.thy` forgets exactly the names still in it, so the three
  structures survive into the `Pure` heap.
- `bootstrap_structures = [...] @ hidden_structures`, and `sml_structure` is
  everything *not* in `bootstrap_structures`. Dropping the three from
  `hidden_structures` therefore puts them back into the `SML` environment too —
  which is precisely where Isabelle2024 had them.

## Consequences

The patched file is Pure ML source, so **the `Pure` heap (and everything built on
it) must be rebuilt** before the change is visible. `isabelle scala_build` is not
involved; apply with `--no-build`.

Exposing the FFI means theory ML can call arbitrary native code and read raw
memory. That is the point — it is also what Isabelle2024 permitted — but it does
remove a guard rail. Only sessions that need `Foreign` should exercise it.

## Versions

- `Isabelle2024` — not needed, `hidden_structures` is already `[]`.
- `Isabelle2025-2` — `ml_name_space.ML.patch`.
