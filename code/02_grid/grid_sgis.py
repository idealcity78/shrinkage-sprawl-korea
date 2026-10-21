"""SGIS 100 m grid statistics (population, households, housing, businesses, employees) on the national frame.

CSV rows are `year, cell code, item code, value` without a header. The cell code is the 100 km sheet
(two Hangul letters, x then y, 가 = 700 km for x and 1,300 km for y, 100 km steps) plus three digits
each for x and y in 100 m. Only cells with a value are listed. A listed value of 0 is suppressed
(N/A: population items below 5, employees where a cell has 2 businesses or fewer) and is stored as -1.

Items: total population (to_in_001), households (to_ga_001), housing units (to_ho_001),
businesses (to_fa_010), employees (to_em_020). The 9023 business/employee files (2023 under the
other KSIC edition) are skipped; 2023 is used.

Output: data_work/grid100/sgis_{item}.npz, sparse: for each year `y{year}_idx` (flat index into the
frame, row 0 at the top) and `y{year}_val` (int32), plus x0, y0, nrow, ncol, cell.
Log   : data_work/logs/grid_sgis.txt, with the suppressed share by year.

Run with ArcGIS Pro Python:  propy.bat code\\02_grid\\grid_sgis.py
"""
import glob
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths

sys.stdout.reconfigure(encoding="utf-8")
GRID = os.path.join(paths.WORK, "grid100")
CELL = 100
LETTERS = "가나다라마바사아자차카타파하"
ITEMS = {  # name: (folder, Korean file label, item code)
    "pop": ("grid_population", "인구", "to_in_001"),
    "hh": ("grid_household", "가구", "to_ga_001"),
    "house": ("grid_housing", "주택", "to_ho_001"),
    "biz": ("grid_business", "사업체", "to_fa_010"),
    "emp": ("grid_employee", "종사자", "to_em_020"),
}
NAME = re.compile(r"^(\d{4})년_(\S+?)_([가-힣]{2})_100M\.csv$")


def frame():
    z = np.load(os.path.join(GRID, "l1_2009.npz"))
    nrow, ncol = z["urb"].shape
    return int(z["x0"]), int(z["y0"]), nrow, ncol


def sheet_origin(sheet):
    return 700000 + LETTERS.index(sheet[0]) * 100000, 1300000 + LETTERS.index(sheet[1]) * 100000


def read_csv(path, code, sheet, x0, ytop, nrow, ncol):
    sx, sy = sheet_origin(sheet)
    idx, val = [], []
    with open(path, encoding="cp949") as f:
        for line in f:
            p = line.rstrip("\n").split(",")
            if len(p) < 4 or p[2] != code:
                continue
            cx, cy = int(p[1][2:5]), int(p[1][5:8])
            col = (sx + cx * CELL - x0) // CELL
            row = (ytop - (sy + cy * CELL) - CELL) // CELL
            if not (0 <= row < nrow and 0 <= col < ncol):
                continue
            v = int(float(p[3]))
            idx.append(row * ncol + col)
            val.append(v if v > 0 else -1)
    return idx, val


def main():
    x0, y0, nrow, ncol = frame()
    ytop = y0 + nrow * CELL
    os.makedirs(paths.LOGS, exist_ok=True)
    log = open(os.path.join(paths.LOGS, "grid_sgis.txt"), "w", encoding="utf-8")

    def say(s):
        print(s)
        log.write(s + "\n")
        log.flush()

    for name, (folder, label, code) in ITEMS.items():
        files = {}
        for f in glob.glob(os.path.join(paths.SGIS, folder, "csv", "*_100M.csv")):
            m = NAME.match(os.path.basename(f))
            if m and m.group(2) == label and not m.group(1).startswith("9"):
                files.setdefault(int(m.group(1)), []).append((f, m.group(3)))
        out = {"x0": x0, "y0": y0, "nrow": nrow, "ncol": ncol, "cell": CELL}
        for year in sorted(files):
            idx, val = [], []
            for f, sheet in files[year]:
                i, v = read_csv(f, code, sheet, x0, ytop, nrow, ncol)
                idx += i
                val += v
            idx, val = np.array(idx, np.int32), np.array(val, np.int32)
            u, first = np.unique(idx, return_index=True)
            if len(u) < len(idx):
                say(f"  {name} {year}: {len(idx) - len(u):,} duplicate cells dropped")
            idx, val = idx[first], val[first]
            out[f"y{year}_idx"], out[f"y{year}_val"] = idx, val
            na = val < 0
            say(f"{name} {year}: {len(files[year])} sheets, {len(idx):,} cells, total {val[~na].sum():,}, "
                f"suppressed {na.sum():,} cells ({na.mean():.1%})")
        np.savez_compressed(os.path.join(GRID, f"sgis_{name}.npz"), **out)
    log.close()


if __name__ == "__main__":
    main()
