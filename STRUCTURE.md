[English](STRUCTURE.md) | [Español](docs/es/ESTRUCTURA.md)

# System structure

What each folder does and how the data travels until it becomes analysis. Back to the [README](README.md). The data are described in [DATASETS.md](DATASETS.md).

## Flow

```text
raw data  ─►  src/  ─►  processed data  ─►  scripts/  ─►  web/data/  ─►  web/ (page and simulator)
(data/raw)  (calculation)  (data/processed)  (packaging)     (JSON)
```

## Folders

| Folder | What is in it | What it does |
|---|---|---|
| `data/raw/` | NBA shots and play-by-play, and the 2014-15 shots in `external/` | Source data. Not uploaded to GitHub; downloaded with the scripts |
| `data/processed/` | Final shot table with expected shot and residual, and the model metrics | Regenerable intermediate results |
| `data/README.md` | Column dictionary | Meaning of every variable |
| **`src/`** | `stint_calculator.py` · `xshot_model.py` · `fatigue_stats.py` | **Where data become analysis** (see below) |
| `scripts/` | `download_seasons.py` · `download_shot_logs.py` · `data_quality.py` · `build_web_data.py` · `build_defense_data.py` | Download data, audit its quality and package the results as JSON for the web |
| `web/` | `index.html` · `css/` · `js/` · `assets/` · `data/` · `simulador/` | The page (no libraries) and the 3D simulator. They calculate nothing: they read the JSON |
| `tests/` | `test_fatigue_stats.py` (6 tests) · `test_simulator.js` (178 checks) | Verify the statistics do not invent effects and the simulator is coherent |
| `docs/` | Devpost text, video script, project description (English) and `docs/es/` (Spanish) | Submission material |
| `.github/workflows/` | `pages.yml` | Publishes `web/` to GitHub Pages on every push to `main` |
| `logos/` | Hackathon graphic material | Origin of the logos in `web/assets/` |

## What each file in `src/` does

1. **`stint_calculator.py`**: rebuilds how many consecutive minutes each player has been on court at each shot, from the play-by-play substitutions. It handles breaks between quarters, halftime and overtime.
2. **`xshot_model.py`**: trains the shot-difficulty model (distance, position, shot type, period, time remaining) and computes residual = actual accuracy − expected accuracy. It is validated by game and with a held-out season.
3. **`fatigue_stats.py`**: the statistics. It compares each player with themselves in each season: slope per minute, ≥ 8 min vs. 2–6 min contrast, heterogeneity between players, placebo test, multiple-comparison correction and new-player projection.

## What each script in `scripts/` does

- **`download_seasons.py`** and **`download_shot_logs.py`**: download the raw data.
- **`data_quality.py`**: audits the data and writes [DATA_QUALITY.md](DATA_QUALITY.md), `docs/es/CALIDAD_DE_DATOS.md` and `web/data/quality.json`.
- **`build_web_data.py`**: calls `fatigue_stats.py` and writes `summary.json`, `players.json` and `shots/<id>.json`.
- **`build_defense_data.py`**: computes the rival-team and defender-distance effects.

## Interface language

The web page and the simulator are bilingual (English default, Spanish). The texts live in `web/js/i18n.js`; the choice is stored in the browser and can be forced with `?lang=es` or `?lang=en`.
