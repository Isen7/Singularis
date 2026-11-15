"""Reproducible Epsilon Indi B astrometry and SPHEREx candidate inspection."""
from __future__ import annotations

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path

import numpy as np
from astropy import units as u
from astropy.coordinates import Distance, SkyCoord, get_body_barycentric
from astropy.time import Time

import server


ROOT = Path(__file__).resolve().parents[1]
FIELD = (331.0764, -56.7865)
CATALOG = {
    "target": "Epsilon Indi B (unresolved Ba/Bb system)",
    "source_id": "Gaia DR3 6412596012146801152",
    "reference_url": "https://gruze.org/10pc/",
    "reference_epoch_jyear": 2016.0,
    "ra_deg": 331.076452596564,
    "dec_deg": -56.7938120668822,
    "pm_ra_cosdec_mas_yr": 3981.97666296105,
    "pm_dec_mas_yr": -2466.83181476635,
    "parallax_mas": 270.658032469453,
    "pm_ra_error_mas_yr": 0.6016568,
    "pm_dec_error_mas_yr": 0.6256827,
    "parallax_error_mas": 0.6895573,
    "ra_error_mas": 0.5048,
    "dec_error_mas": 0.4676,
}


def predict(date: str | Time) -> SkyCoord:
    """Apply catalog proper motion and geocentric annual parallax."""
    epoch = date if isinstance(date, Time) else Time(date)
    origin = SkyCoord(
        ra=CATALOG["ra_deg"] * u.deg, dec=CATALOG["dec_deg"] * u.deg,
        distance=Distance(parallax=CATALOG["parallax_mas"] * u.mas),
        pm_ra_cosdec=CATALOG["pm_ra_cosdec_mas_yr"] * u.mas/u.yr,
        pm_dec=CATALOG["pm_dec_mas_yr"] * u.mas/u.yr,
        obstime=Time(CATALOG["reference_epoch_jyear"], format="jyear"),
    )
    barycentric = origin.apply_space_motion(new_obstime=epoch)
    observer = get_body_barycentric("earth", epoch)
    return SkyCoord(barycentric.cartesian.without_differentials() - observer, frame="icrs")


def inspect(item: dict) -> dict:
    date = Time(item["time"], format="mjd")
    target = predict(date)
    try:
        cutout = server.cutout(item, FIELD[0], FIELD[1], target=(target.ra.deg, target.dec.deg))
        x, y = cutout["target_pixel"]
        data = cutout["data"]
        yi, xi = np.indices(data.shape)
        aperture = (xi - x) ** 2 + (yi - y) ** 2 <= 3 ** 2
        valid = np.isfinite(data) & aperture
        cutout.update({
            "target_ra_deg": target.ra.deg, "target_dec_deg": target.dec.deg,
            "target_aperture_usable_fraction": float(valid.sum() / aperture.sum()),
            "target_aperture_peak": float(np.nanmax(data[valid])) if valid.any() else None,
        })
        for key in ("data", "wcs"):
            del cutout[key]
        return cutout
    except Exception as error:
        return {"url": item["url"], "detector": item["detector"],
                "date": date.isot, "error": str(error)}


def candidates(rows: list[dict]) -> list[dict]:
    groups = defaultdict(list)
    for item in rows:
        if item["detector"] not in ("SPHEREx-D5", "SPHEREx-D6"):
            continue
        month = Time(item["time"], format="mjd").isot[:7]
        groups[(item["detector"], month)].append(item)
    chosen = []
    for (detector, month), group in sorted(groups.items()):
        group.sort(key=lambda row: row["time"])
        for index in sorted({0, len(group)//2, len(group)-1}):
            chosen.append(group[index])
    return chosen


if __name__ == "__main__":
    rows = json.loads((ROOT / "results" / "epsilon_archive_metadata.json").read_text(encoding="utf-8"))
    selection = candidates(rows)
    print("Inspecting", len(selection), "candidate cutouts", flush=True)
    findings = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(inspect, item): item for item in selection}
        for future in as_completed(futures):
            finding = future.result()
            findings.append(finding)
            print(finding.get("date"), finding.get("detector"),
                  finding.get("wavelength_um"), finding.get("target_masked"),
                  finding.get("target_aperture_usable_fraction"), finding.get("error"), flush=True)
    findings.sort(key=lambda item: (item.get("detector", ""), item.get("date", "")))
    (ROOT / "results" / "epsilon_candidate_scan.json").write_text(json.dumps(findings, indent=2), encoding="utf-8")
