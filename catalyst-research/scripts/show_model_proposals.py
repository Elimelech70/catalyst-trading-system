"""
Name of Application : Catalyst Trading System
Name of file        : catalyst-research/scripts/show_model_proposals.py
Version             : 0.1.0
Last Updated        : 2026-05-18
Purpose             : List archetype-generated model proposals filtered by
                      status (default: proposed). Without this, proposals
                      accumulate in a table no one reads (impl §3.4 / §4.4).

CLI                 : python -m scripts.show_model_proposals [STATUS]
                      STATUS in {proposed, training, evaluated_success,
                                 evaluated_failure, integrated}
"""

from __future__ import annotations

import sys

from scripts._db import connect, dictrows


def main(argv: list[str]) -> None:
    status = argv[0] if argv else "proposed"
    with connect() as conn:
        rows = dictrows(conn, (
            "SELECT id, proposing_archetype, pattern_description, "
            "       data_series, model_structure, success_criteria, risks, "
            "       status, created_at "
            "FROM cr_model_proposals "
            "WHERE status = %s "
            "ORDER BY created_at DESC"
        ), (status,))

    if not rows:
        print(f"_No model proposals with status={status!r}._")
        return

    print(f"# Model proposals — status={status} ({len(rows)} total)")
    print()
    for r in rows:
        print(f"## #{r['id']} — {r['proposing_archetype']} "
              f"({r['created_at']:%Y-%m-%d})")
        print()
        print(f"**Pattern:** {r['pattern_description']}")
        print()
        print(f"**Data series:** {r['data_series']}")
        print()
        print(f"**Model structure:** {r['model_structure']}")
        print()
        print(f"**Success criteria:** {r['success_criteria']}")
        if r.get("risks"):
            print()
            print(f"**Risks:** {r['risks']}")
        print()
        print("---")
        print()


if __name__ == "__main__":
    main(sys.argv[1:])
