"""Assemble the public release tree from data/out.

usage: build_release.py OUT_DIR
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(sys.argv[1])
(OUT / "data").mkdir(parents=True, exist_ok=True)

names = pd.read_parquet(ROOT / "data/huc_names.parquet")[["huc_id", "name", "states"]]
names = pd.concat([names, pd.DataFrame([{"huc_id": "US", "name": "Conterminous US",
                                          "states": None}])])
COLS = ["level", "huc_id", "name", "states", "PERIOD", "runoff_mm", "rank", "n_years",
        "percentile", "class", "n_sites", "max_weight"]

for name, key in (("wy", "wy"), ("month", "month")):
    d = pd.read_parquet(ROOT / f"data/out/huc_runoff_{name}.parquet").merge(
        names, on="huc_id", how="left")
    d["n_sites"] = d.n_sites.astype("Int32")
    d["max_weight"] = d.max_weight.round(4)
    d = d[[c.replace("PERIOD", key) for c in COLS]]
    d.to_parquet(OUT / f"data/huc_runoff_{name}.parquet", index=False)
    if name == "wy":
        d.to_csv(OUT / "data/huc_runoff_wy.csv.gz", index=False)
    print(name, len(d))

site = pd.read_parquet(ROOT / "data/stats/site_wy.parquet").rename(columns={"period": "wy"})
site["runoff_mm"] = site.runoff_mm.round(3)
site.to_parquet(OUT / "data/site_runoff_wy.parquet", index=False)

# validation table against WaterWatch's own WY2008 download
ww = pd.read_csv(ROOT / "data/validation/ww_huc8_wy2008.tsv", sep="\t",
                 dtype={"region_cd": str}).rename(columns={
    "region_cd": "huc_id", "runoff(mm)": "ww_runoff_mm", "rank": "ww_rank",
    "percentile": "ww_percentile", "class": "ww_class"}).drop(columns="date")
ours = pd.read_parquet(ROOT / "data/out/huc_runoff_wy.parquet")
ours = ours[ours.wy == 2008][["huc_id", "runoff_mm", "percentile", "class"]]
v = ww.merge(ours, on="huc_id", how="left")
v.to_csv(OUT / "data/validation_wy2008_vs_waterwatch.csv", index=False)

# fixed-set national series 1951+ (HUC8s with a value every year)
h8 = ours_all = pd.read_parquet(ROOT / "data/out/huc_runoff_wy.parquet")
h8 = h8[h8.level == "8"]
area = pd.read_parquet(ROOT / "data/huc8_area.parquet").drop_duplicates("huc8") \
    .set_index("huc8").areasqkm
p = h8.pivot(index="wy", columns="huc_id", values="runoff_mm").loc[1951:]
full = p.dropna(axis=1)
a = area.reindex(full.columns)
us = ((full * a).sum(1) / a.sum()).rename("runoff_mm").reset_index()
us["rank_driest"] = us.runoff_mm.rank().astype(int)
us["n_huc8"] = full.shape[1]
us.round(3).to_csv(OUT / "data/us_fixed_set_wy1951.csv", index=False)
print("fixed set", full.shape[1], "HUC8s")
