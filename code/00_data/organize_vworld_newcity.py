"""Move and extract V-World innovation / enterprise city zones from the browser download folder.

V-World (국토교통부, 연속주제 용도지역지구, CC BY-NC-ND), EPSG:5186 files only:
  UB811  혁신도시개발예정/용도지구   dsId 30450   LSMD_CONT_UB811_{시도}.zip
  UB601  기업도시개발/기업도시       dsId 30316   LSMD_CONT_UB601_{시도}.zip
  UB611  기업도시개발/용도구역       dsId 30317   LSMD_CONT_UB611_{시도}.zip
  LSMD_CONT.xlsx                    code table shared by the 연속주제 datasets
  UQ161  지구단위계획구역(현황)       dsId 30115   C_UQ161.zip (전국), Z_UPIS_C_UQ161.xlsx (정의서). Used for
         innovation cities whose 개발예정지구 was lifted after completion (울산, 전북, 제주)

  data_raw/supply/vworld/zip/       original zips and LSMD_CONT.xlsx
  data_raw/supply/vworld/shp/{code}_{시도}/   extracted shapefiles

Usage:  python code\\00_data\\organize_vworld_newcity.py [download folder]
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


def main(src):
    root = os.path.join(paths.SUPPLY, "vworld")
    zdir = os.path.join(root, "zip")
    os.makedirs(zdir, exist_ok=True)
    for name in ("LSMD_CONT.xlsx", "Z_UPIS_C_UQ161.xlsx"):
        for f in glob.glob(os.path.join(src, name)):
            shutil.move(f, os.path.join(zdir, name))
    zips = [(f, re.match(r"LSMD_CONT_(UB\d{3})_(?!5174)(.+)\.zip$", os.path.basename(f)))
            for f in sorted(glob.glob(os.path.join(src, "LSMD_CONT_UB*.zip")))]
    zips = [(f, f"{m.group(1)}_{m.group(2)}") for f, m in zips if m]
    zips += [(f, "UQ161_전국") for f in glob.glob(os.path.join(src, "C_UQ161.zip"))]
    for f, folder in zips:
        dest = os.path.join(zdir, os.path.basename(f))
        shutil.move(f, dest)
        out = os.path.join(root, "shp", folder)
        os.makedirs(out, exist_ok=True)
        with zipfile.ZipFile(dest) as z:
            for info in z.infolist():
                name = os.path.basename(member_name(info))
                if name:
                    with z.open(info) as s, open(os.path.join(out, name), "wb") as o:
                        shutil.copyfileobj(s, o)
        print(f"{folder}: {len(os.listdir(out))} files")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.expanduser("~"), "Downloads"))
