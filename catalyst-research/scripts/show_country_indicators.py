"""
Name of Application : Catalyst Trading System
Name of file        : catalyst-research/scripts/show_country_indicators.py
Version             : 0.1.0
Last Updated        : 2026-05-18
Purpose             : Print one row per (country, indicator_name) showing the
                      latest value, its source, and how many revisions are
                      on file. Quick health check for Layer 1 ingestion.

CLI                 : python -m scripts.show_country_indicators [COUNTRY]
                      COUNTRY defaults to all four v1 countries.
"""

from __future__ import annotations

import sys

from scripts._db import connect, dictrows


SQL = """
WITH latest AS (
    SELECT DISTINCT ON (country_code, indicator_name)
           country_code, indicator_name, value, unit,
           period_end, source, recorded_at, dalio_power
    FROM cr_country_indicators
    {where}
    ORDER BY country_code, indicator_name, period_end DESC, recorded_at DESC
),
revisions AS (
    SELECT country_code, indicator_name, count(*) AS n_rows
    FROM cr_country_indicators
    GROUP BY country_code, indicator_name
)
SELECT l.country_code, l.indicator_name, l.value, l.unit, l.period_end,
       l.source, l.dalio_power, r.n_rows
FROM latest l JOIN revisions r
  ON l.country_code = r.country_code AND l.indicator_name = r.indicator_name
ORDER BY l.country_code, l.indicator_name
"""


def main(argv: list[str]) -> None:
    country = argv[0].upper() if argv else None
    where = "WHERE country_code = %s" if country else ""
    params = (country,) if country else ()
    with connect() as conn:
        rows = dictrows(conn, SQL.format(where=where), params)

    if not rows:
        print("no rows", file=sys.stderr)
        return

    # Tabular print
    headers = ["country", "indicator", "value", "unit",
               "period_end", "dalio", "src", "n"]
    print(" | ".join(f"{h:<14}" for h in headers))
    print("-" * (len(headers) * 17))
    for r in rows:
        print(" | ".join([
            f"{r['country_code']:<14}",
            f"{r['indicator_name']:<14}",
            f"{r['value']:<14}",
            f"{r['unit']:<14}",
            f"{str(r['period_end']):<14}",
            f"{(r['dalio_power'] or '—'):<14}",
            f"{r['source'][:14]:<14}",
            f"{r['n_rows']:<14}",
        ]))


if __name__ == "__main__":
    main(sys.argv[1:])
