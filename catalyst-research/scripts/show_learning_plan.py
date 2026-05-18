"""
Name of Application : Catalyst Trading System
Name of file        : catalyst-research/scripts/show_learning_plan.py
Version             : 0.1.0
Last Updated        : 2026-05-18
Purpose             : Print a learning plan's status: question, expected
                      observations, null hypothesis, period, current status,
                      the data series the plan depends on, and a tail of
                      recent values for those series so Craig can see whether
                      the data is even arriving.

CLI                 : python -m scripts.show_learning_plan PLAN_NAME
"""

from __future__ import annotations

import datetime as dt
import sys

from scripts._db import connect, dictrows


def main(argv: list[str]) -> None:
    if not argv:
        print("usage: show_learning_plan.py PLAN_NAME", file=sys.stderr)
        sys.exit(2)
    name = argv[0]

    with connect() as conn:
        rows = dictrows(conn, (
            "SELECT id, name, question, period_start, period_end, "
            "       expected_observations, null_hypothesis, data_sources, "
            "       status, outcome_notes, updated_at "
            "FROM cr_learning_plans WHERE name = %s"
        ), (name,))
        if not rows:
            print(f"no learning plan found with name={name!r}", file=sys.stderr)
            sys.exit(1)
        plan = rows[0]

        print(f"# Learning plan — {plan['name']}")
        print()
        print(f"**Status:** {plan['status']}  "
              f"**Period:** {plan['period_start']} .. {plan['period_end']}")
        print()
        print("## Question")
        print(plan["question"])
        print()
        print("## Expected")
        print(plan["expected_observations"] or "_(not set)_")
        print()
        print("## Null hypothesis")
        print(plan["null_hypothesis"] or "_(not set)_")
        print()
        print("## Data sources")
        ds = plan.get("data_sources") or {}
        print("```json")
        import json
        print(json.dumps(ds, indent=2, default=str))
        print("```")
        print()

        if plan.get("outcome_notes"):
            print("## Outcome notes")
            print(plan["outcome_notes"])
            print()

        # Recent data sample — uses architecture-level series names
        # (commodities, securities) if present in data_sources.
        commodities = ds.get("commodities", [])
        if commodities:
            print(f"## Recent commodity prices (last 10 trade days)")
            for c in commodities:
                series_id = f"commodity.{c}"
                hist = dictrows(conn, (
                    "SELECT trade_date, close FROM cr_market_prices "
                    "WHERE series_id = %s "
                    "ORDER BY trade_date DESC LIMIT 10"
                ), (series_id,))
                if not hist:
                    print(f"- {series_id}: _no rows_")
                    continue
                trail = ", ".join(f"{h['close']:.2f}" for h in reversed(hist))
                print(f"- {series_id}: {trail}")
            print()


if __name__ == "__main__":
    main(sys.argv[1:])
