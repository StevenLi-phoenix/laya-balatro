#!/usr/bin/env bash
# Stage 2 on the GPU box (n8): teacher kickoff once, then pure RL in the simulator.
# The real game validates on the Windows PC (realloop + remote_sync).
#   nohup setsid ./run_stage2_n8.sh > runs/stage2_n8.out 2>&1 &
set -uo pipefail
cd "$(dirname "$0")"
export LAYA_ACTIONS=raw PYTHONIOENCODING=utf-8 APPDATA="$PWD/profile"
PY=.venv/bin/python
note() { echo "$(date +%H:%M:%S) $*" >> runs/stage2.log; }

if [ ! -f data/hf_raw.jsonl ]; then
  note "convert start (20 shards in parallel)"
  for k in $(seq 0 19); do
    $PY -u -m laya_player.hf_convert --shards "$k-$k" --per-shard 1500 --seed $((11 + k)) \
      --out "data/hf_raw_$k.jsonl" > "runs/convert_$k.txt" 2>&1 &
  done
  wait
  cat data/hf_raw_{0..19}.jsonl > data/hf_raw.jsonl && rm -f data/hf_raw_*.jsonl
  note "convert done: $(wc -l < data/hf_raw.jsonl) click examples"
fi

if [ ! -f ckpt/raw_init.pt ]; then
  note "kickoff start"
  $PY -u -m laya_player.pretrain --data data/hf_raw.jsonl --init ckpt/sim0053.pt \
    --out ckpt/raw_init.pt --eval-out runs/raw_init_eval.json >> runs/stage2_pretrain.txt 2>&1 || { note "kickoff FAILED"; exit 1; }
  note "kickoff done: $(tail -n 1 runs/pretrain.log)"
fi

note "simloop start"
echo $$ > simloop.pid
exec $PY -u -m laya_player.simloop --init ckpt/raw_init.pt --batch 32 --lr 3e-6 --games 128 --test-games 128 --temperature 0.3 --epochs 2 --group 4 --credit seed >> runs_sim/stdout.txt 2>> runs_sim/stderr.txt
