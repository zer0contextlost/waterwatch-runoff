# waterwatch: reviving USGS WaterWatch HUC runoff + n-day percentiles

Started 2026-11-04. USGS retired WaterWatch 2026-02-26. Its national products
(HUC2-8 runoff 1901-present; 7/14/28-day streamflow percentile maps) have no
replacement: USGS's own blog (waterdata.usgs.gov/blog/wdfn-stats-delivery/)
points users to per-site WDFN stats pages and a hyswap notebook that computes
runoff for a handful of HUC8s. WaterWatch's own runoff download stopped at WY2023.

Prior art (2026-11-04): colby-thrash/usgs-daily-streamflow-percentiles rebuilds
the n-day percentile maps for Missouri only ("short term solution"). Nothing
found for HUC runoff.

## Method
WaterWatch HUC runoff (Jian, Wolock & Lins 2008, FS 2008-3031; USGS catalog
"Water Watch HUC Runoff"): complete-water-year gages, basin area within 25% of
NWIS area, weight = prop_basin_in_huc * prop_huc_in_basin, weighted mean.
Basin/HUC intersections: hyswap example_data/huc_props_tbl_conus.csv (HUC8 only,
19,031 basins, 2,074 HUC8s). Delineated basin area = sum(prop_huc_in_basin *
WBD HUC8 areasqkm). Daily discharge: api.waterdata.usgs.gov OGC daily, 00060/00003.

src/fetch_dv.py   resumable batched fetch -> data/dv/wyA-B/bNNNN.parquet
src/huc_runoff.py WY HUC8 runoff, --method ww | hyswap | hybrid
src/validate.py   compare against WaterWatch's published values

## Validation, WY2008 HUC8 (vs WaterWatch download captured 2016-12-19, Wayback)
| method | HUC8s matched | r | median abs rel diff | within 5% | within 10% |
|---|---|---|---|---|---|
| ww (all overlaps)      | 1951/2038 | 0.983 | 6.2% | 46% | 60% |
| hyswap rules           | 1669/2038 | 0.990 | 2.5% | 61% | 71% |
| hybrid (hyswap, fallback to all overlaps) | 1951/2038 | 0.981 | 3.4% | 56% | 67% |
Bias ~0 in all. Big relative misses are near-zero-runoff arid HUCs (WW 0.004 mm
vs ours ~11 mm in the Upper Canadian 111001xx) and HUCs represented only by a
large downstream basin with tiny weight. Exact match isn't expected: WW's own
basin delineations aren't published, gage records were revised after 2016, and
the hyswap table is newer.

## Gotchas
- Keyless API: ~150 requests per rolling hour, then 429. fetch_dv waits 600 s.
  Set API_USGS_PAT, or point USGS_KEY_FILE at a file containing API_USGS_PAT=... .
- sites.parquet has USCE- duplicates of USGS site numbers; filter to USGS-.
- USGS legacy waterservices retire Nov 2026 - Feb 2027 (NWISWeb campaign 3);
  don't build on them.

## Validation data on hand
data/validation/ww_huc8_wy2008.tsv (all HUC8s + US total). Wayback also has
download/index.php?gt=map&ofmt=js&st=XX&mt=pa07d|pa14d|pa28d JSON (site classes),
e.g. CO 2026-02-11, for checking the n-day percentile piece.

## Full build (2026-11-04)
Pull: 381 batches, 476 MB (data/dv/wy1900-2027), ~5 h with key, 5 rate-limit pauses.
site_stats.py -> data/stats (15,107 sites with complete WYs; 15,877 with complete months).
huc_from_stats.py --method hybrid -> data/out/huc_runoff_{wy,month}.parquet
(HUC8 + HUC2/4/6 + US, WY 1900-2026, months 1899-10..2026-10; rank, n_years,
percentile, class). Monthly step must run per calendar year (OOM at 4 GB otherwise).
Percentile = (1 - rank/(n+1))*100, rank 1 wettest, classes 1 record low ... 8 record
high (inferred from WW's own file). Percentile/class blank when n_years < 10.

Validation of the full WY build vs WW WY2008: runoff r 0.98, median 3.4%;
percentile median gap 3.1 pts (r 0.91); class exact 76%, within one 97%.
US total WY2008 255 mm vs WW 246 mm.

First finding: WY2026 is 3rd driest US water year since 1951 on a fixed set of
1,919 HUC8s (after 1988, 1977). HUC2 03 (South Atlantic-Gulf) and 13 (Rio Grande)
at record lows; HUC 03 April 2026 lowest April in 127 years. Matches NWS JAX/FFC
drought statements (Santa Fe/Suwannee record lows, GA D4 2026-04-14) and NWS
Pueblo (record-low Rio Grande snowpack). WY2026 values are provisional data.
Caveat: US/rollup totals cover only HUC8s with values that period; early years
have far fewer HUC8s (785 in 1901), so compare long-run with a fixed set.

## Next
1. Daily 7/14/28-day gage percentiles (hyswap), validate vs Wayback JSON.
2. Publish dataset (GitHub+HF, zer0contextlost) + hub component + map page.
