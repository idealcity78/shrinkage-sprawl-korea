"""File the downloaded fine-class (L3, 세분류) land cover zips by map version, and extract on demand.

The MCEE download saves one zip per 1:5,000 sheet, named SG05_{sheet}_{production date}.zip.
Sheets on the border between the two requests of a year arrive once (same file name).

The zips stay zipped on the NAS (about 32,000 zips, 42 GB; extracting them there would write
more than 200,000 files and slow every other job). Analysis steps extract the sheets they need to
a local scratch folder with extract_sheets() and keep only their results.

  file mode (default): move SG05_*.zip from the download folder to
                       data_raw/landcover_mcee/L3_{year}/zip/ and report sheet counts
  python unzip_l3.py [download folder]
"""
import os
import shutil
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths

# production date in the file name -> map version year
VERSIONS = {"20200210": "2019", "20251113": "2025"}


def zip_dir(year):
    return os.path.join(paths.LANDCOVER, f"L3_{year}", "zip")


def extract_sheets(year, dest, sheets=None):
    """Extract the zips of one version (all, or only the given sheet numbers) into dest.
    Names inside the zips are stored in cp949 when not flagged UTF-8. Returns the .shp paths."""
    os.makedirs(dest, exist_ok=True)
    shps = []
    for f in sorted(os.listdir(zip_dir(year))):
        if not f.endswith(".zip") or (sheets is not None and f.split("_")[1] not in sheets):
            continue
        with zipfile.ZipFile(os.path.join(zip_dir(year), f)) as z:
            for info in z.infolist():
                if info.is_dir():
                    continue
                name = info.filename
                if not info.flag_bits & 0x800:
                    try:
                        name = name.encode("cp437").decode("cp949")
                    except (UnicodeEncodeError, UnicodeDecodeError):
                        pass
                name = os.path.basename(name)
                with z.open(info) as s, open(os.path.join(dest, name), "wb") as d:
                    shutil.copyfileobj(s, d)
                if name.lower().endswith(".shp"):
                    shps.append(os.path.join(dest, name))
    return shps


def file_downloads(src):
    moved, unknown = {}, {}
    with os.scandir(src) as it:
        entries = [e for e in it if e.is_file() and e.name.startswith("SG05_") and e.name.endswith(".zip")]
    for e in entries:
        year = VERSIONS.get(e.name[:-4].split("_")[-1])
        if year is None:
            unknown[e.name] = 1
            continue
        os.makedirs(zip_dir(year), exist_ok=True)
        target = os.path.join(zip_dir(year), e.name)
        if os.path.exists(target):  # border sheet already filed from the other request
            if os.path.getsize(target) == e.stat().st_size:
                os.remove(e.path)
                continue
        shutil.move(e.path, target)
        moved[year] = moved.get(year, 0) + 1
        if sum(moved.values()) % 2000 == 0:
            print(f"  moved {moved}", flush=True)
    print("moved:", moved, "unknown:", list(unknown)[:5], flush=True)
    for year in sorted(set(VERSIONS.values())):
        if os.path.isdir(zip_dir(year)):
            zips = [f for f in os.listdir(zip_dir(year)) if f.endswith(".zip")]
            gb = sum(os.path.getsize(os.path.join(zip_dir(year), f)) for f in zips) / 1e9
            print(f"L3_{year}: {len(zips)} sheets, {gb:.1f} GB", flush=True)


if __name__ == "__main__":
    file_downloads(sys.argv[1] if len(sys.argv) > 1 else paths.RAW)
