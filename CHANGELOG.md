# Change Log
All notable changes to this project will be documented in this file.

## [1.2.0]

In progress. The opening commit restores CI compatibility against newer numpy and scipy releases.

### Fixed
- `pysampled.Data.frac_power` now resolves the trapezoidal-rule helper at import time via a small shim (`np.trapezoid` on numpy 2.x, falling back to `np.trapz` on numpy 1.x). 1.1.3's CI failed on Ubuntu / macOS / Python 3.11 because numpy 2.x removed the legacy `np.trapz` symbol; the shim keeps `frac_power` working on both lineages without pinning numpy.
- `pysampled.Data.sparc` now passes `freq_sel` as a keyword argument to `scipy.integrate.simpson`. scipy 1.14 made that argument keyword-only, so the old positional call raised `TypeError` on newer scipy installs.
- `pysampled.Data.__setstate__` now re-runs the `n_signals == len(signal_names) * len(signal_coords)` invariant check after restoring an old pickle. Previously a hand-mutated pickle whose labels no longer matched the underlying data shape would unpickle silently; now it raises immediately.

### Changed
- The constructor invariant block in `pysampled.Data.__init__` was extracted to a private `_validate()` method, called from both `__init__` and `__setstate__`. No public API change; the constructor still raises the same error on a label/data mismatch.
- The five rate-changing methods (`resample`, `apply_running_win`, `fft_as_sampled`, `psd_as_sampled`, `frac_power`) now route through a new private `_clone_with_rate(proc_sig, new_sr, *, his_append, t0=None, **kwargs)` helper. Functionally equivalent to the old per-method `Data(...)` calls; centralises the meta / signal_names / signal_coords / `_history` shallow-copy rule. Incidentally fixes a latent aliasing bug in `resample` (which previously passed `meta` and label lists by reference).

## [1.1.3]

Maintenance release driven by a 2026-05-09 audit (`TODO.md`) that found seven propagation bugs around `signal_names` / `signal_coords` / `meta` / `_history`. Two of them (B1 and B2) were silent label-vs-data mismatches that satisfied the existing shape invariant but produced mislabelled data. New tests pin each fix using 2D fixtures.

### Fixed
- `pysampled.Data.split_to_1d` now emits a well-formed 2-tuple history entry. The previous 3-tuple `("split", col, (signal_name, signal_coord))` broke downstream history consumers that expect every entry to be `(name, payload)`. The new payload is a dict with `col`, `signal_name`, `signal_coord` keys.
- `pysampled.Data.__init__` now rejects an explicitly empty `signal_coords=[]` with a clear `ValueError` instead of silently coercing it to the default and later zero-dividing in `_get_default_signal_names`.
- `pysampled.Data._clone` and `pysampled.Data.copy` no longer alias the parent's `meta`, `signal_names`, `signal_coords`, or `_history`. Mutating any of these on a clone (or copy) used to leak back into the parent. They are now shallow-copied at clone time.
- `pysampled.Data._get_multiaxis_signals` and `pysampled.Data._get_coord` now respect the user-requested order of names/coords. Previously they built a boolean mask in parent order while storing labels in user order, so `data_2d[["acc2","acc1"]]` silently returned columns in `[acc1, acc2]` order with `signal_names=["acc2","acc1"]` — labels disagreed with the data. Output column order is now `itertools.product(signal_names, signal_coords)`, which preserves the names-outer / coords-inner invariant.
- `pysampled.Data.take_by_interval` (and any indexing route that goes through it, e.g. `data_2d[1.0:2.0]` or `data_2d[10:20]`) now preserves `signal_names`, `signal_coords`, `meta`, and `_history` instead of resetting them to defaults. The previous positional constructor call stopped at `meta` and silently rebuilt labels.
- The four rate-changing methods that build a fresh `Data` (`apply_running_win`, `fft_as_sampled`, `psd_as_sampled`, `frac_power`) now propagate `meta` and `_history`. `apply_running_win` additionally propagates `signal_names` / `signal_coords` (the other three already did). They cannot route through `_clone` because the sampling rate changes, but the labels and metadata still flow through.

## [1.1.2]
Added `pysampled.Data.envelope2` while packaging the `delsys` module. This was originally written by Roger Pallares-Lopez, and kept in an inherited class to not create unintended changes in this repository. But, the time for that has passed, and Praneeth is now migrating this function here for world code peace.

## [1.1.1]

### Changed
Bugfixes in the `pysampled.Data.apply` method for issues related to the indexing functionality introduced in 1.1.0. Also corrected `ValueError` in `pysampled.Data.__getitem__` to `KeyError`.

## [1.1.0]

### Added
Added "indexing" functionality to `Data` class. For example, if an instance of data represented 6 signals with 1000 samples each coming from two 3-axis accelerometers acc1, and acc2 each with coordinates x, y, and z, then we can simply index subsections of this signal using `s["acc1"]` or `s["x"]` or `s["acc2"]["x"]`. 


## [1.0.2] - 2025-03-12
 
First major release.
