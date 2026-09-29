#!/usr/bin/env python3
from __future__ import annotations
import collections, json, math, statistics
from html import escape
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DATA=ROOT/"data"
MODELS=json.loads((ROOT/"models.json").read_text())
ORDER=list(MODELS)
PARAMETERS={
    "luna": {"label":"Undisclosed","total":None,"active":None},
    "mimov26": {"label":"309B total (15B active)","total":309,"active":15},
    "glm53flash": {"label":"320B total (18B active)","total":320,"active":18},
    "ling3fin": {"label":"124B total (5.1B active)","total":124,"active":5.1},
    "qwen27b": {"label":"27B","total":27,"active":27},
    "nemotron3super": {"label":"120B total (12B active)","total":120,"active":12},
    "deepseekv41": {"label":"552B total (8B input / 16B output active)","total":552,"active":16},
    "gemma31b": {"label":"31B","total":31,"active":31},
    "ministral8b": {"label":"8B","total":8,"active":8},
    "qwen9b": {"label":"9B","total":9,"active":9},
    "granite8b": {"label":"8B","total":8,"active":8},
}

def size_tier(key):
    total=PARAMETERS[key]["total"]
    return "Unknown" if total is None else "Large" if total>=100 else "Medium" if total>=20 else "Small"

RDYLGN=["#a50026","#d73027","#f46d43","#fdae61","#fee08b","#ffffbf","#d9ef8b","#a6d96a","#66bd63","#1a9850","#006837"]

def accuracy_colors(value):
    position=max(0,min(1,value))*(len(RDYLGN)-1)
    index=min(int(position),len(RDYLGN)-2)
    fraction=position-index
    colors=[tuple(int(color[i:i+2],16) for i in (1,3,5)) for color in RDYLGN[index:index+2]]
    rgb=tuple(round(a+(b-a)*fraction) for a,b in zip(*colors))
    background="#"+"".join(f"{channel:02x}" for channel in rgb)
    def luminance(color):
        channels=[int(color[i:i+2],16)/255 for i in (1,3,5)]
        linear=[channel/12.92 if channel<=.04045 else ((channel+.055)/1.055)**2.4 for channel in channels]
        return sum(channel*weight for channel,weight in zip(linear,(.2126,.7152,.0722)))
    light,dark=luminance("#ffffff"),luminance("#000000")
    fill=luminance(background)
    contrast=lambda foreground,background:(max(foreground,background)+.05)/(min(foreground,background)+.05)
    foreground="#ffffff" if contrast(light,fill)>=contrast(dark,fill) else "#000000"
    return background,foreground

def jsonl(path):
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]

def p90(xs):
    xs=sorted(xs); return xs[math.ceil(.9*len(xs))-1]

def brier(rs):
    return statistics.mean((r["confidence"]-r["correct"])**2 for r in rs)

def ece(rs):
    out=0
    for i in range(10):
        lo,hi=i/10,(i+1)/10
        b=[r for r in rs if lo<=r["confidence"]<hi or (i==9 and r["confidence"]==1)]
        if b:
            out += len(b)/len(rs)*abs(statistics.mean(r["confidence"] for r in b)-statistics.mean(r["correct"] for r in b))
    return out

def auroc(rs):
    pos=[r["confidence"] for r in rs if r["correct"]]
    neg=[r["confidence"] for r in rs if not r["correct"]]
    return sum(1 if p>n else .5 if p==n else 0 for p in pos for n in neg)/(len(pos)*len(neg))

def grouped(rs,key):
    g=collections.defaultdict(list)
    for r in rs: g[str(r[key])].append(r)
    return {k:{"n":len(v),"accuracy":sum(x["correct"] for x in v)/len(v)} for k,v in sorted(g.items())}

def route(rs,luna):
    ordered=sorted(rs,key=lambda r:(-r["confidence"],r["id"]))
    out=[]
    for coverage in [.25,.5,.75,1]:
        n=round(100*coverage); keep={r["id"] for r in ordered[:n]}
        correct=sum(r["correct"] if r["id"] in keep else luna[r["id"]]["correct"] for r in rs)
        extra=sum((luna[r["id"]].get("cost") or 0) for r in rs if r["id"] not in keep)
        out.append({"coverage":coverage,"accuracy":correct/100,"cost":sum(r.get("cost") or 0 for r in rs)+extra,
                    "cutoff":ordered[n-1]["confidence"] if n else None})
    return out

def pct(x): return f"{100*x:.0f}%"

rows=[r for r in jsonl(DATA/"results.jsonl") if r.get("status")=="ok"]
assert len(rows)==1100, len(rows)
by=collections.defaultdict(list)
for r in rows: by[r["model_key"]].append(r)
luna={r["id"]:r for r in by["luna"]}
summary={"models":{}}
for k in ORDER:
    rs=by[k]; wrong=[r for r in rs if not r["correct"]]; right=[r for r in rs if r["correct"]]
    actual_cost=sum(r.get("cost") or 0 for r in rs)
    paid=MODELS[k].get("paid_equivalent_pricing")
    paid_cost=(sum(
        (r.get("input_tokens") or 0)*paid["input_per_m"]/1_000_000
        +(r.get("output_tokens") or 0)*paid["output_per_m"]/1_000_000
        for r in rs
    ) if paid else None)
    by_op=grouped(rs,"root_op")
    summary["models"][k]={
      "name":MODELS[k]["name"],"tier":MODELS[k]["tier"],"model_id":MODELS[k]["model"],
      "family":MODELS[k].get("family",MODELS[k]["name"].split()[0]),
      "category":MODELS[k].get("category",MODELS[k]["tier"]),
      "parameters":PARAMETERS[k],"size_tier":size_tier(k),
      "provider":sorted({r["provider"] for r in rs}),"quantization":MODELS[k].get("hosted_quantization","unknown"),
      "accuracy":sum(r["correct"] for r in rs)/100,
      "cost":actual_cost,"chart_cost":actual_cost if actual_cost>0 else paid_cost,
      "cost_basis":"measured" if actual_cost>0 else "paid-equivalent","cost_note":MODELS[k].get("cost_note"),
      "median_latency":statistics.median(r["latency_s"] for r in rs),"p90_latency":p90([r["latency_s"] for r in rs]),
      "brier":brier(rs),"ece":ece(rs),"auroc":auroc(rs),
      "mean_conf_correct":statistics.mean(r["confidence"] for r in right),
      "mean_conf_wrong":statistics.mean(r["confidence"] for r in wrong),
      "wrong90":sum(r["confidence"]>=.9 for r in wrong),
      "reasoning_required":bool(MODELS[k].get("reasoning_required")),
      "reasoning_tokens":sum(r.get("reasoning_tokens") or 0 for r in rs),
      "retry_rows":sum(r.get("attempts",1)>1 for r in rs),
      "by_op":by_op,"by_steps":grouped(rs,"num_steps"),
      "routing":[] if k=="luna" else route(rs,luna),
      "oracle_hybrid":None if k=="luna" else (
          sum(r["correct"] for r in rs)+sum(luna[r["id"]]["correct"] for r in rs if not r["correct"])
      )/100
    }

ORDER=sorted(ORDER,key=lambda k:(-summary["models"][k]["accuracy"],summary["models"][k]["chart_cost"]))
DISPLAY_ORDER=[k for k in ORDER if k!="glm53flash"]
cases={c["id"]:c for c in jsonl(DATA/"cases.jsonl")}
for k in ORDER:
    s=summary["models"][k]
    ranked_ops=sorted(s["by_op"].items(),key=lambda item:(-item[1]["accuracy"],item[0]))
    s["best_ops"]=[{"name":name,**vals} for name,vals in ranked_ops[:2]]
    s["worst_ops"]=[{"name":name,**vals} for name,vals in ranked_ops[-2:]]
    errs=sorted((r for r in by[k] if not r["correct"]),key=lambda r:(-r["confidence"],-r["num_steps"],r["id"]))[:3]
    s["errors"]=[{
      "id":r["id"],"question":cases[r["id"]]["question"],"gold":str(r["gold"]),
      "answer":str(r["answer"]),"confidence":r["reported_confidence"],
      "root_op":r["root_op"],"num_steps":r["num_steps"]
    } for r in errs]

cost_order=sorted(ORDER,key=lambda k:(summary["models"][k]["chart_cost"],-summary["models"][k]["accuracy"]))
frontier=[]; best_so_far=-1
for k in cost_order:
    if summary["models"][k]["accuracy"]>best_so_far:
        frontier.append(k); best_so_far=summary["models"][k]["accuracy"]
summary["frontier"]=frontier
visible_frontier=[]; best_so_far=-1
for k in sorted(DISPLAY_ORDER,key=lambda k:(summary["models"][k]["chart_cost"],-summary["models"][k]["accuracy"])):
    if summary["models"][k]["accuracy"]>best_so_far:
        visible_frontier.append(k); best_so_far=summary["models"][k]["accuracy"]
summary["display_frontier"]=visible_frontier

groups=collections.defaultdict(list)
for r in rows: groups[r["id"]].append(r)
summary["all_wrong"]=[cid for cid,rs in groups.items() if all(not r["correct"] for r in rs)]
summary["luna_wrong_local_right"]=[]
for cid,rs in groups.items():
    d={r["model_key"]:r for r in rs}
    winners=[k for k in ORDER if k!="luna" and d[k]["correct"]]
    if not d["luna"]["correct"] and winners:
        summary["luna_wrong_local_right"].append({"id":cid,"gold":d["luna"]["gold"],"winners":winners})
(DATA/"summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")

table=""
for k in DISPLAY_ORDER:
    s=summary["models"][k]
    badge=" <span class='badge'>frontier</span>" if k in summary["display_frontier"] else ""
    cost=f"{s['chart_cost']*100:.2f}¢"+("*" if s["cost_basis"]=="paid-equivalent" else "")
    reasoning="low*" if s["reasoning_required"] else "off"
    params=PARAMETERS[k]
    params_sort=params["total"] if params["total"] is not None else 1_000_000_000_000
    table += (
      f"<tr><td data-sort='{escape(s['name'].casefold())}'><button class='model-link' data-model='{k}'>{escape(s['name'])}</button>{badge}"
      f"<br><small>{escape(s['family'])} · {escape(s['quantization'])}</small></td>"
      f"<td data-sort='{params_sort}' title='Size tier: {size_tier(k)}'>{escape(params['label'])}</td>"
      f"<td data-sort='{s['accuracy']}'>{pct(s['accuracy'])}</td><td data-sort='{s['chart_cost']}'>{cost}</td>"
      f"<td data-sort='{s['median_latency']}'>{s['median_latency']:.2f}s</td>"
      f"<td data-sort='{s['p90_latency']}'>{s['p90_latency']:.2f}s</td><td data-sort='{s['auroc']}'>{s['auroc']:.2f}</td>"
      f"<td data-sort='{s['wrong90']}'>{s['wrong90']}</td>"
      f"<td data-sort='{reasoning}'>{reasoning}</td></tr>"
    )

ops=["add","subtract","multiply","divide"]
operation_headers="".join(f"<th>{escape(op.title())}</th>" for op in ops)
oprows=""
for k in DISPLAY_ORDER:
    model=summary["models"][k]
    cells=[f"<td data-sort='{escape(model['name'].casefold())}'><button class='model-link' data-model='{k}'>{escape(model['name'])}</button></td>"]
    for op in ops:
        d=summary["models"][k]["by_op"].get(op)
        if d:
            background,foreground=accuracy_colors(d["accuracy"])
            cells.append(f"<td data-sort='{d['accuracy']}' title='{op.title()} · {pct(d['accuracy'])}' style='background:{background};color:{foreground}'>{pct(d['accuracy'])}</td>")
        else:
            cells.append(f"<td data-sort='—'>{'—'}</td>")
    oprows+="<tr>"+"".join(cells)+"</tr>"

steprows=""
for step in ["1","2","3","4","5"]:
    if not any(step in summary["models"][k]["by_steps"] for k in DISPLAY_ORDER): continue
    cells=[f"<td><b>{step} step{'s' if step!='1' else ''}</b></td>"]; n=0
    for k in DISPLAY_ORDER:
        d=summary["models"][k]["by_steps"].get(step)
        n=d["n"] if d else n; cells.append(f"<td>{pct(d['accuracy']) if d else '—'}</td>")
    cells.append(f"<td>{n}</td>"); steprows+="<tr>"+"".join(cells)+"</tr>"

routes=""
for k in [x for x in DISPLAY_ORDER if x!="luna"][:6]:
    s=summary["models"][k]; r=next(x for x in s["routing"] if x["coverage"]==.5)
    routes += f"<tr><td><button class='model-link' data-model='{k}'>{escape(s['name'])}</button></td><td>{pct(s['accuracy'])}</td><td>{pct(r['accuracy'])}</td><td>{pct(s['oracle_hybrid'])}</td><td>{s['auroc']:.2f}</td><td>{r['cutoff']:.0%}</td></tr>"

examples=""
for k in [x for x in DISPLAY_ORDER if x!="luna"][:4]:
    errs=summary["models"][k]["errors"]
    cards=""
    for r in errs:
        cards+=f"<div class='err'><small>{escape(r['id'])} · {escape(r['root_op'])} · {r['num_steps']} step(s)</small><b>{escape(r['question'])}</b><div>Actual: {escape(r['gold'])} · Model: {escape(r['answer'])} · Confidence: {r['confidence']}%</div></div>"
    examples+=f"<h3>{escape(MODELS[k]['name'])}</h3>{cards}"

short_names={
 "luna":"Luna","mimov26":"MiMo 2.6","glm53flash":"GLM 5.3","ling3fin":"Ling Fin",
 "qwen27b":"Qwen 27B","nemotron3super":"Nemotron","deepseekv41":"DeepSeek V4.1",
 "gemma31b":"Gemma 31B","ministral8b":"Ministral 8B","qwen9b":"Qwen 9B","granite8b":"Granite 8B"
}
chart_data=[{
 "key":k,"name":summary["models"][k]["name"],"short":short_names.get(k,summary["models"][k]["name"]),
 "accuracy":summary["models"][k]["accuracy"],"cost":summary["models"][k]["chart_cost"]*100,
 "actual_cost":summary["models"][k]["cost"]*100,"cost_basis":summary["models"][k]["cost_basis"],
 "parameters":PARAMETERS[k],"category":size_tier(k),"frontier":k in summary["display_frontier"],
 "reasoning_required":summary["models"][k]["reasoning_required"]
} for k in DISPLAY_ORDER]
chart_json=json.dumps(chart_data,ensure_ascii=False).replace("</","<"+r"\/")
models_json=json.dumps(summary["models"],ensure_ascii=False).replace("</","<"+r"\/")
frontier_json=json.dumps(summary["display_frontier"])

best=summary["models"][ORDER[0]]
best_open=next(summary["models"][k] for k in ORDER if k!="luna")
best_compact=max((summary["models"][k] for k in ORDER if summary["models"][k]["category"]=="Compact / 8B-class"),key=lambda m:m["accuracy"])
finance=summary["models"]["ling3fin"]
frontier_names=", ".join(summary["models"][k]["name"] for k in summary["frontier"])

html="""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SLM vs LLM on FinQA</title>
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='12' fill='%23315efb'/%3E%3Ctext x='32' y='39' text-anchor='middle' font-family='serif' font-size='25' fill='white'%3EFQ%3C/text%3E%3C/svg%3E">
<style>
:root{--bg:#f5f3ee;--surface:#fffdf8;--ink:#172033;--muted:#667085;--line:#d9d7d0;--grid:#e7e4dc;--accent:#315efb;--frontier:#c66a12;--shadow:0 18px 50px rgba(23,32,51,.09)}
html[data-theme="dark"]{--bg:#101319;--surface:#171b23;--ink:#edf0f7;--muted:#a2aaba;--line:#303744;--grid:#272d38;--accent:#7da2ff;--frontier:#f0a34b;--shadow:0 18px 50px rgba(0,0,0,.35)}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.48 "Avenir Next","Segoe UI",sans-serif}main{max-width:1180px;margin:auto;padding:34px 24px 80px}
h1,h2,h3{font-family:Charter,"Iowan Old Style","Palatino Linotype",serif}h1{font-size:clamp(38px,6vw,66px);line-height:1.01;letter-spacing:-.035em;margin:10px 0 16px;max-width:1050px}h2{font-size:30px;margin:52px 0 10px}
.kicker{font-size:12px;font-weight:800;letter-spacing:.15em;text-transform:uppercase;color:var(--accent)}.lead{font-size:20px;max-width:950px;color:var(--muted)}.topbar{display:flex;justify-content:space-between;gap:16px;align-items:center}
.theme-toggle{border:1px solid var(--line);background:var(--surface);color:var(--ink);border-radius:999px;padding:8px 13px;cursor:pointer}
.chart-card{position:relative;margin:30px 0 24px;background:var(--surface);border:1px solid var(--line);border-radius:18px;padding:18px 18px 12px;box-shadow:var(--shadow)}
.chart-head{display:flex;justify-content:space-between;align-items:end;gap:20px;padding:0 6px 8px}.chart-head h2{margin:0;font-size:27px}.chart-head p{margin:5px 0 0;color:var(--muted)}
.legend{display:flex;flex-wrap:wrap;align-items:center;gap:9px 15px;font-size:12px;color:var(--muted);justify-content:flex-end}.legend>span,.legend>button{display:inline-flex;align-items:center;line-height:1.2}.legend i{width:10px;height:10px;border-radius:50%;display:inline-block;margin-right:5px}.legend-filter{border:1px solid transparent;border-radius:999px;padding:4px 7px;background:transparent;color:inherit;font:inherit;cursor:pointer}.legend-filter[aria-pressed="true"]{border-color:var(--accent);background:color-mix(in srgb,var(--accent) 12%,var(--surface));color:var(--ink);font-weight:750}.legend-filter:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.legend i.legend-line{width:16px;height:0;border-top:2px dashed #d97706;border-radius:0;vertical-align:middle}
#scatter{width:100%;min-height:520px}#scatter svg{display:block;width:100%;height:auto;overflow:visible}.gridline{stroke:var(--grid);stroke-width:1}.axistext{fill:var(--ink);opacity:.72;font-size:12px}
.point-label{fill:var(--ink);font-size:12px;font-weight:650;pointer-events:none}.frontier-line{fill:none;stroke:var(--frontier);stroke-width:2;stroke-dasharray:5 6;opacity:.9}
.point circle{stroke:var(--surface);stroke-width:2}.point-hit{width:100%;height:100%;border:0;background:transparent;cursor:pointer;border-radius:50%;padding:0}.point-hit:focus-visible{outline:3px solid var(--ink);outline-offset:-3px}
.tooltip{position:fixed;z-index:20;pointer-events:none;background:#111827;color:white;border-radius:9px;padding:8px 10px;font-size:12px;box-shadow:0 8px 24px rgba(0,0,0,.25);opacity:0;max-width:250px}
.chart-note{font-size:12px;color:var(--muted);padding:0 7px 4px}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:22px 0}.card{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:17px}
.big{font-size:34px;font-weight:800;letter-spacing:-.03em}.small,small{font-size:12px;color:var(--muted)}.note{background:color-mix(in srgb,var(--accent) 8%,var(--surface));border-left:4px solid var(--accent);padding:14px 17px;margin:18px 0}.warning{border-left-color:#d97706;background:color-mix(in srgb,#d97706 9%,var(--surface))}
.scroll{overflow-x:auto;border-radius:12px;border:1px solid var(--line)}table{width:100%;border-collapse:collapse;background:var(--surface);font-size:14px}th,td{padding:10px 11px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}th{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);background:color-mix(in srgb,var(--surface) 92%,var(--ink) 8%)}th:first-child,td:first-child{text-align:left}
.sort-button{border:0;padding:0;background:none;color:inherit;font:inherit;text-transform:inherit;letter-spacing:inherit;cursor:pointer}.sort-button:focus-visible{outline:2px solid var(--accent);outline-offset:3px;border-radius:2px}th[aria-sort="ascending"] .sort-button::after{content:" ↑"}th[aria-sort="descending"] .sort-button::after{content:" ↓"}
.model-link{border:0;background:none;padding:0;color:var(--ink);font:inherit;font-weight:700;cursor:pointer;text-decoration:underline;text-decoration-color:color-mix(in srgb,var(--accent) 35%,transparent);text-underline-offset:3px}.badge{display:inline-block;margin-left:6px;padding:2px 6px;border-radius:999px;background:color-mix(in srgb,var(--frontier) 14%,var(--surface));color:var(--frontier);font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.05em}
.err{background:var(--surface);border:1px solid var(--line);padding:14px 16px;margin:8px 0;border-radius:10px}.err b{display:block;margin:5px 0}
dialog{width:min(720px,calc(100vw - 28px));border:1px solid var(--line);border-radius:16px;background:var(--surface);color:var(--ink);padding:0;box-shadow:0 30px 90px rgba(0,0,0,.35)}dialog::backdrop{background:rgba(6,10,18,.62);backdrop-filter:blur(3px)}.modal-head{display:flex;justify-content:space-between;gap:16px;padding:20px 22px;border-bottom:1px solid var(--line)}.modal-head h3{margin:0;font-size:28px}.close{border:1px solid var(--line);background:transparent;color:var(--ink);border-radius:50%;width:40px;height:40px;cursor:pointer}.modal-body{padding:20px 22px 24px}.metric-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:16px 0}.metric{border:1px solid var(--line);border-radius:10px;padding:11px}.metric b{display:block;font-size:21px}.meta{color:var(--muted);font-size:13px;overflow-wrap:anywhere}.error{border-top:1px solid var(--line);padding:10px 0}.error:first-child{border-top:0}
footer{margin-top:50px;color:var(--muted);font-size:12px}@media(max-width:980px){.chart-head{display:block}.legend{justify-content:flex-start;margin-top:10px}}@media(max-width:820px){.cards{grid-template-columns:1fr 1fr}.metric-grid{grid-template-columns:1fr 1fr}#scatter{min-height:390px}}@media(max-width:520px){main{padding:24px 14px 60px}.cards{grid-template-columns:1fr}h1{font-size:38px}}@media(prefers-reduced-motion:reduce){*{transition:none!important}}
</style></head><body><main>
<div class="topbar"><div class="kicker">PGIM · FinQA · 100 finance questions · 11 models</div><button id="theme-toggle" class="theme-toggle" type="button">Dark mode</button></div>
<h1>SLM vs LLM on FinQA</h1>
<p class="lead">Luna still leads at <strong>__BEST_ACC__</strong>, while <strong>__BEST_OPEN_NAME__</strong> reaches __BEST_OPEN_ACC__.</p>
<section class="chart-card" aria-labelledby="cq-title"><div class="chart-head"><div><h2 id="cq-title">Accuracy by model size and cost</h2><p>Accuracy vs. API cost per 100 questions. X-axis is logarithmic.</p></div><div class="legend"><span><i class="legend-line"></i>Frontier</span><button class="legend-filter" data-tier="Large" type="button" aria-pressed="false"><i style="background:#7c3aed"></i>Large (≥100B total)</button><button class="legend-filter" data-tier="Medium" type="button" aria-pressed="false"><i style="background:#2563eb"></i>Medium (20–99B)</button><button class="legend-filter" data-tier="Small" type="button" aria-pressed="false"><i style="background:#059669"></i>Small (&lt;20B)</button><button class="legend-filter" data-tier="Unknown" type="button" aria-pressed="false"><i style="background:#64748b"></i>Undisclosed</button></div></div><div id="scatter" role="group" aria-label="Cost versus accuracy scatter plot colored by total parameter count"></div><div id="tooltip" class="tooltip" aria-hidden="true"></div><p class="chart-note">Colors use published total parameter counts: Large ≥100B, Medium 20–99B, Small &lt;20B. Click a size to highlight that group; click it again to restore all points. Mixture-of-experts rows include active counts in the table. GPT-6 Luna has no published parameter count. GLM 5.3 Flash remains in the benchmark data but is omitted from this chart and the comparison tables because its endpoint required reasoning. Nemotron ran on OpenRouter's free NVIDIA endpoint; its chart cost is a paid-equivalent estimate.</p></section>
<div class="cards"><div class="card"><div class="small">Best overall</div><div class="big">__BEST_ACC__</div><strong>__BEST_NAME__</strong><br><span class="small">__BEST_COST__ / 100</span></div><div class="card"><div class="small">Best non-Luna</div><div class="big">__BEST_OPEN_ACC__</div><strong>__BEST_OPEN_NAME__</strong><br><span class="small">__BEST_OPEN_COST__ / 100</span></div><div class="card"><div class="small">Best compact model</div><div class="big">__COMPACT_ACC__</div><strong>__COMPACT_NAME__</strong></div><div class="card"><div class="small">Finance-specialized</div><div class="big">__FINANCE_ACC__</div><strong>Ling 3.0 Flash Fin</strong><br><span class="small">__FINANCE_COST__ / 100</span></div></div>
<h2>Exact benchmark results</h2><div class="scroll" tabindex="0"><table id="exact-results"><thead><tr><th aria-sort="none"><button class="sort-button" type="button">Model</button></th><th aria-sort="none"><button class="sort-button" type="button">Parameters</button></th><th aria-sort="none"><button class="sort-button" type="button">Accuracy</button></th><th aria-sort="none"><button class="sort-button" type="button">Cost / 100</button></th><th aria-sort="none"><button class="sort-button" type="button">Median</button></th><th aria-sort="none"><button class="sort-button" type="button">P90</button></th><th aria-sort="none"><button class="sort-button" type="button">Conf. AUROC</button></th><th aria-sort="none"><button class="sort-button" type="button">Wrong ≥90%</button></th><th aria-sort="none"><button class="sort-button" type="button">Reasoning</button></th></tr></thead><tbody>__TABLE__</tbody></table></div><p class="chart-note">* Nemotron cost is a paid-equivalent estimate; measured benchmark spend on the free endpoint was 0.00¢. All displayed API costs are cents per 100 questions.</p>
<h2>Confidence is still the weak link</h2><p>At 50% local coverage, each model answers its 50 highest-confidence cases and sends the rest to Luna. This is descriptive on the same 100 questions, not a production threshold.</p><div class="scroll" tabindex="0"><table id="route-results"><thead><tr><th>Model</th><th>Local only</th><th>50% confidence route</th><th>Oracle error route</th><th>Conf. AUROC</th><th>Observed cutoff</th></tr></thead><tbody>__ROUTES__</tbody></table></div><div class="note warning"><strong>Do not operationalize these cutoffs.</strong> Calibrate on separate development data and evaluate on a holdout. The oracle is only an upper bound on routing headroom.</div>
<h2>Where models differ</h2><p>Each row is a model; columns compare accuracy on addition, subtraction, multiplication, and division. Cell colors use a red–yellow–green scale.</p><div class="scroll" tabindex="0"><table id="operation-results"><thead><tr><th>Model</th>__OPERATION_HEADERS__</tr></thead><tbody>__OPROWS__</tbody></table></div>
<h2>High-confidence errors from the strongest open models</h2>__EXAMPLES__
<div class="note"><strong>Model diversity helps.</strong> Luna misses __LUNA_MISSES__ questions; at least one other model gets __LUNA_RECOVERED__ of those right. Only __ALL_WRONG__ questions defeat all 11 models.</div>
<footer>Frozen FinQA sample: 100 questions. Same evidence snippets and answer contract. API costs are displayed in cents per 100 questions; Nemotron uses a paid-equivalent estimate. See data/run_metadata.json for rate-limit/provider audit details.</footer></main>
<dialog id="model-dialog" aria-labelledby="modal-title"><div class="modal-head"><div><h3 id="modal-title"></h3><div id="modal-subtitle" class="meta"></div></div><button id="modal-close" class="close" type="button" aria-label="Close model details">×</button></div><div id="modal-body" class="modal-body"></div></dialog>
<script>
const CHART_DATA=__CHART_JSON__, MODELS=__MODELS_JSON__, FRONTIER=__FRONTIER_JSON__;
const COLORS={Large:"#7c3aed",Medium:"#2563eb",Small:"#059669",Unknown:"#64748b"};let activeTier=null;function applyTier(){document.querySelectorAll(".legend-filter").forEach(b=>b.setAttribute("aria-pressed",String(b.dataset.tier===activeTier)));document.querySelectorAll("#scatter .point").forEach(p=>p.style.opacity=activeTier===null||p.dataset.tier===activeTier?"1":".16")}
const OFF={glm53flash:[12,-15],ling3fin:[12,18],granite8b:[12,18],nemotron3super:[-12,22],qwen9b:[12,-12],gemma31b:[12,21],mimov26:[-12,-25],luna:[12,-13],deepseekv41:[12,-10],ministral8b:[12,-12],qwen27b:[-12,-13]};
function hp(){return new URLSearchParams(location.hash.replace(/^#/,""))}function sh(c){const p=hp();Object.entries(c).forEach(([k,v])=>v===null?p.delete(k):p.set(k,v));history.replaceState(null,"","#"+p)}
function theme(t){document.documentElement.dataset.theme=t;document.getElementById("theme-toggle").textContent=t==="dark"?"Light mode":"Dark mode";sh({theme:t})}document.getElementById("theme-toggle").onclick=()=>theme(document.documentElement.dataset.theme==="dark"?"light":"dark");theme(hp().get("theme")||(matchMedia("(prefers-color-scheme:dark)").matches?"dark":"light"));
function se(n,a={},t=null){const e=document.createElementNS("http://www.w3.org/2000/svg",n);Object.entries(a).forEach(([k,v])=>e.setAttribute(k,String(v)));if(t!==null)e.textContent=t;return e}function money(v){return v.toFixed(2)+"¢"}
function draw(){const host=document.getElementById("scatter"),tip=document.getElementById("tooltip");host.innerHTML="";const W=Math.max(340,Math.round(host.getBoundingClientRect().width||1040)),mobile=W<600,H=mobile?560:540,m=mobile?{l:52,r:14,t:28,b:62}:{l:82,r:38,t:35,b:70},pw=W-m.l-m.r,ph=H-m.t-m.b,c=CHART_DATA.map(d=>d.cost),lo=Math.log10(Math.min(...c)/1.25),hi=Math.log10(Math.max(...c)*1.2),x=v=>m.l+(Math.log10(v)-lo)/(hi-lo)*pw,y=v=>m.t+(1-v)*ph,svg=se("svg",{viewBox:"0 0 "+W+" "+H,"aria-label":"Higher is more accurate and farther left is cheaper"});[0,.2,.4,.6,.8,1].forEach(t=>{const yy=y(t);svg.append(se("line",{x1:m.l,x2:W-m.r,y1:yy,y2:yy,class:"gridline"}),se("text",{x:m.l-8,y:yy+4,"text-anchor":"end",class:"axistext"},Math.round(t*100)+"%"))});const ticks=(mobile?[.1,.2,.4,.6]:[.05,.1,.2,.3,.4,.5,.6,.8,1]).filter(v=>Math.log10(v)>=lo&&Math.log10(v)<=hi);ticks.forEach(t=>{const xx=x(t);svg.append(se("line",{x1:xx,x2:xx,y1:m.t,y2:H-m.b,class:"gridline"}),se("text",{x:xx,y:H-m.b+22,"text-anchor":"middle",class:"axistext"},money(t)))});svg.append(se("text",{x:m.l+pw/2,y:H-14,"text-anchor":"middle",class:"axistext"},mobile?"Cost / 100 questions (log scale)":"Cost per 100 questions (cents, log scale)"));const fp=FRONTIER.map(k=>CHART_DATA.find(d=>d.key===k)).filter(Boolean).sort((a,b)=>a.cost-b.cost);if(fp.length>1)svg.append(se("path",{d:fp.map((d,i)=>(i?"L":"M")+x(d.cost)+","+y(d.accuracy)).join(" "),class:"frontier-line"}));const pts=[...CHART_DATA].sort((a,b)=>a.cost-b.cost);pts.forEach((d,i)=>{const xx=x(d.cost),yy=y(d.accuracy),g=se("g",{class:"point","data-tier":d.category}),col=COLORS[d.category]||"#64748b";g.append(se("circle",{cx:xx,cy:yy,r:mobile?10:(d.frontier?10:8),fill:col,opacity:d.frontier?1:.88}));if(d.reasoning_required)g.append(se("text",{x:xx,y:yy+3.5,"text-anchor":"middle","font-size":"9","font-weight":"900",fill:"white","pointer-events":"none"},"R"));if(!mobile||d.frontier){const o=mobile?(d.key==="glm53flash"?[8,-12]:d.key==="mimov26"?[-8,-15]:[8,-12]):(OFF[d.key]||[12,-12]);g.append(se("text",{x:xx+o[0],y:yy+o[1],"text-anchor":o[0]<0?"end":"start",class:"point-label"},d.short))}const show=ev=>{tip.innerHTML="<b>"+d.name+"</b><br>"+Math.round(d.accuracy*100)+"% · "+money(d.cost)+"/100 · "+d.parameters.label+(d.cost_basis==="paid-equivalent"?" · paid-equivalent":"");tip.style.opacity=1;tip.style.left=Math.max(8,Math.min(innerWidth-250,(ev.clientX||xx+host.getBoundingClientRect().left)+12))+"px";tip.style.top=Math.max(8,Math.min(innerHeight-80,(ev.clientY||yy+host.getBoundingClientRect().top)+12))+"px"};svg.append(g);const fo=se("foreignObject",{x:xx-18,y:yy-18,width:36,height:36}),b=document.createElement("button");b.type="button";b.className="point-hit";b.setAttribute("aria-label",d.name+", "+Math.round(d.accuracy*100)+" percent accuracy, "+money(d.cost)+" per 100 questions, "+d.parameters.label+" parameters");b.onpointerenter=show;b.onpointermove=show;b.onpointerleave=()=>tip.style.opacity=0;b.onfocus=show;b.onblur=()=>tip.style.opacity=0;b.onclick=()=>openModel(d.key);b.onkeydown=ev=>{if(["ArrowRight","ArrowDown","ArrowLeft","ArrowUp"].includes(ev.key)){ev.preventDefault();const bs=svg.querySelectorAll(".point-hit"),dir=(ev.key==="ArrowRight"||ev.key==="ArrowDown")?1:-1;bs[(i+dir+pts.length)%pts.length].focus()}};fo.append(b);svg.append(fo)});host.append(svg);applyTier()}draw();document.querySelectorAll(".legend-filter").forEach(b=>b.onclick=()=>{activeTier=activeTier===b.dataset.tier?null:b.dataset.tier;applyTier()});let resizeTimer;addEventListener("resize",()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(draw,120)});
function sortableValue(cell){const raw=cell.dataset.sort??cell.textContent.trim(),numeric=Number(raw.replace(/%$/, ""));return raw!==""&&Number.isFinite(numeric)?{number:numeric}:{text:raw}}
document.querySelectorAll("table").forEach(table=>table.querySelectorAll("thead th").forEach((th,column)=>{let button=th.querySelector(".sort-button");if(!button){button=document.createElement("button");button.type="button";button.className="sort-button";button.textContent=th.textContent.trim();th.replaceChildren(button)}th.setAttribute("aria-sort","none");button.onclick=()=>{const direction=th.getAttribute("aria-sort")==="ascending"?"descending":"ascending",rows=[...table.tBodies[0].rows],values=rows.map(row=>sortableValue(row.cells[column])),numeric=values.every(value=>"number" in value);rows.sort((a,b)=>{const av=sortableValue(a.cells[column]),bv=sortableValue(b.cells[column]),cmp=numeric?av.number-bv.number:av.text.localeCompare(bv.text,undefined,{numeric:true,sensitivity:"base"});return direction==="ascending"?cmp:-cmp});table.tBodies[0].append(...rows);table.querySelectorAll("thead th").forEach(header=>header.setAttribute("aria-sort","none"));th.setAttribute("aria-sort",direction)}}));
const dlg=document.getElementById("model-dialog");function ot(a){return a.map(x=>x.name.replaceAll("_"," ")+" "+Math.round(x.accuracy*100)+"%").join(" · ")}function openModel(k){const m=MODELS[k];if(!m)return;document.getElementById("modal-title").textContent=m.name;document.getElementById("modal-subtitle").textContent=m.family+" · "+m.model_id+" · "+m.provider.join(", ")+" · "+m.quantization;const cost=m.cost_basis==="paid-equivalent"?money(m.chart_cost*100)+" paid-equivalent ("+money(m.cost*100)+" measured)":money(m.cost*100),reason=m.reasoning_required?"Low effort required · "+m.reasoning_tokens+" hidden reasoning tokens":"Reasoning disabled",errs=m.errors.map(e=>"<div class='error'><b>"+e.question+"</b><div class='meta'>Actual: "+e.gold+" · Answer: "+e.answer+" · Confidence: "+e.confidence+"% · "+e.root_op+"</div></div>").join("");document.getElementById("modal-body").innerHTML="<div class='metric-grid'><div class='metric'><span class='small'>Accuracy</span><b>"+Math.round(m.accuracy*100)+"%</b></div><div class='metric'><span class='small'>Parameters</span><b>"+m.parameters.label+"</b></div><div class='metric'><span class='small'>Cost / 100</span><b>"+cost+"</b></div><div class='metric'><span class='small'>Median latency</span><b>"+m.median_latency.toFixed(2)+"s</b></div></div><p class='meta'>"+reason+" · P90 "+m.p90_latency.toFixed(2)+"s · ECE "+m.ece.toFixed(2)+" · "+m.wrong90+" wrong answers at ≥90% confidence · "+m.retry_rows+" rows retried.</p>"+(m.cost_note?"<div class='note warning'>"+m.cost_note+"</div>":"")+"<p><strong>Strongest operations:</strong> "+ot(m.best_ops)+"<br><strong>Weakest operations:</strong> "+ot(m.worst_ops)+"</p><h3>High-confidence errors</h3>"+errs;sh({model:k});if(!dlg.open)dlg.showModal()}document.querySelectorAll(".model-link").forEach(b=>b.onclick=()=>openModel(b.dataset.model));document.getElementById("modal-close").onclick=()=>dlg.close();dlg.onclose=()=>sh({model:null});const initial=hp().get("model");if(initial)openModel(initial);
</script></body></html>"""
repls={
"__FRONTIER_NAMES__":escape(frontier_names),"__BEST_ACC__":pct(best["accuracy"]),"__BEST_NAME__":escape(best["name"]),
"__BEST_COST__":f"{best['chart_cost']*100:.2f}¢","__BEST_OPEN_NAME__":escape(best_open["name"]),"__BEST_OPEN_ACC__":pct(best_open["accuracy"]),
"__BEST_OPEN_COST__":f"{best_open['chart_cost']*100:.2f}¢","__GLM_COST__":f"{summary['models']['glm53flash']['chart_cost']*100:.2f}¢","__COMPACT_NAME__":escape(best_compact["name"]),"__COMPACT_ACC__":pct(best_compact["accuracy"]),
"__FINANCE_ACC__":pct(finance["accuracy"]),"__FINANCE_COST__":f"{finance['chart_cost']*100:.2f}¢","__TABLE__":table,
"__OPERATION_HEADERS__":operation_headers,"__OPROWS__":oprows,"__ROUTES__":routes,"__EXAMPLES__":examples,
"__CHART_JSON__":chart_json,"__MODELS_JSON__":models_json,"__FRONTIER_JSON__":frontier_json,
"__LUNA_MISSES__":str(100-int(100*summary["models"]["luna"]["accuracy"])),"__LUNA_RECOVERED__":str(len(summary["luna_wrong_local_right"])),
"__ALL_WRONG__":str(len(summary["all_wrong"]))
}
for key,value in repls.items(): html=html.replace(key,value)
(ROOT/"index.html").write_text(html)
print("Wrote data/summary.json and index.html")
for k in ORDER:
    s=summary["models"][k]
    print(k,"accuracy",pct(s["accuracy"]),"AUROC",f"{s['auroc']:.3f}","ECE",f"{s['ece']:.3f}","wrong>=90%",s["wrong90"])
print("all_models_wrong",len(summary["all_wrong"]),"luna_wrong_local_right",len(summary["luna_wrong_local_right"]))
