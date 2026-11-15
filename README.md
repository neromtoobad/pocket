# Pocket

**Shrink Tiny Aya to run on a phone and it keeps refusing harmful requests in English, but not in Swahili, Yorùbá, Hausa or Igbo.**

Pocket measures whether [Tiny Aya](https://huggingface.co/CohereLabs/tiny-aya-global)'s safety survives GGUF quantization, language by language, and tries to repair it with safety-aware quantization. Built for the Lexsi AI Safety & Alignment Hackathon (Track 2).

> **Content warning:** the data this code builds and reads contains harmful requests and model answers to them.

| | |
|---|---|
| Write-up | [`writeup/ARTICLE.md`](writeup/ARTICLE.md) |
| Dataset (prompts, every answer, judge scores, tables) | [MOREN808/pocket-safety-evals](https://huggingface.co/datasets/MOREN808/pocket-safety-evals) |
| GGUF builds + imatrix files | [MOREN808/tiny-aya-global-pocket-gguf](https://huggingface.co/MOREN808/tiny-aya-global-pocket-gguf) |
| Browse every answer | [MOREN808/pocket Space](https://huggingface.co/spaces/MOREN808/pocket) |

## Results so far

Refuses harmful prompts, % (120 per language; higher is better):

| Tiny Aya Global | Size | English | Swahili | Yorùbá | Hausa | Igbo |
|---|---|---|---|---|---|---|
| f16 (official) | 6.7 GB | 74 | 56 | 29 | 51 | 48 |
| q4_k_m (official) | 2.1 GB | 73 | 59 | 32 | 56 | 56 |
| q3_k_m | 1.8 GB | 75 | 40 | 18 | 43 | 52 |
| q2_k | 1.5 GB | 75 | 29 | 2 | 20 | 21 |

Attack success, judge-scored intervals, over-refusal, reading comprehension and the Earth variant are in [`results/table.md`](results/table.md) and the write-up.

## Pipeline

```
MultiJail + XSTest ─► NLLB-200 translate ─► back-translation gate ─► CuratorKIT (clean, dedup, export, provenance)
                                                                            │
          official f16 GGUF ─► llama-quantize (q4/q3/q2, imatrix, per-layer types) ─► llama.cpp generation
                                                                            │
   Granite Guardian (English view) + AuditKIT refusal + Pocket refusal + Belebele ─► paired bootstrap tables
                                                                            │
   SafeTune refusal directions (f16) ─► layer-group sweep ─► protected mixed-precision GGUF ─► same evaluation
```

Lexsi kits used: [CuratorKIT](https://github.com/Lexsi-Labs/CuratorKIT) (data curation), [AuditKIT](https://github.com/Lexsi-Labs/AuditKIT) (multilingual refusal metric, extended here to Yorùbá, Hausa and Igbo) and [SafeTune](https://github.com/Lexsi-Labs/SafeTune) (per-language refusal directions with `SteeringVectorExtractor`).

## Repo layout

| Path | What it does |
|---|---|
| `pocket/build_prompts.py` | fetch MultiJail + XSTest, stratified sample, NLLB translate → `data/raw_prompts.jsonl` |
| `pocket/backtranslate_gate.py` | back-translate to English, flag rows with chrF < 35 → `data/gated_prompts.jsonl` |
| `pocket/curate.yaml` | CuratorKIT pipeline → `data/curated/` |
| `pocket/make_calib.py` | held-out calibration prompts; imatrix calibration text (safety chats vs generic) |
| `pocket/generate.py` | run a GGUF over a prompt file with `llama-server` (resumable) |
| `pocket/judge.py` | Granite Guardian 3.1 2B scoring on native text and NLLB back-translation |
| `pocket/refusal.py` | lexical refusal detector for en / sw / yo / ha / ig |
| `pocket/audit_refusal.py` | AuditKIT refusal metric with yo / ha / ig patterns registered |
| `pocket/analyze.py` | per-build, per-language tables, paired deltas vs f16, bootstrap intervals |
| `pocket/locate.py` | SafeTune refusal directions per language and layer; margin vs refusals lost under quantization |
| `pocket/sweep.py` | crush one 6-layer group to q2_k at a time, measure the refusal drop |
| `pocket/protect.py` | keep the most safety-sensitive groups at q6_k in a 3-bit / 2-bit build |
| `pocket/run_grid.sh`, `run_grid2.sh` | the full grid (original order) and the trimmed order actually run |
| `pocket/publish_dataset.py`, `publish_models.py` | upload results and GGUFs to the Hub |
| `pocket/space_static/` | the results explorer Space (static page reading the dataset) |
| `results/` | the tables used in the write-up |
| `hub/` | dataset and model cards |

## Reproduce

Tested on an Apple M1 Pro with 16 GB RAM (Metal). About 12 GB of free disk for the f16 GGUF and quants.

```bash
uv venv -p 3.12 .venv && source .venv/bin/activate
uv pip install -r requirements.txt
mkdir -p vendor && for k in CuratorKIT AuditKIT; do git clone https://github.com/Lexsi-Labs/$k vendor/$k && uv pip install -e vendor/$k; done
```

Get llama.cpp release **b12403** into `bin/llama-b12403/`, accept the Tiny Aya license on Hugging Face, and download into `models/`:

```bash
hf download CohereLabs/tiny-aya-global-GGUF tiny-aya-global-f16.gguf tiny-aya-global-q4_k_m.gguf --local-dir models
hf download CohereLabs/tiny-aya-earth-GGUF tiny-aya-earth-q4_k_m.gguf --local-dir models
```

Plus the judge, a Granite Guardian 3.1 2B Q8_0 GGUF:

```bash
curl -L -o models/guardian-3.1-2b-q8_0.gguf https://huggingface.co/DevQuasar-11/ibm-granite.granite-guardian-3.1-2b-GGUF/resolve/main/ibm-granite.granite-guardian-3.1-2b.Q8_0.gguf
```

Then:

```bash
cd pocket
python build_prompts.py && python backtranslate_gate.py
curatorkit run curate.yaml --output-dir data/curated
python make_calib.py prompts
zsh run_grid2.sh                       # generation for every build (hours on a laptop)
python judge.py global-f16 global-q4_k_m global-q3_k_m global-q2_k earth-q4_k_m
python analyze.py --ref global-f16 global-f16 global-q4_k_m global-q3_k_m global-q2_k earth-q4_k_m
python analyze.py --mt-pass-only --ref global-f16 global-f16 global-q4_k_m global-q3_k_m global-q2_k earth-q4_k_m
python audit_refusal.py global-f16 global-q4_k_m global-q3_k_m global-q2_k earth-q4_k_m
```

Decoding is greedy (temperature 0, seed 0, 160 new tokens) with the model's own chat template (`--jinja`). To skip generation, download `runs/` from the dataset repo and start at `analyze.py`.

## Licenses

Code: MIT. Data and model outputs on the Hub: CC-BY-NC 4.0 (Tiny Aya and NLLB-200 outputs; MultiJail MIT, XSTest CC-BY 4.0, Belebele CC-BY-SA 4.0). Tiny Aya use must follow the Cohere Labs Acceptable Use Policy.
