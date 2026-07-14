import pickle

import pytest
import numpy as np
from pysampled import Data, Siglets, generate_signal


@pytest.fixture
def white_noise():
    return generate_signal("white_noise", 100, 10)


@pytest.fixture
def sine_wave():
    return generate_signal("sine_wave", 100, 10)


@pytest.fixture
def three_sine_waves():
    return generate_signal("three_sine_waves", 100, 10)


@pytest.fixture
def ekg():
    return generate_signal("ekg", 100, 10)


@pytest.fixture
def accelerometer():
    return generate_signal("accelerometer", 100, 10)


@pytest.fixture(scope="module")
def data_2d():
    """Fixture for 2D signal data with shape (1000, 6)."""
    sig = np.random.random((1000, 6))
    return Data(
        sig, sr=100, signal_names=["acc1", "acc2"], signal_coords=["x", "y", "z"]
    )


@pytest.fixture(scope="module")
def data_2d_transposed():
    """Fixture for 2D signal data with shape (6, 1000)."""
    sig = np.random.random((6, 1000))
    return Data(
        sig, sr=100, signal_names=["acc1", "acc2"], signal_coords=["x", "y", "z"]
    )


@pytest.fixture(scope="module")
def data_1d():
    """Fixture for 1D signal data with shape (1000,)."""
    sig = np.random.random(1000)
    return Data(sig, sr=100)


def test_init(white_noise, data_2d, data_2d_transposed, data_1d):
    assert white_noise.sr == 100
    assert white_noise._sig.shape == (1000,)
    d = Data(np.random.random(1000), sr=100)
    assert d.signal_names == ["s0"]
    assert d.signal_coords == ["x"]

    assert data_2d.n_signals() == 6
    assert data_2d_transposed.n_signals() == 6
    assert data_1d.n_signals() == 1

    assert data_2d.signal_names == ["acc1", "acc2"]
    assert data_2d.signal_coords == ["x", "y", "z"]


def test_empty_signal_coords_rejected():
    """Passing signal_coords=[] used to zero-divide in
    _get_default_signal_names. Reject at the constructor instead."""
    with pytest.raises(ValueError):
        Data(np.zeros((100, 2)), sr=10, signal_coords=[])


def test_call(sine_wave):
    assert sine_wave().shape == (1000,)
    assert np.allclose(
        sine_wave()[:10],
        np.sin(2 * np.pi * 1 * np.linspace(0, 0.1, 10, endpoint=False)),
    )


def test_clone(three_sine_waves):
    cloned = three_sine_waves._clone(three_sine_waves._sig * 2)
    assert np.allclose(cloned._sig, three_sine_waves._sig * 2)


def test_clone_does_not_alias_meta(data_2d):
    """Mutating meta on a clone must not bleed into the parent."""
    parent = Data(
        np.random.random((100, 6)),
        sr=100,
        signal_names=["acc1", "acc2"],
        signal_coords=["x", "y", "z"],
        meta={"k": "v"},
    )
    clone = parent.scale(2.0)
    clone.meta["new"] = "added"
    assert "new" not in parent.meta


def test_clone_does_not_alias_signal_names(data_2d):
    parent = Data(
        np.random.random((100, 6)),
        sr=100,
        signal_names=["acc1", "acc2"],
        signal_coords=["x", "y", "z"],
    )
    clone = parent.scale(2.0)
    clone.signal_names.append("acc3")
    assert parent.signal_names == ["acc1", "acc2"]


def test_clone_does_not_alias_signal_coords(data_2d):
    parent = Data(
        np.random.random((100, 6)),
        sr=100,
        signal_names=["acc1", "acc2"],
        signal_coords=["x", "y", "z"],
    )
    clone = parent.scale(2.0)
    clone.signal_coords.append("w")
    assert parent.signal_coords == ["x", "y", "z"]


def test_copy_does_not_alias_history():
    parent = Data(np.zeros(100), sr=10)
    dup = parent.copy()
    dup._history.append(("mutated", None))
    assert ("mutated", None) not in parent._history


def test_clone_does_not_alias_history_when_no_append():
    """_clone called without his_append used to assign self._history by
    reference; mutating one then bled into the other."""
    parent = Data(np.zeros(100), sr=10)
    clone = parent._clone(parent._sig)  # no his_append
    clone._history.append(("mutated", None))
    assert ("mutated", None) not in parent._history


def test_clone_with_rate_does_not_alias():
    """The rate-changing sibling of _clone must apply the same shallow-copy
    rules as _clone (B6) so that meta / signal_names / signal_coords /
    _history on a rate-changed clone never bleed back into the parent."""
    parent = Data(
        np.random.random((100, 6)),
        sr=100,
        signal_names=["acc1", "acc2"],
        signal_coords=["x", "y", "z"],
        meta={"k": "v"},
    )
    new_sig = np.random.random((50, 6))
    clone = parent._clone_with_rate(new_sig, new_sr=50, his_append=("test", None))

    clone.meta["new"] = "added"
    assert "new" not in parent.meta
    clone.signal_names.append("acc3")
    assert parent.signal_names == ["acc1", "acc2"]
    clone.signal_coords.append("w")
    assert parent.signal_coords == ["x", "y", "z"]
    clone._history.append(("mutated", None))
    assert ("mutated", None) not in parent._history


def test_resample_does_not_alias_meta():
    """Pre-1.2.0 `resample` passed `meta=meta` and `signal_names=self.signal_names`
    directly into the constructor, aliasing the parent's mutable state. After
    routing through _clone_with_rate the clone gets fresh shallow copies."""
    parent = Data(
        np.random.random((1000, 6)),
        sr=100,
        signal_names=["acc1", "acc2"],
        signal_coords=["x", "y", "z"],
        meta={"k": "v"},
    )
    clone = parent.resample(50)

    clone.meta["new"] = "added"
    assert "new" not in parent.meta
    clone.signal_names.append("acc3")
    assert parent.signal_names == ["acc1", "acc2"]
    clone.signal_coords.append("w")
    assert parent.signal_coords == ["x", "y", "z"]


def test_resample_propagates_labels_meta_history():
    parent = Data(
        np.random.random((1000, 6)),
        sr=100,
        signal_names=["acc1", "acc2"],
        signal_coords=["x", "y", "z"],
        meta={"k": "v"},
    )
    clone = parent.resample(50)
    assert clone.signal_names == ["acc1", "acc2"]
    assert clone.signal_coords == ["x", "y", "z"]
    assert clone.meta.get("k") == "v"
    assert any(h[0] == "resample" for h in clone._history)


def test_analytic(white_noise, accelerometer):
    analytic_signal = white_noise.analytic()
    assert np.allclose(np.real(analytic_signal._sig), white_noise._sig)
    analytic_signal = accelerometer.analytic()
    assert np.allclose(np.real(analytic_signal._sig), accelerometer._sig)


def test_envelope(three_sine_waves):
    # envelope only makes sense
    envelope_signal = three_sine_waves.envelope(lowpass=2)
    assert envelope_signal._sig.shape == three_sine_waves._sig.shape


def test_phase(white_noise):
    phase_signal = white_noise.phase()
    assert phase_signal._sig.shape == white_noise._sig.shape


def test_instantaneous_frequency(white_noise):
    inst_freq = white_noise.instantaneous_frequency()
    assert inst_freq._sig.shape == (999,)


def test_bandpass(three_sine_waves):
    bandpassed = three_sine_waves.bandpass(0.5, 2.0)
    assert bandpassed._sig.shape == three_sine_waves._sig.shape


def test_notch(three_sine_waves):
    notched = three_sine_waves.notch(1.0)
    assert notched._sig.shape == three_sine_waves._sig.shape


def test_lowpass(three_sine_waves):
    lowpassed = three_sine_waves.lowpass(2.0)
    assert lowpassed._sig.shape == three_sine_waves._sig.shape


def test_highpass(three_sine_waves):
    highpassed = three_sine_waves.highpass(1.0)
    assert highpassed._sig.shape == three_sine_waves._sig.shape


def test_butterfilt_preserves_nans_under_numpy2():
    """`_butterfilt` interpnan's the input, filters, then re-applies the
    NaN mask. The re-apply line used `np.NaN`, which numpy 2.x removed —
    so any NaN-bearing signal through `Data.lowpass` / `Data.highpass`
    crashed under numpy 2.x. Downstream callers (`immersionToolbox.ot`
    velocity paths, `datanavigator.pointtracking` video export) routinely
    pass NaN-bearing signals through these filters. Pins the 1.2.1 fix
    so the regression cannot return.
    """
    sig_1d = np.sin(2 * np.pi * 1 * np.linspace(0, 10, 1000, endpoint=False))
    nan_mask_1d = np.zeros(1000, dtype=bool)
    nan_mask_1d[100:120] = True
    nan_mask_1d[500:505] = True
    sig_1d_with_nan = sig_1d.copy()
    sig_1d_with_nan[nan_mask_1d] = np.nan

    lp = Data(sig_1d_with_nan, sr=100).lowpass(5.0)
    assert lp._sig.shape == (1000,)
    assert np.array_equal(np.isnan(lp._sig), nan_mask_1d)

    hp = Data(sig_1d_with_nan, sr=100).highpass(2.0)
    assert hp._sig.shape == (1000,)
    assert np.array_equal(np.isnan(hp._sig), nan_mask_1d)

    sig_2d = np.tile(sig_1d[:, None], (1, 3))
    nan_mask_2d = np.zeros((1000, 3), dtype=bool)
    nan_mask_2d[100:120, :] = True
    nan_mask_2d[500:505, 0] = True
    sig_2d_with_nan = sig_2d.copy()
    sig_2d_with_nan[nan_mask_2d] = np.nan

    lp2 = Data(sig_2d_with_nan, sr=100, signal_names=["a", "b", "c"]).lowpass(5.0)
    assert lp2._sig.shape == (1000, 3)
    assert np.array_equal(np.isnan(lp2._sig), nan_mask_2d)


def test_smooth(white_noise):
    smoothed = white_noise.smooth(window_len=10)
    assert smoothed.shape == white_noise._sig.shape


def test_get_trend_airPLS(ekg):
    trend = ekg.get_trend_airPLS()
    assert trend._sig.shape == ekg._sig.shape


def test_detrend_airPLS(ekg):
    detrended = ekg.detrend_airPLS()
    assert detrended._sig.shape == ekg._sig.shape


def test_medfilt(three_sine_waves):
    medfiltered = three_sine_waves.medfilt(order=11)
    assert medfiltered._sig.shape == three_sine_waves._sig.shape


def test_interpnan(three_sine_waves):
    interpolated = three_sine_waves.interpnan()
    assert interpolated._sig.shape == three_sine_waves._sig.shape


def test_shift_baseline(white_noise):
    shifted = white_noise.shift_baseline()
    assert shifted._sig.shape == white_noise._sig.shape


def test_shift_left(white_noise):
    shifted = white_noise.shift_left(1.0)
    assert shifted._t0 == white_noise._t0 - 1.0


def test_scale(white_noise):
    scaled = white_noise.scale(2.0)
    assert np.allclose(scaled._sig, white_noise._sig / 2.0)


def test_len(white_noise):
    assert len(white_noise) == 1000


def test_t(white_noise):
    assert white_noise.t.shape == (1000,)


def test_dur(white_noise):
    assert white_noise.dur == 9.99


def test_take_by_interval(white_noise):
    interval = white_noise.interval()
    taken = white_noise.take_by_interval(interval)
    assert taken._sig.shape == white_noise._sig.shape


def test_getitem(white_noise):
    assert white_noise[0].shape == ()
    assert white_noise[0.0:1.0]._sig.shape == (101,)
    assert white_noise[:1.5]._sig.shape == (151,)


def test_take_by_interval_preserves_labels(data_2d):
    """take_by_interval used to drop signal_names/signal_coords back to
    defaults because it called the raw constructor with positional args
    that stopped at meta."""
    sub = data_2d.take_by_interval(data_2d.interval())
    assert sub.signal_names == ["acc1", "acc2"]
    assert sub.signal_coords == ["x", "y", "z"]


def test_time_slice_preserves_labels(data_2d):
    sub = data_2d[1.0:2.0]
    assert sub.signal_names == ["acc1", "acc2"]
    assert sub.signal_coords == ["x", "y", "z"]


def test_sample_slice_preserves_labels(data_2d):
    sub = data_2d[10:20]
    assert sub.signal_names == ["acc1", "acc2"]
    assert sub.signal_coords == ["x", "y", "z"]


def test_meta_survives_time_slice():
    """meta dict must survive a time slice."""
    parent = Data(
        np.random.random((1000, 6)),
        sr=100,
        signal_names=["acc1", "acc2"],
        signal_coords=["x", "y", "z"],
        meta={"k": "v"},
    )
    sub = parent[1.0:2.0]
    assert sub.meta.get("k") == "v"


def test_string_index_then_time_slice(data_2d):
    """Composition: subset by name, then slice in time. Labels must
    propagate through both steps."""
    sub = data_2d["acc1"][1.0:2.0]
    assert sub.signal_names == ["acc1"]
    assert sub.signal_coords == ["x", "y", "z"]


def test_take_by_interval_preserves_labels_transposed(data_2d_transposed):
    sub = data_2d_transposed.take_by_interval(data_2d_transposed.interval())
    assert sub.signal_names == ["acc1", "acc2"]
    assert sub.signal_coords == ["x", "y", "z"]


def test_apply_running_win(white_noise):
    win_inc = 0.1
    applied = white_noise.apply_running_win(np.mean, win_size=0.5, win_inc=win_inc)
    assert applied.sr == white_noise.sr * win_inc
    assert applied._sig.shape[0] == 95


def test_apply_running_win_propagates_labels_meta_history():
    """Rate-changing methods build a fresh Data; they must still propagate
    signal_names / signal_coords / meta / _history."""
    parent = Data(
        np.random.random((1000, 6)),
        sr=100,
        signal_names=["acc1", "acc2"],
        signal_coords=["x", "y", "z"],
        meta={"k": "v"},
    )
    applied = parent.apply_running_win(np.mean, win_size=0.5, win_inc=0.1)
    assert applied.signal_names == ["acc1", "acc2"]
    assert applied.signal_coords == ["x", "y", "z"]
    assert applied.meta.get("k") == "v"
    assert any(h[0] == "apply_running_win" for h in applied._history)


def test_comparison(white_noise):
    assert (white_noise <= 0)._sig.shape == white_noise._sig.shape


def test_onoff_times(white_noise):
    on_times, off_times = (white_noise < 0).onoff_times()
    assert isinstance(on_times, list)
    assert isinstance(off_times, list)


def test_find_crossings(white_noise):
    pos_crossings, neg_crossings = white_noise.find_crossings()
    assert isinstance(pos_crossings, list)
    assert isinstance(neg_crossings, list)


def test_split_to_1d(accelerometer):
    split = accelerometer.split_to_1d()
    assert len(split) == 3
    assert all(s._sig.shape == (1000,) for s in split)


def test_split_to_1d_history_shape(accelerometer):
    """Every history entry must be a 2-tuple (name, payload). The split
    entry's payload is a dict carrying col / signal_name / signal_coord."""
    split = accelerometer.split_to_1d()
    for col, s in enumerate(split):
        assert all(len(h) == 2 for h in s._history)
        last_name, last_payload = s._history[-1]
        assert last_name == "split"
        assert isinstance(last_payload, dict)
        assert last_payload["col"] == col
        assert last_payload["signal_name"] == s.signal_names[0]
        assert last_payload["signal_coord"] == s.signal_coords[0]


def test_transpose(accelerometer):
    transposed = accelerometer.transpose()
    assert transposed._sig.shape == (3, 1000)
    assert accelerometer.axis == 0
    assert transposed.axis == 1


def test_fft(white_noise):
    f, amp = white_noise.fft()
    assert f.shape == amp.shape


def test_fft_as_sampled(white_noise):
    fft_sampled = white_noise.fft_as_sampled()
    assert fft_sampled._sig.shape[0] == 500


def test_fft_as_sampled_propagates_meta_history():
    parent = Data(
        np.random.random((1000, 6)),
        sr=100,
        signal_names=["acc1", "acc2"],
        signal_coords=["x", "y", "z"],
        meta={"k": "v"},
    )
    out = parent.fft_as_sampled()
    assert out.signal_names == ["acc1", "acc2"]
    assert out.signal_coords == ["x", "y", "z"]
    assert out.meta.get("k") == "v"
    assert any(h[0] == "fft_as_sampled" for h in out._history)


def test_psd(white_noise, accelerometer):
    f, Pxx = white_noise.psd()
    assert f.shape == Pxx.shape
    f, Pxx = accelerometer.psd()
    assert Pxx.shape == (251, 3)


def test_psd_as_sampled(white_noise):
    psd_sampled = white_noise.psd_as_sampled()
    assert psd_sampled._sig.shape[0] == 251


def test_psd_as_sampled_propagates_meta_history():
    parent = Data(
        np.random.random((1000, 6)),
        sr=100,
        signal_names=["acc1", "acc2"],
        signal_coords=["x", "y", "z"],
        meta={"k": "v"},
    )
    out = parent.psd_as_sampled()
    assert out.signal_names == ["acc1", "acc2"]
    assert out.signal_coords == ["x", "y", "z"]
    assert out.meta.get("k") == "v"
    assert any(h[0] == "psd_as_sampled" for h in out._history)


def test_frac_power_propagates_meta_history():
    """frac_power outputs a 1D scalar-per-window signal, so use a 1D parent."""
    parent = Data(
        np.random.random(2000),
        sr=100,
        meta={"k": "v"},
    )
    out = parent.frac_power(freq_lim=(2.0, 10.0), win_size=2.0, win_inc=1.0)
    assert out.meta.get("k") == "v"
    assert any(h[0] == "frac_power" for h in out._history)


def test_np_trapezoid_shim_resolves_on_either_numpy_lineage():
    """The compat shim in pysampled.core picks np.trapezoid on numpy 2.x and
    falls back to np.trapz on numpy 1.x. CI failed on 1.1.3 because numpy 2.x
    removed np.trapz; this test pins that frac_power keeps working regardless."""
    from pysampled.core import _np_trapezoid

    assert _np_trapezoid is not None
    expected = getattr(np, "trapezoid", None) or getattr(np, "trapz", None)
    assert _np_trapezoid is expected

    parent = Data(np.random.random(2000), sr=100)
    out = parent.frac_power(freq_lim=(2.0, 10.0), win_size=2.0, win_inc=1.0)
    assert np.all(np.isfinite(out._sig[~np.isnan(out._sig)]))


def test_diff(white_noise):
    diffed = white_noise.diff()
    assert diffed._sig.shape == (1000,)


def test_diff_rejects_single_sample():
    """Data.diff() with <2 samples used to IndexError; now raises ValueError."""
    one_sample_1d = Data(np.array([1.0]), sr=100)
    with pytest.raises(ValueError, match="at least 2 samples"):
        one_sample_1d.diff()

    # 2D with explicit axis=0 (sample axis), 1 sample × 3 signals.
    one_sample_2d = Data(np.array([[1.0, 2.0, 3.0]]), sr=100, axis=0)
    with pytest.raises(ValueError, match="at least 2 samples"):
        one_sample_2d.diff()


def test_magnitude_per_signal_name_on_data_2d(data_2d):
    """1.2.0 behavior change: magnitude is per-signal_name. For data_2d with
    names=['acc1','acc2'] coords=['x','y','z'], output is (1000, 2) — the
    L2 norm across each signal's three coords."""
    out = data_2d.magnitude()
    assert out._sig.shape == (1000, 2)
    assert out.signal_names == ["acc1", "acc2"]
    assert out.signal_coords == ["mag"]
    assert np.allclose(out()[:, 0], np.linalg.norm(data_2d()[:, :3], axis=1))
    assert np.allclose(out()[:, 1], np.linalg.norm(data_2d()[:, 3:], axis=1))


def test_magnitude_propagates_meta_history():
    parent = Data(
        np.random.random((1000, 6)),
        sr=100,
        signal_names=["acc1", "acc2"],
        signal_coords=["x", "y", "z"],
        meta={"k": "v"},
    )
    out = parent.magnitude()
    assert out.meta.get("k") == "v"
    assert any(h[0] == "magnitude" for h in out._history)


def test_magnitude_1d_returns_self(data_1d):
    assert data_1d.magnitude() is data_1d


def test_magnitude_single_signal(data_2d):
    """A subset that's still a 'single multi-axis signal' (one name, all
    coords) collapses to a single magnitude column."""
    out = data_2d["acc1"].magnitude()
    assert out._sig.shape == (1000, 1)
    assert out.signal_names == ["acc1"]
    assert out.signal_coords == ["mag"]
    assert np.allclose(out()[:, 0], np.linalg.norm(data_2d()[:, :3], axis=1))


def test_magnitude_on_accelerometer(accelerometer):
    """The `generate_signal('accelerometer')` fixture defaults to three
    1-coord signals (`signal_names=['s0','s1','s2']`, `signal_coords=['x']`).
    Under the per-signal-name rule, magnitude becomes |x| per signal — a
    no-op besides taking absolute value. Pin this so the unusual case is
    surfaced if a user runs into it."""
    out = accelerometer.magnitude()
    assert out._sig.shape == (1000, 3)
    assert out.signal_coords == ["mag"]


def test_apply(white_noise, accelerometer):
    applied = white_noise.apply(lambda x: x**2)
    assert applied._sig.shape == (1000,)
    # Under the 1.2.0 n_signals rule, a shape-changing func no longer raises;
    # it auto-resets labels to defaults. Pin that behavior here.
    auto = accelerometer.apply(lambda x: np.linalg.norm(x, axis=1))
    assert auto._sig.shape == (1000,)
    assert auto.signal_coords == ["x"]
    assert auto.signal_names == ["s0"]
    x1 = accelerometer.apply(
        lambda x: np.linalg.norm(x, axis=1),
        signal_names=["acc1"],
        signal_coords=["mag"],
    )
    assert x1.signal_names == ["acc1"]
    assert x1.signal_coords == ["mag"]


def test_apply_n_signals_preserved_keeps_labels(data_2d):
    """When func returns the same number of signals, labels propagate."""
    out = data_2d.apply(lambda x, axis: x * 2)
    assert out.signal_names == ["acc1", "acc2"]
    assert out.signal_coords == ["x", "y", "z"]


def test_apply_time_length_change_keeps_labels(data_2d):
    """A time-axis-only change does not by itself trigger a label reset.
    Only n_signals matters."""
    out = data_2d.apply(lambda x, axis: x[100:])
    assert out._sig.shape[0] == data_2d._sig.shape[0] - 100
    assert out.signal_names == ["acc1", "acc2"]
    assert out.signal_coords == ["x", "y", "z"]


def test_apply_n_signals_change_resets_labels(data_2d):
    """A func that drops signals collapses to defaults rather than raising."""
    out = data_2d.apply(lambda x, axis: x.mean(axis=1, keepdims=True))
    assert out._sig.shape == (1000, 1)
    assert out.signal_coords == ["x"]
    assert out.signal_names == ["s0"]


def test_apply_explicit_labels_win(data_2d):
    """Explicit signal_names / signal_coords always override the n_signals
    auto-reset."""
    out = data_2d.apply(
        lambda x, axis: x.mean(axis=1, keepdims=True),
        signal_names=["combo"],
        signal_coords=["mean"],
    )
    assert out.signal_names == ["combo"]
    assert out.signal_coords == ["mean"]


def test_apply_typeerror_in_func_not_swallowed():
    """An unrelated TypeError inside func must re-raise. Pre-1.2.0 the
    blanket try/except in apply silently retried without axis=, masking
    real bugs."""
    parent = Data(np.zeros((100, 3)), sr=10, signal_names=["s"], signal_coords=["x", "y", "z"])

    def bad(x, axis):
        raise TypeError("unrelated bug, has nothing to do with axis")

    with pytest.raises(TypeError, match="unrelated bug"):
        parent.apply(bad)


def test_apply_to_each_signal_n_signals_preserved(accelerometer):
    """apply_to_each_signal with a shape-preserving (per-signal) op keeps
    labels."""
    out = accelerometer.apply_to_each_signal(lambda x: x * 2)
    assert out.signal_names == accelerometer.signal_names
    assert out.signal_coords == accelerometer.signal_coords


def test_apply_along_signals_unchanged(accelerometer):
    """Pin existing behavior: apply_along_signals collapses to 1D and labels
    reset (already the case before 1.2.0; pinned to detect regressions)."""
    out = accelerometer.apply_along_signals(np.mean)
    assert out._sig.shape == (1000,)
    assert out.signal_coords == ["x"]


def test_split_by_signal_name(data_2d):
    parts = data_2d.split_by_signal_name()
    assert len(parts) == 2
    assert parts[0].signal_names == ["acc1"]
    assert parts[0].signal_coords == ["x", "y", "z"]
    assert parts[0]._sig.shape == (1000, 3)
    assert parts[1].signal_names == ["acc2"]
    assert np.allclose(parts[0](), data_2d()[:, :3])
    assert np.allclose(parts[1](), data_2d()[:, 3:])


def test_split_by_signal_coord(data_2d):
    parts = data_2d.split_by_signal_coord()
    assert len(parts) == 3
    for part, coord in zip(parts, ["x", "y", "z"]):
        assert part.signal_coords == [coord]
        assert part.signal_names == ["acc1", "acc2"]
        assert part._sig.shape == (1000, 2)


def test_split_by_signal_name_on_data_2d_transposed(data_2d_transposed):
    parts = data_2d_transposed.split_by_signal_name()
    assert len(parts) == 2
    assert parts[0].signal_names == ["acc1"]
    assert parts[0]._sig.shape == (3, 1000)


def test_split_by_signal_name_1d_returns_self(data_1d):
    parts = data_1d.split_by_signal_name()
    assert parts == [data_1d]


def test_split_by_signal_coord_1d_returns_self(data_1d):
    parts = data_1d.split_by_signal_coord()
    assert parts == [data_1d]


def test_transpose_preserves_labels(data_2d):
    """Pin the documented contract: transpose preserves signal_names and
    signal_coords because they describe the logical signal axis,
    independent of which physical axis it lives on."""
    out = data_2d.transpose()
    assert out.signal_names == data_2d.signal_names
    assert out.signal_coords == data_2d.signal_coords
    assert out.n_signals() == data_2d.n_signals()


def test_pipeline_apply_running_win_then_magnitude(data_2d):
    """Compose a rate-changing op (apply_running_win) with a shape-changing
    op (magnitude) and confirm meta/labels survive the chain."""
    parent = Data(
        data_2d._sig,
        sr=data_2d.sr,
        signal_names=list(data_2d.signal_names),
        signal_coords=list(data_2d.signal_coords),
        meta={"k": "v"},
    )
    out = parent.apply_running_win(np.mean).magnitude()
    assert out.signal_names == ["acc1", "acc2"]
    assert out.signal_coords == ["mag"]
    assert out.meta.get("k") == "v"
    assert any(h[0] == "apply_running_win" for h in out._history)
    assert any(h[0] == "magnitude" for h in out._history)



def test_apply_along_signals(accelerometer):
    applied = accelerometer.apply_along_signals(np.mean)
    assert applied._sig.shape == (1000,)


def test_apply_to_each_signal(accelerometer):
    applied = accelerometer.apply_to_each_signal(
        np.mean
    )  # Even though this works, this is not the intention of this method
    assert applied._sig.shape == (1, 3)


def test_regress(three_sine_waves, sine_wave):
    regressed = three_sine_waves.regress(sine_wave)
    assert regressed._sig.shape == sine_wave._sig.shape


def test_resample(white_noise):
    resampled = white_noise.resample(50)
    assert resampled._sig.shape == (500,)


def test_smooth(white_noise):
    smoothed = white_noise.smooth(win_size=0.5)
    assert smoothed._sig.shape == (1000,)


def test_xlim(white_noise):
    xlim = white_noise.xlim()
    assert isinstance(xlim, tuple)


def test_ylim(white_noise):
    ylim = white_noise.ylim()
    assert isinstance(ylim, tuple)


def test_logdj(accelerometer, white_noise):
    logdj = (
        white_noise.logdj()
    )  # this should be a velocity signal, but testing for a point moving in 1D
    assert isinstance(logdj, float)
    logdj = accelerometer.logdj()  # technically, this should be a velocity signal
    assert isinstance(logdj, float)


def test_logdj2(white_noise):
    logdj2 = white_noise.logdj2()
    assert isinstance(logdj2, float)


def test_sparc(white_noise):
    sparc = white_noise.sparc()
    assert isinstance(sparc, float)


def test_set_nan(white_noise):
    set_nan = white_noise.set_nan([(0.5, 1.0)])
    assert np.isnan(set_nan._sig[50:101]).all()


def test_remove_and_interpolate(white_noise):
    removed = white_noise.remove_and_interpolate([(0.5, 1.0)])
    assert not np.isnan(removed._sig).any()


def test_siglets(three_sine_waves):
    sl = Siglets(three_sine_waves, (-1, 2, 4.7, 6.2, 7.1, 9.9), window=(-1.0, 2.0))
    assert sl.n == 4
    assert sl().shape == (301, 4)
    sl = Siglets(three_sine_waves, (-1, 2, 4.7, 6.2, 7.1, 9.9), window=(-10, 20))
    assert sl().shape == (31, 4)


def test_access_by_signal_name(data_2d, data_2d_transposed):
    """Test accessing signals by their names."""
    acc1 = data_2d["acc1"]
    assert np.allclose(acc1(), data_2d()[:, :3])
    assert np.allclose(data_2d["x"](), data_2d()[:, ::3])
    assert np.allclose(data_2d["y"](), data_2d()[:, 1::3])
    assert np.allclose(data_2d["z"](), data_2d()[:, 2::3])
    assert acc1.n_signals() == 3
    assert acc1.signal_names == ["acc1"]
    assert acc1.signal_coords == ["x", "y", "z"]

    acc2 = data_2d["acc2"]
    assert np.allclose(acc2(), data_2d()[:, 3:])
    assert acc2.n_signals() == 3
    assert acc2.signal_names == ["acc2"]
    assert acc2.signal_coords == ["x", "y", "z"]

    assert np.allclose(data_2d_transposed["acc1"](), data_2d_transposed()[:3, :])
    assert np.allclose(data_2d_transposed["acc2"](), data_2d_transposed()[3:, :])
    assert np.allclose(data_2d_transposed["x"](), data_2d_transposed()[::3, :])
    assert np.allclose(data_2d_transposed["y"](), data_2d_transposed()[1::3, :])
    assert np.allclose(data_2d_transposed["z"](), data_2d_transposed()[2::3, :])


def test_access_by_signal_coord(data_2d):
    """Test accessing signals by their coordinates."""
    x_coord = data_2d["x"]
    assert x_coord.n_signals() == 2
    assert x_coord.signal_names == ["acc1", "acc2"]
    assert x_coord.signal_coords == ["x"]

    y_coord = data_2d["y"]
    assert y_coord.n_signals() == 2
    assert y_coord.signal_names == ["acc1", "acc2"]
    assert y_coord.signal_coords == ["y"]


def test_access_by_signal_name_and_coord(data_2d):
    """Test accessing specific signals by both names and coordinates."""
    acc1_x = data_2d["acc1"]["x"]
    assert np.allclose(acc1_x(), data_2d()[:, :1])
    assert acc1_x.n_signals() == 1
    assert acc1_x.signal_names == ["acc1"]
    assert acc1_x.signal_coords == ["x"]


def test_get_multiaxis_signals_preserves_user_order(data_2d):
    """Selecting names in non-parent order must reorder the columns to
    match. Parent columns are [acc1_x, acc1_y, acc1_z, acc2_x, acc2_y, acc2_z]
    so requesting ['acc2', 'acc1'] must yield columns [3,4,5,0,1,2]."""
    sub = data_2d[["acc2", "acc1"]]
    assert sub.signal_names == ["acc2", "acc1"]
    assert sub.signal_coords == ["x", "y", "z"]
    expected = data_2d()[:, [3, 4, 5, 0, 1, 2]]
    assert np.allclose(sub(), expected)


def test_get_coord_preserves_user_order(data_2d):
    """Selecting coords in non-parent order must reorder columns while
    keeping the names-outer / coords-inner invariant. For coords ['z','x']
    output cols = [(acc1,z),(acc1,x),(acc2,z),(acc2,x)] = parent [2,0,5,3]."""
    sub = data_2d[["z", "x"]]
    assert sub.signal_names == ["acc1", "acc2"]
    assert sub.signal_coords == ["z", "x"]
    expected = data_2d()[:, [2, 0, 5, 3]]
    assert np.allclose(sub(), expected)


def test_get_multiaxis_signals_preserves_user_order_transposed(data_2d_transposed):
    """Same property must hold along the other axis."""
    sub = data_2d_transposed[["acc2", "acc1"]]
    assert sub.signal_names == ["acc2", "acc1"]
    assert sub.signal_coords == ["x", "y", "z"]
    expected = data_2d_transposed()[[3, 4, 5, 0, 1, 2], :]
    assert np.allclose(sub(), expected)


def test_invalid_access(data_2d):
    """Test invalid access scenarios."""
    with pytest.raises(KeyError):
        data_2d["invalid"]


def test_subset_creation(data_2d):
    """Test creating subsets of IndexedData."""
    subset = data_2d["acc1"]["x"]
    assert subset.n_signals() == 1
    assert subset.signal_names == ["acc1"]
    assert subset.signal_coords == ["x"]


def test_transposed_data_access(data_2d_transposed):
    """Test accessing signals in transposed data."""
    acc1 = data_2d_transposed["acc1"]
    assert acc1.n_signals() == 3
    assert acc1.signal_names == ["acc1"]
    assert acc1.signal_coords == ["x", "y", "z"]

    x_coord = data_2d_transposed["x"]
    assert x_coord.n_signals() == 2
    assert x_coord.signal_names == ["acc1", "acc2"]
    assert x_coord.signal_coords == ["x"]


def test_1d_data_access(data_1d):
    """Test accessing 1D data."""
    assert data_1d.n_signals() == 1
    assert np.allclose(data_1d["s0"](), data_1d())
    assert np.allclose(data_1d["x"](), data_1d())


# def test_smooth_vs_moving_average():
#     s = Data(np.hstack((np.arange(20), np.arange(20)[::-1])), sr=12)

#     pysampled.plot([s, s.smooth(0.3), s.moving_average(0.3)]) # even kernel
#     pysampled.plot([s, s.smooth(0.4), s.moving_average(0.4)]) # odd kernel


def test_meta_survives_multi_step_pipeline():
    parent = Data(
        np.random.random(2000),
        sr=100,
        meta={"stream_id": "abc"},
    )
    out = parent.bandpass(2.0, 30.0).envelope().shift_baseline()
    assert out.meta.get("stream_id") == "abc"


def test_init_rejects_n_signals_label_mismatch():
    """The n_signals == len(signal_names) * len(signal_coords) invariant must
    be enforced at construction time. Pinned so the upcoming _validate
    refactor cannot silently weaken it."""
    with pytest.raises(AssertionError):
        Data(
            np.zeros((100, 6)),
            sr=10,
            signal_names=["a", "b"],
            signal_coords=["x", "y"],
        )


def test_setstate_validates_malformed_pickle():
    """A pickle whose signal_names / signal_coords / data shape no longer
    satisfy the n_signals == names * coords invariant must raise on
    unpickle, not silently restore. The existing old-shape round-trip test
    only covers the missing-attribute path; this pins the malformed path."""
    parent = Data(
        np.zeros((100, 6)),
        sr=10,
        signal_names=["acc1", "acc2"],
        signal_coords=["x", "y", "z"],
    )
    state = parent.__dict__.copy()
    state["signal_names"] = ["a", "b", "c"]  # 6 != 3 * 3
    payload = pickle.dumps(state)

    restored_state = pickle.loads(payload)
    new = Data.__new__(Data)
    with pytest.raises(AssertionError):
        new.__setstate__(restored_state)


def test_setstate_old_pickle_round_trip():
    """An old pickle (no meta, no signal_coords, no signal_names) must
    round-trip with the documented defaults restored."""
    parent = Data(np.zeros((100, 6)), sr=10)
    state = parent.__dict__.copy()
    state.pop("meta", None)
    state.pop("signal_coords", None)
    state.pop("signal_names", None)
    payload = pickle.dumps(state)

    restored_state = pickle.loads(payload)
    new = Data.__new__(Data)
    new.__setstate__(restored_state)
    assert new.meta == {}
    assert new.signal_coords == ["x"]
    assert new.signal_names == [f"s{i}" for i in range(6)]


def test_transpose_then_string_index(data_2d):
    transposed = data_2d.transpose()
    sub = transposed["acc1"]
    assert sub.signal_names == ["acc1"]
    assert sub.signal_coords == ["x", "y", "z"]
    assert sub.n_signals() == 3


def test_subset_then_bandpass(data_2d):
    """Composition: subset by name and coord, then run a rate-preserving
    filter. Labels must survive intact through the pipeline."""
    sub = data_2d["acc1"]["x"].bandpass(2.0, 30.0)
    assert sub.signal_names == ["acc1"]
    assert sub.signal_coords == ["x"]
    assert sub.n_signals() == 1


# ---------------------------------------------------------------------------
# merge_along_* classmethods (1.3.0) — inverses of the split_by_* family
# ---------------------------------------------------------------------------


def test_merge_along_signal_name_round_trip(data_2d):
    parts = data_2d.split_by_signal_name()
    assert len(parts) == 2
    rebuilt = Data.merge_along_signal_name(parts)
    assert np.allclose(rebuilt(), data_2d())
    assert rebuilt.signal_names == data_2d.signal_names
    assert rebuilt.signal_coords == data_2d.signal_coords


def test_merge_along_signal_coord_round_trip(data_2d):
    parts = data_2d.split_by_signal_coord()
    assert len(parts) == 3
    rebuilt = Data.merge_along_signal_coord(parts)
    # column permutation must restore the exact names-outer / coords-inner order
    assert np.allclose(rebuilt(), data_2d())
    assert rebuilt.signal_names == data_2d.signal_names
    assert rebuilt.signal_coords == data_2d.signal_coords


def test_merge_along_time_contiguous():
    sr = 100
    sig = np.arange(20, dtype=float)
    a = Data(sig[0:10], sr=sr, t0=0.0)
    b = Data(sig[10:20], sr=sr, t0=10.0 / sr)  # starts one sample after a ends
    merged = Data.merge_along_time([a, b])
    assert len(merged) == 20
    assert np.allclose(merged(), sig)


def test_merge_along_time_trims_one_sample_overlap():
    """The float-slice round-trip boundary: parts overlap by one sample; the
    duplicated sample is dropped rather than rejected."""
    sr = 100
    sig = np.arange(20, dtype=float)
    a = Data(sig[0:10], sr=sr, t0=0.0)
    b = Data(sig[9:20], sr=sr, t0=9.0 / sr)  # b[0] == a[-1] (overlap by one)
    merged = Data.merge_along_time([a, b])
    assert len(merged) == 20
    assert np.allclose(merged(), sig)


def test_merge_along_time_rejects_gap():
    sr = 100
    a = Data(np.arange(10, dtype=float), sr=sr, t0=0.0)
    b = Data(np.arange(10, dtype=float), sr=sr, t0=5.0)  # far-apart
    with pytest.raises(ValueError, match="not contiguous"):
        Data.merge_along_time([a, b])


def test_merge_meta_keeps_agreeing_drops_conflicting():
    sr = 100
    a = Data(np.random.random((100, 3)), sr=sr, signal_names=["n"],
             signal_coords=["x", "y", "z"], meta={"unit": "mV", "sensor": "A"})
    b = Data(np.random.random((100, 3)), sr=sr, signal_names=["m"],
             signal_coords=["x", "y", "z"], meta={"unit": "mV", "sensor": "B"})
    with pytest.warns(UserWarning, match="sensor"):
        merged = Data.merge_along_signal_name([a, b])
    assert merged.meta == {"unit": "mV"}  # agreeing kept, conflicting dropped


def test_merge_meta_override_wins_and_is_silent(recwarn):
    sr = 100
    a = Data(np.random.random((100, 3)), sr=sr, signal_names=["n"],
             signal_coords=["x", "y", "z"], meta={"sensor": "A"})
    b = Data(np.random.random((100, 3)), sr=sr, signal_names=["m"],
             signal_coords=["x", "y", "z"], meta={"sensor": "B"})
    merged = Data.merge_along_signal_name([a, b], meta={"sensors": ["A", "B"]})
    assert merged.meta == {"sensors": ["A", "B"]}
    assert len(recwarn) == 0  # override path does not warn


def test_merge_tolerates_t0_float_drift():
    sr = 100
    a = Data(np.random.random((100, 3)), sr=sr, signal_names=["a"],
             signal_coords=["x", "y", "z"], t0=0.0)
    b = Data(np.random.random((100, 3)), sr=sr, signal_names=["b"],
             signal_coords=["x", "y", "z"], t0=1e-9)  # within 1/sr
    merged = Data.merge_along_signal_name([a, b])  # must not raise
    assert merged.signal_names == ["a", "b"]


def test_merge_rejects_coord_mismatch():
    a = Data(np.random.random((100, 3)), sr=100, signal_names=["a"], signal_coords=["x", "y", "z"])
    b = Data(np.random.random((100, 2)), sr=100, signal_names=["b"], signal_coords=["x", "y"])
    with pytest.raises(ValueError, match="signal_coords mismatch"):
        Data.merge_along_signal_name([a, b])


def test_merge_empty_raises():
    with pytest.raises(ValueError, match="at least one"):
        Data.merge_along_signal_name([])


def test_merge_along_signal_name_rejects_1d():
    a = Data(np.arange(10.0), sr=100)
    b = Data(np.arange(10.0), sr=100)
    with pytest.raises(ValueError, match="2D"):
        Data.merge_along_signal_name([a, b])
