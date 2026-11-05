"""Fetch USGS daily mean discharge (00060/00003) for every gage in the hyswap
huc-basin intersection table, plus drainage areas.

Writes one parquet per (water-year range, site batch) under data/dv/, skipping
batches that already exist, so a killed run resumes where it stopped.

usage: fetch_dv.py WY_START WY_END [--batch 200]
"""
import argparse
import sys
import os
import time
from pathlib import Path

import pandas as pd
from dataretrieval import waterdata

ROOT = Path(__file__).resolve().parent.parent
# optional: file with API_USGS_PAT=... (or set API_USGS_PAT directly)
KEY = Path(os.environ.get("USGS_KEY_FILE", "usgs_waterdata.env"))
if KEY.exists() and "API_USGS_PAT" not in os.environ:
    os.environ["API_USGS_PAT"] = KEY.read_text().strip().split("=", 1)[-1]
TABLE = ROOT / "ref/hyswap/example_notebooks/example_data/huc_props_tbl_conus.csv"
DV = ROOT / "data/dv"
SITES = ROOT / "data/sites.parquet"


def all_sites():
    t = pd.read_csv(TABLE, dtype=str, index_col=0)
    return sorted(t.da_site_no.unique())


def fetch_site_info(sites, batch):
    if SITES.exists():
        return
    parts = []
    for i in range(0, len(sites), batch):
        df, _ = waterdata.get_monitoring_locations(
            monitoring_location_number=sites[i:i + batch],
            properties=["monitoring_location_id", "monitoring_location_number",
                        "drainage_area", "contributing_drainage_area"],
            skip_geometry=True)
        parts.append(df)
    pd.concat(parts).to_parquet(SITES)


def retry(fn, tries=12):
    # keyless api.waterdata.usgs.gov allows ~150 requests per rolling hour;
    # on 429 wait for the window instead of hammering it
    for n in range(tries):
        try:
            return fn()
        except Exception as e:  # network / 429 / 5xx
            limited = "429" in str(e)
            wait = 600 if limited else 30 * (n + 1)
            print(f"  {'rate limited' if limited else repr(e)[:200]}, retry in {wait}s",
                  flush=True)
            time.sleep(wait)
    raise RuntimeError("giving up")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wy_start", type=int)
    ap.add_argument("wy_end", type=int)
    ap.add_argument("--batch", type=int, default=200)
    a = ap.parse_args()

    sites = all_sites()
    fetch_site_info(sites, a.batch)
    out = DV / f"wy{a.wy_start}-{a.wy_end}"
    out.mkdir(parents=True, exist_ok=True)
    span = f"{a.wy_start - 1}-10-01/{a.wy_end}-09-30"
    nb = (len(sites) + a.batch - 1) // a.batch
    t0 = time.time()
    for b in range(nb):
        f = out / f"b{b:04d}.parquet"
        if f.exists():
            continue
        ids = ["USGS-" + s for s in sites[b * a.batch:(b + 1) * a.batch]]
        df, _ = retry(lambda: waterdata.get_daily(
            monitoring_location_id=ids, parameter_code="00060",
            statistic_id="00003", time=span,
            properties=["monitoring_location_id", "time", "value",
                        "approval_status", "qualifier"],
            skip_geometry=True))
        if df.empty:
            df = pd.DataFrame(columns=["monitoring_location_id", "time", "value",
                                       "approval_status", "qualifier"])
        df["qualifier"] = df["qualifier"].astype(str)
        df.to_parquet(f.with_suffix(".tmp"))
        f.with_suffix(".tmp").rename(f)
        print(f"batch {b + 1}/{nb}: {len(df)} rows, "
              f"{df.monitoring_location_id.nunique()} sites, "
              f"{time.time() - t0:.0f}s", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    sys.exit(main())
