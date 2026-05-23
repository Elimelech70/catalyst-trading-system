"""
Name of Application: Catalyst Trading System
Name of file: news_classifier_regex.py
Version: 0.1.0
Last Updated: 2026-05-23
Purpose: Regex-baseline news classifier — 15-category taxonomy.

REVISION HISTORY:
v0.1.0 (2026-05-23) - Initial implementation. Phase 2 of v0.4 context-conditioned plan.
  - Loads news_taxonomy.yaml
  - Scores headlines by matched keyword count, with boost-keyword multiplier
  - Returns top 3 categories above confidence threshold, ranked by score
  - Supports backfill mode (tag all NULL rows) and at-collection-time mode (tag one)

Reference: Documentation/Implementation/catalyst-context-conditioned-implementation-v0.1.md Phase 2.
"""

import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from storage.database import get_connection

TAXONOMY_PATH = Path(__file__).parent / "news_taxonomy.yaml"
CLASSIFIER_VERSION = "regex_v1"


def load_taxonomy(path: Path = TAXONOMY_PATH) -> dict:
    """Load the 15-category news taxonomy."""
    with open(path) as f:
        return yaml.safe_load(f)


def _compile_patterns(taxonomy: dict) -> Dict[str, dict]:
    """
    Pre-compile case-insensitive regex patterns per category.
    Each keyword is matched as a word-boundary-aware substring.

    Returns: {category_name: {"match": [pattern, ...], "boost": [pattern, ...], "priority": int}}
    """
    compiled = {}
    for name, spec in taxonomy["categories"].items():
        if name == "other":
            compiled[name] = {"match": [], "boost": [], "priority": spec.get("priority", 5)}
            continue
        match_patterns = []
        for kw in spec.get("match_keywords") or []:
            # Word-boundary if keyword is alphanumeric; else literal substring.
            if re.match(r"^[a-z0-9 ]+$", kw, re.IGNORECASE):
                pattern = re.compile(rf"\b{re.escape(kw)}\b", re.IGNORECASE)
            else:
                pattern = re.compile(re.escape(kw), re.IGNORECASE)
            match_patterns.append(pattern)
        boost_patterns = []
        for kw in spec.get("boost_keywords") or []:
            pattern = re.compile(re.escape(kw), re.IGNORECASE)
            boost_patterns.append(pattern)
        compiled[name] = {
            "match": match_patterns,
            "boost": boost_patterns,
            "priority": spec.get("priority", 3),
        }
    return compiled


def classify_headline(
    headline: str,
    content_snippet: Optional[str] = None,
    compiled: Optional[Dict[str, dict]] = None,
    taxonomy: Optional[dict] = None,
) -> Tuple[List[str], float]:
    """
    Classify a single headline against the 15-category taxonomy.

    Returns: (top-3 categories above threshold, confidence of the top match).
        Pads with None if fewer than 3 matches.
        Returns (['other', None, None], 0.0) if nothing matches.

    Scoring: match_count + 0.5 * boost_count, normalized to 0-1 by the
    max-possible score (= number of match keywords in the category).
    """
    if compiled is None:
        if taxonomy is None:
            taxonomy = load_taxonomy()
        compiled = _compile_patterns(taxonomy)
    if taxonomy is None:
        taxonomy = load_taxonomy()

    text = headline or ""
    if content_snippet:
        text = f"{text} {content_snippet}"

    scores = {}
    for name, spec in compiled.items():
        if name == "other":
            continue
        match_count = sum(1 for p in spec["match"] if p.search(text))
        if match_count == 0:
            continue
        boost_count = sum(1 for p in spec["boost"] if p.search(text))
        # Saturating score: 1 match = 0.33, 2 = 0.67, 3+ = 1.0, plus 0.5/boost.
        # Don't divide by category size — a category having more keywords doesn't
        # mean a matched-against headline is less likely to belong to it.
        raw = (match_count + 0.5 * boost_count) / 3.0
        scores[name] = min(1.0, raw)

    threshold = float(taxonomy.get("confidence_threshold", 0.15))
    # Filter and rank: higher score wins; ties broken by lower priority number.
    ranked = sorted(
        ((name, score) for name, score in scores.items() if score >= threshold),
        key=lambda x: (-x[1], compiled[x[0]]["priority"]),
    )

    if not ranked:
        return (["other", None, None], 0.0)

    top3 = [r[0] for r in ranked[:3]]
    while len(top3) < 3:
        top3.append(None)
    return (top3, ranked[0][1])


def tag_row(news_id: int, headline: str, content_snippet: Optional[str],
            compiled: Dict[str, dict], taxonomy: dict, conn=None) -> dict:
    """
    Tag a single news row in the DB. Returns the tag dict.
    Caller provides a connection (and commits) or this opens its own.
    """
    own_conn = conn is None
    if own_conn:
        conn = get_connection()

    cats, conf = classify_headline(headline, content_snippet, compiled, taxonomy)
    now = datetime.utcnow().isoformat()
    conn.execute(
        """
        UPDATE news SET
            news_category_primary = ?,
            news_category_secondary = ?,
            news_category_tertiary = ?,
            category_confidence = ?,
            classified_by = ?,
            classified_at = ?
        WHERE id = ?
        """,
        (cats[0], cats[1], cats[2], conf, CLASSIFIER_VERSION, now, news_id),
    )
    if own_conn:
        conn.commit()
        conn.close()

    return {
        "id": news_id,
        "primary": cats[0],
        "secondary": cats[1],
        "tertiary": cats[2],
        "confidence": conf,
    }


def backfill(batch_size: int = 500, only_unclassified: bool = True, verbose: bool = True) -> dict:
    """
    Backfill news_category_* on all rows.

    only_unclassified: if True, skip rows where news_category_primary is already set.
    Returns: {"processed": N, "by_category": {cat: count, ...}}
    """
    taxonomy = load_taxonomy()
    compiled = _compile_patterns(taxonomy)

    conn = get_connection()
    where = " WHERE news_category_primary IS NULL " if only_unclassified else ""
    total = conn.execute(f"SELECT COUNT(*) FROM news{where}").fetchone()[0]

    if verbose:
        print(f"Backfilling {total:,} news rows ({'unclassified only' if only_unclassified else 'all'})...")

    if total == 0:
        conn.close()
        return {"processed": 0, "by_category": {}}

    by_category = {}
    processed = 0
    offset = 0

    while True:
        rows = conn.execute(
            f"SELECT id, headline, content_snippet FROM news{where} "
            f"ORDER BY id LIMIT ? OFFSET ?",
            (batch_size, offset),
        ).fetchall()
        if not rows:
            break
        for row in rows:
            tag = tag_row(row["id"], row["headline"], row["content_snippet"],
                          compiled, taxonomy, conn=conn)
            by_category[tag["primary"]] = by_category.get(tag["primary"], 0) + 1
            processed += 1
        conn.commit()
        offset += batch_size
        if verbose and processed % (batch_size * 10) == 0:
            print(f"  {processed:,} / {total:,}")

    conn.close()
    if verbose:
        print(f"Done. Processed {processed:,}.")
        print("Category distribution:")
        for cat, n in sorted(by_category.items(), key=lambda x: -x[1]):
            pct = 100.0 * n / processed
            print(f"  {cat:25s} {n:6,}  ({pct:5.1f}%)")

    return {"processed": processed, "by_category": by_category}


def sample_review(n: int = 20, seed: int = 42) -> List[dict]:
    """
    Pull n random tagged headlines for manual review.
    """
    import random
    random.seed(seed)
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, headline, news_category_primary, news_category_secondary, "
        "category_confidence FROM news WHERE news_category_primary IS NOT NULL "
        "ORDER BY RANDOM() LIMIT ?",
        (n,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Regex news classifier (15 categories)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_back = sub.add_parser("backfill", help="Tag all unclassified news rows")
    p_back.add_argument("--all", action="store_true", help="Re-tag already-classified rows too")
    p_back.add_argument("--batch", type=int, default=500)

    p_test = sub.add_parser("test", help="Classify a single headline (stdin or argv)")
    p_test.add_argument("headline", nargs="?", help="Headline to classify")

    p_sample = sub.add_parser("sample", help="Pull random tagged headlines for review")
    p_sample.add_argument("-n", type=int, default=20)

    args = parser.parse_args()

    if args.cmd == "backfill":
        backfill(batch_size=args.batch, only_unclassified=not args.all)
    elif args.cmd == "test":
        headline = args.headline or sys.stdin.read().strip()
        cats, conf = classify_headline(headline)
        print(f"Headline: {headline}")
        print(f"Top 3: {cats}")
        print(f"Confidence: {conf:.3f}")
    elif args.cmd == "sample":
        for r in sample_review(args.n):
            print(f"  [{r['news_category_primary']:25s}] ({r['category_confidence']:.2f}) {r['headline']}")
