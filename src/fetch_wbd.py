"""Fetch WBD HUC names, states and areas (HUC2/4/6/8) from the USGS National Map
service -> data/huc_names.parquet and data/huc8_area.parquet."""
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
URL = "https://hydro.nationalmap.gov/arcgis/rest/services/wbd/MapServer/{}/query"

rows = []
for layer, field in ((1, "huc2"), (2, "huc4"), (3, "huc6"), (4, "huc8")):
    off = 0
    while True:
        r = requests.get(URL.format(layer), timeout=120, params=dict(
            where="1=1", outFields=f"{field},name,states,areasqkm", returnGeometry="false",
            f="json", resultOffset=off, resultRecordCount=1000)).json()
        feats = r.get("features", [])
        rows += [dict(huc_id=x["attributes"][field], name=x["attributes"]["name"],
                      states=x["attributes"].get("states"),
                      area_km2=x["attributes"]["areasqkm"]) for x in feats]
        if not feats or not r.get("exceededTransferLimit"):
            break
        off += len(feats)
d = pd.DataFrame(rows).drop_duplicates("huc_id")
d.to_parquet(ROOT / "data/huc_names.parquet")
h8 = d[d.huc_id.str.len() == 8].rename(columns={"huc_id": "huc8", "area_km2": "areasqkm"})
h8[["huc8", "areasqkm"]].to_parquet(ROOT / "data/huc8_area.parquet")
print(d.huc_id.str.len().value_counts().to_dict())
