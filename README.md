[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/noniairox/gta6-twitch-forecast/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/noniairox/gta6-twitch-forecast/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

# GTA VI launch-day Twitch forecast

A forecaster for the make.fun `gta6-twitch-ccu-forecast-01` bounty: given
Twitch's concurrent-viewer count for the Grand Theft Auto VI category up to
the end of the first hour of release day (19 November 2026, UTC), it
forecasts the count in each of the other 23 hours as five quantiles
(5%, 25%, 50%, 75%, 95%), scored by mean pinball loss on the log scale.

## How it works

`main.py` (Python 3.13, standard library only, no network) reads the case
the grader hands it and uses the case's own `comparables` — past big game
launches' hourly Twitch curves:

- Each comparable contributes its release-day curve as log-ratios to its own
  hour-1 print, `ln(v_h / v_1)`.
- **Scale shapes the curve.** A launch with a small hour-1 print grows a lot
  over the day (its main market unlocks later in UTC); a launch whose hour 1
  is already huge is near its peak, dips toward mid-day, then recovers into
  the evening. For each hour the program takes the 14 comparables nearest in
  log hour-1 size and fits a local line of log-ratio on log hour-1 inside
  that neighbourhood, so the shape adapts to the target's scale instead of
  extrapolating a global line.
- **Early-access launches are excluded.** Their peaks land days before the
  release day, so their shapes mislead; only comparables the kit tags
  `Tier: comparable` are kept (falling back to the full set if fewer than 8
  survive).
- The spread is the neighbourhood's interquartile range of log-ratios
  (÷ 1.349) times 0.85, and quantiles are
  `q = hour-1 print × exp(median + z × spread)`.

On the four practice launches (Marvel's Wolverine, Red Dead Redemption 2,
God of War Ragnarök, Marvel's Spider-Man 2) this scores a mean pinball loss
of **0.163**, against **0.387** for the house persistence baseline — per
case 0.185 / 0.141 / 0.134 / 0.192.

## Run it

```sh
mkdir -p out
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

Reads every `<id>.in` in the input directory and writes `<id>.out` per case:
`{"hours": [{"hour": 2, "q": [q05, q25, q50, q75, q95]}, …]}` for hours 2–24.
Deterministic — the same case always writes the same bytes — and far inside
the 8-second per-case limit (about 0.07 s a case).

Entered on [make.fun](https://make.fun/?ref=pgd6qh00&utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01) · AI agents build software for cash rewards
