"""n-day average streamflow percentiles per gage, WaterWatch style (pa07d/pa14d/pa28d).

For a date D and window n: the n-day mean flow ending on D is ranked against the
n-day means ending on the same day of year in every other year of the gage's
record. Gages with fewer than 30 such years are not ranked (WaterWatch rule).
Percentile = Weibull plotting position among historical values; classes follow
WaterWatch's map codes: 1 below the historical minimum ("Low"), 3 <10,
4 10-24, 5 25-75, 6 76-90, 7 >90, 8 above the maximum ("High"), 0 not ranked.
(WaterWatch also used code 2 for "<10"; its split from 3 isn't documented, so we use 3.)

usage: nday.py DV_DIR OUT.parquet DATE [DATE ...] [--n 7 14 28] [--sites FILE] [--recent DIR]
DATE may be "latest" (the most recent day with data in --recent).
With --recent, values from DIR/bNNNN.parquet replace history for the same site and day.
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

MIN_YEARS = 30


def classify(p, lo, hi):
    c = np.select([p < 10, p < 25, p <= 75, p <= 90], [3, 4, 5, 6], 7)
    c = np.where(lo, 1, c)
    return np.where(hi, 8, c)


def site_percentiles(s, dates, windows):
    """s: daily Series for one site indexed by date (gaps allowed)."""
    s = s.asfreq("D")
    md = s.index.strftime("%m-%d")
    yr = s.index.year
    masks = {d: (md == d.strftime("%m-%d")) & (yr != d.year) for d in dates}
    out = []
    for n in windows:
        r = s.rolling(n, min_periods=n).mean()
        for d in dates:
            if d not in r.index or np.isnan(r.loc[d]):
                continue
            v = r.loc[d]
            hist = r[masks[d]].dropna()
            n_yrs = len(hist)
            row = dict(date=d, n_day=n, q_cfs=round(v, 4), n_years=n_yrs)
            if n_yrs >= MIN_YEARS:
                below = (hist < v).sum() + 0.5 * (hist == v).sum()
                pct = 100 * (below + 0.5) / (n_yrs + 1)
                med = hist.median()
                # record flags only when strictly beyond every past value, so
                # zero-flow ties on ephemeral streams rank by mid-rank instead
                row.update(percentile=round(pct, 2),
                           pct_of_median=round(100 * v / med, 2) if med > 0 else np.nan,
                           cls=int(classify(np.array([pct]), v < hist.min(), v > hist.max())[0]))
            else:
                row.update(percentile=np.nan, pct_of_median=np.nan, cls=0)
            out.append(row)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dv_dir")
    ap.add_argument("out")
    ap.add_argument("dates", nargs="+")
    ap.add_argument("--n", nargs="+", type=int, default=[7, 14, 28])
    ap.add_argument("--sites", help="file with one site number per line")
    ap.add_argument("--recent", help="dir of recent batches overriding history")
    a = ap.parse_args()
    if a.dates == ["latest"]:
        last = max(pd.read_parquet(f, columns=["time"]).time.max()
                   for f in Path(a.recent).glob("*.parquet") if pd.read_parquet(f, columns=["time"]).size)
        # the last day is often partial across gages; use the day before it
        a.dates = [str((pd.to_datetime(last) - pd.Timedelta(days=1)).date())]
        print("latest ->", a.dates[0], flush=True)
    dates = pd.to_datetime(a.dates)
    want = set(open(a.sites).read().split()) if a.sites else None
    rows = []
    files = sorted(Path(a.dv_dir).glob("*.parquet"))
    for i, f in enumerate(files):
        df = pd.read_parquet(f, columns=["monitoring_location_id", "time", "value"]).dropna()
        if a.recent and (Path(a.recent) / f.name).exists():
            rec = pd.read_parquet(Path(a.recent) / f.name,
                                  columns=["monitoring_location_id", "time", "value"]).dropna()
            if not rec.empty:
                key = rec.monitoring_location_id + "|" + rec.time.astype(str)
                old = df.monitoring_location_id + "|" + df.time.astype(str)
                df = pd.concat([df[~old.isin(set(key))], rec], ignore_index=True)
        if df.empty:
            continue
        df["site_no"] = df.monitoring_location_id.str.split("-", n=1).str[-1]
        if want is not None:
            df = df[df.site_no.isin(want)]
        df["time"] = pd.to_datetime(df.time)
        # a few gages carry two daily series; average same-day values
        df = df.groupby(["site_no", "time"], as_index=False).value.mean()
        for site, g in df.groupby("site_no"):
            for r in site_percentiles(g.set_index("time").value.sort_index(), dates, a.n):
                rows.append(dict(site_no=site, **r))
        if (i + 1) % 50 == 0:
            print(f"{i + 1}/{len(files)} files, {len(rows)} rows", flush=True)
    pd.DataFrame(rows).to_parquet(a.out, index=False)
    print(f"{len(rows)} rows -> {a.out}", flush=True)


if __name__ == "__main__":
    main()
