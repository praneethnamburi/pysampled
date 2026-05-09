# TODO

Items deferred during the 1.1.x maintenance window. Most of the entries
below are propagation bugs around `signal_names` / `signal_coords` /
`meta` — surfaced by a focused audit on 2026-05-09. The single
propagation hub is `Data._clone` (`pysampled/core.py` ~L491); the
bugs cluster in methods that bypass it or that override its kwargs
inconsistently.

## Audit snapshot (2026-05-09)

Audit scope was the contract under which every processing method
returns a `Data` whose `signal_names` × `signal_coords` ordering
matches the column ordering of the underlying array. The load-bearing
invariant is `core.py:427`:

    assert self.n_signals() == len(self.signal_names) * len(self.signal_coords)

That assertion is the *only* line of defence today. Several methods
satisfy it numerically while still producing **silently mislabelled**
data — bugs B1 and B2 below are both of that flavour: array shape and
label list length agree, but the order does not.

Treat as informational; no code changes were made during the audit.
The "Open questions" section in
`C:/dev/pn-specs/specs/pysampled.md` predates this file — once 1.1.3
ships the bugfixes below, the spec's open-questions list should be
updated to point here for everything except the int-vs-float and
xarray-boundary items (which remain genuine open questions).

## Bugs (1.1.3)

Each bug below has a short repro recorded in the audit conversation
(2026-05-09) and is reproducible against `master`.

- **`take_by_interval` drops `signal_names` / `signal_coords`**
  (`core.py:862-872`). The constructor call is positional and stops at
  `meta`:

      return self.__class__(proc_sig, self.sr, self.axis, his, self.t[rng_start], meta)

  Every time-based or sample-based slice through `__getitem__` routes
  through here. So `data_2d[1.0:2.0]` (or `data_2d[10:20]`) silently
  resets labels to defaults: `signal_names=["s0", "s1", ...]`,
  `signal_coords=["x"]`. Existing tests miss this because
  `test_take_by_interval` runs on 1D `white_noise`. **Fix**: route
  through `_clone`, or add `signal_names=` / `signal_coords=` kwargs
  to the explicit constructor call.

- **`_get_multiaxis_signals` / `_get_coord` ignore user-requested
  order** (`core.py:966-1008`). The selection mask is built from
  `itertools.product(self.signal_names, self.signal_coords)` (i.e. the
  *parent's* order), but `signal_names=multiaxis_signal_names` /
  `signal_coords=coord_names` are stored in the *user's* order. So
  `data_2d[["acc2", "acc1"]]` returns array columns in `[acc1, acc2]`
  order while labelling them `["acc2", "acc1"]`. Same for coord
  reordering: `data_2d[["z", "x"]]`. Silent data/label mismatch.
  **Fix**: build the index list in the user-requested order, e.g.
  iterate `multiaxis_signal_names` outer, `signal_coords` inner, and
  collect the matching column indices.

- **`apply_running_win` drops `meta`, `signal_names`, `signal_coords`,
  and `_history`** (`core.py:1061`). Sampling rate changes here, so
  using a raw `Data(...)` constructor (rather than `_clone`) is
  intentional — but the *labels and history* should still propagate.
  **Fix**: pass `meta=self.meta`, `signal_names=self.signal_names`,
  `signal_coords=self.signal_coords`, and the `_history + [...]` list
  through to the new `Data`.

- **`fft_as_sampled` / `psd_as_sampled` / `frac_power` drop `meta`
  and `_history`** (`core.py:1238`, `1287`, `1340`). These three
  rate-changing methods do propagate `signal_names` / `signal_coords`
  but forget `meta` and `history`. **Fix**: same as above — propagate
  labels *and* metadata even when sampling rate changes.

- **`split_to_1d` history record is a malformed 3-tuple**
  (`core.py:1149`):

      ("split", col, (signal_name, signal_coord))

  Every other history entry is a 2-tuple `(name, payload)`; downstream
  consumers reading `h[1]` to get the payload now read `col` (an int)
  instead of the label tag. **Fix**: emit
  `("split", {"col": col, "signal_name": ..., "signal_coord": ...})`
  or `("split", (col, signal_name, signal_coord))`.

- **`_clone` aliases mutable state**. `meta`, `signal_names`,
  `signal_coords` are passed by reference to the new instance — two
  clones share the same Python objects, so mutating one propagates.
  Same for `copy()` re: `_history`. **Fix**: shallow-copy in
  `_clone` and `copy` (or document that these collections are
  treated as immutable).

- **`_get_default_signal_names` divides by zero** when
  `signal_coords=[]` is explicitly passed (`core.py:431`). The
  validation block at L420 only guards the `>1` branch. **Fix**: add
  a `len(signal_coords) >= 1` precondition or reject empty
  `signal_coords` at the top of `__init__`.

## Suspected bugs / contract holes (1.1.3 or 1.2.0)

- **Mixed int/float slicing silently flips conventions.** `s[0:5.]`
  treats the int `0` as time `0.0`, not sample `0`. `_slice_to_interval`
  switches to the time branch as soon as *either* endpoint is float,
  then uses `key.start` as a raw value (cast through `float()`).
  Either reject mixed types with a clear error, or make the
  conversion explicit (and document it). Repro confirmed
  2026-05-09.

- **`apply` with shape-changing func keeps stale labels.** Today the
  `n_signals == len(names) * len(coords)` assertion fires; `test_apply`
  even uses `pytest.raises(AssertionError)` to pin this. The failure
  is undiscoverable from the API and the workaround (pass
  `signal_names=` / `signal_coords=` explicitly) is undocumented.
  Either reset labels automatically (like `apply_along_signals` does
  at `core.py:1433`) or raise with a guiding error message.

- **`apply`'s `TypeError` retry catches too much** (`core.py:1405-1410`).
  Any `TypeError` from `func` — not just "doesn't accept `axis`" —
  triggers the silent retry, masking real bugs. **Fix**: introspect
  the signature with `inspect.signature(func)` instead of try/except,
  or narrow the catch to a specific exception message.

- **`apply_to_each_signal` doesn't update labels when shape changes**
  (`core.py:1450-1469`). `_clone` is called with no kwargs so labels
  inherit. For shape-preserving ops this is correct; for shape-changing
  ops, the L427 assertion may or may not catch the mismatch depending
  on factor compatibility. **Fix**: align with `apply_along_signals`
  (auto-reset on shape change) or document the contract.

## Robustness gaps (open questions)

- **Meta-vs-name precedence.** `__getitem__` checks `meta` first
  (`core.py:938`), so a meta key that happens to collide with a
  `signal_name` or `signal_coord` silently wins. Either define a
  precedence in the docstring, raise on overlap, or deprecate the
  meta-by-bracket lookup (the docstring already calls it "Not
  recommended").

- **`transpose` and signal_names / signal_coords.** Currently both
  are *preserved* (`core.py:1159-1163`), which is semantically correct
  — they describe the logical signal axis, independent of which
  physical axis it lives on — but the contract is undocumented and
  counter-intuitive. Add a paragraph to the docstring; consider an
  explicit test.

- **`magnitude` collapses dimensionality but uses default labels**
  (`core.py:1391`). After `magnitude()` on a `data_2d` with
  `signal_names=["acc1","acc2"]`, the result has `signal_names=["s0",
  "s1"]` and `signal_coords=["x"]`. Should probably set
  `signal_coords=["mag"]` and keep `signal_names`.

- **Document which methods change the sampling rate.** Per the
  audit conversation, `_clone` is reserved for rate-preserving
  methods; rate-changing methods must build a fresh `Data` and pass
  the new `sr` explicitly. The current rate-changing list (worth
  surfacing in the `Data` docstring or in `docs/`):

  - `resample` — explicit new rate.
  - `apply_running_win` — `sr / round(win_inc * sr)`.
  - `fft_as_sampled`, `psd_as_sampled` — `1 / df`, samples per Hz.
  - `frac_power` — `1 / win_inc`.
  - `instantaneous_frequency` — drops one sample (size, not rate,
    technically; uses `_clone`). Worth flagging anyway.
  - `diff` — preserves length & rate (uses `_clone`).

- **`__setstate__` skips the L427 invariant.** Old pickles default
  missing fields (`meta={}`, `signal_coords=["x"]`, default names)
  but never re-validate. A pickle saved before 1.1.0 with mismatched
  data will load without complaint. **Fix**: call a private
  `_validate()` from both `__init__` and `__setstate__`.

- **`signal_coords=["x"]` magic default.** 1D data automatically
  picks up a coord named `"x"` regardless of meaning, which surfaces
  in expressions like `data_1d["x"]` returning the whole signal.
  Consider `signal_coords=[None]` (or `[""]`) for the unlabelled case.

- **String-key namespace overlap.** What if `signal_names` and
  `signal_coords` share a label (e.g. both contain `"x"`)? Today
  coords win (`core.py:945`); mixed lists like `["x", "acc1"]` raise
  `KeyError` even though both are individually valid. Define the
  rule.

## Coverage gaps

The audit found these untested surfaces. Each is a candidate test;
several would have caught a bug above on the first run.

- 2D `take_by_interval` / time-slicing label preservation (B1).
- Out-of-order subset selection: `data_2d[["acc2","acc1"]]`,
  `data_2d[["z","x"]]` (B2).
- Mixed int/float slicing semantics.
- `apply_running_win` propagation (labels, meta, history).
- `fft_as_sampled` / `psd_as_sampled` / `frac_power` propagation.
- `meta` dict survives a multi-step pipeline.
- `__setstate__` round-trip with old-shape pickles (no `meta`, no
  `signal_coords`).
- `signal_coords=[]` edge case (B7).
- Composition: slice-then-`apply`, `transpose`-then-string-index,
  `s["acc1"]["x"].bandpass(...)`.
- `split_to_1d` history shape (B5).

## Refactor opportunities

- **Three `apply` variants with three different label-propagation
  rules.** `apply` preserves blindly (and asserts on mismatch);
  `apply_along_signals` auto-resets on shape change;
  `apply_to_each_signal` preserves blindly (no auto-reset). Either
  pick one rule or factor out a helper that all three share.

- **Methods that bypass `_clone` for rate changes.**
  `take_by_interval` (rate unchanged — should *not* bypass),
  `apply_running_win`, `fft_as_sampled`, `psd_as_sampled`,
  `frac_power`, and `magnitude` each construct `Data` directly. Of
  these, only the rate-changing ones legitimately need their own
  constructor call. Consider a `_clone_with_rate(self, proc_sig,
  new_sr, *, his_append, **kwargs)` sibling that handles label /
  meta / history propagation in one place.

- **Consolidate string-key dispatch.** Meta lookup, signal-name
  lookup, and coord lookup are three separate code paths in
  `__getitem__` (`core.py:938-952`) with implicit precedence. Pull
  into a private `_resolve_str_key(key) -> (kind, value)` with
  documented priority rules.

- **Move L427's invariant into a private `_validate()` method.**
  Run it from `__init__`, from `__setstate__`, and (optionally) at
  the end of `_clone`. Centralises the rule and removes the
  `__setstate__` blind spot above.

## Post-1.1.x roadmap

- **Stricter alternative API for indexing.** The int-vs-float
  convention is intentional but surprising on first contact. Adding
  `sig.at_time(10, 20)` / `sig.at_sample(10, 20)` (and possibly
  `sig.between_times(...)`, `sig.between_samples(...)`) would let
  users pick clarity over conciseness when readability matters
  more. This is the spec's Open Question #1; pull it into TODO.md
  once a decision is made.

- **xarray boundary.** Today `signal_names` / `signal_coords` cover
  the portfolio's needs. Reconsider absorbing a few more
  xarray-shaped features only if two downstream repos independently
  re-implement the same gap. (Spec's Open Question #2.)

- **Promote-when-general pattern.** The 1.1.2 `envelope2` migration
  from delsys is the model — when delsys / datanest / project
  scripts grow a helper that's clearly not equipment- or
  project-specific, lift it into core. No new feature push planned
  beyond opportunistic merges of this kind.

- **Public posture.** Docs polish, examples gallery, conda-forge
  submission, broader teaching framing — defer until external
  interest materialises or a contribution lands that makes the
  maintenance overhead worthwhile.
