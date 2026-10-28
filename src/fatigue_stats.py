"""
CourtFatigue - Estadística del efecto de fatiga (inferencia, no solo descripción)

Estimando principal ("contraste largo vs corto"), por jugador:
    C_i = residuo medio del jugador con stint >= LONG  -  residuo medio con SHORT_LO <= stint < SHORT
(la referencia empieza en 2 min para excluir el arranque frío, que no es fatiga)
donde residuo = SHOT_MADE_FLAG - xShot. Al restar dentro del mismo jugador, su nivel
base (efecto fijo) se cancela. C_i < 0 significa que rinde peor tras muchos minutos seguidos.

Qué ofrece este módulo:
  * contraste_por_jugador: C_i con error estándar e IC95.
  * heterogeneidad: promedio poblacional mu y varianza entre jugadores tau^2
    (DerSimonian-Laird). Si tau^2 ~ 0, los jugadores no se distinguen entre sí.
  * recomendación por jugador: solo si el IC excluye 0 tras corregir por
    comparaciones múltiples (Benjamini-Hochberg). Si no, no se recomienda nada.
  * pendiente poblacional (regresión con efectos fijos, errores robustos por jugador).
  * prueba placebo: repite el procedimiento con los minutos barajados dentro de cada
    jugador, donde la fatiga no puede existir, para medir la tasa de falsos positivos.
  * proyección para un jugador nuevo: distribución previa N(mu, tau^2) actualizada con
    sus propios tiros (si los hay).
"""

import math
import numpy as np
import pandas as pd

Z95 = 1.959964
SHORT_LO_DEFAULT = 2.0   # referencia "ya calentado": entre 2 y 6 min (excluye el arranque frío)
SHORT_DEFAULT = 6.0
LONG_DEFAULT = 8.0
MIN_SHOTS_GROUP = 15  # tiros mínimos en cada grupo (corto y largo) para estimar C_i


def fe_keys(df: pd.DataFrame) -> list:
    """Con varias temporadas, cada jugador se compara con su propio nivel EN ESA temporada."""
    return ["PLAYER_ID", "SEASON"] if "SEASON" in df.columns else ["PLAYER_ID"]


def add_dev(df: pd.DataFrame) -> pd.DataFrame:
    """Añade `dev` = residuo menos el promedio del jugador (y temporada)."""
    df = df.copy()
    df["dev"] = df.shot_residual - df.groupby(fe_keys(df)).shot_residual.transform("mean")
    return df


def _norm_cdf(z):
    return 0.5 * (1.0 + np.vectorize(math.erf)(np.asarray(z) / math.sqrt(2.0)))


def benjamini_hochberg(pvals: np.ndarray) -> np.ndarray:
    """Valores q (FDR) de Benjamini-Hochberg."""
    p = np.asarray(pvals, dtype=float)
    n = len(p)
    order = np.argsort(p)
    ranked = p[order] * n / (np.arange(n) + 1)
    q = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(n)
    out[order] = np.minimum(q, 1.0)
    return out


def contrast_by_player(df: pd.DataFrame, short: float = SHORT_DEFAULT, long: float = LONG_DEFAULT,
                       stint_col: str = "stint_minutes", min_shots: int = MIN_SHOTS_GROUP,
                       short_lo: float = SHORT_LO_DEFAULT) -> pd.DataFrame:
    """C_i, su error estándar e IC95 para cada jugador con muestra suficiente en ambos grupos."""
    d = add_dev(df)[["PLAYER_ID", stint_col, "dev"]]
    s = d[(d[stint_col] >= short_lo) & (d[stint_col] < short)].groupby("PLAYER_ID").dev.agg(n_s="size", m_s="mean", v_s="var")
    l = d[d[stint_col] >= long].groupby("PLAYER_ID").dev.agg(n_l="size", m_l="mean", v_l="var")
    t = s.join(l, how="inner")
    t = t[(t.n_s >= min_shots) & (t.n_l >= min_shots)].copy()
    t["effect"] = t.m_l - t.m_s
    t["se"] = np.sqrt(t.v_s / t.n_s + t.v_l / t.n_l)
    t["lo"] = t.effect - Z95 * t.se
    t["hi"] = t.effect + Z95 * t.se
    t["p"] = 2 * (1 - _norm_cdf(np.abs(t.effect / t.se)))
    t["q"] = benjamini_hochberg(t.p.values) if len(t) else np.array([])
    return t.reset_index()


def heterogeneity(effects: pd.Series, se: pd.Series) -> dict:
    """Media poblacional y varianza entre jugadores (DerSimonian-Laird)."""
    y = effects.values.astype(float)
    w = 1.0 / se.values.astype(float) ** 2
    mu_fe = np.sum(w * y) / np.sum(w)
    q = np.sum(w * (y - mu_fe) ** 2)
    k = len(y)
    c = np.sum(w) - np.sum(w ** 2) / np.sum(w)
    tau2 = max(0.0, (q - (k - 1)) / c)
    w_re = 1.0 / (se.values ** 2 + tau2)
    mu = np.sum(w_re * y) / np.sum(w_re)
    se_mu = math.sqrt(1.0 / np.sum(w_re))
    i2 = max(0.0, (q - (k - 1)) / q) if q > 0 else 0.0
    return {"mu": mu, "se_mu": se_mu, "mu_lo": mu - Z95 * se_mu, "mu_hi": mu + Z95 * se_mu,
            "tau2": tau2, "tau": math.sqrt(tau2), "Q": q, "k": k, "I2": i2,
            "p_het": float(1 - _chi2_cdf(q, k - 1))}


def _chi2_cdf(x, k):
    """CDF chi-cuadrado vía aproximación de Wilson-Hilferty (suficiente para k grande)."""
    if k <= 0:
        return 0.0
    z = ((x / k) ** (1 / 3) - (1 - 2 / (9 * k))) / math.sqrt(2 / (9 * k))
    return float(_norm_cdf(z))


def flag_players(t: pd.DataFrame, mu: float, tau2: float, alpha: float = 0.05) -> pd.DataFrame:
    """Marca recomendaciones (solo si hay evidencia tras FDR) y añade la estimación encogida."""
    t = t.copy()
    t["flag"] = (t.q < alpha) & (t.hi < 0)
    shrink = tau2 / (tau2 + t.se ** 2)
    t["shrunk"] = mu + shrink * (t.effect - mu)
    return t


def fe_slope(df: pd.DataFrame, xcols, stint_col: str = "stint_minutes") -> pd.DataFrame:
    """
    Regresión del residuo sobre variables (p. ej. minutos seguidos) con efectos fijos de
    jugador y errores robustos agrupados por jugador. Coeficientes en puntos porcentuales.
    """
    cols = list(xcols)
    keys = fe_keys(df)
    d = df[list(dict.fromkeys(keys + ["shot_residual"] + cols))].dropna()
    g = d.groupby(keys)
    y = (d.shot_residual - g.shot_residual.transform("mean")).values
    X = np.column_stack([(d[c] - g[c].transform("mean")).values for c in cols])
    xtx_inv = np.linalg.inv(X.T @ X)
    beta = xtx_inv @ X.T @ y
    e = y - X @ beta
    scores = pd.DataFrame(X * e[:, None], columns=cols)
    scores["pid"] = d.PLAYER_ID.values
    S = scores.groupby("pid")[cols].sum().values
    cov = xtx_inv @ (S.T @ S) @ xtx_inv
    se = np.sqrt(np.diag(cov))
    return pd.DataFrame({"term": cols, "coef_pp": beta * 100, "se_pp": se * 100,
                         "lo_pp": (beta - Z95 * se) * 100, "hi_pp": (beta + Z95 * se) * 100,
                         "n": len(d)})


def bucket_effects(df: pd.DataFrame, edges, stint_col: str = "stint_minutes") -> pd.DataFrame:
    """Residuo medio por tramo, relativo a la media de cada jugador (efectos fijos), IC95 por jugador."""
    d = add_dev(df)[["PLAYER_ID", stint_col, "dev"]].copy()
    d["bucket"] = pd.cut(d[stint_col], edges, right=False)
    rows = []
    for b, sub in d.groupby("bucket", observed=True):
        n = len(sub)
        per_player = sub.groupby("PLAYER_ID").dev.sum()
        se = math.sqrt((per_player ** 2).sum()) / n  # error estándar agrupado por jugador
        m = sub.dev.mean()
        rows.append({"lo_edge": b.left, "hi_edge": b.right, "n": n, "effect_pp": m * 100,
                     "lo_pp": (m - Z95 * se) * 100, "hi_pp": (m + Z95 * se) * 100})
    return pd.DataFrame(rows)


def zone_slopes(df: pd.DataFrame, zones, stint_col: str = "stint_minutes") -> pd.DataFrame:
    """Pendiente por zona (pp por minuto seguido) con efectos fijos y q de Benjamini-Hochberg."""
    rows = []
    for z in zones:
        sub = df[df.SHOT_ZONE_BASIC == z]
        if len(sub) < 500:
            continue
        r = fe_slope(sub, [stint_col]).iloc[0]
        p = 2 * (1 - float(_norm_cdf(abs(r.coef_pp / r.se_pp))))
        rows.append({"zone": z, "n": int(r.n), "coef_pp": r.coef_pp, "lo_pp": r.lo_pp, "hi_pp": r.hi_pp, "p": p})
    out = pd.DataFrame(rows)
    if len(out):
        out["q"] = benjamini_hochberg(out.p.values)
    return out


def placebo_flag_rate(df: pd.DataFrame, short: float, long: float, n_perm: int = 20, seed: int = 0,
                      short_lo: float = SHORT_LO_DEFAULT,
                      naive_drop_pp: float = 3.0, min_naive: int = 20, min_player_shots: int = 200) -> dict:
    """
    Tasa de jugadores 'marcados' con datos reales y con minutos barajados dentro de cada jugador.
    Compara la regla ingenua original (caída >= 3 pp en algún tramo con >= 20 tiros) con la
    regla basada en inferencia (IC95 < 0 y q < 0.05).
    """
    rng = np.random.default_rng(seed)
    big = df.groupby("PLAYER_ID").size()
    ids = big[big >= min_player_shots].index
    keep = fe_keys(df) + ["stint_minutes", "shot_residual"]
    d = df[df.PLAYER_ID.isin(ids)][keep].reset_index(drop=True)
    edges = [0, 2, 5, 8, 10, 99]

    def naive_rate(stint):
        tmp = pd.DataFrame({"pid": d.PLAYER_ID, "res": d.shot_residual, "b": pd.cut(stint, edges, right=False)})
        base = tmp.groupby("pid").res.transform("mean")
        tmp["dev"] = tmp.res - base
        g = tmp.groupby(["pid", "b"], observed=True).dev.agg(["size", "mean"]).reset_index()
        hit = g[(g["size"] >= min_naive) & (g["mean"] <= -naive_drop_pp / 100)].pid.nunique()
        return hit / len(ids)

    def inference_rate(stint):
        tmp = d.assign(stint_minutes=stint)
        t = contrast_by_player(tmp, short, long, short_lo=short_lo)
        if t.empty:
            return 0.0
        het = heterogeneity(t.effect, t.se)
        f = flag_players(t, het["mu"], het["tau2"])
        return float(f.flag.mean())

    real = (naive_rate(d.stint_minutes.values), inference_rate(d.stint_minutes.values))
    perm_naive, perm_inf = [], []
    for _ in range(n_perm):
        shuffled = d.groupby(fe_keys(d)).stint_minutes.transform(lambda s: rng.permutation(s.values))
        perm_naive.append(naive_rate(shuffled.values))
        perm_inf.append(inference_rate(shuffled.values))
    return {"n_players": int(len(ids)), "naive_real": real[0], "naive_placebo": float(np.mean(perm_naive)),
            "inference_real": real[1], "inference_placebo": float(np.mean(perm_inf)), "n_perm": n_perm}


def _cluster_mean(sub: pd.DataFrame, n_total_label: str = "dev") -> dict:
    """Media de la desviación (relativa al promedio del jugador) con IC95% agrupado por jugador."""
    n = len(sub)
    if n < 30:
        return {"n": n, "effect_pp": None, "lo_pp": None, "hi_pp": None}
    se = math.sqrt((sub.groupby("PLAYER_ID").dev.sum() ** 2).sum()) / n
    m = sub.dev.mean()
    return {"n": n, "effect_pp": m * 100, "lo_pp": (m - Z95 * se) * 100, "hi_pp": (m + Z95 * se) * 100}


def cold_start_table(df: pd.DataFrame, stint_col: str = "stint_minutes") -> list:
    """
    Rendimiento justo después de entrar a cancha (relativo al promedio de cada jugador).
    Devuelve filas {group, label, n, effect_pp, lo_pp, hi_pp}: por tramo de tiempo, por cuarto
    y según sea la primera entrada del jugador al partido o una re-entrada.
    """
    d = add_dev(df)
    rows = []

    def add(group, label, sub):
        rows.append({"group": group, "label": label, **_cluster_mean(sub)})

    for lo, hi, lab in ((0, 0.5, "0–30 s"), (0.5, 1, "30–60 s"), (1, 2, "1–2 min"), (2, 4, "2–4 min (referencia)")):
        add("Tiempo desde que entra", lab, d[(d[stint_col] >= lo) & (d[stint_col] < hi)])
    first_min = d[d[stint_col] < 1]
    re_entry = (first_min.game_minutes_played - first_min[stint_col]) > 0.5
    add("Primer minuto: ¿primera entrada?", "Primera vez en el partido", first_min[~re_entry])
    add("Primer minuto: ¿primera entrada?", "Re-entrada (ya jugó antes)", first_min[re_entry])
    for q in (1, 2, 3, 4):
        add("Primer minuto, por cuarto", f"Cuarto {q}", first_min[first_min.PERIOD == q])
    return rows


def season_replication(df: pd.DataFrame, short: float = SHORT_DEFAULT, long: float = LONG_DEFAULT,
                       short_lo: float = SHORT_LO_DEFAULT) -> list:
    """El mismo análisis, temporada por temporada: ¿se repite el resultado?"""
    rows = []
    for season, d in df.groupby("SEASON"):
        t = contrast_by_player(d, short, long, short_lo=short_lo)
        het = heterogeneity(t.effect, t.se)
        sl = fe_slope(d[d.stint_minutes >= short_lo], ["stint_minutes"]).iloc[0]  # pendiente tras calentar
        rows.append({"season": str(season), "n": int(len(d)), "mu_pp": het["mu"] * 100, "mu_lo_pp": het["mu_lo"] * 100,
                     "mu_hi_pp": het["mu_hi"] * 100, "slope_pp": sl.coef_pp, "slope_lo_pp": sl.lo_pp,
                     "slope_hi_pp": sl.hi_pp, "k": int(het["k"])})
    return rows


def project_new_player(prior: dict, base_fg: float, own: dict = None) -> dict:
    """
    Proyección para un jugador sin historial.
    prior: salida de heterogeneity() (mu, tau2).
    own  : opcional {"n_s","fg_s","n_l","fg_l"} con tiros propios (cortos/largos). Se combina por
           precisión: la media a posteriori se acerca a lo observado cuando hay muchos tiros.
    Devuelve el efecto largo-vs-corto esperado en pp con intervalo de predicción al 95%.
    """
    mu, tau2 = prior["mu"], prior["tau2"]
    post_mu, post_var = mu, tau2 + prior["se_mu"] ** 2
    if own and own.get("n_s", 0) > 0 and own.get("n_l", 0) > 0:
        p_s, p_l = own["fg_s"], own["fg_l"]
        obs = p_l - p_s
        obs_var = p_s * (1 - p_s) / own["n_s"] + p_l * (1 - p_l) / own["n_l"]
        prec = 1 / post_var + 1 / obs_var
        post_mu = (mu / post_var + obs / obs_var) / prec
        post_var = 1 / prec
    half = Z95 * math.sqrt(post_var)
    return {"effect": post_mu, "lo": post_mu - half, "hi": post_mu + half, "base_fg": base_fg,
            "fg_short": base_fg, "fg_long": base_fg + post_mu}
