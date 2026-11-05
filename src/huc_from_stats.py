"""HUC runoff for every water year and month from site_stats output, with
WaterWatch-style ranks, percentiles and classes, plus HUC2/4/6 and US rollups.

Percentile (WaterWatch convention, inferred from its own download): rank 1 =
wettest; percentile = (1 - rank / (n + 1)) * 100 over all periods on record
(months ranked against the same calendar month). Classes: 1 record low,
2 <5, 3 5-10, 4 10-25, 5 25-75, 6 75-90, 7 >90, 8 record high.

HUC2/4/6 and US are area-weighted means of their HUC8s (WaterWatch computed
those levels from their own basin intersections; ours is an approximation).

usage: huc_from_stats.py STATS_DIR OUT_DIR [--method hybrid]
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from huc_runoff import huc_runoff, HUC_AREA

MIN_YEARS = 10


def rank_pct(df, group):
    df = df[np.isfinite(df.runoff_mm)].copy()
    g = df.groupby(group).runoff_mm
    df["n_years"] = g.transform("size")
    df["rank"] = g.rank(ascending=False, method="min").astype(int)
    df["percentile"] = ((1 - df["rank"] / (df.n_years + 1)) * 100).round(2)
    p = df.percentile
    cls = np.select([p < 5, p < 10, p < 25, p <= 75, p <= 90], [2, 3, 4, 5, 6], 7)
    cls = np.where(df["rank"] == df.n_years, 1, cls)
    cls = np.where(df["rank"] == 1, 8, cls)
    df["class"] = cls
    short = df.n_years < MIN_YEARS
    df.loc[short, ["percentile"]] = np.nan
    df.loc[short, "class"] = 0
    return df


def rollups(h8, key):
    area = pd.read_parquet(HUC_AREA).drop_duplicates("huc8").set_index("huc8").areasqkm
    h8 = h8.assign(a=h8.huc_id.map(area)).dropna(subset=["a"])
    out = []
    for lvl in (2, 4, 6):
        x = h8.assign(huc_id=h8.huc_id.str[:lvl], ar=h8.runoff_mm * h8.a)
        g = x.groupby(["huc_id", key]).agg(ar=("ar", "sum"), a=("a", "sum")).reset_index()
        g["runoff_mm"] = g.ar / g.a
        out.append(g[["huc_id", key, "runoff_mm"]])
    x = h8.assign(ar=h8.runoff_mm * h8.a)
    g = x.groupby(key).agg(ar=("ar", "sum"), a=("a", "sum")).reset_index()
    g["huc_id"] = "US"
    g["runoff_mm"] = g.ar / g.a
    out.append(g[["huc_id", key, "runoff_mm"]])
    return pd.concat(out, ignore_index=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stats_dir")
    ap.add_argument("out_dir")
    ap.add_argument("--method", default="hybrid", choices=["ww", "hyswap", "hybrid"])
    a = ap.parse_args()
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name, key in (("wy", "wy"), ("month", "month")):
        s = pd.read_parquet(Path(a.stats_dir) / f"site_{name}.parquet")
        s = s.rename(columns={"period": "wy"})
        if key == "month":
            # one calendar year at a time keeps the site x huc join small
            yr = s.wy.str[:4]
            h8 = pd.concat([huc_runoff(c, a.method) for _, c in s.groupby(yr)],
                           ignore_index=True)
        else:
            h8 = huc_runoff(s, a.method)
        h8 = h8.rename(columns={"wy": key})
        del s
        allh = pd.concat([h8, rollups(h8, key)], ignore_index=True)
        allh["level"] = allh.huc_id.where(allh.huc_id == "US", allh.huc_id.str.len().astype(str))
        if key == "month":
            allh["cal_month"] = allh.month.str[5:]
            allh = rank_pct(allh, ["huc_id", "cal_month"]).drop(columns="cal_month")
        else:
            allh = rank_pct(allh, ["huc_id"])
        allh["runoff_mm"] = allh.runoff_mm.round(3)
        allh = allh.sort_values(["level", "huc_id", key])
        allh.to_parquet(out / f"huc_runoff_{name}.parquet", index=False)
        print(f"{name}: {len(allh)} rows; HUC8s {h8.huc_id.nunique()}; "
              f"{allh[key].min()}..{allh[key].max()}", flush=True)


if __name__ == "__main__":
    main()
