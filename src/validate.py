"""Compare our HUC8 water-year runoff with WaterWatch's own published values.

usage: validate.py OURS.parquet WW.tsv WY
"""
import sys

import numpy as np
import pandas as pd

ours = pd.read_parquet(sys.argv[1])
ww = pd.read_csv(sys.argv[2], sep="\t", dtype={"region_cd": str}).rename(columns={"runoff(mm)": "runoff_mm"})
wy = int(sys.argv[3])
ww = ww[(ww.date == wy) & (ww.region_cd.str.len() == 8)]
m = ww.merge(ours[ours.wy == wy], left_on="region_cd", right_on="huc_id", how="left",
             suffixes=("_ww", "_ours"))
print(f"WaterWatch HUC8s: {len(ww)}; we have a value for {m.runoff_mm_ours.notna().sum()}")
m = m.dropna(subset=["runoff_mm_ours"])
m = m[m.runoff_mm_ww > 0]
rel = (m.runoff_mm_ours - m.runoff_mm_ww) / m.runoff_mm_ww
print(f"pearson r = {np.corrcoef(m.runoff_mm_ww, m.runoff_mm_ours)[0, 1]:.4f}")
print(f"log r     = {np.corrcoef(np.log1p(m.runoff_mm_ww), np.log1p(m.runoff_mm_ours))[0, 1]:.4f}")
print(f"median |rel diff| = {rel.abs().median():.3%}; median bias = {rel.median():+.3%}")
for tol in (0.01, 0.05, 0.10, 0.25):
    print(f"  within {tol:>4.0%}: {(rel.abs() <= tol).mean():.1%}")
w = m.assign(rel=rel).sort_values("rel", key=abs, ascending=False)
print("worst 10:")
print(w[["region_cd", "runoff_mm_ww", "runoff_mm_ours", "rel", "n_sites", "max_weight"]]
      .head(10).to_string(index=False))
