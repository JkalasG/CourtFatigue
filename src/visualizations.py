"""
CourtFatigue - Módulo de Visualizaciones Interactivas (Cancha y Curvas)
Autor: Proyecto CourtFatigue (AQX Sports Analytics Data Bowl 4.0)

Este script crea gráficos interactivos en Plotly:
1. Media cancha de la NBA a escala reglamentaria.
2. Mapa de tiro comparativo: Descansado (< 4 min) vs Cansado (>= 8 min).
3. Curva de Fatiga interactiva con bandas de confianza al 95%.
4. Gráfico de barras de deterioro por zona geométrica de la cancha.
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import pandas as pd


def get_court_shapes():
    """
    Genera las líneas reglamentarias de una media cancha de la NBA para Plotly.
    Coordenadas en décimas de pie (escala estándar NBA: 1 pie = 10 unidades).
    Aro centrado en (0, 0).
    """
    shapes = []
    
    # 1. Perímetro de la media cancha (-250 a 250 en X; -47.5 a 422.5 en Y)
    shapes.append(dict(
        type="rect", x0=-250, y0=-47.5, x1=250, y1=422.5,
        line=dict(color="#4A5568", width=2), layer="below"
    ))
    
    # 2. Tablero (6 pies de ancho = 60 unidades a y = -7.5)
    shapes.append(dict(
        type="line", x0=-30, y0=-7.5, x1=30, y1=-7.5,
        line=dict(color="#CBD5E0", width=3), layer="below"
    ))
    
    # 3. Aro (radio de 7.5 unidades a (0, 0))
    shapes.append(dict(
        type="circle", x0=-7.5, y0=-7.5, x1=7.5, y1=7.5,
        line=dict(color="#ED8936", width=2), layer="below"
    ))
    
    # 4. Zona Pintada / La Llave (ancho 160 unidades, largo 190 unidades)
    shapes.append(dict(
        type="rect", x0=-80, y0=-47.5, x1=80, y1=142.5,
        line=dict(color="#4A5568", width=1.5), layer="below"
    ))
    # Llave interior (12 pies = 120 unidades)
    shapes.append(dict(
        type="rect", x0=-60, y0=-47.5, x1=60, y1=142.5,
        line=dict(color="#4A5568", width=1.5, dash="dash"), layer="below"
    ))
    
    # 5. Círculo de Tiro Libre (radio 60 unidades centrado en (0, 142.5))
    shapes.append(dict(
        type="circle", x0=-60, y0=82.5, x1=60, y1=202.5,
        line=dict(color="#4A5568", width=1.5), layer="below"
    ))
    
    # 6. Área Restringida (semicírculo radio 40 unidades)
    theta = np.linspace(0, np.pi, 50)
    ra_x = 40 * np.cos(theta)
    ra_y = 40 * np.sin(theta)
    path_ra = f"M {ra_x[0]} {ra_y[0]}"
    for x, y in zip(ra_x[1:], ra_y[1:]):
        path_ra += f" L {x} {y}"
    shapes.append(dict(
        type="path", path=path_ra,
        line=dict(color="#4A5568", width=1.5), layer="below"
    ))
    
    # 7. Línea de 3 puntos:
    # Líneas laterales de esquina rectas hasta y = 92.5
    shapes.append(dict(
        type="line", x0=-220, y0=-47.5, x1=-220, y1=92.5,
        line=dict(color="#4A5568", width=2), layer="below"
    ))
    shapes.append(dict(
        type="line", x0=220, y0=-47.5, x1=220, y1=92.5,
        line=dict(color="#4A5568", width=2), layer="below"
    ))
    
    # Arco central de 3 puntos (radio 237.5 unidades = 23.75 pies)
    arc_angle = np.arcsin(92.5 / 237.5)
    angles = np.linspace(arc_angle, np.pi - arc_angle, 100)
    arc_x = 237.5 * np.cos(angles)
    arc_y = 237.5 * np.sin(angles)
    path_3pt = f"M {-220} {92.5}"
    for x, y in zip(arc_x, arc_y):
        path_3pt += f" L {x} {y}"
    path_3pt += f" L {220} {92.5}"
    
    shapes.append(dict(
        type="path", path=path_3pt,
        line=dict(color="#4A5568", width=2), layer="below"
    ))
    
    return shapes


def plot_comparative_court(df_player: pd.DataFrame, fresh_thresh: float = 4.0, fatigue_thresh: float = 8.0) -> go.Figure:
    """
    Genera dos canchas lado a lado comparando tiros Descansado vs Cansado.
    """
    df_fresh = df_player[df_player["stint_minutes"] < fresh_thresh]
    df_fatigued = df_player[df_player["stint_minutes"] >= fatigue_thresh]
    
    fresh_acc = round(df_fresh["SHOT_MADE_FLAG"].mean() * 100, 1) if len(df_fresh) > 0 else 0.0
    fatigue_acc = round(df_fatigued["SHOT_MADE_FLAG"].mean() * 100, 1) if len(df_fatigued) > 0 else 0.0
    
    diff = round(fatigue_acc - fresh_acc, 1)
    diff_sign = "+" if diff > 0 else ""
    
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=(
            f"<b>DESCANSADO (&lt; {fresh_thresh:.0f} min)</b><br>Acierto: {fresh_acc}% ({len(df_fresh)} tiros)",
            f"<b>CANSADO (&ge; {fatigue_thresh:.0f} min)</b><br>Acierto: {fatigue_acc}% ({len(df_fatigued)} tiros) [Δ: {diff_sign}{diff}%]"
        ),
        horizontal_spacing=0.08
    )
    
    court_shapes = get_court_shapes()
    
    for col_idx, (subset, title) in enumerate([(df_fresh, "Descansado"), (df_fatigued, "Cansado")], 1):
        if not subset.empty:
            made = subset[subset["SHOT_MADE_FLAG"] == 1]
            missed = subset[subset["SHOT_MADE_FLAG"] == 0]
            
            # Tiros Anotados (Verde)
            fig.add_trace(go.Scatter(
                x=made["LOC_X"], y=made["LOC_Y"],
                mode="markers",
                name="Anotado" if col_idx == 1 else None,
                showlegend=(col_idx == 1),
                marker=dict(size=7, color="#10B981", symbol="circle", opacity=0.85, line=dict(width=1, color="#047857")),
                customdata=np.stack((made["ACTION_TYPE"], made["SHOT_DISTANCE"], made["stint_minutes"], made["PERIOD"]), axis=-1),
                hovertemplate="<b>CANASTA</b><br>Acción: %{customdata[0]}<br>Distancia: %{customdata[1]} ft<br>Minutos en pista: %{customdata[2]:.1f} min<br>Cuarto: %{customdata[3]}<extra></extra>"
            ), row=1, col=col_idx)
            
            # Tiros Fallados (Rojo)
            fig.add_trace(go.Scatter(
                x=missed["LOC_X"], y=missed["LOC_Y"],
                mode="markers",
                name="Fallado" if col_idx == 1 else None,
                showlegend=(col_idx == 1),
                marker=dict(size=7, color="#EF4444", symbol="x", opacity=0.75, line=dict(width=1, color="#B91C1C")),
                customdata=np.stack((missed["ACTION_TYPE"], missed["SHOT_DISTANCE"], missed["stint_minutes"], missed["PERIOD"]), axis=-1),
                hovertemplate="<b>FALLO</b><br>Acción: %{customdata[0]}<br>Distancia: %{customdata[1]} ft<br>Minutos en pista: %{customdata[2]:.1f} min<br>Cuarto: %{customdata[3]}<extra></extra>"
            ), row=1, col=col_idx)

    # Configuración de diseño
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#111827",
        plot_bgcolor="#111827",
        height=540,
        shapes=court_shapes + [
            # Duplicar líneas en la segunda columna con desfase de subplots
            dict(s, xref="x2", yref="y2") for s in court_shapes
        ],
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.12, xanchor="center", x=0.5),
        margin=dict(l=20, r=20, t=90, b=20)
    )
    
    # Bloquear ejes para mantener proporciones cuadradas de la cancha
    for axis in ["xaxis", "xaxis2"]:
        fig.update_layout({axis: dict(range=[-260, 260], showgrid=False, zeroline=False, showticklabels=False)})
    for axis in ["yaxis", "yaxis2"]:
        fig.update_layout({axis: dict(range=[-50, 430], showgrid=False, zeroline=False, showticklabels=False)})
        
    return fig


def plot_fatigue_curve(profile: dict) -> go.Figure:
    """
    Genera la curva interactiva de rendimiento de tiro según minutos seguidos en pista,
    con bandas de confianza al 95%.
    """
    curve = profile["curve"]
    labels = [pt["bucket"] for pt in curve]
    actual = [pt["actual_fg"] for pt in curve]
    expected = [pt["expected_fg"] for pt in curve]
    ci_lower = [pt["ci_lower"] for pt in curve]
    ci_upper = [pt["ci_upper"] for pt in curve]
    shots_counts = [pt["shots_count"] for pt in curve]
    deltas = [pt["fatigue_delta"] for pt in curve]
    
    fig = go.Figure()
    
    # Banda de confianza sombreada (95% CI)
    valid_ci = [i for i, v in enumerate(ci_lower) if v is not None]
    if valid_ci:
        x_ci = [labels[i] for i in valid_ci]
        y_upper = [ci_upper[i] for i in valid_ci]
        y_lower = [ci_lower[i] for i in valid_ci]
        
        fig.add_trace(go.Scatter(
            x=x_ci + x_ci[::-1],
            y=y_upper + y_lower[::-1],
            fill="toself",
            fillcolor="rgba(59, 130, 246, 0.15)",
            line=dict(color="rgba(255, 255, 255, 0)"),
            hoverinfo="skip",
            showlegend=True,
            name="Intervalo Confianza (95%)"
        ))
        
    # Línea de Tiro Esperado (Baseline de Dificultad)
    fig.add_trace(go.Scatter(
        x=labels, y=expected,
        mode="lines+markers",
        name="Tiro Esperado (xShot)",
        line=dict(color="#9CA3AF", width=2, dash="dash"),
        marker=dict(size=6, color="#9CA3AF"),
        hovertemplate="<b>Esperado (xShot):</b> %{y:.1f}%<extra></extra>"
    ))
    
    # Línea de Acierto Real del Jugador
    fig.add_trace(go.Scatter(
        x=labels, y=actual,
        mode="lines+markers+text",
        name="Acierto Real",
        text=[f"{v:.1f}%" if v is not None else "" for v in actual],
        textposition="top center",
        textfont=dict(color="#F9FAFB", size=11),
        line=dict(color="#3B82F6", width=3.5),
        marker=dict(size=10, color="#60A5FA", line=dict(width=2, color="#1D4ED8")),
        customdata=np.stack((shots_counts, deltas), axis=-1),
        hovertemplate="<b>Acierto Real:</b> %{y:.1f}%<br>Muestra: %{customdata[0]} tiros<br>Efecto Fatiga: %{customdata[1]}%<extra></extra>"
    ))
    
    # Línea vertical del minuto recomendado de descanso
    rec_cap = profile.get("recommended_stint_cap", 8.5)
    rec_text = profile.get("recommendation_text", "")
    
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#111827",
        plot_bgcolor="#1F2937",
        title=dict(
            text=f"<b>Curva de Fatiga: Rendimiento vs. Minutos Seguidos</b><br><span style='font-size:12px;color:#9CA3AF'>{rec_text}</span>",
            x=0.03, y=0.95
        ),
        xaxis=dict(
            title="Minutos Continuos en Pista (Stint)",
            gridcolor="#374151",
            tickfont=dict(color="#D1D5DB")
        ),
        yaxis=dict(
            title="% de Acierto de Tiro (FG%)",
            gridcolor="#374151",
            tickformat=".0f",
            ticksuffix="%",
            tickfont=dict(color="#D1D5DB")
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1),
        height=420,
        margin=dict(l=40, r=40, t=80, b=40)
    )
    
    return fig


def plot_zone_deterioration(df_player: pd.DataFrame, fresh_thresh: float = 4.0, fatigue_thresh: float = 8.0) -> go.Figure:
    """
    Gráfico de barras que muestra en qué zonas específicas se deteriora más el tiro por fatiga.
    """
    df_fresh = df_player[df_player["stint_minutes"] < fresh_thresh]
    df_fatigued = df_player[df_player["stint_minutes"] >= fatigue_thresh]
    
    zones = ["Restricted Area", "In The Paint (Non-RA)", "Mid-Range", "Above the Break 3", "Left Corner 3", "Right Corner 3"]
    
    zone_stats = []
    for z in zones:
        f_sub = df_fresh[df_fresh["SHOT_ZONE_BASIC"] == z]
        fat_sub = df_fatigued[df_fatigued["SHOT_ZONE_BASIC"] == z]
        
        f_acc = f_sub["SHOT_MADE_FLAG"].mean() if len(f_sub) >= 5 else np.nan
        fat_acc = fat_sub["SHOT_MADE_FLAG"].mean() if len(fat_sub) >= 5 else np.nan
        
        if pd.notna(f_acc) and pd.notna(fat_acc):
            diff = (fat_acc - f_acc) * 100
            zone_stats.append({
                "zone": z.replace("In The Paint", "Pintura").replace("Restricted Area", "Bajo Aro").replace("Above the Break", "Triple Frontal").replace("Corner", "Triple Esquina"),
                "diff": round(diff, 1),
                "fresh_acc": round(f_acc * 100, 1),
                "fatigue_acc": round(fat_acc * 100, 1),
                "sample": len(f_sub) + len(fat_sub)
            })
            
    df_z = pd.DataFrame(zone_stats)
    if df_z.empty:
        return go.Figure()
        
    df_z = df_z.sort_values(by="diff", ascending=True)
    colors = ["#EF4444" if v < 0 else "#10B981" for v in df_z["diff"]]
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=df_z["zone"],
        x=df_z["diff"],
        orientation="h",
        marker=dict(color=colors, line=dict(color="#111827", width=1)),
        text=[f"{v:+.1f}%" for v in df_z["diff"]],
        textposition="outside",
        textfont=dict(color="#F3F4F6", size=11),
        customdata=np.stack((df_z["fresh_acc"], df_z["fatigue_acc"], df_z["sample"]), axis=-1),
        hovertemplate="<b>%{y}</b><br>Variación por Fatiga: %{x:+.1f}%<br>Descansado: %{customdata[0]}% | Cansado: %{customdata[1]}%<br>Muestra total: %{customdata[2]} tiros<extra></extra>"
    ))
    
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#111827",
        plot_bgcolor="#1F2937",
        title=dict(
            text="<b>Impacto de la Fatiga por Zona de Cancha (Diferencia de % de Acierto)</b>",
            x=0.03, y=0.95
        ),
        xaxis=dict(
            title="Diferencia de Acierto (Cansado vs. Descansado)",
            ticksuffix="%",
            gridcolor="#374151"
        ),
        yaxis=dict(gridcolor="#374151"),
        height=340,
        margin=dict(l=20, r=40, t=60, b=40)
    )
    
    return fig
