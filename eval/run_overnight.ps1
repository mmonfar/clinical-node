# Starts the live debate evaluation for up to 9 hours. Resumable: run it again with the
# same RunId and finished cases are skipped. Needs Ollama running (this script does not start it).
# This script does not create a scheduled task. Research software, synthetic cases only.
param([string]$RunId = "overnight-1", [double]$Hours = 9)
$ErrorActionPreference = "Continue"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
$logDir = Join-Path $repo "eval\runs"
New-Item -ItemType Directory -Force $logDir | Out-Null
$log = Join-Path $logDir ("{0}_{1:yyyyMMdd_HHmmss}.log" -f $RunId, (Get-Date))
$py = Join-Path $repo ".venv\Scripts\python.exe"
& $py -m debate.eval --live --run-id $RunId --hours $Hours *>&1 | Tee-Object -FilePath $log
"Log: $log"
"Report: " + (Join-Path $logDir "$RunId\report.md")
