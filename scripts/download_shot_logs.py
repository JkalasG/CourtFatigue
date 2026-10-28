"""
Descarga el registro de tiros 2014-15 con distancia al defensor (Kaggle "NBA shot logs", licencia CC0)
desde el espejo de OpenML y lo convierte a CSV.

Uso:  python scripts/download_shot_logs.py        (requiere pandas)
Salida: data/raw/external/shot_logs_2014/shot_logs_2014.csv  (128,069 tiros, 904 partidos, hasta el 4-mar-2015)

El archivo se trata como NO confiable: solo se lee como texto ARFF; no se ejecuta nada de él.
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
    print("descargando", URL)
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
    print(f"{len(d):,} tiros -> {out}")


if __name__ == "__main__":
    main()
