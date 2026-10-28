"""
Defense data for the 3D simulator (web/data/defense.json, contest.json, distance.json).

1) Team defensive effect (our 2021-25 seasons): opponent accuracy minus what shot difficulty
   and the shooter themselves predict (`dev`), averaged per team-season and shrunk toward the
   league mean. The latest season is published. It is a team AVERAGE, not a single defender.

2) Defender distance (2014-15 shot log, CC0, 128k shots; data/raw/external/): a monotone
   gradient-boosting model (more defender distance => never less accuracy) and a table
   P(make | shot distance, defender distance) with a game-bootstrap confidence band. The
   simulator uses the DIFFERENCE from the TYPICAL defender distance for that shot type
   (median per shot distance), so it is an adjustment rather than an absolute probability and
   does not double count what the shot-distance curve already includes.

Usage: python scripts/build_defense_data.py             (everything, ~10 min because of the bootstrap)
       python scripts/build_defense_data.py contest     (defender-distance table only)
       python scripts/build_defense_data.py team        (team defensive effect only)
       python scripts/build_defense_data.py distance    (shot-distance curve only)
       python scripts/build_defense_data.py gap         (accuracy with/without defender data only)
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
SHOT_GRID = list(range(0, 41, 2))           # shot distance, feet
DEF_GRID = [round(x * 0.5, 1) for x in range(0, 25)]   # defender distance, 0 to 12 feet
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
    # true between-team variance (method of moments) per season, and empirical-Bayes shrinkage
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
            sd = math.sqrt(B * r.se2)          # posterior uncertainty
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

    # Reference: TYPICAL defender distance for each shot distance (median in a +/-1.5 ft window).
    # The accuracy-by-shot-distance curve already includes how closely that shot type is usually
    # guarded, so the defender adjustment is measured against that typical level, not a fixed distance.
    ref_def = []
    for sd in SHOT_GRID:
        near = d.CLOSE_DEF_DIST[(d.SHOT_DIST - sd).abs() <= 1.5]
        if len(near) < 300:
            near = d.CLOSE_DEF_DIST[(d.SHOT_DIST - sd).abs() <= 3.5]
        ref_def.append(float(near.median()) if len(near) >= 100 else float(d.CLOSE_DEF_DIST.median()))
    ref = pd.DataFrame([(sd, 1 if sd >= 23 else 0, r) for sd, r in zip(SHOT_GRID, ref_def)], columns=feats)

    def fit_predict(data):
        m = HistGradientBoostingClassifier(max_iter=120, learning_rate=0.08, max_depth=4, random_state=0,
                                           monotonic_cst=[0, 0, 1])   # more defender distance => accuracy never drops
        m.fit(data[feats], data.FGM)
        p = m.predict_proba(grid)[:, 1].reshape(len(SHOT_GRID), len(DEF_GRID))
        p0 = m.predict_proba(ref)[:, 1][:, None]
        return p, p - p0

    p_hat, adj_hat = fit_predict(d)
    boots = []
    for b in range(N_BOOT):
        pick = rng.choice(games, size=len(games), replace=True)
        sample = d.merge(pd.DataFrame({"GAME_ID": pick}), on="GAME_ID")   # resample games with replacement
        boots.append(fit_predict(sample)[1])
        print(f"   bootstrap {b + 1}/{N_BOOT}")
    B = np.stack(boots)
    lo, hi = np.percentile(B, 2.5, axis=0), np.percentile(B, 97.5, axis=0)
    return {"source": "NBA 2014-15 shot log (CC0), %d shots" % len(d), "ref_def_by_shot_ft": [round(r, 2) for r in ref_def],
            "shot_grid_ft": SHOT_GRID, "def_grid_ft": DEF_GRID,
            "p": np.round(p_hat * 100, 2).tolist(), "adj_pp": np.round(adj_hat * 100, 2).tolist(),
            "adj_lo_pp": np.round(lo * 100, 2).tolist(), "adj_hi_pp": np.round(hi * 100, 2).tolist(),
            "mean_def_ft": float(d.CLOSE_DEF_DIST.mean()), "n_boot": N_BOOT}


def distance_curve():
    """Accuracy by shot distance (our 4 seasons), relative to the league average.
    Replaces the simulator's hand-written penalty."""
    d = pd.read_csv("data/processed/shots_fatigue_processed.csv", usecols=["SHOT_DISTANCE", "SHOT_MADE_FLAG"])
    d = d[(d.SHOT_DISTANCE >= 0) & (d.SHOT_DISTANCE <= 40)]
    league = d.SHOT_MADE_FLAG.mean()
    by = d.groupby("SHOT_DISTANCE").SHOT_MADE_FLAG.agg(["mean", "size"])
    by = by.reindex(range(0, 41))
    raw = (by["mean"] - league) * 100
    smooth = raw.rolling(3, center=True, min_periods=1).mean()          # smooth the noise of feet with few shots
    return {"league_fg_pct": float(league * 100), "adj_pp": [round(float(x), 2) for x in smooth.ffill().bfill()],
            "n": [int(x) if x == x else 0 for x in by["size"]], "source": "NBA 2021-22 to 2024-25 (our data)"}


def defender_gap():
    """How much does an expected-shot model improve when the defender distance is known? (2014-15, game-grouped validation)"""
    from sklearn.metrics import log_loss, roc_auc_score
    from sklearn.model_selection import GroupKFold
    d = pd.read_csv("data/raw/external/shot_logs_2014/shot_logs_2014.csv")
    d = d[(d.SHOT_DIST > 0) & (d.TOUCH_TIME >= 0)].copy()
    d["IS3"] = (d.PTS_TYPE == 3).astype(int)
    y, g = d.FGM.values, d.GAME_ID.values
    base = ["SHOT_DIST", "IS3", "PERIOD"]
    sets = [("Without defender data (like our model)", base),
            ("With defender distance", base + ["CLOSE_DEF_DIST"]),
            ("With defender, shot clock, touch time and dribbles", base + ["CLOSE_DEF_DIST", "SHOT_CLOCK", "TOUCH_TIME", "DRIBBLES"])]
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
        print("Team defensive effect...")
        td = team_defense()
        print("   season", td["season"], "| between-season stability r =", [round(x, 2) for x in td["stability_r"]])
        json.dump(td, open(os.path.join(OUT, "defense.json"), "w", encoding="utf-8"), ensure_ascii=False)
    if run_all or "contest" in args:
        print("Defender-distance table (2014-15) with bootstrap...")
        old_gap = json.load(open(cpath, encoding="utf-8")).get("gap") if os.path.exists(cpath) else None
        ct = contest_table()
        if old_gap:
            ct["gap"] = old_gap                    # keep the accuracy gap already computed
        json.dump(ct, open(cpath, "w", encoding="utf-8"))
    if run_all or "gap" in args:
        ct = json.load(open(cpath, encoding="utf-8"))
        ct["gap"] = defender_gap()
        json.dump(ct, open(cpath, "w", encoding="utf-8"))
        print("   accuracy gap:", [(r["model"][:22], round(r["auc"], 3)) for r in ct["gap"]["rows"]])
    if run_all or "distance" in args:
        json.dump(distance_curve(), open(os.path.join(OUT, "distance.json"), "w", encoding="utf-8"))
    print("Defense data ready in", OUT)


if __name__ == "__main__":
    main()
