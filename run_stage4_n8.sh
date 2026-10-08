#!/usr/bin/env bash
# Stage 4 on the GPU box (n8): imitate the teacher at scale from Stage 2's champion raw0056, no computed notes.
#   nohup setsid ./run_stage4_n8.sh > runs/stage4_n8.out 2>&1 &
set -uo pipefail
cd "$(dirname "$0")"
export LAYA_ACTIONS=raw LAYA_CALC=0 PYTHONIOENCODING=utf-8 APPDATA="$PWD/profile"
PY=.venv/bin/python
note() { echo "$(date '+%F %T') $*" >> runs/stage4.log; }

if [ ! -f data/hf_s4.jsonl ]; then
  note "convert start (20 shards x 20000 decisions, in parallel)"
  for k in $(seq 0 19); do
    $PY -u -m laya_player.hf_convert --shards "$k-$k" --per-shard 20000 --seed $((101 + k)) \
      --out "data/hf_s4_$k.jsonl" > "runs/convert4_$k.txt" 2>&1 &
  done
  wait
  cat data/hf_s4_{0..19}.jsonl > data/hf_s4.jsonl && rm -f data/hf_s4_*.jsonl
  note "convert done: $(wc -l < data/hf_s4.jsonl) click examples"
fi

note "teach start"
echo $$ > teach.pid
exec $PY -u -m laya_player.teach --data data/hf_s4.jsonl --init ckpt_sim/raw0056.pt >> runs/stage4_teach.out 2>&1
