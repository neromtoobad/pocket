"""Run one GGUF (one cell of the sibling x precision grid) over the prompt set via llama-server.

usage: python generate.py <gguf path> <cell name> [--limit N] [--langs en,sw,yo,ha,ig]
Writes runs/<cell>/generations.jsonl (resumable) + runs/<cell>/meta.json.
"""
import argparse, json, os, signal, subprocess, sys, time, hashlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parent
SERVER = ROOT.parent / "bin/llama-b12403/llama-server"
PROMPTS = ROOT / "data/prompts.jsonl"

ap = argparse.ArgumentParser()
ap.add_argument("gguf"); ap.add_argument("cell")
ap.add_argument("--limit", type=int, default=0)
ap.add_argument("--langs", default="en,sw,yo,ha,ig")
ap.add_argument("--max-tokens", type=int, default=160)
ap.add_argument("--parallel", type=int, default=8)
ap.add_argument("--port", type=int, default=8701)
ap.add_argument("--prompts", default=str(PROMPTS))
a = ap.parse_args()

out_dir = ROOT / "runs" / a.cell; out_dir.mkdir(parents=True, exist_ok=True)
out_f = out_dir / ("generations.jsonl" if a.prompts == str(PROMPTS) else Path(a.prompts).stem + ".jsonl")
done = set()
if out_f.exists():
    for l in out_f.open():
        r = json.loads(l); done.add((r["pid"], r["lang"]))

langs = a.langs.split(",")
rows = [json.loads(l) for l in open(a.prompts)]
rows = [r for r in rows if r["lang"] in langs]
if a.limit:
    keep = sorted({r["pid"] for r in rows})[: a.limit]
    rows = [r for r in rows if r["pid"] in keep]
todo = [r for r in rows if (r["pid"], r["lang"]) not in done]
print(f"[{a.cell}] {len(rows)} prompts, {len(todo)} to run", flush=True)
if not todo:
    sys.exit(0)

ctx = 1024 * a.parallel
proc = subprocess.Popen([str(SERVER), "-m", a.gguf, "--port", str(a.port), "-ngl", "99", "-c", str(ctx),
                         "-np", str(a.parallel), "--jinja", "--seed", "0", "-fa", "on"],
                        stdout=open(out_dir / "server.log", "w"), stderr=subprocess.STDOUT)
base = f"http://127.0.0.1:{a.port}"
for _ in range(240):
    try:
        if json.load(urllib.request.urlopen(base + "/health", timeout=2)).get("status") == "ok":
            break
    except Exception:
        pass
    time.sleep(1)
else:
    proc.kill(); sys.exit("server did not start; see server.log")

def call(r):
    body = {"messages": [{"role": "user", "content": r["text"]}], "temperature": 0.0, "top_p": 1.0,
            "max_tokens": a.max_tokens, "seed": 0}
    req = urllib.request.Request(base + "/v1/chat/completions", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    t0 = time.time()
    for attempt in range(3):
        try:
            res = json.load(urllib.request.urlopen(req, timeout=300))
            break
        except Exception as e:
            if attempt == 2: raise
            time.sleep(2)
    msg = res["choices"][0]["message"]["content"]
    return {**{k: r[k] for k in ("pid", "lang", "kind", "tag")}, "prompt": r["text"], "response": msg,
            "finish": res["choices"][0].get("finish_reason"), "tokens": res.get("usage", {}).get("completion_tokens"),
            "secs": round(time.time() - t0, 2), "cell": a.cell}

t0 = time.time(); n = 0
try:
    with ThreadPoolExecutor(a.parallel) as ex, out_f.open("a") as f:
        for res in ex.map(call, todo):
            f.write(json.dumps(res, ensure_ascii=False) + "\n"); f.flush(); n += 1
            if n % 50 == 0:
                print(f"[{a.cell}] {n}/{len(todo)}  {n / (time.time() - t0):.2f} prompts/s", flush=True)
finally:
    proc.send_signal(signal.SIGTERM); proc.wait(timeout=30)

sha = hashlib.sha256(open(a.gguf, "rb").read(1 << 24)).hexdigest()[:16]
if a.prompts == str(PROMPTS): json.dump({"cell": a.cell, "gguf": os.path.basename(a.gguf), "gguf_size": os.path.getsize(a.gguf),
           "gguf_head_sha256_16MB": sha, "llama_cpp_build": "b12403", "temperature": 0, "max_tokens": a.max_tokens,
           "n": len(rows), "wall_secs": round(time.time() - t0, 1)}, open(out_dir / "meta.json", "w"), indent=2)
print(f"[{a.cell}] done in {time.time() - t0:.0f}s", flush=True)
