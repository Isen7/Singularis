"""Small SPHEREx cutout API for the Singularis static website."""
from __future__ import annotations

import base64
import io
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
from PIL import Image
from astropy.io import fits
from astropy.io.votable import parse_single_table
from astropy.time import Time
from astropy.wcs import WCS

ORIGIN = os.environ.get("SINGULARIS_ORIGIN", "https://isen7.github.io")
CACHE: dict[str, dict] = {}
LOCK = threading.Lock()


def fetch(url: str, limit: int = 18_000_000) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "Singularis/1.0 (SPHEREx public-data viewer)"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=35) as response:
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
        for row in table:
            url = str(row["access_url"])
            if not url.startswith("https://irsa.ipac.caltech.edu/ibe/data/spherex/") or "/level2/" not in url:
                continue
            rows.append({"url": url, "detector": str(row["energy_bandpassname"]), "time": float(row["t_min"]), "band": (float(row["em_min"]) + float(row["em_max"])) / 2, "collection": collection})
    return rows


def choose_pair(rows: list[dict]) -> tuple[dict, dict]:
    best = None
    score = -1e9
    for i, a in enumerate(rows):
        for b in rows[i + 1:]:
            days = abs(a["time"] - b["time"])
            if a["detector"] != b["detector"] or days < 30:
                continue
            wave_delta = abs(a["band"] - b["band"]) / max(a["band"], b["band"])
            if wave_delta > .035:
                continue
            candidate_score = min(days, 400) - wave_delta * 4000
            if candidate_score > score:
                best, score = (a, b), candidate_score
    if best is None:
        raise LookupError("No pair at comparable wavelengths and at least 30 days apart was found.")
    return tuple(sorted(best, key=lambda item: item["time"]))


def cutout(item: dict, ra: float, dec: float) -> dict:
    url = item["url"] + "?" + urllib.parse.urlencode({"center": f"{ra},{dec}", "size": "0.1"})
    with fits.open(io.BytesIO(fetch(url)), memmap=False) as hdus:
        image = np.asarray(hdus["IMAGE"].data, dtype=np.float32)
        zodi = np.asarray(hdus["ZODI"].data, dtype=np.float32)
        residual = image - zodi
        flags = np.asarray(hdus["FLAGS"].data)
        residual[flags != 0] = np.nan
        wcs = WCS(hdus["IMAGE"].header)
        date = hdus["IMAGE"].header.get("DATE-OBS") or Time(item["time"], format="mjd").isot
        return {"data": residual, "wcs": wcs, "date": str(date), "url": url, "detector": item["detector"], "collection": item["collection"]}


def align(second: dict, first: dict) -> np.ndarray:
    yy, xx = np.indices(first["data"].shape)
    ra, dec = first["wcs"].pixel_to_world_values(xx, yy)
    sx, sy = second["wcs"].world_to_pixel_values(ra, dec)
    x0 = np.floor(sx).astype(int)
    y0 = np.floor(sy).astype(int)
    data = second["data"]
    height, width = data.shape
    valid = (x0 >= 0) & (y0 >= 0) & (x0 + 1 < width) & (y0 + 1 < height)
    x = np.clip(x0, 0, width - 2)
    y = np.clip(y0, 0, height - 2)
    dx, dy = sx - x0, sy - y0
    out = (data[y, x] * (1 - dx) * (1 - dy) + data[y, x + 1] * dx * (1 - dy)
           + data[y + 1, x] * (1 - dx) * dy + data[y + 1, x + 1] * dx * dy)
    out[~valid] = np.nan
    return out


def render(data: np.ndarray, low: float, high: float) -> str:
    normalized = np.clip((data - low) / (high - low), 0, 1)
    pixels = np.uint8(255 * np.nan_to_num(np.arcsinh(6 * normalized) / np.arcsinh(6)))
    image = Image.fromarray(pixels, "L").resize((512, 512), Image.Resampling.BILINEAR)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")


def search(ra: float, dec: float) -> dict:
    key = f"{ra:.5f},{dec:.5f}"
    with LOCK:
        if key in CACHE:
            return CACHE[key]
    a, b = choose_pair(query(ra, dec))
    first, second = cutout(a, ra, dec), cutout(b, ra, dec)
    aligned = align(second, first)
    values = np.concatenate([arr[np.isfinite(arr)] for arr in (first["data"], aligned)])
    if len(values) < 100:
        raise LookupError("The selected pair has too few usable pixels.")
    low, high = np.percentile(values, [2, 99.3])
    if high <= low:
        raise LookupError("The selected images have no usable display range.")
    result = {"ra": ra, "dec": dec, "native_pixels": [int(first["data"].shape[1]), int(first["data"].shape[0])], "frames": [
        {"date": first["date"], "image": render(first["data"], low, high), "source": first["url"]},
        {"date": second["date"], "image": render(aligned, low, high), "source": second["url"]}],
        "detector": first["detector"], "collection": first["collection"],
        "warning": "Preliminary visual comparison only. Wavelength at the target, PSF, and photometric uncertainties require further validation."}
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
            if not np.isfinite(ra) or not np.isfinite(dec) or not 0 <= ra < 360 or not -90 <= dec <= 90:
                raise ValueError("RA must be 0–360 and Dec must be −90–90 degrees.")
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


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8000"))), Handler).serve_forever()
