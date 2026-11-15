#!/bin/zsh
# Trimmed grid (Nov 15 16:50) to meet the deadline: 3-bit fixes first, then sweep, then protected 3-bit,
# then the 2-bit fixes only if time allows. q8_0 / q4_0 dropped. Resumable like run_grid.sh.
set -e
cd "$(dirname "$0")"
PY=../.venv/bin/python; BIN=../bin/llama-b12403; M=../models; F16=$M/tiny-aya-global-f16.gguf
log() { echo "[grid2 $(date +%H:%M)] $*"; }
gen() { $PY generate.py $1 $2 --max-tokens 160 --parallel 8 --port 8711
        $PY generate.py $1 $2 --prompts data/belebele.jsonl --max-tokens 6 --parallel 8 --port 8711; }
q() { local out=$M/$1.gguf; shift; local t=$1; shift
      [[ -f $out ]] || $BIN/llama-quantize "$@" $F16 $out $t > /dev/null 2>&1; echo $out; }
log "waiting for imatrix"; while pgrep -f llama-imatrix >/dev/null; do sleep 20; done
for k in safety generic; do log "q3_k_m imatrix-$k"; gen $(q tiny-aya-global-q3_k_m-imat-$k q3_k_m --imatrix $M/imatrix-$k.gguf) global-q3_k_m-imat-$k; done
log "sweep"; $PY sweep.py --group 6 --low q2_k --n 40
log "protect q3"; $PY protect.py --lows q3_k_m --ks 1,2
for f in $M/tiny-aya-global-protect-q3_k_m-*.gguf; do n=$(basename $f .gguf); gen $f ${n#tiny-aya-}; done
log "3-bit DONE"
log "q2_k imatrix-safety"; gen $(q tiny-aya-global-q2_k-imat-safety q2_k --imatrix $M/imatrix-safety.gguf) global-q2_k-imat-safety
log "protect q2"; $PY protect.py --lows q2_k --ks 1
for f in $M/tiny-aya-global-protect-q2_k-*.gguf; do n=$(basename $f .gguf); gen $f ${n#tiny-aya-}; done
log "q2_k imatrix-generic"; gen $(q tiny-aya-global-q2_k-imat-generic q2_k --imatrix $M/imatrix-generic.gguf) global-q2_k-imat-generic
log "DONE"
