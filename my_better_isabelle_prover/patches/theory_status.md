# Patch: `PIDE/theory_status` — Per-Theory Processing Status Query

## Problem

Isabelle's `vscode_server` provides no way to query the processing status of
auto-loaded dependency files. When file A.thy imports B.thy:

- **Decorations** (`PIDE/decoration`): only sent for files opened via
  `didOpen` (`node_visible=true`). Auto-loaded dependencies are marked
  `external=true` → `node_visible=false` → empty decorations.
- **Diagnostics** (`publishDiagnostics`): only sent for files **with errors**.
  Clean dependencies produce no notifications at all.

This means an LSP client has **zero visibility** into dependency processing.
During a 30-second proof in B.thy, the client sees A.thy as "fully processed"
with no indication that anything is still running.

**Empirically verified** (2026-05-25) with a test where B.thy contains
`by (sleep 30)`: no decorations, no diagnostics for B.thy during the entire
30-second window. Only a failure diagnostic arrives after the proof fails.

## Solution

A new `PIDE/theory_status` LSP **request** that returns
`Document_Status.Node_Status` for ALL loaded theories — both explicitly
opened and auto-loaded dependencies. This data already exists inside Isabelle
(`Node_Status.make()` with a built-in `.json` serializer) but was not exposed
via any LSP message.

## Protocol

**Request:** `PIDE/theory_status` (no parameters)

**Response:**
```json
{
  "theories": [
    {
      "node_name": "/path/to/A.thy",
      "theory_name": "Test.A",
      "external": false,
      "imports": [
        {"node_name": "/path/to/B.thy", "theory_name": "Test.B"}
      ],
      "ok": true,
      "total": 8,
      "unprocessed": 0,
      "running": 0,
      "warned": 0,
      "failed": 0,
      "finished": 8,
      "canceled": false,
      "consolidated": true,
      "percentage": 100
    },
    {
      "node_name": "/path/to/B.thy",
      "theory_name": "Test.B",
      "external": true,
      "imports": [
        {"node_name": "~~/src/HOL/Main.thy", "theory_name": "HOL.Main"}
      ],
      "ok": true,
      "total": 10,
      "unprocessed": 0,
      "running": 1,
      "warned": 0,
      "failed": 0,
      "finished": 9,
      "canceled": false,
      "consolidated": false,
      "percentage": 99
    }
  ]
}
```

### Field descriptions

| Field | Source | Description |
|-------|--------|-------------|
| `node_name` | `model.node_name.node` | File path |
| `theory_name` | `model.node_name.theory` | Qualified theory name (e.g. `Test.B`) |
| `external` | `model.external_file` | `true` = auto-loaded dependency, `false` = explicitly opened |
| `imports` | `snapshot.node.header.imports` | List of imported theories (each with `node_name` + `theory_name`) |
| `ok` | `Node_Status.ok` | `failed == 0` |
| `total` | `Node_Status.total` | `unprocessed + running + warned + failed + finished` |
| `unprocessed` | `Node_Status` | Commands not yet started |
| `running` | `Node_Status` | Commands currently executing |
| `warned` | `Node_Status` | Commands completed with warnings |
| `failed` | `Node_Status` | Commands that failed |
| `finished` | `Node_Status` | Commands completed successfully |
| `canceled` | `Node_Status` | Whether processing was canceled |
| `consolidated` | `Node_Status` | Whether the theory is fully finished (including forked proofs) |
| `percentage` | `Node_Status` | 0–100, reaches 100 only when consolidated |

## Patch files

### Isabelle2024

```
patches/Isabelle2024/theory_status/
├── lsp.scala.patch
└── language_server.scala.patch
```

Apply from the Isabelle2024 root:
```bash
cd $ISABELLE2024_HOME
patch -p1 < patches/Isabelle2024/theory_status/lsp.scala.patch
patch -p1 < patches/Isabelle2024/theory_status/language_server.scala.patch
bin/isabelle scala_build -f
```

### Isabelle2025-2

```
patches/Isabelle2025-2/theory_status/
├── lsp.scala.patch
└── language_server.scala.patch
```

Apply from the Isabelle2025-2 root:
```bash
cd $ISABELLE2025_HOME
patch -p1 < patches/Isabelle2025-2/theory_status/lsp.scala.patch
patch -p1 < patches/Isabelle2025-2/theory_status/language_server.scala.patch
bin/isabelle scala_build -f
```

### Difference between versions

The only code difference is `Document_Status.Node_Status.make()`:
- **Isabelle2024**: `make(state, version, name)` — 3 parameters
- **Isabelle2025-2**: `make(now, state, version, name)` — 4 parameters (added `now: Date`)

## Test results

Tested with A.thy importing B.thy, where B.thy has `lemma "True" by (sleep 30)`.
Only A.thy opened via `didOpen`.

### Isabelle2024 (verified 2026-05-25)

| Time | A.thy | B.thy |
|------|-------|-------|
| 15–40s | pct=100%, consolidated=True | **pct=99%, running=1**, consolidated=False |
| ~42s | — | `publishDiagnostics` (proof failed) |
| 45s+ | pct=100%, ok=True | pct=100%, running=0, **ok=False**, consolidated=True |

### Isabelle2025-2 (verified 2026-05-25)

| Time | A.thy | B.thy |
|------|-------|-------|
| 14–39s | pct=100%, consolidated=True | **pct=99%, running=1**, consolidated=False |
| ~41s | — | `publishDiagnostics` (proof failed) |
| 44s+ | pct=100%, ok=True | pct=100%, running=0, **ok=False**, consolidated=True |

Both versions correctly:
- Report auto-loaded dependencies (B.thy with `external=true`)
- Show `running=1` during the 30s forked proof
- Transition to `consolidated=true` after completion
- Report `ok=false` when the proof fails
