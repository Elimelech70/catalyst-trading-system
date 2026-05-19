"""
Name of Application : Catalyst Trading System
Name of file        : catalyst-research/scripts/show_weekly_report.py
Version             : 0.1.0
Last Updated        : 2026-05-18
Purpose             : Prints a Markdown report of the week's archetype
                      analyses + peer reviews. This is what Craig reads on
                      the weekly review (per impl §3.6 / §4.4).

CLI                 : python -m scripts.show_weekly_report [WEEK_END_YYYY-MM-DD]
                      Default WEEK_END = today.
"""

from __future__ import annotations

import datetime as dt
import sys
from textwrap import indent

from scripts._db import connect, dictrows


def fmt(date: dt.date) -> str:
    return date.strftime("%Y-%m-%d")


def main(argv: list[str]) -> None:
    week_end = (dt.date.fromisoformat(argv[0]) if argv else dt.date.today())
    week_start = week_end - dt.timedelta(days=7)

    print(f"# Weekly Archetype Report — {fmt(week_start)} to {fmt(week_end)}")
    print()

    with connect() as conn:
        analyses = dictrows(conn, (
            "SELECT id, archetype, scope, run_date, period_start, period_end, "
            "       conclusions, uncertainties "
            "FROM cr_archetype_analyses "
            "WHERE run_date >= %s AND run_date <= %s "
            "ORDER BY archetype, run_date DESC"
        ), (week_start, week_end))

        reviews_by_analysis: dict[int, list[dict]] = {}
        if analyses:
            ids = [a["id"] for a in analyses]
            reviews = dictrows(conn, (
                "SELECT reviewer_archetype, reviewed_analysis_id, "
                "       agreement, critique "
                "FROM cr_archetype_peer_reviews "
                "WHERE reviewed_analysis_id = ANY(%s) "
                "ORDER BY reviewed_analysis_id, reviewer_archetype"
            ), (ids,))
            for r in reviews:
                reviews_by_analysis.setdefault(
                    r["reviewed_analysis_id"], []).append(r)

    if not analyses:
        print("_No archetype analyses recorded in this window._")
        return

    # Section per archetype, latest-first
    by_arch: dict[str, list[dict]] = {}
    for a in analyses:
        by_arch.setdefault(a["archetype"], []).append(a)

    for arch in ("historian", "strategist", "macro_theorist", "skeptic"):
        rows = by_arch.get(arch, [])
        if not rows:
            continue
        print(f"## {arch.replace('_', ' ').title()}")
        print()
        for a in rows:
            print(f"### {fmt(a['run_date'])} — {a['scope']} "
                  f"(window {fmt(a['period_start'])}..{fmt(a['period_end'])})")
            print()
            print(a["conclusions"] or "_(empty conclusions)_")
            if a.get("uncertainties"):
                print()
                print("**Uncertainties:**")
                print()
                print(indent(a["uncertainties"], "> "))
            revs = reviews_by_analysis.get(a["id"], [])
            if revs:
                print()
                print("**Peer reviews:**")
                print()
                for r in revs:
                    print(f"- _{r['reviewer_archetype']}_ "
                          f"(**{r['agreement']}**): {r['critique']}")
            print()

    print("---")
    print()
    print(f"_End of report. Generated {dt.datetime.now().isoformat(timespec='seconds')}._")


if __name__ == "__main__":
    main(sys.argv[1:])
