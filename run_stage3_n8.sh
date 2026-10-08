#!/usr/bin/env bash
# Stage 3 on the GPU box (n8): the hand clicks carry computed consequences (LAYA_CALC=1, calc.py).
# No new kickoff: Stage 2's champion raw0056 reads the new text as is; then pure RL as in Stage 2.
#   nohup setsid ./run_stage3_n8.sh > runs/stage3_n8.out 2>&1 &
set -uo pipefail
cd "$(dirname "$0")"
export LAYA_ACTIONS=raw LAYA_CALC=1 PYTHONIOENCODING=utf-8 APPDATA="$PWD/profile"
PY=.venv/bin/python
note() { echo "$(date '+%F %T') $*" >> runs/stage3.log; }
ARGS="--batch 32 --lr 3e-6 --games 256 --test-games 128 --temperature 0.5 --epochs 2 --group 4 --credit best --promote-t 2.0"

if [ ! -f runs/ladder_calc.json ]; then  # zero-shot: raw0056 with the notes, on Stage 2's final ladder seeds
  note "zero-shot ladder start"
  $PY -u -m laya_player.ladder ckpt_sim/raw0056.pt --seeds-from runs/ladder.json --tag +calc \
    --out runs/ladder_calc.json >> runs/stage3.log 2>&1 || note "ladder FAILED"
fi

note "simloop (re)started: $ARGS"
echo $$ > simloop.pid
exec $PY -u -m laya_player.simloop $ARGS >> runs_sim/stdout.txt 2>> runs_sim/stderr.txt
