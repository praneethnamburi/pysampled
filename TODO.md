# TODO

Open work for the 1.3.x cycle. The 1.2.0 cleanup release shipped on
2026-05-09 (see `CHANGELOG.md` and the per-commit log on `master`,
`11f12c0..d342051`). Entries below are everything that did *not* ship
in 1.1.3 / 1.2.0, plus the standing roadmap items.

## Shipped in 1.2.0 (2026-05-09)

Internal cleanup release; nine commits on top of 1.1.3.

- **CI compat (`11f12c0`).** `frac_power` now resolves the
  trapezoidal-rule helper at import time via a getattr shim
  (`np.trapezoid` on numpy 2.x, falling back to `np.trapz` on numpy
  1.x). `sparc` passes `freq_sel=` to `scipy.integrate.simpson` as a
  keyword (scipy 1.14 made it keyword-only). Restored CI green.
- **`_validate()` extraction (`85a6498`).** Lifted the
  `n_signals == len(signal_names) * len(signal_coords)` invariant out
  of `__init__` and into a private `_validate()` called from both
  `__init__` and `__setstate__`. Closes the 1.1.3 audit blind spot
  where a hand-mutated pickle could restore silently.
- **`_clone_with_rate` helper (`a26bc82`).** Rate-changing methods
  (`resample`, `apply_running_win`, `fft_as_sampled`,
  `psd_as_sampled`, `frac_power`) now route through one helper that
  centralises the meta/labels/history shallow-copy ritual. Fixed an
  incidental B6-style aliasing bug in `resample`.
- **Apply-variant unification (`71cae5d`).** Closes S2, S3, and the
  `apply_to_each_signal` label-update gap together. `apply`,
  `apply_along_signals`, and `apply_to_each_signal` share one
  label-propagation rule (auto-reset iff `n_signals` changes;
  explicit `signal_names=` / `signal_coords=` always win) and one
  axis-introspection helper (`inspect.signature(func)` with a
  narrowed `TypeError` fallback). Behavior change: `apply` with a
  shape-changing func no longer raises `AssertionError`.
- **`split_by_signal_name` / `split_by_signal_coord` (`10b2485`).**
  Coarser-grained companions to `split_to_1d`. Thin wrappers over
  `__getitem__`. Matching `merge_along_*` classmethods were
  prototyped but pulled before release — see "Open design work"
  below.
- **`magnitude` semantic fix (`6176ced`).** Now per-`signal_name`:
  for a `Data` with `signal_names=["acc1","acc2"]` and
  `signal_coords=["x","y","z"]`, output is `(n_samples, 2)` with
  `signal_coords=["mag"]`. Previously it collapsed all non-time
  columns globally — silently wrong on multi-signal inputs.
  Migration: `sig.apply_along_signals(np.linalg.norm)` recovers the
  old global form. `logdj`'s internal call was updated.
- **Docs + integration tests (`56399ec`).** The `Data` class
  docstring now spells out the propagation invariants, the
  rate-changing method list, the transpose label contract, the apply
  n_signals rule, and the split/merge family. Two integration tests
  exercise the rate-change × shape-change pipeline and the
  split-then-merge round trip.

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

## Post-1.2.0 roadmap

- **Stricter alternative API for indexing.** The int-vs-float
  convention is intentional but surprising on first contact. Adding
  `sig.at_time(10, 20)` / `sig.at_sample(10, 20)` (and possibly
  `sig.between_times(...)`, `sig.between_samples(...)`) would let
  users pick clarity over conciseness when readability matters
  more. This is the spec's Open Question #1 and pairs with the
  mixed int/float decision above.
- **Merge dunders.** Once the `merge_along_*` classmethods land
  (see "Open design work"), consider dunder shorthand: `s1 + s2`
  for time-axis merge, `s1 | s2` (or similar) for signal-axis
  merge. Design risk: `Data` already defines `__le__` / `__ge__` /
  `__eq__` / etc. for thresholding, so adding `__add__` opens a
  real ambiguity question (concat vs element-wise). Don't tackle
  the dunders before the underlying merge methods are stable.
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
