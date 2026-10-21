"""Move the SGIS census-block (집계구) downloads of request 88979 into data_raw/sgis/oa_stats and extract them.

  statistics zip  -> oa_stats/88979_oa_stats.zip, extracted to oa_stats/csv/
  boundary zip    -> oa_stats/bnd_oa_00_2025_2Q.zip, extracted to oa_stats/bnd_oa_00_2025_2Q/
Names inside the zips are stored in cp949 when not flagged UTF-8.

Usage: python organize_sgis_oa.py <download folder> <statistics zip file name>
"""
import os
import shutil
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths

src, stats_zip = sys.argv[1], sys.argv[2]
dest = os.path.join(paths.SGIS, "oa_stats")


def extract(zpath, out):
    os.makedirs(out, exist_ok=True)
    n = 0
    with zipfile.ZipFile(zpath) as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            name = info.filename
            if not info.flag_bits & 0x800:
                try:
                    name = name.encode("cp437").decode("cp949")
                except (UnicodeEncodeError, UnicodeDecodeError):
                    pass
            with z.open(info) as s, open(os.path.join(out, os.path.basename(name)), "wb") as d:
                shutil.copyfileobj(s, d)
            n += 1
    return n


os.makedirs(dest, exist_ok=True)
jobs = [(stats_zip, "88979_oa_stats.zip", "csv"),
        ("bnd_oa_00_2025_2Q.zip", "bnd_oa_00_2025_2Q.zip", "bnd_oa_00_2025_2Q")]
for name, new, sub in jobs:
    f = os.path.join(src, name)
    z = os.path.join(dest, new)
    shutil.copy2(f, z)
    assert os.path.getsize(z) == os.path.getsize(f)
    n = extract(z, os.path.join(dest, sub))
    os.remove(f)
    print(f"{name} -> oa_stats/{new} ({n} files -> oa_stats/{sub})")
