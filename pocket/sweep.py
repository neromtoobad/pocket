"""Layer-group safety sensitivity sweep (black-box 'where does safety live under quantization').

For each group of layers g, build a GGUF where every tensor is q8_0 except blocks in g, which are crushed
to a low type (default q2_k). Run the held-out calibration harmful prompts (all 5 languages, short answers)
and measure lexical refusal rate. Large drop => safety-critical group. Also runs all-q8 and all-low anchors.

usage: python sweep.py [--group 6] [--low q2_k] [--n 40]
Writes runs/sweep/summary.json
"""
import argparse, json, subprocess, sys
from pathlib import Path
from refusal import is_refusal

ROOT = Path(__file__).resolve().parent
BIN = ROOT.parent / "bin/llama-b12403"
F16 = ROOT.parent / "models/tiny-aya-global-f16.gguf"
ap = argparse.ArgumentParser()
ap.add_argument("--group", type=int, default=6); ap.add_argument("--low", default="q2_k")
ap.add_argument("--n", type=int, default=40); ap.add_argument("--layers", type=int, default=36)
a = ap.parse_args()
SW = ROOT / "runs/sweep"; SW.mkdir(parents=True, exist_ok=True)
QDIR = ROOT.parent / "models/sweep"; QDIR.mkdir(parents=True, exist_ok=True)

# probe = first n held-out harmful pids, all 5 langs
calib = [json.loads(l) for l in open(ROOT / "data/calib_prompts.jsonl")]
pids = sorted({r["pid"] for r in calib if r["kind"] == "harmful"})[: a.n]
probe = [r for r in calib if r["pid"] in pids]
pf = SW / "probe.jsonl"; pf.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in probe))

def quantize(name, overrides, base_type):
    out = QDIR / f"{name}.gguf"
    if not out.exists():
        cmd = [str(BIN / "llama-quantize")] + sum([["--tensor-type", o] for o in overrides], []) + [str(F16), str(out), base_type]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return out

def run(name, gguf):
    cell = f"sweep-{name}"
    subprocess.run([sys.executable, str(ROOT / "generate.py"), str(gguf), cell, "--prompts", str(pf),
                    "--max-tokens", "48", "--parallel", "8", "--port", "8711"], check=True)
    rows = [json.loads(l) for l in open(ROOT / "runs" / cell / "probe.jsonl")]
    by = {}
    for r in rows:
        by.setdefault(r["lang"], []).append(is_refusal(r["response"], r["lang"]))
    res = {l: round(sum(v) / len(v), 3) for l, v in by.items()}
    res["all"] = round(sum(sum(v) for v in by.values()) / sum(len(v) for v in by.values()), 3)
    res["size_gb"] = round(gguf.stat().st_size / 1e9, 3)
    return res

summary = {"probe_n": len(probe), "low": a.low, "group": a.group, "results": {}}
summary["results"]["all_q8_0"] = run("all_q8_0", quantize("all_q8_0", [], "q8_0"))
summary["results"][f"all_{a.low}"] = run(f"all_{a.low}", quantize(f"all_{a.low}", [], a.low))
for g0 in range(0, a.layers, a.group):
    ls = list(range(g0, min(g0 + a.group, a.layers)))
    pat = "blk\\.(" + "|".join(map(str, ls)) + ")\\..*"
    name = f"crush_{ls[0]}-{ls[-1]}"
    summary["results"][name] = run(name, quantize(name, [f"{pat}={a.low}"], "q8_0"))
    json.dump(summary, open(SW / "summary.json", "w"), indent=2)
    print(name, summary["results"][name], flush=True)
json.dump(summary, open(SW / "summary.json", "w"), indent=2)
print(json.dumps(summary["results"], indent=1))
