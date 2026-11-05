"""Reduce daily discharge to per-site water-year and calendar-month runoff (mm),
keeping only complete periods (every day present), one batch file at a time.

usage: site_stats.py DV_DIR OUT_DIR
writes OUT_DIR/site_wy.parquet and OUT_DIR/site_month.parquet
(columns: site_no, period, runoff_mm; period = WY int or 'YYYY-MM')
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SITES = ROOT / "data/sites.parquet"
HUC_AREA = ROOT / "data/huc8_area.parquet"
TABLE = ROOT / "ref/hyswap/example_notebooks/example_data/huc_props_tbl_conus.csv"
CFS_TO_M3S = 0.028316846592
SQMI_TO_KM2 = 2.58998811
AREA_TOL = 0.25


def site_areas():
    """NWIS drainage area for sites whose delineated basin is within 25% of it
    (WaterWatch step 1). Delineated = sum(prop_huc_in_basin * WBD HUC8 area)."""
    info = pd.read_parquet(SITES)
    info = info[info.monitoring_location_id.str.startswith("USGS-")]
    area = info.set_index("monitoring_location_number").drainage_area * SQMI_TO_KM2
    t = pd.read_csv(TABLE, dtype={"da_site_no": str, "huc_id": str}, index_col=0)
    harea = pd.read_parquet(HUC_AREA).drop_duplicates("huc8").set_index("huc8").areasqkm
    delin = (t.prop_huc_in_basin * t.huc_id.map(harea)).groupby(t.da_site_no).sum()
    ok = (delin.reindex(area.index) / area - 1).abs() <= AREA_TOL
    return area[ok & (area > 0)]


def reduce(df, key, ndays):
    g = df.groupby(["site_no", key]).value.agg(["mean", "count"]).reset_index()
    g["ndays"] = ndays(g[key])
    g = g[g["count"] == g.ndays]
    return g.rename(columns={key: "period"})[["site_no", "period", "mean", "ndays"]]


def main():
    dv, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    area = site_areas()
    wy_parts, mo_parts = [], []
    files = sorted(dv.glob("*.parquet"))
    for i, f in enumerate(files):
        df = pd.read_parquet(f, columns=["monitoring_location_id", "time", "value"]).dropna()
        if df.empty:
            continue
        df["site_no"] = df.monitoring_location_id.str.split("-", n=1).str[-1]
        df = df[df.site_no.isin(area.index)]
        t = pd.to_datetime(df.time)
        df["wy"] = t.dt.year + (t.dt.month >= 10)
        df["mo"] = t.dt.strftime("%Y-%m")
        wy_parts.append(reduce(df, "wy", lambda s: np.where(
            pd.to_datetime(s.astype(str) + "-02-28").dt.is_leap_year, 366, 365)))
        mo_parts.append(reduce(df, "mo", lambda s: pd.to_datetime(s + "-01").dt.days_in_month))
        if (i + 1) % 50 == 0:
            print(f"{i + 1}/{len(files)}", flush=True)
    for name, parts in (("site_wy", wy_parts), ("site_month", mo_parts)):
        g = pd.concat(parts, ignore_index=True)
        a = g.site_no.map(area)
        g["runoff_mm"] = g["mean"] * CFS_TO_M3S * 86400 * g.ndays / (a * 1e6) * 1000
        g[["site_no", "period", "runoff_mm"]].to_parquet(out / f"{name}.parquet")
        print(f"{name}: {len(g)} rows, {g.site_no.nunique()} sites", flush=True)


if __name__ == "__main__":
    main()
