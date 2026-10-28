"""
Download additional NBA seasons from the public shufinskiy/nba_data repository
(the same source as the CSVs in data/raw/). Convention: season "2023" is 2023-24.

Usage: python scripts/download_seasons.py 2021 2022 2023

Each season goes to data/raw/seasons/<year>/ as nbastats_<year>.csv (play-by-play) and
shotdetail_<year>.csv (shots). Files are treated as UNTRUSTED: each .tar.xz must contain
exactly one CSV with the expected name and no path, or it is rejected.
Standard library only.
"""
import os
import sys
import tarfile
import urllib.request

BASE = "https://raw.githubusercontent.com/shufinskiy/nba_data/main/datasets/{kind}_{year}.tar.xz"


def fetch(kind: str, year: str, out_dir: str) -> None:
    expected = f"{kind}_{year}.csv"
    archive = os.path.join(out_dir, f"{kind}.tar.xz")
    print(f"  downloading {kind}_{year}.tar.xz ...")
    urllib.request.urlretrieve(BASE.format(kind=kind, year=year), archive)
    with tarfile.open(archive, "r:xz") as tar:
        names = tar.getnames()
        if names != [expected]:
            raise SystemExit(f"Unexpected content in {archive}: {names}")
        member = tar.getmember(expected)
        if not member.isfile():
            raise SystemExit(f"{expected} is not a regular file")
        with tar.extractfile(member) as src, open(os.path.join(out_dir, expected), "wb") as dst:
            dst.write(src.read())


if __name__ == "__main__":
    years = sys.argv[1:]
    if not years:
        raise SystemExit(__doc__)
    for year in years:
        out_dir = os.path.join("data", "raw", "seasons", year)
        os.makedirs(out_dir, exist_ok=True)
        print(f"Season {year}-{int(year) + 1 - 2000:02d}")
        for kind in ("nbastats", "shotdetail"):
            fetch(kind, year, out_dir)
    print("Done. Next: python src/stint_calculator.py", " ".join(years), "2024")
