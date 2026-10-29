param(
 [string]$VivadoRoot='C:\Xilinx\Vivado\2018.3',
 [string]$Python='python'
)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
$vivado=Join-Path $VivadoRoot 'bin\vivado.bat'
$previousPython=$env:JOHN_PYTHON
Push-Location $projectRoot
try {
 $env:JOHN_PYTHON=& $Python -c "import sys; print(sys.executable)"
 if($LASTEXITCODE -ne 0){throw 'Python unavailable'}
 $runId=Get-Date -Format 'yyyyMMdd_HHmmss'
 $runRoot=Join-Path $projectRoot "reports\stage34_runs\$runId"
 New-Item -ItemType Directory -Force $runRoot | Out-Null
 & $Python scripts/prepare_integration.py
 if($LASTEXITCODE -ne 0){throw 'Preparation failed'}
 & $Python tests/test_codec.py | Tee-Object "$runRoot\codec.log"
 if($LASTEXITCODE -ne 0){throw 'Codec tests failed'}
 & $Python tests/test_integration.py | Tee-Object "$runRoot\software.log"
 if($LASTEXITCODE -ne 0){throw 'Software tests failed'}
 & $vivado -mode batch -source vivado/test_adapters.tcl -log "$runRoot\adapters.log" -journal "$runRoot\adapters.jou"
 if($LASTEXITCODE -ne 0){throw 'Adapters failed'}
 & $vivado -mode batch -source vivado/test_reset.tcl -log "$runRoot\reset.log" -journal "$runRoot\reset.jou"
 if($LASTEXITCODE -ne 0){throw 'Reset protection failed'}
 foreach($case in @(@(1,4),@(8,4),@(8,5))) {
   $n=$case[0]; $cost=$case[1]
   & $Python host/rtl_udp_demo.py --cores $n --cost $cost --vivado $vivado --output "$runRoot\udp_${n}_cost${cost}"
   if($LASTEXITCODE -ne 0){throw "UDP/RTL failed: $n cores cost $cost"}
 }
 # 用户要求直接8核，不执行2/4核验证。
 & $vivado -mode batch -source vivado/implement_multicore.tcl -log "$runRoot\pl8.log" -journal "$runRoot\pl8.jou" -tclargs 8
 if($LASTEXITCODE -ne 0){throw 'PL8 implementation command failed'}
 & $vivado -mode batch -source vivado/create_soc.tcl -log "$runRoot\soc8.log" -journal "$runRoot\soc8.jou"
 if($LASTEXITCODE -ne 0){throw 'SoC8 build failed'}
 & $Python scripts/audit_delivery.py
 if($LASTEXITCODE -ne 0){throw 'Bit/HWH audit failed'}
 & $Python scripts/report_integration.py --single "$runRoot\udp_1_cost4" --eight4 "$runRoot\udp_8_cost4" --eight5 "$runRoot\udp_8_cost5"
 if($LASTEXITCODE -ne 0){throw 'Evidence gate failed'}
 Write-Host 'OFFLINE_STAGE34_PASS (NOT BOARD TESTED)'
}
finally {
 $env:JOHN_PYTHON=$previousPython
 Pop-Location
}
