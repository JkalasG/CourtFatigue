"""
CourtFatigue - expected shot (xShot) model and performance residual.

xShot = probability that a shot goes in given its intrinsic difficulty (distance, court
position, zone, shot mechanics). It does NOT use minutes on court or player identity, so the
residual (SHOT_MADE_FLAG - xShot) measures over/under-performance without absorbing the
effect we want to study.

Validation (two levels):
  1) game-grouped cross-validation (GroupKFold): every shot is predicted by a model that
     never saw its game; this produces the residual used in the analysis;
  2) TEMPORAL test: train on earlier seasons, evaluate on the last one, which the model
     never saw (the most honest accuracy measure).
Reported: log-loss, Brier, AUC and calibration error, comparing logistic regression with
gradient boosting; the one with the lower log-loss is used.
"""

import sys
import os
import json
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

CAT = ["SHOT_ZONE_BASIC", "ACTION_GROUP", "SHOT_TYPE", "PERIOD_GROUP"]
NUM = ["SHOT_DISTANCE_CAPPED", "LOC_X", "LOC_Y", "SECS_LEFT"]
FEATURES = CAT + NUM
METRICS_FILE = "data/processed/xshot_metrics.json"


def clean_action_type(action: str) -> str:
    """Group similar shot mechanics to make the model more robust."""
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


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ACTION_GROUP"] = df["ACTION_TYPE"].apply(clean_action_type)
    df["SHOT_DISTANCE_CAPPED"] = df["SHOT_DISTANCE"].clip(0, 35)
    df["PERIOD_GROUP"] = np.where(df["PERIOD"] > 4, "OT", df["PERIOD"].astype(str))
    df["SECS_LEFT"] = df["MINUTES_REMAINING"] * 60 + df["SECONDS_REMAINING"]
    return df


def _logistic():
    pre = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore", drop="first"), CAT),
        ("num", "passthrough", ["SHOT_DISTANCE_CAPPED"]),
    ])
    return Pipeline([("pre", pre), ("clf", LogisticRegression(max_iter=1000, C=1.0))])


def _boosting():
    pre = ColumnTransformer([
        ("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1), CAT),
        ("num", "passthrough", NUM),
    ])
    clf = HistGradientBoostingClassifier(
        max_depth=5, learning_rate=0.08, max_iter=250, l2_regularization=1.0,
        categorical_features=list(range(len(CAT))), random_state=42)
    return Pipeline([("pre", pre), ("clf", clf)])


def expected_calibration_error(y, p, bins=10) -> float:
    edges = np.quantile(p, np.linspace(0, 1, bins + 1))
    idx = np.clip(np.searchsorted(edges, p, side="right") - 1, 0, bins - 1)
    ece = 0.0
    for b in range(bins):
        m = idx == b
        if m.any():
            ece += m.mean() * abs(y[m].mean() - p[m].mean())
    return float(ece)


def cross_fitted_xshot(df: pd.DataFrame, n_splits: int = 5):
    """Out-of-sample (game-grouped) predictions with both models; returns the metrics."""
    df = add_features(df)
    ok = df[FEATURES + ["SHOT_MADE_FLAG"]].notna().all(axis=1)
    df = df[ok].reset_index(drop=True)
    y = df["SHOT_MADE_FLAG"].values
    groups = df["GAME_ID"].values
    preds = {"logistic": np.zeros(len(df)), "boosting": np.zeros(len(df))}
    for k, (tr, te) in enumerate(GroupKFold(n_splits=n_splits).split(df, y, groups), 1):
        print(f"   fold {k}/{n_splits}")
        for name, make in (("logistic", _logistic), ("boosting", _boosting)):
            m = make().fit(df.loc[tr, FEATURES], y[tr])
            preds[name][te] = m.predict_proba(df.loc[te, FEATURES])[:, 1]
    metrics = {}
    for name, p in preds.items():
        metrics[name] = {
            "log_loss": float(log_loss(y, p)), "brier": float(brier_score_loss(y, p)),
            "auc": float(roc_auc_score(y, p)), "ece": expected_calibration_error(y, p),
        }
    metrics["baseline_log_loss"] = float(log_loss(y, np.full(len(y), y.mean())))
    if "SEASON" in df.columns and df["SEASON"].nunique() > 1:
        last = sorted(df["SEASON"].astype(str).unique())[-1]
        tr_m, te_m = (df["SEASON"].astype(str) != last).values, (df["SEASON"].astype(str) == last).values
        print(f"   temporal test: train on {int(tr_m.sum()):,} shots, evaluate on {last} ({int(te_m.sum()):,} shots)")
        hold = {}
        for name, make in (("logistic", _logistic), ("boosting", _boosting)):
            m = make().fit(df.loc[tr_m, FEATURES], y[tr_m])
            p = m.predict_proba(df.loc[te_m, FEATURES])[:, 1]
            hold[name] = {"log_loss": float(log_loss(y[te_m], p)), "brier": float(brier_score_loss(y[te_m], p)),
                          "auc": float(roc_auc_score(y[te_m], p)), "ece": expected_calibration_error(y[te_m], p)}
        hold["baseline_log_loss"] = float(log_loss(y[te_m], np.full(int(te_m.sum()), y[tr_m].mean())))
        hold["test_season"] = last
        hold["n_test"] = int(te_m.sum())
        metrics["temporal_holdout"] = hold
    best = min(("logistic", "boosting"), key=lambda n: metrics[n]["log_loss"])
    metrics["chosen"] = best
    metrics["n_shots"] = int(len(df))
    metrics["validation"] = f"GroupKFold({n_splits}) by game, out-of-sample"
    df["xShot"] = np.round(preds[best], 4)
    df["shot_residual"] = np.round(df["SHOT_MADE_FLAG"] - df["xShot"], 4)
    return df, metrics


KEEP = ["GAME_ID", "GAME_EVENT_ID", "GAME_DATE", "SEASON", "PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "TEAM_NAME",
        "PERIOD", "MINUTES_REMAINING", "SECONDS_REMAINING", "SHOT_ZONE_BASIC", "SHOT_TYPE", "SHOT_DISTANCE",
        "LOC_X", "LOC_Y", "SHOT_MADE_FLAG", "stint_minutes", "stint_minutes_quarter", "game_minutes_played",
        "stint_inferred", "score_margin", "is_home", "xShot", "shot_residual"]


def process_and_save_full_dataset(seasons=("2021", "2022", "2023", "2024"),
                                  output_file: str = "data/processed/shots_fatigue_processed.csv"):
    frames = []
    for sea in seasons:
        f = f"data/processed/by_season/stints_{sea}.csv"
        print(f"Reading {f}")
        frames.append(pd.read_csv(f, low_memory=False, dtype={"SEASON": str}))
    df = pd.concat(frames, ignore_index=True)
    print(f"   {len(df):,} shots in {len(seasons)} seasons")
    print("Validating the expected-shot model...")
    df_out, metrics = cross_fitted_xshot(df)
    with open(METRICS_FILE, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    for name in ("logistic", "boosting"):
        m = metrics[name]
        print(f"   [GroupKFold] {name:9s} log-loss {m['log_loss']:.4f} | Brier {m['brier']:.4f} | AUC {m['auc']:.3f} | ECE {m['ece']:.4f}")
    h = metrics.get("temporal_holdout")
    if h:
        for name in ("logistic", "boosting"):
            m = h[name]
            print(f"   [Temporal {h['test_season']}] {name:9s} log-loss {m['log_loss']:.4f} | AUC {m['auc']:.3f} | ECE {m['ece']:.4f}")
    print(f"   chosen: {metrics['chosen']}")
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    df_out[[c for c in KEEP if c in df_out.columns]].to_csv(output_file, index=False)
    print(f"Saved {output_file} ({len(df_out):,} shots)")
    return df_out


if __name__ == "__main__":
    # Usage: python src/xshot_model.py [season ...]   (default: 2021 2022 2023 2024)
    process_and_save_full_dataset(tuple(sys.argv[1:]) or ("2021", "2022", "2023", "2024"))
