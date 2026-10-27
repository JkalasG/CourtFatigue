"""
CourtFatigue - Módulo de Cálculo de Stints (Minutos Seguidos en Cancha)
Autor: Proyecto CourtFatigue (AQX Sports Analytics Data Bowl 4.0)

Este script reconstruye segundo a segundo la presencia de cada jugador en pista
usando los eventos de sustitución del Play-by-Play (nbastats) y asocia a cada tiro
(shotdetail) cuántos minutos continuos llevaba el jugador en cancha.
"""

import sys
import os
import pandas as pd
import numpy as np

# Asegurar codificación UTF-8 en consola
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


def parse_clock_to_seconds(clock_str: str) -> int:
    """
    Convierte un string de reloj 'MM:SS' a segundos restantes en el cuarto.
    Ejemplo: '11:43' -> 11 * 60 + 43 = 703 segundos.
    """
    try:
        parts = str(clock_str).strip().split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except Exception:
        return 0


def calculate_stints_for_game(pbp_game: pd.DataFrame, shots_game: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula los minutos seguidos (stint) para todos los tiros de un partido específico.
    """
    shots_with_stints = []
    
    # Agrupar por periodos (cuartos 1 a 4, o prórrogas 5+)
    for period, pbp_period in pbp_game.groupby("PERIOD"):
        quarter_duration = 300 if period > 4 else 720  # Prórroga 5 min (300s), cuarto normal 12 min (720s)
        
        # Tiros de este cuarto
        period_shots = shots_game[shots_game["PERIOD"] == period].copy()
        if period_shots.empty:
            continue
            
        # Diccionario para rastrear el segundo en que entró cada jugador activo: {player_id: entered_at_elapsed_sec}
        # Y minutos acumulados en el partido: {player_id: accumulated_seconds}
        active_players = {}
        
        # 1. Encontrar los 5 titulares que empezaron el cuarto:
        # Cualquier jugador que aparezca en una jugada antes de haber sido sustituido tuvo que empezar en cancha.
        sub_ins = set(pbp_period[pbp_period["EVENTMSGTYPE"] == 8]["PLAYER2_ID"].dropna().astype(int))
        
        starters = set()
        for _, event in pbp_period.iterrows():
            event_type = event["EVENTMSGTYPE"]
            p1 = event["PLAYER1_ID"]
            
            # Si es sustitución, el que sale (p1) estaba en cancha antes del cambio
            if event_type == 8:
                if pd.notna(p1) and int(p1) not in sub_ins and int(p1) > 0:
                    starters.add(int(p1))
            else:
                # Cualquier jugador con jugada activa (tiro, rebote, falta) antes de entrar de cambio
                if pd.notna(p1) and int(p1) not in sub_ins and int(p1) > 0:
                    starters.add(int(p1))
                    
        # Inicializar los titulares al inicio del cuarto (segundo 0 transcurrido)
        for pid in starters:
            active_players[pid] = 0.0  # Inició en el segundo 0 transcurrido
            
        # 2. Recorrer los eventos cronológicamente para actualizar entradas, salidas y tiros
        pbp_sorted = pbp_period.sort_values(by="EVENTNUM", ascending=True)
        
        # Mapeo de tiros por EVENTNUM para búsqueda rápida
        shots_by_event = {row["GAME_EVENT_ID"]: row for _, row in period_shots.iterrows()}
        
        for _, event in pbp_sorted.iterrows():
            event_num = event["EVENTNUM"]
            event_type = event["EVENTMSGTYPE"]
            clock_str = event["PCTIMESTRING"]
            secs_remaining = parse_clock_to_seconds(clock_str)
            elapsed_in_period = quarter_duration - secs_remaining  # Segundos transcurridos en el cuarto
            
            # MANEJO DE SUSTITUCIÓN (EVENTMSGTYPE == 8)
            if event_type == 8:
                player_out = int(event["PLAYER1_ID"]) if pd.notna(event["PLAYER1_ID"]) else None
                player_in = int(event["PLAYER2_ID"]) if pd.notna(event["PLAYER2_ID"]) else None
                
                # Jugador sale a la banca
                if player_out and player_out in active_players:
                    del active_players[player_out]
                    
                # Jugador entra a la cancha: su stint arranca en este segundo transcurrido
                if player_in:
                    active_players[player_in] = elapsed_in_period
                    
            # MANEJO DE TIRO (Si este evento es un tiro que estamos rastreando)
            if event_num in shots_by_event:
                shot_row = shots_by_event[event_num].to_dict()
                shooter_id = int(shot_row["PLAYER_ID"])
                
                # Si por alguna razón el tirador no estaba registrado como activo, asumimos que entró al inicio
                if shooter_id not in active_players:
                    active_players[shooter_id] = 0.0
                    
                # Calcular segundos continuos en pista en el momento del tiro
                stint_seconds = max(0, elapsed_in_period - active_players[shooter_id])
                stint_minutes = round(stint_seconds / 60.0, 2)
                
                shot_row["stint_seconds"] = stint_seconds
                shot_row["stint_minutes"] = stint_minutes
                
                # Clasificación por tramos de fatiga
                if stint_minutes < 2.0:
                    bucket = "0-2 min (Inicio)"
                elif stint_minutes < 5.0:
                    bucket = "2-5 min (Ritmo Óptimo)"
                elif stint_minutes < 8.0:
                    bucket = "5-8 min (Carga Media)"
                elif stint_minutes < 10.0:
                    bucket = "8-10 min (Zona Crítica)"
                else:
                    bucket = "10+ min (Fatiga Extrema)"
                    
                shot_row["fatigue_bucket"] = bucket
                shots_with_stints.append(shot_row)
                
    return pd.DataFrame(shots_with_stints)


def process_all_stints(sample_size: int = None, output_file: str = "data/processed/shots_with_stints.csv") -> pd.DataFrame:
    """
    Carga los datasets crudos, procesa los stints para todos los partidos (o una muestra)
    y guarda el resultado procesado en data/processed/.
    """
    print("⏳ [1/4] Leyendo datasets de tiros y play-by-play...")
    df_shots = pd.read_csv("data/raw/shotdetail_2024.csv", low_memory=False)
    df_pbp = pd.read_csv("data/raw/nbastats_2024.csv", low_memory=False)
    
    unique_games = df_shots["GAME_ID"].unique()
    total_games = len(unique_games)
    
    if sample_size and sample_size < total_games:
        print(f"🔹 Modo prueba: Procesando muestra de {sample_size} de {total_games} partidos...")
        unique_games = unique_games[:sample_size]
    else:
        print(f"🚀 Procesando los {total_games} partidos de la temporada completa...")

    all_processed_shots = []
    
    # Indexar PBP por GAME_ID para búsquedas rápidas
    pbp_grouped = {game_id: group for game_id, group in df_pbp.groupby("GAME_ID")}
    shots_grouped = {game_id: group for game_id, group in df_shots.groupby("GAME_ID")}
    
    total_to_process = len(unique_games)
    print("⏳ [2/4] Calculando cronómetros de stint segundo a segundo...")
    
    for idx, game_id in enumerate(unique_games, 1):
        if game_id not in pbp_grouped or game_id not in shots_grouped:
            continue
            
        pbp_g = pbp_grouped[game_id]
        shots_g = shots_grouped[game_id]
        
        df_game_shots = calculate_stints_for_game(pbp_g, shots_g)
        if not df_game_shots.empty:
            all_processed_shots.append(df_game_shots)
            
        if idx % 100 == 0 or idx == total_to_process:
            print(f"   Progreso: {idx}/{total_to_process} partidos procesados ({idx / total_to_process * 100:.1f}%)")
            
    print("⏳ [3/4] Uniendo todos los tiros procesados...")
    final_df = pd.concat(all_processed_shots, ignore_index=True)
    
    # Crear carpeta processed si no existe
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    print(f"💾 [4/4] Guardando archivo con {len(final_df):,} tiros en '{output_file}'...")
    final_df.to_csv(output_file, index=False)
    print("✅ ¡Procesamiento de Stints completado con éxito!")
    
    return final_df


if __name__ == "__main__":
    # Prueba inicial rápida con los primeros 50 partidos para verificar velocidad y exactitud
    print("--- INICIANDO PRUEBA DE CÁLCULO DE STINTS ---")
    df_sample = process_all_stints(sample_size=50, output_file="data/processed/shots_sample_stints.csv")
    
    print("\n📊 Muestra de resultados (Primeros 5 tiros con sus minutos seguidos):")
    sample_cols = ["PLAYER_NAME", "PERIOD", "MINUTES_REMAINING", "SECONDS_REMAINING", "stint_minutes", "fatigue_bucket", "SHOT_MADE_FLAG"]
    print(df_sample[sample_cols].head())
