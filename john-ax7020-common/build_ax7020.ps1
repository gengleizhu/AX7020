[CmdletBinding()]
param(
    [ValidateSet('all','bcrypt8','descrypt8','md5crypt8','sha256crypt8','sha512crypt4')]
    [string]$Project = 'all',

    [ValidateSet('validate-board','project','full','open')]
    [string]$Mode = 'project',

    [string]$Vivado = 'E:\Xilinx\Vivado\2020.1\bin\vivado.bat',
    [string]$PythonExe = ''
)

$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot

if (-not (Test-Path -LiteralPath $Vivado)) {
    throw "Vivado 2020.1 not found: $Vivado"
}

if ($Mode -eq 'validate-board') {
    & $Vivado -mode batch -source (Join-Path $PSScriptRoot 'vivado\validate_ps7_2020_1.tcl')
    exit $LASTEXITCODE
}

if (-not $PythonExe) {
    $PythonExe = (& py -3 -c 'import sys; print(sys.executable)' 2>$null | Select-Object -First 1)
}
if (-not $PythonExe -or -not (Test-Path -LiteralPath $PythonExe)) {
    throw 'Python 3 not found. Pass -PythonExe with an absolute path.'
}

$projects = [ordered]@{
    bcrypt8       = @{ Dir = 'john-ax7020-bcrypt8';      Xpr = 'build\soc8\john_ax7020_bcrypt8.xpr' }
    descrypt8     = @{ Dir = 'john-ax7020-descrypt8';    Xpr = 'build\soc\john_ax7020_descrypt8.xpr' }
    md5crypt8     = @{ Dir = 'john-ax7020-md5crypt8';    Xpr = 'build\soc\john_ax7020_md5crypt8.xpr' }
    sha256crypt8  = @{ Dir = 'john-ax7020-sha256crypt8'; Xpr = 'build\soc\john_ax7020_sha256crypt8.xpr' }
    sha512crypt4  = @{ Dir = 'john-ax7020-sha512crypt4'; Xpr = 'build\soc\john_ax7020_sha512crypt4.xpr' }
}

$selected = if ($Project -eq 'all') { @($projects.Keys) } else { @($Project) }

foreach ($name in $selected) {
    $item = $projects[$name]
    $projectDir = Join-Path $workspace $item.Dir
    $xpr = Join-Path $projectDir $item.Xpr

    if ($Mode -eq 'open') {
        if (-not (Test-Path -LiteralPath $xpr)) {
            throw "Project has not been generated: $xpr"
        }
        & $Vivado $xpr
        continue
    }

    $logDir = Join-Path $projectDir 'logs'
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
    $env:JOHN_PYTHON = $PythonExe
    if ($Mode -eq 'project') {
        $env:JOHN_BUILD_MODE = 'project'
    } else {
        Remove-Item Env:JOHN_BUILD_MODE -ErrorAction SilentlyContinue
    }

    try {
        $script = Join-Path $projectDir 'vivado\create_soc.tcl'
        Write-Host "[$name] mode=$Mode"
        & $Vivado -mode batch `
            -log (Join-Path $logDir "vivado_${Mode}.log") `
            -journal (Join-Path $logDir "vivado_${Mode}.jou") `
            -source $script
        if ($LASTEXITCODE -ne 0) {
            throw "$name failed with exit code $LASTEXITCODE"
        }
    }
    finally {
        Remove-Item Env:JOHN_BUILD_MODE -ErrorAction SilentlyContinue
        Remove-Item Env:JOHN_PYTHON -ErrorAction SilentlyContinue
    }
}

