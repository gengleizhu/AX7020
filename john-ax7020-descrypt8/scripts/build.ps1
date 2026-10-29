param([string]$VivadoRoot='C:\Xilinx\Vivado\2018.3')
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$oldPython=$env:JOHN_PYTHON
Push-Location $root
try {
 $python=Join-Path $root '.venv\Scripts\python.exe'
 if(!(Test-Path $python)){throw 'Create .venv and install requirements.txt first (see README).'}
 $env:JOHN_PYTHON=$python
 & $python scripts/make_vectors.py
 if($LASTEXITCODE){throw 'Reference generation failed'}
 & $python scripts/test_codec.py
 if($LASTEXITCODE){throw 'Host tests failed'}
 & $python scripts/test_codec8.py
 if($LASTEXITCODE){throw 'Eight-core host tests failed'}
 & $python scripts/test_board_mock.py
 if($LASTEXITCODE){throw 'DMA software mock tests failed'}
 $vivado=Join-Path $VivadoRoot 'bin\vivado.bat'
 & $vivado -mode batch -source vivado/test.tcl -log reports/simulation.log -journal reports/simulation.jou
 if($LASTEXITCODE -or !(Select-String -Path reports/simulation.log -Pattern '^DESCRYPT_TEST_PASS')){throw 'RTL test failed'}
 & $vivado -mode batch -source vivado/test8.tcl -log reports/simulation8.log -journal reports/simulation8.jou
 if($LASTEXITCODE -or !(Select-String -Path reports/simulation8.log -Pattern '^DESCRYPT8_TEST_PASS')){throw 'Eight-core RTL test failed'}
 & $vivado -mode batch -source vivado/create_soc.tcl -log reports/build.log -journal reports/build.jou
 if($LASTEXITCODE -or !(Select-String -Path reports/build.log -Pattern '^DESCRYPT_SOC_COMPLETE')){throw 'SoC build failed'}
 & $python scripts/audit.py
 if($LASTEXITCODE){throw 'Audit failed'}
} finally {$env:JOHN_PYTHON=$oldPython;Pop-Location}
