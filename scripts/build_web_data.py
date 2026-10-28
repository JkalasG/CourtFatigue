"""
Export the analysis results to JSON for the web interface (web/).

Input : data/processed/shots_fatigue_processed.csv (output of src/xshot_model.py)
Output: web/data/summary.json, web/data/players.json, web/data/shots/<PLAYER_ID>.json

Usage: python scripts/build_web_data.py
"""

import json
import math
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import fatigue_stats as fs  # noqa: E402

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

SRC = "data/processed/shots_fatigue_processed.csv"
OUT = "web/data"
SHORT_LO, SHORT, LONG = fs.SHORT_LO_DEFAULT, fs.SHORT_DEFAULT, fs.LONG_DEFAULT
EDGES = [0, 2, 4, 6, 8, 10, 12, 24]
ZONES = ["Restricted Area", "In The Paint (Non-RA)", "Mid-Range",
         "Left Corner 3", "Right Corner 3", "Above the Break 3"]
MIN_PLAYER_SHOTS = 100


def clean(o):
    """Turn NaN/inf and numpy types into valid JSON."""
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        return None if (math.isnan(o) or math.isinf(o)) else round(float(o), 5)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return o


def meta_regression(t: pd.DataFrame, het: dict, feats: pd.DataFrame) -> list:
    """Does the effect depend on any player trait? Weighted meta-regression."""
    rows = []
    d = t.merge(feats, left_on="PLAYER_ID", right_index=True)
    w = 1.0 / (d.se ** 2 + het["tau2"])
    for col, label in (("share3", "% of 3-point shots"), ("share_rim", "% of shots at the rim"),
                       ("share_mid", "% of mid-range shots"), ("avg_dist", "Average shot distance"),
                       ("avg_xshot", "Average shot difficulty (xShot)"), ("log_shots", "Shot volume"),
                       ("avg_stint", "Average stint length (role)")):
        x = d[col].values.astype(float)
        sd = x.std()
        if sd == 0:
            continue
        z = (x - np.average(x, weights=w)) / sd
        xbar = np.average(z, weights=w)
        sxx = np.sum(w * (z - xbar) ** 2)
        b = np.sum(w * (z - xbar) * (d.effect.values - np.average(d.effect.values, weights=w))) / sxx
        se = math.sqrt(1.0 / sxx)
        p = 2 * (1 - float(fs._norm_cdf(abs(b / se))))
        rows.append({"feature": label, "coef_pp": b * 100, "lo_pp": (b - fs.Z95 * se) * 100,
                     "hi_pp": (b + fs.Z95 * se) * 100, "p": p})
    q = fs.benjamini_hochberg(np.array([r["p"] for r in rows]))
    for r, qq in zip(rows, q):
        r["q"] = float(qq)
    return rows


def main():
    print("Reading", SRC)
    df_all = pd.read_csv(SRC, low_memory=False, dtype={"SEASON": str})
    df_all["is_home"] = df_all.is_home.astype(float)
    seasons = sorted(df_all.SEASON.unique())
    # Schedule context: did the team play the day before (back-to-back)?
    games = df_all[["TEAM_ID", "GAME_ID", "GAME_DATE"]].drop_duplicates().copy()
    games["date"] = pd.to_datetime(games.GAME_DATE.astype(str), format="%Y%m%d")
    games = games.sort_values(["TEAM_ID", "date"])
    games["b2b"] = (games.groupby("TEAM_ID").date.diff().dt.days <= 1).astype(float)
    df_all = df_all.merge(games[["TEAM_ID", "GAME_ID", "b2b"]], on=["TEAM_ID", "GAME_ID"], how="left")
    df_all["b2b"] = df_all.b2b.fillna(0.0)
    n_inferred = int(df_all.stint_inferred.sum())
    df = df_all[~df_all.stint_inferred].copy()  # main analysis: reliable stints only
    print(f"   {len(df_all):,} shots; {n_inferred:,} with inferred stint excluded from the main analysis")

    # ---- Population effect ----
    print("Population effects...")
    buckets = fs.bucket_effects(df, EDGES)
    full = ["stint_minutes", "game_minutes_played", "is_home", "score_margin", "b2b"]
    slopes = {
        "principal": fs.fe_slope(df, ["stint_minutes"]).iloc[0].to_dict(),
        "con_controles": fs.fe_slope(df, full).to_dict("records"),
    }

    def spec(label, data, cols=("stint_minutes",)):
        r = fs.fe_slope(data, list(cols)).iloc[0]
        return {"label": label, "coef_pp": r.coef_pp, "lo_pp": r.lo_pp, "hi_pp": r.hi_pp, "n": int(r.n)}

    margin_abs = df.score_margin.abs()
    robustness = [
        spec("Main analysis (all buckets)", df),
        spec("Warmed up only (from 2 min)", df[df.stint_minutes >= SHORT_LO]),
        spec("Excluding blowouts (margin < 20)", df[margin_abs < 20]),
        spec("Close games only (margin ≤ 10)", df[margin_abs <= 10]),
        spec("With controls: game minutes, home, score, back-to-back", df, full),
        spec("Counter resets every quarter", df, ("stint_minutes_quarter",)),
        spec("Includes shots with uncertain stint", df_all),
    ]
    replication = fs.season_replication(df, SHORT, LONG, SHORT_LO)
    cold_by_season = []
    for sea, d in df.groupby("SEASON"):
        r0 = fs.cold_start_table(d)[0]
        cold_by_season.append({"season": sea, "n": r0["n"], "effect_pp": r0["effect_pp"], "lo_pp": r0["lo_pp"], "hi_pp": r0["hi_pp"]})
    cold = fs.cold_start_table(df)
    # Cold-start robustness: same calculation with the counter reset every quarter
    cold_quarter = fs.cold_start_table(df, "stint_minutes_quarter")[:4]
    contr = fs.contrast_by_player(df, SHORT, LONG, short_lo=SHORT_LO)
    # "naive" contrast against everything < 4 min (includes the cold start), for reference only
    contr_cold = fs.contrast_by_player(df, 4.0, LONG, short_lo=0.0)
    het_cold = fs.heterogeneity(contr_cold.effect, contr_cold.se)
    het = fs.heterogeneity(contr.effect, contr.se)
    contr = fs.flag_players(contr, het["mu"], het["tau2"])
    print(f"   long-short contrast: mu={het['mu']*100:.2f} pp [{het['mu_lo']*100:.2f}, {het['mu_hi']*100:.2f}], "
          f"tau={het['tau']*100:.2f} pp, players={het['k']}, flagged={int(contr.flag.sum())}")
    zone = fs.zone_slopes(df[df.stint_minutes >= SHORT_LO], ZONES)  # after warm-up: the cold start is not fatigue
    zone_fg = df.groupby("SHOT_ZONE_BASIC").SHOT_MADE_FLAG.mean().to_dict()
    zone_share = (df.SHOT_ZONE_BASIC.value_counts(normalize=True)).to_dict()

    print("Placebo test (may take a while)...")
    placebo = fs.placebo_flag_rate(df, SHORT, LONG, n_perm=20, short_lo=SHORT_LO)
    print("   ", {k: (round(v, 3) if isinstance(v, float) else v) for k, v in placebo.items()})

    # ---- Player traits (meta-regression) ----
    df = fs.add_dev(df)  # residual relative to each player's average in each season
    g = df.groupby("PLAYER_ID")
    feats = pd.DataFrame({
        "share3": g.apply(lambda s: (s.SHOT_TYPE == "3PT Field Goal").mean(), include_groups=False),
        "share_rim": g.apply(lambda s: (s.SHOT_ZONE_BASIC == "Restricted Area").mean(), include_groups=False),
        "share_mid": g.apply(lambda s: (s.SHOT_ZONE_BASIC == "Mid-Range").mean(), include_groups=False),
        "avg_dist": g.SHOT_DISTANCE.mean(), "avg_xshot": g.xShot.mean(),
        "log_shots": np.log(g.size()), "avg_stint": g.stint_minutes.mean(),
    })
    metareg = meta_regression(contr, het, feats)

    # ---- Data coverage per bucket ----
    cov = df.assign(b=pd.cut(df.stint_minutes, EDGES, right=False)).groupby("b", observed=True).agg(
        n=("SHOT_MADE_FLAG", "size"), fg=("SHOT_MADE_FLAG", "mean"), xfg=("xShot", "mean"),
        players=("PLAYER_ID", "nunique")).reset_index()
    cov["lo"] = [e.left for e in cov.b]
    cov["hi"] = [e.right for e in cov.b]
    cov = cov.drop(columns="b")
    long_players = df[df.stint_minutes >= LONG].groupby("PLAYER_ID").size()

    xmetrics = {}
    if os.path.exists("data/processed/xshot_metrics.json"):
        xmetrics = json.load(open("data/processed/xshot_metrics.json", encoding="utf-8"))

    summary = {
        "season": f"NBA {seasons[0]}-{str(int(seasons[0]) + 1)[2:]} to {seasons[-1]}-{str(int(seasons[-1]) + 1)[2:]} (regular season)",
        "seasons": seasons, "robustness": robustness, "replication": replication, "cold_by_season": cold_by_season,
        "n_games": int(df_all.GAME_ID.nunique()), "n_shots": int(len(df_all)),
        "n_shots_analysis": int(len(df)), "n_inferred": n_inferred,
        "n_players": int(df_all.PLAYER_ID.nunique()),
        "short": SHORT, "short_lo": SHORT_LO, "long": LONG, "heterogeneity_vs_cold": het_cold,
        "buckets": buckets.to_dict("records"), "coverage": cov.to_dict("records"),
        "slopes": slopes, "heterogeneity": het, "zone_slopes": zone.to_dict("records"),
        "zone_fg": zone_fg, "zone_share": zone_share, "placebo": placebo, "metareg": metareg,
        "players_with_long_30": int((long_players >= 30).sum()),
        "n_flagged": int(contr.flag.sum()), "n_contrast_players": int(len(contr)),
        "xshot": xmetrics, "cold_start": cold, "cold_start_quarter": cold_quarter,
        # minimum detectable effect per player (80% power, 5% error, no multiplicity correction)
        "power": {"median_se_pp": float(contr.se.median() * 100), "mde_pp": float(2.8 * contr.se.median() * 100)},
    }
    os.makedirs(os.path.join(OUT, "shots"), exist_ok=True)
    with open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(clean(summary), f, ensure_ascii=False)

    # ---- Players ----
    print("Players and shots...")
    cmap = contr.set_index("PLAYER_ID")
    players = []
    counts = df_all.PLAYER_ID.value_counts()
    for pid in counts[counts >= MIN_PLAYER_SHOTS].index:
        d_all = df_all[df_all.PLAYER_ID == pid]
        d = d_all[~d_all.stint_inferred]
        if len(d) < MIN_PLAYER_SHOTS:
            continue
        d = fs.add_dev(d)
        b = []
        for lo, hi in zip(EDGES[:-1], EDGES[1:]):
            s = d[(d.stint_minutes >= lo) & (d.stint_minutes < hi)]
            n = len(s)
            if n >= 2:
                se = s.dev.std() / math.sqrt(n)
                dev = s.dev.mean()
                b.append({"lo": lo, "hi": hi, "n": n, "fg": s.SHOT_MADE_FLAG.mean(), "xfg": s.xShot.mean(),
                          "dev_pp": dev * 100, "lo_pp": (dev - fs.Z95 * se) * 100, "hi_pp": (dev + fs.Z95 * se) * 100})
            else:
                b.append({"lo": lo, "hi": hi, "n": n})
        team = d_all.groupby("TEAM_ID").size().idxmax()
        row = {"id": int(pid), "name": d_all.PLAYER_NAME.iloc[0], "team": d_all[d_all.TEAM_ID == team].TEAM_NAME.iloc[0],
               "team_id": int(team), "n": int(len(d_all)), "fg": d_all.SHOT_MADE_FLAG.mean(), "xfg": d_all.xShot.mean(),
               "buckets": b, "contrast": None, "seasons": int(d_all.SEASON.nunique())}
        if pid in cmap.index:
            c = cmap.loc[pid]
            row["contrast"] = {"effect_pp": c.effect * 100, "lo_pp": c.lo * 100, "hi_pp": c.hi * 100,
                               "se_pp": c.se * 100, "q": c.q, "flag": bool(c.flag), "shrunk_pp": c.shrunk * 100,
                               "n_s": int(c.n_s), "n_l": int(c.n_l)}
        players.append(row)
        with open(os.path.join(OUT, "shots", f"{int(pid)}.json"), "w", encoding="utf-8") as f:
            json.dump({"x": d_all.LOC_X.astype(int).tolist(), "y": d_all.LOC_Y.astype(int).tolist(),
                       "m": d_all.SHOT_MADE_FLAG.astype(int).tolist(),
                       "s": (d_all.stint_minutes * 10).round().astype(int).tolist(),
                       "i": d_all.stint_inferred.astype(int).tolist()}, f, separators=(",", ":"))
    players.sort(key=lambda r: -r["n"])
    with open(os.path.join(OUT, "players.json"), "w", encoding="utf-8") as f:
        json.dump(clean(players), f, ensure_ascii=False, separators=(",", ":"))
    print(f"Exported {len(players)} players to {OUT}/")


if __name__ == "__main__":
    main()
