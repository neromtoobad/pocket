"""Where does Tiny Aya's refusal live, per language, and does it predict what quantization breaks?

Uses SafeTune's SteeringVectorExtractor (safetune.core.runtime.inference.vector_extraction) on the full-precision
HF weights of Tiny Aya Global:

1. Refusal direction per language and layer, from the HELD-OUT calibration prompts (data/calib_prompts.jsonl):
   SafeTune's extract() gives mean(harmless) - mean(harmful) at the last prompt token; we flip the sign so a
   higher projection = "looks harmful" (what the model should refuse).
2. On the EVALUATION prompts (data/prompts.jsonl), project every prompt onto those directions and report, per
   layer and language: AUROC harmful-vs-harmless with the language's own direction and with the English one
   (does English refusal transfer?), and the cosine between each language's direction and English's.
3. Margin vs quantization: at the best layer, does a harmful prompt's projection on the f16 model predict whether
   the 3-bit / 2-bit GGUF stops refusing it? (AUROC of margin for kept-vs-lost refusals, from the judged runs.)

usage: python locate.py [--model ../models/hf-tiny-aya-global] [--device mps] [--limit N]
Writes results/locate.json and runs/locate/{vectors.pt,scores.jsonl}.
"""
import argparse, json
from pathlib import Path
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from safetune.core.runtime.inference.vector_extraction import SteeringVectorExtractor, VectorExtractionConfig

ROOT = Path(__file__).resolve().parent
LANGS = ["en", "sw", "yo", "ha", "ig"]
ap = argparse.ArgumentParser()
ap.add_argument("--model", default=str(ROOT.parent / "models/hf-tiny-aya-global"))
ap.add_argument("--device", default="mps" if torch.backends.mps.is_available() else "cpu")
ap.add_argument("--limit", type=int, default=0, help="prompts per (lang, kind), for smoke tests")
ap.add_argument("--batch", type=int, default=8)
ap.add_argument("--quant-cells", default="global-q3_k_m,global-q2_k")
a = ap.parse_args()

def load(f):
    rows = [json.loads(l) for l in open(ROOT / "data" / f)]
    if a.limit:
        keep, seen = [], {}
        for r in rows:
            k = (r["lang"], r["kind"]); seen[k] = seen.get(k, 0) + 1
            if seen[k] <= a.limit: keep.append(r)
        rows = keep
    return rows

def auroc(pos, neg):
    if not pos or not neg: return None
    allv = sorted([(v, 1) for v in pos] + [(v, 0) for v in neg])
    ranks, i = {}, 0
    while i < len(allv):  # average ranks for ties
        j = i
        while j < len(allv) and allv[j][0] == allv[i][0]: j += 1
        for k in range(i, j): ranks[k] = (i + j + 1) / 2
        i = j
    rpos = sum(ranks[k] for k, (_, y) in enumerate(allv) if y == 1)
    return round((rpos - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)), 4)

dtype = torch.float16 if a.device == "mps" else torch.float32
tok = AutoTokenizer.from_pretrained(a.model)
model = AutoModelForCausalLM.from_pretrained(a.model, dtype=dtype).to(a.device).eval()
n_layers = model.config.num_hidden_layers
ext = SteeringVectorExtractor(model, tok, VectorExtractionConfig(target_layers=list(range(n_layers)),
                              batch_size=a.batch, pool_method="last_token", normalize=True))

# 1. directions per language from held-out prompts (SafeTune public API)
calib = load("calib_prompts.jsonl")
dirs = {}
for lang in LANGS:
    harm = [r["text"] if "text" in r else r["prompt"] for r in calib if r["lang"] == lang and r["kind"] == "harmful"]
    safe = [r["text"] if "text" in r else r["prompt"] for r in calib if r["lang"] == lang and r["kind"] == "benign"]
    v = ext.extract(safe_prompts=safe, unsafe_prompts=harm)          # mean(safe) - mean(harmful), unit norm
    dirs[lang] = {l: -v[l] for l in v}                                 # flip: + = looks harmful
    print(f"[locate] directions {lang}: {len(harm)} harmful / {len(safe)} harmless", flush=True)
out_dir = ROOT / "runs/locate"; out_dir.mkdir(parents=True, exist_ok=True)
torch.save({lang: {l: d.cpu() for l, d in dd.items()} for lang, dd in dirs.items()}, out_dir / "vectors.pt")

# 2. project evaluation prompts
ev = load("prompts.jsonl")
acts = ext._collect_activations([r["text"] for r in ev], desc="eval")    # {layer: (N, d)} pooled last token
per_layer = {}
for l in range(n_layers):
    A = acts[l].float()
    row = {}
    for lang in LANGS:
        idx_h = [i for i, r in enumerate(ev) if r["lang"] == lang and r["kind"] == "harmful"]
        idx_b = [i for i, r in enumerate(ev) if r["lang"] == lang and r["kind"] == "benign"]
        own = (A @ dirs[lang][l].float()).tolist(); en = (A @ dirs["en"][l].float()).tolist()
        row[lang] = {"auroc_own": auroc([own[i] for i in idx_h], [own[i] for i in idx_b]),
                     "auroc_en_dir": auroc([en[i] for i in idx_h], [en[i] for i in idx_b]),
                     "cos_to_en": round(float(torch.nn.functional.cosine_similarity(dirs[lang][l], dirs["en"][l], dim=0)), 4)}
    per_layer[l] = row
best = max(range(n_layers), key=lambda l: sum(per_layer[l][x]["auroc_own"] or 0 for x in LANGS))

# 3. margin at the best layer vs refusals lost under quantization
A = acts[best].float()
scores = []
for i, r in enumerate(ev):
    scores.append({"pid": r["pid"], "lang": r["lang"], "kind": r["kind"],
                   "margin_own": round(float(A[i] @ dirs[r["lang"]][best].float()), 4),
                   "margin_en_dir": round(float(A[i] @ dirs["en"][best].float()), 4)})
with open(out_dir / "scores.jsonl", "w") as f:
    for s in scores: f.write(json.dumps(s) + "\n")

def refusals(cell):
    p = ROOT / "runs" / cell / "judged.jsonl"
    return {(json.loads(x)["pid"], json.loads(x)["lang"]): json.loads(x)["refusal"] for x in open(p)} if p.exists() else {}
f16 = refusals("global-f16")
flip = {}
for cell in a.quant_cells.split(","):
    q = refusals(cell)
    if not q or not f16: continue
    flip[cell] = {}
    for lang in LANGS:
        S = [s for s in scores if s["lang"] == lang and s["kind"] == "harmful" and f16.get((s["pid"], lang))
             and (s["pid"], lang) in q]
        kept = [s["margin_own"] for s in S if q[(s["pid"], lang)]]
        lost = [s["margin_own"] for s in S if not q[(s["pid"], lang)]]
        flip[cell][lang] = {"n_refused_f16": len(S), "n_lost": len(lost),
                            "auroc_margin_kept_vs_lost": auroc(kept, lost),
                            "mean_margin_kept": round(sum(kept) / len(kept), 3) if kept else None,
                            "mean_margin_lost": round(sum(lost) / len(lost), 3) if lost else None}
lang_margin = {lang: round(sum(s["margin_own"] for s in scores if s["lang"] == lang and s["kind"] == "harmful") /
                           max(1, sum(1 for s in scores if s["lang"] == lang and s["kind"] == "harmful")), 3) for lang in LANGS}

res = {"model": a.model, "n_layers": n_layers, "best_layer": best, "pool": "last_token",
       "directions_from": "data/calib_prompts.jsonl (held out)", "scored_on": "data/prompts.jsonl",
       "per_layer": per_layer, "mean_harmful_margin_best_layer": lang_margin, "quant_flip": flip}
(ROOT / "results").mkdir(exist_ok=True)
json.dump(res, open(ROOT / "results/locate.json", "w"), indent=1)
print(f"[locate] best layer {best}")
for l in range(0, n_layers, 3):
    print(f"  L{l:02d} " + " ".join(f"{x}:{per_layer[l][x]['auroc_own']}/{per_layer[l][x]['auroc_en_dir']}/cos{per_layer[l][x]['cos_to_en']}" for x in LANGS))
print("  harmful margin at best layer:", lang_margin)
print("  quant flip:", json.dumps(flip))
