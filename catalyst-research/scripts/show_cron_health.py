"""
Name of Application : Catalyst Trading System
Name of file        : catalyst-research/scripts/show_cron_health.py
Version             : 0.1.0
Last Updated        : 2026-05-18
Purpose             : Heartbeat for the system. The doc commits to NO
                      alerting (Appendix B); this is Craig's discovery
                      mechanism for silently-failing jobs and archetype
                      budget drift.

                      For each ingestion job (identified by recorded_by),
                      shows the most-recent insert date and row count.
                      For archetypes, shows month-to-date run count vs the
                      ~37/month projection.

                      Run weekly alongside show_weekly_report.py.

CLI                 : python -m scripts.show_cron_health
"""

from __future__ import annotations

import datetime as dt

from scripts._db import connect, dictrows


FACT_TABLES = [
    "cr_country_indicators",
    "cr_country_cycle_estimates",
    "cr_market_prices",
    "cr_security_prices",
    "cr_country_pair_observations",
    "cr_financial_infra_observations",
]


def main() -> None:
    print(f"# Cron health — {dt.datetime.now().isoformat(timespec='seconds')}")
    print()

    with connect() as conn:
        print("## Ingestion jobs — most-recent insert per recorded_by")
        print()
        print("| Table | Job (recorded_by) | Last insert | Rows in last 7d |")
        print("|---|---|---|---|")
        for table in FACT_TABLES:
            rows = dictrows(conn, (
                f"SELECT recorded_by, "
                f"       max(recorded_at) AS last_insert, "
                f"       count(*) FILTER (WHERE recorded_at > now() - interval '7 days') AS recent_n "
                f"FROM {table} "
                f"GROUP BY recorded_by "
                f"ORDER BY recorded_by"
            ))
            if not rows:
                print(f"| {table} | _(no rows)_ | — | — |")
                continue
            for r in rows:
                ts = r["last_insert"]
                print(f"| {table} | {r['recorded_by']} | "
                      f"{ts.isoformat(timespec='seconds') if ts else '—'} | "
                      f"{r['recent_n']} |")
        print()

        print("## News events — last 24h, 7d")
        rows = dictrows(conn, (
            "SELECT count(*) FILTER (WHERE recorded_at > now() - interval '24 hours') AS h24, "
            "       count(*) FILTER (WHERE recorded_at > now() - interval '7 days')  AS d7,  "
            "       max(recorded_at) AS last_insert "
            "FROM cr_news_events"
        ))
        r = rows[0]
        print(f"- 24h: {r['h24']}, 7d: {r['d7']}, last: {r['last_insert']}")
        print()

        print("## Archetype runs — month-to-date (projection ~37/month)")
        first_of_month = dt.date.today().replace(day=1)
        rows = dictrows(conn, (
            "SELECT archetype, scope, count(*) AS n "
            "FROM cr_archetype_analyses "
            "WHERE run_date >= %s "
            "GROUP BY archetype, scope "
            "ORDER BY archetype, scope"
        ), (first_of_month,))
        peer_rows = dictrows(conn, (
            "SELECT reviewer_archetype, count(*) AS n "
            "FROM cr_archetype_peer_reviews "
            "WHERE recorded_at >= %s "
            "GROUP BY reviewer_archetype "
            "ORDER BY reviewer_archetype"
        ), (first_of_month,))
        analyses_total = sum(r["n"] for r in rows)
        reviews_total  = sum(r["n"] for r in peer_rows)
        total = analyses_total + reviews_total
        print()
        print("Analyses:")
        for r in rows:
            print(f"  - {r['archetype']:<15} {r['scope']:<10} {r['n']}")
        print(f"  Subtotal: {analyses_total}")
        print()
        print("Peer reviews:")
        for r in peer_rows:
            print(f"  - {r['reviewer_archetype']:<15} {r['n']}")
        print(f"  Subtotal: {reviews_total}")
        print()
        print(f"**Month-to-date total: {total}** (projection ~37; alarm at 1.5× = 55+)")
        if total > 55:
            print()
            print("> ⚠️ ABOVE 1.5× projection. Investigate before next cycle.")


if __name__ == "__main__":
    main()
