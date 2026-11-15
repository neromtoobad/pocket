#!/bin/zsh
# Round-up queue after the 19:42 reboot: finish q3 imatrix-generic, judge both imatrix fixes, tables, publish, small SafeTune run.
cd "$(dirname "$0")"; PY=../.venv/bin/python; M=../models
log() { echo "[finish $(date +%H:%M)] $*"; }
ORDER=(global-f16 global-q4_k_m global-q3_k_m global-q3_k_m-imat-generic global-q3_k_m-imat-safety global-q2_k earth-q4_k_m)
tables() { local CS=(); for c in $ORDER; do [[ -f runs/$c/judged.jsonl ]] && CS+=$c; done
  $PY analyze.py --ref global-f16 $CS > /dev/null && $PY analyze.py --mt-pass-only --ref global-f16 $CS > /dev/null
  $PY audit_refusal.py $CS > /dev/null; $PY publish_dataset.py 2>&1 | tail -1; }
G=global-q3_k_m-imat-generic
( $PY generate.py $M/tiny-aya-$G.gguf $G --max-tokens 160 --parallel 8 --port 8711 > gen_fix2.log 2>&1 &&
  $PY generate.py $M/tiny-aya-$G.gguf $G --prompts data/belebele.jsonl --max-tokens 6 --parallel 8 --port 8711 >> gen_fix2.log 2>&1
  echo "gen exit $?" >> gen_fix2.log ) &
GEN=$!
log "judge imat-safety"; PYTORCH_ENABLE_MPS_FALLBACK=1 $PY judge.py global-q3_k_m-imat-safety > judge_fix1.log 2>&1 || log "judge fix1 FAILED"
tables; log "tables after fix1"
wait $GEN; log "fix2 generated: $(tail -1 gen_fix2.log)"
PYTORCH_ENABLE_MPS_FALLBACK=1 $PY judge.py $G > judge_fix2.log 2>&1 || log "judge fix2 FAILED"
tables; log "tables after fix2"
log "SafeTune locate (small)"; $PY locate.py --limit 20 > locate.log 2>&1 || log "locate FAILED"
grep -v Calibrate locate.log | tail -10
log "DONE"
