"""Checks for independent astrometry, centroid fitting, and error handling."""
import sys
from pathlib import Path

import numpy as np
import pytest
from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.time import Time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_motion import displacement_uncertainty, fit_source
from motion_science import CATALOG, predict


def test_catalog_propagation_includes_proper_motion_and_parallax():
    origin = predict(Time(2016.0, format="jyear"))
    later = predict(Time(2026.0, format="jyear"))
    catalog = SkyCoord(CATALOG["ra_deg"] * u.deg, CATALOG["dec_deg"] * u.deg)
    assert origin.separation(catalog).arcsec < 0.3
    assert 45 < origin.separation(later).arcsec < 49
    spring = predict("2025-04-29T16:17:11.776")
    fall = predict("2026-09-28T08:04:44.319")
    assert 6.2 < spring.separation(fall).arcsec < 6.8


def test_source_fit_recovers_offset_without_forcing_catalog_position():
    yy, xx = np.indices((19, 19))
    data = 3 + 20 * np.exp(-0.5 * (((xx - 9.6) / .7)**2 + ((yy - 8.4) / .8)**2))
    variance = np.full_like(data, .1)
    bad = np.zeros(data.shape, dtype=bool)
    fit = fit_source(data, variance, bad, 9.0, 9.0)
    assert fit is not None
    assert fit["x"] == pytest.approx(9.6, abs=.03)
    assert fit["y"] == pytest.approx(8.4, abs=.03)
    assert fit["peak_snr"] > 20


def test_source_fit_rejects_masked_or_weak_source():
    yy, xx = np.indices((19, 19))
    data = 1 + 10 * np.exp(-0.5 * (((xx - 9) / .8)**2 + ((yy - 9) / .8)**2))
    variance = np.ones(data.shape)
    bad = np.zeros(data.shape, dtype=bool)
    bad[5:14, 5:14] = True
    assert fit_source(data, variance, bad, 9, 9) is None
    assert fit_source(np.ones_like(data), variance, np.zeros_like(bad), 9, 9) is None


def test_displacement_uncertainty_includes_both_epochs_and_registration():
    assert displacement_uncertainty([.15, .1], .5) == pytest.approx(np.sqrt(.15**2 + .1**2 + .5))
    with pytest.raises(ValueError):
        displacement_uncertainty([.1], .5)
    with pytest.raises(ValueError):
        displacement_uncertainty([.1, float("nan")], .5)
