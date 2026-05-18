"""
Name of Application : Catalyst Trading System
Name of file        : catalyst-research/tests/test_archetype_wrapper.py
Version             : 0.1.0
Last Updated        : 2026-05-18
Purpose             : Smoke tests for the archetype wrapper — parsing the
                      `claude --output-format=json` output and selecting
                      the right system-prompt assembly. Does NOT call out
                      to the real `claude` CLI in unit tests; that's a
                      Phase 3 entry-criterion live test.
"""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import sys

import pytest

os.environ.setdefault("RESEARCH_ARCHETYPE_DATABASE_URL",
                      "postgres://test:test@localhost/test")

# Make `archetypes` package importable when pytest runs from anywhere
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from archetypes import run as run_mod  # noqa: E402


def test_parse_claude_output_plain_json():
    stdout = json.dumps({
        "result": json.dumps({
            "conclusions": "test conclusions",
            "uncertainties": "test uncertainty",
            "supporting_observations": {"indicators": ["USA.gdp 2026-03-31"]},
        })
    })
    parsed = run_mod.parse_claude_output(stdout)
    assert parsed["conclusions"] == "test conclusions"
    assert "USA.gdp 2026-03-31" in parsed["supporting_observations"]["indicators"]


def test_parse_claude_output_strips_markdown_fences():
    stdout = json.dumps({
        "result": (
            "```json\n"
            '{"conclusions": "fenced output", "uncertainties": null, '
            '"supporting_observations": {}}'
            "\n```"
        )
    })
    parsed = run_mod.parse_claude_output(stdout)
    assert parsed["conclusions"] == "fenced output"


def test_parse_claude_output_handles_proposals():
    stdout = json.dumps({
        "result": json.dumps({
            "conclusions": "x",
            "proposals": [
                {
                    "pattern_description": "iron-ore lag",
                    "data_series": {"commodities": ["iron_ore"]},
                    "model_structure": "linear regression",
                    "success_criteria": "out-of-sample R^2 > 0.3",
                    "risks": "small sample",
                }
            ],
        })
    })
    parsed = run_mod.parse_claude_output(stdout)
    assert len(parsed["proposals"]) == 1
    assert parsed["proposals"][0]["pattern_description"] == "iron-ore lag"


def test_parse_claude_output_invalid_inner_json_raises():
    stdout = json.dumps({"result": "this is not JSON at all"})
    with pytest.raises(json.JSONDecodeError):
        run_mod.parse_claude_output(stdout)


def test_lens_files_exist_for_all_archetypes():
    """The wrapper depends on each archetype having a system.md lens file.
    Catch a missing file before a cron run does.
    """
    base = Path(__file__).resolve().parents[1] / "archetypes"
    for a in run_mod.ARCHETYPES:
        path = base / a / "system.md"
        assert path.exists(), f"missing lens prompt: {path}"
        # Sanity check: lens prompts should be at least a few hundred bytes.
        assert path.stat().st_size > 200, f"suspiciously short lens prompt: {path}"
