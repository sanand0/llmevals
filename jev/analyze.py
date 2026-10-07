#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy>=2", "scikit-learn>=1.5"]
# ///
"""Analyze the frozen Jev/BANKING77 pilot and rebuild summary.json + index.html."""
from __future__ import annotations

import csv
import html
import json
import math
import statistics
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
MODELS = json.loads((ROOT / "models.json").read_text())
ORDER = list(MODELS)


def ece(y: list[int], p: list[float], bins: int = 10) -> float:
    yy, pp = np.asarray(y), np.asarray(p)
    total = 0.0
    for i in range(bins):
        lo, hi = i / bins, (i + 1) / bins
        mask = (pp >= lo) & ((pp < hi) if i < bins - 1 else (pp <= hi))
        if mask.any():
            total += mask.mean() * abs(pp[mask].mean() - yy[mask].mean())
    return float(total)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    p = k / n
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return center - half, center + half


def attainable_coverage(y: list[int], p: list[float], target: float) -> tuple[float, float | None, float | None]:
    best = (0, None, None)
    for threshold in sorted(set(p), reverse=True):
        keep = [i for i, score in enumerate(p) if score >= threshold]
        error = sum(1 - y[i] for i in keep) / len(keep)
        if error <= target and len(keep) > best[0]:
            best = (len(keep), threshold, error)
    return best[0] / len(y), best[1], best[2]


def load_unique_results() -> dict[tuple[str, str], dict[str, object]]:
    rows = [json.loads(line) for line in (DATA / "results.jsonl").read_text().splitlines() if line.strip()]
    unique: dict[tuple[str, str], dict[str, object]] = {}
    for row in rows:
        unique.setdefault((row["model_key"], row["id"]), row)
    return unique


def summarize() -> tuple[list[dict[str, object]], dict[tuple[str, str], dict[str, object]]]:
    unique = load_unique_results()
    summaries = []
    for key in ORDER:
        rows = [row for (model, _), row in unique.items() if model == key]
        if len(rows) != 77:
            raise RuntimeError(f"{key}: expected 77 unique results, found {len(rows)}")
        y = [int(row["correct"]) for row in rows]
        p = [float(row["confidence"]) for row in rows]
        accuracy = statistics.mean(y)
        mean_confidence = statistics.mean(p)
        lo, hi = wilson(sum(y), len(y))
        coverage5, threshold5, error5 = attainable_coverage(y, p, 0.05)
        item: dict[str, object] = {
            "key": key,
            "name": MODELS[key]["name"],
            "model": MODELS[key]["model"],
            "n": len(rows),
            "correct": sum(y),
            "errors": len(y) - sum(y),
            "accuracy": accuracy,
            "accuracy_ci95": [lo, hi],
            "mean_confidence": mean_confidence,
            "confidence_gap": mean_confidence - accuracy,
            "brier": statistics.mean((a - b) ** 2 for a, b in zip(p, y)),
            "ece10": ece(y, p),
            "auroc": float(roc_auc_score(y, p)),
            "coverage_at_5pct_observed_error": coverage5,
            "threshold_at_5pct_observed_error": threshold5,
            "observed_error_at_threshold": error5,
            "cost_77": sum(float(row.get("cost") or 0) for row in rows),
            "cost_per_1000": sum(float(row.get("cost") or 0) for row in rows) / 77 * 1000,
            "input_tokens": sum(int(row.get("input_tokens") or 0) for row in rows),
            "output_tokens": sum(int(row.get("output_tokens") or 0) for row in rows),
            "reasoning_tokens": sum(int(row.get("reasoning_tokens") or 0) for row in rows),
            "median_latency_s": statistics.median(float(row["latency_s"]) for row in rows),
        }
        if key == "jev":
            item["multiclass_brier"] = statistics.mean(
                sum(
                    (float(prob) - (1 if label == row["gold"] else 0)) ** 2
                    for label, prob in row["probabilities"].items()
                )
                for row in rows
            )
        summaries.append(item)
    return summaries, unique


def pct(x: float, decimals: int = 1) -> str:
    return f"{x * 100:.{decimals}f}%"


def money(x: float) -> str:
    return f"${x:.2f}" if x >= 0.01 else f"${x:.4f}"



def humanize(label: str) -> str:
    return label.replace("_", " ").replace("?", "").strip()


def scatter_svg(summary: list[dict[str, object]]) -> str:
    """Render cost vs accuracy with a log-cost axis and clipped accuracy range."""
    width, height = 860, 430
    left, right, top, bottom = 70, 24, 28, 62
    costs = [float(row["cost_per_1000"]) for row in summary]
    accuracies = [float(row["accuracy"]) for row in summary]
    x_min = 0.05
    x_max = max(12.0, max(costs) * 1.2)
    y_min = max(0.0, math.floor((min(accuracies) - 0.03) * 100) / 100)
    y_max = min(1.0, math.ceil((max(accuracies) + 0.025) * 100) / 100)
    inner_w, inner_h = width - left - right, height - top - bottom

    def x(value: float) -> float:
        lo, hi = math.log10(x_min), math.log10(x_max)
        return left + (math.log10(value) - lo) / (hi - lo) * inner_w

    def y(value: float) -> float:
        return top + (y_max - value) / (y_max - y_min) * inner_h

    x_ticks = [v for v in (0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10) if x_min <= v <= x_max]
    y_ticks = [
        v / 100
        for v in range(
            math.ceil(y_min * 100 / 5) * 5,
            math.floor(y_max * 100 / 5) * 5 + 1,
            5,
        )
    ]
    offsets = {
        "jev": (10, 18),
        "deepseek": (10, -10),
        "openai_decisions": (-10, 12),
        "clef": (10, -10),
        "clef_flash": (10, 18),
        "luna": (10, -10),
        "luna6": (10, 18),
        "sol": (10, 18),
        "gemini": (10, -10),
        "sonnet": (10, 18),
        "opus": (10, 18),
        "astra": (-10, -10),
        "fable": (-10, 18),
    }
    parts = [
        f'<svg class="scatter-chart" viewBox="0 0 {width} {height}" role="img" aria-labelledby="scatter-title scatter-desc">',
        '<title id="scatter-title">Cost versus classification accuracy</title>',
        (
            f'<desc id="scatter-desc">{len(summary)} models. Cost per thousand requests uses a logarithmic '
            'horizontal scale. Accuracy is shown on a clipped vertical range.</desc>'
        ),
    ]
    for tick in y_ticks:
        yy = y(tick)
        parts.append(
            f'<line class="scatter-grid" x1="{left}" y1="{yy:.1f}" x2="{width-right}" y2="{yy:.1f}"/>'
        )
        parts.append(
            f'<text class="scatter-tick" x="{left-10}" y="{yy+4:.1f}" text-anchor="end">{tick*100:.0f}%</text>'
        )
    for tick in x_ticks:
        xx = x(tick)
        label = "$" + f"{tick:g}"
        parts.append(
            f'<line class="scatter-grid x-grid" x1="{xx:.1f}" y1="{top}" x2="{xx:.1f}" y2="{height-bottom}"/>'
        )
        parts.append(
            f'<text class="scatter-tick" x="{xx:.1f}" y="{height-bottom+25}" text-anchor="middle">{label}</text>'
        )
    parts.extend(
        [
            f'<line class="scatter-axis" x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}"/>',
            f'<line class="scatter-axis" x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}"/>',
            (
                f'<text class="scatter-axis-label" x="{left+inner_w/2:.1f}" y="{height-12}" '
                'text-anchor="middle">Cost per 1,000 classifications · USD · log scale</text>'
            ),
            (
                f'<text class="scatter-axis-label" transform="translate(17 {top+inner_h/2:.1f}) rotate(-90)" '
                'text-anchor="middle">Accuracy on 77 cases</text>'
            ),
        ]
    )
    for row in summary:
        key = str(row["key"])
        xx, yy = x(float(row["cost_per_1000"])), y(float(row["accuracy"]))
        dx, dy = offsets.get(key, (10, -10))
        anchor = "end" if dx < 0 else "start"
        klass = " scatter-model-focus" if key == "clef_flash" else (" scatter-model-jev" if key == "jev" else "")
        title = (
            f'{row["name"]}: {float(row["accuracy"])*100:.1f}% accuracy, '
            f'{money(float(row["cost_per_1000"]))} per 1,000'
        )
        parts.append(
            f'<g class="scatter-model{klass}" role="button" tabindex="0" data-model="{html.escape(key)}" '
            f'aria-label="{html.escape(title)}"><title>{html.escape(title)}. Click for details.</title>'
            f'<circle cx="{xx:.1f}" cy="{yy:.1f}" r="7"/>'
            f'<text x="{xx+dx:.1f}" y="{yy+dy:.1f}" text-anchor="{anchor}">{html.escape(str(row["name"]))}</text></g>'
        )
    parts.append("</svg>")
    return "".join(parts)

def render_html(summary: list[dict[str, object]], unique: dict[tuple[str, str], dict[str, object]]) -> str:
    by_key = {row["key"]: row for row in summary}
    ranked = sorted(summary, key=lambda row: (-float(row["accuracy"]), float(row["cost_77"])))
    astra, jev, luna6, openai_decisions, clef, clef_flash = (
        by_key[k] for k in ("astra", "jev", "luna6", "openai_decisions", "clef", "clef_flash")
    )
    model_count = len(summary)
    all_case_ids = sorted({case_id for _, case_id in unique})
    all_miss = sum(not any(unique[(key, case_id)]["correct"] for key in ORDER) for case_id in all_case_ids)
    clef_only_vs_astra = sum(
        unique[("clef", case_id)]["correct"] and not unique[("astra", case_id)]["correct"]
        for case_id in all_case_ids
    )
    astra_only_vs_clef = sum(
        unique[("astra", case_id)]["correct"] and not unique[("clef", case_id)]["correct"]
        for case_id in all_case_ids
    )
    flash_cost_advantage = float(astra["cost_per_1000"]) / float(clef_flash["cost_per_1000"])
    decisions_speedup = float(luna6["median_latency_s"]) / float(openai_decisions["median_latency_s"])
    scatter = scatter_svg(summary)
    cases = list(csv.DictReader((DATA / "cases.csv").open()))
    table_keys = [str(row["key"]) for row in ranked]
    result_head = "".join(
        f'<th scope="col">{html.escape(str(MODELS[key]["name"]))}</th>' for key in table_keys
    )
    result_rows = []
    for case in cases:
        cells = []
        for key in table_keys:
            row = unique[(key, case["id"])]
            prediction = humanize(str(row["prediction"]))
            if row["correct"]:
                cells.append(
                    f'<td class="result-cell correct"><span aria-hidden="true">✓</span> '
                    f'{html.escape(prediction)}</td>'
                )
            else:
                expected = humanize(case["category"])
                tooltip = f"Expected: {expected}"
                cells.append(
                    f'<td class="result-cell wrong" tabindex="0" title="{html.escape(tooltip)}" '
                    f'aria-label="{html.escape(prediction)}. Wrong. {html.escape(tooltip)}">'
                    f'<span aria-hidden="true">✕</span> {html.escape(prediction)}</td>'
                )
        result_rows.append(
            f'<tr><th scope="row" class="request-cell">{html.escape(case["text"])}</th>'
            + "".join(cells)
            + "</tr>"
        )
    results_matrix = "".join(result_rows)
    model_data = json.dumps({str(row["key"]): row for row in summary}, separators=(",", ":"))

    bars = "".join(
        f'''<div class="bar-row">
          <div class="bar-label"><strong>{html.escape(str(row["name"]))}</strong><span>{int(row["correct"])}/77</span></div>
          <div class="bar-track"><span style="width:{float(row["accuracy"]) * 100:.1f}%"></span></div>
          <div class="bar-value">{pct(float(row["accuracy"]))}</div>
        </div>'''
        for row in ranked
    )

    business_rows = "".join(
        f'''<tr>
          <td><strong>{html.escape(str(row["name"]))}</strong></td>
          <td>{pct(float(row["accuracy"]))}</td>
          <td>{float(row["errors"]) / 77 * 100:.1f}</td>
          <td>{money(float(row["cost_per_1000"]))}</td>
          <td>{float(row["median_latency_s"]):.2f}s</td>
        </tr>'''
        for row in ranked
    )

    calibration_rows = "".join(
        f'''<tr>
          <td>{html.escape(str(row["name"]))}</td>
          <td>{pct(float(row["accuracy"]))}</td>
          <td>{pct(float(row["mean_confidence"]))}</td>
          <td>{float(row["confidence_gap"]) * 100:+.1f} pp</td>
          <td>{float(row["brier"]):.3f}</td>
          <td>{float(row["ece10"]):.3f}</td>
          <td>{float(row["auroc"]):.3f}</td>
        </tr>'''
        for row in ranked
    )

    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Decision models vs frontier LLMs: BANKING77 pilot</title>
<meta name="description" content="A 77-case paired pilot comparing {model_count} decision-model and LLM systems on banking-support classification, confidence, speed and cost.">
<style>
:root{{--ink:#17212b;--muted:#66717c;--line:#dce2e7;--soft:#f5f7f8;--paper:#fff;--accent:#1769aa;--good:#147a55;--warn:#a85c00;--bad:#b42318;color-scheme:light}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}}main{{max-width:980px;margin:auto;padding:clamp(28px,6vw,72px) 22px 80px}}h1,h2,h3{{line-height:1.12;text-wrap:balance}}h1{{font-size:clamp(2.2rem,6vw,4.5rem);letter-spacing:-.045em;margin:.12em 0 .25em}}h2{{font-size:clamp(1.45rem,3vw,2rem);margin:2.2em 0 .55em}}p{{max-width:760px}}.eyebrow{{font-size:.75rem;font-weight:750;letter-spacing:.09em;text-transform:uppercase;color:var(--accent)}}.deck{{font-size:clamp(1.1rem,2.2vw,1.35rem);color:#384550;margin-bottom:2rem}}.hero{{border-bottom:1px solid var(--line);padding-bottom:32px}}.callout{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:24px 0}}.card{{background:var(--soft);padding:18px;border-top:3px solid var(--accent)}}.card b{{display:block;font-size:1.65rem;line-height:1.1;margin:.15em 0 .3em}}.card span{{color:var(--muted);font-size:.85rem}}.takeaway{{border-left:4px solid var(--good);padding:3px 0 3px 18px;margin:24px 0;font-size:1.06rem}}.bar-chart{{display:grid;gap:11px;margin:24px 0 30px}}.bar-row{{display:grid;grid-template-columns:190px 1fr 58px;gap:12px;align-items:center}}.bar-label{{display:flex;justify-content:space-between;gap:8px;font-size:.82rem}}.bar-label span{{color:var(--muted)}}.bar-track{{height:16px;background:#edf1f3;overflow:hidden}}.bar-track span{{display:block;height:100%;background:var(--accent)}}.bar-value{{font-variant-numeric:tabular-nums;font-weight:700;text-align:right}}.table-wrap{{overflow-x:auto;border:1px solid var(--line)}}table{{border-collapse:collapse;width:100%;font-size:.88rem}}th,td{{padding:10px 12px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}}th:first-child,td:first-child{{text-align:left}}th{{color:var(--muted);font-size:.72rem;text-transform:uppercase;letter-spacing:.035em;background:var(--soft)}}tbody tr:last-child td{{border-bottom:0}}.note{{color:var(--muted);font-size:.84rem}}.decision{{background:#eef7f3;border:1px solid #cce7db;padding:20px 22px;margin:28px 0}}.decision strong{{font-size:1.08rem}}details{{border-top:1px solid var(--line);padding:13px 0}}summary{{cursor:pointer;font-weight:700}}code{{background:var(--soft);padding:.1em .3em}}a{{color:var(--accent)}}footer{{border-top:1px solid var(--line);margin-top:42px;padding-top:18px;color:var(--muted);font-size:.8rem}}

.scatter-shell{{margin:22px 0 10px;border:1px solid var(--line);background:var(--paper);padding:14px 10px 4px}}
.scatter-scroll{{overflow-x:auto;overscroll-behavior-inline:contain}}
.scatter-chart{{display:block;width:100%;min-width:700px;height:auto}}
.scatter-grid{{stroke:#e4e9ed;stroke-width:1}}.scatter-grid.x-grid{{opacity:.6}}.scatter-axis{{stroke:#94a0aa;stroke-width:1.2}}
.scatter-tick{{fill:var(--muted);font-size:11px}}.scatter-axis-label{{fill:var(--muted);font-size:12px;font-weight:650}}
.scatter-model{{cursor:pointer;outline:none}}.scatter-model circle{{fill:var(--accent);stroke:var(--paper);stroke-width:2}}
.scatter-model text{{fill:var(--ink);font-size:12px;font-weight:650;pointer-events:none}}
.scatter-model-focus circle{{fill:var(--good)}}.scatter-model-jev circle{{fill:var(--warn)}}.scatter-model:hover circle,.scatter-model:focus-visible circle{{stroke:var(--ink);stroke-width:3}}
.scatter-caption{{display:flex;gap:12px;justify-content:space-between;align-items:flex-start;color:var(--muted);font-size:.8rem;margin:8px 2px 18px}}
.scatter-caption strong{{color:var(--ink)}}.mobile-scroll{{display:none}}
dialog{{width:min(680px,calc(100vw - 32px));border:0;padding:0;box-shadow:0 22px 70px #17212b44;background:var(--paper);color:var(--ink)}}
dialog::backdrop{{background:#17212b99}}.modal-inner{{padding:24px}}.modal-head{{display:flex;justify-content:space-between;gap:18px;align-items:flex-start;border-bottom:1px solid var(--line);padding-bottom:14px}}
.modal-head h3{{font-size:1.5rem;margin:0}}.modal-close{{border:1px solid var(--line);background:var(--paper);font:inherit;width:40px;height:40px;cursor:pointer}}
.modal-close:hover,.modal-close:focus-visible{{background:var(--soft);outline:2px solid var(--accent);outline-offset:2px}}
.modal-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:18px}}.modal-stat{{background:var(--soft);padding:12px}}
.modal-stat span{{display:block;color:var(--muted);font-size:.72rem}}.modal-stat strong{{display:block;font-size:1.05rem;margin-top:2px}}
.result-details{{margin-top:14px}}.result-details>summary{{padding:8px 0}}.results-wrap{{width:calc(100vw - 32px);max-height:72vh;overflow:auto;border:1px solid var(--line);margin-top:12px;margin-left:calc(50% - 50vw + 16px)}}
.results-table{{border-collapse:separate;border-spacing:0;width:max-content;min-width:100%;font-size:.76rem}}
.results-table th,.results-table td{{border-right:1px solid var(--line);border-bottom:1px solid var(--line);padding:8px 9px;vertical-align:top}}
.results-table thead th{{position:sticky;top:0;z-index:3;background:var(--soft);text-align:left;white-space:normal;min-width:145px;max-width:165px}}
.results-table .request-cell{{position:sticky;left:0;z-index:2;min-width:300px;max-width:360px;white-space:normal;text-align:left;background:var(--paper);font-weight:500;line-height:1.35}}
.results-table thead .request-cell{{z-index:4;background:var(--soft);font-weight:700}}
.result-cell{{min-width:145px;max-width:180px;white-space:normal;text-align:left;line-height:1.25}}
.result-cell.correct{{background:#edf8f3;color:#0b6444}}.result-cell.wrong{{background:#fff0ef;color:var(--bad);cursor:help}}
.result-cell:focus-visible{{outline:3px solid var(--accent);outline-offset:-3px}}
.matrix-note{{color:var(--muted);font-size:.8rem;margin:5px 0 0}}

@media(max-width:700px){{.callout{{grid-template-columns:1fr}}.bar-row{{grid-template-columns:128px 1fr 54px}}.bar-label span{{display:none}}.mobile-scroll{{display:inline}}.modal-grid{{grid-template-columns:repeat(2,1fr)}}}}
</style>
</head>
<body><main>
<section class="hero">
<div class="eyebrow">BANKING77 · 77-case paired pilot · updated 7 October 2026</div>
<h1>The specialist wins.<br>But not every specialist.</h1>
<p class="deck">{model_count} AI systems classified exactly the same banking-support requests. Cloudflare's Clef and Clef-flash beat every general-purpose model here, while Jev and OpenAI Decisions did not. <strong>A decision-model architecture can be excellent—but the implementation matters more than the label.</strong></p>
<div class="callout">
  <div class="card"><span>Highest observed accuracy</span><b>{pct(float(clef["accuracy"]))}</b><span>Clef · {int(clef["correct"])} of 77 correct</span></div>
  <div class="card"><span>Best value near the top</span><b>{pct(float(clef_flash["accuracy"]))}</b><span>Clef-flash · {money(float(clef_flash["cost_per_1000"]))} per 1,000</span></div>
  <div class="card"><span>Frontier baseline</span><b>{pct(float(astra["accuracy"]))}</b><span>GPT-6 Astra · {money(float(astra["cost_per_1000"]))} per 1,000</span></div>
</div>
<p class="takeaway"><strong>Clef-flash is the practical winner on this pilot.</strong> It got <strong>{int(clef_flash["correct"])}/77</strong> right versus Astra's {int(astra["correct"])}/77, at about <strong>{flash_cost_advantage:.0f}× lower list-equivalent inference cost</strong>. Full Clef gained one more correct case; against Astra, Clef got {clef_only_vs_astra} cases right that Astra missed, while Astra got {astra_only_vs_clef} that Clef missed.</p>
</section>

<section>
<h2>What happened?</h2>
<p>We selected one request from each of BANKING77's 77 support categories. Every model saw the same request and the same 77 allowed labels. There was no LLM judge: a prediction counted only when it exactly matched the dataset's gold routing label.</p>
<div class="bar-chart" aria-label="Classification accuracy by model">{bars}</div>
<p class="note"><strong>Clef and Clef-flash are effectively tied here:</strong> 74/77 versus 73/77. Clef's advantage over Astra is more striking in the paired cases: Clef got {clef_only_vs_astra} requests right that Astra missed, and Astra got {astra_only_vs_clef} that Clef missed. This is still only a 77-case pilot, so treat the exact percentages as directional rather than production SLAs.</p>
</section>

<section>
<h2>Model price is rarely the business bottleneck</h2>
<p>The chart puts quality and inference cost on the same page. Cost uses a log scale because the models span more than two orders of magnitude. Click any model for its details.</p>
<div class="scatter-shell"><div class="scatter-scroll">{scatter}</div></div>
<div class="scatter-caption"><span><strong>Up and left is better:</strong> more accurate and cheaper. The vertical axis is intentionally clipped to the observed range; it does not start at zero. Costs are list-equivalent for the measured token usage.</span><span class="mobile-scroll">Swipe the chart horizontally →</span></div>
<p>The table below translates the same experiment into operational units. “Errors per 100” is simply what this small pilot observed; it is not a production SLA.</p>
<div class="table-wrap"><table>
<thead><tr><th>Model</th><th>Accuracy</th><th>Errors / 100</th><th>Cost / 1,000</th><th>Median latency</th></tr></thead>
<tbody>{business_rows}</tbody>
</table></div>
<p class="note">Cost uses each system's measured token usage: OpenRouter's reported <code>usage.cost</code> for hosted LLMs/Jev, current direct OpenAI token pricing for OpenAI Decisions, and Cloudflare's listed $0.24/M and $0.09/M input-token prices for Clef and Clef-flash. Cloudflare includes a daily free Workers AI allocation, so actual billed cost can be lower. Development retries are excluded.</p>
<div class="decision"><strong>Business implication:</strong> Clef-flash is unusual because it improves both axes at once: higher observed accuracy than Astra at roughly {flash_cost_advantage:.0f}× lower list-equivalent cost. Validate that dominance on your own taxonomy before standardizing—but do not assume a frontier general model is automatically the safest choice for a bounded decision.</div>
</section>

<section>
<h2>Confidence is not a guarantee</h2>
<p>A useful confidence score should behave like a probability. Clef-flash was <strong>{pct(float(clef_flash["mean_confidence"]))} confident on average and {pct(float(clef_flash["accuracy"]))} correct</strong>; Clef was {pct(float(clef["mean_confidence"]))} confident at {pct(float(clef["accuracy"]))} accuracy. Both were slightly underconfident rather than aggressively overconfident.</p>
<p>More importantly, their confidence ranked risk extremely well: Clef-flash's AUROC was {float(clef_flash["auroc"]):.3f} and Clef's was {float(clef["auroc"]):.3f}. Their binary Brier scores ({float(clef_flash["brier"]):.3f} and {float(clef["brier"]):.3f}) were the best in this pilot. By contrast, Jev and OpenAI Decisions remained materially overconfident.</p>
<div class="decision"><strong>Business implication:</strong> never turn “confidence ≥ 95%” directly into “no human review.” Learn that threshold from historical cases with known answers, freeze it, and validate it on untouched cases.</div>
</section>

<section>
<h2>What should a company do with decision models?</h2>
<p><strong>Benchmark the implementation, not the architecture label.</strong> The same broad decision-model idea spans {pct(float(jev["accuracy"]))} accuracy for Jev, {pct(float(openai_decisions["accuracy"]))} for OpenAI Decisions, {pct(float(clef_flash["accuracy"]))} for Clef-flash, and {pct(float(clef["accuracy"]))} for Clef on these exact cases.</p>
<p><strong>For this task, Clef-flash is the default choice.</strong> Full Clef bought one additional correct answer, but cost more and was slower. OpenAI Decisions tells a different story: using GPT-6 Luna through the typed Decisions API produced 61/77 correct versus 60/77 through chat—essentially no quality change—but cut observed median latency from {float(luna6["median_latency_s"]):.2f}s to {float(openai_decisions["median_latency_s"]):.2f}s, about {decisions_speedup:.1f}× faster. Here, its value is structure and speed, not an accuracy leap.</p>
<p>Also note the dataset itself is imperfect for this label-name-only setup: <strong>{all_miss} of 77 requests were missed by all {model_count} systems.</strong> Several depend on fine distinctions that are clearer with a routing guide than with label names alone. Production evaluation should include the real policy or taxonomy definitions users expect the model to follow.</p>
</section>

<section>
<h2>Technical detail</h2>
<details class="result-details"><summary>See all 77 classification results</summary>
<p class="matrix-note">Each row is the actual customer request; each model column shows its predicted label. ✓ green cells are correct. ✕ red cells are wrong; hover them to see the expected label. Scroll horizontally to compare models.</p>
<div class="results-wrap"><table class="results-table">
<thead><tr><th scope="col" class="request-cell">Customer request</th>{result_head}</tr></thead>
<tbody>{results_matrix}</tbody>
</table></div>
</details>
<details><summary>Calibration and ranking metrics</summary>
<p class="note">Brier and ECE are lower-is-better probability-quality measures. AUROC asks only whether confidence ranks correct cases above incorrect ones; higher is better.</p>
<div class="table-wrap"><table><thead><tr><th>Model</th><th>Accuracy</th><th>Mean confidence</th><th>Gap</th><th>Brier ↓</th><th>ECE ↓</th><th>AUROC ↑</th></tr></thead><tbody>{calibration_rows}</tbody></table></div>
</details>
<details><summary>Methodology and reproducibility</summary>
<p>One deterministic frozen case per BANKING77 class, 77 total. Ordinary chat models receive the 77 labels in the prompt and return one label plus a 0–100 probability of being exactly correct. Decision-model systems receive the same 77 label values plus the same humanized label descriptions through their native typed-choice interface: Jev via OpenRouter Decisions, GPT-6 Luna via OpenAI's direct Decisions API, and Clef/Clef-flash via Cloudflare Workers AI. For all decision models, the chosen label's probability is the comparable confidence score.</p>
<p class="note">Latency is observed end-to-end from this machine, not model-only latency; provider and network paths differ. Reasoning was disabled for GPT-5.6 Luna, GPT-6 Luna, GPT-5.6 Sol and DeepSeek; low reasoning was requested for Astra, Opus, Fable, Gemini and Sonnet.</p>
<p>The runner is resumable: an existing <code>(model, case)</code> result is skipped. Re-running <code>uv run run.py --dry-run</code> should report zero pending calls.</p>
<p class="note">Current interface/pricing references: <a href="https://developers.openai.com/api/reference/resources/decisions/methods/create">OpenAI Decisions API</a> · <a href="https://developers.openai.com/api/docs/pricing">OpenAI pricing</a> · <a href="https://developers.cloudflare.com/ai/models/%40cf/cloudflare/clef/">Clef</a> · <a href="https://developers.cloudflare.com/ai/models/%40cf/cloudflare/clef-flash/">Clef-flash</a>.</p>
</details>
<details><summary>Files</summary>
<p><a href="data/cases.csv">Frozen 77 cases</a> · <a href="data/results.jsonl">Raw results</a> · <a href="summary.json">Computed summary</a> · <a href="models.json">Model configuration</a> · <a href="prompt.md">Prompt</a> · <a href="run.py">Runner</a> · <a href="analyze.py">Analysis</a></p>
</details>
</section>
<footer>Observed results from 77 paired BANKING77 cases across {model_count} systems. This is a pilot, not a production model-selection benchmark.</footer>
</main>
<dialog id="model-dialog" aria-labelledby="model-dialog-title">
  <div class="modal-inner">
    <div class="modal-head">
      <div><div class="eyebrow">Model detail</div><h3 id="model-dialog-title" data-detail="name"></h3><p class="note" data-detail="model"></p></div>
      <form method="dialog"><button class="modal-close" aria-label="Close model details">×</button></form>
    </div>
    <div class="modal-grid">
      <div class="modal-stat"><span>Accuracy</span><strong data-detail="accuracy"></strong></div>
      <div class="modal-stat"><span>Correct</span><strong data-detail="correct"></strong></div>
      <div class="modal-stat"><span>Cost / 1,000</span><strong data-detail="cost1000"></strong></div>
      <div class="modal-stat"><span>Median latency</span><strong data-detail="latency"></strong></div>
      <div class="modal-stat"><span>Mean confidence</span><strong data-detail="confidence"></strong></div>
      <div class="modal-stat"><span>Confidence gap</span><strong data-detail="gap"></strong></div>
      <div class="modal-stat"><span>Brier ↓</span><strong data-detail="brier"></strong></div>
      <div class="modal-stat"><span>ECE ↓</span><strong data-detail="ece"></strong></div>
      <div class="modal-stat"><span>AUROC ↑</span><strong data-detail="auroc"></strong></div>
    </div>
    <p class="note" data-detail="tokens"></p>
  </div>
</dialog>
<script>
const modelData = {model_data};
const modelDialog = document.querySelector("#model-dialog");
const setDetail = (name, value) => {{ modelDialog.querySelector('[data-detail="' + name + '"]').textContent = value; }};
const pctValue = value => (value * 100).toFixed(1) + "%";
const moneyValue = value => value >= 0.01 ? "$" + value.toFixed(2) : "$" + value.toFixed(4);
const openModel = key => {{
  const model = modelData[key];
  setDetail("name", model.name);
  setDetail("model", model.model);
  setDetail("accuracy", pctValue(model.accuracy));
  setDetail("correct", model.correct + " / " + model.n);
  setDetail("cost1000", moneyValue(model.cost_per_1000));
  setDetail("latency", model.median_latency_s.toFixed(2) + "s");
  setDetail("confidence", pctValue(model.mean_confidence));
  setDetail("gap", (model.confidence_gap * 100 >= 0 ? "+" : "") + (model.confidence_gap * 100).toFixed(1) + " pp");
  setDetail("brier", model.brier.toFixed(3));
  setDetail("ece", model.ece10.toFixed(3));
  setDetail("auroc", model.auroc.toFixed(3));
  setDetail("tokens", model.input_tokens.toLocaleString() + " input tokens · " + model.output_tokens.toLocaleString() + " output tokens · " + model.reasoning_tokens.toLocaleString() + " reported reasoning tokens across 77 cases.");
  modelDialog.showModal();
}};
document.querySelectorAll(".scatter-model").forEach(point => {{
  point.addEventListener("click", () => openModel(point.dataset.model));
  point.addEventListener("keydown", event => {{
    if (event.key === "Enter" || event.key === " ") {{
      event.preventDefault();
      openModel(point.dataset.model);
    }}
  }});
}});
modelDialog.addEventListener("click", event => {{ if (event.target === modelDialog) modelDialog.close(); }});
</script>
</body></html>'''


def main() -> None:
    summary, unique = summarize()
    (ROOT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    fields = [
        "model_key", "model_requested", "model_returned", "id", "gold", "prediction", "correct",
        "confidence", "reported_confidence", "input_tokens", "output_tokens", "reasoning_tokens", "cost",
        "latency_s", "generation_id", "provider",
    ]
    with (DATA / "results.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for key in ORDER:
            for case_id in sorted(case for model, case in unique if model == key):
                row = unique[(key, case_id)]
                writer.writerow({field: row.get(field) for field in fields})
    (ROOT / "index.html").write_text(render_html(summary, unique))
    print("Wrote summary.json, data/results.csv, index.html")


if __name__ == "__main__":
    main()
