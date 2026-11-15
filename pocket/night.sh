#!/bin/zsh
# Overnight queue: judge each fix cell as it finishes (one heavy job at a time), then SafeTune locate,
# rebuild tables and republish to HF after every step. Log: night.log
cd "$(dirname "$0")"
PY=../.venv/bin/python
log() { echo "[night $(date +%H:%M)] $*"; }
ORDER=(global-f16 global-q4_k_m global-q3_k_m global-q3_k_m-imat-generic global-q3_k_m-imat-safety
       global-protect-q3_k_m-top1 global-protect-q3_k_m-top2 global-q2_k global-q2_k-imat-safety
       global-protect-q2_k-top1 global-q2_k-imat-generic earth-q4_k_m)
tables() {
  local CS=(); for c in $ORDER; do [[ -f runs/$c/judged.jsonl ]] && CS+=$c; done
  $PY analyze.py --ref global-f16 $CS > /dev/null && $PY analyze.py --mt-pass-only --ref global-f16 $CS > /dev/null
  $PY audit_refusal.py $CS > /dev/null; $PY publish_dataset.py 2>&1 | tail -1
}
idle_judge() { while pgrep -f "judge.py" > /dev/null; do sleep 30; done; }
ready() { [[ -f runs/$1/belebele.jsonl && $(wc -l < runs/$1/belebele.jsonl) -ge 300 ]]; }
wait_cell() {  # returns 1 if the grid died without producing the cell
  until ready $1; do pgrep -f run_grid2.sh > /dev/null || { ready $1 || return 1; }; sleep 60; done; }
judge_cell() {
  [[ -f runs/$1/judged.jsonl ]] && return 0
  wait_cell $1 || { log "skip $1 (grid stopped)"; return 0; }
  idle_judge; [[ -f runs/$1/judged.jsonl ]] && return 0; log "judge $1"
  PYTORCH_ENABLE_MPS_FALLBACK=1 $PY judge.py $1 >> judge_night.log 2>&1 || log "judge $1 FAILED"
  tables; log "tables updated after $1"
}
for c in global-q3_k_m-imat-safety global-q3_k_m-imat-generic global-protect-q3_k_m-top1 global-protect-q3_k_m-top2; do judge_cell $c; done
idle_judge; log "SafeTune locate"
$PY locate.py > locate.log 2>&1 || { log "locate OOM? retry without MPS watermark"; PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0 $PY locate.py > locate.log 2>&1 || log "locate FAILED"; }
tail -8 locate.log
for c in global-q2_k-imat-safety global-protect-q2_k-top1 global-q2_k-imat-generic; do judge_cell $c; done
log "NIGHT DONE"
