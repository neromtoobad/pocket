"""Leak-free calibration split for the quantization fixes.

Uses only MultiJail / XSTest prompts NOT in the eval set (data/prompts.jsonl).
  data/calib_prompts.jsonl  - held-out harmful + benign prompts (en + MultiJail-human sw + NLLB yo/ha/ig)
After the f16 reference run on these (generate.py --prompts data/calib_prompts.jsonl), build_calib_text()
turns (prompt, f16 answer) pairs into chat-formatted text for llama-imatrix:
  data/calib_safety.txt     - refusal-aware calibration (held-out harmful+benign chats, all 5 languages)
  data/calib_generic.txt    - same token budget of generic multilingual text (Belebele passages not used in eval)
"""
import csv, io, json, random, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
random.seed(13)

def fetch_csv(url):
    return list(csv.DictReader(io.StringIO(urllib.request.urlopen(url).read().decode("utf-8-sig"))))

def make_prompts(n_harm=60, n_ben=60):
    used = {json.loads(l)["pid"] for l in open(ROOT / "data/prompts.jsonl")}
    mj = [r for r in fetch_csv("https://huggingface.co/datasets/DAMO-NLP-SG/MultiJail/resolve/main/MultiJail.csv")
          if "mj" + r["id"] not in used]
    xs = [r for r in fetch_csv("https://huggingface.co/datasets/Paul/XSTest/resolve/main/xstest_prompts.csv")
          if r["label"] == "safe" and "xs" + r["id"] not in used]
    random.shuffle(mj); random.shuffle(xs)
    items = [("mj" + r["id"], "harmful", r["en"], r["sw"]) for r in mj[:n_harm]] + \
            [("xs" + r["id"], "benign", r["prompt"], None) for r in xs[:n_ben]]
    import torch
    from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    tok = AutoTokenizer.from_pretrained("facebook/nllb-200-distilled-600M", src_lang="eng_Latn")
    mt = AutoModelForSeq2SeqLM.from_pretrained("facebook/nllb-200-distilled-600M").to(dev).eval()
    def tr(texts, code):
        out = []
        for i in range(0, len(texts), 16):
            enc = tok(texts[i:i + 16], return_tensors="pt", padding=True, truncation=True, max_length=256).to(dev)
            with torch.no_grad():
                g = mt.generate(**enc, forced_bos_token_id=tok.convert_tokens_to_ids(code), max_new_tokens=256, num_beams=2)
            out += tok.batch_decode(g, skip_special_tokens=True)
        return out
    en = [it[2] for it in items]
    mts = {l: tr(en, c) for l, c in {"yo": "yor_Latn", "ha": "hau_Latn", "ig": "ibo_Latn", "sw": "swh_Latn"}.items()}
    with open(ROOT / "data/calib_prompts.jsonl", "w") as f:
        for i, (pid, kind, e, sw) in enumerate(items):
            for lang, txt in {"en": e, "sw": sw or mts["sw"][i], "yo": mts["yo"][i], "ha": mts["ha"][i], "ig": mts["ig"][i]}.items():
                f.write(json.dumps({"pid": pid, "lang": lang, "kind": kind, "tag": "calib", "text": txt}, ensure_ascii=False) + "\n")
    print("calib prompts:", len(items) * 5)

def build_calib_text(ref_cell="global-f16"):
    """Chat-formatted (prompt, f16 answer) text in Tiny Aya's template, plus a matched generic set."""
    rows = [json.loads(l) for l in open(ROOT / "runs" / ref_cell / "calib_prompts.jsonl")]
    random.shuffle(rows)
    import jinja2
    tpl = jinja2.Environment(loader=jinja2.BaseLoader(), extensions=["jinja2.ext.loopcontrols"]).from_string((ROOT / "data/tiny_aya_template.jinja").read_text())
    def chat(p, r):  # Tiny Aya's own template, incl. its default contextual-safety system preamble
        return tpl.render(messages=[{"role": "user", "content": p}, {"role": "assistant", "content": r}],
                          bos_token="<BOS_TOKEN>", add_generation_prompt=False)
    safety = "\n".join(chat(r["prompt"], r["response"]) for r in rows)
    (ROOT / "data/calib_safety.txt").write_text(safety)
    # generic: Belebele passages not used in data/belebele.jsonl, same character budget
    used = {json.loads(l)["pid"] for l in open(ROOT / "data/belebele.jsonl")}
    codes = ["eng_Latn", "swh_Latn", "yor_Latn", "hau_Latn", "ibo_Latn"]
    passages = []
    for c in codes:
        data = urllib.request.urlopen(f"https://huggingface.co/datasets/facebook/belebele/resolve/main/data/{c}.jsonl").read().decode().splitlines()
        seen = set()
        for i, l in enumerate(data):
            r = json.loads(l)
            if f"bb{i}" in used or r["flores_passage"] in seen: continue
            seen.add(r["flores_passage"]); passages.append(r["flores_passage"])
    random.shuffle(passages)
    out, n = [], 0
    for p in passages:
        if n >= len(safety): break
        out.append(p); n += len(p) + 1
    (ROOT / "data/calib_generic.txt").write_text("\n".join(out))
    print("calib_safety chars", len(safety), "calib_generic chars", n)

if __name__ == "__main__":
    make_prompts() if sys.argv[1:] == ["prompts"] else build_calib_text(*sys.argv[2:])
