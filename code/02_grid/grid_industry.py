"""Commerce and manufacturing shares of employees from the SGIS 1 km industry grid, for the 100 m frame.

SGIS gives employees by KSIC 2-digit industry only on the 1 km grid (2000, 2005, 2010, 2015, 2019, 2020, 2024);
the 100 m grid has the total only. Each 1 km cell's share of employees in
  comm    도소매 + 숙박·음식 (KSIC 8th: 50-52, 55; 9th/10th: 45-47, 55-56)
  manuf   제조업          (KSIC 8th: 15-37; 9th: 10-33; 10th: 10-34)
is stored at 1 km; a 100 m cell's commerce employees = its total employees x the share of its 1 km cell
(industry mix assumed even inside a 1 km cell). Shares use the listed (non-suppressed) values; a 0 in the CSV is a
suppressed small value and is left out of both numerator and denominator.
Revision by year: 2000, 2005 = 8th; 2010, 2015 = 9th; 2019, 2020, 2024 = 10th.

Output: data_work/grid100/ind_share.npz   per year `y{year}_comm`, `y{year}_manuf` (float32, 1 km rows x cols,
        row 0 at the top) and `y{year}_emp1k` (listed employees per 1 km cell), plus x0k, ytopk (km of the 1 km
        array's left / top edge) and the 100 m -> 1 km row / column maps `r1k`, `c1k`.
Run with ArcGIS Pro Python:  propy.bat code\\02_grid\\grid_industry.py
"""
import glob
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths
from grid_sgis import LETTERS, frame

sys.stdout.reconfigure(encoding="utf-8")
GRID = os.path.join(paths.WORK, "grid100")
SRC = os.path.join(paths.SGIS, "grid_industry", "csv")
NAME = re.compile(r"^(\d{4})년_종사자중분류_([가-힣]{2})_1K\.csv$")
REV = {2000: 8, 2005: 8, 2010: 9, 2015: 9, 2019: 10, 2020: 10, 2024: 10}
COMM = {8: {50, 51, 52, 55}, 9: {45, 46, 47, 55, 56}, 10: {45, 46, 47, 55, 56}}
MANUF = {8: set(range(15, 38)), 9: set(range(10, 34)), 10: set(range(10, 35))}


def main():
    x0, y0, nrow, ncol = frame()
    ytop = y0 + nrow * 100
    x0k, ytopk = x0 // 1000, -(-ytop // 1000)  # 1 km array covers the frame
    ncolk = -(-(x0 + ncol * 100) // 1000) - x0k
    nrowk = ytopk - y0 // 1000
    out = {"x0k": x0k, "ytopk": ytopk,
           "c1k": ((x0 + np.arange(ncol) * 100) // 1000 - x0k).astype(np.int32),
           "r1k": (ytopk - 1 - (ytop - 100 - np.arange(nrow) * 100) // 1000).astype(np.int32)}
    files = {}
    for f in glob.glob(os.path.join(SRC, "*_1K.csv")):
        m = NAME.match(os.path.basename(f))
        if m:
            files.setdefault(int(m.group(1)), []).append((f, m.group(2)))
    for year in sorted(files):
        rev = REV[year]
        tot = np.zeros((nrowk, ncolk), np.float64)
        com = np.zeros_like(tot)
        man = np.zeros_like(tot)
        for f, sheet in files[year]:
            sx = 700 + LETTERS.index(sheet[0]) * 100
            sy = 1300 + LETTERS.index(sheet[1]) * 100
            with open(f, encoding="cp949") as fh:
                for line in fh:
                    p = line.rstrip("\n").split(",")
                    if len(p) < 4 or not p[2].startswith("cp2_bem_"):
                        continue
                    v = float(p[3])
                    if v <= 0:
                        continue
                    xk, yk = sx + int(p[1][2:4]), sy + int(p[1][4:6])
                    c, r = xk - x0k, ytopk - 1 - yk
                    if not (0 <= r < nrowk and 0 <= c < ncolk):
                        continue
                    k = int(p[2][8:])
                    tot[r, c] += v
                    if k in COMM[rev]:
                        com[r, c] += v
                    if k in MANUF[rev]:
                        man[r, c] += v
        with np.errstate(invalid="ignore", divide="ignore"):
            out[f"y{year}_comm"] = np.where(tot > 0, com / tot, np.nan).astype(np.float32)
            out[f"y{year}_manuf"] = np.where(tot > 0, man / tot, np.nan).astype(np.float32)
        out[f"y{year}_emp1k"] = tot.astype(np.float32)
        print(f"{year} (KSIC {rev}th): {len(files[year])} sheets, employees {tot.sum():,.0f}, "
              f"commerce {com.sum() / tot.sum():.1%}, manufacturing {man.sum() / tot.sum():.1%}", flush=True)
    np.savez_compressed(os.path.join(GRID, "ind_share.npz"), **out)


if __name__ == "__main__":
    main()
