"""Move and extract SGIS request 89101 from the browser download folder.

The census zip (`_census_reqdoc_*.zip`) holds 1 km grid industry tables (사업체중분류, 종사자중분류) and
census-block tables (성연령별 인구, 건축년도별 주택 for 2019 and 2024). The urban-area boundary zips
(`_grid_border_urban_도시화경계_{year}_*.zip`) hold 1 km grid polygons, 도시 and 준도시, per year.

  data_raw/sgis/89101_census.zip                     original census zip
  data_raw/sgis/grid_industry/csv/                   {year}년_{사업체|종사자}중분류_{sheet}_1K.csv
  data_raw/sgis/oa_stats/csv/                        2025년기준_{year}년_{item}.csv (added to 88979)
  data_raw/sgis/urban_area_grid/zip/, shp/           도시화경계_{year}.zip, 도시화경계_{year}_{도시|준도시}.shp

Zip member names are CP949. Duplicate downloads ("... (1).zip") are deleted after checking the size.

Usage:  python code\\00_data\\organize_sgis_89101.py [download folder]
"""
import glob
import os
import re
import shutil
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths

sys.stdout.reconfigure(encoding="utf-8")


def member_name(info):
    try:
        return info.filename.encode("cp437").decode("cp949")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return info.filename


def extract(zpath, route):
    """Extract each member to the folder `route(name)` returns (None skips it)."""
    n = 0
    with zipfile.ZipFile(zpath) as z:
        for info in z.infolist():
            name = os.path.basename(member_name(info))
            dest = route(name) if name else None
            if not dest:
                continue
            os.makedirs(dest, exist_ok=True)
            with z.open(info) as src, open(os.path.join(dest, name), "wb") as out:
                shutil.copyfileobj(src, out)
            n += 1
    return n


def main(src):
    sg = paths.SGIS
    census = [f for f in glob.glob(os.path.join(src, "_census_reqdoc_*.zip")) if "(" not in os.path.basename(f)]
    for f in glob.glob(os.path.join(src, "_census_reqdoc_* (*).zip")):
        base = re.sub(r" \(\d+\)", "", f)
        if os.path.exists(base) and os.path.getsize(base) == os.path.getsize(f):
            os.remove(f)
    for f in census:
        with zipfile.ZipFile(f) as z:
            if not any("중분류" in member_name(i) for i in z.infolist()):
                continue
        dest = os.path.join(sg, "89101_census.zip")
        shutil.move(f, dest)
        n = extract(dest, lambda name: os.path.join(sg, "grid_industry", "csv") if "중분류" in name
                    else os.path.join(sg, "oa_stats", "csv") if name.startswith("2025년기준") else None)
        print(f"89101 census zip: {n} files extracted")

    zdir = os.path.join(sg, "urban_area_grid", "zip")
    os.makedirs(zdir, exist_ok=True)
    for f in sorted(glob.glob(os.path.join(src, "_grid_border_urban_도시화경계_*.zip"))):
        m = re.search(r"도시화경계_(\d{4})", os.path.basename(f))
        dest = os.path.join(zdir, f"도시화경계_{m.group(1)}.zip")
        shutil.move(f, dest)
        n = extract(dest, lambda name: os.path.join(sg, "urban_area_grid", "shp"))
        print(f"urban area {m.group(1)}: {n} files")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.expanduser("~"), "Downloads"))
