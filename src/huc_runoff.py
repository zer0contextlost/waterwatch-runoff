"""Water-year HUC8 runoff from gage daily discharge, WaterWatch method
(Jian, Wolock & Lins 2008; USGS catalog "Water Watch HUC Runoff"):

1. per water year, keep gages with a complete daily record;
2. basin runoff = mean daily flow / drainage area (uniform over basin);
3. weight = prop_basin_in_huc * prop_huc_in_basin;
4. HUC runoff = weighted mean over all overlapping basins.

hyswap's calculate_geometric_runoff adds two rules on top, both optional here:
a single basin with weight > 0.81 is used alone ("tight"), and with
clip=True only basins inside the HUC plus the smallest basin containing it
are kept.

usage: huc_runoff.py DV_DIR OUT.parquet [--method ww|hyswap]
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
TABLE = ROOT / "ref/hyswap/example_notebooks/example_data/huc_props_tbl_conus.csv"
SITES = ROOT / "data/sites.parquet"
HUC_AREA = ROOT / "data/huc8_area.parquet"
AREA_TOL = 0.25
CFS_TO_M3S = 0.028316846592
SQMI_TO_KM2 = 2.58998811


def load_dv(dv_dir):
    df = pd.concat(pd.read_parquet(f, columns=["monitoring_location_id", "time", "value"])
                   for f in sorted(Path(dv_dir).glob("*.parquet")))
    df["site_no"] = df.monitoring_location_id.str.split("-", n=1).str[-1]
    df["time"] = pd.to_datetime(df.time)
    df["wy"] = df.time.dt.year + (df.time.dt.month >= 10)
    return df.dropna(subset=["value"])


def site_wy_runoff(df):
    """Annual runoff (mm) per site and water year, complete years only."""
    g = df.groupby(["site_no", "wy"]).value.agg(["mean", "count"]).reset_index()
    g["ndays"] = np.where(pd.to_datetime(g.wy.astype(str) + "-02-28").dt.is_leap_year, 366, 365)
    g = g[g["count"] == g.ndays].copy()
    info = pd.read_parquet(SITES)
    info = info[info.monitoring_location_id.str.startswith("USGS-")]
    area = info.set_index("monitoring_location_number").drainage_area * SQMI_TO_KM2
    g["area_km2"] = g.site_no.map(area)
    g = g[g.area_km2 > 0]
    # WaterWatch step 1: drop gages whose delineated basin area is not within
    # 25% of the NWIS drainage area. Delineated area = sum over HUCs of
    # prop_huc_in_basin * HUC area (WBD areasqkm).
    t = pd.read_csv(TABLE, dtype={"da_site_no": str, "huc_id": str}, index_col=0)
    harea = pd.read_parquet(HUC_AREA).drop_duplicates("huc8").set_index("huc8").areasqkm
    t["a"] = t.prop_huc_in_basin * t.huc_id.map(harea)
    delin = t.groupby("da_site_no").a.sum()
    g["delin_km2"] = g.site_no.map(delin)
    g = g[(g.delin_km2 / g.area_km2 - 1).abs() <= AREA_TOL]
    # mm over the year = m3/s * s / m2 * 1000
    g["runoff_mm"] = g["mean"] * CFS_TO_M3S * 86400 * g.ndays / (g.area_km2 * 1e6) * 1000
    return g[["site_no", "wy", "runoff_mm"]]


def huc_runoff(ro, method="ww", tight=0.81, full=0.98):
    t = pd.read_csv(TABLE, dtype={"da_site_no": str, "huc_id": str}, index_col=0)
    t["weight"] = t.prop_basin_in_huc * t.prop_huc_in_basin
    m = ro.merge(t, left_on="site_no", right_on="da_site_no")
    if method in ("hyswap", "hybrid"):
        # rule a: one tightly-overlapping basin is used alone
        m["is_tight"] = m.weight > tight
        has_tight = m.groupby(["huc_id", "wy"]).is_tight.transform("any")
        best = m[m.is_tight].sort_values("weight").groupby(["huc_id", "wy"]).tail(1)
        rest = m[~has_tight]
        # rule b: basins inside the huc + smallest basin containing it
        inside = rest[rest.prop_basin_in_huc > full]
        cont = rest[rest.prop_huc_in_basin > full].sort_values("weight") \
            .groupby(["huc_id", "wy"]).tail(1)
        sel = pd.concat([best, inside, cont]).drop_duplicates(["huc_id", "wy", "site_no"])
        if method == "hybrid":
            # hucs with no tight/inside/containing basin fall back to all overlaps
            done = sel.set_index(["huc_id", "wy"]).index
            left = m[~m.set_index(["huc_id", "wy"]).index.isin(done)]
            sel = pd.concat([sel, left])
        m = sel
    m["wr"] = m.weight * m.runoff_mm
    g = m.groupby(["huc_id", "wy"]).agg(wr=("wr", "sum"), w=("weight", "sum"),
                                       n_sites=("site_no", "size"),
                                       max_weight=("weight", "max"))
    g = g[g.w > 0]
    g["runoff_mm"] = g.wr / g.w
    return g[["runoff_mm", "n_sites", "max_weight"]].reset_index()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dv_dir")
    ap.add_argument("out")
    ap.add_argument("--method", default="ww", choices=["ww", "hyswap", "hybrid"])
    a = ap.parse_args()
    ro = site_wy_runoff(load_dv(a.dv_dir))
    print(f"{ro.site_no.nunique()} sites with complete water years")
    h = huc_runoff(ro, a.method)
    h.to_parquet(a.out)
    print(f"{h.huc_id.nunique()} HUC8s, {h.wy.nunique()} water years -> {a.out}")


if __name__ == "__main__":
    main()
