# Patch: `show_types_nv` — Type Annotation Only on Non-Variables

## Problem

A custom printing option `show_types_nv` ("nv" = *no variables*) that, when
`show_types` is on, **suppresses the type annotation of free/fixed variables**
while still annotating everything else (constants, in particular). It is **not a
stock Isabelle option** — it was added by hand to the vendored Isabelle2024
tree, and the change was never carried over to Isabelle2025-2.

It is consumed by the term-deformalization / printing code that produces the
textual form of goals and premises fed to the embedding model
(`contrib/Isa-Mini/translator/library/print_formats.ML`, which sets
`show_types_nv true` for one of its formats), and it is referenced from the
theorem-relevance extraction stack. Without it, those `Config.put
Printer.show_types_nv …` sites fail to compile on 2025-2.

## Semantics

When a free/fixed variable's type *would* be shown — i.e. under any of
`show_types`, `show_sorts` (folded into `show_types`), or `show_markup` — turning
`show_types_nv` on suppresses that annotation: the variable `x` prints as `x`
(no `::T`, no type hover markup), whereas a constant still prints with its type
constraint. Schematic variables (`?x`), bound variables, and `_idtdummy` are
**unaffected** (they keep whatever the other `show_*` flags dictate).

> Note: the option's own doc string in `etc/options` reads "effective only when
> `show_types` is on" — this is the original 2024 wording and is slightly loose;
> the flag in fact also fires under `show_sorts` / `show_markup` alone, per the
> gating code below. The doc string is kept verbatim for fidelity with the
> user's 2024 tree (the 2024 patch is a reverse-recording, so editing it there
> would desync the record), and the 2025-2 copy is kept identical for parity.

The flag is an `option ... for content` bool (default `false`), a
`Printer.show_types_nv : bool Config.T`, registered as an attribute so
`term [show_types_nv] …` and `[[show_types_nv]]` work.

## Touched files (both versions)

| File | Change |
|------|--------|
| `etc/options` | add `option show_types_nv : bool = false for content` after `show_types` |
| `src/Pure/Syntax/printer.ML` | add signature entry + `Config.declare_option_bool ("show_types_nv", …)` |
| `src/Pure/Isar/attrib.ML` | add `register_config_bool Printer.show_types_nv` |
| `src/Pure/Syntax/syntax_phases.ML` | thread an `is_v` flag through the variable-printing helper and gate the type constraint on `not is_v orelse not show_types_nv` |

Pure ML + one options file. **No `scala_build`** — the change takes effect when
the Pure heap is rebuilt (`isabelle build -b Pure`, or automatically on next
launch/build).

## Difference between versions

The mechanical three (`etc/options`, `printer.ML`, `attrib.ML`) are identical in
spirit across versions.

The interesting one is `syntax_phases.ML`, whose `term_to_ast` was refactored
between 2024 and 2025-2:

- **Isabelle2024** — the helper is `constrain t T0`. The patch adds a leading
  `is_v` parameter (`constrain is_v t T0`), passes `true` at the `_free` call
  site and `false` at `_var` / `_bound` / `_idtdummy`, and inside `constrain`
  shadows `show_types`/`show_markup` with `… andalso (not is_v orelse not
  show_types_nv)`.
- **Isabelle2025-2** — the helper is now `variable v T` (shared by `_free`,
  `_var`, `_bound`, `_idtdummy`), and variable type display is already factored
  into `show_var_types`. The patch adds the same `is_v` parameter
  (`variable is_v v T`), passes `true`/`false` at the same four call sites, and
  gates the single constraint with
  `(show_var_types andalso (not is_v orelse not show_types_nv)) ?`.

Both reproduce the exact same observable behaviour (free-variable types
suppressed, everything else untouched).

## Patch files

```
patches/Isabelle2024/show_types_nv/{etc-options,printer.ML,attrib.ML,syntax_phases.ML}.patch
patches/Isabelle2025-2/show_types_nv/{etc-options,printer.ML,attrib.ML,syntax_phases.ML}.patch
```

Independent of the other features (touches disjoint files), so no `order.txt`
entry is needed. Apply just this feature with:

```bash
my-better-isabelle patch --feature show_types_nv --no-build
# then rebuild the Pure heap so the ML change takes effect:
isabelle build -b Pure
```

## Verification status

- **Isabelle2025-2** — all four hunks apply cleanly forward against the pristine
  vendored tree (`patch -p1 -F0 --dry-run`). Authored from the pristine 2025-2
  source.
- **Isabelle2024** — recorded from the diff of pristine official Isabelle2024
  vs. the already-hand-patched `contrib/Isabelle2024`; all four hunks
  reverse-detect cleanly, so `status` reports `applied` for that tree. (2024
  ships the manual edit already; the patch just makes it reproducible /
  reversible.)
- **Runtime** — after applying + rebuilding Pure, confirm
  `Config.get \<^context> Printer.show_types_nv` resolves and that
  `term [show_types, show_types_nv] \<open>\<lambda>x::nat. x + c\<close>` drops the `::nat`
  on the bound/free variable while keeping constant type info.
