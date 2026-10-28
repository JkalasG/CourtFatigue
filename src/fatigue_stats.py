"""
CourtFatigue - fatigue statistics (inference, not just description).

Main estimand, per player ("long vs. short contrast"):
    C_i = mean residual with stint >= LONG  -  mean residual with SHORT_LO <= stint < SHORT
where residual = SHOT_MADE_FLAG - xShot. Subtracting within the same player cancels their
baseline (fixed effect). C_i < 0 means the player shoots worse after many minutes in a row.
The reference starts at 2 min to exclude the cold start, which is not fatigue.

Contents:
  * contrast_by_player: C_i with standard error and 95% CI.
  * heterogeneity: population mean mu and between-player variance tau^2 (DerSimonian-Laird).
  * flag_players: a recommendation only if the CI excludes 0 after Benjamini-Hochberg correction.
  * fe_slope: population slope (fixed-effects regression, player-clustered robust errors).
  * placebo_flag_rate: repeats the procedure with minutes shuffled within each player
    (where fatigue cannot exist) to measure the false-positive rate.
  * project_new_player: prior N(mu, tau^2) updated with the player's own shots, if any.
"""

import math
import numpy as np
import pandas as pd

Z95 = 1.959964
SHORT_LO_DEFAULT = 2.0   # "warmed up" reference starts at 2 min (excludes the cold start)
SHORT_DEFAULT = 6.0
LONG_DEFAULT = 8.0
MIN_SHOTS_GROUP = 15     # minimum shots in each group (short and long) to estimate C_i


def fe_keys(df: pd.DataFrame) -> list:
    """With several seasons, each player is compared with their own level IN THAT season."""
    return ["PLAYER_ID", "SEASON"] if "SEASON" in df.columns else ["PLAYER_ID"]


def add_dev(df: pd.DataFrame) -> pd.DataFrame:
    """Add `dev` = residual minus the player(-season) mean."""
    df = df.copy()
    df["dev"] = df.shot_residual - df.groupby(fe_keys(df)).shot_residual.transform("mean")
    return df


def _norm_cdf(z):
    return 0.5 * (1.0 + np.vectorize(math.erf)(np.asarray(z) / math.sqrt(2.0)))


def benjamini_hochberg(pvals: np.ndarray) -> np.ndarray:
    """Benjamini-Hochberg q-values (FDR)."""
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
    """C_i, standard error and 95% CI for each player with enough shots in both groups."""
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
    """Population mean and between-player variance (DerSimonian-Laird)."""
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
    """Chi-square CDF via the Wilson-Hilferty approximation (fine for large k)."""
    if k <= 0:
        return 0.0
    z = ((x / k) ** (1 / 3) - (1 - 2 / (9 * k))) / math.sqrt(2 / (9 * k))
    return float(_norm_cdf(z))


def flag_players(t: pd.DataFrame, mu: float, tau2: float, alpha: float = 0.05) -> pd.DataFrame:
    """Flag players only with evidence after FDR; add the shrunken estimate."""
    t = t.copy()
    t["flag"] = (t.q < alpha) & (t.hi < 0)
    shrink = tau2 / (tau2 + t.se ** 2)
    t["shrunk"] = mu + shrink * (t.effect - mu)
    return t


def fe_slope(df: pd.DataFrame, xcols, stint_col: str = "stint_minutes") -> pd.DataFrame:
    """
    Regress the residual on covariates (e.g. consecutive minutes) with player fixed effects
    and player-clustered robust errors. Coefficients in percentage points.
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
    """Mean residual per bucket relative to each player's mean (fixed effects), player-clustered 95% CI."""
    d = add_dev(df)[["PLAYER_ID", stint_col, "dev"]].copy()
    d["bucket"] = pd.cut(d[stint_col], edges, right=False)
    rows = []
    for b, sub in d.groupby("bucket", observed=True):
        n = len(sub)
        per_player = sub.groupby("PLAYER_ID").dev.sum()
        se = math.sqrt((per_player ** 2).sum()) / n  # player-clustered standard error
        m = sub.dev.mean()
        rows.append({"lo_edge": b.left, "hi_edge": b.right, "n": n, "effect_pp": m * 100,
                     "lo_pp": (m - Z95 * se) * 100, "hi_pp": (m + Z95 * se) * 100})
    return pd.DataFrame(rows)


def zone_slopes(df: pd.DataFrame, zones, stint_col: str = "stint_minutes") -> pd.DataFrame:
    """Slope per zone (pp per consecutive minute) with fixed effects and Benjamini-Hochberg q."""
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
    Share of players flagged with real data and with minutes shuffled within each player.
    Compares the naive rule (drop >= 3 pp in any bucket with >= 20 shots) with the
    inference-based rule (95% CI < 0 and q < 0.05).
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
    """Mean deviation (relative to the player's average) with player-clustered 95% CI."""
    n = len(sub)
    if n < 30:
        return {"n": n, "effect_pp": None, "lo_pp": None, "hi_pp": None}
    se = math.sqrt((sub.groupby("PLAYER_ID").dev.sum() ** 2).sum()) / n
    m = sub.dev.mean()
    return {"n": n, "effect_pp": m * 100, "lo_pp": (m - Z95 * se) * 100, "hi_pp": (m + Z95 * se) * 100}


def cold_start_table(df: pd.DataFrame, stint_col: str = "stint_minutes") -> list:
    """
    Performance right after entering the court (relative to each player's average).
    Rows {group, label, n, effect_pp, lo_pp, hi_pp}: by time bucket, by quarter, and
    first appearance vs. re-entry.
    """
    d = add_dev(df)
    rows = []

    def add(group, label, sub):
        rows.append({"group": group, "label": label, **_cluster_mean(sub)})

    for lo, hi, lab in ((0, 0.5, "0–30 s"), (0.5, 1, "30–60 s"), (1, 2, "1–2 min"), (2, 4, "2–4 min (reference)")):
        add("Time since entering", lab, d[(d[stint_col] >= lo) & (d[stint_col] < hi)])
    first_min = d[d[stint_col] < 1]
    re_entry = (first_min.game_minutes_played - first_min[stint_col]) > 0.5
    add("First minute: first appearance?", "First time in the game", first_min[~re_entry])
    add("First minute: first appearance?", "Re-entry (played before)", first_min[re_entry])
    for q in (1, 2, 3, 4):
        add("First minute, by quarter", f"Quarter {q}", first_min[first_min.PERIOD == q])
    return rows


def season_replication(df: pd.DataFrame, short: float = SHORT_DEFAULT, long: float = LONG_DEFAULT,
                       short_lo: float = SHORT_LO_DEFAULT) -> list:
    """Same analysis, season by season: does the result repeat?"""
    rows = []
    for season, d in df.groupby("SEASON"):
        t = contrast_by_player(d, short, long, short_lo=short_lo)
        het = heterogeneity(t.effect, t.se)
        sl = fe_slope(d[d.stint_minutes >= short_lo], ["stint_minutes"]).iloc[0]  # slope after warm-up
        rows.append({"season": str(season), "n": int(len(d)), "mu_pp": het["mu"] * 100, "mu_lo_pp": het["mu_lo"] * 100,
                     "mu_hi_pp": het["mu_hi"] * 100, "slope_pp": sl.coef_pp, "slope_lo_pp": sl.lo_pp,
                     "slope_hi_pp": sl.hi_pp, "k": int(het["k"])})
    return rows


def project_new_player(prior: dict, base_fg: float, own: dict = None) -> dict:
    """
    Projection for a player with no history.
    prior: output of heterogeneity() (mu, tau2).
    own  : optional {"n_s","fg_s","n_l","fg_l"} with the player's own short/long shots, combined by
           precision: the posterior mean moves toward the observed value as shots accumulate.
    Returns the expected long-vs-short effect with a 95% prediction interval.
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
