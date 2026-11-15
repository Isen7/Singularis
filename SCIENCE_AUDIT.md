# Singularis: science audit of the published example fields

**Result:** Neither published two-frame example establishes a measured change in its named target. The images are valid illustrations of the time-comparison interface, but they are not evidence for a new object, target motion, or target variability.

## What was checked

We reopened the four original NASA/IPAC IRSA SPHEREx FITS cutouts used by the site's prepared examples. At the site's stated coordinates, the spatial FITS WCS provided the detector pixel. The alternate `W` WCS provided the wavelength and bandpass width at that pixel; its spatial SIP distortion was disabled, as in the [IRSA spectral-image tutorial](https://caltech-ipac.github.io/irsa-tutorials/spherex-intro/). We decoded the FITS `FLAGS` bitmask using each file's own `MSKNnnnn` header definitions. A 2.5-pixel-radius aperture was inspected around the entered coordinate. The audit JSON records the exact pixel coordinates, wavelength, bandpass, and count of flagged pixels.

| Example | Observation dates (UTC) | Wavelength at entered coordinate | Quality finding | Scientific conclusion |
|---|---|---|---|---|
| WISE 0855 | 2025-05-06 / 2025-11-07 | 1.280417 / 1.285176 µm | No bad-pixel flags in the inspected aperture; all aperture pixels have the ordinary `SOURCE` flag. The site's fixed coordinate was not propagated to each epoch for this high-proper-motion object. | Target identity and motion have not been established in these frames. |
| RW Aurigae | 2025-09-03 / 2026-03-04 | 0.858651 / 0.858217 µm | The target core has `OVERFLOW` in both images; the first also has `BLOOM`. Nearby pixels additionally carry `TRANSIENT`, `SUR_ERROR`, or `HALO` in the inspected aperture. | Direct core brightness comparison is unreliable; variability is not established. |

The two wavelengths in each pair are close relative to their respective bandpass widths (approximately 0.031 µm for WISE 0855 and 0.021 µm for RW Aurigae). This is a useful preliminary matching check, not a flux calibration. SPHEREx pixels are approximately 6.1 arcsec wide in these cutouts.

WISE 0855 has published proper motion of about 8.1 arcsec per year, which corresponds to roughly 4 arcsec between these two visits, before considering parallax. A fixed coordinate marker does not track the object. At these wavelengths, the object also requires a demonstrated detection and source association before a displacement can be measured. See the [published NEOWISE measurement](https://arxiv.org/abs/1405.7350).

The IRSA documentation defines `OVERFLOW` as nearing saturation and explains that the [spectrophotometry tool](https://irsa.ipac.caltech.edu/onlinehelp/spherex/spherex/sp.html) fits a position-dependent PSF, uses the `VARIANCE` layer, masks source pixels for local background estimation, and reports flux uncertainty and fit quality. Although those layers are present in our FITS files, a reliable target flux cannot be obtained from the affected RW Aurigae core by simply summing the displayed pixels.

## Claim suitable for the project

> Singularis retrieves real SPHEREx observations and makes repeated visits easy to compare visually. The prepared examples demonstrate the workflow. They are not confirmed detections of motion or brightness change; the quality audit identifies saturation in the RW Aurigae pair and a missing epoch-dependent position for WISE 0855.

## Requirements for a future detection claim

1. Propagate the target's catalog position, proper motion, and parallax to each exposure time, then verify the source is detected at both positions. For a new object, cross-match against known catalogs and obtain follow-up observations.
2. Use clean observations or a validated PSF-fitting method that handles saturated cores and nearby sources. The present RW Aurigae pair does not pass this gate.
3. Compare measurements at the target-specific wavelengths with flux errors, fit quality, background, and all relevant pixel flags. Demonstrate a significant difference against stable comparison sources and the instrument's systematic uncertainty.
4. Retain the raw FITS URLs, observation IDs, processing versions, and analysis code so the result can be independently reproduced.

## Reproduction

Run `python validate_examples.py` with the four named FITS files beside the script. The script writes `Singularis-science-audit.json`. The JSON is the machine-readable record of this audit. This audit deliberately reports no flux significance or discovery probability because the necessary source association and quality gates have not passed.
