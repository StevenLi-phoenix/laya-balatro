# Stage 2 (raw clicks): teacher kickoff once, then pure RL in the simulator; real Balatro validates.
# Usage: powershell -File run_stage2.ps1
$root = $PSScriptRoot
Set-Location $root
$py = Join-Path $root ".venv\Scripts\python.exe"
$env:PYTHONIOENCODING = "utf-8"
$env:LAYA_ACTIONS = "raw"
$log = Join-Path $root "runs\stage2.log"
function Note($m) { Add-Content -Path $log -Value ("{0} {1}" -f (Get-Date -Format "HH:mm:ss"), $m) -Encoding utf8 }

# 1. archive the Stage 1 (combo-action) simulator runs
if ((Test-Path runs_sim) -and -not (Test-Path runs_sim_v2_combo)) { Move-Item runs_sim runs_sim_v2_combo }
if ((Test-Path ckpt_sim) -and -not (Test-Path ckpt_sim_v2_combo)) { Move-Item ckpt_sim ckpt_sim_v2_combo }

# 2. teacher decisions -> click sequences (kickoff data only)
if (-not (Test-Path data\hf_raw.jsonl)) {
    Note "convert start"
    & $py -u -m laya_player.hf_convert --per-shard 1500 --seed 11 --out data/hf_raw.jsonl 1>> runs\stage2_convert.txt 2>&1
    Note "convert done"
}

# 3. kickoff imitation from the Stage 1 champion
if (-not (Test-Path ckpt\raw_init.pt)) {
    Note "kickoff start"
    & $py -u -m laya_player.pretrain --data data/hf_raw.jsonl --init ckpt_sim_v2_combo/sim0053.pt `
        --out ckpt/raw_init.pt --eval-out runs/raw_init_eval.json 1>> runs\stage2_pretrain.txt 2>&1
    Note "kickoff done"
}

# 4. pure RL in the simulator (random seeds, head-to-head tests)
& powershell -ExecutionPolicy Bypass -File (Join-Path $root "run_simloop.ps1") --init ckpt/raw_init.pt
Note "simloop launched"

# 5. real Balatro validates the current champion on random seeds
$p = Start-Process -FilePath $py -ArgumentList @("-u", "-m", "laya_player.realloop") -WorkingDirectory $root `
    -RedirectStandardOutput (Join-Path $root "runs\realloop_stdout.txt") `
    -RedirectStandardError (Join-Path $root "runs\realloop_stderr.txt") -WindowStyle Hidden -PassThru
Set-Content -Path (Join-Path $root "realloop.pid") -Value $p.Id -Encoding ascii
Note "realloop launched pid $($p.Id)"
