"""
Name of Application : Catalyst Trading System
Name of file        : catalyst-research/archetypes/run.py
Version             : 0.1.0
Last Updated        : 2026-05-18
Purpose             : Orchestrator for the four catalyst-research archetypes.
                      For each archetype: builds the system prompt
                      (lens system.md + context bundle), invokes headless
                      `claude` CLI, parses the JSON output, and writes one
                      row per archetype into cr_archetype_analyses (plus
                      any model proposals into cr_model_proposals).

                      Two phases:
                        --phase=analysis     — independent runs, all four
                        --phase=peer_review  — each archetype reviews the
                                                others' analyses written
                                                earlier in the same window

CLI                 : python -m archetypes.run \
                          --scope=weekly \
                          --phase=analysis
                      python -m archetypes.run \
                          --scope=weekly --phase=peer_review
                      python -m archetypes.run \
                          --scope=quarterly --archetype=macro_theorist
                      python -m archetypes.run \
                          --scope=learning_plan_review --plan=iron_ore_china_demand

Reference           : Documentation/Implementation/catalyst-research-implementation-v1.3.md §3

IMPORTANT           : The `claude` CLI flag set below is the v1.3 starting
                      point. Smoke-testing it against the actually-installed
                      Claude Code version on the intl droplet is a Phase 3
                      entry criterion (see §3.6). If a flag is unrecognised,
                      this wrapper fails fast — better than silently writing
                      empty rows.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

import structlog

from archetypes import build_context, db

log = structlog.get_logger()

ARCHETYPES = ["historian", "strategist", "macro_theorist", "skeptic"]

# Per-archetype turn budgets. Lower = cheaper, less elaboration.
TURNS_BY_PHASE = {
    "analysis":    10,
    "peer_review": 6,
}

THIS_DIR = Path(__file__).resolve().parent


# -----------------------------------------------------------------------------
# Claude CLI invocation
# -----------------------------------------------------------------------------

def _claude_cli() -> str:
    return os.environ.get("CLAUDE_CLI", "claude")


def assert_claude_available() -> None:
    """Hard-fail if `claude --version` doesn't succeed. Catches missing CLI
    or path issues before we burn API credits.
    """
    try:
        cp = subprocess.run([_claude_cli(), "--version"],
                            capture_output=True, text=True, timeout=15)
    except FileNotFoundError as e:
        raise RuntimeError(
            f"`claude` CLI not found on PATH (CLAUDE_CLI={_claude_cli()!r})."
        ) from e
    if cp.returncode != 0:
        raise RuntimeError(
            f"`claude --version` exited {cp.returncode}: {cp.stderr.strip()}"
        )
    log.info("claude.version", out=cp.stdout.strip())


def invoke_claude(*, system_prompt: str, max_turns: int) -> str:
    """Run headless `claude` and return its stdout (the JSON output).

    The flag set is verified against Claude Code's headless docs as of
    2026-05. If a future CLI release breaks this, the Phase 3 smoke-test
    rerun catches it.
    """
    cmd = [
        _claude_cli(),
        "--print",
        "--output-format", "json",
        "--append-system-prompt", system_prompt,
        "--max-turns", str(max_turns),
        "--permission-mode", "plan",  # archetypes must not edit files
    ]
    cp = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if cp.returncode != 0:
        raise RuntimeError(
            f"claude CLI exited {cp.returncode}: {cp.stderr.strip()[:500]}"
        )
    return cp.stdout


# -----------------------------------------------------------------------------
# Output parsing
# -----------------------------------------------------------------------------

def parse_claude_output(stdout: str) -> dict:
    """Parse the JSON stdout of `claude --output-format=json`. The shape
    Claude Code returns is `{ "result": "<assistant text>", ... }` plus
    metadata. We expect the assistant text to itself be a JSON object with
    our required schema; if it isn't pure JSON, attempt a best-effort
    extraction.
    """
    payload = json.loads(stdout)
    text = payload.get("result", "")
    text = text.strip()
    # Trim ```json ... ``` fences if the model produced them
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[len("json"):]
        text = text.strip()
    return json.loads(text)


# -----------------------------------------------------------------------------
# System prompt assembly
# -----------------------------------------------------------------------------

def _load_lens(archetype: str) -> str:
    path = THIS_DIR / archetype / "system.md"
    if not path.exists():
        raise FileNotFoundError(f"missing lens prompt: {path}")
    return path.read_text(encoding="utf-8")


def assemble_system_prompt(*, archetype: str, scope: str,
                           period_end: dt.date | None,
                           extra: str = "") -> str:
    lens = _load_lens(archetype)
    context = build_context.build(archetype, scope, period_end)
    pieces = [lens, "", "---", "", context]
    if extra:
        pieces.extend(["", "---", "", extra])
    return "\n".join(pieces)


# -----------------------------------------------------------------------------
# Phase: analysis
# -----------------------------------------------------------------------------

def run_analysis(*, scope: str, period_end: dt.date,
                 only_archetype: str | None = None) -> None:
    targets = [only_archetype] if only_archetype else list(ARCHETYPES)
    period_start = period_end - build_context.SCOPE_WINDOWS[scope]

    log.info("archetypes.run.analysis.start",
             scope=scope, period_start=period_start.isoformat(),
             period_end=period_end.isoformat(), archetypes=targets)

    runs_dir = THIS_DIR / "runs" / dt.date.today().isoformat()
    runs_dir.mkdir(parents=True, exist_ok=True)

    for archetype in targets:
        system_prompt = assemble_system_prompt(
            archetype=archetype, scope=scope, period_end=period_end,
        )
        log.info("archetypes.invoke", archetype=archetype, scope=scope,
                 prompt_chars=len(system_prompt))
        try:
            stdout = invoke_claude(
                system_prompt=system_prompt,
                max_turns=TURNS_BY_PHASE["analysis"],
            )
        except Exception as e:  # noqa: BLE001
            log.error("archetypes.invoke_failed",
                      archetype=archetype, error=str(e))
            continue

        # Persist raw artefact for forensic review
        (runs_dir / f"{archetype}_{scope}_analysis.json").write_text(
            stdout, encoding="utf-8"
        )

        try:
            parsed = parse_claude_output(stdout)
        except Exception as e:  # noqa: BLE001
            log.error("archetypes.parse_failed",
                      archetype=archetype, error=str(e),
                      stdout_head=stdout[:300])
            continue

        with db.connect() as conn:
            analysis_id = db.insert_archetype_analysis(
                conn,
                archetype=archetype,
                run_date=dt.date.today(),
                period_start=period_start,
                period_end=period_end,
                scope=scope,
                conclusions=parsed.get("conclusions", ""),
                uncertainties=parsed.get("uncertainties"),
                supporting_observations=parsed.get("supporting_observations"),
            )

            for prop in (parsed.get("proposals") or []):
                try:
                    db.insert_model_proposal(
                        conn,
                        proposing_archetype=archetype,
                        pattern_description=prop["pattern_description"],
                        data_series=prop.get("data_series", {}),
                        model_structure=prop["model_structure"],
                        success_criteria=prop["success_criteria"],
                        risks=prop.get("risks"),
                    )
                except KeyError as e:
                    log.warning("archetypes.proposal_missing_field",
                                archetype=archetype, error=str(e))

        log.info("archetypes.analysis.recorded",
                 archetype=archetype, analysis_id=analysis_id)


# -----------------------------------------------------------------------------
# Phase: peer review
# -----------------------------------------------------------------------------

def _format_peer_review_extra(others: list[dict]) -> str:
    """Render the other archetypes' analyses as appendable system-prompt
    text for the reviewing archetype to react to.
    """
    out = ["", "## Peer-review task",
           "Below are this week's analyses from the OTHER archetypes. For "
           "each one, decide if you agree (strong_agree, agree, disagree, "
           "strong_disagree) and write a short critique. Reply with a JSON "
           "object with field `reviews`: a list of "
           "`{reviewed_analysis_id, agreement, critique}`."]
    for a in others:
        out.append(f"\n### Analysis #{a['id']} — {a['archetype']} ({a['scope']}, {a['run_date']})")
        out.append(a["conclusions"] or "_(no conclusions)_")
        if a.get("uncertainties"):
            out.append(f"_Uncertainties:_ {a['uncertainties']}")
    return "\n".join(out)


def run_peer_review(*, scope: str, period_end: dt.date) -> None:
    period_start = period_end - build_context.SCOPE_WINDOWS[scope]
    log.info("archetypes.run.peer_review.start",
             scope=scope, period_start=period_start.isoformat(),
             period_end=period_end.isoformat())

    with db.connect() as conn:
        recent = db.prior_archetype_analyses(
            conn, since=period_start, limit=20,
        )

    # Group by archetype, latest per archetype only
    latest: dict[str, dict] = {}
    for a in recent:
        if a["archetype"] not in latest:
            latest[a["archetype"]] = a

    if len(latest) < 2:
        log.warning("archetypes.peer_review.too_few_analyses",
                    count=len(latest))
        return

    # Skeptic reviews last per implementation §3.3
    review_order = [a for a in ARCHETYPES if a != "skeptic"] + ["skeptic"]

    runs_dir = THIS_DIR / "runs" / dt.date.today().isoformat()
    runs_dir.mkdir(parents=True, exist_ok=True)

    for reviewer in review_order:
        if reviewer not in latest:
            continue
        others = [v for k, v in latest.items() if k != reviewer]
        extra = _format_peer_review_extra(others)

        system_prompt = assemble_system_prompt(
            archetype=reviewer, scope=scope, period_end=period_end,
            extra=extra,
        )
        log.info("archetypes.peer_review.invoke", reviewer=reviewer,
                 prompt_chars=len(system_prompt),
                 reviewing=[a["id"] for a in others])
        try:
            stdout = invoke_claude(
                system_prompt=system_prompt,
                max_turns=TURNS_BY_PHASE["peer_review"],
            )
        except Exception as e:  # noqa: BLE001
            log.error("archetypes.peer_review.failed",
                      reviewer=reviewer, error=str(e))
            continue

        (runs_dir / f"{reviewer}_{scope}_peer_review.json").write_text(
            stdout, encoding="utf-8"
        )

        try:
            parsed = parse_claude_output(stdout)
            reviews = parsed.get("reviews") or []
        except Exception as e:  # noqa: BLE001
            log.error("archetypes.peer_review.parse_failed",
                      reviewer=reviewer, error=str(e),
                      stdout_head=stdout[:300])
            continue

        with db.connect() as conn:
            for r in reviews:
                try:
                    db.insert_archetype_peer_review(
                        conn,
                        reviewer_archetype=reviewer,
                        reviewed_analysis_id=int(r["reviewed_analysis_id"]),
                        agreement=r["agreement"],
                        critique=r["critique"],
                    )
                except (KeyError, ValueError) as e:
                    log.warning("archetypes.peer_review.bad_row",
                                reviewer=reviewer, error=str(e), row=r)
        log.info("archetypes.peer_review.recorded",
                 reviewer=reviewer, count=len(reviews))


# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------

def main(argv: list[str]) -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--scope", required=True,
                   choices=["weekly", "monthly", "quarterly",
                            "learning_plan_review", "ad_hoc"])
    p.add_argument("--phase", choices=["analysis", "peer_review"],
                   default="analysis")
    p.add_argument("--archetype",
                   choices=ARCHETYPES,
                   help="If set, only run this archetype (analysis phase).")
    p.add_argument("--period-end",
                   help="Window end date (YYYY-MM-DD); defaults to today.")
    p.add_argument("--plan",
                   help="Plan name for --scope=learning_plan_review (informational).")
    args = p.parse_args(argv)

    period_end = (dt.date.fromisoformat(args.period_end)
                  if args.period_end else dt.date.today())

    assert_claude_available()

    if args.phase == "analysis":
        run_analysis(scope=args.scope, period_end=period_end,
                     only_archetype=args.archetype)
    else:
        run_peer_review(scope=args.scope, period_end=period_end)


if __name__ == "__main__":
    main(sys.argv[1:])
