[English](../../STRUCTURE.md) | [Español](ESTRUCTURA.md)

# Estructura del sistema

Qué hace cada carpeta y por dónde pasan los datos hasta convertirse en análisis. Volver al [README](../../README.es.md). Los datos están descritos en [DATASETS.md](DATASETS.md).

## Flujo

```text
datos crudos  ─►  src/  ─►  datos procesados  ─►  scripts/  ─►  web/data/  ─►  web/ (página y simulador)
(data/raw)      (cálculo)    (data/processed)    (empaquetado)    (JSON)
```

## Carpetas

| Carpeta | Qué hay | Qué hace |
|---|---|---|
| `data/raw/` | Tiros y play-by-play de la NBA, y los tiros 2014-15 en `external/` | Datos de origen. No se suben a GitHub; se descargan con los scripts |
| `data/processed/` | Tabla final de tiros con tiro esperado y residuo, y las métricas del modelo | Resultados intermedios, regenerables |
| `data/README.es.md` | Diccionario de columnas | Significado de cada variable |
| **`src/`** | `stint_calculator.py` · `xshot_model.py` · `fatigue_stats.py` | **Aquí se convierte el dato en análisis** (ver abajo) |
| `scripts/` | `download_seasons.py` · `download_shot_logs.py` · `data_quality.py` · `build_web_data.py` · `build_defense_data.py` | Descargan datos, auditan su calidad y empaquetan los resultados en JSON para la web |
| `web/` | `index.html` · `css/` · `js/` · `assets/` · `data/` · `simulador/` | La página (sin librerías) y el simulador 3D. No calculan nada: leen los JSON |
| `tests/` | `test_fatigue_stats.py` (6 pruebas) · `test_simulator.js` (178 comprobaciones) | Verifican que la estadística no invente efectos y que el simulador sea coherente |
| `docs/` | Texto para Devpost, guion del video y descripción del proyecto (inglés) y `docs/es/` (español) | Material de la entrega |
| `.github/workflows/` | `pages.yml` | Publica `web/` en GitHub Pages en cada push a `main` |
| `logos/` | Material gráfico del hackatón | Origen de los logos de `web/assets/` |

## Qué hace cada archivo de `src/`

1. **`stint_calculator.py`**: reconstruye cuántos minutos seguidos lleva cada jugador en cancha en cada tiro, a partir de las sustituciones del play-by-play. Cuida los descansos entre cuartos, el medio tiempo y los tiempos extra.
2. **`xshot_model.py`**: entrena el modelo de dificultad del tiro (distancia, posición, tipo de tiro, periodo, tiempo restante) y calcula el residuo = acierto real − acierto esperado. Se valida por partido y con una temporada reservada.
3. **`fatigue_stats.py`**: la estadística. Compara cada jugador contra sí mismo en cada temporada: pendiente por minuto, contraste ≥ 8 min contra 2–6 min, heterogeneidad entre jugadores, prueba placebo, corrección por comparaciones múltiples y proyección de un jugador nuevo.

## Qué hace cada script de `scripts/`

- **`download_seasons.py`** y **`download_shot_logs.py`**: bajan los datos crudos.
- **`data_quality.py`**: audita los datos y escribe [CALIDAD_DE_DATOS.md](CALIDAD_DE_DATOS.md), `DATA_QUALITY.md` y `web/data/quality.json`.
- **`build_web_data.py`**: llama a `fatigue_stats.py` y escribe `summary.json`, `players.json` y `shots/<id>.json`.
- **`build_defense_data.py`**: calcula el efecto del equipo rival y de la distancia del defensor.

## Idioma de la interfaz

La página y el simulador son bilingües (inglés por defecto, español). Los textos están en `web/js/i18n.js`; la elección se guarda en el navegador y se puede forzar con `?lang=es` o `?lang=en`.
