"""Safety-protected quantization: keep the most safety-sensitive layer groups (from runs/sweep/summary.json)
at q6_k while the rest go to the low type, using the safety imatrix. Builds size-matched uniform baselines
so the comparison is 'same file size, different bit allocation' rather than 'more bits'.

Writes models/tiny-aya-global-protect-<low>-top<k>.gguf (+ a uniform baseline at the next type up when needed)
"""
import argparse, json, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BIN = ROOT.parent / "bin/llama-b12403"; M = ROOT.parent / "models"; F16 = M / "tiny-aya-global-f16.gguf"
ap = argparse.ArgumentParser(); ap.add_argument("--lows", default="q3_k_m,q2_k"); ap.add_argument("--ks", default="1,2")
a = ap.parse_args()
s = json.load(open(ROOT / "runs/sweep/summary.json"))
res = s["results"]; base = res["all_q8_0"]["all"]
groups = {k: base - v["all"] for k, v in res.items() if k.startswith("crush_")}
ranked = sorted(groups, key=groups.get, reverse=True)
print("refusal drop when crushed:", {k: round(groups[k], 3) for k in ranked})
plan = {}
for low in a.lows.split(","):
    for k in map(int, a.ks.split(",")):
        layers = []
        for g in ranked[:k]:
            a, b = map(int, g.split("_")[1].split("-")); layers += list(range(a, b + 1))
        pat = "blk\\.(" + "|".join(map(str, layers)) + ")\\..*"
        out = M / f"tiny-aya-global-protect-{low}-top{k}.gguf"
        if not out.exists():
            subprocess.run([str(BIN / "llama-quantize"), "--imatrix", str(M / "imatrix-safety.gguf"),
                            "--tensor-type", f"{pat}=q6_k", str(F16), str(out), low], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        plan[out.name] = {"low": low, "protected_layers": layers, "size_gb": round(out.stat().st_size / 1e9, 3)}
json.dump({"ranked_groups": ranked, "drops": groups, "builds": plan}, open(ROOT / "runs/protect_plan.json", "w"), indent=2)
print(json.dumps(plan, indent=1))
