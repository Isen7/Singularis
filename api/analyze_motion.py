"""Measure Epsilon Indi B positions in independently observed SPHEREx images."""
from __future__ import annotations

import base64
import json
from pathlib import Path

import numpy as np
from scipy.ndimage import maximum_filter
from scipy.optimize import least_squares
from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.time import Time
from astropy.wcs import WCS

import server
from motion_science import CATALOG, FIELD, ROOT, predict


SELECTED_DATES = ("2025-04-29T16:17", "2025-06-10T04:33", "2026-09-28T08:04")


def displacement_uncertainty(fit_errors_arcsec: list[float], registration_floor_arcsec: float) -> float:
    """Combine independent centroid errors with an astrometric floor per epoch."""
    if len(fit_errors_arcsec) != 2 or registration_floor_arcsec <= 0 or any(
        not np.isfinite(error) or error < 0 for error in fit_errors_arcsec
    ):
        raise ValueError("Two nonnegative fit errors and a positive registration floor are required")
    return float(np.sqrt(sum(error**2 for error in fit_errors_arcsec) + 2*registration_floor_arcsec**2))


def moment_source(frame: dict, position: SkyCoord) -> SkyCoord | None:
    """Independent local flux-weighted centroid check."""
    x0, y0 = map(float, frame["wcs"].world_to_pixel_values(position.ra.deg, position.dec.deg))
    yy, xx = np.indices(frame["data"].shape)
    distance2 = (xx - x0)**2 + (yy - y0)**2
    annulus = (distance2 >= 9) & (distance2 <= 25) & ~frame["bad"]
    core = (distance2 <= 6.25) & ~frame["bad"]
    if core.sum() < 8 or annulus.sum() < 15:
        return None
    level = np.median(frame["data"][annulus])
    weights = np.where(core, np.maximum(frame["data"] - level, 0), 0)
    if weights.sum() <= 0:
        return None
    x = float((xx * weights).sum() / weights.sum())
    y = float((yy * weights).sum() / weights.sum())
    ra, dec = frame["wcs"].pixel_to_world_values(x, y)
    return SkyCoord(float(ra) * u.deg, float(dec) * u.deg)


def fit_source(data: np.ndarray, variance: np.ndarray, bad: np.ndarray,
               x0: float, y0: float, radius: int = 4) -> dict | None:
    """Fit a local elliptical Gaussian and background without a positional prior."""
    height, width = data.shape
    xlo, xhi = max(0, int(round(x0)) - radius), min(width, int(round(x0)) + radius + 1)
    ylo, yhi = max(0, int(round(y0)) - radius), min(height, int(round(y0)) + radius + 1)
    if xhi - xlo < 7 or yhi - ylo < 7:
        return None
    yy, xx = np.mgrid[ylo:yhi, xlo:xhi]
    values = data[ylo:yhi, xlo:xhi]
    noise = np.sqrt(variance[ylo:yhi, xlo:xhi])
    valid = ~bad[ylo:yhi, xlo:xhi] & np.isfinite(values) & np.isfinite(noise) & (noise > 0)
    if valid.sum() < 35 or valid.sum() / valid.size < .8:
        return None
    background = float(np.median(values[valid]))
    weighted = np.where(valid, values - background, -np.inf)
    py, px = np.unravel_index(np.argmax(weighted), weighted.shape)
    peak_x, peak_y = float(xx[py, px]), float(yy[py, px])
    if np.hypot(peak_x - x0, peak_y - y0) > 2.5:
        return None
    amplitude = float(values[py, px] - background)
    if amplitude <= 0 or amplitude / noise[py, px] < 8:
        return None

    def residual(parameters):
        a, xc, yc, sx, sy, level = parameters
        model = level + a * np.exp(-.5 * (((xx - xc) / sx)**2 + ((yy - yc) / sy)**2))
        return ((model - values) / noise)[valid]

    initial = [amplitude, peak_x, peak_y, 0.9, 0.9, background]
    lower = [0, peak_x - 1.5, peak_y - 1.5, .45, .45, background - max(1, amplitude)]
    upper = [amplitude * 3, peak_x + 1.5, peak_y + 1.5, 2.5, 2.5, background + max(1, amplitude)]
    fit = least_squares(residual, initial, bounds=(lower, upper), max_nfev=200)
    if not fit.success:
        return None
    a, xc, yc, sx, sy, level = fit.x
    if not (.5 < sx < 2.4 and .5 < sy < 2.4):
        return None
    dof = max(1, valid.sum() - len(fit.x))
    reduced_chi2 = float(np.sum(fit.fun**2) / dof)
    try:
        covariance = np.linalg.inv(fit.jac.T @ fit.jac) * max(1, reduced_chi2)
        error_x, error_y = np.sqrt(np.diag(covariance)[1:3])
    except np.linalg.LinAlgError:
        return None
    return {"x": float(xc), "y": float(yc), "x_error_px": float(error_x),
            "y_error_px": float(error_y), "amplitude": float(a),
            "peak_snr": float(amplitude / noise[py, px]),
            "sigma_x_px": float(sx), "sigma_y_px": float(sy),
            "reduced_chi2": reduced_chi2, "valid_fraction": float(valid.mean())}


def load(item: dict) -> dict:
    path = ROOT / "results" / "cache" / Path(item["url"].split("?")[0]).name
    if not path.exists():
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(server.fetch(item["url"]))
    with fits.open(path, memmap=False) as hdus:
        image = np.asarray(hdus["IMAGE"].data, dtype=float)
        zodi = np.asarray(hdus["ZODI"].data, dtype=float)
        variance = np.asarray(hdus["VARIANCE"].data, dtype=float)
        flags_hdu = hdus["FLAGS"]
        flags = np.asarray(flags_hdu.data)
        finast = hdus["IMAGE"].header.get("FINAST")
        if finast != 0:
            raise ValueError(f"Rejected exposure with FINAST={finast}")
        bad_bits = sum(1 << int(key[4:]) for key, name in flags_hdu.header.items()
                       if key.startswith("MSKN") and name in server.BAD_VISUAL_FLAGS)
        bad = (flags & bad_bits) != 0
        return {"data": image-zodi, "variance": variance, "bad": bad,
                "wcs": WCS(hdus["IMAGE"].header), "date": item["date"],
                "url": item["url"], "detector": item["detector"],
                "wavelength_um": item["wavelength_um"],
                "observation_id": item["observation_id"],
                "processing_version": item["processing_version"], "finast": finast}


def measure(frame: dict, position: SkyCoord) -> dict | None:
    px, py = map(float, frame["wcs"].world_to_pixel_values(position.ra.deg, position.dec.deg))
    fit = fit_source(frame["data"], frame["variance"], frame["bad"], px, py)
    if fit is None:
        return None
    ra, dec = frame["wcs"].pixel_to_world_values(fit["x"], fit["y"])
    return {**fit, "ra_deg": float(ra), "dec_deg": float(dec),
            "predicted_x": px, "predicted_y": py,
            "predicted_ra_deg": float(position.ra.deg),
            "predicted_dec_deg": float(position.dec.deg)}


def background_sources(reference: dict, others: list[dict], target: SkyCoord) -> list[dict]:
    data = reference["data"]
    peaks = (data == maximum_filter(data, size=5)) & (data > 0.3) & ~reference["bad"]
    points = np.argwhere(peaks)
    calibrators = []
    for py, px in points:
        if min(px, py, data.shape[1]-1-px, data.shape[0]-1-py) < 5:
            continue
        world = SkyCoord(*reference["wcs"].pixel_to_world_values(float(px), float(py)), unit="deg")
        if world.separation(target).arcsec < 25:
            continue
        anchor = fit_source(reference["data"], reference["variance"], reference["bad"], float(px), float(py))
        if anchor is None:
            continue
        anchor_world = SkyCoord(*reference["wcs"].pixel_to_world_values(anchor["x"], anchor["y"]), unit="deg")
        matches = []
        for frame in others:
            x, y = map(float, frame["wcs"].world_to_pixel_values(anchor_world.ra.deg, anchor_world.dec.deg))
            match = fit_source(frame["data"], frame["variance"], frame["bad"], x, y)
            if match:
                actual = SkyCoord(*frame["wcs"].pixel_to_world_values(match["x"], match["y"]), unit="deg")
                east, north = anchor_world.spherical_offsets_to(actual)
                matches.append({"date": frame["date"], "east_arcsec": east.arcsec,
                                "north_arcsec": north.arcsec, "peak_snr": match["peak_snr"]})
        if len(matches) >= 2:
            calibrators.append({"reference_ra_deg": anchor_world.ra.deg,
                                "reference_dec_deg": anchor_world.dec.deg, "matches": matches})
    return calibrators


def run() -> dict:
    scan = json.loads((ROOT / "results" / "epsilon_candidate_scan.json").read_text(encoding="utf-8"))
    selected = [next(item for item in scan if item.get("date", "").startswith(date)
                     and item.get("detector") == "SPHEREx-D6" and item.get("wavelength_um")
                     and 4.63 < item["wavelength_um"] < 4.68) for date in SELECTED_DATES]
    frames = [load(item) for item in selected]
    measurements = []
    moments = []
    aligned = []
    for frame in frames:
        predicted = predict(Time(frame["date"]))
        measured = measure(frame, predicted)
        moment = moment_source(frame, predicted)
        moments.append(moment)
        aligned.append(frame["data"] if frame is frames[0] else server.align(frame, frames[0]))
        measurements.append({"date": frame["date"], "wavelength_um": frame["wavelength_um"],
                             "url": frame["url"], "detector": frame["detector"],
                             "observation_id": frame["observation_id"],
                             "processing_version": frame["processing_version"],
                             "predicted_ra_deg": float(predicted.ra.deg),
                             "predicted_dec_deg": float(predicted.dec.deg), "finast": frame["finast"],
                             "measured": measured})
    calibrators = background_sources(frames[0], frames[1:], predict(Time(frames[0]["date"])))
    if any(item["measured"] is None for item in measurements):
        raise ValueError("At least one target centroid is unreliable")
    values = np.concatenate([image[np.isfinite(image)] for image in aligned])
    low, high = np.percentile(values, [2, 99.5])
    for index, (item, image) in enumerate(zip(measurements, aligned), 1):
        image_name = f"epsilon_indi_b_frame_{index}.png"
        encoded = server.render(image, low, high, None).split(",", 1)[1]
        (ROOT / "results" / image_name).write_bytes(base64.b64decode(encoded))
        item["image"] = f"./results/{image_name}"
        item["masked_fraction"] = float(np.mean(frames[index-1]["bad"]))
        item["usable_fraction"] = float(np.isfinite(image).mean())
        predicted = SkyCoord(item["predicted_ra_deg"] * u.deg, item["predicted_dec_deg"] * u.deg)
        measured = item["measured"]
        predicted_x, predicted_y = map(float, frames[0]["wcs"].world_to_pixel_values(predicted.ra.deg, predicted.dec.deg))
        measured_x, measured_y = map(float, frames[0]["wcs"].world_to_pixel_values(measured["ra_deg"], measured["dec_deg"]))
        item["predicted_pixel_aligned"] = [predicted_x, predicted_y]
        item["measured_pixel_aligned"] = [measured_x, measured_y]

    first, last = measurements[0], measurements[-1]
    first_pred = SkyCoord(first["predicted_ra_deg"] * u.deg, first["predicted_dec_deg"] * u.deg)
    last_pred = SkyCoord(last["predicted_ra_deg"] * u.deg, last["predicted_dec_deg"] * u.deg)
    first_meas = SkyCoord(first["measured"]["ra_deg"] * u.deg, first["measured"]["dec_deg"] * u.deg)
    last_meas = SkyCoord(last["measured"]["ra_deg"] * u.deg, last["measured"]["dec_deg"] * u.deg)
    pred_east, pred_north = first_pred.spherical_offsets_to(last_pred)
    obs_east, obs_north = first_meas.spherical_offsets_to(last_meas)
    observed = first_meas.separation(last_meas).arcsec
    predicted = first_pred.separation(last_pred).arcsec
    scale = np.linalg.norm(frames[0]["wcs"].pixel_scale_matrix, axis=0) * 3600
    for item in measurements:
        fit_radial = float(np.hypot(item["measured"]["x_error_px"] * scale[0],
                                    item["measured"]["y_error_px"] * scale[1]))
        item["fit_position_uncertainty_arcsec"] = fit_radial
        item["position_uncertainty_arcsec"] = float(np.hypot(fit_radial, 0.5))
    fit_errors = [float(np.hypot(item["measured"]["x_error_px"] * scale[0],
                                 item["measured"]["y_error_px"] * scale[1]))
                  for item in (first, last)]
    registration_floor = 0.5  # Conservative per-epoch floor in arcseconds.
    displacement_error = displacement_uncertainty(fit_errors, registration_floor)
    reference_drift = None
    if calibrators:
        latest = next((match for match in calibrators[0]["matches"] if match["date"] == last["date"]), None)
        if latest:
            reference_drift = float(np.hypot(latest["east_arcsec"], latest["north_arcsec"]))
    moment_displacement = (float(moments[0].separation(moments[-1]).arcsec)
                           if moments[0] is not None and moments[-1] is not None else None)
    vector_disagreement = float(np.hypot(obs_east.arcsec-pred_east.arcsec,
                                         obs_north.arcsec-pred_north.arcsec))
    checks = {
        "independent_epochs": len({item["observation_id"] for item in measurements}) >= 3,
        "target_wavelength_range_under_0_1_percent":
            (max(item["wavelength_um"] for item in measurements) - min(item["wavelength_um"] for item in measurements))
            / np.mean([item["wavelength_um"] for item in measurements]) < .001,
        "all_finast_good": all(item["finast"] == 0 for item in measurements),
        "target_snr_over_20": all(item["measured"]["peak_snr"] > 20 for item in measurements),
        "stationary_source_drift_under_0_5_arcsec": reference_drift is not None and reference_drift < .5,
        "independent_centroid_displacement_within_0_5_arcsec":
            moment_displacement is not None and abs(moment_displacement - observed) < .5,
        "observed_predicted_vector_difference_within_two_sigma": vector_disagreement < 2*displacement_error,
    }
    checks = {name: bool(passed) for name, passed in checks.items()}
    result = {"target": CATALOG["target"], "catalog": CATALOG,
              "field_ra_deg": FIELD[0], "field_dec_deg": FIELD[1],
              "native_pixels": list(frames[0]["data"].shape[::-1]),
              "frames": measurements, "background_calibrators": calibrators,
              "observed_displacement_arcsec": float(observed),
              "predicted_displacement_arcsec": float(predicted),
              "observed_displacement_uncertainty_arcsec": displacement_error,
              "motion_significance_sigma": float(observed/displacement_error),
              "observed_predicted_vector_difference_arcsec": vector_disagreement,
              "stationary_source_drift_arcsec": reference_drift,
              "moment_centroid_displacement_arcsec": moment_displacement,
              "uncertainty_model": "Quadrature of Gaussian-fit covariance and a conservative 0.5 arcsec per-epoch astrometric/registration floor; binary orbital acceleration and PSF modeling are not fully quantified.",
              "quality_checks": checks,
              "quality_status": "Supported with limitations" if all(checks.values()) else "Inconclusive",
              "conclusion": "The unresolved Epsilon Indi B source moves relative to the background in three SPHEREx D6 epochs at matched wavelengths, consistent with catalog proper motion and parallax under the stated uncertainty model." if all(checks.values()) else "The candidate motion remains inconclusive because one or more validation checks failed.",
              "limitations": ["Only one bright stationary source was available for a direct local registration check.",
                              "A Gaussian is an approximation to the SPHEREx effective PSF.",
                              "The Ba/Bb binary is unresolved; component motion is not measured separately.",
                              "Geocentric annual parallax approximates the SPHEREx observer; low-Earth-orbit parallax is negligible at this precision."],
              "source_documentation": "https://irsa.ipac.caltech.edu/data/SPHEREx/docs/SPHEREx_Expsupp.pdf"}
    (ROOT / "results" / "motion_validation.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    outcome = run()
    for frame in outcome["frames"]:
        measured = frame["measured"]
        print(frame["date"], frame["wavelength_um"],
              None if measured is None else (measured["ra_deg"], measured["dec_deg"], measured["peak_snr"], measured["reduced_chi2"]))
    print("background calibrators", len(outcome["background_calibrators"]))
