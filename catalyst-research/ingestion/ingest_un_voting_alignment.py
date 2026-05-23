"""
Name of Application : Catalyst Trading System
Name of file        : catalyst-research/ingestion/ingest_un_voting_alignment.py
Version             : 0.1.0
Last Updated        : 2026-05-18
Purpose             : Layer 4 — annual UN General Assembly voting-alignment
                      scores between country pairs, from the Voeten dataset.

                      Computes a simple agreement score per pair-year: the
                      share of UNGA votes where both countries voted the
                      same way among votes where both cast a position (yes,
                      no, abstain).

Cadence             : Annual. Cron: 0 8 1 6 * UTC (June 1, after typical
                      Voeten release window).
Writes to           : cr_country_pair_observations (dimension = 'unga_voting_alignment')

Reference           : Documentation/Implementation/catalyst-research-implementation-v1.3.md §2.1
                      Voeten dataverse:
                      https://dataverse.harvard.edu/dataset.xhtml?persistentId=hdl:1902.1/12379

STATUS              : Scaffold. The Voeten dataset is distributed as Stata
                      .dta and CSV. Without committing to a specific URL
                      that may break, v1 implementation downloads a stable
                      mirror or local file path. For now, the fetcher returns
                      empty until a stable source is wired in. Idempotency
                      and shape are correct.
"""

from __future__ import annotations

import datetime as dt
import os
import sys
from itertools import combinations

import structlog

from ingestion import _adapter

log = structlog.get_logger()

COUNTRIES = ["AUS", "CHN", "HKG", "USA"]

# Voeten uses Correlates of War (CoW) country codes:
ISO_TO_COW = {"USA": 2, "AUS": 900, "CHN": 710}
# HKG does NOT have a separate UNGA vote (delegation is part of CHN);
# we record `HKG`-pair entries as NULL or skip — design choice for v1: SKIP.
# So the v1 voting-alignment job covers AUS, CHN, USA only (3 pairs).


def fetch_voeten_rows() -> list[dict]:
    """Return [(year, country_a_cow, country_b_cow, agreement_score)] from
    the Voeten dataset. Empty list until a stable source is wired in.

    Suggested approach when implementing:
      1. Download `UNVotes.dta` or `UNVotes.csv` (size ~300 MB) once to
         /root/catalyst-research/data/voeten/UNVotes.csv.
      2. Use pandas + numpy: groupby(year, country_a, country_b),
         compute share of identical votes.
      3. Return one row per pair-year for the COUNTRIES we care about.
    """
    log.info("voeten.stub", msg="Voeten ingestion stub — returning empty.")
    return []


def run(*, backfill_from_year: int | None = None) -> None:
    rows_raw = fetch_voeten_rows()
    if not rows_raw:
        return

    cow_to_iso = {v: k for k, v in ISO_TO_COW.items()}

    grand_total = _adapter.UpsertResult()
    backfill = backfill_from_year is not None

    with _adapter.connect() as conn:
        rows = []
        for r in rows_raw:
            iso_a = cow_to_iso.get(r["country_a_cow"])
            iso_b = cow_to_iso.get(r["country_b_cow"])
            if iso_a is None or iso_b is None:
                continue
            a, b = sorted([iso_a, iso_b])
            year = r["year"]
            if backfill_from_year and year < backfill_from_year:
                continue
            rows.append({
                "country_a":    a,
                "country_b":    b,
                "dimension":    "unga_voting_alignment",
                "period_end":   dt.date(year, 12, 31),
                "value":        float(r["agreement_score"]),
                "unit":         "score_0_1",
                "period_start": dt.date(year, 1, 1),
                "event_date":   dt.date(year, 12, 31),
                "source":       "voeten_unga",
                "backfill":     backfill,
            })

        if rows:
            result = _adapter.upsert_facts(
                conn,
                table="cr_country_pair_observations",
                rows=rows,
                business_key_columns=("country_a", "country_b",
                                      "dimension", "period_end"),
                value_columns=("value", "unit", "period_start", "event_date"),
                value_compare_column="value",
            )
            grand_total.inserted += result.inserted
            grand_total.revised  += result.revised
            grand_total.skipped  += result.skipped
            grand_total.errors.extend(result.errors)

    grand_total.log_summary(job="ingest_un_voting_alignment",
                            table="cr_country_pair_observations")


if __name__ == "__main__":
    backfill_from_year = None
    args = sys.argv[1:]
    if args and args[0] == "--backfill-from-year" and len(args) >= 2:
        backfill_from_year = int(args[1])
    run(backfill_from_year=backfill_from_year)
