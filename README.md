# Singularis SPHEREx

Beyond Limits, Beyond the Known.

Static website for comparing SPHEREx observations. Two prepared examples are included. A small Python API can search the NASA/IPAC IRSA archive for other sky coordinates.

## GitHub Pages deployment

Publish the repository's `main` branch from its root directory in Settings → Pages.
This directory is ready for GitHub Pages: `index.html` is at the repository root.

## Editing

- `index.html`: page structure and text
- `styles.css`: colors, typography, layout and mobile styles
- `app.js`: target metadata, interaction and image paths
- `wise0855-may.png`, `wise0855-nov.png`, `rwaur-sep.png`, `rwaur-mar.png`: four aligned display images

## Live search API

Deploy this repository as a free Render web service using `render.yaml`. Once the service is running, set `window.SINGULARIS_API_BASE` in `config.js` to its HTTPS origin, without a trailing slash. GitHub Pages remains the user-facing site. The API queries the official SIA2 endpoint for DR1 and QR3 records, picks two observations from the same detector at nearby catalog wavelengths at least 30 days apart, requests FITS cutouts, aligns the images with WCS, and returns two display images and raw FITS links. These are preliminary visual comparisons, not confirmed detections; target-specific wavelength, PSF, and photometric uncertainty need further checks.

Source data: NASA/IPAC IRSA SPHEREx DR1. The page links to the original FITS cutouts and contains the required acknowledgement.
