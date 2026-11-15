"""Small SPHEREx cutout API for the Singularis static website."""
from __future__ import annotations

import base64
import io
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
from PIL import Image, ImageDraw
from astropy.io import fits
from astropy.io.votable import parse_single_table
from astropy.time import Time
from astropy.wcs import WCS
from reproject import reproject_interp

ORIGIN = os.environ.get("SINGULARIS_ORIGIN", "https://isen7.github.io")
CACHE: dict[str, dict] = {}
LOCK = threading.Lock()
BAD_VISUAL_FLAGS = {
    "TRANSIENT", "OVERFLOW", "SUR_ERROR", "NONFUNC", "DICHROIC",
    "MISSING_DATA", "HOT", "COLD", "NONLINEAR", "PERSIST",
    "OUTLIER", "CROSSTALK", "GHOST", "GHOST_FPA", "GHOST_EXT",
    "STREAK", "BLOOM", "SNOWBALL", "HALO",
}


def processing_version(url: str) -> str:
    match = re.search(r"/([^/]*l2b[^/]*-v[^/]+)/", url)
    return match.group(1) if match else "Unknown"


def fetch(url: str, limit: int = 18_000_000) -> bytes:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != "irsa.ipac.caltech.edu" or not (
        parsed.path == "/SIA" or parsed.path.startswith("/ibe/data/spherex/")
    ):
        raise ValueError("The archive URL is not an approved IRSA endpoint.")
    request = urllib.request.Request(url, headers={"User-Agent": "Singularis/1.0 (SPHEREx public-data viewer)"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=35) as response:
                if urllib.parse.urlsplit(response.geturl()).hostname != "irsa.ipac.caltech.edu":
                    raise ValueError("The archive redirected outside IRSA.")
                data = response.read(limit + 1)
            break
        except urllib.error.HTTPError as error:
            if error.code not in (429, 502, 503, 504) or attempt == 2:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
        time.sleep(1.5 * (attempt + 1))
    if len(data) > limit:
        raise ValueError("The archive response exceeded the size limit.")
    return data


def query(ra: float, dec: float) -> list[dict]:
    rows = []
    for collection in ("spherex_dr1", "spherex_qr3"):
        params = urllib.parse.urlencode({"COLLECTION": collection, "POS": f"circle {ra} {dec} 0.005"})
        table = parse_single_table(io.BytesIO(fetch("https://irsa.ipac.caltech.edu/SIA?" + params, 5_000_000))).to_table(use_names_over_ids=True)
        if len(table) > 2000:
            raise ValueError("Too many archive records cover this position; narrow the archive query.")
        for row in table:
            url = str(row["access_url"])
            if not url.startswith("https://irsa.ipac.caltech.edu/ibe/data/spherex/") or "/level2/" not in url:
                continue
            rows.append({"url": url, "detector": str(row["energy_bandpassname"]), "time": float(row["t_min"]), "band": (float(row["em_min"]) + float(row["em_max"])) / 2, "collection": collection})
    return rows


def choose_frames(rows: list[dict], maximum: int = 5) -> list[dict]:
    """Find a wavelength-matched time series with one visit per 30-day window."""
    best: list[dict] = []
    best_score = (-1, -1.0)
    for anchor in rows:
        matches = sorted(
            (row for row in rows if row["detector"] == anchor["detector"]
             and abs(row["band"] - anchor["band"]) / max(row["band"], anchor["band"]) <= .035),
            key=lambda row: (row["time"], abs(row["band"] - anchor["band"])),
        )
        visits: list[dict] = []
        for row in matches:
            if not visits or row["time"] - visits[-1]["time"] >= 30:
                visits.append(row)
        if len(visits) > maximum:
            indices = np.linspace(0, len(visits) - 1, maximum).round().astype(int)
            visits = [visits[index] for index in indices]
        score = (len(visits), visits[-1]["time"] - visits[0]["time"] if visits else 0)
        if score > best_score:
            best, best_score = visits, score
    if len(best) < 2:
        raise LookupError("No repeat observations at comparable wavelengths and at least 30 days apart were found.")
    return best


def cutout(item: dict, ra: float, dec: float) -> dict:
    url = item["url"] + "?" + urllib.parse.urlencode({"center": f"{ra},{dec}", "size": "0.1"})
    with fits.open(io.BytesIO(fetch(url)), memmap=False) as hdus:
        image = np.asarray(hdus["IMAGE"].data, dtype=np.float32)
        zodi = np.asarray(hdus["ZODI"].data, dtype=np.float32)
        if image.ndim != 2 or image.shape != zodi.shape or image.shape != hdus["FLAGS"].data.shape:
            raise ValueError("The archive cutout has inconsistent image layers.")
        if str(hdus["IMAGE"].header.get("BUNIT", "")).replace(" ", "").lower() != "mjy/sr":
            raise ValueError("The archive cutout has unexpected image units.")
        residual = image - zodi
        flags_hdu = hdus["FLAGS"]
        flags = np.asarray(flags_hdu.data)
        bad_bits = sum(
            1 << int(key[4:])
            for key, name in flags_hdu.header.items()
            if key.startswith("MSKN") and name in BAD_VISUAL_FLAGS
        )
        if bad_bits == 0:
            raise ValueError("The archive cutout lacks recognizable quality-flag metadata.")
        residual[(flags & bad_bits) != 0] = np.nan
        wcs = WCS(hdus["IMAGE"].header)
        x, y = map(float, wcs.world_to_pixel_values(ra, dec))
        if not np.isfinite([x, y]).all() or not (0 <= x < image.shape[1] and 0 <= y < image.shape[0]):
            raise ValueError("The requested position is outside the archive cutout.")
        pixel_x = int(np.clip(round(x), 0, image.shape[1] - 1))
        pixel_y = int(np.clip(round(y), 0, image.shape[0] - 1))
        target_masked = bool(flags[pixel_y, pixel_x] & bad_bits)
        spectral = WCS(hdus["IMAGE"].header, fobj=hdus, key="W")
        spectral.sip = None
        wavelength, bandwidth = spectral.pixel_to_world(x, y)
        date = hdus["IMAGE"].header.get("DATE-OBS") or Time(item["time"], format="mjd").isot
        return {"data": residual, "wcs": wcs, "date": str(date), "url": url,
                "detector": item["detector"], "collection": item["collection"],
                "wavelength_um": float(wavelength.value), "bandwidth_um": float(bandwidth.value),
                "masked_fraction": float(np.mean((flags & bad_bits) != 0)),
                "target_masked": target_masked,
                "observation_id": str(hdus["IMAGE"].header.get("OBSID", "Unknown")),
                "processing_version": processing_version(item["url"])}


def align(frame: dict, reference: dict) -> np.ndarray:
    data, footprint = reproject_interp(
        (frame["data"], frame["wcs"]), reference["wcs"],
        shape_out=reference["data"].shape, order="bilinear",
    )
    data[footprint <= 0] = np.nan
    return data


def render(data: np.ndarray, low: float, high: float, marker: tuple[float, float]) -> str:
    normalized = np.clip((data - low) / (high - low), 0, 1)
    pixels = np.uint8(255 * np.nan_to_num(np.arcsinh(6 * normalized) / np.arcsinh(6)))
    image = Image.fromarray(pixels, "L").resize((512, 512), Image.Resampling.BILINEAR).convert("RGB")
    x = marker[0] * 512 / data.shape[1]
    y = marker[1] * 512 / data.shape[0]
    draw = ImageDraw.Draw(image)
    for start, end in [((x - 12, y), (x - 4, y)), ((x + 4, y), (x + 12, y)),
                       ((x, y - 12), (x, y - 4)), ((x, y + 4), (x, y + 12))]:
        draw.line((start, end), fill=(235, 222, 45), width=2)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")


def render_difference(earlier: np.ndarray, later: np.ndarray) -> str | None:
    valid = np.isfinite(earlier) & np.isfinite(later)
    if valid.mean() < 0.6:
        return None
    difference = (later - np.median(later[valid])) - (earlier - np.median(earlier[valid]))
    scale = float(np.percentile(np.abs(difference[valid]), 99))
    if not np.isfinite(scale) or scale <= 0:
        return None
    gray = np.uint8(127.5 + 127.5 * np.clip(np.nan_to_num(difference) / scale, -1, 1))
    rgb = np.repeat(gray[:, :, None], 3, axis=2)
    rgb[~valid] = (235, 222, 45)  # Yellow denotes unusable overlap, not signal.
    image = Image.fromarray(rgb, "RGB").resize((512, 512), Image.Resampling.NEAREST)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")


def search(ra: float, dec: float) -> dict:
    key = f"{ra:.5f},{dec:.5f}"
    with LOCK:
        if key in CACHE:
            return CACHE[key]
    selected = choose_frames(query(ra, dec))
    first = None
    frames = []
    for item in selected:
        try:
            frame = cutout(item, ra, dec)
            if np.isfinite(frame["data"]).mean() < 0.6:
                continue
            if first is None:
                first = frame
                frames.append((frame, frame["data"]))
                continue
            if abs(frame["wavelength_um"] - first["wavelength_um"]) / max(frame["wavelength_um"], first["wavelength_um"]) > .035:
                continue
            aligned = align(frame, first)
            if np.isfinite(aligned).mean() >= 0.6:
                frames.append((frame, aligned))
        except (LookupError, ValueError, KeyError, OSError):
            continue
    if len(frames) < 2:
        raise LookupError("The selected observations have insufficient usable overlap.")
    values = np.concatenate([arr[np.isfinite(arr)] for _, arr in frames])
    if len(values) < 100:
        raise LookupError("The selected pair has too few usable pixels.")
    low, high = np.percentile(values, [2, 99.3])
    if high <= low:
        raise LookupError("The selected images have no usable display range.")
    marker = tuple(map(float, first["wcs"].world_to_pixel_values(ra, dec)))
    result = {"ra": ra, "dec": dec, "native_pixels": [int(first["data"].shape[1]), int(first["data"].shape[0])], "frames": [
        {"date": frame["date"], "image": render(data, low, high, marker), "source": frame["url"],
         "collection": frame["collection"], "wavelength_um": frame["wavelength_um"],
         "bandwidth_um": frame["bandwidth_um"], "masked_fraction": frame["masked_fraction"],
         "usable_fraction": float(np.isfinite(data).mean()), "target_masked": frame.get("target_masked", False),
         "observation_id": frame["observation_id"], "processing_version": frame["processing_version"],
         "detector": frame["detector"]}
        for frame, data in frames],
        "detector": first["detector"], "collection": first["collection"],
        "difference": render_difference(frames[0][1], frames[-1][1]),
        "warning": "Preliminary visual comparison only. Different PSFs, masked pixels, and photometric uncertainties can mimic change; no target motion or variability is confirmed."}
    with LOCK:
        if len(CACHE) > 20:
            CACHE.clear()
        CACHE[key] = result
    return result


class Handler(BaseHTTPRequestHandler):
    def send_json(self, code: int, payload: dict) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", ORIGIN)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        path = urllib.parse.urlsplit(self.path)
        if path.path == "/health":
            return self.send_json(200, {"ok": True})
        if path.path != "/api/search":
            return self.send_json(404, {"error": "Not found"})
        try:
            params = urllib.parse.parse_qs(path.query)
            ra, dec = float(params["ra"][0]), float(params["dec"][0])
            validate_coordinates(ra, dec)
            return self.send_json(200, search(ra, dec))
        except (KeyError, IndexError, ValueError) as error:
            return self.send_json(400, {"error": str(error)})
        except LookupError as error:
            return self.send_json(404, {"error": str(error)})
        except Exception:
            self.log_exception()
            return self.send_json(502, {"error": "The SPHEREx archive could not be processed right now."})

    def log_exception(self) -> None:
        import traceback
        traceback.print_exc(file=sys.stderr)


def validate_coordinates(ra: float, dec: float) -> None:
    if not np.isfinite(ra) or not np.isfinite(dec) or not 0 <= ra < 360 or not -90 <= dec <= 90:
        raise ValueError("RA must be 0–360 and Dec must be −90–90 degrees.")


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8000"))), Handler).serve_forever()
