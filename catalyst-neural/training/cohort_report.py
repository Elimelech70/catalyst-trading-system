"""
Cohort experiment HTML comparison report.

Generates Documentation/Reports/cohort_experiment_<draw_date>.html with:
  A. Header (metadata + verdict block)
  B. 15-cohort leaderboard table
  C. Strategy-level boxplot (dir_acc by strategy)
  D. Strategy ANOVA + Dunn pairwise table
  E. Cohort-metric Spearman correlation table
  F. Sweet-spot scatter (median_realized_vol × dir_acc)
  G. Deflated Sharpe leaderboard
  H. PBO value with interpretation
  I. Verdict — Outcome 1 / 2 / 3 / 4 per architecture v0.2 §11

Matplotlib SVGs are base64-embedded so the HTML is self-contained.
"""

import sys
import json
import base64
from io import BytesIO
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
import numpy as np

from training.cohort_analysis import run_all_analyses

# Architecture thresholds (per architecture v0.2 §11)
DSR_THRESHOLD = 0.95          # cohort wins if DSR > this
PBO_GOOD      = 0.20          # PBO < this = winner generalises
ETA_SQ_GOOD   = 0.20          # η² > this = strategy meaningfully matters
ETA_SQ_TRIVIAL = 0.10         # η² < this = numerically significant but trivial


# ── Plotting ─────────────────────────────────────────────────────────────

def _svg_for(plot_fn):
    """Render a matplotlib figure and return base64-embedded SVG markup."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(8, 5))
    plot_fn(fig)
    buf = BytesIO()
    fig.savefig(buf, format="svg", bbox_inches="tight")
    plt.close(fig)
    svg = buf.getvalue().decode("utf-8")
    # Strip leading XML declaration so we can embed inline
    if svg.startswith("<?xml"):
        svg = svg[svg.index("?>") + 2:]
    return svg


def _boxplot_by_strategy(rows, fig):
    from collections import defaultdict
    ax = fig.add_subplot(111)
    by_strategy = defaultdict(list)
    for r in rows:
        by_strategy[r["strategy_id"]].append(r["median_dir_acc"])
    strategies = sorted(by_strategy.keys())
    data = [by_strategy[s] for s in strategies]
    ax.boxplot(data, tick_labels=strategies, showmeans=True)
    ax.set_ylabel("Median dir_acc (%)")
    ax.set_xlabel("Strategy")
    ax.set_title("Per-strategy directional accuracy distribution")
    ax.axhline(33.3, color="gray", linestyle="--", linewidth=0.8,
              label="Chance (33.3%)")
    ax.legend()
    ax.grid(True, alpha=0.3)


def _sweet_spot_scatter(rows, fig):
    ax = fig.add_subplot(111)
    xs, ys, ids = [], [], []
    for r in rows:
        m = json.loads(r["cohort_metrics_json"])
        v = m.get("median_realized_vol")
        if v is None: continue
        xs.append(v); ys.append(r["median_dir_acc"]); ids.append(r["cohort_id"])
    # Colour by strategy
    colors = {"A": "tab:red", "B": "tab:blue", "C": "tab:green",
              "D": "tab:orange", "E": "tab:purple"}
    for cid, x, y in zip(ids, xs, ys):
        strategy = cid[0]
        ax.scatter(x, y, c=colors.get(strategy, "gray"), s=80, alpha=0.7,
                  edgecolors="black", linewidth=0.5)
        ax.annotate(cid.split("_")[0], (x, y), fontsize=7,
                   xytext=(3, 3), textcoords="offset points")
    ax.set_xlabel("Median realized vol (raw 5m σ)")
    ax.set_ylabel("Median dir_acc (%)")
    ax.set_title("Sweet-spot: volatility × directional accuracy")
    ax.grid(True, alpha=0.3)
    import matplotlib.patches
    handles = [matplotlib.patches.Patch(color=c, label=s)
              for s, c in colors.items()]
    ax.legend(handles=handles, title="Strategy", loc="best")


def _correlation_bar(corrs, fig):
    ax = fig.add_subplot(111)
    keys = list(corrs.keys())
    rhos = [corrs[k]["rho"] for k in keys]
    pvals = [corrs[k]["p_value"] for k in keys]
    colors = ["tab:green" if p < 0.05 else "lightgray" for p in pvals]
    ax.barh(keys, rhos, color=colors, edgecolor="black", linewidth=0.5)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlabel("Spearman ρ (vs median dir_acc)")
    ax.set_title("Cohort-metric correlations with directional accuracy")
    ax.set_xlim(-1, 1)
    ax.grid(True, axis="x", alpha=0.3)


# ── Verdict ──────────────────────────────────────────────────────────────

def determine_verdict(analyses):
    """Architecture v0.2 §11 outcome classification.
    Returns (outcome_id, headline, body)."""
    pbo = analyses["pbo"]
    eta = analyses["anova_dir_acc"]["eta_squared"]
    anova_p = analyses["anova_dir_acc"]["p_value"]
    dsr = analyses["deflated_sharpe"]

    # Group DSRs by strategy
    from collections import defaultdict
    dsr_by_strategy = defaultdict(list)
    for cid, v in dsr.items():
        dsr_by_strategy[cid[0]].append(v["dsr"])

    # Outcome 1: A strategy where ALL 3 instances clear DSR threshold, PBO good, ANOVA rejects
    strategies_all_clear = [s for s, lst in dsr_by_strategy.items()
                           if len(lst) >= 1 and all(d > DSR_THRESHOLD for d in lst)]
    if (len(strategies_all_clear) == 1 and pbo < PBO_GOOD
            and anova_p < 0.05 and eta > ETA_SQ_GOOD):
        winner = strategies_all_clear[0]
        return ("1", f"Outcome 1: Strategy {winner} wins clearly",
                f"All cohorts of Strategy {winner} cleared DSR > {DSR_THRESHOLD}, "
                f"PBO = {pbo:.3f} < {PBO_GOOD}, ANOVA omnibus p = {anova_p:.4f} "
                f"with η² = {eta:.3f} > {ETA_SQ_GOOD}. "
                f"Action: freeze Strategy {winner} as the v0.4.1 production "
                f"universe-selection rule.")

    # Outcome 2: Two strategies tie
    if len(strategies_all_clear) == 2 and pbo < 0.3:
        return ("2", f"Outcome 2: Strategies {strategies_all_clear} tie",
                f"Two strategies cleared DSR threshold; PBO = {pbo:.3f} < 0.30. "
                f"Action: pick the operationally simpler strategy "
                f"(C — stratified mix is usually the lowest-burden choice). "
                f"Document the tie in the decision note.")

    # Outcome 3: Vol is real signal but no structured strategy wins
    # B1 (top decile) > B3 (bottom) AND E1 (top vol) > E3 (random null)
    by_cohort_id = {r["cohort_id"]: r for r in analyses["leaderboard"]}
    try:
        b1 = next(r for cid, r in by_cohort_id.items() if cid.startswith("B1"))
        b3 = next(r for cid, r in by_cohort_id.items() if cid.startswith("B3"))
        e1 = next(r for cid, r in by_cohort_id.items() if cid.startswith("E1"))
        e3 = next(r for cid, r in by_cohort_id.items() if cid.startswith("E3"))
        if (b1["median_dir_acc"] - b3["median_dir_acc"] > 1.0
                and e1["median_dir_acc"] - e3["median_dir_acc"] > 0.5):
            return ("3", "Outcome 3: Volatility is a real driver",
                    f"B1 (top-vol decile) beats B3 (bottom-vol decile) by "
                    f"{b1['median_dir_acc'] - b3['median_dir_acc']:+.2f} pp; "
                    f"E1 (top-150 mover) beats E3 (random null) by "
                    f"{e1['median_dir_acc'] - e3['median_dir_acc']:+.2f} pp. "
                    f"No single grouping strategy dominates, but volatility "
                    f"itself is signal. Action: adopt vol-rank-filtered universe "
                    f"for v0.4.1.")
    except StopIteration:
        pass

    # Outcome 4: null
    return ("4", "Outcome 4: No strategy beats the null",
            f"DSR threshold not cleared by any strategy's cohorts in unison "
            f"(strategies clearing all-3: {strategies_all_clear or 'none'}). "
            f"PBO = {pbo:.3f}, ANOVA p = {anova_p:.4f}, η² = {eta:.3f}. "
            f"The universe is not the bottleneck. Action: return to the v0.4 "
            f"architecture. Revisit news coverage breadth or model architecture. "
            f"Do NOT deploy v0.4.1 from this experiment.")


# ── HTML rendering ───────────────────────────────────────────────────────

_VERDICT_STYLE = {
    "1": "background:#d4edda;border-left:6px solid #28a745;",
    "2": "background:#d4edda;border-left:6px solid #28a745;",
    "3": "background:#fff3cd;border-left:6px solid #ffc107;",
    "4": "background:#f8d7da;border-left:6px solid #dc3545;",
}


def _table(headers, rows, classes=""):
    """Render a simple HTML table."""
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>"
                  for r in rows)
    return (f'<table class="{classes}"><thead><tr>{head}</tr></thead>'
            f'<tbody>{body}</tbody></table>')


def render_report(analyses, output_path):
    if "error" in analyses:
        raise RuntimeError(analyses["error"])

    rows = analyses["leaderboard"]
    outcome, headline, body = determine_verdict(analyses)

    # Section A — verdict block
    verdict_html = (
        f'<div class="verdict" style="{_VERDICT_STYLE[outcome]}'
        f'padding:18px;margin:24px 0;border-radius:4px;">'
        f'<h2 style="margin:0 0 8px 0;">{headline}</h2>'
        f'<p style="margin:0;">{body}</p></div>'
    )

    # Section B — leaderboard
    lb_rows = []
    for r in rows:
        dsr = analyses["deflated_sharpe"][r["cohort_id"]]["dsr"]
        sr  = analyses["deflated_sharpe"][r["cohort_id"]]["sr"]
        lb_rows.append([
            r["cohort_id"], r["strategy_id"], r["instance_id"], r["n_symbols"],
            f"{r['median_dir_acc']:.2f}%", f"{r['median_val_loss']:.4f}",
            f"{r['median_val_mae']:.4f}", f"{sr:+.2f}", f"{dsr:.3f}",
            r["effective_sample_n"],
        ])
    leaderboard_html = _table(
        ["Cohort", "Str", "Inst", "N", "Dir acc", "Val loss", "Val MAE",
         "Sharpe", "DSR", "Eff. N"],
        lb_rows, "leaderboard")

    # Section C — strategy boxplot
    boxplot_svg = _svg_for(lambda f: _boxplot_by_strategy(rows, f))

    # Section D — ANOVA + Dunn
    a = analyses["anova_dir_acc"]
    anova_html = (
        f'<p><b>Kruskal-Wallis omnibus:</b> H = {a["H"]:.3f}, '
        f'p = {a["p_value"]:.4f}, η² = {a["eta_squared"]:.3f}</p>'
    )
    bs = a["by_strategy"]
    anova_html += _table(
        ["Strategy", "Mean dir_acc", "SD", "N"],
        [[s, f'{bs[s]["mean"]:.2f}%', f'{bs[s]["std"]:.2f}', bs[s]["n"]]
         for s in sorted(bs)], "anova")
    dunn = analyses["pairwise_dunn"]
    if dunn:
        anova_html += "<h4>Pairwise Dunn (BH-FDR α=0.05)</h4>"
        anova_html += _table(
            ["Pair", "z", "p_raw", "p_adj", "significant"],
            [[f'{d["pair"][0]} vs {d["pair"][1]}',
              f'{d["z"]:+.3f}', f'{d["p_raw"]:.4f}', f'{d["p_adj"]:.4f}',
              "yes" if d["significant"] else "no"]
             for d in dunn], "dunn")

    # Section E — correlations
    corr = analyses["correlations"]
    corr_html = _table(
        ["Descriptor", "ρ (vs dir_acc)", "p-value", "n"],
        [[k, f'{v["rho"]:+.3f}', f'{v["p_value"]:.4f}', v["n"]]
         for k, v in corr.items()], "corr")
    corr_svg = _svg_for(lambda f: _correlation_bar(corr, f))

    # Section F — sweet-spot scatter
    sweet_svg = _svg_for(lambda f: _sweet_spot_scatter(rows, f))
    ss = analyses["sweet_spot_vol"]
    sweet_caption = (f'Spearman ρ(vol, dir_acc) = {ss.get("rho", float("nan")):+.3f}, '
                    f'p = {ss.get("p_value", float("nan")):.4f}. '
                    f'Shape: <b>{ss.get("shape", "")}</b>')

    # Section H — PBO
    pbo = analyses["pbo"]
    if pbo < 0.20:
        pbo_interp = "Winner generalises (PBO < 0.20)."
    elif pbo < 0.50:
        pbo_interp = "Borderline — winner has modest out-of-sample reliability."
    else:
        pbo_interp = "Severe overfit risk (PBO ≥ 0.50). Treat as null result."

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>Cohort Experiment Report — {analyses['draw_date']}</title>
<style>
body {{ font-family: -apple-system, sans-serif; max-width: 1100px;
        margin: 24px auto; padding: 0 16px; color: #222; }}
h1 {{ border-bottom: 2px solid #333; padding-bottom: 6px; }}
h2 {{ margin-top: 32px; color: #444; }}
table {{ border-collapse: collapse; margin: 12px 0; }}
th, td {{ padding: 6px 12px; text-align: left; border: 1px solid #ddd; }}
th {{ background: #f4f4f4; }}
.leaderboard td:nth-child(5), .leaderboard td:nth-child(9) {{ font-weight: bold; }}
.tag {{ background: #eef; padding: 2px 6px; border-radius: 3px; font-size: 12px; }}
.caption {{ font-size: 13px; color: #666; margin-top: 4px; }}
svg {{ max-width: 100%; height: auto; }}
</style></head>
<body>
<h1>Cohort experiment — {analyses['draw_date']}</h1>
<p class="caption">
  {analyses['n_cohorts']} cohorts complete · generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}
</p>

{verdict_html}

<h2>A. Leaderboard</h2>
{leaderboard_html}

<h2>B. Strategy-level distribution</h2>
{boxplot_svg}

<h2>C. Strategy ANOVA</h2>
{anova_html}

<h2>D. Cohort-metric Spearman correlations</h2>
{corr_html}
{corr_svg}

<h2>E. Sweet-spot detection</h2>
{sweet_svg}
<p class="caption">{sweet_caption}</p>

<h2>F. Deflated Sharpe Ratio per cohort</h2>
{_table(["Cohort", "Raw Sharpe", "DSR (N=15 deflated)"],
        [[cid, f'{v["sr"]:+.2f}', f'{v["dsr"]:.3f}']
         for cid, v in sorted(analyses["deflated_sharpe"].items(),
                             key=lambda kv: -kv[1]["dsr"])], "dsr-table")}
<p class="caption">Threshold for "winner": DSR &gt; {DSR_THRESHOLD}</p>

<h2>G. Probability of Backtest Overfitting</h2>
<p><b>PBO = {pbo:.3f}</b> — {pbo_interp}</p>

<h2>H. Common failure modes</h2>
<p class="caption">{analyses['common_failures']['note']}</p>

<hr>
<p class="caption">
Catalyst Neural — Cohort Experiments. Architecture: catalyst-cohort-experiments-architecture-v0.1.md v0.2.
Methodology: catalyst-ml-methodology-v0.1.md.
</p>
</body></html>"""

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(html)
    return output_path


def main(draw_date=None, output_dir=None):
    analyses = run_all_analyses(draw_date)
    if "error" in analyses:
        print(analyses["error"]); sys.exit(1)
    if output_dir is None:
        output_dir = Path(__file__).parent.parent.parent / "Documentation" / "Reports"
    out_path = Path(output_dir) / f"cohort_experiment_{analyses['draw_date']}.html"
    render_report(analyses, out_path)
    print(f"Report written: {out_path}")
    return out_path


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Cohort experiment HTML report")
    p.add_argument("--draw-date", default=None)
    p.add_argument("--output-dir", default=None)
    args = p.parse_args()
    main(args.draw_date, args.output_dir)
