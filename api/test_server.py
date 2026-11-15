"""Checks for observation selection and sky-coordinate alignment."""
import sys
from pathlib import Path

import numpy as np
import pytest
from astropy.table import Table
from astropy.io.votable import from_table, writeto
from astropy.wcs import WCS
import io

sys.path.insert(0, str(Path(__file__).resolve().parent))
import server


def sky_wcs(ra=100.0):
    wcs = WCS(naxis=2)
    wcs.wcs.crpix = [5.0, 5.0]
    wcs.wcs.cdelt = [-0.001, 0.001]
    wcs.wcs.crval = [ra, 20.0]
    wcs.wcs.ctype = ['RA---TAN', 'DEC--TAN']
    return wcs


def test_choose_frames_keeps_distinct_visits_and_one_detector():
    rows = [
        {'time': time, 'band': band, 'detector': detector, 'url': str(time)}
        for time, band, detector in [
            (100, 1.00, 'D1'), (101, 1.00, 'D1'), (145, 1.01, 'D1'),
            (190, 1.00, 'D1'), (235, 1.00, 'D1'), (280, 1.00, 'D1'),
            (330, 1.00, 'D1'), (350, 1.20, 'D1'), (360, 1.00, 'D2'),
        ]
    ]
    selected = server.choose_frames(rows, maximum=5)
    assert len(selected) == 5
    assert selected[0]['time'] == 100
    assert selected[-1]['time'] == 330
    assert all(item['detector'] == 'D1' for item in selected)
    assert all(b['time'] - a['time'] >= 30 for a, b in zip(selected, selected[1:]))


def test_choose_frames_requires_repeated_compatible_observations():
    with pytest.raises(LookupError):
        server.choose_frames([{'time': 100, 'band': 1.0, 'detector': 'D1'},
                              {'time': 110, 'band': 1.0, 'detector': 'D1'}])


def test_reproject_aligns_same_sky_position():
    reference = {'data': np.ones((10, 10)), 'wcs': sky_wcs()}
    shifted_wcs = sky_wcs(ra=100.001)
    source = np.zeros((10, 10))
    x, y = map(float, shifted_wcs.world_to_pixel_values(100.0, 20.0))
    source[round(y), round(x)] = 10
    aligned = server.align({'data': source, 'wcs': shifted_wcs}, reference)
    assert np.unravel_index(np.nanargmax(aligned), aligned.shape) == (4, 4)
    assert np.isnan(aligned).any()  # No extrapolation outside the cutout.


def test_search_returns_multiple_frames_in_date_order(monkeypatch):
    rows = [{'time': time, 'band': 1.0, 'detector': 'D1', 'url': str(time),
             'collection': 'spherex_dr1'} for time in (100, 145, 190)]
    monkeypatch.setattr(server, 'query', lambda ra, dec: rows)
    monkeypatch.setattr(server, 'cutout', lambda item, ra, dec: {
        'data': np.full((10, 10), item['time'], dtype=float),
        'wcs': sky_wcs(), 'date': str(item['time']), 'url': item['url'],
        'detector': 'D1', 'collection': item['collection'],
        'wavelength_um': 1.0, 'bandwidth_um': 0.02, 'masked_fraction': 0.0,
        'observation_id': str(item['time']), 'processing_version': 'test-v1',
    })
    monkeypatch.setattr(server, 'render', lambda data, low, high, marker: 'image')
    server.CACHE.clear()
    result = server.search(42.0, 12.0)
    assert [frame['date'] for frame in result['frames']] == ['100', '145', '190']
    assert all(frame['image'] == 'image' for frame in result['frames'])
    assert all(frame['observation_id'] == frame['date'] for frame in result['frames'])
    assert all(frame['source'] == frame['date'] for frame in result['frames'])
    assert all(frame['detector'] == result['detector'] for frame in result['frames'])
    assert all(frame['usable_fraction'] == pytest.approx(1.0) for frame in result['frames'])


def test_difference_uses_numeric_overlap_and_rejects_sparse_coverage():
    earlier = np.zeros((10, 10))
    later = earlier.copy()
    later[5, 5] = 10
    assert server.render_difference(earlier, later).startswith('data:image/png;base64,')
    earlier[:5, :] = np.nan
    assert server.render_difference(earlier, later) is None


@pytest.mark.parametrize('ra,dec', [(0, -90), (359.999, 90)])
def test_valid_coordinates(ra, dec):
    server.validate_coordinates(ra, dec)


@pytest.mark.parametrize('ra,dec', [(-1, 0), (360, 0), (0, -91), (0, 91), (float('nan'), 0)])
def test_invalid_coordinates(ra, dec):
    with pytest.raises(ValueError):
        server.validate_coordinates(ra, dec)


def test_query_parses_irsa_votable_and_rejects_untrusted_urls(monkeypatch):
    table = Table({
        'access_url': [
            'https://irsa.ipac.caltech.edu/ibe/data/spherex/dr1/level2/a.fits',
            'https://another.example/ibe/data/spherex/dr1/level2/b.fits',
        ],
        'energy_bandpassname': ['SPHEREx-D2', 'SPHEREx-D2'],
        't_min': [60000.0, 60040.0],
        'em_min': [1.2e-6, 1.2e-6],
        'em_max': [1.3e-6, 1.3e-6],
    })
    payload = io.BytesIO()
    writeto(from_table(table), payload)
    monkeypatch.setattr(server, 'fetch', lambda url, limit=0: payload.getvalue())
    rows = server.query(42.0, 12.0)
    assert len(rows) == 2  # One trusted record from each queried collection.
    assert all(row['band'] == pytest.approx(1.25e-6) for row in rows)


def test_cutout_rejects_invalid_fits(monkeypatch):
    monkeypatch.setattr(server, 'fetch', lambda url: b'not a FITS image')
    with pytest.raises(OSError):
        server.cutout({'url': 'https://irsa.ipac.caltech.edu/ibe/data/spherex/dr1/level2/a.fits'}, 1, 2)


def test_fetch_rejects_external_url_before_network_access():
    with pytest.raises(ValueError):
        server.fetch('https://example.org/secret')


def test_processing_version_handles_reprocessed_fits_paths():
    url = 'https://irsa.ipac.caltech.edu/ibe/data/spherex/dr1/level2/x/l2b_retry-v27-2026-239/1/image.fits'
    assert server.processing_version(url) == 'l2b_retry-v27-2026-239'


def test_fetch_reports_timeout_after_bounded_retries(monkeypatch):
    attempts = []

    def timed_out(request, timeout):
        attempts.append(timeout)
        raise TimeoutError('Archive timed out')

    monkeypatch.setattr(server.urllib.request, 'urlopen', timed_out)
    monkeypatch.setattr(server.time, 'sleep', lambda seconds: None)
    with pytest.raises(TimeoutError):
        server.fetch('https://irsa.ipac.caltech.edu/SIA?COLLECTION=spherex_dr1')
    assert attempts == [35, 35, 35]


def test_search_reports_insufficient_usable_frames(monkeypatch):
    rows = [{'time': time, 'band': 1.0, 'detector': 'D1', 'url': str(time)} for time in (100, 145)]
    monkeypatch.setattr(server, 'query', lambda ra, dec: rows)
    monkeypatch.setattr(server, 'cutout', lambda item, ra, dec: {'data': np.full((10, 10), np.nan)})
    server.CACHE.clear()
    with pytest.raises(LookupError, match='insufficient usable overlap'):
        server.search(43.0, 12.0)
