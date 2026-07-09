# Patch: `Sign.map_syn` — Expose Wholesale Syntax Replacement

## Problem

A theory's entire *inner* syntax — every `notation` / `syntax` mixfix, all
translations, and the print machinery — lives in a single `Syntax.syntax` value
stored in the theory's `Sign` (`src/Pure/sign.ML`), inside a **module-private**
theory-data slot:

```ml
structure Data = Theory_Data'
(
  type T = sign;
  val empty = make_sign (Syntax.empty_syntax, Type.empty_tsig, Consts.empty);
  ...
);
```

The only function that can replace that whole `Syntax.syntax` value is

```ml
fun map_syn f = map_sign (fn (syn, tsig, consts) => (f syn, tsig, consts));
```

but it is **not exported** — the `SIGN` signature ends before it, so from
user-level Isabelle/ML `Sign.map_syn` raises

```
Value or constructor (map_syn) has not been declared in structure Sign
```

Every *exported* syntax writer is **incremental**: `Sign.syntax` /
`Sign.notation_global` / `Sign.type_notation_global` and the `syntax` /
`no_syntax` / `notation` / `no_notation` commands all take a `bool` add/delete
flag plus the exact declarations, so removing syntax requires re-stating every
clause. There is no public "clear all" and no public enumerator over the syntax
tables to drive one (the `Syntax` internal tabs are private to that structure).

The context level offers no escape either: `Proof_Context.map_syntax` is also
private, and `Local_Syntax` always rebuilds the local syntax from
`Sign.syntax_of thy` (`src/Pure/Syntax/local_syntax.ML`, `init` / `build_syntax`),
so it cannot present a base with the theory syntax stripped.

Consequently, wholesale clearing (or any wholesale rewrite) of a theory's inner
syntax — e.g. `Sign.map_syn (K Syntax.empty_syntax)` — is impossible without
editing vendored Pure. This patch makes it possible.

## Solution

Add a single declaration to the `SIGN` signature in `src/Pure/sign.ML`, right
after `syntax_of`:

```ml
  val syntax_of: theory -> Syntax.syntax
  val map_syn: (Syntax.syntax -> Syntax.syntax) -> theory -> theory
```

The function body already exists (unchanged) further down the structure; the
patch only exports it. Nothing else changes — no new logic, no behavioural
change to any existing symbol.

### Usage

```ml
(* wipe ALL inner syntax of a theory *)
val thy' = Sign.map_syn (K Syntax.empty_syntax) thy;

(* or transform it, e.g. keep only a hand-built minimal syntax *)
val thy' = Sign.map_syn (fn _ => my_minimal_syntax) thy;
```

> [!WARNING]
> `Syntax.empty_syntax` (`src/Pure/Syntax/syntax.ML`) has an **empty lexicon and
> empty grammar**. After `Sign.map_syn (K Syntax.empty_syntax)` the theory can no
> longer parse or print *any* inner term or type — not `a + b`, not `A ⟹ B`, not
> application or numerals. This is by design (full clear); re-install a base inner
> syntax afterwards if you need the theory to remain usable. Outer command syntax
> (`theorem`, `by`, …) is unaffected — it is managed by `Keyword`/`Thy_Header`,
> not `Syntax.syntax`.

## Patch files

```
patches/Isabelle2025-2/expose_map_syn/
└── sign.ML.patch
patches/Isabelle2024/expose_map_syn/
└── sign.ML.patch
```

The two versions' `SIGN` signatures are byte-identical in the patched region, so
the diff is the same for both. Apply from the Isabelle root:

```bash
cd $ISABELLE_HOME
patch -p1 < patches/<version>/expose_map_syn/sign.ML.patch
```

No `isabelle scala_build` needed — this is a **pure ML change**. It takes effect
only when the **Pure heap is rebuilt** (`sign.ML` is core Pure, compiled into the
heap; a running/heap-based REPL will not see the new symbol until Pure and its
downstream heaps are rebuilt).

## Verification status

- Authored against pristine `src/Pure/sign.ML` for both Isabelle2024 and
  Isabelle2025-2 via `diff -u`; the patched region (`SIGN` signature, lines
  12–18) is identical across the two releases.
- **Not yet done:** applying it, rebuilding the Pure heap, and calling
  `Sign.map_syn` from a running REPL. Run `my-better-isabelle status
  --feature expose_map_syn` (expect `not-applied` on pristine source, `applied`
  after `patch`, back to `not-applied` after `unpatch`), then rebuild Pure and
  do a REPL round-trip before relying on it.
