param([string]$Vivado='C:\Xilinx\Vivado\2018.3\bin\vivado.bat')
$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
Push-Location $projectRoot
try {
    $python=Join-Path $projectRoot '.venv\Scripts\python.exe'
    if (!(Test-Path $python)) { throw 'Create .venv and install requirements.txt first' }
    $env:JOHN_PYTHON=$python
    & $python scripts/make_vectors.py
    if ($LASTEXITCODE) {throw 'Reference vectors failed'}
    & $python -m unittest discover -s host -p 'test_*.py' -v
    if ($LASTEXITCODE) {throw 'Host tests failed'}
    foreach ($run in @(@('test_known','known'),@('test','simulation'),@('test_invalid','invalid'),@('create_soc','build'))) {
        & $Vivado -mode batch -source "vivado/$($run[0]).tcl" -log "reports/$($run[1]).log" -journal "reports/$($run[1]).jou"
        if ($LASTEXITCODE) {throw "Vivado $($run[0]) failed"}
    }
    & $python scripts/audit.py
    if ($LASTEXITCODE) {throw 'Evidence audit failed'}
} finally {Pop-Location}
