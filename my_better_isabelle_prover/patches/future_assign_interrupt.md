# Feature: `future_assign_interrupt` — don't turn a cancelled future into `exception Option`

A correctness fix, not a capability: without it Isabelle silently converts an
asynchronous interrupt into `exception Option`, which surfaces as an
intermittent, traceless failure in any code that runs under `Timeout.apply` or
cancels future groups.

Applies to **Isabelle2024** and **Isabelle2025-2** — the defect and its
surrounding source are byte-identical in both, so the two patches are the same
diff. Pure ML, so no `scala_build`; it takes effect on the next Pure heap
rebuild.

## The defect

`src/Pure/Concurrent/future.ML`, `assign_result`:

```sml
val _ =
  (case Exn.capture_body (fn () => Single_Assignment.assign result res) of
    Exn.Exn (exn as Fail _) => …      (*only Fail is re-raised*)
  | _ => ());                          (*everything else is dropped — including an interrupt*)
val ok =
  (case the (Single_Assignment.peek result) of …   (*unassigned → the → Option*)
```

The code after the `case` assumes the result is assigned. That holds when
`assign` returns, and the `Fail` branch (duplicate assignment) re-raises. But a
third case exists and was silently dropped:

1. A racer group is cancelled, or a `Timeout.apply` deadline fires, and an
   **asynchronous interrupt** is delivered to the working thread.
2. It lands in the interruptible window of `Single_Assignment.assign`. The state
   mutation itself sits in an inner `uninterruptible_body` and cannot be
   interrupted; what can is the prologue, after `Multithreading.synchronized`'s
   `run e` has restored the caller's interrupt attributes and before that body is
   entered.
3. `Exn.capture_body` catches the interrupt, and `| _ => ()` throws it away.
   `capture_body` also consumes the thread's break flag, so the interrupt is now
   gone in both of its representations.
4. `the (Single_Assignment.peek result)` then meets a result that was never
   assigned, and raises `exception Option` at `General/basics.ML:84`.

A real interrupt has become a bogus `Option`, at a site that names neither.

## The fix

```sml
  | Exn.Exn exn => if Exn.is_interrupt exn then Exn.reraise exn else ()
  | Exn.Res _ => ());
```

Re-raise the interrupt, so the code below runs only when the assignment actually
happened. This lands at the single point all four callers of `assign_result`
pass through — `future_job`, `value_result`, `promise_group`, `fulfill_result` —
which is why no call site needs its own guard.

### Both interrupt forms, not just the proper one

`Exn.is_interrupt`, **not** the `Exn.is_interrupt_proper` used a few lines above.
`Exn.capture_body` is `Isabelle_Thread`'s shadowing version
(`isabelle_thread.ML:161-165`), which normalises what it catches:

```sml
fun capture f x = Res (f x) handle e => Exn (check_interrupt e);
fun check_interrupt exn =
  if Exn.is_interrupt_raw exn then make_interrupt (reset_interrupt ()) else exn;
fun make_interrupt break = if break then Exn.Interrupt_Break else Exn.Interrupt_Breakdown;
```

So a raw `Thread.Thread.Interrupt` never reaches this `case`. It arrives as
`Interrupt_Break`, or — when the thread's break flag had already been consumed —
as `Interrupt_Breakdown`. And `is_interrupt_proper` is `raw orelse break`
(`exn.ML:116`): it **misses `Interrupt_Breakdown`**, while `is_interrupt` covers
both (`exn.ML:117`). Both forms mean the same thing here — the assignment did not
happen — so both must be re-raised. The archived logs of this defect carried 239
`Interrupt_Breakdown` records against 11 `Option` events, so the form the narrower
predicate misses is not a corner case.

`Exn.reraise` rather than a bare `raise`: a bare one overwrites Poly/ML's raise
location and truncates the frame trace.

Note that `promise_group` (`future.ML:652` on 2025-2) already handles
`assign_result` raising an interrupt, so re-raising is within the existing
contract rather than a new obligation on callers.

### Why not re-raise everything

An earlier draft re-raised every non-`Fail` exception, on the grounds that
`assign` can only produce `Fail` or an interrupt anyway, so the wider form was
behaviourally identical and made the invariant structural. It was narrowed
deliberately: there is a brief window *after* the assignment has succeeded in
which an exception can still escape `assign` — the inner `uninterruptible_body`
restores the caller's interruptible attributes (`thread_attributes.ML`,
`with_attributes`) before its `Exn.release` — and in that case the old code was
right to carry on. Keying on the interrupt keeps the change confined to the path
that was actually broken.

## Which call paths are exposed

Only those that assign on the **caller's own thread**, with the caller's
interrupt attributes:

| entry point | exposed? |
|---|---|
| `Future.value`, `Future.value_result` | **yes** |
| `Future.map` on an already-finished future | **yes** (takes the `value_result` fast path) |
| `Future.cond_forks` with parallelism off | **yes** |
| `Future.fork` / `forks` | no — the worker thread runs with `interrupts = false` |
| `Future.fulfill_result` | no — wrapped in `Thread_Attributes.no_interrupts` |

Pure itself takes those paths from hot code: `Lazy.force`
(`Concurrent/lazy.ML:109,112,151`), promise fulfilment (`thm.ML:1184,2048`), and
proof-term construction (`proofterm.ML:258,363,480`). So the defect is reachable
from an ordinary simplifier call, not only from code that touches futures
directly.

## Evidence

Diagnosed 2026-09-08 with a probe in `assign_result` that changed no semantics —
it recorded what had been dropped and still raised the same `Option`:

```
future_probe.log     10:37:34.941  assign_result UNASSIGNED swallowed=INTERRUPT
event_log/exception  10:37:35.232  exn="Option"  raised=Concurrent/future.ML:450
```

Milliseconds apart, with the reasoner's own stage chain filling the gap. Before
the fix the corpus hit this within 9 minutes of starting.

The first fix verified was the wider "re-raise everything" draft: 15 consecutive
passes (~3h40m) clean, `REPLFail = 0`, and the passes also stopped dying with
`ConnectionResetError` — consistent with the swallowed interrupt having lost the
cancellation signal too, though that part was not verified separately. The
shipped narrow form is behaviourally identical on this path (only `Fail` and an
interrupt can reach the branch), but it is a different edit, so it was re-run
rather than inheriting that result.

Full investigation record: `OPTION_EXCEPTION_IN_PROOF_REPLAY.md` in the MLML
repository, section 「2026-09-08 结案」.

## Upstream

Not reported yet. Worth reporting together with the design question this fix
does **not** settle: after the re-raise the result variable is still unassigned,
so a later `Single_Assignment.await` on it would block forever. The previous
behaviour left it unassigned too, so this is not a regression, but the thorough
fix would assign `Exn.Exn Interrupt` as the result before propagating — a change
to Isabelle's concurrency semantics, and upstream's call to make.
