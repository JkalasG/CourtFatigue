"""
CourtFatigue - stint calculator (consecutive minutes on court).

Rebuilds who is on the court at every moment from the play-by-play substitutions
(nbastats) and attaches to each shot (shotdetail) how many consecutive minutes the
shooter had been playing.

Rules (stated explicitly because they change the results):
  * The counter counts game-clock time only (breaks do not add).
  * stint_minutes (main rule): keeps running across Q1->Q2 and Q3->Q4 (2-min breaks)
    and RESETS at halftime (before Q3).
  * stint_minutes_quarter (sensitivity analysis): resets every quarter.
  * The play-by-play does NOT record substitutions made between quarters. In each
    quarter, anyone who appears active before entering as a substitute counts as
    already on court. If they were also on court at the end of the previous quarter
    they keep their counter; otherwise it starts at the beginning of the quarter.
  * A shooter missing from the reconstructed lineup (e.g. a starter with no earlier
    events) is assumed to have entered at the start of the quarter, and the shot is
    flagged stint_inferred = True so it can be excluded.
"""

import sys
import os
import pandas as pd
import numpy as np

# UTF-8 console output
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

HALFTIME_PERIOD = 3  # the counter resets when this period starts
BUCKETS = [
    ("0-2 min (Start)", 0.0, 2.0),
    ("2-5 min (Optimal rhythm)", 2.0, 5.0),
    ("5-8 min (Medium load)", 5.0, 8.0),
    ("8-10 min (Critical zone)", 8.0, 10.0),
    ("10-12 min (Long)", 10.0, 12.0),
    ("12+ min (Very long)", 12.0, 99.0),
]


def period_start(period: int) -> int:
    """Game seconds elapsed when the period starts (breaks excluded)."""
    return (period - 1) * 720 if period <= 4 else 4 * 720 + (period - 5) * 300


def period_length(period: int) -> int:
    return 720 if period <= 4 else 300


def parse_clock_to_seconds(clock_str: str) -> int:
    """Convert 'MM:SS' to seconds remaining in the period ('11:43' -> 703)."""
    try:
        parts = str(clock_str).strip().split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except Exception:
        return 0


def _valid_player(pid, ptype) -> bool:
    return ptype in (4, 5) and pid == pid and pid > 0  # pid == pid rejects NaN


def reconstruct_game_stints(pbp_game: pd.DataFrame) -> list:
    """
    Walk one game and return, for each shot (EVENTMSGTYPE 1 and 2), a tuple
    (GAME_ID, EVENTNUM, PLAYER_ID, stint_sec, stint_sec_quarter, seconds_played, inferred,
    shooter_margin, is_home). The margin is the score BEFORE the shot.
    """
    rows = []
    on = {}    # team_id -> {player_id: [game_entry, stint_entry, inferred]}
    acc = {}   # player_id -> game seconds accumulated in closed stints
    margin = 0  # home - away score before the current event

    for period, p in pbp_game.groupby("PERIOD", sort=True):
        p = p.sort_values("EVENTNUM", kind="stable")
        ps = period_start(period)
        plen = period_length(period)

        if period == HALFTIME_PERIOD:
            for team in on.values():
                for v in team.values():
                    v[1] = ps  # halftime: reset the consecutive-minutes counter

        # Players already on court the first time they appear
        # (their first appearance is not entering as a substitute).
        first = {}
        for r in p.itertuples(index=False):
            for k, (pid, ptype, tid) in enumerate((
                (r.PLAYER1_ID, r.PERSON1TYPE, r.PLAYER1_TEAM_ID),
                (r.PLAYER2_ID, r.PERSON2TYPE, r.PLAYER2_TEAM_ID),
                (r.PLAYER3_ID, r.PERSON3TYPE, r.PLAYER3_TEAM_ID),
            ), 1):
                if _valid_player(pid, ptype) and pid not in first:
                    first[pid] = (tid, r.EVENTMSGTYPE == 8 and k == 2)
        for pid, (tid, entered_as_sub) in first.items():
            team = on.setdefault(tid, {})
            if not entered_as_sub and pid not in team:
                # Not on court in the previous quarter: Q1 starter, or entered during the
                # break (the play-by-play does not record between-quarter substitutions).
                team[pid] = [ps, ps, False]

        for r in p.itertuples(index=False):
            t = ps + (plen - parse_clock_to_seconds(r.PCTIMESTRING))
            margin_before = margin
            sm = r.SCOREMARGIN
            if sm == sm and sm != "":  # not NaN: the event changes the score
                try:
                    margin = 0 if str(sm) == "TIE" else int(float(sm))
                except ValueError:
                    pass

            if r.EVENTMSGTYPE == 8:  # substitution: PLAYER1 leaves, PLAYER2 enters
                team = on.setdefault(r.PLAYER1_TEAM_ID, {})
                v = team.pop(r.PLAYER1_ID, None)
                if v is not None:
                    acc[r.PLAYER1_ID] = acc.get(r.PLAYER1_ID, 0) + max(0, t - v[0])
                if r.PLAYER2_ID == r.PLAYER2_ID and r.PLAYER2_ID > 0:
                    team[r.PLAYER2_ID] = [t, t, False]

            elif r.EVENTMSGTYPE in (1, 2):  # made / missed shot
                pid = r.PLAYER1_ID
                if not _valid_player(pid, r.PERSON1TYPE):
                    continue
                team = on.setdefault(r.PLAYER1_TEAM_ID, {})
                v = team.get(pid)
                if v is None:
                    v = [ps, ps, True]
                    team[pid] = v
                home = r.PERSON1TYPE == 4
                rows.append((
                    r.GAME_ID, r.EVENTNUM, int(pid),
                    max(0, t - v[1]),
                    max(0, t - max(v[0], ps)),
                    acc.get(pid, 0) + max(0, t - v[0]),
                    bool(v[2]),
                    margin_before if home else -margin_before,  # shooter team's margin
                    home,
                ))
    return rows


def assign_bucket(stint_minutes: float) -> str:
    for label, lo, hi in BUCKETS:
        if lo <= stint_minutes < hi:
            return label
    return BUCKETS[-1][0]


def season_paths(season: str):
    """Paths of the raw CSVs. Season '2024' is 2024-25 (convention of the source repository)."""
    if season == "2024":
        return "data/raw/nbastats_2024.csv", "data/raw/shotdetail_2024.csv"
    return f"data/raw/seasons/{season}/nbastats_{season}.csv", f"data/raw/seasons/{season}/shotdetail_{season}.csv"


def process_all_stints(season: str = "2024", sample_size: int = None, output_file: str = None) -> pd.DataFrame:
    """
    Rebuild the stints of one season (or a sample of games) and save the result to
    data/processed/by_season/stints_<season>.csv.
    """
    pbp_path, shots_path = season_paths(season)
    output_file = output_file or f"data/processed/by_season/stints_{season}.csv"
    print(f"[{season}] Reading shots and play-by-play...")
    df_shots = pd.read_csv(shots_path, low_memory=False)
    df_pbp = pd.read_csv(pbp_path, low_memory=False)

    unique_games = df_shots["GAME_ID"].unique()
    total_games = len(unique_games)
    if sample_size and sample_size < total_games:
        print(f"Sample mode: {sample_size} of {total_games} games...")
        unique_games = unique_games[:sample_size]
    else:
        print(f"[{season}] Processing {total_games} games...")

    pbp_grouped = {gid: g for gid, g in df_pbp.groupby("GAME_ID")}

    all_rows = []
    for idx, gid in enumerate(unique_games, 1):
        if gid in pbp_grouped:
            all_rows.extend(reconstruct_game_stints(pbp_grouped[gid]))
        if idx % 400 == 0 or idx == len(unique_games):
            print(f"   [{season}] {idx}/{len(unique_games)} games")

    stints = pd.DataFrame(all_rows, columns=[
        "GAME_ID", "GAME_EVENT_ID", "PLAYER_ID",
        "stint_seconds", "stint_seconds_quarter", "game_seconds_played", "stint_inferred",
        "score_margin", "is_home",
    ])
    stints = stints.drop_duplicates(["GAME_ID", "GAME_EVENT_ID", "PLAYER_ID"])
    final_df = df_shots[df_shots["GAME_ID"].isin(unique_games)].merge(
        stints, on=["GAME_ID", "GAME_EVENT_ID", "PLAYER_ID"], how="inner")
    final_df["SEASON"] = season
    final_df["stint_minutes"] = (final_df["stint_seconds"] / 60.0).round(2)
    final_df["stint_minutes_quarter"] = (final_df["stint_seconds_quarter"] / 60.0).round(2)
    final_df["game_minutes_played"] = (final_df["game_seconds_played"] / 60.0).round(2)
    final_df["fatigue_bucket"] = final_df["stint_minutes"].map(assign_bucket)

    dropped = len(df_shots[df_shots["GAME_ID"].isin(unique_games)]) - len(final_df)
    print(f"   [{season}] shots without stint: {dropped} | inferred stint: {final_df['stint_inferred'].mean() * 100:.2f}%")

    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    final_df.to_csv(output_file, index=False)
    print(f"[{season}] {len(final_df):,} shots -> {output_file}")
    return final_df


if __name__ == "__main__":
    # Usage: python src/stint_calculator.py [season ...]   (default 2024; e.g. 2021 2022 2023 2024)
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    for season in (args or ["2024"]):
        process_all_stints(season, sample_size=50 if "--sample" in sys.argv else None)
