# Preregistration: replication of the cold start on NBA 2025-26

Written and committed on 29 Oct 2026, **before** any 2025-26 data was downloaded or read. The date and the hash of the commit that adds this file are the proof. The analysis code is committed with it: `scripts/holdout_replication.py`.

## Question

Does the cold start found in 2021-22 to 2024-25 (players shoot worse in their first seconds after entering the court) appear again in a season the analysis never saw? And does the absence of shooting fatigue hold?

## Data

- **Test season:** NBA 2025-26 regular season, from the same public source as the rest of the project (shufinskiy/nba_data): `shotdetail_2025` (shots) and `nbastatsv3_2025` (play-by-play).
- 2026-27 is not available in the source, so it is not tested.
- The 2025-26 play-by-play only exists in the "v3" format. `v3_to_v2()` maps it to the fields the stint calculator reads. It was validated on 2024-25, where both formats exist: the stint matches the published one in **99.66%** of 219,526 shots, and the share of uncertain stints is the same (0.36% vs. 0.35%).

## Frozen elements (not changed after seeing the data)

- **Stint rule:** `src/stint_calculator.reconstruct_game_stints`, unchanged. Shots with an uncertain stint are excluded, as in the main analysis.
- **Expected-shot model:** the same specification (`src/xshot_model._boosting`, same features, `random_state=42`), trained **only** on 2021-22 to 2024-25 and applied to 2025-26. It is not retrained with 2025-26 data.
- **Estimators:** the same functions as the published analysis: `fatigue_stats.cold_start_table` (deviation from each player-season's average, player-clustered 95% CI) and `contrast_by_player` + `heterogeneity` (≥ 8 min vs. 2-6 min).
- **Thresholds:** 0-30 s, 30-60 s, 1-2 min; 2-6 min as the warmed-up reference, 8 min as "long".

## Estimates being tested (2021-22 to 2024-25)

| Window | Published estimate | 95% CI |
| --- | --- | --- |
| Cold start 0-30 s | −1.46 pp | −1.95 to −0.97 |
| Cold start 30-60 s | −0.50 pp | −0.88 to −0.12 |
| Cold start 1-2 min | −0.39 pp | −0.65 to −0.12 |
| Fatigue: ≥ 8 min vs. 2-6 min | +0.21 pp | −0.13 to +0.56 |

## Success rule (primary test: cold start 0-30 s in 2025-26, player-clustered 95% CI)

- **Replicated:** the estimate is negative and its 95% CI excludes 0.
- **Partially replicated:** negative, but the CI includes 0.
- **Not replicated:** zero or positive.

A game-bootstrap CI is also reported as a secondary check; it does not change the verdict.

## Secondary test

The fatigue contrast (≥ 8 min vs. 2-6 min) stays close to 0: its 95% CI overlaps the published one (−0.13 to +0.56) and the estimate is within ±1 pp.

## Commitments

- The result is published whatever it is, in the *Evidence* tab and in the README, with this commit's hash.
- No threshold, model or exclusion is changed after seeing the 2025-26 data. Any deviation would be reported as such, next to the preregistered result.
