"""Move the downloaded middle-class (L2) land cover zips into data_raw and extract them.

The MCEE download saves one zip per 1:25,000 sheet, named SG04_{sheet}_{production date}.zip,
into the folder chosen in RAON-K. This script moves them to
    data_raw/landcover_mcee/L2_{year}/zip/
and extracts each into
    data_raw/landcover_mcee/L2_{year}/shp/
Names inside the zips are stored in cp949 when not flagged UTF-8.

Usage: python unzip_l2.py [download folder]   (default: the project folder)
"""
import os
import shutil
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths

# production date in the file name -> map version year
VERSIONS = {"20071210": "2007", "20230126": "2022"}

src = sys.argv[1] if len(sys.argv) > 1 else paths.DATA


def extract(zpath, dest):
    with zipfile.ZipFile(zpath) as z:
        for info in z.infolist():
            name = info.filename
            if not info.flag_bits & 0x800:
                try:
                    name = name.encode("cp437").decode("cp949")
                except (UnicodeEncodeError, UnicodeDecodeError):
                    pass  # already decoded (e.g. Unicode path extra field)
            with z.open(info) as s, open(os.path.join(dest, os.path.basename(name)), "wb") as d:
                shutil.copyfileobj(s, d)


def zip_dir(year):
    return os.path.join(paths.LANDCOVER, f"L2_{year}", "zip")


# 1) move new downloads into data_raw
for f in sorted(os.listdir(src)):
    if f.startswith("SG04_") and f.endswith(".zip"):
        year = VERSIONS[f[:-4].split("_")[-1]]
        os.makedirs(zip_dir(year), exist_ok=True)
        shutil.move(os.path.join(src, f), os.path.join(zip_dir(year), f))

# 2) extract everything that is in data_raw
counts = {}
for year in sorted(set(VERSIONS.values())):
    zdir = zip_dir(year)
    if not os.path.isdir(zdir):
        continue
    sdir = os.path.join(os.path.dirname(zdir), "shp")
    os.makedirs(sdir, exist_ok=True)
    for f in sorted(os.listdir(zdir)):
        if f.endswith(".zip"):
            extract(os.path.join(zdir, f), sdir)
            counts[year] = counts.get(year, 0) + 1

for year, n in sorted(counts.items()):
    print(f"L2_{year}: {n} zips extracted")
