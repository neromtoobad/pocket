#!/bin/zsh
# Pocket grid on the Mac, in priority order. Resumable: every step skips finished work.
set -e
cd "$(dirname "$0")"
PY=../.venv/bin/python
BIN=../bin/llama-b12403
M=../models
F16=$M/tiny-aya-global-f16.gguf
log() { echo "[grid $(date +%H:%M)] $*"; }

gen() {  # gguf cell
  $PY generate.py $1 $2 --max-tokens 160 --parallel 8 --port 8711
  $PY generate.py $1 $2 --prompts data/belebele.jsonl --max-tokens 6 --parallel 8 --port 8711
}
q() {  # name type [extra llama-quantize args...]
  local out=$M/$1.gguf; shift; local t=$1; shift
  [[ -f $out ]] || $BIN/llama-quantize "$@" $F16 $out $t > /dev/null 2>&1
  echo $out
}

log "waiting for f16"; while [[ $(stat -f%z $F16 2>/dev/null || echo 0) -lt 6710484576 ]]; do sleep 20; done

# 0. capability on the already-run official 4-bit cells
for c in global earth; do $PY generate.py $M/tiny-aya-$c-q4_k_m.gguf $c-q4_k_m --prompts data/belebele.jsonl --max-tokens 6 --port 8711; done

# 1. full-precision reference
log "f16"; gen $F16 global-f16
# 2. the cliff: low-bit uniform quants (no imatrix), straight from f16
for t in q3_k_m q2_k; do log $t; gen $(q tiny-aya-global-$t $t) global-$t; done

# 3. calibration (held-out prompts) on f16 -> imatrix: generic vs safety-aware
log "calib"; $PY generate.py $F16 global-f16 --prompts data/calib_prompts.jsonl --max-tokens 160 --port 8711
$PY make_calib.py text global-f16
for k in generic safety; do
  [[ -f $M/imatrix-$k.gguf ]] || $BIN/llama-imatrix -m $F16 -f data/calib_$k.txt -o $M/imatrix-$k.gguf -ngl 99 -c 512 --chunks 400 > runs/imatrix-$k.log 2>&1
done
for k in generic safety; do for t in q3_k_m q2_k; do
  log "$t imatrix-$k"; gen $(q tiny-aya-global-$t-imat-$k $t --imatrix $M/imatrix-$k.gguf) global-$t-imat-$k
done; done

# 4. where safety lives under quantization
log "sweep"; $PY sweep.py --group 6 --low q2_k --n 40

# 5. protected quant (layers from sweep, see protect.py) — run separately once sweep is read
log "protect"; $PY protect.py && for f in $M/tiny-aya-global-protect-*.gguf; do n=$(basename $f .gguf); gen $f ${n#tiny-aya-}; done

# 6. remaining precision points
for t in q8_0 q4_0; do log $t; gen $(q tiny-aya-global-$t $t) global-$t; done
log "DONE"
