# 📊 Diccionario y Documentación de Datasets — CourtFatigue

Este directorio contiene los datos de la **Temporada Regular de la NBA 2023–24 (1,230 partidos completos)** utilizados por **CourtFatigue** para estimar el impacto de la fatiga en el rendimiento de tiro de los jugadores.

---

## 📁 Estructura del Directorio `data/`

```text
data/
├── raw/                                 # Datasets originales sin modificar
│   ├── shotdetail_2024.csv              # 219,527 tiros con coordenadas y zonas
│   └── nbastats_2024.csv                # Play-by-play completo y sustituciones
├── processed/                           # Datasets procesados y listos para modelado
│   └── (generado por pipeline)          # Tiros con stint_minutes, xShot y residuos
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
│  • stint_minutes        (Minutos ininterrumpidos)      │
│  • total_game_minutes   (Carga acumulada en el juego)  │
│  • xShot                (Probabilidad base de acierto) │
│  • fatigue_residual     (Acierto Real - xShot)         │
│  • fatigue_bucket       (Rango: 0-2m, 2-5m, 8-10m...)  │
└────────────────────────────────────────────────────────┘
```

1. **Reconstrucción de Quintetos Iniciales:** Al inicio de cada periodo (`PERIOD`, reloj `12:00`), se deduce qué 5 jugadores de cada equipo están en pista. Su contador de minutos continuos arranca en `0.0`.
2. **Cronómetro Continuo de Stints:** Cada segundo de reloj transcurrido suma tiempo a los 10 jugadores en pista.
3. **Manejo de Sustituciones (`EVENTMSGTYPE = 8`):**
   * El jugador que sale (`PLAYER1_ID`) congela su contador y sale de la lista activa.
   * El jugador que entra (`PLAYER2_ID`) se incorpora con su contador de minutos continuos reiniciado a `0.0`.
4. **Asignación del Tiro:** Al ocurrir un tiro (`GAME_EVENT_ID`), se le asigna el valor exacto de `stint_minutes` que acumulaba ese jugador en ese instante.
5. **Cálculo del Tiro Esperado ($xShot$) y Residuo:**
   * $xShot$: Probabilidad promedio esperada en base a `SHOT_DISTANCE`, `SHOT_ZONE_BASIC` y `ACTION_TYPE`.
   * $\text{Residuo} = \text{SHOT\_MADE\_FLAG} - xShot$.
   * Si el residuo disminuye significativamente conforme `stint_minutes` supera los 8–10 minutos, se comprueba la curva de fatiga.
