# Singularis SPHEREx

Beyond Limits, Beyond the Known.

Static website for comparing SPHEREx observations. Two prepared examples are included. A small Python API searches the NASA/IPAC IRSA archive for other valid ICRS sky coordinates. Live results can contain two to five usable frames, depending on the archive and quality checks.

## GitHub Pages deployment

Publish the repository's `main` branch from its root directory in Settings → Pages.
This directory is ready for GitHub Pages: `index.html` is at the repository root.

## Editing

- `index.html`: page structure and text
- `styles.css`: colors, typography, layout and mobile styles
- `app.js`: target metadata, interaction and image paths
- `wise0855-may.png`, `wise0855-nov.png`, `rwaur-sep.png`, `rwaur-mar.png`: four aligned display images

## Live search API

Deploy this repository as a free Render web service using `render.yaml`. Once the service is running, set `window.SINGULARIS_API_BASE` in `config.js` to its HTTPS origin, without a trailing slash. GitHub Pages remains the user-facing site. The API queries the official SIA2 endpoint for DR1 and QR3 records, selects up to five visits from the same detector at nearby catalog wavelengths and at least 30 days apart, requests FITS cutouts, and aligns them on a common WCS grid with `reproject`. It checks actual target-position wavelengths, rejects insufficient usable overlap, and uses one display scale. It returns display images, a preliminary numerical difference image when sufficient overlap exists, per-frame quality indicators, and raw FITS links. The display masks selected bad-pixel flags but keeps the SOURCE flag visible. The per-frame wavelength is measured from the FITS spectral WCS at the input coordinate; the displayed mask fraction is a quality indicator, not a flux uncertainty. These are preliminary visual comparisons, not confirmed detections; PSF differences and photometric uncertainty need further checks.

The optional Sky Map loads CDS Aladin Lite only when opened. Its background survey is distinct from SPHEREx. It can update the coordinate fields and start a SPHEREx search. The viewer continues to work if the map service fails. Calibrated photometry is unavailable because the current image quality and uncertainty workflow does not support a defensible flux measurement.

For local checks, install `api/requirements-dev.txt`, run `python -m playwright install chromium`, and then run `python -m pytest -q api/test_server.py tests/browser/test_viewer.py`. Backend tests mock archive responses and cover coordinate checks, VOTable parsing, frame selection, WCS alignment, sparse overlap, bad FITS, and metadata. Browser tests mock the API for two and five frames and cover playback, comparison, errors, the optional map, and a mobile viewport. Real archive verification is separate from these deterministic tests.

Source data: NASA/IPAC IRSA SPHEREx DR1 and QR3. The page links to the original FITS cutouts and contains the required acknowledgement.

## Science audit

The [science audit](SCIENCE_AUDIT.md) checks the four FITS files behind the prepared examples at the stated target coordinates and records preliminary checks of three additional challenge fields. RW Aurigae's core is flagged `OVERFLOW` in both epochs, and the WISE 0855 fixed coordinate has not been propagated for proper motion and parallax. None of these fields supports a confirmed motion or variability claim from the current analysis. The examples demonstrate the search and visual-comparison workflow.
