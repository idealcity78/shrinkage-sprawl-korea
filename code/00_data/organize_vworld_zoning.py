"""Move and extract V-World zoning layers (용도지역) from the browser download folder.

V-World (국토교통부, 연속주제 국토계획, CC BY-NC-ND), EPSG:5186 files by 시도, base month 2026-10:
  UQ111  도시지역 (주거·상업·공업·녹지지역)   dsId 30300   LSMD_CONT_UQ111_{시도}.zip   (16 시도)
  UQ112  관리지역 (계획·생산·보전관리지역)    dsId 30291   LSMD_CONT_UQ112_{시도}.zip   (14 시도; 서울·부산 none)
Each polygon carries NTFDATE (고시일, YYYYMMDD) and its zoning class in the MNUM code.
Skipped: the EPSG:5174 copies (_5174_), browser duplicates (" (1)") and superseded names (전북 -> 전북특별자치도,
전남 / 광주 -> 전남광주통합특별시) when the current file is present.

  data_raw/supply/vworld/zip/              original zips
  data_raw/supply/vworld/shp/{code}_{시도}/  extracted shapefiles

Usage:  python code\\00_data\\organize_vworld_zoning.py [download folder]
"""
import glob
import os
import re
import shutil
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths
from organize_vworld_newcity import member_name

sys.stdout.reconfigure(encoding="utf-8")
SUPERSEDED = {"전북": "전북특별자치도", "전남": "전남광주통합특별시", "광주": "전남광주통합특별시"}


def main(src):
    root = os.path.join(paths.SUPPLY, "vworld")
    zdir = os.path.join(root, "zip")
    os.makedirs(zdir, exist_ok=True)
    found = {}
    for f in sorted(glob.glob(os.path.join(src, "LSMD_CONT_UQ11[12]_*.zip"))):
        m = re.match(r"LSMD_CONT_(UQ11[12])_(?!5174)([^ ()]+)\.zip$", os.path.basename(f))
        if m:
            found[(m.group(1), m.group(2))] = f
    for (code, sido), f in sorted(found.items()):
        if sido in SUPERSEDED and (code, SUPERSEDED[sido]) in found:
            print(f"skip {os.path.basename(f)} (superseded by {SUPERSEDED[sido]})")
            continue
        dest = os.path.join(zdir, os.path.basename(f))
        shutil.move(f, dest)
        out = os.path.join(root, "shp", f"{code}_{sido}")
        os.makedirs(out, exist_ok=True)
        with zipfile.ZipFile(dest) as z:
            for info in z.infolist():
                name = os.path.basename(member_name(info))
                if name:
                    with z.open(info) as s, open(os.path.join(out, name), "wb") as o:
                        shutil.copyfileobj(s, o)
        print(f"{code}_{sido}: {len(os.listdir(out))} files")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.expanduser("~"), "Downloads"))
