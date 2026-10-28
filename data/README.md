[English](README.md) | [Español](README.es.md)

# Dataset dictionary and documentation - CourtFatigue

This directory holds the data **CourtFatigue** uses to estimate the effect of fatigue on shooting performance:

| Dataset | Content | Use |
| --- | --- | --- |
| **NBA 2021-22, 2022-23, 2023-24, 2024-25** (regular seasons) | 4 x 1,230 games, 872,158 shots with coordinates and their play-by-play | Main analysis |
| **2014-15 shot log** ("NBA shot logs", CC0) | 128,069 shots with nearest-defender distance, shot clock, touch time and dribbles | 3D simulator and measuring the limitation of having no defender data. **Not merged** with the other seasons |

**Naming convention:** in the source files, season `2024` is 2024-25 (it starts in October 2024), `2023` is 2023-24, and so on.

Table of datasets with download links and licenses: [DATASETS.md](../DATASETS.md).

---

## Structure of `data/`

```text
data/
├── raw/                                 # Original datasets, unmodified
│   ├── shotdetail_2024.csv              # 2024-25: 219,527 shots with coordinates and zones
│   ├── nbastats_2024.csv                # 2024-25: full play-by-play (94 MB; not versioned)
│   ├── seasons/<year>/                  # 2021, 2022, 2023: same two files (scripts/download_seasons.py)
│   └── external/shot_logs_2014/         # 2014-15 with defender distance (scripts/download_shot_logs.py)
├── processed/                           # Processed datasets ready for modelling (regenerable)
│   ├── by_season/stints_<year>.csv      # shots + consecutive minutes, score and home flag, per season
│   ├── shots_fatigue_processed.csv      # 4 seasons + out-of-sample xShot + residual
│   └── xshot_metrics.json               # xShot log-loss, Brier, AUC and calibration (cross-validated and temporal)
└── README.md                            # This specification document
```

---

## 1. Dataset: `shotdetail_2024.csv` (spatial shot record)

* **Path:** `data/raw/shotdetail_2024.csv`
* **Records:** 219,527 regular-season shot attempts.
* **Source:** NBA Stats API (`ShotChartDetail` endpoint).
* **Purpose in CourtFatigue:** provides exact Cartesian coordinates, distance to the hoop, technical difficulty of the play, court zone and the result of each shot.

### Column dictionary

| Column | Type | Description | Example / possible values |
| :--- | :--- | :--- | :--- |
| `GRID_TYPE` | `String` | Report type identifier | `"Shot Chart Detail"` |
| `GAME_ID` | `String` / `Int` | Official unique NBA game identifier (10 digits) | `"0022400001"` |
| `GAME_EVENT_ID` | `Int` | Sequential event number within the game. **Links directly to `EVENTNUM` in the play-by-play.** | `7`, `10`, `45` |
| `PLAYER_ID` | `Int` | Official numeric NBA player ID | `1628369` (Jayson Tatum), `201939` (Stephen Curry) |
| `PLAYER_NAME` | `String` | Player's full name | `"Jayson Tatum"`, `"Nikola Jokić"` |
| `TEAM_ID` | `Int` | Official numeric franchise ID | `1610612738` (Boston Celtics) |
| `TEAM_NAME` | `String` | Franchise full name | `"Boston Celtics"`, `"Denver Nuggets"` |
| `PERIOD` | `Int` | Period or quarter of the shot | `1`, `2`, `3`, `4` (5+ for overtime) |
| `MINUTES_REMAINING` | `Int` | Minutes left on the quarter clock | `11`, `4`, `0` |
| `SECONDS_REMAINING` | `Int` | Seconds left in the current minute | `43`, `12`, `0` |
| `EVENT_TYPE` | `String` | Textual shot result | `"Made Shot"`, `"Missed Shot"` |
| `ACTION_TYPE` | `String` | Specific shot mechanics | `"Jump Shot"`, `"Pullup Jump Shot"`, `"Step Back Jump Shot"`, `"Driving Layup"`, `"Fadeaway Bank Jump Shot"` |
| `SHOT_TYPE` | `String` | General scoring-value category | `"2PT Field Goal"`, `"3PT Field Goal"` |
| `SHOT_ZONE_BASIC` | `String` | Standard court zone by NBA geometry | `"Restricted Area"`, `"In The Paint (Non-RA)"`, `"Mid-Range"`, `"Left Corner 3"`, `"Right Corner 3"`, `"Above the Break 3"`, `"Backcourt"` |
| `SHOT_ZONE_AREA` | `String` | Lateral orientation of the shot relative to the hoop | `"Center(C)"`, `"Left Side(L)"`, `"Left Side Center(LC)"`, `"Right Side Center(RC)"`, `"Right Side(R)"`, `"Back Court(BC)"` |
| `SHOT_ZONE_RANGE` | `String` | Distance-to-hoop category | `"Less Than 8 ft."`, `"8-16 ft."`, `"16-24 ft."`, `"24+ ft."`, `"Back Court Shot"` |
| `SHOT_DISTANCE` | `Int` | Exact Euclidean distance from the hoop in feet | `26` (three), `4` (layup), `14` (mid-range) |
| `LOC_X` | `Int` | Horizontal shot coordinate (X axis, tenths of a foot). `0` is the court / hoop center. | `-168` (left), `120` (right) |
| `LOC_Y` | `Int` | Vertical shot coordinate (Y axis, tenths of a foot). `0` is the baseline at the hoop. | `205` (toward mid-court), `-10` (behind the hoop) |
| `SHOT_ATTEMPTED_FLAG` | `Int` | Attempted-shot flag (always 1) | `1` |
| `SHOT_MADE_FLAG` | `Int` | **Target variable:** `1` if the shot went in, `0` if missed. | `1` or `0` |
| `GAME_DATE` | `String` | Date the game was played (`YYYYMMDD`) | `"20241112"` |
| `HTM` | `String` | Home team abbreviation | `"BOS"`, `"DEN"`, `"LAL"` |
| `VTM` | `String` | Visitor team abbreviation | `"ATL"`, `"GSW"`, `"MIA"` |

---

## 2. Dataset: `nbastats_2024.csv` (play-by-play and substitutions)

* **Path:** `data/raw/nbastats_2024.csv`
* **Records:** ~550,000+ game events from the 1,230 games.
* **Source:** NBA Stats API (`PlayByPlayV2` endpoint).
* **Purpose in CourtFatigue:** track chronologically when each player enters and leaves, to compute second-accurate **uninterrupted minutes on court (*stints*)**.

### Key column dictionary

| Column | Type | Description and use in CourtFatigue |
| :--- | :--- | :--- |
| `GAME_ID` | `String` / `Int` | Game identifier (join key with `shotdetail`). |
| `EVENTNUM` | `Int` | Sequential event number within the game. **Direct join key with `GAME_EVENT_ID`.** |
| `EVENTMSGTYPE` | `Int` | **Core event code.** Defines the action: <br>• `1`: Made shot <br>• `2`: Missed shot <br>• `3`: Free throw <br>• `4`: Rebound <br>• `5`: Turnover <br>• `6`: Personal foul <br>• **`8`: Substitution (key for CourtFatigue)** <br>• `9`: Timeout <br>• `10`: Jump ball <br>• `12`: Start of period <br>• `13`: End of period |
| `EVENTMSGACTIONTYPE` | `Int` | Technical sub-classification of the event action. |
| `PERIOD` | `Int` | Period or quarter (1 to 4 regulation, 5+ overtime). |
| `WCTIMESTRING` | `String` | Wall-clock time at the arena (e.g. `"7:11 PM"`). |
| `PCTIMESTRING` | `String` | **Period clock:** time remaining as `MM:SS` (e.g. `"11:43"`). |
| `HOMEDESCRIPTION` | `String` | Description of the play for the home team. |
| `NEUTRALDESCRIPTION` | `String` | Description of neutral events (e.g. `"Start of 1st Period"`). |
| `VISITORDESCRIPTION` | `String` | Description for the visiting team. |
| `SCORE` | `String` | Running score after the event (e.g. `"104 - 101"`). |
| `SCOREMARGIN` | `String` | Point difference between home and visitor. |
| `PERSON1TYPE` | `Int` | Person 1 type (`4` = home player, `5` = visiting player). |
| `PLAYER1_ID` | `Int` | Main player ID. **In `EVENTMSGTYPE = 8` (substitution) events, this is the PLAYER LEAVING for the bench.** |
| `PLAYER1_NAME` | `String` | Main player name (**player who LEAVES in substitutions**). |
| `PLAYER1_TEAM_ID` | `Int` | Franchise ID of player 1. |
| `PLAYER1_TEAM_ABBREVIATION` | `String` | Team abbreviation (e.g. `"BOS"`, `"LAL"`). |
| `PERSON2TYPE` | `Int` | Person 2 type. |
| `PLAYER2_ID` | `Int` | Secondary player ID. **In `EVENTMSGTYPE = 8` (substitution) events, this is the PLAYER ENTERING the court.** |
| `PLAYER2_NAME` | `String` | Secondary player name (**player who ENTERS in substitutions**). |
| `PLAYER3_ID` / `PLAYER3_NAME` | `Int` / `String` | Third actor of the event (assister on a make, blocker on a miss, or fouled player). |

---

## 3. How the datasets are joined and processed (CourtFatigue algorithm)

```
┌────────────────────────────────────────────────────────┐
│                   shotdetail_2024.csv                  │
│  [GAME_ID] + [GAME_EVENT_ID]                           │
│  Coordinates (LOC_X, LOC_Y) + SHOT_DISTANCE + ACTION   │
└───────────────────────────┬────────────────────────────┘
                            │ Relational join
                            │ GAME_ID == GAME_ID
                            │ GAME_EVENT_ID == EVENTNUM
                            ▼
┌────────────────────────────────────────────────────────┐
│                   nbastats_2024.csv                    │
│  [GAME_ID] + [EVENTNUM]                                │
│  EVENTMSGTYPE == 8 (Substitutions: OUT -> IN)          │
│  PCTIMESTRING clock (seconds on court)                 │
└───────────────────────────┬────────────────────────────┘
                            │ Inference pipeline
                            ▼
┌────────────────────────────────────────────────────────┐
│        PROCESSED DATASET (data/processed/)             │
│  • stint_minutes        (consecutive minutes; halftime │
│                          resets)                       │
│  • game_minutes_played  (accumulated load in the game) │
│  • xShot                (baseline make probability)    │
│  • shot_residual        (actual - xShot)               │
│  • stint_inferred       (shooter not on court)         │
└────────────────────────────────────────────────────────┘
```

1. **Who is on court:** the play-by-play **does not record substitutions made between quarters**. In each quarter, anyone who appears active before entering as a substitute counts as "already on court"; if they were also on court at the end of the previous quarter they keep their counter. A shooter who is not on court is flagged `stint_inferred = True` (~0.3% of shots) and excluded from the main analysis.
2. **Stint clock:** counts game-clock time only (breaks do not add). `stint_minutes` continues across Q1→Q2 and Q3→Q4 and **resets at halftime**; `stint_minutes_quarter` resets every quarter (sensitivity check).
3. **Substitutions (`EVENTMSGTYPE = 8`):** `PLAYER1_ID` leaves and `PLAYER2_ID` enters with the counter at 0.
4. **Shot assignment:** each shot receives `stint_minutes`, `stint_minutes_quarter`, `game_minutes_played` (accumulated load in the game), `score_margin` (shooter team's margin **before** the shot, from `SCOREMARGIN`, which is home − visitor) and `is_home` (`PERSON1TYPE = 4`).
5. **Expected shot (xShot) and residual:** gradient boosting on distance, coordinates, zone, shot type, period and time remaining (no minutes on court or player identity). Predicted out of sample with game-grouped cross-validation; also evaluated with a temporal test (train on earlier seasons, evaluate on the last). `shot_residual = SHOT_MADE_FLAG - xShot`.
6. **Within-season comparison:** each player is compared with their average **in that season** (`dev = shot_residual − player-season mean`), because their level changes from one year to the next.
7. **Inference:** the fatigue effect is estimated in `src/fatigue_stats.py` (≥ 8 min vs. 2-6 min contrast per player, fixed-effects slope, random effects, multiple-comparison correction and placebo test).
8. **Schedule:** `b2b` (the team played the day before) is computed in `scripts/build_web_data.py` from `GAME_DATE`.

### Columns added by the pipeline

| Column | Description |
| --- | --- |
| `SEASON` | Source season (`2021`…`2024`) |
| `stint_minutes` / `stint_minutes_quarter` | Consecutive minutes (reset at halftime / every quarter) |
| `game_minutes_played` | Minutes accumulated by the shooter in the game |
| `stint_inferred` | The shooter was not on court according to the reconstruction |
| `score_margin` | Shooter team's margin before the shot |
| `is_home` | The shooter plays at home |
| `xShot`, `shot_residual` | Expected probability (out of sample) and residual |

## 4. 2014-15 shot log (defender distance)

* **Path:** `data/raw/external/shot_logs_2014/shot_logs_2014.csv` (generated by `scripts/download_shot_logs.py`).
* **Source:** Kaggle "NBA shot logs", OpenML mirror (CC0). 128,069 shots, 904 games, through 4 March 2015.
* **Key columns:** `SHOT_DIST` (ft), `PTS_TYPE`, `CLOSE_DEF_DIST` (nearest defender distance, ft), `CLOSEST_DEFENDER`, `SHOT_CLOCK`, `TOUCH_TIME`, `DRIBBLES`, `FGM`.
* **Use:** (a) table of the defender-distance effect for the simulator (`web/data/contest.json`), only between 1.5 and 8 ft, and relative to the typical defender distance for each shot distance (2014-15 median); (b) measure how much an expected-shot model improves when the defender is known (AUC 0.617 → 0.634).
* **Caution:** another era and another measurement system; the effect is association (defenders get closer to the best shooters and there are fast breaks with no defender). There is no key to join it with the 2021-25 seasons.
