"""Build the Pocket prompt set: harmful (MultiJail) + benign look-alikes (XSTest safe),
in English, Swahili (MultiJail human translation) and Yoruba / Hausa / Igbo (NLLB-200 MT).

Writes data/raw_prompts.jsonl (alpaca-style rows with metadata) for CuratorKIT to clean.
"""
import csv, io, json, random, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data"; OUT.mkdir(exist_ok=True)
N_HARM = int(sys.argv[1]) if len(sys.argv) > 1 else 120
N_BEN = int(sys.argv[2]) if len(sys.argv) > 2 else 120
SEED = 7
random.seed(SEED)

def fetch_csv(url):
    with urllib.request.urlopen(url) as r:
        return list(csv.DictReader(io.StringIO(r.read().decode("utf-8-sig"))))

mj = fetch_csv("https://huggingface.co/datasets/DAMO-NLP-SG/MultiJail/resolve/main/MultiJail.csv")
xs = fetch_csv("https://huggingface.co/datasets/Paul/XSTest/resolve/main/xstest_prompts.csv")
print("MultiJail rows", len(mj), "cols", list(mj[0].keys()))
print("XSTest rows", len(xs), "cols", list(xs[0].keys()))

# stratified sample of MultiJail by first tag
by_tag = {}
for r in mj:
    tag = (r.get("tags") or "other").split(",")[0].strip().strip("[]'\" ") or "other"
    by_tag.setdefault(tag, []).append(r)
harm = []
tags = sorted(by_tag)
while len(harm) < N_HARM and any(by_tag.values()):
    for t in tags:
        if by_tag[t] and len(harm) < N_HARM:
            harm.append((t, by_tag[t].pop(random.randrange(len(by_tag[t])))))

safe = [r for r in xs if r.get("label", "").strip() == "safe"]
random.shuffle(safe)
ben = safe[:N_BEN]

items = []
for t, r in harm:
    items.append({"pid": f"mj{r['id']}", "kind": "harmful", "tag": t, "en": r["en"].strip(),
                  "sw": r["sw"].strip(), "source": "DAMO-NLP-SG/MultiJail"})
for r in ben:
    items.append({"pid": f"xs{r['id']}", "kind": "benign", "tag": r.get("type", ""), "en": r["prompt"].strip(),
                  "sw": None, "source": "Paul/XSTest"})

# ---- machine translation with NLLB-200 (supplementary model, translation only) ----
import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
mt_id = "facebook/nllb-200-distilled-600M"
dev = "mps" if torch.backends.mps.is_available() else "cpu"
tok = AutoTokenizer.from_pretrained(mt_id, src_lang="eng_Latn")
mt = AutoModelForSeq2SeqLM.from_pretrained(mt_id).to(dev).eval()
CODES = {"yo": "yor_Latn", "ha": "hau_Latn", "ig": "ibo_Latn", "sw": "swh_Latn"}

def translate(texts, lang, bs=16):
    out = []
    for i in range(0, len(texts), bs):
        batch = texts[i:i + bs]
        enc = tok(batch, return_tensors="pt", padding=True, truncation=True, max_length=256).to(dev)
        with torch.no_grad():
            gen = mt.generate(**enc, forced_bos_token_id=tok.convert_tokens_to_ids(CODES[lang]),
                              max_new_tokens=256, num_beams=2)
        out += tok.batch_decode(gen, skip_special_tokens=True)
        print(f"  {lang} {min(i + bs, len(texts))}/{len(texts)}", flush=True)
    return out

en = [it["en"] for it in items]
mt_out = {l: translate(en, l) for l in ["yo", "ha", "ig"]}
# benign XSTest has no human Swahili: machine-translate those only
ben_idx = [i for i, it in enumerate(items) if it["sw"] is None]
sw_mt = translate([items[i]["en"] for i in ben_idx], "sw")
for j, i in enumerate(ben_idx):
    items[i]["sw"] = sw_mt[j]; items[i]["sw_method"] = "nllb-200-distilled-600M"

rows = []
for i, it in enumerate(items):
    texts = {"en": (it["en"], "original"),
             "sw": (it["sw"], it.get("sw_method", "human (MultiJail)")),
             **{l: (mt_out[l][i], "nllb-200-distilled-600M") for l in ["yo", "ha", "ig"]}}
    for lang, (txt, method) in texts.items():
        rows.append({"instruction": txt, "input": "", "output": "",
                     "metadata": {"pid": it["pid"], "lang": lang, "kind": it["kind"], "tag": it["tag"],
                                  "source": it["source"], "translation": method, "en": it["en"]}})

with open(OUT / "raw_prompts.jsonl", "w") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print("wrote", len(rows), "rows ->", OUT / "raw_prompts.jsonl")
