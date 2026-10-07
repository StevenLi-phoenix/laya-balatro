# Chain: wait for the HF conversion -> pause simloop (needs the GPU) -> large imitation -> resume simloop.
# Usage: powershell -File run_imitate.ps1 -ConvertPid <pid>
param([int]$ConvertPid = 0, [Parameter(ValueFromRemainingArguments = $true)] $Rest)
$root = $PSScriptRoot
$py = Join-Path $root ".venv\Scripts\python.exe"
$env:PYTHONIOENCODING = "utf-8"
if ($ConvertPid) { Wait-Process -Id $ConvertPid -ErrorAction SilentlyContinue }
$sim = Get-Content (Join-Path $root "simloop.pid") -ErrorAction SilentlyContinue
if ($sim) { taskkill /PID $sim /T /F | Out-Null }
& $py -u -m laya_player.imitate --data data/hf_big.jsonl @Rest `
    1>> (Join-Path $root "runs_sim\imitate_stdout.txt") 2>> (Join-Path $root "runs_sim\imitate_stderr.txt")
& powershell -ExecutionPolicy Bypass -File (Join-Path $root "run_simloop.ps1")
