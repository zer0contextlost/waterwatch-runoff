# waterwatch-runoff: US watershed runoff 1900-2026, continuing USGS WaterWatch

Monthly and water-year runoff for every gaged HUC8 watershed in the conterminous US, plus
HUC2/4/6 regions and a national total, computed from USGS streamgage records with the method
USGS WaterWatch used. Each value carries WaterWatch's rank, percentile and condition class.
Version 1, November 2026.

Data: [huggingface.co/datasets/zer0contextlost/waterwatch-runoff](https://huggingface.co/datasets/zer0contextlost/waterwatch-runoff) · Code and notes: [github.com/zer0contextlost/waterwatch-runoff](https://github.com/zer0contextlost/waterwatch-runoff)

Not affiliated with or endorsed by the U.S. Geological Survey.

## Why this exists

USGS retired WaterWatch on 2026-02-26. Its HUC runoff maps and tables (monthly, quarterly and
annual runoff for every hydrologic unit back to 1901) went with it. The replacement pages on
Water Data for the Nation give statistics per streamgage; for watershed runoff USGS points users to
an example notebook in its `hyswap` package that computes it for a handful of HUC8s. WaterWatch's
own runoff download had already stopped at water year 2023.

The gages still report every day. This dataset runs the calculation for all of them.

## Method

Following WaterWatch (Jian, Wolock & Lins 2008, USGS Fact Sheet 2008-3031, and the USGS catalog
entry "Water Watch HUC Runoff"):

1. For each water year (or calendar month), keep streamgages with a complete daily record, and only
   gages whose delineated basin area is within 25% of the NWIS drainage area.
2. Basin runoff = mean daily flow / drainage area, assumed uniform over the basin.
3. Weight each basin-HUC pair by (share of basin in the HUC) x (share of HUC in the basin).
4. HUC runoff = weighted mean over overlapping basins.

Basin-HUC intersections come from the table USGS ships with `hyswap`
(`huc_props_tbl_conus.csv`, 19,031 gaged basins, 2,074 HUC8s). Daily discharge (parameter 00060,
daily mean) comes from the USGS Water Data API. Where one basin covers a HUC almost exactly
(weight > 0.81) it is used alone; otherwise basins inside the HUC plus the smallest basin containing
it are used, as `hyswap` does, falling back to all overlapping basins when neither exists.

HUC2/4/6 and the national total are area-weighted means of their HUC8 values. WaterWatch built
those levels from its own basin intersections, so ours are an approximation at those levels.

Rank 1 is the wettest period on record. Percentile = (1 - rank/(n+1)) x 100 over all periods with
a value (months ranked against the same calendar month), which is the convention in WaterWatch's
own download. Classes: 1 record low, 2 below 5th, 3 5th-10th, 4 10th-25th, 5 25th-75th, 6 75th-90th,
7 above 90th, 8 record high. Percentile and class are blank where a HUC has fewer than 10 periods.

## Validation

Compared with WaterWatch's published water-year 2008 HUC8 runoff (its download as archived by the
Internet Archive on 2016-12-19), for 1,951 of its 2,038 HUC8s:

| | value |
|---|---|
| runoff correlation | 0.98 |
| median absolute difference | 3.4% |
| median bias | +0.1% |
| within 5% / 10% / 25% | 56% / 67% / 79% |
| percentile, median gap | 3.1 points |
| class, exact / within one | 76% / 97% |
| US total, WY2008 | 255 mm (WaterWatch 246 mm) |

The largest relative misses are near-zero-runoff HUCs in the arid West and HUCs represented only by
a large downstream basin. An exact match isn't possible: WaterWatch's own basin delineations were
not published, gage records have been revised since 2016, and the `hyswap` table is newer.
Per-HUC comparison: `data/validation_wy2008_vs_waterwatch.csv`.

## Water year 2026

Water year 2026 (October 2025 to September 2026) was the third driest since 1951 for the
conterminous US, on a fixed set of 1,919 HUC8s with values every year: 182 mm, after 1988 (172 mm)
and 1977 (177 mm). Series: `data/us_fixed_set_wy1951.csv`.

| HUC2 | region | runoff mm | rank (1 = wettest) | percentile |
|---|---|---|---|---|
| 03 | South Atlantic-Gulf | 210 | 127 of 127 | 0.8 |
| 13 | Rio Grande | 7 | 127 of 127 | 0.8 |
| 14 | Upper Colorado | 38 | 125 of 127 | 2.3 |
| 02 | Mid Atlantic | 301 | 122 of 127 | 4.7 |
| 08 | Lower Mississippi | 215 | 121 of 127 | 5.5 |
| 01 | New England | 435 | 120 of 127 | 6.2 |
| 06 | Tennessee | 354 | 117 of 127 | 8.6 |
| 04 | Great Lakes | 357 | 51 of 127 | 60.2 |

April 2026 was the lowest April on record for the South Atlantic-Gulf region. This is consistent
with NWS drought statements from the spring (record-low flows on the Santa Fe River and near-record
lows on the Suwannee; Georgia in D4 drought from 2026-04-14) and with record-low Upper Rio Grande
snowpack. 2026 values use provisional USGS data and will move as records are approved.

## Files

| file | rows | contents |
|---|---|---|
| `data/huc_runoff_wy.parquet` (+ `.csv.gz`) | 293,042 | water years 1900-2026, HUC8/6/4/2 and US |
| `data/huc_runoff_month.parquet` | 3,552,991 | months 1899-10 to 2026-10 |
| `data/site_runoff_wy.parquet` | 508,907 | per-gage water-year runoff used as input |
| `data/us_fixed_set_wy1951.csv` | 76 | national series on a fixed HUC8 set |
| `data/validation_wy2008_vs_waterwatch.csv` | 2,039 | per-HUC comparison with WaterWatch |

Columns: `level` (2/4/6/8/US), `huc_id`, `name`, `states` (WBD), `wy` or `month`, `runoff_mm`,
`rank`, `n_years`, `percentile`, `class`, `n_sites` and `max_weight` (HUC8 only: gages used and the
largest single weight).

## Caveats

- Rollups and the US total average only HUC8s that have a value in that period. Early years have far
  fewer (785 HUC8s in 1901, about 2,000 since 1950), so use a fixed HUC8 set for long-run comparisons.
- Values before 1930 rest on a sparse gage network; WaterWatch carried the same warning.
- Runoff here is gaged streamflow per unit area. Regulated rivers (reservoirs, diversions) are included
  as measured, as in WaterWatch.
- Conterminous US only. Alaska, Hawaii and Puerto Rico are not in the `hyswap` intersection table.

## Reproduce

Clone [DOI-USGS/hyswap](https://github.com/DOI-USGS/hyswap) into `ref/hyswap` (for the intersection table) and run `src/fetch_wbd.py` (HUC names and areas). `src/fetch_dv.py 1900 2027` pulls daily discharge for all gages in the intersection table (a free
USGS Water Data API key makes this hours instead of days); `src/site_stats.py` reduces it to complete
periods; `src/huc_from_stats.py --method hybrid` builds the HUC tables; `src/validate.py` compares
with WaterWatch. Details in [NOTES.md](NOTES.md).

## License

Code: MIT. Data: CC BY 4.0. Inputs are USGS public-domain data.
