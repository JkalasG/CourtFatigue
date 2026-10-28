"""
Descarga temporadas adicionales de la NBA desde el repositorio público shufinskiy/nba_data
(el mismo origen de los CSV de data/raw/). Convención: la temporada "2023" es 2023-24.

Uso:  python scripts/download_seasons.py 2021 2022 2023

Cada temporada va a data/raw/seasons/<año>/ con nbastats_<año>.csv (play-by-play) y
shotdetail_<año>.csv (tiros). Los archivos se tratan como NO confiables: cada .tar.xz debe
contener exactamente un CSV con el nombre esperado, sin rutas, o se descarta.
Solo usa la biblioteca estándar de Python.
"""
import os
import sys
import tarfile
import urllib.request

BASE = "https://raw.githubusercontent.com/shufinskiy/nba_data/main/datasets/{kind}_{year}.tar.xz"


def fetch(kind: str, year: str, out_dir: str) -> None:
    expected = f"{kind}_{year}.csv"
    archive = os.path.join(out_dir, f"{kind}.tar.xz")
    print(f"  descargando {kind}_{year}.tar.xz ...")
    urllib.request.urlretrieve(BASE.format(kind=kind, year=year), archive)
    with tarfile.open(archive, "r:xz") as tar:
        names = tar.getnames()
        if names != [expected]:
            raise SystemExit(f"Contenido inesperado en {archive}: {names}")
        member = tar.getmember(expected)
        if not member.isfile():
            raise SystemExit(f"{expected} no es un archivo regular")
        with tar.extractfile(member) as src, open(os.path.join(out_dir, expected), "wb") as dst:
            dst.write(src.read())


if __name__ == "__main__":
    years = sys.argv[1:]
    if not years:
        raise SystemExit(__doc__)
    for year in years:
        out_dir = os.path.join("data", "raw", "seasons", year)
        os.makedirs(out_dir, exist_ok=True)
        print(f"Temporada {year}-{int(year) + 1 - 2000:02d}")
        for kind in ("nbastats", "shotdetail"):
            fetch(kind, year, out_dir)
    print("Listo. Siguiente: python src/stint_calculator.py", " ".join(years), "2024")
