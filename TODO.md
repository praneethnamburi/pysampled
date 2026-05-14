# TODO

Open design questions and deferred work for the 1.3.x cycle. Release
narrative lives in [`CHANGELOG.md`](CHANGELOG.md).

## Open design work

- **Merge classmethods (deferred from 1.2.0).** Initial
  `merge_along_signal_name` / `merge_along_signal_coord` /
  `merge_along_time` prototypes were pulled before release; the
  design needs more work before re-landing. Open questions to
  discuss collaboratively: meta-merge collision rule (last-wins
  was the prototype, but probably wrong); history representation
  (the prototype's `parts_history_tails` is awkward); contiguity
  tolerance for time merges (strict-by-default rejects float-slice
  round trips that overlap by one sample at the boundary —
  surprising); whether to support overlap / gap / resampling-on-merge
  variants; whether the API should be classmethods or module-level
  functions or instance methods. No timeline; revisit when the use
  case is concrete.

## Suspected bugs / contract holes (1.3.0)

- **Mixed int/float slicing silently flips conventions.** `s[0:5.]`
  treats the int `0` as time `0.0`, not sample `0`.
  `_slice_to_interval` switches to the time branch as soon as
  *either* endpoint is float, then uses `key.start` as a raw value
  (cast through `float()`). Either reject mixed types with a clear
  error, or make the conversion explicit (and document it). Pairs
  with the `at_time` / `at_sample` API decision below — if explicit
  modes ship in 1.3.0, mixed-type rejection becomes ergonomic.

## Robustness gaps (open questions)

- **Meta-vs-name precedence.** `__getitem__` checks `meta` first, so
  a meta key that happens to collide with a `signal_name` or
  `signal_coord` silently wins. Define the rule in the docstring,
  raise on overlap, or deprecate the meta-by-bracket lookup (the
  docstring already calls it "Not recommended"). Pairs naturally
  with the `_resolve_str_key` refactor below.
- **`signal_coords=["x"]` magic default.** 1D data automatically
  picks up a coord named `"x"` regardless of meaning, which surfaces
  in expressions like `data_1d["x"]` returning the whole signal.
  Consider `signal_coords=[None]` (or `[""]`) for the unlabelled
  case. Needs a deprecation pathway: warn in 1.3.0, swap default in
  1.4.0.
- **String-key namespace overlap.** What if `signal_names` and
  `signal_coords` share a label (e.g. both contain `"x"`)? Today
  coords win; mixed lists like `["x", "acc1"]` raise `KeyError` even
  though both are individually valid. Pairs with `_resolve_str_key`.

## Refactor opportunities (1.3.0)

- **Consolidate string-key dispatch (`_resolve_str_key`).** Meta
  lookup, signal-name lookup, and coord lookup are three separate
  code paths in `__getitem__` with implicit precedence. Pull into a
  private `_resolve_str_key(key) -> (kind, value)` with documented
  priority rules. Blocked on the meta-vs-name precedence and
  namespace-overlap decisions above; design the rules first, then
  refactor.

## From 2026-05-12 audit

Findings from a 2026-05-12 internal audit. Verdict: package
structurally robust; everything below is folded into the 1.3.0 cycle
unless explicitly flagged for 1.2.1.

### Bugs / numpy-2 vestiges

- ✅ **N1 [shipped in 1.2.1, 2026-05-12]** — `core.py:723` now uses
  `np.nan` (numpy 2.0 removed `np.NaN`). Regression test
  `test_butterfilt_preserves_nans_under_numpy2` pins both 1D and 2D
  inputs through `lowpass` and `highpass`. Downstream confirmation
  during the audit: `immersionToolbox.ot` velocity methods and
  `datanavigator.pointtracking` video-export paths both routinely
  pass NaN-bearing signals through these filters.

- **N2 [MED]** — `Time` setter / `__init__` round-vs-truncate
  inconsistency. `__init__` (`core.py:84`) uses `round(inp * sr)`
  to convert seconds → samples, but the `sr` setter
  (`core.py:104`), `sample` setter (`core.py:116`), and `time`
  setter (`core.py:127`) all use `int()` (truncation toward zero).
  Causes silent off-by-one at FP-edge values. Fix: unify on
  `round(...)`. Add a property-style round-trip-stability test
  across a sweep of `(t, sr1, sr2)` values.

### Robustness / edge cases

- **E1 [LOW-MED]** — Empty `Data` (`np.array([])`) passes
  `_validate()` but breaks `diff()`, `apply_running_win`, and
  `dur` (`core.py:886` → negative duration). Either reject at
  construction or document the constraint.
- **E2 [LOW]** — Single-sample `Data`: `diff()` indexes `self._sig[1]`
  → `IndexError` (`core.py:1495`). `Siglets` boundary semantics
  also fuzzy at the single-sample end. Either reject or handle.
- **E3 [LOW]** — All-NaN signal through `lowpass` / `highpass`
  short-circuits `interpnan` (`min_data_frac=0.2` guard at
  `core.py:2207`) but then hits **N1**. Combined fix; same
  regression test covers both.
- **N3 [LOW]** — `Interval.t_iter` and iterating an `Interval`
  produce off-by-one lengths: `_t(rate)` returns
  `int(dur*rate)+1` samples (`core.py:291-294`); `__next__`
  yields `int(dur*rate)+2` items (`core.py:261-273`). Quietly
  drops the last yielded tuple when zip'd with `t_iter`. Pick
  one convention and document.

### Module hygiene

- **M1 [LOW]** — Code-side deprecation of `DataList`, `Event`,
  `Events`. Spec hygiene happened 2026-05-12 (see audit). To do
  in 1.3.0: add `DeprecationWarning` on instantiation; remove
  from `pysampled/__init__.py` re-exports and the module
  docstring's Classes index. Migration target for the lone
  external caller (`pn-projects/projects/fencing/xrm01.py:356,373`,
  dormant): plain `list`. Removal can wait until 1.4.0 / 2.0.0.

### Refactor smells

- **S1 [LOW]** — `_butterfilt` rebinds the local `self`:
  `self = self.interpnan()` (`core.py:717`). Behaviorally correct
  (clone-routed) but mind-bending. Rename local: e.g.
  `working = self.interpnan()`.
- **S2 [LOW]** — `apply_to_each_signal` does an unconditional
  per-signal `s._sig.copy()` (`core.py:1665-1666`). Doubles memory
  for large signals when `func` is non-mutating (the common case).
  Decide: drop the copy and document the no-mutation contract, OR
  keep it and document the defensive guarantee. Current state
  pays the cost without claiming the benefit.
- **S4 [INFO]** — Module-level `interpnan` (`core.py:2175`) and
  `Data.interpnan` method (`core.py:829`) share a name; the method
  body relies on closure resolution to disambiguate. Consider
  renaming the module helper to `_interpnan_1d` (and dropping it
  from `__init__.py` re-exports if no external callers).

### Docstring drift

- **D1 [LOW]** — `Data.__call__` docstring (`core.py:494-505`)
  says `s(0)` returns the "first axis," but for 1D signals
  `_dynamic_indexing` returns the entire signal regardless of
  index. Clarify the 1D special case.
- **D2 [LOW]** — `Time` docstring doesn't surface the
  round-vs-truncate behaviour. Update alongside the **N2** fix.

### Test coverage gaps (low-priority)

These flagged silent regressions, not bugs. Address opportunistically
during 1.3.0 work that touches each area.

- `Data._butterfilt` NaN-replay path is unexercised — covered
  alongside **N1**.
- `Data.envelope2` (added 1.1.2) is completely untested.
- Filter / spectral methods (`bandpass`, `notch`, `lowpass`,
  `highpass`, `fft`, `psd`, `frac_power`, `medfilt`,
  `interpnan`, `smooth`, `moving_average`) have shape-only smoke
  tests; numerical assertions would catch silent regressions.
- `Data.diff`'s n-sample-preserved invariant (vs `np.diff`'s
  n-1 output) isn't pinned by assertion.
- `Data.find_crossings` `th_time=` path untested.
- Comparison dunders — only `<=` has a smoke test; `<`, `>`,
  `==`, `!=`, `>=` untested.
- `Data.__getitem__` interpolation path (list/tuple of floats)
  documented at `core.py:976-977` but untested.
- `Data.__call__('')` empty-string tuple path documented at
  `core.py:501-503` but untested.
- `Time` setter round-trip stability — see **N2**.
- `Interval.union` / `intersection` with no overlap (returns
  `()` empty tuple, not `Interval`) untested.
- `RunningWin` with explicit `step=` parameter — undocumented
  and untested.
- `Siglets` boundary semantics (the `>` vs `>=` at
  `core.py:2091`) untested.
- `uniform_resample` has zero direct tests despite being the
  delsys-facing helper.
- `onoff_samples` and module-level `interpnan` have no direct
  tests; only exercised through `Data`.
