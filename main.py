"""Forecast GTA VI's launch-day Twitch viewers hour by hour.

make.fun bounty gta6-twitch-ccu-forecast-01: the program reads one case
(/input/<id>.in, schema "makefun/twitch-ccu-case/v1") and writes
/output/<id>.out: for each of hours 2 to 24 of the release day (UTC), five
quantiles (5%, 25%, 50%, 75%, 95%) of that hour's concurrent Twitch viewers
in the Grand Theft Auto VI category. Score is the mean pinball loss on the
log scale; the house persistence baseline scores about 0.387 on the practice.

Method (tuned on the four practice launches, whose answers were reconstructed
from the same public SullyGnome source the kit cites; practice mean pinball
about 0.163 against the baseline's 0.387):

  The case ships `comparables`: past big game launches' hourly Twitch curves
  from 14 days before to 3 days after their release day. For each comparable
  I take its release-day curve as log-ratios to its own hour-1 print,
  ln(v_h / v_1). Two facts drive the forecast:

  1. Scale shapes the curve. A launch whose hour-1 print is small grows a
     lot over the day (its main market unlocks later in UTC); a launch whose
     hour-1 is already huge is near its peak and decays toward mid-day, then
     recovers into the evening. Across the comparables the correlation of
     ln(hour-1) with the log-ratio reaches about -0.9 by hour 20. So for each
     hour I take the k = 14 comparables nearest in log hour-1 size, and fit a
     local line of log-ratio on log hour-1 inside that neighbourhood: the
     median log-ratio shifted by the slope times the target's distance from
     the neighbourhood's mean log size. This adapts the shape to the target's
     scale instead of extrapolating a global line far outside the data.
  2. Early-access launches distort the shape (their peak lands days before
     the release day, or their hour 1 is already inflated), so I keep only
     comparables the kit tags "Tier: comparable" in their unlock note, and
     fall back to the full set only if fewer than 8 survive. The GTA VI
     category's own pre-release history is not a launch and has no release-day
     curve, so it never enters the library.

  The spread is the neighbourhood's interquartile range of log-ratios
  (divided by 1.349, the normal IQR-to-sigma factor), times 0.85: slightly
  narrower than the raw IQR, which scored best on the practice, while still
  honest about how far an unprecedented launch can sit from its neighbours.
  Quantiles are q_tau = p1 * exp(median + z_tau * sigma), p1 the case's
  hour-1 print, z the standard normal quantiles.

  Fallbacks keep every case valid: if the library is too small the program
  falls back to the house persistence shape (flat median, spread widening
  like 0.15 * sqrt(h - 1) in log space).

Runs on Python 3.13 standard library only, no network, deterministic: the
same case always writes the same bytes.
"""

import json
import math
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# The grader's -P leaves /bot off sys.path: put it back first, so a module
# shipped beside this file imports. (This entry is a single file.)
sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.645, -0.674, 0, 0.674, 1.645]
K_NEIGHBOURS = 14
SPREAD_MULT = 0.85
MIN_LIBRARY = 8
BASE_SIGMA = 0.15
SPREAD_FLOOR = 0.05
TIER_RE = re.compile(r"Tier:\s*([a-z\-]+)")


def round2(x: float) -> float | int:
    """x rounded to 2 decimals, half up, as JavaScript's Math.round(x*100)/100."""
    scaled = x * 100
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100
    return int(value) if value.is_integer() else value


def parse_time(text: str) -> float:
    """ISO 8601 UTC timestamp to epoch seconds."""
    return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()


def tier_of(comp: dict) -> str:
    """The kit's tier tag in the comparable's unlock note, or 'comparable'."""
    match = TIER_RE.search(comp.get("unlock") or "")
    return match.group(1) if match else "comparable"


def release_day_curve(comp: dict) -> dict:
    """Hour -> viewers for the comparable's release day (hours 1..24, UTC)."""
    start = parse_time(comp["day_start"])
    curve = {}
    for point in comp.get("hourly") or []:
        offset = (parse_time(point["from"]) - start) / 3600
        if 0 <= offset < 24:
            curve[int(offset) + 1] = point["viewers"]
    return curve


def build_library(case: dict) -> list:
    """Comparable launches as (log hour-1 viewers, {hour: log-ratio}) pairs.

    Only launches with a complete 24-hour release-day curve and a positive
    hour-1 print, tagged Tier: comparable; the full set is the fallback.
    """
    full = []
    for comp in case.get("comparables") or []:
        curve = release_day_curve(comp)
        if len(curve) < 24 or curve.get(1, 0) <= 0:
            continue
        p1 = curve[1]
        ratios = {
            h: math.log(max(curve[h], 1) / p1) for h in range(2, 25)
        }
        full.append((tier_of(comp), math.log(p1), ratios))
    clean = [entry for entry in full if entry[0] == "comparable"]
    chosen = clean if len(clean) >= MIN_LIBRARY else full
    return [(ln_p1, ratios) for _, ln_p1, ratios in chosen]


def median(values: list) -> float:
    ordered = sorted(values)
    return ordered[len(ordered) // 2]


def iqr_sigma(values: list) -> float:
    ordered = sorted(values)
    n = len(ordered)
    return (ordered[(3 * n) // 4] - ordered[n // 4]) / 1.349


def ols_slope(xs: list, ys: list) -> float:
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    var_x = sum((x - mean_x) ** 2 for x in xs)
    if var_x == 0:
        return 0.0
    return sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / var_x


def hour_quantiles(library: list, p1: float, hour: int) -> list:
    """Five quantiles of hour `hour`'s viewers, from the neighbour library."""
    if len(library) < 3:
        # Too little to learn from: the house persistence shape.
        return [
            round2(p1 * math.exp(z * BASE_SIGMA * math.sqrt(hour - 1)))
            for z in Z
        ]
    target = math.log(p1)
    # Nearest neighbours in log hour-1 size; name-independent order is
    # guaranteed by sorting on (distance, log size) only.
    neighbours = sorted(
        library, key=lambda entry: (abs(entry[0] - target), entry[0])
    )[:K_NEIGHBOURS]
    log_sizes = [entry[0] for entry in neighbours]
    ratios = [entry[1][hour] for entry in neighbours]
    centre = median(ratios)
    centre += ols_slope(log_sizes, ratios) * (target - sum(log_sizes) / len(log_sizes))
    sigma = max(iqr_sigma(ratios) * SPREAD_MULT, SPREAD_FLOOR)
    return [round2(p1 * math.exp(centre + z * sigma)) for z in Z]


def forecast_case(case: dict, name: str) -> dict:
    if case["levels"] != LEVELS:
        raise ValueError(f"{name} asks for levels {case['levels']}, not {LEVELS}")
    first = next((k for k in case["known"] if k["hour"] == 1), None)
    if first is None:
        raise ValueError(f"{name} has no hour-1 print")
    p1 = max(1, first["viewers"])
    library = build_library(case)
    hours = [
        {"hour": row["hour"], "q": hour_quantiles(library, p1, row["hour"])}
        for row in case["forecast"]
    ]
    return {"hours": hours}


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # Every case file, in name order, so two runs write the same bytes.
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case, path.name)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
