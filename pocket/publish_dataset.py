"""Stage and upload the Pocket eval dataset to the Hub (public, un-gated). Safe to re-run as new cells finish.

Uploads: prompt sets, CuratorKIT outputs, every finished cell (generations, Belebele, judge scores, meta),
results tables, the layer sweep, and results/all_judged.jsonl (one row per cell x prompt, read by the Space).
Only cells with a judged.jsonl are included.

usage: python publish_dataset.py [--repo MOREN808/pocket-safety-evals]
"""
import argparse, json, shutil
from pathlib import Path
from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parent
ap = argparse.ArgumentParser(); ap.add_argument("--repo", default="MOREN808/pocket-safety-evals")
a = ap.parse_args()
STAGE = ROOT.parent / "hub/dataset"
if STAGE.exists(): shutil.rmtree(STAGE)
(STAGE / "data").mkdir(parents=True); (STAGE / "runs").mkdir(); (STAGE / "results").mkdir()

for f in ["prompts.jsonl", "belebele.jsonl", "calib_prompts.jsonl", "raw_prompts.jsonl", "gated_prompts.jsonl"]:
    if (ROOT / "data" / f).exists(): shutil.copy(ROOT / "data" / f, STAGE / "data" / f)
shutil.copytree(ROOT / "data/curated", STAGE / "data/curated")
shutil.copy(ROOT / "curate.yaml", STAGE / "data/curated/curate.yaml")

KEEP = ["generations.jsonl", "belebele.jsonl", "judged.jsonl", "meta.json", "bt_cache.json", "calib_prompts.jsonl"]
cells, all_rows = [], []
FIELDS = ["pid", "lang", "kind", "tag", "prompt", "prompt_en", "response", "response_en", "refusal",
          "harm_native", "harm_en", "mt_gate"]
for d in sorted((ROOT / "runs").iterdir()):
    if not d.is_dir() or not (d / "judged.jsonl").exists() or d.name.startswith("smoke"): continue
    cells.append(d.name); (STAGE / "runs" / d.name).mkdir()
    for f in KEEP:
        if (d / f).exists(): shutil.copy(d / f, STAGE / "runs" / d.name / f)
    for l in open(d / "judged.jsonl"):
        r = json.loads(l); all_rows.append({"cell": d.name, **{k: r.get(k) for k in FIELDS}})
if (ROOT / "runs/sweep").exists():
    shutil.copytree(ROOT / "runs/sweep", STAGE / "runs/sweep", ignore=shutil.ignore_patterns("*.log"))
for f in (ROOT / "results").glob("*"):
    shutil.copy(f, STAGE / "results" / f.name)
with open(STAGE / "results/all_judged.jsonl", "w") as f:
    for r in all_rows: f.write(json.dumps(r, ensure_ascii=False) + "\n")
card = (ROOT.parent / "hub/DATASET_CARD.md").read_text().replace("{{CELLS}}", "\n".join(f"- `{c}`" for c in cells))
(STAGE / "README.md").write_text(card)

api = HfApi()
api.create_repo(a.repo, repo_type="dataset", private=False, exist_ok=True)
api.upload_folder(repo_id=a.repo, repo_type="dataset", folder_path=str(STAGE),
                  commit_message=f"Pocket evals: {len(cells)} cells", delete_patterns=["runs/**", "results/**"])
print(f"https://huggingface.co/datasets/{a.repo}  cells={cells}  rows={len(all_rows)}")
