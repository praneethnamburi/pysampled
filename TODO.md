# TODO

Open design questions and deferred work for the 1.3.x cycle. Release
narrative lives in `CHANGELOG.md`; portfolio-level roadmap lives in
`C:/dev/pn-specs/ROADMAP.md`.

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
