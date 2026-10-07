# Launch simulator self-play training as a detached process.
# Usage: powershell -File run_simloop.ps1 [simloop args...]
param([Parameter(ValueFromRemainingArguments = $true)] $Rest)
$root = $PSScriptRoot
$py = Join-Path $root ".venv\Scripts\python.exe"
$env:PYTHONIOENCODING = "utf-8"
New-Item -ItemType Directory -Force (Join-Path $root "runs_sim") | Out-Null
$args = @("-u", "-m", "laya_player.simloop")
if ($Rest) { $args += $Rest }
$p = Start-Process -FilePath $py -ArgumentList $args -WorkingDirectory $root `
    -RedirectStandardOutput (Join-Path $root "runs_sim\stdout.txt") `
    -RedirectStandardError (Join-Path $root "runs_sim\stderr.txt") -WindowStyle Hidden -PassThru
Set-Content -Path (Join-Path $root "simloop.pid") -Value $p.Id
"simloop pid $($p.Id)"
