#!/usr/bin/env bash
# (Re)start Stage 2 RL on n8; resumes from runs_sim/state.json + ckpt_sim/work.pt.
cd "$HOME/laya-player"
export LAYA_ACTIONS=raw PYTHONIOENCODING=utf-8 APPDATA="$PWD/profile"
nohup setsid .venv/bin/python -u -m laya_player.simloop --init ckpt/raw_init.pt "$@" \
  >> runs_sim/stdout.txt 2>> runs_sim/stderr.txt < /dev/null &
echo $! > simloop.pid
echo "$(date +%H:%M:%S) simloop (re)started: $*" >> runs/stage2.log
