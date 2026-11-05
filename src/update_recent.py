"""Refresh the last DAYS days of daily discharge for every gage, in the same
50-site batches as the history store, into data/dv/recent/ (overwritten each run).

usage: update_recent.py [--days 45]
"""
import argparse
import datetime as dt
import time

import pandas as pd
from dataretrieval import waterdata

from fetch_dv import DV, all_sites, retry

BATCH = 50  # must match the history pull (fetch_dv.py ... --batch 50)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=45)
    a = ap.parse_args()
    end = dt.date.today()
    start = end - dt.timedelta(days=a.days)
    out = DV / "recent"
    tmp = DV / "recent.tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    sites = all_sites()
    nb = (len(sites) + BATCH - 1) // BATCH
    t0 = time.time()
    for b in range(nb):
        f = tmp / f"b{b:04d}.parquet"
        if f.exists():
            continue
        ids = ["USGS-" + s for s in sites[b * BATCH:(b + 1) * BATCH]]
        df, _ = retry(lambda: waterdata.get_daily(
            monitoring_location_id=ids, parameter_code="00060", statistic_id="00003",
            time=f"{start}/{end}",
            properties=["monitoring_location_id", "time", "value", "approval_status", "qualifier"],
            skip_geometry=True))
        if df.empty:
            df = pd.DataFrame(columns=["monitoring_location_id", "time", "value",
                                       "approval_status", "qualifier"])
        df["qualifier"] = df["qualifier"].astype(str)
        df.to_parquet(f)
        if (b + 1) % 50 == 0:
            print(f"batch {b + 1}/{nb} {time.time() - t0:.0f}s", flush=True)
    if out.exists():
        for p in out.glob("*"):
            p.unlink()
        out.rmdir()
    tmp.rename(out)
    print(f"recent {start}..{end} -> {out}", flush=True)


if __name__ == "__main__":
    main()
