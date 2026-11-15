"""Investigate candidate SPHEREx epochs and catalog astrometry."""
from collections import Counter
import csv
import io
import json
from pathlib import Path
import urllib.parse
import urllib.request

from astropy.time import Time

import server


ROOT = Path(__file__).resolve().parents[1]


def tap(query: str) -> list[dict]:
    params = urllib.parse.urlencode({"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "csv", "QUERY": query})
    with urllib.request.urlopen("https://irsa.ipac.caltech.edu/TAP/sync?" + params, timeout=50) as response:
        return list(csv.DictReader(io.StringIO(response.read().decode())))


if __name__ == "__main__":
    metadata_path = ROOT / "results" / "epsilon_archive_metadata.json"
    rows = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else server.query(331.0764, -56.7865)
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "epsilon_archive_metadata.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print("Records:", len(rows), Counter((x["detector"], x["collection"]) for x in rows), flush=True)
    try:
        print("Gaia tables:", tap("SELECT table_name FROM TAP_SCHEMA.tables WHERE table_name LIKE '%gaia%'"), flush=True)
    except Exception as error:
        print("Gaia TAP unavailable:", error, flush=True)
    for detector in sorted({x["detector"] for x in rows}):
        subset = [x for x in rows if x["detector"] == detector]
        dates = sorted({Time(x["time"], format="mjd").isot[:10] for x in subset})
        print(detector, len(subset), dates, flush=True)
