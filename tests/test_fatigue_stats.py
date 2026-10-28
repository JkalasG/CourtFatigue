"""
Tests of the statistics module on synthetic data (the correct answer is known).
Run:  python tests/test_fatigue_stats.py    (or with pytest)
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import fatigue_stats as fs  # noqa: E402


def make_league(n_players=300, shots=400, effect=0.0, share_affected=1.0, seed=0):
    """45% accuracy (fixed xShot). With stint >= 8 min it drops by `effect` for a `share_affected` fraction of players."""
    rng = np.random.default_rng(seed)
    rows = []
    for pid in range(n_players):
        stint = rng.uniform(0, 12, shots)
        hit = pid < n_players * share_affected
        p = np.where((stint >= 8) & hit, 0.45 + effect, 0.45)
        made = (rng.random(shots) < p).astype(float)
        rows.append(pd.DataFrame({"PLAYER_ID": pid, "stint_minutes": stint, "stint_minutes_quarter": stint,
                                  "shot_residual": made - 0.45}))
    return pd.concat(rows, ignore_index=True)


def population(df):
    t = fs.contrast_by_player(df)
    het = fs.heterogeneity(t.effect, t.se)
    return t, het, fs.flag_players(t, het["mu"], het["tau2"])


def test_null_world_marks_nobody():
    t, het, f = population(make_league(effect=0.0))
    assert het["mu_lo"] < 0 < het["mu_hi"], het
    assert f.flag.mean() < 0.01, f.flag.mean()      # the procedure does not invent fatigue


def test_planted_effect_is_detected():
    df = make_league(effect=-0.06)
    t, het, f = population(df)
    assert het["mu_hi"] < 0, het                     # average drop detected
    assert abs(het["mu"] - (-0.06)) < 0.01, het["mu"]
    slope = fs.fe_slope(df, ["stint_minutes"]).iloc[0]
    assert slope.hi_pp < 0, slope                    # the slope is negative too


def test_heterogeneous_world_flags_only_the_affected():
    # ~330 shots per bucket -> standard error ~4 pp: only large drops are detectable per player
    df = make_league(n_players=300, shots=1000, effect=-0.15, share_affected=0.3, seed=1)
    t, het, f = population(df)
    affected = f[f.PLAYER_ID < 90]
    unaffected = f[f.PLAYER_ID >= 90]
    assert affected.flag.mean() > 0.5, affected.flag.mean()     # detects a good share of the affected
    assert unaffected.flag.mean() < 0.02, unaffected.flag.mean()  # almost no false positives
    assert het["tau"] > 0.02, het                                # and estimates heterogeneity


def test_naive_rule_fires_on_noise():
    df = make_league(n_players=200, shots=300, effect=0.0, seed=2)
    r = fs.placebo_flag_rate(df, 4.0, 8.0, n_perm=3)
    assert r["naive_real"] > 0.3, r                  # the "drop >= 3 pp" rule flags many with no fatigue at all
    assert r["inference_real"] < 0.02, r             # the inference-based rule does not


def test_new_player_projection_moves_toward_own_data():
    prior = {"mu": 0.0, "tau2": 0.0004, "se_mu": 0.004}
    alone = fs.project_new_player(prior, 0.45)
    own = fs.project_new_player(prior, 0.45, {"n_s": 800, "fg_s": 0.50, "n_l": 800, "fg_l": 0.40})
    assert abs(alone["effect"]) < 1e-9
    # the observed value (-10 pp) is shrunk toward the prior (0) but clearly moves toward it
    assert -0.10 < own["effect"] < -0.03, own["effect"]
    assert own["hi"] - own["lo"] < alone["hi"] - alone["lo"]  # and uncertainty drops


def test_season_fixed_effects_remove_skill_drift():
    """A player improves between seasons and plays longer stints in the better one, with no fatigue at all.
    Comparing only with the overall mean invents an effect; comparing within each season does not."""
    rng = np.random.default_rng(3)
    parts = []
    for pid in range(200):
        for season, lo, hi, p in (("A", 0, 4, 0.40), ("B", 8, 12, 0.50)):   # A: short stints only; B: long stints only
            stint = rng.uniform(lo, hi, 300)
            made = (rng.random(300) < p).astype(float)
            parts.append(pd.DataFrame({"PLAYER_ID": pid, "SEASON": season, "stint_minutes": stint,
                                       "shot_residual": made - 0.45}))
    df = pd.concat(parts, ignore_index=True)

    def mu(d):
        t = fs.contrast_by_player(d)
        return fs.heterogeneity(t.effect, t.se)["mu"]

    assert abs(mu(df)) < 0.01, mu(df)                          # per season: no effect, as it should be
    assert mu(df.drop(columns="SEASON")) > 0.05, "without the season key a spurious effect should appear"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok ", name)
