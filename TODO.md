# TODO

Open work for the 1.2.x cycle. The 1.1.3 propagation-bugfix release
shipped on 2026-05-09 (see `CHANGELOG.md` and the per-bug commits on
`master`); the entries below are everything from the audit that did
*not* ship in 1.1.3, plus the standing roadmap items.

## Shipped in 1.1.3 (2026-05-09)

A focused audit identified seven concrete propagation bugs around
`signal_names` / `signal_coords` / `meta` / `_history`. All seven
shipped with failing-test-first commits (`e0327bc..63ca444`):

- B1 — `take_by_interval` now routes through `_clone`, preserving
  labels / meta / history on every time-based or sample-based slice.
- B2 — `_get_multiaxis_signals` and `_get_coord` build the column
  index list in user-requested order. The output keeps the documented
  names-outer / coords-inner column ordering, so labels and data
  agree even after reordering.
- B3 — `apply_running_win` propagates labels, meta, and history.
- B4 — `fft_as_sampled` / `psd_as_sampled` / `frac_power` propagate
  meta and history (labels were already flowing).
- B5 — `split_to_1d` emits a 2-tuple history entry
  `("split", {"col": …, "signal_name": …, "signal_coord": …})`.
- B6 — `_clone` and `copy` shallow-copy `meta`, `signal_names`,
  `signal_coords`, and `_history` so siblings no longer alias.
- B7 — `__init__` rejects an explicitly empty `signal_coords=[]`
  with a `ValueError`.

The load-bearing invariant `assert self.n_signals() ==
len(self.signal_names) * len(self.signal_coords)` (`core.py:427`)
remains the only structural defence. The 1.1.3 tests against
`data_2d` / `data_2d_transposed` verify *semantic* correctness
(column values match labels) for the two ordering bugs that the
assertion couldn't catch.

## Suspected bugs / contract holes (1.2.0)

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
  on shape change) or raise with a guiding error message.

- **`apply`'s `TypeError` retry catches too much** (the try/except
  block in `apply` that retries without `axis=` on `TypeError`). Any
  `TypeError` from `func` — not just "doesn't accept `axis`" —
  triggers the silent retry, masking real bugs. **Fix**: introspect
  the signature with `inspect.signature(func)` instead of
  try/except, or narrow the catch to a specific exception message.

- **`apply_to_each_signal` doesn't update labels when shape changes.**
  `_clone` is called with no kwargs so labels inherit. For
  shape-preserving ops this is correct; for shape-changing ops, the
  L427 assertion may or may not catch the mismatch depending on
  factor compatibility. **Fix**: align with `apply_along_signals`
  (auto-reset on shape change) or document the contract.

## Robustness gaps (open questions)

- **Meta-vs-name precedence.** `__getitem__` checks `meta` first, so
  a meta key that happens to collide with a `signal_name` or
  `signal_coord` silently wins. Either define a precedence in the
  docstring, raise on overlap, or deprecate the meta-by-bracket
  lookup (the docstring already calls it "Not recommended").

- **`transpose` and signal_names / signal_coords.** Currently both
  are *preserved*, which is semantically correct — they describe the
  logical signal axis, independent of which physical axis it lives
  on — but the contract is undocumented and counter-intuitive. Add a
  paragraph to the docstring; consider an explicit test.

- **`magnitude` collapses dimensionality but uses default labels.**
  After `magnitude()` on a `data_2d` with
  `signal_names=["acc1","acc2"]`, the result has
  `signal_names=["s0","s1"]` and `signal_coords=["x"]`. Should
  probably set `signal_coords=["mag"]` and keep `signal_names`.

- **Document which methods change the sampling rate.** `_clone` is
  reserved for rate-preserving methods; rate-changing methods build
  a fresh `Data` and pass the new `sr` explicitly. The current
  rate-changing list (worth surfacing in the `Data` docstring or in
  `docs/`):

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
  `_validate()` from both `__init__` and `__setstate__`. (1.1.3
  added a round-trip test for the *old-shape* case but not the
  malformed-pickle case.)

- **`signal_coords=["x"]` magic default.** 1D data automatically
  picks up a coord named `"x"` regardless of meaning, which surfaces
  in expressions like `data_1d["x"]` returning the whole signal.
  Consider `signal_coords=[None]` (or `[""]`) for the unlabelled
  case.

- **String-key namespace overlap.** What if `signal_names` and
  `signal_coords` share a label (e.g. both contain `"x"`)? Today
  coords win; mixed lists like `["x", "acc1"]` raise `KeyError` even
  though both are individually valid. Define the rule.

## Coverage gaps

Most coverage items from the audit shipped alongside the 1.1.3
fixes. Still untested:

- Mixed int/float slicing semantics (paired with the contract
  decision above).

## Refactor opportunities

- **Three `apply` variants with three different label-propagation
  rules.** `apply` preserves blindly (and asserts on mismatch);
  `apply_along_signals` auto-resets on shape change;
  `apply_to_each_signal` preserves blindly (no auto-reset). Either
  pick one rule or factor out a helper that all three share.

- **Methods that bypass `_clone` for rate changes.** After 1.1.3,
  `apply_running_win`, `fft_as_sampled`, `psd_as_sampled`,
  `frac_power`, and `magnitude` each still construct `Data`
  directly with manual label / meta / history propagation. Consider
  a `_clone_with_rate(self, proc_sig, new_sr, *, his_append,
  **kwargs)` sibling that handles propagation in one place.
  (`take_by_interval` no longer bypasses `_clone`.)

- **Consolidate string-key dispatch.** Meta lookup, signal-name
  lookup, and coord lookup are three separate code paths in
  `__getitem__` with implicit precedence. Pull into a private
  `_resolve_str_key(key) -> (kind, value)` with documented priority
  rules. Pairs naturally with the meta-vs-name precedence question.

- **Move L427's invariant into a private `_validate()` method.**
  Run it from `__init__`, from `__setstate__`, and (optionally) at
  the end of `_clone`. Centralises the rule and removes the
  `__setstate__` blind spot.

## Post-1.1.x roadmap

- **Stricter alternative API for indexing.** The int-vs-float
  convention is intentional but surprising on first contact. Adding
  `sig.at_time(10, 20)` / `sig.at_sample(10, 20)` (and possibly
  `sig.between_times(...)`, `sig.between_samples(...)`) would let
  users pick clarity over conciseness when readability matters
  more. This is the spec's Open Question #1; pull it into the main
  list above once a decision is made.

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
