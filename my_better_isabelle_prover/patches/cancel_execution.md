# Patch: `PIDE/cancel_execution` — Global Execution Cancellation

## Problem

Isabelle's `vscode_server` has no way to immediately cancel ALL processing globally.
Existing mechanisms are insufficient:

- **Caret move**: No effect on running commands
- **Edit only**: Command re-executes (still in perspective)
- **Caret to line 0 + edit**: Stops target file, but dependencies continue
  (they remain `node_required=true` because the header import command is still processed)
- **`Execution.discontinue()`**: Prevents NEW commands from starting but does not
  interrupt currently running threads
- **`Execution.cancel(exec_id)`**: Interrupts a specific exec's future groups but
  requires knowing the exec_id

## Solution

A new `PIDE/cancel_execution` LSP **request** that atomically:
1. Sets `execution_id := Document_ID.none` (prevents new commands from starting)
2. Collects ALL future groups from the `execs` table
3. Sends `interrupt_thread` to each group via `Future.cancel_group`

This combines `discontinue` + cancel-all-groups into one operation. The ML
implementation lives in `Execution.cancel_execution()`.

## Protocol

**Request:** `PIDE/cancel_execution` (no parameters)

**Response:**
```json
{
  "cancelled": true
}
```

### Reply semantics

The response is **fire-and-forget**: `"cancelled": true` means "cancel requested",
not "cancel confirmed". The actual cancellation happens asynchronously:

- **Proof methods** (`auto`, `simp`, `blast`): call `expose_interrupt()` periodically
  → interrupted within milliseconds
- **Blocking operations** (`OS.Process.sleep`): don't check interrupts → run to completion
- **Theory workers**: check `Execution.is_running(execution_id)` before each command
  → see false after discontinue → stop iterating

The client should poll `PIDE/theory_status` to confirm `running == 0`.

### Recovery

Every `Document.update` (triggered by any edit) naturally follows this flow:
```
Execution.discontinue()    → stop eval chain
Document.update(...)       → new_execution() → Execution.start() → fresh execution_id
Document.start_execution() → schedule nodes with new execution_id
```

So the next `evaluate_to` call (caret_update + didChange) automatically resumes processing.
No special recovery needed.

## Patch files

### Isabelle2024

```
patches/Isabelle2024/cancel_execution/
├── execution.ML.patch
├── protocol.ML.patch
├── protocol.scala.patch
├── lsp.scala.patch
└── language_server.scala.patch
```

Apply from the Isabelle2024 root:
```bash
cd $ISABELLE2024_HOME
for p in execution.ML protocol.ML protocol.scala lsp.scala language_server.scala; do
  patch -p1 < patches/Isabelle2024/cancel_execution/$p.patch
done
bin/isabelle scala_build -f
```

### Isabelle2025-2

```
patches/Isabelle2025-2/cancel_execution/
├── execution.ML.patch
├── protocol.ML.patch
├── protocol.scala.patch
├── lsp.scala.patch
└── language_server.scala.patch
```

Apply from the Isabelle2025-2 root:
```bash
cd $ISABELLE2025_HOME
for p in execution.ML protocol.ML protocol.scala lsp.scala language_server.scala; do
  patch -p1 < patches/Isabelle2025-2/cancel_execution/$p.patch
done
bin/isabelle scala_build -f
```

### Difference between versions

The cancel_execution code is **identical** in both versions. Only the insertion
line numbers differ (due to different surrounding code in lsp.scala, protocol.scala,
and language_server.scala).

## Test results

Tested with `Slow.thy` containing an interruptible ML loop (`loop 1000000000` with
`expose_interrupt()`). After sending `PIDE/cancel_execution`:
- `running=0` within 1-2 seconds (proof methods interrupted immediately)
- State remains stable at `running=0` until explicitly restarted
- After restart (caret_update + edit), processing resumes normally
