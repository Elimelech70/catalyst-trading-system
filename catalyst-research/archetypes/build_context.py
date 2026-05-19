"""
Name of Application : Catalyst Trading System
Name of file        : catalyst-research/archetypes/build_context.py
Version             : 0.1.0
Last Updated        : 2026-05-18
Purpose             : Builds the data context bundle that the wrapper appends
                      to the archetype's system prompt at run time. The
                      output is a Markdown-formatted summary of:
                        - The observation window (period_start..period_end)
                        - Active learning plans
                        - Recent country-indicator readings
                        - Recent market-price moves
                        - Recent news event headlines
                        - Prior analyses (for continuity)

                      Designed to be concise: archetypes are charged tokens
                      per run, and a tight context bundle keeps cost
                      predictable. Hard cap ~6000 tokens worth of text.

CLI                 : python -m archetypes.build_context \
                          --archetype historian \
                          --scope weekly \
                          [--period-end 2026-05-17]
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from textwrap import shorten

from archetypes import db


# Scope → observation window
SCOPE_WINDOWS = {
    "weekly":               dt.timedelta(days=7),
    "monthly":              dt.timedelta(days=30),
    "quarterly":            dt.timedelta(days=92),
    "learning_plan_review": dt.timedelta(days=90),
    "ad_hoc":               dt.timedelta(days=14),
}

MAX_INDICATORS  = 40
MAX_PRICES      = 30
MAX_NEWS        = 25
MAX_PRIOR       = 6


def build(archetype: str, scope: str,
          period_end: dt.date | None = None) -> str:
    if scope not in SCOPE_WINDOWS:
        raise ValueError(f"unknown scope: {scope!r}")
    if period_end is None:
        period_end = dt.date.today()
    period_start = period_end - SCOPE_WINDOWS[scope]

    lines: list[str] = []
    lines.append(f"# Observation window — {scope}")
    lines.append(f"From {period_start} to {period_end}")
    lines.append("")

    with db.connect() as conn:
        plans = db.active_learning_plans(conn)
        indicators = db.recent_country_indicators(
            conn, period_start=period_start, period_end=period_end)
        prices = db.recent_market_prices(
            conn, period_start=period_start, period_end=period_end)
        news = db.recent_news(
            conn, period_start=period_start, period_end=period_end, limit=MAX_NEWS)
        priors = db.prior_archetype_analyses(
            conn, since=period_start - dt.timedelta(days=30), limit=MAX_PRIOR)

    lines.append("## Active learning plans")
    if not plans:
        lines.append("_(none active)_")
    for p in plans:
        lines.append(f"- **{p['name']}** ({p['status']}): {shorten(p['question'], width=180)}")
    lines.append("")

    lines.append(f"## Country indicators (recent, latest revision per row, capped at {MAX_INDICATORS})")
    if not indicators:
        lines.append("_(no recent rows in window)_")
    else:
        seen_keys: set[tuple] = set()
        shown = 0
        for ind in indicators:
            key = (ind["country_code"], ind["indicator_name"], ind["period_end"])
            if key in seen_keys:
                continue
            seen_keys.add(key)
            lines.append(
                f"- {ind['country_code']} {ind['indicator_name']} "
                f"({ind['period_end']}): {ind['value']} {ind['unit']} "
                f"[{ind['source']}]"
            )
            shown += 1
            if shown >= MAX_INDICATORS:
                break
    lines.append("")

    lines.append(f"## Market series (one closing print per series, latest in window, capped at {MAX_PRICES})")
    if not prices:
        lines.append("_(no prices in window)_")
    else:
        latest_per_series: dict[str, dict] = {}
        for p in prices:
            latest_per_series[p["series_id"]] = p
        shown = 0
        for sid, p in sorted(latest_per_series.items()):
            lines.append(
                f"- {sid} ({p['trade_date']}): close {p['close']}"
                + (f", vol {p['volume']}" if p["volume"] is not None else "")
            )
            shown += 1
            if shown >= MAX_PRICES:
                break
    lines.append("")

    lines.append(f"## News events (most recent, capped at {MAX_NEWS})")
    if not news:
        lines.append("_(no news in window)_")
    else:
        for n in news:
            lines.append(
                f"- [{n['event_date']:%Y-%m-%d}] ({n['source']}) "
                f"{shorten(n['headline'], width=200)}"
            )
    lines.append("")

    lines.append(f"## Prior archetype analyses (latest {MAX_PRIOR}, for continuity)")
    if not priors:
        lines.append("_(none in lookback)_")
    else:
        for a in priors:
            lines.append(f"### [{a['run_date']}] {a['archetype']} — {a['scope']}")
            lines.append(shorten(a["conclusions"] or "", width=600))
            if a.get("uncertainties"):
                lines.append(f"_Uncertainties:_ {shorten(a['uncertainties'], width=300)}")
    lines.append("")

    lines.append("## Output requirements")
    lines.append(
        "Reply with a single JSON object with these fields:\n"
        "  - `conclusions` (string, required): your interpretation of the window\n"
        "  - `uncertainties` (string, optional): where you are least confident\n"
        "  - `supporting_observations` (object, optional): pointers to specific "
        "rows above (e.g. `{\"indicators\": [\"CHN gdp_growth_pct 2026-03-31\"], "
        "\"prices\": [\"commodity.iron_ore 2026-05-15\"]}`)\n"
        "  - `proposals` (array of objects, optional): each with "
        "`pattern_description`, `data_series`, `model_structure`, "
        "`success_criteria`, `risks`. Only include if you actually see a pattern "
        "worth attempting to learn."
    )
    return "\n".join(lines)


def main(argv: list[str]) -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--archetype", required=True,
                   choices=["historian", "strategist", "macro_theorist", "skeptic"])
    p.add_argument("--scope", required=True,
                   choices=list(SCOPE_WINDOWS.keys()))
    p.add_argument("--period-end")
    args = p.parse_args(argv)
    period_end = dt.date.fromisoformat(args.period_end) if args.period_end else None
    sys.stdout.write(build(args.archetype, args.scope, period_end))


if __name__ == "__main__":
    main(sys.argv[1:])
