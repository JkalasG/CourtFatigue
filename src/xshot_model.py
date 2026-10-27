"""
CourtFatigue - Módulo de Tiro Esperado (xShot) y Análisis del Residuo de Fatiga
Autor: Proyecto CourtFatigue (AQX Sports Analytics Data Bowl 4.0)

Este script:
1. Entrena un modelo estadístico de Tiro Esperado (xShot) basado en dificultad de tiro
   (distancia, zona, mecánica y periodo) usando Logistic Regression calibrada.
2. Calcula el Residuo de Fatiga: Residual = SHOT_MADE_FLAG - xShot.
3. Compara a cada jugador contra su propio nivel base (Efectos Fijos) para aislar
   el impacto real de los minutos continuos en cancha.
4. Genera el dataset final procesado en 'data/processed/shots_fatigue_processed.csv'.
"""

import sys
import os
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


def clean_action_type(action: str) -> str:
    """Agrupa mecánicas de tiro similares para dar robustez al modelo."""
    act = str(action).lower()
    if "dunk" in act:
        return "Dunk"
    elif "layup" in act or "finger roll" in act:
        return "Layup"
    elif "step back" in act:
        return "Step Back"
    elif "pullup" in act or "pull up" in act:
        return "Pullup Jumper"
    elif "fadeaway" in act or "turnaround" in act:
        return "Fadeaway / Turnaround"
    elif "hook" in act or "floater" in act or "floating" in act:
        return "Floater / Hook"
    elif "jump shot" in act or "jumper" in act:
        return "Jump Shot"
    else:
        return "Other"


def train_xshot_model(df_shots: pd.DataFrame):
    """
    Entrena el modelo de Tiro Esperado (xShot) usando la dificultad intrínseca del tiro.
    """
    print("🧠 [1/3] Preparando características para el Modelo de Tiro Esperado (xShot)...")
    
    # Crear características de dificultad
    df = df_shots.copy()
    df["ACTION_GROUP"] = df["ACTION_TYPE"].apply(clean_action_type)
    df["SHOT_DISTANCE_CAPPED"] = df["SHOT_DISTANCE"].clip(0, 35)
    
    features = ["SHOT_DISTANCE_CAPPED", "SHOT_ZONE_BASIC", "ACTION_GROUP", "SHOT_TYPE", "PERIOD"]
    target = "SHOT_MADE_FLAG"
    
    # Filtrar valores válidos
    valid_mask = df[features + [target]].notna().all(axis=1)
    df_clean = df[valid_mask]
    
    categorical_features = ["SHOT_ZONE_BASIC", "ACTION_GROUP", "SHOT_TYPE", "PERIOD"]
    numeric_features = ["SHOT_DISTANCE_CAPPED"]
    
    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore", drop="first"), categorical_features),
            ("num", "passthrough", numeric_features)
        ]
    )
    
    pipeline = Pipeline(steps=[
        ("preprocessor", preprocessor),
        ("classifier", LogisticRegression(max_iter=1000, C=1.0, random_state=42))
    ])
    
    print("⏳ [2/3] Entrenando Regresión Logística con todos los tiros de la liga...")
    X = df_clean[features]
    y = df_clean[target]
    pipeline.fit(X, y)
    
    # Predicción de probabilidades (xShot)
    probs = pipeline.predict_proba(df_clean[features])[:, 1]
    df_clean = df_clean.copy()
    df_clean["xShot"] = np.round(probs, 4)
    
    # Calcular Residuo: Real - Esperado
    # Positivo = Tiro por encima de lo esperado
    # Negativo = Tiro por debajo de lo esperado (síntoma de fatiga)
    df_clean["shot_residual"] = np.round(df_clean["SHOT_MADE_FLAG"] - df_clean["xShot"], 4)
    
    print("✅ [3/3] Modelo xShot entrenado exitosamente.")
    return df_clean, pipeline


def calculate_player_fatigue_profile(df_player: pd.DataFrame) -> dict:
    """
    Calcula la curva de fatiga y la recomendación de rotación para un jugador específico.
    Compara al jugador CONSIGO MISMO (efectos fijos).
    """
    player_name = df_player["PLAYER_NAME"].iloc[0]
    total_shots = len(df_player)
    
    # Rendimiento base del jugador
    player_baseline_fg = df_player["SHOT_MADE_FLAG"].mean()
    player_baseline_xshot = df_player["xShot"].mean()
    player_baseline_residual = df_player["shot_residual"].mean()
    
    # Agrupar por tramos de stint
    buckets = [
        ("0-2 min (Inicio)", 0.0, 2.0),
        ("2-5 min (Ritmo Óptimo)", 2.0, 5.0),
        ("5-8 min (Carga Media)", 5.0, 8.0),
        ("8-10 min (Zona Crítica)", 8.0, 10.0),
        ("10+ min (Fatiga Extrema)", 10.0, 99.0)
    ]
    
    curve = []
    for label, min_val, max_val in buckets:
        mask = (df_player["stint_minutes"] >= min_val) & (df_player["stint_minutes"] < max_val)
        subset = df_player[mask]
        n_shots = len(subset)
        
        if n_shots > 0:
            actual_fg = subset["SHOT_MADE_FLAG"].mean()
            expected_fg = subset["xShot"].mean()
            raw_residual = subset["shot_residual"].mean()
            
            # Ajuste de Efectos Fijos: diferencia respecto al nivel habitual de este jugador
            fatigue_delta = raw_residual - player_baseline_residual
            
            # Error estándar e Intervalo de confianza al 95%
            std_err = np.sqrt((actual_fg * (1 - actual_fg)) / n_shots) if n_shots > 1 else 0.0
            ci_lower = max(0.0, actual_fg - 1.96 * std_err)
            ci_upper = min(1.0, actual_fg + 1.96 * std_err)
            reliable = n_shots >= 20
        else:
            actual_fg = np.nan
            expected_fg = np.nan
            fatigue_delta = np.nan
            std_err = 0.0
            ci_lower, ci_upper = np.nan, np.nan
            reliable = False
            
        curve.append({
            "bucket": label,
            "min_stint": min_val,
            "max_stint": max_val,
            "shots_count": n_shots,
            "actual_fg": round(actual_fg * 100, 1) if pd.notna(actual_fg) else None,
            "expected_fg": round(expected_fg * 100, 1) if pd.notna(expected_fg) else None,
            "fatigue_delta": round(fatigue_delta * 100, 2) if pd.notna(fatigue_delta) else None,
            "ci_lower": round(ci_lower * 100, 1) if pd.notna(ci_lower) else None,
            "ci_upper": round(ci_upper * 100, 1) if pd.notna(ci_upper) else None,
            "reliable": reliable
        })
        
    # Lógica de Recomendación de Rotación para el entrenador
    # Buscar el minuto de inflexión donde la fatiga_delta cae persistentemente
    rec_minute = None
    rec_drop = None
    confidence_level = "Moderada"
    
    for pt in curve:
        if pt["reliable"] and pt["fatigue_delta"] is not None:
            if pt["fatigue_delta"] <= -3.0:  # Caída notable mayor a 3 puntos porcentuales
                rec_minute = pt["min_stint"]
                rec_drop = pt["fatigue_delta"]
                confidence_level = "Alta" if pt["shots_count"] >= 40 else "Moderada"
                break
                
    if rec_minute is None:
        # Si no hay caída abrupta, resistencia alta
        recommendation_text = f"Excelente resistencia física. Mantiene su eficiencia incluso en tramos de 8+ minutos continuos."
        recommended_stint_cap = 9.5
    else:
        recommendation_text = f"Sustituir o dar descanso en el minuto {rec_minute:.1f} de stint continuo (caída de acierto estimada: {rec_drop:.1f}% respecto a su media)."
        recommended_stint_cap = rec_minute
        
    return {
        "player_name": player_name,
        "total_shots": total_shots,
        "baseline_fg": round(player_baseline_fg * 100, 1),
        "baseline_xshot": round(player_baseline_xshot * 100, 1),
        "curve": curve,
        "recommended_stint_cap": recommended_stint_cap,
        "recommendation_text": recommendation_text,
        "confidence_level": confidence_level
    }


def process_and_save_full_dataset(input_file: str = "data/processed/shots_with_stints.csv",
                                   output_file: str = "data/processed/shots_fatigue_processed.csv"):
    """
    Carga los tiros con stints, aplica el modelo xShot y guarda el dataset final.
    """
    print(f"📂 Leyendo tiros con stints desde '{input_file}'...")
    df = pd.read_csv(input_file, low_memory=False)
    
    df_processed, _ = train_xshot_model(df)
    
    print(f"💾 Guardando dataset procesado final en '{output_file}'...")
    df_processed.to_csv(output_file, index=False)
    print(f"🎉 ¡Dataset listo! Total: {len(df_processed):,} tiros procesados con xShot y Stints.")
    return df_processed


if __name__ == "__main__":
    # Si existe el archivo completo de stints lo usa, sino usa el de muestra para validar
    if os.path.exists("data/processed/shots_with_stints.csv"):
        file_to_use = "data/processed/shots_with_stints.csv"
    else:
        file_to_use = "data/processed/shots_sample_stints.csv"
        
    df_res = process_and_save_full_dataset(input_file=file_to_use)
    
    # Probar perfil de fatiga con el jugador que más tiros tenga en la muestra
    top_player = df_res["PLAYER_NAME"].value_counts().index[0]
    print(f"\n🏀 Análisis de Fatiga para la Estrella: {top_player}")
    player_data = df_res[df_res["PLAYER_NAME"] == top_player]
    profile = calculate_player_fatigue_profile(player_data)
    
    print(f"Total tiros analizados: {profile['total_shots']}")
    print(f"Acierto real general: {profile['baseline_fg']}% vs Esperado: {profile['baseline_xshot']}%")
    print(f"Recomendación para el DT: {profile['recommendation_text']}")
    print(f"Nivel de Confianza: {profile['confidence_level']}")
    print("\nCurva de Rendimiento por Tramo de Minutos Seguidos:")
    for pt in profile["curve"]:
        status = "✅ Fiable" if pt["reliable"] else "⚠️ Muestra Pequeña"
        print(f"  • {pt['bucket']:<25} | Tiros: {pt['shots_count']:<4} | Acierto: {pt['actual_fg']}% | Delta Fatiga: {pt['fatigue_delta']}% | {status}")
