# Launch the Laya evolution loop as a detached process (survives the launching shell).
# Usage: powershell -File run_evolve.ps1 [-RestartGame] [extra evolve args...]
param([switch]$RestartGame, [Parameter(ValueFromRemainingArguments = $true)] $Rest)
$root = $PSScriptRoot
$py = Join-Path $root ".venv\Scripts\python.exe"
$env:PYTHONIOENCODING = "utf-8"
if ($RestartGame) {
    & $py -c "from laya_player import evolve; evolve.restart_game().close()"
}
$args = @("-u", "-m", "laya_player.evolve", "--runs-per-gen", "2", "--gen0-runs", "2") + $Rest
$p = Start-Process -FilePath $py -ArgumentList $args -WorkingDirectory $root `
    -RedirectStandardOutput (Join-Path $root "logs_evolve.txt") `
    -RedirectStandardError (Join-Path $root "logs_evolve_err.txt") -WindowStyle Hidden -PassThru
Set-Content -Path (Join-Path $root "evolve.pid") -Value $p.Id
"evolve pid $($p.Id)"
