# 📊 Diccionario y Documentación de Datasets — CourtFatigue

Este directorio contiene los datos usados por **CourtFatigue** para estimar el impacto de la fatiga en el rendimiento de tiro:

| Conjunto | Contenido | Uso |
| --- | --- | --- |
| **NBA 2021-22, 2022-23, 2023-24, 2024-25** (temporadas regulares) | 4 × 1,230 partidos, 872,158 tiros con coordenadas y su play-by-play | Análisis principal |
| **Registro de tiros 2014-15** ("NBA shot logs", CC0) | 128,069 tiros con distancia al defensor más cercano, reloj de posesión, toques y regates | Simulador 3D y medición de la limitación por falta de datos del defensor. **No se cruza** con las otras temporadas |

**Convención de nombres:** en los archivos de origen, la temporada `2024` es la 2024-25 (empieza en octubre de 2024), la `2023` es la 2023-24, y así sucesivamente.

---

## 📁 Estructura del Directorio `data/`

```text
data/
├── raw/                                 # Datasets originales sin modificar
│   ├── shotdetail_2024.csv              # 2024-25: 219,527 tiros con coordenadas y zonas
│   ├── nbastats_2024.csv                # 2024-25: play-by-play completo (94 MB; no versionado)
│   ├── seasons/<año>/                   # 2021, 2022, 2023: mismos dos archivos (scripts/download_seasons.py)
│   └── external/shot_logs_2014/         # 2014-15 con distancia al defensor (scripts/download_shot_logs.py)
├── processed/                           # Datasets procesados y listos para modelado (regenerables)
│   ├── by_season/stints_<año>.csv       # tiros + minutos seguidos, marcador y local, por temporada
│   ├── shots_fatigue_processed.csv      # 4 temporadas + xShot validado fuera de muestra + residuo
│   └── xshot_metrics.json               # log-loss, Brier, AUC y calibración del xShot (cruzada y temporal)
└── README.md                            # Este documento de especificación
```

---

## 🎯 1. Dataset: `shotdetail_2024.csv` (Registro Espacial de Tiros)

* **Ruta:** `data/raw/shotdetail_2024.csv`
* **Registros:** 219,527 tiros intentados en temporada regular.
* **Fuente:** NBA Stats API (`ShotChartDetail` endpoint).
* **Propósito en CourtFatigue:** Aporta las coordenadas cartesianas exactas, distancia al aro, dificultad técnica de la jugada, zona de la cancha y el resultado de cada lanzamiento.

### Diccionario de Columnas

| Columna | Tipo de Dato | Descripción | Ejemplo / Valores Posibles |
| :--- | :--- | :--- | :--- |
| `GRID_TYPE` | `String` | Identificador de tipo de reporte | `"Shot Chart Detail"` |
| `GAME_ID` | `String` / `Int` | Identificador único oficial del partido en la NBA (10 dígitos) | `"0022400001"` |
| `GAME_EVENT_ID` | `Int` | Número correlativo del evento dentro del partido. **Enlaza directamente con `EVENTNUM` del Play-by-Play.** | `7`, `10`, `45` |
| `PLAYER_ID` | `Int` | ID numérico oficial del jugador en la NBA | `1628369` (Jayson Tatum), `201939` (Stephen Curry) |
| `PLAYER_NAME` | `String` | Nombre completo del jugador | `"Jayson Tatum"`, `"Nikola Jokić"` |
| `TEAM_ID` | `Int` | ID numérico oficial de la franquicia | `1610612738` (Boston Celtics) |
| `TEAM_NAME` | `String` | Nombre completo de la franquicia | `"Boston Celtics"`, `"Denver Nuggets"` |
| `PERIOD` | `Int` | Periodo o cuarto en el que ocurre el tiro | `1`, `2`, `3`, `4` (5+ para prórrogas) |
| `MINUTES_REMAINING` | `Int` | Minutos restantes en el reloj del cuarto | `11`, `4`, `0` |
| `SECONDS_REMAINING` | `Int` | Segundos restantes en el minuto actual | `43`, `12`, `0` |
| `EVENT_TYPE` | `String` | Resultado textual del tiro | `"Made Shot"`, `"Missed Shot"` |
| `ACTION_TYPE` | `String` | Mecánica o tipo específico de tiro ejecutado | `"Jump Shot"`, `"Pullup Jump Shot"`, `"Step Back Jump Shot"`, `"Driving Layup"`, `"Fadeaway Bank Jump Shot"` |
| `SHOT_TYPE` | `String` | Categoría general de valor de anotación | `"2PT Field Goal"`, `"3PT Field Goal"` |
| `SHOT_ZONE_BASIC` | `String` | Zona estándar de la cancha según geometría NBA | `"Restricted Area"`, `"In The Paint (Non-RA)"`, `"Mid-Range"`, `"Left Corner 3"`, `"Right Corner 3"`, `"Above the Break 3"`, `"Backcourt"` |
| `SHOT_ZONE_AREA` | `String` | Orientación lateral del tiro respecto al aro | `"Center(C)"`, `"Left Side(L)"`, `"Left Side Center(LC)"`, `"Right Side Center(RC)"`, `"Right Side(R)"`, `"Back Court(BC)"` |
| `SHOT_ZONE_RANGE` | `String` | Categoría de distancia al aro | `"Less Than 8 ft."`, `"8-16 ft."`, `"16-24 ft."`, `"24+ ft."`, `"Back Court Shot"` |
| `SHOT_DISTANCE` | `Int` | Distancia euclidiana exacta medida desde el aro en pies | `26` (triple), `4` (bandeja), `14` (media distancia) |
| `LOC_X` | `Int` | Coordenada horizontal del tiro en la cancha (eje X, décimas de pie). `0` es el centro de la cancha/aro. | `-168` (hacia la izquierda), `120` (hacia la derecha) |
| `LOC_Y` | `Int` | Coordenada vertical del tiro en la cancha (eje Y, décimas de pie). `0` es la línea de fondo del aro. | `205` (hacia el centro de la cancha), `-10` (detrás del aro) |
| `SHOT_ATTEMPTED_FLAG` | `Int` | Indicador de tiro intentado (siempre 1) | `1` |
| `SHOT_MADE_FLAG` | `Int` | **Variable Objetivo:** `1` si el tiro entró a la canasta, `0` si fue fallado. | `1` o `0` |
| `GAME_DATE` | `String` | Fecha en que se disputó el encuentro (`YYYYMMDD`) | `"20241112"` |
| `HTM` | `String` | Abreviatura del equipo local (*Home Team*) | `"BOS"`, `"DEN"`, `"LAL"` |
| `VTM` | `String` | Abreviatura del equipo visitante (*Visitor Team*) | `"ATL"`, `"GSW"`, `"MIA"` |

---

## ⏱️ 2. Dataset: `nbastats_2024.csv` (Play-by-Play & Sustituciones)

* **Ruta:** `data/raw/nbastats_2024.csv`
* **Registros:** ~550,000+ eventos de juego de los 1,230 partidos.
* **Fuente:** NBA Stats API (`PlayByPlayV2` endpoint).
* **Propósito en CourtFatigue:** Rastrear cronológicamente cuándo entra y sale cada jugador para calcular con precisión de segundos los **minutos ininterrumpidos en pista (*stints*)**.

### Diccionario de Columnas Clave

| Columna | Tipo | Descripción y Uso en CourtFatigue |
| :--- | :--- | :--- |
| `GAME_ID` | `String` / `Int` | Identificador del partido (clave de cruce con `shotdetail`). |
| `EVENTNUM` | `Int` | Número correlativo del evento dentro del partido. **Clave de unión directa con `GAME_EVENT_ID`.** |
| `EVENTMSGTYPE` | `Int` | **Código fundamental de evento.** Define la acción ocurrida: <br>• `1`: Tiro anotado <br>• `2`: Tiro fallado <br>• `3`: Tiro libre <br>• `4`: Rebote <br>• `5`: Pérdida de posesión (*Turnover*) <br>• `6`: Falta personal <br>• **`8`: Sustitución de jugador (clave para CourtFatigue)** <br>• `9`: Tiempo muerto (*Timeout*) <br>• `10`: Salto entre dos (*Jump Ball*) <br>• `12`: Inicio de periodo / cuarto <br>• `13`: Fin de periodo / cuarto |
| `EVENTMSGACTIONTYPE` | `Int` | Subclasificación técnica de la acción del evento. |
| `PERIOD` | `Int` | Periodo o cuarto (1 a 4 reglamentarios, 5+ prórrogas). |
| `WCTIMESTRING` | `String` | Hora de reloj de pared en la arena (ej. `"7:11 PM"`). |
| `PCTIMESTRING` | `String` | **Reloj del cuarto (*Period Clock*):** Tiempo restante en formato `MM:SS` (ej. `"11:43"`). |
| `HOMEDESCRIPTION` | `String` | Descripción de la jugada referente al equipo local. |
| `NEUTRALDESCRIPTION` | `String` | Descripción de eventos neutrales (ej. `"Start of 1st Period"`). |
| `VISITORDESCRIPTION` | `String` | Descripción referente al equipo visitante. |
| `SCORE` | `String` | Marcador acumulado tras el evento (ej. `"104 - 101"`). |
| `SCOREMARGIN` | `String` | Diferencia en puntos entre el equipo local y el visitante. |
| `PERSON1TYPE` | `Int` | Tipo de persona 1 (`4` = Jugador Local, `5` = Jugador Visitante). |
| `PLAYER1_ID` | `Int` | ID del jugador principal. **En eventos `EVENTMSGTYPE = 8` (Sustitución), representa al JUGADOR QUE SALE a la banca.** |
| `PLAYER1_NAME` | `String` | Nombre del jugador principal (**Jugador que SALE en sustituciones**). |
| `PLAYER1_TEAM_ID` | `Int` | ID de la franquicia del jugador 1. |
| `PLAYER1_TEAM_ABBREVIATION` | `String` | Abreviatura del equipo (ej. `"BOS"`, `"LAL"`). |
| `PERSON2TYPE` | `Int` | Tipo de persona 2. |
| `PLAYER2_ID` | `Int` | ID del jugador secundario. **En eventos `EVENTMSGTYPE = 8` (Sustitución), representa al JUGADOR QUE INGRESA a la cancha.** |
| `PLAYER2_NAME` | `String` | Nombre del jugador secundario (**Jugador que INGRESA en sustituciones**). |
| `PLAYER3_ID` / `PLAYER3_NAME` | `Int` / `String` | Tercer actor del evento (asistente en canasta, taponador en tiro errado o jugador víctima de falta). |

---

## 🔗 3. Cómo se Unen y Operan los Datasets (Algoritmo CourtFatigue)

```
┌────────────────────────────────────────────────────────┐
│                   shotdetail_2024.csv                  │
│  [GAME_ID] + [GAME_EVENT_ID]                           │
│  Coordenadas (LOC_X, LOC_Y) + SHOT_DISTANCE + ACTION   │
└───────────────────────────┬────────────────────────────┘
                            │ Cruce relacional
                            │ GAME_ID == GAME_ID
                            │ GAME_EVENT_ID == EVENTNUM
                            ▼
┌────────────────────────────────────────────────────────┐
│                   nbastats_2024.csv                    │
│  [GAME_ID] + [EVENTNUM]                                │
│  EVENTMSGTYPE == 8 (Sustituciones: SALE -> ENTRA)      │
│  Reloj PCTIMESTRING (Cálculo de segundos en pista)     │
└───────────────────────────┬────────────────────────────┘
                            │ Pipeline de Inferencia
                            ▼
┌────────────────────────────────────────────────────────┐
│        DATASET PROCESADO (data/processed/)             │
│  • stint_minutes        (Minutos seguidos, medio       │
│                          tiempo reinicia)              │
│  • game_minutes_played  (Carga acumulada en el juego)  │
│  • xShot                (Probabilidad base de acierto) │
│  • shot_residual        (Acierto Real - xShot)         │
│  • stint_inferred       (tirador no figuraba en pista) │
└────────────────────────────────────────────────────────┘
```

1. **Quién está en pista:** el PBP **no registra las sustituciones hechas entre cuartos**. En cada cuarto se considera "ya en pista" a quien aparece activo antes de entrar como sustituto; si además estaba en pista al cerrar el cuarto anterior, conserva su contador. Un tirador que no figura en pista se marca con `stint_inferred = True` (~0.3% de los tiros) y se excluye del análisis principal.
2. **Cronómetro de stints:** solo cuenta tiempo de juego (los descansos no suman). `stint_minutes` sigue entre Q1→Q2 y Q3→Q4 y **se reinicia en el medio tiempo**; `stint_minutes_quarter` se reinicia en cada cuarto (prueba de sensibilidad).
3. **Sustituciones (`EVENTMSGTYPE = 8`):** `PLAYER1_ID` sale y `PLAYER2_ID` entra con el contador en 0.
4. **Asignación del tiro:** cada tiro recibe `stint_minutes`, `stint_minutes_quarter`, `game_minutes_played` (carga acumulada en el partido), `score_margin` (ventaja del equipo del tirador **antes** del tiro, a partir de `SCOREMARGIN`, que es local − visitante) e `is_home` (`PERSON1TYPE = 4`).
5. **Tiro esperado (xShot) y residuo:** gradient boosting con distancia, coordenadas, zona, tipo de tiro, periodo y tiempo restante (sin minutos en pista ni identidad del jugador). Se predice fuera de muestra con validación cruzada agrupada por partido; además se evalúa con una prueba temporal (entrenar con las temporadas anteriores, evaluar en la última). `shot_residual = SHOT_MADE_FLAG - xShot`.
6. **Comparación dentro de temporada:** cada jugador se compara con su promedio **en esa temporada** (`dev = shot_residual − promedio del jugador-temporada`), porque su nivel cambia de un año a otro.
7. **Inferencia:** el efecto de fatiga se estima en `src/fatigue_stats.py` (contraste ≥ 8 min contra 2-6 min por jugador, pendiente con efectos fijos, efectos aleatorios, corrección por comparaciones múltiples y prueba placebo).
8. **Calendario:** `b2b` (el equipo jugó el día anterior) se calcula en `scripts/build_web_data.py` con `GAME_DATE`.

### Columnas añadidas por el pipeline

| Columna | Descripción |
| --- | --- |
| `SEASON` | Temporada de origen (`2021`…`2024`) |
| `stint_minutes` / `stint_minutes_quarter` | Minutos seguidos (reinicia en el medio tiempo / en cada cuarto) |
| `game_minutes_played` | Minutos acumulados por el tirador en el partido |
| `stint_inferred` | El tirador no figuraba en pista según la reconstrucción |
| `score_margin` | Ventaja del equipo del tirador antes del tiro |
| `is_home` | El tirador juega de local |
| `xShot`, `shot_residual` | Probabilidad esperada (fuera de muestra) y residuo |

## 🛡️ 4. Registro de tiros 2014-15 (distancia al defensor)

* **Ruta:** `data/raw/external/shot_logs_2014/shot_logs_2014.csv` (se genera con `scripts/download_shot_logs.py`).
* **Fuente:** Kaggle "NBA shot logs", espejo de OpenML (CC0). 128,069 tiros, 904 partidos, hasta el 4 de marzo de 2015.
* **Columnas clave:** `SHOT_DIST` (pies), `PTS_TYPE`, `CLOSE_DEF_DIST` (distancia al defensor más cercano, pies), `CLOSEST_DEFENDER`, `SHOT_CLOCK`, `TOUCH_TIME`, `DRIBBLES`, `FGM`.
* **Uso:** (a) tabla del efecto de la distancia al defensor para el simulador (`web/data/contest.json`), solo entre 1.5 y 8 pies, y relativa a la distancia típica del defensor para cada distancia de tiro (mediana en 2014-15); (b) medir cuánto mejora un tiro esperado al conocer al defensor (AUC 0.617 → 0.634).
* **Cuidado:** otra época y otro sistema de medición; el efecto es asociación (los defensores se acercan más a los mejores tiradores y hay contraataques sin defensor). No hay una clave que permita cruzarlo con las temporadas 2021-25.
