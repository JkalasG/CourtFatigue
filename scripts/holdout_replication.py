"""
Preregistered replication of the cold start (and of the null fatigue result) on a season the
analysis never saw: NBA 2025-26. The plan is fixed in docs/preregistration.md, committed BEFORE
this script reads any 2025-26 data.

The 2025-26 play-by-play only exists in the "v3" format of the source repository. v3_to_v2()
maps it to the columns that src/stint_calculator.reconstruct_game_stints reads, so the stint
rule is the same code, unchanged. The adapter is validated on 2024-25, where both formats exist.

Usage:
  python scripts/holdout_replication.py validate   # adapter check on 2024-25 (data already analysed)
  python scripts/holdout_replication.py run        # 2025-26: refuses to run without the preregistration commit

Output (run): web/data/holdout_replication.json
"""

import json
import os
import re
import subprocess
import sys
import tarfile
import unicodedata
import urllib.request

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import fatigue_stats as fs  # noqa: E402
from src.stint_calculator import reconstruct_game_stints  # noqa: E402
from src.xshot_model import FEATURES, _boosting, add_features  # noqa: E402
from scripts.build_web_data import clean  # noqa: E402

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

BASE = "https://raw.githubusercontent.com/shufinskiy/nba_data/main/datasets/{name}.tar.xz"
PREREG = "docs/preregistration.md"
OUT = "web/data/holdout_replication.json"
TRAIN_SEASONS = ["2021", "2022", "2023", "2024"]
COLD = ("0–30 s", "30–60 s", "1–2 min")
FROZEN = {  # 2021-22 to 2024-25, as published (pp, 95% CI)
    "0–30 s": (-1.45954, -1.94513, -0.97394), "30–60 s": (-0.50006, -0.88417, -0.11594),
    "1–2 min": (-0.38637, -0.65457, -0.11818), "fatigue": (0.21, -0.13, 0.56),
}
N_BOOT = 2000

EVENT_TYPE = {"Made Shot": 1, "Missed Shot": 2, "Free Throw": 3, "Rebound": 4, "Turnover": 5, "Foul": 6,
              "Violation": 7, "Substitution": 8, "Timeout": 9, "Jump Ball": 10, "Ejection": 11,
              "Instant Replay": 18}
CLOCK = re.compile(r"PT(\d+)M([\d.]+)S")
SUB = re.compile(r"SUB:\s*(.+?)\s+FOR\s+(.+)$")


def fetch(name: str, out_dir: str) -> str:
    """Download <name>.tar.xz and extract its single CSV (untrusted: exact name, regular file)."""
    os.makedirs(out_dir, exist_ok=True)
    expected, csv = f"{name}.csv", os.path.join(out_dir, f"{name}.csv")
    if os.path.exists(csv):
        return csv
    archive = os.path.join(out_dir, f"{name}.tar.xz")
    print(f"  downloading {name}.tar.xz ...")
    urllib.request.urlretrieve(BASE.format(name=name), archive)
    with tarfile.open(archive, "r:xz") as tar:
        if tar.getnames() != [expected] or not tar.getmember(expected).isfile():
            raise SystemExit(f"Unexpected content in {archive}: {tar.getnames()}")
        with tar.extractfile(expected) as src, open(csv, "wb") as dst:
            dst.write(src.read())
    return csv


def _clock(s: str) -> str:
    m = CLOCK.match(str(s))
    return f"{int(m.group(1))}:{int(float(m.group(2))):02d}" if m else "0:00"


def _norm(name: str) -> str:
    """'Schröder' -> 'schroder'; 'Ja. Green' -> 'green' (namesakes are told apart later)."""
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode().lower().strip()
    return re.sub(r"^[a-z]{1,3}\.\s+", "", s)


def v3_to_v2(g: pd.DataFrame, stats: dict) -> pd.DataFrame:
    """One game of v3 play-by-play -> the v2 columns that reconstruct_game_stints reads."""
    g = g.sort_values("actionNumber", kind="stable")
    pid = g.personId.fillna(0).astype(int).values
    loc = g.location.fillna("")
    ptype = np.where(loc == "h", 4, np.where(loc == "v", 5, 0))
    # surname (as written in "SUB: X FOR Y") -> ids of that team's players in this game
    names = {}
    for tid, name, p in zip(g.teamId, g.playerName, pid):
        if p > 0 and isinstance(name, str):
            names.setdefault((tid, _norm(name)), set()).add(p)
    # first row index where each player shows up, to tell namesakes apart (e.g. LeBron and Bronny James)
    rows_of = {}
    for i, p in enumerate(pid):
        if p > 0:
            rows_of.setdefault(p, []).append(i)
    on = {}  # team -> ids seen entering
    p2 = np.full(len(g), np.nan)
    for i, (at, desc, tid, p) in enumerate(zip(g.actionType, g.description, g.teamId, pid)):
        if at != "Substitution":
            continue
        m = SUB.match(str(desc))
        cands = names.get((tid, _norm(m.group(1))), set()) - {p} if m else set()
        stats["subs"] += 1
        if not cands:
            stats["unresolved"] += 1
            continue
        if len(cands) > 1:
            stats["ambiguous"] += 1
            free = cands - on.get(tid, set())
            cands = free or cands
            # the one entering is the namesake who appears first after this substitution
            nxt = {c: next((j for j in rows_of.get(c, []) if j > i), len(g)) for c in cands}
            cands = {min(nxt, key=nxt.get)}
        p_in = min(cands)
        p2[i] = p_in
        team = on.setdefault(tid, set())
        team.discard(p)
        team.add(p_in)
    margin = (g.scoreHome - g.scoreAway) if {"scoreHome", "scoreAway"} <= set(g.columns) else pd.Series(np.nan, index=g.index)
    etype = [12 if a == "period" and s == "start" else 13 if a == "period" else EVENT_TYPE.get(str(a).strip(), 0)
             for a, s in zip(g.actionType, g.subType)]
    desc = g.description.fillna("")
    return pd.DataFrame({
        "GAME_ID": g.gameId.values, "EVENTNUM": g.actionNumber.values, "EVENTMSGTYPE": etype,
        "PERIOD": g.period.values, "PCTIMESTRING": [_clock(c) for c in g.clock],
        "SCOREMARGIN": [("TIE" if m == 0 else str(int(m))) if m == m else np.nan for m in margin],
        "PERSON1TYPE": ptype, "PLAYER1_ID": pid, "PLAYER1_TEAM_ID": g.teamId.values,
        "PERSON2TYPE": np.where(np.isnan(p2), 0, ptype), "PLAYER2_ID": p2, "PLAYER2_TEAM_ID": g.teamId.values,
        "PERSON3TYPE": 0, "PLAYER3_ID": np.nan, "PLAYER3_TEAM_ID": np.nan,
        "HOMEDESCRIPTION": np.where(loc == "h", desc, ""), "VISITORDESCRIPTION": np.where(loc == "v", desc, ""),
    })


def stints_from_v3(pbp_csv: str) -> tuple:
    pbp = pd.read_csv(pbp_csv, low_memory=False)
    stats = {"subs": 0, "unresolved": 0, "ambiguous": 0}
    rows = []
    for i, (_, g) in enumerate(pbp.groupby("gameId"), 1):
        rows.extend(reconstruct_game_stints(v3_to_v2(g, stats)))
        if i % 400 == 0:
            print(f"   {i} games")
    st = pd.DataFrame(rows, columns=["GAME_ID", "GAME_EVENT_ID", "PLAYER_ID", "stint_seconds", "stint_seconds_quarter",
                                     "game_seconds_played", "stint_inferred", "score_margin", "is_home"])
    return st.drop_duplicates(["GAME_ID", "GAME_EVENT_ID", "PLAYER_ID"]), stats


def validate():
    """Adapter check on 2024-25: the v3 stints must match the published (v2) ones."""
    csv = fetch("nbastatsv3_2024", "data/raw/seasons/2024v3")
    st, stats = stints_from_v3(csv)
    ref = pd.read_csv("data/processed/by_season/stints_2024.csv", low_memory=False,
                      usecols=["GAME_ID", "GAME_EVENT_ID", "PLAYER_ID", "stint_seconds", "stint_inferred"])
    m = ref.merge(st, on=["GAME_ID", "GAME_EVENT_ID", "PLAYER_ID"], how="left", suffixes=("_v2", "_v3"))
    found = m.stint_seconds_v3.notna()
    same = (m.stint_seconds_v2 - m.stint_seconds_v3).abs() <= 1
    out = {"shots_v2": int(len(ref)), "found_in_v3": float(found.mean()), "stint_match": float(same.mean()),
           "stint_match_reliable": float(same[~m.stint_inferred_v2.astype(bool)].mean()),
           "inferred_v2": float(m.stint_inferred_v2.astype(bool).mean()),
           "inferred_v3": float(m.stint_inferred_v3[found].astype(bool).mean()), **stats}
    print(json.dumps(out, indent=2))
    os.makedirs("data/processed/extra", exist_ok=True)
    with open("data/processed/extra/v3_adapter_check.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    return out


def prereg_commit() -> str:
    """Hash of the commit that added the preregistration; refuse to run without it."""
    try:
        h = subprocess.run(["git", "log", "--diff-filter=A", "--format=%H|%cI", "--", PREREG],
                           capture_output=True, text=True, check=True).stdout.strip().splitlines()
    except (OSError, subprocess.CalledProcessError):
        h = []
    if not h:
        raise SystemExit(f"{PREREG} is not committed yet: commit it before looking at 2025-26.")
    return h[-1]


def boot_ci(d: pd.DataFrame, lo: float, hi: float, rng) -> tuple:
    """Game-bootstrap 95% CI of the mean deviation in a window (secondary CI)."""
    w = d[(d.stint_minutes >= lo) & (d.stint_minutes < hi)]
    per = w.groupby("GAME_ID").dev.agg(["sum", "size"]).reindex(d.GAME_ID.unique()).fillna(0.0).values
    idx = rng.integers(0, len(per), size=(N_BOOT, len(per)))
    s = per[idx]
    est = s[..., 0].sum(axis=1) / s[..., 1].sum(axis=1) * 100
    return float(np.percentile(est, 2.5)), float(np.percentile(est, 97.5))


def verdict(est, lo, hi) -> str:
    if est < 0 and hi < 0:
        return "replicated"
    if est < 0:
        return "partially replicated"
    return "not replicated"


def run():
    commit = prereg_commit()
    print("Preregistration commit:", commit)
    rng = np.random.default_rng(0)
    pbp = fetch("nbastatsv3_2025", "data/raw/seasons/2025")
    shots_csv = fetch("shotdetail_2025", "data/raw/seasons/2025")
    print("[2025] stints from the v3 play-by-play...")
    st, stats = stints_from_v3(pbp)
    shots = pd.read_csv(shots_csv, low_memory=False)
    df = shots.merge(st, on=["GAME_ID", "GAME_EVENT_ID", "PLAYER_ID"], how="inner")
    df["SEASON"] = "2025"
    df["stint_minutes"] = df.stint_seconds / 60.0
    df["game_minutes_played"] = df.game_seconds_played / 60.0

    print("Frozen expected-shot model (same specification, trained on 2021-22 to 2024-25 only)...")
    train = pd.concat([pd.read_csv(f"data/processed/by_season/stints_{s}.csv", low_memory=False) for s in TRAIN_SEASONS])
    train = add_features(train)
    train = train[train[FEATURES + ["SHOT_MADE_FLAG"]].notna().all(axis=1)]
    model = _boosting().fit(train[FEATURES], train.SHOT_MADE_FLAG.values)
    df = add_features(df)
    df = df[df[FEATURES + ["SHOT_MADE_FLAG"]].notna().all(axis=1)].copy()
    df["xShot"] = model.predict_proba(df[FEATURES])[:, 1]
    df["shot_residual"] = df.SHOT_MADE_FLAG - df.xShot
    n_all = len(df)
    df = df[~df.stint_inferred.astype(bool)].copy()

    cold = {r["label"]: r for r in fs.cold_start_table(df)}
    d = fs.add_dev(df)
    contr = fs.contrast_by_player(df, fs.SHORT_DEFAULT, fs.LONG_DEFAULT, short_lo=fs.SHORT_LO_DEFAULT)
    het = fs.heterogeneity(contr.effect, contr.se)
    rows = {}
    for (lo, hi), lab in zip(((0, 0.5), (0.5, 1), (1, 2)), COLD):
        r = cold[lab]
        rows[lab] = {"frozen": FROZEN[lab][0], "frozen_ci95": FROZEN[lab][1:], "new": r["effect_pp"],
                     "ci95": [r["lo_pp"], r["hi_pp"]], "ci95_game_bootstrap": list(boot_ci(d, lo, hi, rng)), "n": r["n"]}
    fat = {"frozen": FROZEN["fatigue"][0], "frozen_ci95": FROZEN["fatigue"][1:], "new": het["mu"] * 100,
           "ci95": [het["mu_lo"] * 100, het["mu_hi"] * 100], "players": int(het["k"])}
    p = rows["0–30 s"]
    out = {
        "preregistration_commit": commit.split("|")[0], "preregistration_date": commit.split("|")[1],
        "seasons_tested": ["2025-26"], "games": int(df.GAME_ID.nunique()), "shots": int(n_all),
        "shots_analysis": int(len(df)), "inferred_share": float(1 - len(df) / n_all), "adapter": stats,
        "cold_start": rows, "fatigue_8plus_vs_2_6": fat,
        "verdict": verdict(p["new"], *p["ci95"]),
        "fatigue_near_zero": bool(fat["ci95"][0] < 0.56 and fat["ci95"][1] > -0.13 and abs(fat["new"]) < 1.0),
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(clean(out), f, ensure_ascii=False, indent=1)
    print(json.dumps(clean(out), ensure_ascii=False, indent=1))
    print("->", OUT)


if __name__ == "__main__":
    {"validate": validate, "run": run}.get((sys.argv[1:] or [""])[0], lambda: sys.exit(__doc__))()
