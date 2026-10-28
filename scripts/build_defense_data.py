"""
Datos de defensa para el simulador 3D (web/data/defense.json y web/data/contest.json).

1) Efecto defensivo de cada equipo (nuestras temporadas 2021-25):
   acierto del rival menos lo esperado por la dificultad del tiro y por el propio tirador
   (`dev`), promediado por equipo-temporada y suavizado hacia el promedio de la liga.
   Se publica la temporada más reciente. Es un efecto PROMEDIO del equipo, no de un defensor.

2) Distancia al defensor (registro de tiros 2014-15, CC0, 128 mil tiros; data/raw/external/):
   modelo de gradient boosting monótono (más distancia al defensor => no menos acierto) y una
   tabla P(anota | distancia del tiro, distancia del defensor) con banda de confianza por
   bootstrap sobre partidos. El simulador usa la DIFERENCIA respecto a la distancia TÍPICA del defensor
   para ese tipo de tiro (mediana por distancia de tiro), para que sea un ajuste y no una
   probabilidad absoluta, y para no contar dos veces lo que la curva por distancia ya incluye.

Uso: python scripts/build_defense_data.py                 (todo, ~10 min por el remuestreo)
     python scripts/build_defense_data.py contest         (solo la tabla de distancia al defensor)
     python scripts/build_defense_data.py team            (solo el efecto defensivo por equipo)
     python scripts/build_defense_data.py distance        (solo la curva por distancia del tiro)
     python scripts/build_defense_data.py gap             (solo la comparación con/sin datos del defensor)
"""
import json
import math
import os
import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import fatigue_stats as fs  # noqa: E402

OUT = "web/data"
SHOT_GRID = list(range(0, 41, 2))           # distancia del tiro, pies
DEF_GRID = [round(x * 0.5, 1) for x in range(0, 25)]   # distancia del defensor, 0 a 12 pies
N_BOOT = 24


def team_defense():
    d = pd.read_csv("data/processed/shots_fatigue_processed.csv",
                    usecols=["GAME_ID", "SEASON", "TEAM_ID", "TEAM_NAME", "PLAYER_ID", "shot_residual"], dtype={"SEASON": str})
    d = fs.add_dev(d)
    names = d.groupby("TEAM_ID").TEAM_NAME.agg(lambda s: s.iloc[-1]).to_dict()
    teams = d[["GAME_ID", "TEAM_ID"]].drop_duplicates()
    opp = teams.merge(teams, on="GAME_ID", suffixes=("", "_o"))
    opp = opp[opp.TEAM_ID != opp.TEAM_ID_o].rename(columns={"TEAM_ID_o": "OPP_ID"})[["GAME_ID", "TEAM_ID", "OPP_ID"]]
    d = d.merge(opp, on=["GAME_ID", "TEAM_ID"], how="left").dropna(subset=["OPP_ID"])
    g = d.groupby(["SEASON", "OPP_ID"]).dev.agg(mean="mean", n="size", sd="std").reset_index()
    g["se2"] = (g.sd ** 2) / g.n
    # varianza real entre equipos (método de momentos) por temporada y suavizado (empirical Bayes)
    last = sorted(g.SEASON.unique())[-1]
    rows, per_season = [], []
    for sea, h in g.groupby("SEASON"):
        tau2 = max(0.0, h["mean"].var() - h.se2.mean())
        per_season.append({"season": sea, "tau_pp": math.sqrt(tau2) * 100, "se_pp": math.sqrt(h.se2.mean()) * 100})
        if sea != last:
            continue
        mu = h["mean"].mean()
        for r in h.itertuples():
            B = tau2 / (tau2 + r.se2)
            eff = mu + B * (r.mean - mu)
            sd = math.sqrt(B * r.se2)          # incertidumbre a posteriori
            rows.append({"team_id": int(r.OPP_ID), "team": names.get(int(r.OPP_ID), str(int(r.OPP_ID))),
                         "effect_pp": eff * 100, "lo_pp": (eff - fs.Z95 * sd) * 100, "hi_pp": (eff + fs.Z95 * sd) * 100,
                         "raw_pp": r.mean * 100, "n": int(r.n), "shrink": B})
    rows.sort(key=lambda r: r["effect_pp"])
    wide = g.pivot(index="OPP_ID", columns="SEASON", values="mean")
    seasons = sorted(wide.columns)
    stab = [float(wide[[a, b]].dropna().corr().iloc[0, 1]) for a, b in zip(seasons[:-1], seasons[1:])]
    return {"season": last, "teams": rows, "per_season": per_season, "stability_r": stab}


def contest_table():
    d = pd.read_csv("data/raw/external/shot_logs_2014/shot_logs_2014.csv")
    d = d[(d.SHOT_DIST > 0) & d.CLOSE_DEF_DIST.notna()].copy()
    d["IS3"] = (d.PTS_TYPE == 3).astype(int)
    feats = ["SHOT_DIST", "IS3", "CLOSE_DEF_DIST"]
    games = d.GAME_ID.unique()
    rng = np.random.default_rng(0)
    grid = pd.DataFrame([(s, 1 if s >= 23 else 0, k) for s in SHOT_GRID for k in DEF_GRID], columns=feats)

    # Referencia: distancia TÍPICA del defensor para cada distancia de tiro (mediana en una ventana de ±1.5 ft).
    # La curva de acierto por distancia del tiro ya incluye cuánto suele estar marcado ese tipo de tiro; el ajuste del
    # defensor debe medirse contra ese nivel típico, no contra una distancia fija (que sumaría de más a los triples).
    ref_def = []
    for sd in SHOT_GRID:
        near = d.CLOSE_DEF_DIST[(d.SHOT_DIST - sd).abs() <= 1.5]
        if len(near) < 300:
            near = d.CLOSE_DEF_DIST[(d.SHOT_DIST - sd).abs() <= 3.5]
        ref_def.append(float(near.median()) if len(near) >= 100 else float(d.CLOSE_DEF_DIST.median()))
    ref = pd.DataFrame([(sd, 1 if sd >= 23 else 0, r) for sd, r in zip(SHOT_GRID, ref_def)], columns=feats)

    def fit_predict(data):
        m = HistGradientBoostingClassifier(max_iter=120, learning_rate=0.08, max_depth=4, random_state=0,
                                           monotonic_cst=[0, 0, 1])   # más distancia al defensor => no baja el acierto
        m.fit(data[feats], data.FGM)
        p = m.predict_proba(grid)[:, 1].reshape(len(SHOT_GRID), len(DEF_GRID))
        p0 = m.predict_proba(ref)[:, 1][:, None]
        return p, p - p0

    p_hat, adj_hat = fit_predict(d)
    boots = []
    for b in range(N_BOOT):
        pick = rng.choice(games, size=len(games), replace=True)
        sample = d.merge(pd.DataFrame({"GAME_ID": pick}), on="GAME_ID")   # remuestreo de partidos con reposición
        boots.append(fit_predict(sample)[1])
        print(f"   bootstrap {b + 1}/{N_BOOT}")
    B = np.stack(boots)
    lo, hi = np.percentile(B, 2.5, axis=0), np.percentile(B, 97.5, axis=0)
    return {"source": "NBA 2014-15, registro de tiros (CC0), %d tiros" % len(d), "ref_def_by_shot_ft": [round(r, 2) for r in ref_def],
            "shot_grid_ft": SHOT_GRID, "def_grid_ft": DEF_GRID,
            "p": np.round(p_hat * 100, 2).tolist(), "adj_pp": np.round(adj_hat * 100, 2).tolist(),
            "adj_lo_pp": np.round(lo * 100, 2).tolist(), "adj_hi_pp": np.round(hi * 100, 2).tolist(),
            "mean_def_ft": float(d.CLOSE_DEF_DIST.mean()), "n_boot": N_BOOT}


def distance_curve():
    """Acierto por distancia del tiro (nuestras 4 temporadas), relativo al promedio de la liga.
    Reemplaza la penalización escrita a mano del simulador."""
    d = pd.read_csv("data/processed/shots_fatigue_processed.csv", usecols=["SHOT_DISTANCE", "SHOT_MADE_FLAG"])
    d = d[(d.SHOT_DISTANCE >= 0) & (d.SHOT_DISTANCE <= 40)]
    league = d.SHOT_MADE_FLAG.mean()
    by = d.groupby("SHOT_DISTANCE").SHOT_MADE_FLAG.agg(["mean", "size"])
    by = by.reindex(range(0, 41))
    raw = (by["mean"] - league) * 100
    smooth = raw.rolling(3, center=True, min_periods=1).mean()          # suaviza el ruido de pies con pocos tiros
    return {"league_fg_pct": float(league * 100), "adj_pp": [round(float(x), 2) for x in smooth.ffill().bfill()],
            "n": [int(x) if x == x else 0 for x in by["size"]], "source": "NBA 2021-22 a 2024-25 (nuestros datos)"}


def defender_gap():
    """¿Cuánto mejora un modelo de tiro esperado al conocer la distancia al defensor? (2014-15, validación por partido)"""
    from sklearn.metrics import log_loss, roc_auc_score
    from sklearn.model_selection import GroupKFold
    d = pd.read_csv("data/raw/external/shot_logs_2014/shot_logs_2014.csv")
    d = d[(d.SHOT_DIST > 0) & (d.TOUCH_TIME >= 0)].copy()
    d["IS3"] = (d.PTS_TYPE == 3).astype(int)
    y, g = d.FGM.values, d.GAME_ID.values
    base = ["SHOT_DIST", "IS3", "PERIOD"]
    sets = [("Sin datos del defensor (como nuestro modelo)", base),
            ("Con la distancia al defensor", base + ["CLOSE_DEF_DIST"]),
            ("Con defensor, reloj de posesión, toques y regates", base + ["CLOSE_DEF_DIST", "SHOT_CLOCK", "TOUCH_TIME", "DRIBBLES"])]
    rows = []
    for name, cols in sets:
        p = np.zeros(len(d))
        for tr, te in GroupKFold(5).split(d, y, g):
            m = HistGradientBoostingClassifier(max_iter=150, learning_rate=0.08, random_state=0).fit(d.iloc[tr][cols], y[tr])
            p[te] = m.predict_proba(d.iloc[te][cols])[:, 1]
        rows.append({"model": name, "auc": float(roc_auc_score(y, p)), "log_loss": float(log_loss(y, p))})
    return {"n": int(len(d)), "rows": rows, "baseline_log_loss": float(log_loss(y, np.full(len(y), y.mean())))}


def main():
    os.makedirs(OUT, exist_ok=True)
    args = set(sys.argv[1:])
    run_all = not args
    cpath = os.path.join(OUT, "contest.json")
    if run_all or "team" in args:
        print("🛡️  Efecto defensivo por equipo...")
        td = team_defense()
        print("   temporada", td["season"], "| estabilidad entre temporadas r =", [round(x, 2) for x in td["stability_r"]])
        json.dump(td, open(os.path.join(OUT, "defense.json"), "w", encoding="utf-8"), ensure_ascii=False)
    if run_all or "contest" in args:
        print("📏 Tabla de distancia al defensor (2014-15) con bootstrap...")
        old_gap = json.load(open(cpath, encoding="utf-8")).get("gap") if os.path.exists(cpath) else None
        ct = contest_table()
        if old_gap:
            ct["gap"] = old_gap                    # se conserva la brecha de precisión ya calculada
        json.dump(ct, open(cpath, "w", encoding="utf-8"))
    if run_all or "gap" in args:
        ct = json.load(open(cpath, encoding="utf-8"))
        ct["gap"] = defender_gap()
        json.dump(ct, open(cpath, "w", encoding="utf-8"))
        print("   brecha de precisión:", [(r["model"][:22], round(r["auc"], 3)) for r in ct["gap"]["rows"]])
    if run_all or "distance" in args:
        json.dump(distance_curve(), open(os.path.join(OUT, "distance.json"), "w", encoding="utf-8"))
    print("✅ datos de defensa listos en", OUT)


if __name__ == "__main__":
    main()
