param(
    [string]$VivadoRoot = 'C:\Xilinx\Vivado\2018.3',
    [string]$Python = 'python',
    [switch]$SkipSynthesis
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$vivado = Join-Path $VivadoRoot 'bin\vivado.bat'
$gccDir = Join-Path $VivadoRoot 'tps\mingw\6.2.0\win64.o\nt\bin'
$gcc = Join-Path $gccDir 'gcc.exe'
if (!(Test-Path -LiteralPath $vivado)) { throw "Vivado 2018.3 not found: $vivado" }
if (!(Test-Path -LiteralPath $gcc)) { throw "Bundled GCC not found: $gcc" }
$originalPath = $env:PATH
Push-Location $projectRoot
try {
    New-Item -ItemType Directory -Force -Path 'logs\stage1','reports\stage1','build' | Out-Null
    & $vivado -version | Tee-Object 'logs\stage1\vivado_version.txt'
    if ($LASTEXITCODE -ne 0) {throw 'Vivado version check failed'}
    if (!(Select-String -LiteralPath 'logs\stage1\vivado_version.txt' -Pattern 'Vivado v2018.3' -Quiet)) {
        throw 'This project requires Vivado 2018.3'
    }
    if (!(Test-Path 'third_party\john\.git')) {
        & git clone --branch bleeding-jumbo https://github.com/gengleizhu/john.git third_party/john
        if ($LASTEXITCODE -ne 0) {throw 'John clone failed'}
        & git -C third_party/john checkout --detach 5184bc0b8c105f8c5978b112e723d65b2de3e63e
        if ($LASTEXITCODE -ne 0) {throw 'Pinned commit unavailable'}
    }
    & $Python scripts/prepare.py 2>&1 | Tee-Object 'logs\stage1\prepare.log'
    if ($LASTEXITCODE -ne 0) {throw 'Reference/source preparation failed'}
    $env:PATH = $gccDir + ';' + $env:PATH
    & $gcc -std=c99 -O2 -I third_party/john/src/ztex/pkt_comm tests/packet_oracle.c third_party/john/src/ztex/pkt_comm/pkt_comm.c -o build/packet_oracle.exe
    if ($LASTEXITCODE -ne 0) {throw 'Upstream C oracle build failed'}
    & .\build\packet_oracle.exe tests/c_packet_vectors.txt
    if ($LASTEXITCODE -ne 0) {throw 'C vectors failed'}
    & $Python tests/test_codec.py 2>&1 | Tee-Object 'logs\stage1\codec.log'
    if ($LASTEXITCODE -ne 0) {throw 'Python/C codec compatibility failed'}
    & $vivado -mode batch -source vivado/run_sim.tcl -log logs/stage1/simulation.log -journal logs/stage1/simulation.jou
    if ($LASTEXITCODE -ne 0) {throw 'RTL simulation failed'}
    & $Python scripts/check_packet_output.py 2>&1 | Tee-Object 'logs\stage1\packet_compare.log'
    if ($LASTEXITCODE -ne 0) {throw 'RTL packet byte comparison failed'}
    if (!$SkipSynthesis) {
        & $vivado -mode batch -source vivado/synth_single_core.tcl -log logs/stage1/synthesis.log -journal logs/stage1/synthesis.jou
        if ($LASTEXITCODE -ne 0) {throw 'Synthesis failed'}
    }
    & $Python scripts/report.py
    if ($LASTEXITCODE -ne 0) {throw 'Report verification failed'}
    Write-Host 'STAGE1_ALL_PASS'
}
finally {
    $env:PATH = $originalPath
    Pop-Location
}
