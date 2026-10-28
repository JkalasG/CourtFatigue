"""
CourtFatigue data-quality audit.

Checks the raw data of every season (shots and play-by-play), verifies that both sources agree,
and counts how many shots are lost at each step until the final analysis.

Usage:  python scripts/data_quality.py        (uses the seasons in data/processed/by_season/)
Output: web/data/quality.json, DATA_QUALITY.md (English) and docs/es/CALIDAD_DE_DATOS.md (Spanish)

Read-only: it does not modify anything in the analysis.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from stint_calculator import season_paths  # noqa: E402

OUT_JSON = os.path.join("web", "data", "quality.json")
OUT_MD = {"en": "DATA_QUALITY.md", "es": os.path.join("docs", "es", "CALIDAD_DE_DATOS.md")}
PROCESSED = os.path.join("data", "processed", "shots_fatigue_processed.csv")
SHOT_COLS = ["GAME_ID", "GAME_EVENT_ID", "PLAYER_ID", "TEAM_ID", "PERIOD", "MINUTES_REMAINING", "SECONDS_REMAINING",
             "ACTION_TYPE", "SHOT_TYPE", "SHOT_ZONE_BASIC", "SHOT_DISTANCE", "LOC_X", "LOC_Y", "SHOT_MADE_FLAG", "GAME_DATE"]
LABELS = {"2021": "2021-22", "2022": "2022-23", "2023": "2023-24", "2024": "2024-25"}


def pct(a, b):
    return round(100.0 * a / b, 3) if b else 0.0


def audit_season(season):
    pbp_path, shots_path = season_paths(season)
    shots = pd.read_csv(shots_path, usecols=SHOT_COLS, low_memory=False)
    pbp = pd.read_csv(pbp_path, usecols=["GAME_ID", "EVENTNUM", "EVENTMSGTYPE", "PERIOD"], low_memory=False)
    n = len(shots)
    r = {"season": season, "label": LABELS.get(season, season), "n_shots_raw": n,
         "n_games": int(shots.GAME_ID.nunique())}

    # 1) missing values
    r["missing_pct"] = {c: pct(int(shots[c].isna().sum()), n) for c in SHOT_COLS}
    r["missing_any_pct"] = pct(int(shots[SHOT_COLS].isna().any(axis=1).sum()), n)

    # 2) duplicates
    r["duplicates"] = int(shots.duplicated(["GAME_ID", "GAME_EVENT_ID", "PLAYER_ID"]).sum())

    # 3) ranges and internal consistency
    d = shots.SHOT_DISTANCE
    r["dist_out_of_range"] = int(((d < 0) | (d > 94)).sum())
    r["dist_over_35"] = int((d > 35).sum())
    r["made_flag_invalid"] = int((~shots.SHOT_MADE_FLAG.isin([0, 1])).sum())
    r["period_invalid"] = int((~shots.PERIOD.between(1, 10)).sum())
    ot = shots.PERIOD > 4
    clock = shots.MINUTES_REMAINING * 60 + shots.SECONDS_REMAINING
    r["clock_invalid"] = int(((clock < 0) | (clock > np.where(ot, 300, 720))).sum())
    # declared distance must match the coordinates (LOC in tenths of a foot from the hoop)
    diff = (np.hypot(shots.LOC_X, shots.LOC_Y) / 10.0 - d).abs()
    r["coord_vs_dist_gt3ft"] = int((diff > 3).sum())
    r["coord_vs_dist_pct"] = pct(r["coord_vs_dist_gt3ft"], n)
    # shot type vs. distance (a three cannot come from very close, a two from very far)
    is3 = shots.SHOT_TYPE.astype(str).str.startswith("3")
    r["three_under_21ft"] = int((is3 & (d < 21)).sum())
    r["two_over_25ft"] = int((~is3 & (d > 25)).sum())

    # 4) cross-check against the play-by-play (other source): made and missed shots per game
    fg = pbp[pbp.EVENTMSGTYPE.isin([1, 2])]
    g = pd.DataFrame({
        "s_att": shots.groupby("GAME_ID").size(),
        "p_att": fg.groupby("GAME_ID").size(),
        "s_made": shots.groupby("GAME_ID").SHOT_MADE_FLAG.sum(),
        "p_made": fg[fg.EVENTMSGTYPE == 1].groupby("GAME_ID").size(),
    }).fillna(0)
    inter = g[(g.s_att > 0) & (g.p_att > 0)]
    r["games_in_shots_not_pbp"] = int(((g.s_att > 0) & (g.p_att == 0)).sum())
    r["games_match_exact_pct"] = pct(int(((inter.s_att == inter.p_att) & (inter.s_made == inter.p_made)).sum()), len(inter))
    r["games_diff_le2_pct"] = pct(int(((inter.s_att - inter.p_att).abs() <= 2).sum()), len(inter))
    r["attempts_shots"] = int(inter.s_att.sum())
    r["attempts_pbp"] = int(inter.p_att.sum())
    r["fg_pct_shots"] = round(100.0 * inter.s_made.sum() / inter.s_att.sum(), 2)
    r["fg_pct_pbp"] = round(100.0 * inter.p_made.sum() / inter.p_att.sum(), 2)

    # 5) traits to compare seasons
    r["shots_per_game"] = round(n / r["n_games"], 1)
    r["three_share_pct"] = round(100.0 * is3.mean(), 2)
    r["fg_pct"] = round(100.0 * shots.SHOT_MADE_FLAG.mean(), 2)
    r["mean_dist_ft"] = round(float(d.mean()), 2)

    # 6) funnel and sanity of the derived variables
    st_path = os.path.join("data", "processed", "by_season", f"stints_{season}.csv")
    if os.path.exists(st_path):
        st = pd.read_csv(st_path, usecols=["stint_minutes", "stint_minutes_quarter", "game_minutes_played", "stint_inferred",
                                           "PERIOD", "score_margin"], low_memory=False)
        r["n_with_stint"] = len(st)
        r["n_without_stint"] = n - len(st)
        r["n_inferred"] = int(st.stint_inferred.sum())
        r["inferred_pct"] = pct(r["n_inferred"], len(st))
        r["stint_min_max"] = round(float(st.stint_minutes.max()), 1)
        r["stint_quarter_gt12"] = int((st.stint_minutes_quarter > 12.05).sum())
        lim = 48 + 5 * np.maximum(st.PERIOD - 4, 0)
        over = st.game_minutes_played > lim + 0.05
        r["game_minutes_gt_possible"] = int(over.sum())
        r["game_minutes_gt_possible_main"] = int((over & ~st.stint_inferred).sum())   # those that enter the main analysis
        r["stint_negative"] = int((st.stint_minutes < 0).sum())
        r["score_margin_missing"] = int(st.score_margin.isna().sum())
    return r


def funnel(seasons):
    raw = sum(s["n_shots_raw"] for s in seasons)
    with_stint = sum(s.get("n_with_stint", 0) for s in seasons)
    steps = [("raw", raw), ("stint", with_stint)]
    if os.path.exists(PROCESSED):
        p = pd.read_csv(PROCESSED, usecols=["stint_inferred", "xShot"], low_memory=False)
        steps += [("xshot", int(p.xShot.notna().sum())), ("reliable", int((~p.stint_inferred).sum()))]
    rows, prev = [], None
    for key, n in steps:
        rows.append({"step": key, "n": int(n), "lost": (int(prev - n) if prev is not None else 0)})
        prev = n
    return rows


# ------------------------------------------------------------------ report text (EN / ES)
TXT = {
    "en": {
        "title": "Data quality",
        "intro": "What we checked in the data before analysing it, what we found and what we did about each finding. "
                 "Generated by `python scripts/data_quality.py` (repeatable). Back to the [README]({readme}).",
        "h_funnel": "1. From raw data to the analysis (funnel)",
        "funnel_cols": "| Step | Shots | Lost | Reason |\n|---|---:|---:|---|",
        "steps": {
            "raw": ("Raw shots (4 seasons)", "NBA shot records, all seasons"),
            "stint": ("With minutes on court rebuilt", "Shots that cannot be matched to the play-by-play are lost"),
            "xshot": ("With expected shot (xShot)", "Rows with missing model inputs are dropped"),
            "reliable": ("With reliable stint (main analysis)", "Inferred stints are excluded"),
        },
        "h_checks": "2. What was checked in each season",
        "cmp": "Check",
        "shots": "Shots", "games": "Games",
        "missing": "Rows with any missing value", "dups": "Duplicate shots",
        "made_bad": "Made flag other than 0/1", "clock_bad": "Clock out of range",
        "coord": "Distance inconsistent with coordinates (>3 ft)",
        "three_close": "Threes from under 21 ft", "two_far": "Twos from over 25 ft",
        "over35": "Shots over 35 ft (clipped to 35)",
        "h_cross": "3. Do the two files agree?",
        "cross_intro": "Shots come from one file and plays from another. For each game we compare how many shots and how many makes each file has.",
        "match": "Games that match exactly", "le2": "Games differing by 2 shots or fewer",
        "att": "Attempts: shot file / play-by-play", "fgp": "FG%: shots / play-by-play", "nopbp": "Games without play-by-play",
        "h_stint": "4. Rebuilt minutes on court",
        "nostint": "Shots without rebuilt minutes", "inferred": "Inferred stints (excluded from the main analysis)",
        "maxstint": "Longest stint (min)", "q12": "Quarter minutes above 12",
        "over": "Minutes played above what is possible (all / in the main analysis)", "neg": "Negative minutes",
        "h_comp": "5. Are the seasons comparable?",
        "spg": "Shots per game (both teams)", "three": "Three-point share", "fg": "Overall FG%", "dist": "Average distance (ft)",
        "h_dec": "6. What we do about the findings",
        "dec": [
            "**Distances over 35 ft** (half-court heaves): clipped to 35 ft for the expected-shot model so a few extreme shots do not distort the curve.",
            "**Inferred stints** (the shooter does not appear on court according to the substitutions): flagged and excluded from the main analysis; they enter only in a robustness check.",
            "**Shots without rebuilt minutes:** dropped, because fatigue cannot be assigned.",
            "**Missing values and duplicates:** none found in the columns the analysis uses; the code still drops incomplete rows and removes duplicates by game-event-player in case the source changes.",
            "**Minutes played above what is possible** ({tot} shots out of {raw}; {inf} with inferred stint and therefore outside the main analysis): games where a substitution out is missing. The other {main} are in the main analysis; they are a negligible share and are not corrected one by one.",
            "**Minor differences with the play-by-play** (under 1% of games, by 1 or 2 shots): they come from the source; they are not corrected because overall FG% matches to the hundredth in both sources.",
            "**Clock reset at halftime:** the consecutive-minutes counter resets in the third quarter, and an alternative that resets every quarter is tested.",
        ],
        "h_limits": "7. What these checks cannot detect",
        "limits": [
            "Systematic source errors (e.g. a shot logged at the wrong position but within range).",
            "A coach substituting someone because of visible fatigue: that is selection bias, not a data error (see *Limitations* in the README).",
            "Substitutions were not verified against video; the stint is rebuilt from the recorded plays.",
        ],
    },
    "es": {
        "title": "Calidad de los datos",
        "intro": "Qué comprobamos en los datos antes de analizarlos, qué encontramos y qué hicimos con cada hallazgo. "
                 "Lo genera `python scripts/data_quality.py` (se puede repetir). Volver al [README]({readme}).",
        "h_funnel": "1. De los datos crudos al análisis (embudo)",
        "funnel_cols": "| Paso | Tiros | Perdidos | Motivo |\n|---|---:|---:|---|",
        "steps": {
            "raw": ("Tiros crudos (4 temporadas)", "Registro de tiros de la NBA, todas las temporadas"),
            "stint": ("Con minutos en cancha reconstruidos", "Se pierden los tiros que no se pueden unir con el play-by-play"),
            "xshot": ("Con tiro esperado (xShot) calculado", "Se descartan filas con datos faltantes en las variables del modelo"),
            "reliable": ("Con stint fiable (análisis principal)", "Se excluyen los stints inferidos"),
        },
        "h_checks": "2. Qué se comprobó en cada temporada",
        "cmp": "Comprobación",
        "shots": "Tiros", "games": "Partidos",
        "missing": "Filas con algún dato faltante", "dups": "Tiros duplicados",
        "made_bad": "Marca de anotado distinta de 0/1", "clock_bad": "Reloj fuera de rango",
        "coord": "Distancia con coordenadas incoherentes (>3 ft)",
        "three_close": "Triples desde menos de 21 ft", "two_far": "Dobles desde más de 25 ft",
        "over35": "Tiros de más de 35 ft (se recortan a 35)",
        "h_cross": "3. ¿Coinciden los dos archivos entre sí?",
        "cross_intro": "Los tiros vienen de un archivo y las jugadas de otro. Comparamos, partido por partido, cuántos tiros y cuántos anotados tiene cada uno.",
        "match": "Partidos que coinciden exactamente", "le2": "Partidos con diferencia de 2 tiros o menos",
        "att": "Intentos: archivo de tiros / play-by-play", "fgp": "% de acierto: tiros / play-by-play", "nopbp": "Partidos sin play-by-play",
        "h_stint": "4. Minutos en cancha reconstruidos",
        "nostint": "Tiros sin minutos reconstruidos", "inferred": "Stints inferidos (excluidos del análisis principal)",
        "maxstint": "Stint más largo (min)", "q12": "Minutos en el cuarto por encima de 12",
        "over": "Minutos jugados por encima de lo posible (todos / en el análisis principal)", "neg": "Minutos negativos",
        "h_comp": "5. ¿Son comparables las temporadas?",
        "spg": "Tiros por partido (ambos equipos)", "three": "Porcentaje de triples", "fg": "Acierto global", "dist": "Distancia media (ft)",
        "h_dec": "6. Qué hacemos con lo encontrado",
        "dec": [
            "**Distancias de más de 35 ft** (tiros desde media cancha): se recortan a 35 ft para el modelo de tiro esperado, para que unos pocos tiros extremos no distorsionen la curva.",
            "**Stints inferidos** (el tirador no aparece como jugador en cancha según las sustituciones): se marcan y se excluyen del análisis principal; entran solo en una prueba de robustez.",
            "**Tiros sin minutos reconstruidos:** se descartan, porque no se puede asignar fatiga.",
            "**Datos faltantes y duplicados:** no se encontraron en las columnas que usa el análisis; aun así el código descarta filas incompletas y elimina duplicados por la clave partido-evento-jugador, por si cambia la fuente.",
            "**Minutos jugados por encima de lo posible** ({tot} tiros de {raw}; {inf} con stint inferido y por eso fuera del análisis principal): son partidos donde falta registrar una salida a banca. Los otros {main} están en el análisis principal; son una fracción mínima de la muestra y no se corrigen individualmente.",
            "**Diferencias menores con el play-by-play** (menos del 1% de los partidos, de 1 o 2 tiros): vienen de la fuente; no se corrigen porque el acierto global coincide al centésimo en las dos fuentes.",
            "**Reloj reiniciado en el medio tiempo:** el contador de minutos seguidos se reinicia en el tercer cuarto, y se prueba una alternativa que lo reinicia en cada cuarto.",
        ],
        "h_limits": "7. Lo que estas comprobaciones no pueden detectar",
        "limits": [
            "Errores sistemáticos de la fuente (por ejemplo, un tiro registrado con la posición equivocada pero dentro de rango).",
            "Que un entrenador sustituyera a alguien por cansancio visible: eso es un sesgo de selección, no un error de datos (ver *Limitaciones* en el README).",
            "No se verificaron las sustituciones contra el video; el stint se reconstruye con las jugadas registradas.",
        ],
    },
}


def write_md(res, lang):
    S, t = res["seasons"], TXT[lang]
    L = []
    a = L.append

    def table(rows):
        a("| " + t["cmp"] + " | " + " | ".join(s["label"] for s in S) + " |\n|---|" + "---:|" * len(S))
        for name, fn in rows:
            a(f"| {name} | " + " | ".join(str(fn(s)) for s in S) + " |")
        a("")

    a("[English](DATA_QUALITY.md) | [Español](docs/es/CALIDAD_DE_DATOS.md)\n" if lang == "en"
      else "[English](../../DATA_QUALITY.md) | [Español](CALIDAD_DE_DATOS.md)\n")
    a(f"# {t['title']}\n")
    a(t["intro"].format(readme="README.md" if lang == "en" else "../../README.es.md") + "\n")
    a(f"## {t['h_funnel']}\n")
    a(t["funnel_cols"])
    for f in res["funnel"]:
        name, why = t["steps"][f["step"]]
        a(f"| {name} | {f['n']:,} | {f['lost']:,} | {why} |")
    a("")
    a(f"## {t['h_checks']}\n")
    table([
        (t["shots"], lambda s: f"{s['n_shots_raw']:,}"), (t["games"], lambda s: f"{s['n_games']:,}"),
        (t["missing"], lambda s: f"{s['missing_any_pct']}%"), (t["dups"], lambda s: f"{s['duplicates']:,}"),
        (t["made_bad"], lambda s: f"{s['made_flag_invalid']:,}"), (t["clock_bad"], lambda s: f"{s['clock_invalid']:,}"),
        (t["coord"], lambda s: f"{s['coord_vs_dist_gt3ft']:,} ({s['coord_vs_dist_pct']}%)"),
        (t["three_close"], lambda s: f"{s['three_under_21ft']:,}"), (t["two_far"], lambda s: f"{s['two_over_25ft']:,}"),
        (t["over35"], lambda s: f"{s['dist_over_35']:,}"),
    ])
    a(f"## {t['h_cross']}\n")
    a(t["cross_intro"] + "\n")
    table([
        (t["match"], lambda s: f"{s['games_match_exact_pct']}%"), (t["le2"], lambda s: f"{s['games_diff_le2_pct']}%"),
        (t["att"], lambda s: f"{s['attempts_shots']:,} / {s['attempts_pbp']:,}"),
        (t["fgp"], lambda s: f"{s['fg_pct_shots']} / {s['fg_pct_pbp']}"), (t["nopbp"], lambda s: f"{s['games_in_shots_not_pbp']:,}"),
    ])
    a(f"## {t['h_stint']}\n")
    table([
        (t["nostint"], lambda s: f"{s.get('n_without_stint', 0):,}"), (t["inferred"], lambda s: f"{s.get('inferred_pct', 0)}%"),
        (t["maxstint"], lambda s: s.get("stint_min_max", 0)), (t["q12"], lambda s: f"{s.get('stint_quarter_gt12', 0):,}"),
        (t["over"], lambda s: f"{s.get('game_minutes_gt_possible', 0):,} / {s.get('game_minutes_gt_possible_main', 0):,}"),
        (t["neg"], lambda s: f"{s.get('stint_negative', 0):,}"),
    ])
    a(f"## {t['h_comp']}\n")
    table([
        (t["spg"], lambda s: s["shots_per_game"]), (t["three"], lambda s: f"{s['three_share_pct']}%"),
        (t["fg"], lambda s: f"{s['fg_pct']}%"), (t["dist"], lambda s: s["mean_dist_ft"]),
    ])
    tot = sum(s.get("game_minutes_gt_possible", 0) for s in S)
    main = sum(s.get("game_minutes_gt_possible_main", 0) for s in S)
    a(f"## {t['h_dec']}\n")
    for line in t["dec"]:
        a("- " + line.format(tot=tot, main=main, inf=tot - main, raw=f"{sum(s['n_shots_raw'] for s in S):,}"))
    a("")
    a(f"## {t['h_limits']}\n")
    for line in t["limits"]:
        a("- " + line)
    a("")
    path = OUT_MD[lang]
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    open(path, "w", encoding="utf-8").write("\n".join(L))


def main():
    folder = os.path.join("data", "processed", "by_season")
    seasons = sorted(f.split("_")[1].split(".")[0] for f in os.listdir(folder) if f.startswith("stints_") and f.endswith(".csv"))
    print("seasons:", seasons)
    S = []
    for s in seasons:
        print("auditing", s, "...")
        S.append(audit_season(s))
    res = {"seasons": S, "funnel": funnel(S)}
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    for lang in ("en", "es"):
        write_md(res, lang)
    print("done ->", OUT_JSON, ",", OUT_MD["en"], "and", OUT_MD["es"])


if __name__ == "__main__":
    main()
