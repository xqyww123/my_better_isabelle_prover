# Feature: `pide_control` — PIDE LSP Control Extensions

Bundles related PIDE LSP requests that Isabelle's stock `vscode_server` does
not expose:

- **`PIDE/theory_status`** — query per-theory processing status (including
  auto-loaded dependencies).
- **`PIDE/cancel_execution`** — globally cancel all running processing.
- **`PIDE/command_at_position`** — return the full source text and range of the
  Isar command enclosing a given position.
- **`PIDE/output_at_position`** — return the source text, range, AND rendered
  prover output of the Isar command enclosing a given position, in one request.

## Why one feature

These requests edit the same two Scala files at adjacent points: they each add an
object to `lsp.scala`, a handler method + a `match` case to
`language_server.scala`. Authored as separate features, their diffs overlapped
(the second one's hunk context contained the first one's inserted lines), which
forced a fragile apply-order dependency. They are merged into a single feature so
the shared-file edits live in **one self-consistent patch each** — no inter-patch
overlap, no ordering. The runtime story already ties them together too: a client
cancels via `PIDE/cancel_execution`, then polls `PIDE/theory_status` to confirm
`running == 0`.

Trade-off accepted: the two cannot be applied/reversed independently.

## Patch files

```
patches/<version>/pide_control/
├── execution.ML.patch        # ML: Execution.cancel_execution()
├── protocol.ML.patch         # ML: Document.cancel_execution protocol command
├── protocol.scala.patch      # Scala: protocol command plumbing
├── lsp.scala.patch           # Scala: LSP.Theory_Status + Cancel_Execution + Command_At_Position [+ Output_At_Position] objects
└── language_server.scala.patch  # Scala: handler methods + main-loop dispatch cases
```

`lsp.scala.patch` and `language_server.scala.patch` are combined diffs containing
all of the above requests' insertions; the other three come from the cancellation
side only. All five target distinct files, so there is no intra-feature ordering
concern.

Apply from the Isabelle root:
```bash
cd $ISABELLE_HOME
for p in execution.ML protocol.ML protocol.scala lsp.scala language_server.scala; do
  patch -p1 -F0 < patches/<version>/pide_control/$p.patch
done
bin/isabelle scala_build -f
```

or via the manager (handles ordering, idempotency, and `scala_build`):
```bash
python -m my_better_isabelle_prover --isabelle-bin $ISABELLE_HOME/bin/isabelle \
  patch --feature pide_control
```

### Difference between versions

- **`Document_Status.Node_Status.make()`** in `language_server.scala`:
  Isabelle2024 takes `(state, version, name)`; Isabelle2025-2 adds a leading
  `now: Date` → `(now, state, version, name)`.
- **`PIDE/output_at_position`** handler body differs between versions because
  Isabelle2025-2 rewrote `dynamic_output.scala` to route rendering through
  `server.editor.output(snapshot, offset)` + `Pretty_Text_Panel`. Both versions
  keep the SAME command selection (`command_iterator`) and render the command's
  results with `Browser_Info.Node_Context.make_html` + `HTML.source`, but 2025-2
  needs two adaptations:
    1. `Rendering.output_messages` was removed → its body is inlined
       (`results.iterator.map(_._2).filterNot(Protocol.is_result).partition(Protocol.is_state)`,
       states prepended iff `editor_output_state`).
    2. `Resources.source_file` moved to `Store` → use `session.store.source_file`,
       which returns a *platform* path, so re-standardize with `File.standard_path`
       before `Path.explode` (mirrors stock `pretty_text_panel.scala`'s `make_ref`).
  The 2025-2 patch was authored and round-trip-verified against pristine source but
  **not compiled** (per the 2024-only build/test scope).
- Otherwise the inserted code is identical; only surrounding line numbers differ.

## `PIDE/theory_status`

### Problem
`vscode_server` gives an LSP client no visibility into the processing status of
auto-loaded dependency files. Decorations are only sent for `didOpen` files;
diagnostics only for files with errors. During a long proof in a dependency, the
client sees nothing.

### Solution / Protocol
A request returning `Document_Status.Node_Status` for **all** loaded theories
(opened and auto-loaded). Response:
```json
{
  "theories": [
    {
      "node_name": "/path/to/A.thy",
      "theory_name": "Test.A",
      "external": false,
      "imports": [ {"node_name": "/path/to/B.thy", "theory_name": "Test.B"} ],
      "ok": true, "total": 8, "unprocessed": 0, "running": 0, "warned": 0,
      "failed": 0, "finished": 8, "canceled": false, "consolidated": true,
      "percentage": 100
    }
  ]
}
```

| Field | Source | Description |
|-------|--------|-------------|
| `node_name` / `theory_name` | `model.node_name` | File path / qualified name |
| `external` | `model.external_file` | `true` = auto-loaded dependency |
| `imports` | `snapshot.node.header.imports` | imported theories |
| `ok` | `Node_Status.ok` | `failed == 0` |
| `total`/`unprocessed`/`running`/`warned`/`failed`/`finished` | `Node_Status` | command counts |
| `canceled` | `Node_Status` | processing canceled |
| `consolidated` | `Node_Status` | fully finished incl. forked proofs |
| `percentage` | `Node_Status` | 0–100, 100 only when consolidated |

## `PIDE/cancel_execution`

### Problem
`vscode_server` has no way to immediately cancel ALL processing globally
(caret moves / edits / `Execution.discontinue()` / `Execution.cancel(exec_id)`
are each insufficient on their own).

### Solution / Protocol
A request that atomically (1) sets `execution_id := Document_ID.none`, (2) collects
all future groups from the `execs` table, (3) interrupts each via
`Future.cancel_group`. ML implementation in `Execution.cancel_execution()`.

**Response:** `{ "cancelled": true }` — fire-and-forget ("cancel requested", not
"cancel confirmed"). Proof methods interrupt within milliseconds; blocking ops
(e.g. `OS.Process.sleep`) run to completion. Client should poll
`PIDE/theory_status` until `running == 0`. Recovery is automatic: the next edit
triggers `Document.update` → fresh `execution_id`.

## `PIDE/command_at_position`

### Problem
`vscode_server` exposes proof state (state panel) and output (dynamic output)
tied to a caret, but never the **command** itself. An LSP client has no way to
recover the full source text or range of the Isar command enclosing a position —
the protocol only emits per-element decoration ranges (and only for
running/unprocessed commands), and `Isabelle_RPC_Host` has no outer-syntax
command splitter. The enclosing command is the natural unit for reporting proof
state (state is per-command, not per-character).

### Solution / Protocol
A `RequestTextDocumentPosition` request that resolves the command at an explicit
position — no caret move, so it composes with any other query and is reusable by
multiple tools (e.g. goal state and command output). Implementation:
`rendering_offset(node_pos)` → `(rendering, offset)`, then
`snapshot.node.command_iterator(offset).next()` gives `(command, start)`; the
reply carries `command.source` and `Text.Range(start, start + command.length)`
converted to line/character via `model.content.doc.range`.

**Request:** `PIDE/command_at_position` with the standard text-document-position
params:
```json
{ "textDocument": { "uri": "file:///path/A.thy" },
  "position": { "line": 8, "character": 4 } }
```
**Response** (`source`/`range` present when a non-ignored command is found,
omitted otherwise):
```json
{
  "source": "apply (rule someThm\n  [where x = y])",
  "range": { "start": {"line": 8, "character": 2},
             "end":   {"line": 9, "character": 16} }
}
```
Line/character are 0-indexed LSP coordinates. The range spans the whole command,
including any trailing whitespace that belongs to its span.

## `PIDE/output_at_position`

### Problem
The stock way to read a command's prover output is the `PIDE/dynamic_output`
notification, which the server pushes only when the **caret moves to a position
whose Output-panel content differs**. Two consequences make it unreliable for an
on-demand client: (1) a redundant `caret_update` to the *same* position is a no-op
— no push, so a poll for the same line blocks forever; (2) it depends on the caret
mechanism and, when auto-tools (`auto_solve_direct`, quickcheck, …) keep the
document active, the client-side "settled" fallback never fires either. Verified
experimentally: re-querying the same caret never receives a `dynamic_output`.

### Solution / Protocol
A `RequestTextDocumentPosition` request that resolves the command at an explicit
position (same selection as `command_at_position`) and renders that command's
output **server-side**, returning it in the response — no caret move, no push, no
dedup. Because it renders the *whole command's* results
(`snapshot.command_results(command)`), the precise offset within the command is
irrelevant, so even a caret on the first line of a multi-line command yields the
full output. The rendering reuses `dynamic_output.scala`'s own pipeline:
`Rendering.output_messages` → `Browser_Info.Node_Context.make_html` →
`HTML.source` (identical HTML to what the Output panel shows).

**Request:** `PIDE/output_at_position` with the standard text-document-position
params (as above).
**Response** (`source`/`range`/`content` present when a non-ignored command is
found, omitted otherwise):
```json
{
  "source": "by simp",
  "range": { "start": {"line": 5, "character": 2},
             "end":   {"line": 5, "character": 9} },
  "content": "<pre class=\"source\"><span class=\"writeln_message\">theorem foo: 1 + 1 = 2</span></pre>"
}
```
`content` is the Output-panel HTML; the client parses its CSS classes
(`writeln_message`, `warning`, `error`, `information`/`state_message`,
`tracing_message`, …) into typed messages.

## Test results

`theory_status` verified 2026-05-25 (A.thy importing B.thy with `by (sleep 30)`):
auto-loaded B.thy reported with `external=true`, `running=1` during the 30s forked
proof, `consolidated=true` after, `ok=false` on failure — on both Isabelle2024 and
Isabelle2025-2.

`cancel_execution` verified with an interruptible ML loop (`expose_interrupt()`):
`running=0` within 1–2s of the request, stable until restarted, resumes normally
after a subsequent edit.

`output_at_position` verified 2026-06-03 on Isabelle2024 (`scala_build` clean):
across ML `writeln`/`tracing`/`warning`, `lemma`/`apply` proof-state, a multi-line
`lemma`, and terminal `by simp`, every query returns in 0–1s with the correct
typed output — and critically, **re-querying the same line no longer hangs** (the
`dynamic_output` same-caret block is gone). Blank/comment lines return no command.
The Isabelle2025-2 patch is authored + round-trip-verified against pristine source
but not yet compiled/tested.
