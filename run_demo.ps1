# Run this from a normal PowerShell session, outside a restricted agent process.
$ErrorActionPreference = 'Stop'
$demoRoot = $PSScriptRoot
$demoPython = Join-Path $demoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $demoPython)) {
    throw 'Missing .venv. Create the Python environment and install requirements.txt first.'
}
Set-Location -LiteralPath $demoRoot
Write-Host 'Open http://localhost:8501/?demo=hcm then press Play.'
Write-Host 'The recorded road demo works without contacting OSRM; custom locations require Internet.'
& $demoPython -m streamlit run (Join-Path $demoRoot 'app.py') --server.address 127.0.0.1 --server.port 8501 --server.headless true --browser.gatherUsageStats false
exit $LASTEXITCODE
