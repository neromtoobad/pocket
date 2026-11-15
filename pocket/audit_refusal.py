"""Second refusal scorer: AuditKIT's multilingual refusal metric (auditkit.metrics.refusal).

AuditKIT ships refusal patterns for en/hi/bn/ta/ar/sw but not Yorùbá, Hausa or Igbo. We register ours
(from refusal.py, mined from Tiny Aya's own answer openings) into AuditKIT's pattern table at runtime, then
score every judged row with `find_refusal`, which reads only the opening sentence (ours reads the first 200
characters). Reports per-cell, per-language refusal rates from both scorers and their Cohen's kappa.

usage: python audit_refusal.py cell [cell ...]   -> results/audit_refusal.json
"""
import json, re, sys
from pathlib import Path
import auditkit.metrics.refusal as akr
from refusal import MARKERS, is_refusal

ROOT = Path(__file__).resolve().parent
ADDED = [l for l in ("yo", "ha", "ig") if l not in akr.REFUSAL_PATTERNS]
for lang in ADDED:
    akr.REFUSAL_PATTERNS[lang] = MARKERS[lang]
    akr._COMPILED[lang] = [re.compile(akr._fold(p), re.IGNORECASE | re.DOTALL) for p in MARKERS[lang]]

def kappa(x, y):
    n = len(x); po = sum(a == b for a, b in zip(x, y)) / n
    px, py = sum(x) / n, sum(y) / n; pe = px * py + (1 - px) * (1 - py)
    return round((po - pe) / (1 - pe), 3) if pe < 1 else 1.0

out = {"auditkit_languages_added": ADDED, "cells": {}}
for cell in sys.argv[1:]:
    f = ROOT / "runs" / cell / "judged.jsonl"
    rows = [json.loads(l) for l in open(f if f.exists() else ROOT / "runs" / cell / "generations.jsonl")]
    out["cells"][cell] = {}
    for lang in ["en", "sw", "yo", "ha", "ig"]:
        for kind in ["harmful", "benign"]:
            R = [r for r in rows if r["lang"] == lang and r["kind"] == kind]
            ak = [akr.find_refusal(r["response"] or "", lang) is not None for r in R]
            ours = [is_refusal(r["response"], lang) for r in R]
            out["cells"][cell][f"{lang}_{kind}"] = {"n": len(R), "auditkit": round(sum(ak) / len(R), 3),
                                                   "pocket": round(sum(ours) / len(R), 3), "kappa": kappa(ak, ours)}
(ROOT / "results").mkdir(exist_ok=True)
json.dump(out, open(ROOT / "results/audit_refusal.json", "w"), indent=1)
for cell, t in out["cells"].items():
    print(cell, " ".join(f"{k.split('_')[0]}:{v['auditkit']*100:.0f}/{v['pocket']*100:.0f} k{v['kappa']}"
                         for k, v in t.items() if k.endswith("harmful")))
