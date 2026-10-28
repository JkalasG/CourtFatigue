[English](devpost_description.md) | [Español](es/devpost_descripcion.md)

# CourtFatigue - Devpost text

> Copy into the form fields. Replace `[DEMO URL]` and `[REPO URL]` when publishing.
> Written for non-technical judges: the language avoids advanced statistics.

## Title
CourtFatigue: when does an NBA player stop performing?

## Short description (tagline)
Using 872 thousand shots from 4 NBA seasons we measure whether shooting drops after many consecutive minutes on court, and find something different from what is expected: the issue is not when players leave, but how they enter.

## The problem
NBA rotations are largely decided by intuition: the coach "sees" a player tired and substitutes them. Substituting too early wastes the best players; substituting late costs points. There was no data-based guide saying how many consecutive minutes each player can keep performing, or how certain that is.

## What we did
Using 872,158 shots from the 2021-22 to 2024-25 regular seasons we rebuilt how many consecutive minutes each shooter had been on court at the moment of every shot, and discounted the difficulty of each shot (a forced shot is not fatigue's fault). Each player is compared with themselves, within their own season. To avoid confusing fatigue with "being cold", we compare players with many minutes against players who have already warmed up.

## What we found
- **Up to ~12 consecutive minutes there is no measurable drop in accuracy:** +0.2 percentage points, with a margin that rules out average drops larger than ~0.1. It repeats in each of the 4 seasons and holds under controls for blowouts, home or away, score and back-to-back games.
- **Cold start:** in the first 30 seconds after entering, players score ~1.5 percentage points below their norm; it normalises toward minute 2. It is negative in all 4 seasons (with a clear interval in 3) and under two different rules for counting minutes.
- **A popular rule does not work:** "substitute if accuracy drops 3 points" flags 60% of players with real data and 59% with minutes shuffled at random. That is noise, not fatigue.
- **No individual player shows a demonstrable drop** (0 of 592). With these data only drops of ~14 points would be detectable, so the tool does not label anyone as "the one who tires".
- **Schedule and defense:** a second game in a row lowers accuracy by ~0.4 points; playing at home raises it by ~0.4; and some teams defend consistently better than others (from −1.2 to +1.7 points between the best and the worst).

## Actionable impact
- **Coaches:** do not shorten stretches for "shooting fatigue" up to ~12 min; design the first play after a substitution for a rhythm shot (a hypothesis to test on video); manage key shooters in the second game of a back-to-back.
- **Conditioning staff and front office:** do not label a player as "gets tired" without evidence of their own; load must be measured with real physical data.
- **Analysts:** defensive ranking of the 30 teams with its margin of error, and the limit of what can be claimed about a player with public data.
- **Anyone:** the *New player* panel projects how someone with no history would perform and how much uncertainty there is, and updates with their real shots.

## Features
1. Plain-language summary ("In 30 seconds"), coaching-staff panel and glossary.
2. Explorer of 643 players: curve by consecutive minutes, rested vs. tired shot maps, verdict with its margin of error.
3. Evidence: data coverage, robustness, repetition by season, cold start, court zones, player traits and defensive ranking.
4. New-player projector with an uncertainty interval.
5. **3D simulator** where the scoring probability adds up measured terms: player accuracy, shot distance, **defender distance**, **rival team**, cold start and fatigue. The positions of the other defenders are illustrative and labelled as such.
6. English and Spanish interface.

## How we built it
Python (pandas, scikit-learn) for the analysis; interface in HTML, CSS and JavaScript with no libraries and custom SVG charts; Three.js for the simulator. Expected-shot model validated out of sample (by game) and with a **temporal test** (trained on 3 seasons and evaluated on the 4th, which it never saw). Statistics: player-season fixed effects, clustered errors, multiple-comparison correction, placebo test and tests on synthetic data. For defense we also use a 2014-15 shot log with defender distance (CC0).

## Rigor and limits (stated)
It is association, not causation: coaches substitute whoever they see as tired, which may hide real fatigue. Recent seasons do not include defender positions; in 2014-15 knowing them improves the expected-shot model (AUC 0.617 → 0.634), and that remains noise in our analysis. The defender-distance effect comes from that other era, and the rival effect is the team average. There are almost no shots after more than 12 consecutive minutes. "Not detected" does not mean "does not exist".

## Links
- Demo: [DEMO URL]
- Code: [REPO URL]
