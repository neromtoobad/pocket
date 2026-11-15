"""Upload Pocket GGUF builds + imatrix files to a public, un-gated model repo. Re-runnable: skips files
already on the Hub with the same size. Extra rows for the model card come from hub/model_rows.md if present.

usage: python publish_models.py [--repo MOREN808/tiny-aya-global-pocket-gguf] [files...]
"""
import argparse
from pathlib import Path
from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parent; M = ROOT.parent / "models"; HUB = ROOT.parent / "hub"
ap = argparse.ArgumentParser(); ap.add_argument("--repo", default="MOREN808/tiny-aya-global-pocket-gguf")
ap.add_argument("files", nargs="*")
a = ap.parse_args()
files = a.files or ["tiny-aya-global-q3_k_m.gguf", "tiny-aya-global-q2_k.gguf", "imatrix-generic.gguf", "imatrix-safety.gguf"]
api = HfApi()
api.create_repo(a.repo, private=False, exist_ok=True)
have = {s.rfilename: s.size for s in api.model_info(a.repo, files_metadata=True).siblings or []}
extra = (HUB / "model_rows.md").read_text().strip() if (HUB / "model_rows.md").exists() else ""
api.upload_file(path_or_fileobj=(HUB / "MODEL_CARD.md").read_text().replace("{{EXTRA_ROWS}}", extra).encode(),
                path_in_repo="README.md", repo_id=a.repo, commit_message="model card")
for f in files:
    p = M / f
    if have.get(f) == p.stat().st_size:
        print("skip", f); continue
    print("upload", f, round(p.stat().st_size / 1e9, 2), "GB", flush=True)
    api.upload_file(path_or_fileobj=str(p), path_in_repo=f, repo_id=a.repo, commit_message=f"add {f}")
print(f"https://huggingface.co/{a.repo}")
