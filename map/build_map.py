"""Build the public gage map (docs/) from an nday output parquet.

usage: build_map.py NDAY.parquet DOCS_DIR
writes DOCS_DIR/latest.json, DOCS_DIR/latest.csv, DOCS_DIR/index.html, DOCS_DIR/status.json
"""
import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
nd = pd.read_parquet(sys.argv[1])
docs = Path(sys.argv[2])
docs.mkdir(parents=True, exist_ok=True)
geo = pd.read_parquet(ROOT / "data/sites_geo.parquet")
FIPS = dict(x.split(":") for x in "01:AL 02:AK 04:AZ 05:AR 06:CA 08:CO 09:CT 10:DE 11:DC 12:FL 13:GA 15:HI 16:ID 17:IL 18:IN 19:IA 20:KS 21:KY 22:LA 23:ME 24:MD 25:MA 26:MI 27:MN 28:MS 29:MO 30:MT 31:NE 32:NV 33:NH 34:NJ 35:NM 36:NY 37:NC 38:ND 39:OH 40:OK 41:OR 42:PA 44:RI 45:SC 46:SD 47:TN 48:TX 49:UT 50:VT 51:VA 53:WA 54:WV 55:WI 56:WY 72:PR".split())
geo["state"] = geo.state.map(FIPS)
date = str(pd.to_datetime(nd.date).max().date())
nd = nd[pd.to_datetime(nd.date) == pd.to_datetime(date)]

wide = nd.pivot_table(index="site_no", columns="n_day", values=["cls", "percentile", "q_cfs"],
                      aggfunc="first")
wide.columns = [f"{a}{b}" for a, b in wide.columns]
d = wide.reset_index().merge(geo, on="site_no").dropna(subset=["lat", "lon"])
for n in (7, 14, 28):
    if f"cls{n}" not in d:
        d[f"cls{n}"] = 0
    d[f"cls{n}"] = d[f"cls{n}"].fillna(0).astype(int)

# compact columnar json: [site, name, state, lat, lon, cls7, cls14, cls28, pct7, pct14, pct28, q7, q14, q28]
cols = ["site_no", "name", "state", "lat", "lon"] + [f"cls{n}" for n in (7, 14, 28)] + \
       [f"percentile{n}" for n in (7, 14, 28)] + [f"q_cfs{n}" for n in (7, 14, 28)]
for c in cols:
    if c not in d:
        d[c] = None
rows = d[cols].astype(object).where(d[cols].notna(), None)
rows["lat"] = rows.lat.map(lambda v: round(v, 4))
rows["lon"] = rows.lon.map(lambda v: round(v, 4))
data = {"date": date, "rows": rows.values.tolist()}
(docs / "latest.json").write_text(json.dumps(data, separators=(",", ":")))
d[cols].to_csv(docs / "latest.csv", index=False)

counts = {str(n): d[f"cls{n}"].value_counts().reindex(range(9), fill_value=0).tolist()
          for n in (7, 14, 28)}
ranked7 = int((d.cls7 > 0).sum())
status = {"name": "waterwatch-runoff gage map", "ok": True, "date": date,
          "gages": int(len(d)), "ranked_7day": ranked7,
          "below_normal_7day_pct": round(100 * d.cls7.isin([1, 2, 3, 4]).sum() / max(ranked7, 1), 1)}
(docs / "status.json").write_text(json.dumps(status))
html = (HERE / "template.html").read_text().replace("__COUNTS__", json.dumps(counts))
(docs / "index.html").write_text(html)
print(status)
