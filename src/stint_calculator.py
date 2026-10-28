"""
CourtFatigue - Módulo de Cálculo de Stints (Minutos Seguidos en Cancha)
Autor: Proyecto CourtFatigue (AQX Sports Analytics Data Bowl 4.0)

Reconstruye quién está en pista en cada instante usando las sustituciones del
Play-by-Play (nbastats) y asocia a cada tiro (shotdetail) cuántos minutos
seguidos llevaba el tirador en cancha.

Reglas (declaradas, porque cambian los resultados):
  * El contador cuenta SOLO tiempo de juego (los descansos no suman).
  * stint_minutes (regla principal): el contador sigue entre Q1->Q2 y Q3->Q4
    (descansos de 2 min) y se REINICIA en el medio tiempo (antes del Q3).
  * stint_minutes_quarter (análisis de sensibilidad): se reinicia en cada cuarto.
  * El PBP NO registra las sustituciones hechas entre cuartos. En cada cuarto se
    toma como "ya en pista" a quien aparece activo antes de entrar como sustituto.
    Si además estaba en pista al cerrar el cuarto anterior, conserva su contador;
    si no, su contador arranca al inicio del cuarto (entró en el descanso).
  * Si un tirador no figuraba en pista según la reconstrucción (p. ej. un titular
    sin eventos previos), se asume que entró al inicio del cuarto y el tiro se
    marca con stint_inferred = True para poder excluirlo en el análisis.
"""

import sys
import os
import pandas as pd
import numpy as np

# Asegurar codificación UTF-8 en consola
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

HALFTIME_PERIOD = 3  # el contador se reinicia al comenzar este periodo
BUCKETS = [
    ("0-2 min (Inicio)", 0.0, 2.0),
    ("2-5 min (Ritmo Óptimo)", 2.0, 5.0),
    ("5-8 min (Carga Media)", 5.0, 8.0),
    ("8-10 min (Zona Crítica)", 8.0, 10.0),
    ("10-12 min (Largo)", 10.0, 12.0),
    ("12+ min (Muy largo)", 12.0, 99.0),
]


def period_start(period: int) -> int:
    """Segundos de juego transcurridos al comenzar el periodo (sin descansos)."""
    return (period - 1) * 720 if period <= 4 else 4 * 720 + (period - 5) * 300


def period_length(period: int) -> int:
    return 720 if period <= 4 else 300


def parse_clock_to_seconds(clock_str: str) -> int:
    """Convierte 'MM:SS' a segundos restantes en el cuarto ('11:43' -> 703)."""
    try:
        parts = str(clock_str).strip().split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except Exception:
        return 0


def _valid_player(pid, ptype) -> bool:
    return ptype in (4, 5) and pid == pid and pid > 0  # pid == pid descarta NaN


def reconstruct_game_stints(pbp_game: pd.DataFrame) -> list:
    """
    Recorre un partido y devuelve, para cada tiro (EVENTMSGTYPE 1 y 2), una tupla
    (GAME_ID, EVENTNUM, PLAYER_ID, stint_seg, stint_seg_cuarto, seg_jugados, inferido,
    ventaja_del_tirador, es_local). La ventaja usa el marcador ANTES del tiro.
    """
    rows = []
    on = {}    # team_id -> {player_id: [entrada_juego, entrada_stint, inferido]}
    acc = {}   # player_id -> segundos de juego acumulados en stints ya cerrados
    margin = 0  # marcador local - visitante antes del evento actual

    for period, p in pbp_game.groupby("PERIOD", sort=True):
        p = p.sort_values("EVENTNUM", kind="stable")
        ps = period_start(period)
        plen = period_length(period)

        if period == HALFTIME_PERIOD:
            for team in on.values():
                for v in team.values():
                    v[1] = ps  # medio tiempo: reinicia el contador de minutos seguidos

        # Jugadores que ya estaban en pista cuando aparecen por primera vez
        # (su primera aparición no es entrar como sustituto).
        first = {}
        for r in p.itertuples(index=False):
            for k, (pid, ptype, tid) in enumerate((
                (r.PLAYER1_ID, r.PERSON1TYPE, r.PLAYER1_TEAM_ID),
                (r.PLAYER2_ID, r.PERSON2TYPE, r.PLAYER2_TEAM_ID),
                (r.PLAYER3_ID, r.PERSON3TYPE, r.PLAYER3_TEAM_ID),
            ), 1):
                if _valid_player(pid, ptype) and pid not in first:
                    first[pid] = (tid, r.EVENTMSGTYPE == 8 and k == 2)
        for pid, (tid, entered_as_sub) in first.items():
            team = on.setdefault(tid, {})
            if not entered_as_sub and pid not in team:
                # No venía en pista del cuarto anterior: titular del Q1, o entró en el
                # descanso (el PBP no registra las sustituciones entre cuartos).
                team[pid] = [ps, ps, False]

        for r in p.itertuples(index=False):
            t = ps + (plen - parse_clock_to_seconds(r.PCTIMESTRING))
            margin_before = margin
            sm = r.SCOREMARGIN
            if sm == sm and sm != "":  # no es NaN: el evento cambia el marcador
                try:
                    margin = 0 if str(sm) == "TIE" else int(float(sm))
                except ValueError:
                    pass

            if r.EVENTMSGTYPE == 8:  # sustitución: PLAYER1 sale, PLAYER2 entra
                team = on.setdefault(r.PLAYER1_TEAM_ID, {})
                v = team.pop(r.PLAYER1_ID, None)
                if v is not None:
                    acc[r.PLAYER1_ID] = acc.get(r.PLAYER1_ID, 0) + max(0, t - v[0])
                if r.PLAYER2_ID == r.PLAYER2_ID and r.PLAYER2_ID > 0:
                    team[r.PLAYER2_ID] = [t, t, False]

            elif r.EVENTMSGTYPE in (1, 2):  # tiro anotado / fallado
                pid = r.PLAYER1_ID
                if not _valid_player(pid, r.PERSON1TYPE):
                    continue
                team = on.setdefault(r.PLAYER1_TEAM_ID, {})
                v = team.get(pid)
                if v is None:
                    v = [ps, ps, True]
                    team[pid] = v
                home = r.PERSON1TYPE == 4
                rows.append((
                    r.GAME_ID, r.EVENTNUM, int(pid),
                    max(0, t - v[1]),
                    max(0, t - max(v[0], ps)),
                    acc.get(pid, 0) + max(0, t - v[0]),
                    bool(v[2]),
                    margin_before if home else -margin_before,  # ventaja del equipo del tirador
                    home,
                ))
    return rows


def assign_bucket(stint_minutes: float) -> str:
    for label, lo, hi in BUCKETS:
        if lo <= stint_minutes < hi:
            return label
    return BUCKETS[-1][0]


def season_paths(season: str):
    """Rutas de los CSV crudos. La temporada '2024' es 2024-25 (convención del repositorio de origen)."""
    if season == "2024":
        return "data/raw/nbastats_2024.csv", "data/raw/shotdetail_2024.csv"
    return f"data/raw/seasons/{season}/nbastats_{season}.csv", f"data/raw/seasons/{season}/shotdetail_{season}.csv"


def process_all_stints(season: str = "2024", sample_size: int = None, output_file: str = None) -> pd.DataFrame:
    """
    Reconstruye los stints de una temporada (o una muestra de partidos) y guarda el resultado
    en data/processed/by_season/stints_<temporada>.csv.
    """
    pbp_path, shots_path = season_paths(season)
    output_file = output_file or f"data/processed/by_season/stints_{season}.csv"
    print(f"⏳ [{season}] Leyendo datasets de tiros y play-by-play...")
    df_shots = pd.read_csv(shots_path, low_memory=False)
    df_pbp = pd.read_csv(pbp_path, low_memory=False)

    unique_games = df_shots["GAME_ID"].unique()
    total_games = len(unique_games)
    if sample_size and sample_size < total_games:
        print(f"🔹 Modo prueba: {sample_size} de {total_games} partidos...")
        unique_games = unique_games[:sample_size]
    else:
        print(f"🚀 [{season}] Procesando {total_games} partidos...")

    pbp_grouped = {gid: g for gid, g in df_pbp.groupby("GAME_ID")}

    all_rows = []
    for idx, gid in enumerate(unique_games, 1):
        if gid in pbp_grouped:
            all_rows.extend(reconstruct_game_stints(pbp_grouped[gid]))
        if idx % 400 == 0 or idx == len(unique_games):
            print(f"   [{season}] {idx}/{len(unique_games)} partidos")

    stints = pd.DataFrame(all_rows, columns=[
        "GAME_ID", "GAME_EVENT_ID", "PLAYER_ID",
        "stint_seconds", "stint_seconds_quarter", "game_seconds_played", "stint_inferred",
        "score_margin", "is_home",
    ])
    stints = stints.drop_duplicates(["GAME_ID", "GAME_EVENT_ID", "PLAYER_ID"])
    final_df = df_shots[df_shots["GAME_ID"].isin(unique_games)].merge(
        stints, on=["GAME_ID", "GAME_EVENT_ID", "PLAYER_ID"], how="inner")
    final_df["SEASON"] = season
    final_df["stint_minutes"] = (final_df["stint_seconds"] / 60.0).round(2)
    final_df["stint_minutes_quarter"] = (final_df["stint_seconds_quarter"] / 60.0).round(2)
    final_df["game_minutes_played"] = (final_df["game_seconds_played"] / 60.0).round(2)
    final_df["fatigue_bucket"] = final_df["stint_minutes"].map(assign_bucket)

    dropped = len(df_shots[df_shots["GAME_ID"].isin(unique_games)]) - len(final_df)
    print(f"   [{season}] tiros sin stint: {dropped} | stint inferido: {final_df['stint_inferred'].mean() * 100:.2f}%")

    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    final_df.to_csv(output_file, index=False)
    print(f"💾 [{season}] {len(final_df):,} tiros -> {output_file}")
    return final_df


if __name__ == "__main__":
    # Uso: python src/stint_calculator.py [temporada ...]   (por defecto 2024; ej.: 2021 2022 2023 2024)
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    for season in (args or ["2024"]):
        process_all_stints(season, sample_size=50 if "--sample" in sys.argv else None)
