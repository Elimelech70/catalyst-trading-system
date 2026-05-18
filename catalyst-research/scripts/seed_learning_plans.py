"""
Name of Application : Catalyst Trading System
Name of file        : catalyst-research/scripts/seed_learning_plans.py
Version             : 0.1.0
Last Updated        : 2026-05-18
Purpose             : Idempotent applicator for new / updated learning plans.
                      The initial three v1 plans are seeded by
                      sql/002_seed_v1.sql; this script is the path Craig
                      uses to add a new plan or revise an existing one
                      between major migrations.

                      INSERT ... ON CONFLICT (name) DO UPDATE so re-running
                      with a YAML/JSON definition is safe.

CLI                 : python -m scripts.seed_learning_plans plan_file.json
                      The JSON file is a single object or an array of objects
                      with fields matching cr_learning_plans columns.

Connects as         : RESEARCH_ADMIN_DATABASE_URL (it can UPDATE; ingestion
                      role cannot).
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


def _conn_url() -> str:
    url = os.environ.get("RESEARCH_ADMIN_DATABASE_URL")
    if not url:
        raise RuntimeError("RESEARCH_ADMIN_DATABASE_URL is not set.")
    return url


def upsert_plan(conn, *, plan: dict) -> str:
    required = ("name", "question", "period_start", "period_end")
    for k in required:
        if k not in plan:
            raise ValueError(f"plan missing required field: {k}")
    data_sources = plan.get("data_sources") or {}

    sql = (
        "INSERT INTO cr_learning_plans "
        "(name, question, period_start, period_end, expected_observations, "
        " null_hypothesis, data_sources, status) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s) "
        "ON CONFLICT (name) DO UPDATE SET "
        "  question              = EXCLUDED.question, "
        "  period_start          = EXCLUDED.period_start, "
        "  period_end            = EXCLUDED.period_end, "
        "  expected_observations = EXCLUDED.expected_observations, "
        "  null_hypothesis       = EXCLUDED.null_hypothesis, "
        "  data_sources          = EXCLUDED.data_sources, "
        "  status                = EXCLUDED.status "
        "RETURNING (xmax = 0) AS inserted"
    )
    with conn.cursor() as cur:
        cur.execute(sql, (
            plan["name"],
            plan["question"],
            dt.date.fromisoformat(plan["period_start"]),
            dt.date.fromisoformat(plan["period_end"]),
            plan.get("expected_observations"),
            plan.get("null_hypothesis"),
            psycopg2.extras.Json(data_sources),
            plan.get("status", "active"),
        ))
        row = cur.fetchone()
        return "inserted" if row[0] else "updated"


def main(argv: list[str]) -> None:
    if not argv:
        print("usage: seed_learning_plans.py PATH.json", file=sys.stderr)
        sys.exit(2)
    with open(argv[0], "r", encoding="utf-8") as f:
        payload = json.load(f)
    plans = payload if isinstance(payload, list) else [payload]

    conn = psycopg2.connect(_conn_url())
    try:
        for plan in plans:
            try:
                outcome = upsert_plan(conn, plan=plan)
                print(f"{plan['name']}: {outcome}")
            except Exception as e:  # noqa: BLE001
                conn.rollback()
                print(f"{plan.get('name', '?')}: FAILED — {e}", file=sys.stderr)
                continue
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    main(sys.argv[1:])
