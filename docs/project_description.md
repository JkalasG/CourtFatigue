[English](project_description.md) | [Español](es/descripcion_proyecto.md)

# CourtFatigue: when does a player stop performing, and where does the court notice?

Updated 28 Oct 2026

## Summary

CourtFatigue is an analysis tool that measures whether an NBA player's shooting performance drops with the consecutive minutes they have been on court, in which zones, and how certainly anything can be said about a specific player or a new one. It includes a 3D simulator where every term of the scoring probability comes from measured data. Its goal is to give coaches an honest reference for substitution decisions: what the data say, what they do not, and what is worth testing.

## The problem

Rotations in professional basketball are largely decided by intuition: the coach "sees" a player tired and substitutes them. There is no clear data-based guide to how many consecutive minutes each player can sustain before dropping off, or which kinds of shots deteriorate first.

Substituting too early wastes the best players. Substituting late costs points at key moments.

## The solution

CourtFatigue rebuilds how many consecutive minutes each player has been on court at the moment of each shot, and measures how their accuracy changes relative to what shot difficulty predicts. It is presented in views designed for people with no technical background:

1. **Plain-language summary** ("In 30 seconds"), a panel for the coaching staff and a glossary.
2. **Player explorer:** curve by consecutive minutes with a confidence interval, and rested vs. tired shot maps.
3. **Evidence:** data coverage, robustness of the result, repetition season by season, cold start, court zones, player traits and a defensive ranking of the 30 teams.
4. **New player:** projection for someone with no history, with its uncertainty, updated with their real shots.
5. **3D simulator:** consecutive minutes, rival team and defender distance.
6. **English and Spanish** interface.

The tool **only recommends substituting a player if there is statistically solid evidence of a drop in them**; otherwise it says so and shows how much margin there is.

## Data

- **NBA regular seasons 2021-22 to 2024-25** (NBA Stats API through the public `shufinskiy/nba_data` repository): 4 x 1,230 games, 872,158 shots with coordinates (`ShotChartDetail`) and the play-by-play with substitutions and score (`PlayByPlayV2`). 913 players; 592 with enough shots in the compared buckets.
- **2014-15 shot log** (Kaggle "NBA shot logs", OpenML mirror, CC0 license): 128,069 shots with nearest-defender distance. Used for the simulator and to measure the limitation of having no defender data in recent seasons. It is not merged with the others.

Details and links: [DATASETS.md](../DATASETS.md). Data quality: [DATA_QUALITY.md](../DATA_QUALITY.md).

## Methodology

1. **Stint reconstruction:** counts game-clock time only; the counter continues across Q1→Q2 and Q3→Q4 and resets at halftime (sensitivity check: reset every quarter). The play-by-play does not record substitutions between quarters, so in each quarter we detect who was already on court. ~0.3% of shots have an uncertain stint and are excluded.
2. **Expected shot:** gradient boosting on distance, coordinates, zone, shot type, period and time remaining, without minutes on court or player identity. Validated with game-grouped cross-validation (AUC 0.657, calibration 0.17 pp) and a **temporal test**: trained on 2021-22 to 2023-24 and evaluated on 2024-25, which it never saw (log-loss 0.6407 vs. 0.6910 without a model, AUC 0.654, calibration 0.50 pp).
3. **Fatigue effect:** each player is compared with their own level **in that season**. We contrast ≥ 8 consecutive min against 2-6 min (already warmed up, so the cold start is not mixed with fatigue) and estimate the per-minute slope with fixed effects and player-clustered errors. A random-effects model separates real differences between players from noise.
4. **False-positive control:** Benjamini-Hochberg correction and a placebo test (minutes shuffled within each player).
5. **Cold start, schedule and context:** performance by time since entering, by quarter and by first entry vs. re-entry; controls for back-to-back, home and score.
6. **Defense:** effect of each rival team (shrunk toward the league) and effect of defender distance (monotone, with a game-resampling band).
7. **Uncertainty:** all results are shown with confidence intervals, and buckets with little data are flagged as unreliable.

## Findings

- **Average fatigue effect: not detectable.** With ≥ 8 consecutive min, difficulty-adjusted accuracy changes **+0.21 pp** (95% CI: −0.13 to +0.56) versus warmed-up players; average drops larger than ~0.13 pp are ruled out. The slope after warm-up is +0.027 pp/min (CI −0.014 to +0.069). The result repeats in every season and holds under the controls (blowouts, home, score, back-to-back, per-quarter reset).
- **Zones:** no zone shows a significant drop after warm-up. The two interior zones show a slight improvement (+0.11 and +0.16 pp/min).
- **Differences between players:** none demonstrable. 0 of 592 players show a drop with a 95% CI below zero and false discoveries < 5%. Individual power is limited: only drops of ~14 pp or more would be detected.
- **Cold start:** in the first 30 s after entering the player scores **−1.46 pp** below their norm (CI −1.95 to −0.97), −0.50 pp between 30 and 60 s and −0.39 pp between 1 and 2 min; from 2 min it is normal. It is negative in all 4 seasons (clear interval in 3; in 2022 the interval includes 0) and repeats under another stint rule (−1.08 pp).
- **Schedule and context:** back-to-back −0.39 pp (CI −0.67 to −0.11); playing at home +0.38 pp.
- **Defense:** each team's defensive effect is real and stable across seasons (r ≈ 0.52), from −1.2 pp (Thunder) to +1.7 pp (Kings) in 2024-25. In 2014-15, knowing the defender distance raises the expected-shot AUC from 0.617 to 0.634.
- **The naive rule does not work:** "substitute if accuracy drops 3 pp in any bucket with ≥ 20 shots" flags 60.5% of players with real data and 59.4% with minutes shuffled at random; it is noise.

As the premise anticipated, no large fatigue effect appeared, and that is a valid finding: current rotations are probably already fairly efficient. The actionable part is elsewhere: how players enter.

## Practical impact

| Profile | How they use it |
| --- | --- |
| Coaches | Do not shorten stretches for "shooting fatigue" up to ~12 consecutive min; design the first play after a substitution for a rhythm shot (a hypothesis to test); manage key shooters in the second game of a back-to-back. |
| Conditioning staff | Know that, with these data, no player shows a demonstrable drop by consecutive minutes; load must be measured with real physical data. |
| Analysts and front office | Defensive ranking by team with its margin of error; the "−3 pp" rule discarded with evidence; the limit of what can be claimed about a player from one season. |
| Fans and media | See clearly what is signal and what is noise in performance. |

## Limitations

The analysis measures association and does not prove causation. They are stated explicitly:

- Coaches already substitute when they perceive fatigue, so long stints are biased toward players who are doing well and are rare beyond ~12 min. This may hide real fatigue.
- No defender data in recent seasons: the expected-shot model leaves that part as noise, and we cannot check whether it biases the comparison between minutes.
- No individual physical-condition data.
- Limited power per player. "Not detected" does not mean "does not exist".
- The defender-distance effect comes from another era (2014-15) and is association; the rival effect is the team average, not a specific defender.
- The thresholds (2-6 min as reference, 8 min as "long") are a choice; the continuous slope is reported as an alternative.

## Technologies

Python (`pandas`, `numpy`, `scikit-learn`) for the analysis; interface in HTML, CSS and JavaScript with no libraries (custom SVG charts), publishable on GitHub Pages; Three.js for the 3D simulator; GitHub for open source code. Tests on synthetic data for the statistics and for the simulator model.

## Future work

- Tracking data (defender positions) in recent seasons.
- Include accumulated fatigue from travel and real load.
- Extend the analysis to the WNBA or EuroLeague.
- Also measure the defensive impact of fatigue, not just shooting.

## Short version for Devpost

CourtFatigue measures, with 872 thousand shots from 4 NBA seasons, whether shooting drops after many consecutive minutes on court. It finds no measurable drop up to ~12 minutes, debunks a popular rule ("substitute if accuracy drops 3 points", which flags the same with random data) and detects something different: a cold start of ~1.5 percentage points in the first 30 seconds after entering. It includes a 3D simulator where every term of the scoring probability comes from data, with the rival and the defender distance, and is explicit about what cannot be claimed about an individual player.
