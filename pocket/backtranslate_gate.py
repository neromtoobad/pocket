"""Faithfulness gate for machine-translated prompts: NLLB back-translation -> chrF vs the English original.
Adds metadata.bt_en and metadata.bt_chrf to every MT row; rows under the threshold are marked for rejection.
Output: data/gated_prompts.jsonl (input for the CuratorKIT pipeline).
"""
import json, sys
from pathlib import Path
import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

ROOT = Path(__file__).resolve().parent
THRESH = float(sys.argv[1]) if len(sys.argv) > 1 else 35.0
rows = [json.loads(l) for l in open(ROOT / "data/raw_prompts.jsonl")]
CODES = {"yo": "yor_Latn", "ha": "hau_Latn", "ig": "ibo_Latn", "sw": "swh_Latn"}
mt_id = "facebook/nllb-200-distilled-600M"
dev = "mps" if torch.backends.mps.is_available() else "cpu"
mt = AutoModelForSeq2SeqLM.from_pretrained(mt_id).to(dev).eval()

def chrf(hyp, ref, n=6, beta=2):
    """sentence chrF (character n-gram F-score), as in sacrebleu's default."""
    import collections
    hyp, ref = hyp.replace(" ", ""), ref.replace(" ", "")
    ps, rs = [], []
    for k in range(1, n + 1):
        h = collections.Counter(hyp[i:i + k] for i in range(len(hyp) - k + 1))
        r = collections.Counter(ref[i:i + k] for i in range(len(ref) - k + 1))
        m = sum((h & r).values())
        ps.append(m / max(sum(h.values()), 1)); rs.append(m / max(sum(r.values()), 1))
    p, r = sum(ps) / n, sum(rs) / n
    return 0.0 if p + r == 0 else 100 * (1 + beta ** 2) * p * r / (beta ** 2 * p + r)

for lang, code in CODES.items():
    idx = [i for i, r in enumerate(rows) if r["metadata"]["lang"] == lang and r["metadata"]["translation"].startswith("nllb")]
    tok = AutoTokenizer.from_pretrained(mt_id, src_lang=code)
    for s in range(0, len(idx), 16):
        b = idx[s:s + 16]
        enc = tok([rows[i]["instruction"] for i in b], return_tensors="pt", padding=True, truncation=True, max_length=256).to(dev)
        with torch.no_grad():
            g = mt.generate(**enc, forced_bos_token_id=tok.convert_tokens_to_ids("eng_Latn"), max_new_tokens=200, num_beams=2)
        for i, bt in zip(b, tok.batch_decode(g, skip_special_tokens=True)):
            md = rows[i]["metadata"]; md["bt_en"] = bt; md["bt_chrf"] = round(chrf(bt.lower(), md["en"].lower()), 1)
            md["mt_gate"] = "pass" if md["bt_chrf"] >= THRESH else "fail"
    print(lang, "done", flush=True)

with open(ROOT / "data/gated_prompts.jsonl", "w") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
import collections
c = collections.Counter((r["metadata"]["lang"], r["metadata"].get("mt_gate", "n/a")) for r in rows)
print(dict(c))
