[English](../../DATASETS.md) | [Español](DATASETS.md)

# Datasets de CourtFatigue

Qué datos usa el proyecto, de dónde salen, cómo descargarlos y en qué se transforman. Volver al [README](../../README.es.md). El significado de cada columna está en [`data/README.es.md`](../../data/README.es.md); la revisión de su calidad, en [CALIDAD_DE_DATOS.md](CALIDAD_DE_DATOS.md).

## 1. Datos de origen (se descargan)

| Dataset | Contenido | Tamaño | Fuente y descarga | Licencia / uso | Cómo se obtiene en el proyecto | Para qué se usa |
|---|---|---|---|---|---|---|
| **Tiros** `shotdetail_<año>` | Cada tiro de campo: jugador, equipo, periodo, reloj, posición (x, y), distancia, zona, tipo de tiro y si entró. 4 temporadas: 2021-22 a 2024-25 (el año del archivo es el de inicio) | ≈ 44 MB por temporada (≈ 217 mil tiros) | Repositorio [shufinskiy/nba_data](https://github.com/shufinskiy/nba_data/tree/main/datasets), archivos `shotdetail_<año>.tar.xz`. Origen: NBA Stats API (`ShotChartDetail`) | Datos de la NBA, redistribuidos para uso no comercial | `python scripts/download_seasons.py 2021 2022 2023` (la 2024 ya viene en `data/raw/`) | Tiro esperado (xShot) y unidad de análisis |
| **Play-by-play** `nbastats_<año>` | Cada jugada del partido: sustituciones, tiros, marcador y reloj | ≈ 94–105 MB por temporada | El mismo repositorio, archivos `nbastats_<año>.tar.xz`. Origen: NBA Stats API (`PlayByPlayV2`) | Igual que arriba | Igual que arriba | Reconstruir los minutos seguidos en cancha y el marcador |
| **NBA shot logs 2014-15** | 128,069 tiros con la distancia al defensor más cercano, su nombre, reloj de posesión, toques y regates. Solo hasta el 4-mar-2015 | ≈ 17 MB | [Kaggle: NBA shot logs](https://www.kaggle.com/datasets/dansbecker/nba-shot-logs) y su espejo en [OpenML](https://www.openml.org/search?type=data&q=nba-shot-logs), de donde lo baja el script | CC0 (dominio público) | `python scripts/download_shot_logs.py` | Efecto de la distancia al defensor en el simulador (otra época: ver limitaciones) |

Descarga directa de los dos primeros: `https://raw.githubusercontent.com/shufinskiy/nba_data/main/datasets/<tipo>_<año>.tar.xz` (`<tipo>` = `shotdetail` o `nbastats`).

> Verifica los términos vigentes de cada fuente antes de reutilizar los datos. Los datos crudos no se suben a este repositorio por su tamaño (ver `.gitignore`).

## 2. Datos que genera el proyecto

| Archivo | Lo genera | Contenido | Dónde se usa |
|---|---|---|---|
| `data/processed/by_season/stints_<año>.csv` | `src/stint_calculator.py` | Los tiros de la temporada con minutos seguidos en cancha, minutos jugados, ventaja en el marcador y local/visitante (≈ 59 MB por temporada) | Entrada del paso siguiente |
| `data/processed/shots_fatigue_processed.csv` | `src/xshot_model.py` | Las 4 temporadas juntas, 872,158 tiros, con tiro esperado (`xShot`) y residuo (acierto − esperado) (≈ 150 MB) | Toda la estadística |
| `data/processed/xshot_metrics.json` | `src/xshot_model.py` | Calidad del modelo de tiro esperado (validación por partido y temporal) | Pestaña Método |
| `web/data/summary.json` | `scripts/build_web_data.py` | Resultados poblacionales: efectos, robustez, replicación, arranque frío, placebo, potencia | Pestañas Resumen, Evidencia y Método |
| `web/data/players.json` y `web/data/shots/<id>.json` | `scripts/build_web_data.py` | 643 jugadores: curvas por minuto, mapas de tiro y tiros individuales | Pestaña Jugador y simulador |
| `web/data/defense.json` | `scripts/build_defense_data.py` | Efecto defensivo por equipo rival (2024-25) | Pestaña Evidencia y simulador |
| `web/data/contest.json` y `web/data/distance.json` | `scripts/build_defense_data.py` | Efecto de la distancia al defensor y curva de acierto por distancia de tiro | Simulador |
| `web/data/quality.json` | `scripts/data_quality.py` | Resultado de la auditoría de calidad | Pestaña Método |

Los archivos de `web/data/` sí se suben al repositorio (toda la carpeta `web/` pesa unos 15 MB) porque la página los lee directamente. Los de `data/` son regenerables y están en `.gitignore`.

## 3. Cómo se relacionan

```text
shotdetail_<año>  ─┐
                   ├─►  stints_<año>.csv  ─►  shots_fatigue_processed.csv  ─►  web/data/*.json  ─►  página y simulador
nbastats_<año>    ─┘                              (+ xShot, residuo)                  ▲
                                                                                      │
NBA shot logs 2014-15 ────────────────────────────────────────────────────────────────┘
(solo para el efecto de la distancia al defensor; no se cruza con las otras temporadas)
```
