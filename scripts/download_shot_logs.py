"""
Download the 2014-15 shot log with defender distance (Kaggle "NBA shot logs", CC0)
from the OpenML mirror and convert it to CSV.

Usage:  python scripts/download_shot_logs.py        (requires pandas)
Output: data/raw/external/shot_logs_2014/shot_logs_2014.csv  (128,069 shots, 904 games, through 4 Mar 2015)

The file is treated as UNTRUSTED: it is only read as ARFF text; nothing in it is executed.
"""
import os
import re
import urllib.request

import pandas as pd

URL = "https://openml.org/data/v1/download/22045034/nba-shot-logs.arff"
OUT_DIR = os.path.join("data", "raw", "external", "shot_logs_2014")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    arff = os.path.join(OUT_DIR, "nba-shot-logs.arff")
    print("downloading", URL)
    urllib.request.urlretrieve(URL, arff)
    names, start = [], 0
    with open(arff, encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f):
            if line.lower().startswith("@attribute"):
                m = re.match(r"@attribute\s+('([^']+)'|\"([^\"]+)\"|(\S+))", line, re.I)
                names.append(next(g for g in m.groups()[1:] if g))
            if line.lower().startswith("@data"):
                start = i + 1
                break
    d = pd.read_csv(arff, skiprows=start, names=names, quotechar="'", escapechar="\\", na_values=["?"], engine="python")
    out = os.path.join(OUT_DIR, "shot_logs_2014.csv")
    d.to_csv(out, index=False)
    print(f"{len(d):,} shots -> {out}")


if __name__ == "__main__":
    main()
