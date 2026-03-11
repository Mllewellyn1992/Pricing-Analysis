$taskName = "ANZ Business Base Rate"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$batPath = Join-Path $scriptDir "run_scrape.bat"

schtasks /Create /F /SC DAILY /ST 07:30 /TN $taskName /TR "`"$batPath`""
