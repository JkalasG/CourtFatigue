"""
CourtFatigue: ¿Cuándo deja de rendir un jugador y dónde lo nota la cancha?
Proyecto para el AQX Sports Analytics Data Bowl 4.0
"""

import os
import streamlit as st
import pandas as pd
import numpy as np

# Importar módulos locales del proyecto
from src.xshot_model import calculate_player_fatigue_profile
from src.visualizations import plot_comparative_court, plot_fatigue_curve, plot_zone_deterioration

# 1. Configuración de Página en Streamlit
st.set_page_config(
    page_title="CourtFatigue | NBA Fatigue Analytics",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="auto"
)

# 2. Estilos CSS Personalizados para una Estética Premium (Dark Mode deportivo)
st.markdown("""
<style>
    /* Estilo general oscuro y moderno */
    .main {
        background-color: #0B0F19;
        color: #F3F4F6;
    }
    .stApp {
        background-color: #0B0F19;
    }
    
    /* Tarjetas de métricas */
    .metric-card {
        background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 18px 20px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        margin-bottom: 12px;
    }
    .metric-title {
        font-size: 0.82rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #94A3B8;
        margin-bottom: 4px;
        font-weight: 600;
    }
    .metric-value {
        font-size: 1.85rem;
        font-weight: 700;
        color: #F8FAFC;
    }
    .metric-delta-neg {
        color: #EF4444;
        font-size: 0.88rem;
        font-weight: 600;
    }
    .metric-delta-pos {
        color: #10B981;
        font-size: 0.88rem;
        font-weight: 600;
    }
    
    /* Tarjeta de recomendación para el DT */
    .coach-card {
        background: linear-gradient(135deg, rgba(30, 58, 138, 0.4) 0%, rgba(15, 23, 42, 0.8) 100%);
        border-left: 5px solid #3B82F6;
        border-top: 1px solid #1E3A8A;
        border-right: 1px solid #1E3A8A;
        border-bottom: 1px solid #1E3A8A;
        border-radius: 10px;
        padding: 16px 20px;
        margin: 15px 0 25px 0;
    }
    
    /* Insignias de confianza */
    .badge-high {
        background-color: rgba(16, 185, 129, 0.2);
        color: #10B981;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        border: 1px solid rgba(16, 185, 129, 0.4);
    }
    .badge-mod {
        background-color: rgba(245, 158, 11, 0.2);
        color: #F59E0B;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        border: 1px solid rgba(245, 158, 11, 0.4);
    }
</style>
""", unsafe_allow_html=True)


# 3. Función con Caché para Cargar los Datos
@st.cache_data
def load_data():
    full_path = "data/processed/shots_fatigue_processed.csv"
    if os.path.exists(full_path):
        df = pd.read_csv(full_path, low_memory=False)
    else:
        # Fallback a la muestra si el completo aún no termina
        df = pd.read_csv("data/processed/shots_sample_stints.csv", low_memory=False)
        if "xShot" not in df.columns:
            from src.xshot_model import train_xshot_model
            df, _ = train_xshot_model(df)
    return df

df_all = load_data()

# 4. Barra Lateral (Sidebar): Selector de Jugador y Parámetros
with st.sidebar:
    st.image("https://cdn.nba.com/logos/leagues/L/nba.svg", width=70)
    st.title("🏀 CourtFatigue")
    st.caption("AQX Sports Analytics Data Bowl 4.0")
    
    st.markdown("---")
    
    # Filtro opcional por Franquicia / Equipo
    all_teams = ["Todas las Franquicias"] + sorted(df_all["TEAM_NAME"].dropna().unique().tolist())
    selected_team = st.selectbox("Filtrar por Franquicia:", options=all_teams, index=0)
    
    if selected_team != "Todas las Franquicias":
        df_team_pool = df_all[df_all["TEAM_NAME"] == selected_team]
    else:
        df_team_pool = df_all

    # Lista de jugadores ordenada por número de tiros
    player_counts = df_team_pool["PLAYER_NAME"].value_counts()
    top_players = player_counts[player_counts >= 15].index.tolist()
    if not top_players:
        top_players = player_counts.index.tolist()
    
    selected_player = st.selectbox(
        "Selecciona un Jugador:",
        options=top_players,
        index=0 if len(top_players) > 0 else 0
    )
    
    # Datos del jugador seleccionado
    df_player = df_all[df_all["PLAYER_NAME"] == selected_player]
    player_id = int(df_player["PLAYER_ID"].iloc[0])
    team_name = df_player["TEAM_NAME"].iloc[0]
    team_id = int(df_player["TEAM_ID"].iloc[0])
    
    # Foto oficial del jugador desde el CDN de la NBA
    headshot_url = f"https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png"
    logo_url = f"https://cdn.nba.com/logos/nba/{team_id}/primary/L/logo.svg"
    
    col_img1, col_img2 = st.columns([2, 1])
    with col_img1:
        st.image(headshot_url, caption=selected_player, use_container_width=True)
    with col_img2:
        st.image(logo_url, caption=team_name, use_container_width=True)
        
    st.markdown("---")
    st.subheader("⚙️ Umbrales de Fatiga")
    fresh_thresh = st.slider("Minutos Descansado (<):", min_value=2.0, max_value=5.0, value=4.0, step=0.5)
    fatigue_thresh = st.slider("Minutos Cansado (≥):", min_value=6.0, max_value=10.0, value=8.0, step=0.5)
    
    st.markdown("---")
    st.markdown("""
    <div style='font-size:0.8rem; color:#94A3B8;'>
    <b>Metodología:</b><br>
    • Stints de sustitución en PBP<br>
    • Tiro Esperado (xShot) calibrado<br>
    • Efectos fijos por jugador
    </div>
    """, unsafe_allow_html=True)

# 5. Encabezado Principal del Dashboard
st.markdown(f"## 📊 Análisis de Fatiga y Rotación: **{selected_player}**")
st.markdown(f"**Franquicia:** {team_name} | **Temporada:** NBA 2023–24 Regular Season")

# Calcular perfil de fatiga del jugador
profile = calculate_player_fatigue_profile(df_player)

# 6. Tarjetas de Métricas Clave (KPIs)
df_fresh = df_player[df_player["stint_minutes"] < fresh_thresh]
df_fatigued = df_player[df_player["stint_minutes"] >= fatigue_thresh]

acc_fresh = df_fresh["SHOT_MADE_FLAG"].mean() * 100 if len(df_fresh) > 0 else 0.0
acc_fatigue = df_fatigued["SHOT_MADE_FLAG"].mean() * 100 if len(df_fatigued) > 0 else 0.0
drop = acc_fatigue - acc_fresh

kpi1, kpi2, kpi3, kpi4 = st.columns(4)

with kpi1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Minuto Crítico de Reemplazo</div>
        <div class="metric-value">{profile['recommended_stint_cap']:.1f} min</div>
        <span class="badge-high">Confianza: {profile['confidence_level']}</span>
    </div>
    """, unsafe_allow_html=True)

with kpi2:
    delta_class = "metric-delta-neg" if drop < 0 else "metric-delta-pos"
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Caída de Acierto por Fatiga</div>
        <div class="metric-value {delta_class}">{drop:+.1f}%</div>
        <div style="font-size:0.75rem; color:#94A3B8;">Cansado vs. Descansado</div>
    </div>
    """, unsafe_allow_html=True)

with kpi3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Acierto Descansado (&lt; {fresh_thresh:.0f}m)</div>
        <div class="metric-value">{acc_fresh:.1f}%</div>
        <div style="font-size:0.75rem; color:#94A3B8;">{len(df_fresh)} tiros registrados</div>
    </div>
    """, unsafe_allow_html=True)

with kpi4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Tiros Totales Analizados</div>
        <div class="metric-value">{profile['total_shots']:,}</div>
        <div style="font-size:0.75rem; color:#94A3B8;">xShot Esperado: {profile['baseline_xshot']}%</div>
    </div>
    """, unsafe_allow_html=True)

# 7. Tarjeta de Recomendación para el Cuerpo Técnico (Coach Card)
st.markdown(f"""
<div class="coach-card">
    <div style="display:flex; align-items:center; gap:10px; margin-bottom:6px;">
        <span style="font-size:1.3rem;">📋</span>
        <b style="font-size:1.05rem; color:#60A5FA;">RECOMENDACIÓN DE ROTACIÓN PARA EL ENTRENADOR</b>
    </div>
    <div style="font-size:0.95rem; line-height:1.5; color:#E2E8F0;">
        {profile['recommendation_text']}<br>
        <span style="font-size:0.83rem; color:#94A3B8;">
        💡 <i>Estrategia: Programar la rotación de <b>{selected_player}</b> en bloques de hasta {profile['recommended_stint_cap']:.1f} minutos seguidos para maximizar su eficiencia de tiro en posesiones decisivas.</i>
        </span>
    </div>
</div>
""", unsafe_allow_html=True)

# 8. Pestañas de Análisis Visual
tab1, tab2, tab3, tab4 = st.tabs([
    "🏀 Cancha Comparativa (Descansado vs. Cansado)",
    "🎮 Simulador 3D de Tiro & Fatiga",
    "📈 Curva de Fatiga & Intervalos de Confianza",
    "📑 Metodología & Criterios del Jurado"
])

with tab2:
    st.markdown("#### 🎮 Simulador Físico 3D en Tiempo Real (Three.js & WebGL)")
    st.caption("💡 **Tip de visualización:** Puedes **arrastrar las tarjetas** a cualquier lugar con el ratón o **minimizarlas con el botón `[−]`** para ver toda la cancha limpia.")
    
    sim_path = "simulator_3d/index.html"
    if os.path.exists(sim_path):
        with open(sim_path, "r", encoding="utf-8") as f:
            html_3d = f.read()
        import streamlit.components.v1 as components
        components.html(html_3d, height=840, scrolling=False)
    else:
        st.warning("El archivo simulator_3d/index.html no fue encontrado.")

with tab1:
    st.markdown("#### Distribución Espacial de Tiros según Fatiga")
    st.caption("Puntos verdes = Canastas anotadas | Puntos rojos = Tiros fallados. Pasa el ratón por cada punto para ver reloj y distancia.")
    
    fig_court = plot_comparative_court(df_player, fresh_thresh=fresh_thresh, fatigue_thresh=fatigue_thresh)
    st.plotly_chart(fig_court, use_container_width=True)
    
    st.markdown("---")
    st.markdown("#### ¿Dónde se nota más el cansancio?")
    st.caption("Deterioro porcentual del acierto desglosado por las 6 zonas reglamentarias de la cancha.")
    fig_zones = plot_zone_deterioration(df_player, fresh_thresh=fresh_thresh, fatigue_thresh=fatigue_thresh)
    st.plotly_chart(fig_zones, use_container_width=True)

with tab3:
    st.markdown("#### Rendimiento Real vs. Dificultad del Tiro (xShot)")
    st.caption("El modelo aísla la fatiga controlando por la dificultad intrínseca de cada lanzamiento (distancia, ángulo y tipo de tiro).")
    
    fig_curve = plot_fatigue_curve(profile)
    st.plotly_chart(fig_curve, use_container_width=True)
    
    st.markdown("#### Tabla de Datos por Tramo de Permanencia en Pista")
    df_curve_table = pd.DataFrame(profile["curve"])[[
        "bucket", "shots_count", "actual_fg", "expected_fg", "fatigue_delta", "ci_lower", "ci_upper", "reliable"
    ]].rename(columns={
        "bucket": "Tramo de Minutos en Pista",
        "shots_count": "Tiros",
        "actual_fg": "Acierto Real (%)",
        "expected_fg": "xShot Esperado (%)",
        "fatigue_delta": "Efecto Fatiga (Δ %)",
        "ci_lower": "IC Inf 95%",
        "ci_upper": "IC Sup 95%",
        "reliable": "Muestra Fiable"
    })
    st.dataframe(df_curve_table, use_container_width=True, hide_index=True)

with tab4:
    st.markdown("""
    ### 🔬 Metodología Científica de CourtFatigue
    
    #### 1. Reconstrucción de Stints
    A partir de los eventos de sustitución (`EVENTMSGTYPE = 8`) del Play-by-Play de la NBA, se reconstruyen segundo a segundo las entradas y salidas de cada jugador. 
    * El cronómetro continuo se reinicia a `0.0 min` cada vez que el jugador sale a la banca y reingresa.
    * El descanso de medio tiempo reinicia el contador de minutos seguidos.
    
    #### 2. Modelo Base de Tiro Esperado ($xShot$)
    Para evitar el sesgo de *"el jugador tiró peor porque tomó tiros más forzados"*, entrenamos una **Regresión Logística calibrada** sobre más de 200,000 tiros de la NBA usando:
    * Distancia euclidiana al aro (`SHOT_DISTANCE`).
    * Zona geométrica (`SHOT_ZONE_BASIC`).
    * Mecánica de tiro (`ACTION_TYPE`: stepback, pullup, floater, layup, dunk).
    * Periodo del partido (`PERIOD`).
    
    #### 3. Análisis del Residuo con Efectos Fijos
    $$\Delta_{\text{Fatiga}} = (\text{Acierto Real} - xShot) - \overline{\text{Residuo}}_{\text{Jugador}}$$
    Comparamos al jugador **consigo mismo**, midiendo cómo varía su eficiencia respecto a su propio estándar cuando está fresco.
    
    #### 4. Tratamiento de Incertidumbre
    Todos los tramos calculan su intervalo de confianza al 95%. Tramos con menos de 20 tiros se marcan explícitamente como muestra insuficiente para evitar conclusiones sesgadas.
    """)

# Pie de página
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #64748B; font-size: 0.85rem;">
🏀 <b>CourtFatigue</b> | AQX Sports Analytics Data Bowl 4.0 | Desarrollado con Streamlit, Plotly y Scikit-Learn.
</div>
""", unsafe_allow_html=True)
