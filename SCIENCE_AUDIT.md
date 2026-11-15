# Singularis: science audit and motion demonstration

**Original examples:** Neither original two-frame example establishes a measured change in its named target. The images are valid illustrations of the time-comparison interface, but they are not evidence for a new object, target motion, or target variability. A separate Epsilon Indi B analysis below measures known motion in three additional observations.

## Epsilon Indi B: measured motion with limitations (2026-11-15)

The [direct demonstration](https://isen7.github.io/Singularis/?demo=epsilon-indi-b#viewer) displays three background-aligned, numerical SPHEREx D6 FITS cutouts. Their target-position spectral WCS wavelengths span 4.660817–4.661144 µm (0.0070%), so the same infrared signal is compared. Each has `FINAST=0` and an unmasked target core. The dates and independent observation identifiers are:

| Date (UTC) | Observation ID | Processing | Target wavelength | Peak S/N | Fitted position (RA, Dec; degrees) | Position uncertainty |
|---|---|---|---:|---:|---|---:|
| 2025-04-29 16:17:11.776 | `2025W18_1B_0175_1` | DR1 | 4.660817 µm | 50.9 | 331.095596971, −56.800328025 | 0.52″ |
| 2025-06-10 04:33:19.725 | `2025W24_1A_0245_4` | DR1 | 4.661144 µm | 47.6 | 331.095855009, −56.800416460 | 0.51″ |
| 2026-09-28 08:04:44.319 | `2026W40_1A_0070_2` | QR3 | 4.660875 µm | 48.0 | 331.098229790, −56.801408264 | 0.51″ |

The [first](https://irsa.ipac.caltech.edu/ibe/data/spherex/dr1/level2/2025W18_1B/l2b-v27-2026-196/6/level2_2025W18_1B_0175_1D6_spx_l2b-v27-2026-196.fits?center=331.0764%2C-56.7865&size=0.1), [second](https://irsa.ipac.caltech.edu/ibe/data/spherex/dr1/level2/2025W24_1A/l2b-v27-2026-201/6/level2_2025W24_1A_0245_4D6_spx_l2b-v27-2026-201.fits?center=331.0764%2C-56.7865&size=0.1), and [third](https://irsa.ipac.caltech.edu/ibe/data/spherex/qr3/level2/2026W40_1A/l2b-v27-2026-276/6/level2_2026W40_1A_0070_2D6_spx_l2b-v27-2026-276.fits?center=331.0764%2C-56.7865&size=0.1) cutouts are directly traceable to NASA/IPAC IRSA. Full identifiers, quality checks, predictions, fitted positions, and URLs are in [`results/motion_validation.json`](results/motion_validation.json).

For the unresolved Ba/Bb system, the [10 pc Gaia-based catalog](https://gruze.org/10pc/) lists source 6412596012146801152 at epoch J2016.0, RA 331.076452596564°, Dec −56.7938120668822°, proper motion (+3981.9767, −2466.8318) mas/year in (RA cos Dec, Dec), and parallax 270.6580 mas. `api/motion_science.py` propagates this position with Astropy and subtracts Earth's barycentric position for annual parallax. The observer is approximated as geocentric; the additional low-Earth-orbit parallax is negligible at the adopted 0.5″ floor.

The measured first-to-last displacement is **6.485″ ± 0.731″**. The independent catalog prediction is **6.482″**. Their displacement vectors differ by **0.095″**, within the stated uncertainty. The conditional motion significance is **8.9σ** using the quadrature of formal Gaussian-fit position errors and a conservative 0.5″ per-epoch registration/astrometric floor. This is evidence for *known* Epsilon Indi B system motion, not a newly discovered object or separate Ba/Bb component orbit. The first fit has reduced χ² 3.54, showing the Gaussian is an imperfect effective-PSF model; this is why formal fit covariance alone is insufficient.

The source was fitted independently in each native FITS frame, without a catalog-position constraint in the fit. Frames were then reprojected onto the first frame's WCS for display, never shifted to hold the moving target fixed. A separate flux-moment centroid gives 6.442″ first-to-last displacement. One bright local stationary reference source shows 0.290″ apparent first-to-last drift. **Only one** sufficiently bright local reference was available; a broad multi-star registration validation and complete PSF/systematic error calibration remain open. The images therefore say **“Supported with limitations”**, not an absolute precision claim. The [SPHEREx explanatory supplement](https://irsa.ipac.caltech.edu/data/SPHEREx/docs/SPHEREx_Expsupp.pdf) documents FITS layers and astrometry flags.

Reproduce from a checkout with `pip install -r api/requirements-dev.txt`, then run `python api/explore_motion.py`, `python api/motion_science.py`, and `python api/analyze_motion.py` in that order. The first script uses the committed archive metadata snapshot (or queries IRSA if absent), the second examines candidate FITS at propagated target positions, and the third downloads the three selected FITS, fits centroids, checks the stationary source, and regenerates JSON and PNGs. The raw FITS cache is deliberately excluded from Git; the exact URLs are retained. Run `python -m pytest -q api/test_server.py api/test_motion.py tests/browser/test_viewer.py` after installing Chromium with `python -m playwright install chromium`.

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

## Additional field feasibility check (2026-11-15)

These candidate coordinates were checked with the live IRSA SIA2 records and two actual FITS cutouts per field. The names describe nearby test fields; no catalog source association or epoch-propagated target position has been established. SIA2 catalog band values are insufficient on their own: the FITS spectral WCS must be checked at the entered position.

| Candidate field (ICRS degrees) | SIA2 records | Cutouts checked | Target-position wavelengths | Quality and conclusion |
|---|---:|---|---|---|
| Barnard's Star field (269.4521, +4.6934) | 363 | 2025-08-15, 2026-09-20; D6 | 4.9155, 4.9997 µm | The entered pixels were unmasked in both sampled frames. This does not identify the star or establish its motion. A separate end-to-end search returned two usable D6 frames dated 2026-03-19 and 2026-08-16; it is a visual workflow check, not a detection. |
| Epsilon Indi B candidate field (331.0764, −56.7865) | 465 | 2025-04-24, 2026-09-28; D2 | 1.5584, 1.1377 µm | The sampled wavelengths differ by about 27%; the later entered pixel is masked. This pair is unsuitable for direct change analysis. The archive also returned a transient HTTP 503 during the first cutout attempt. |
| R Draconis field (248.1675, +66.7550) | 545 | 2025-06-06, 2026-07-06; D4 | 3.1691, 3.4183 µm | The sampled wavelengths differ by about 7%; the entered pixel is masked in both frames. This pair is unsuitable for direct change analysis. |

The checked [Barnard's Star first](https://irsa.ipac.caltech.edu/ibe/data/spherex/dr1/level2/2025W33_2C/l2b-v27-2026-228/6/level2_2025W33_2C_0321_1D6_spx_l2b-v27-2026-228.fits?center=269.4521%2C4.6934&size=0.1) and [last](https://irsa.ipac.caltech.edu/ibe/data/spherex/qr3/level2/2026W38_2A/l2b-v27-2026-264/6/level2_2026W38_2A_0562_1D6_spx_l2b-v27-2026-264.fits?center=269.4521%2C4.6934&size=0.1) FITS cutouts and [R Draconis first](https://irsa.ipac.caltech.edu/ibe/data/spherex/dr1/level2/2025W23_2B/l2b-v27-2026-201/4/level2_2025W23_2B_0206_1D4_spx_l2b-v27-2026-201.fits?center=248.1675%2C66.755&size=0.1) and [last](https://irsa.ipac.caltech.edu/ibe/data/spherex/qr3/level2/2026W28_1A/l2b-v27-2026-275/4/level2_2026W28_1A_0104_1D4_spx_l2b-v27-2026-275.fits?center=248.1675%2C66.755&size=0.1) FITS cutouts are directly traceable to IRSA. The API preserves the corresponding source URL for every returned frame. No additional preset was added because these checks do not establish a scientifically interpretable target change.

## Requirements for a future detection claim

1. Propagate the target's catalog position, proper motion, and parallax to each exposure time, then verify the source is detected at both positions. For a new object, cross-match against known catalogs and obtain follow-up observations.
2. Use clean observations or a validated PSF-fitting method that handles saturated cores and nearby sources. The present RW Aurigae pair does not pass this gate.
3. Compare measurements at the target-specific wavelengths with flux errors, fit quality, background, and all relevant pixel flags. Demonstrate a significant difference against stable comparison sources and the instrument's systematic uncertainty.
4. Retain the raw FITS URLs, observation IDs, processing versions, and analysis code so the result can be independently reproduced.

## Reproduction

Run `python validate_examples.py` with the four named FITS files beside the script. The script writes `Singularis-science-audit.json`. The JSON is the machine-readable record of this audit. This audit deliberately reports no flux significance or discovery probability because the necessary source association and quality gates have not passed.
