param(
    [string]$PortName = 'COM7',
    [string]$LogPath = '',
    [int]$CaptureSeconds = 50
)

$ErrorActionPreference = 'Stop'
if (-not $LogPath) {
    $LogPath = Join-Path $PWD ('ax7020_boot_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.log')
}
$parent = Split-Path -Parent $LogPath
if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }

$port = [IO.Ports.SerialPort]::new(
    $PortName, 115200, [IO.Ports.Parity]::None, 8, [IO.Ports.StopBits]::One)
$port.Handshake = [IO.Ports.Handshake]::None
$port.DtrEnable = $false
$port.RtsEnable = $false
$port.ReadTimeout = 200
$writer = [IO.StreamWriter]::new($LogPath, $false, [Text.UTF8Encoding]::new($false))
$writer.AutoFlush = $true

try {
    $port.Open()
    $port.DiscardInBuffer()
    $port.Write("sync; reboot`r")
    $deadline = [DateTime]::UtcNow.AddSeconds($CaptureSeconds)
    $tail = ''
    $loginSent = $false
    $passwordSent = $false
    while ([DateTime]::UtcNow -lt $deadline) {
        $chunk = $port.ReadExisting()
        if ($chunk) {
            [Console]::Write($chunk)
            $writer.Write($chunk)
            if ($chunk.Contains("`e[6n")) { $port.Write("`e[1;1R") }
            $tail = ($tail + $chunk)
            if ($tail.Length -gt 512) { $tail = $tail.Substring($tail.Length - 512) }
            if (-not $loginSent -and $tail -match 'login:') {
                $port.Write("root`r")
                $loginSent = $true
                $tail = ''
            } elseif ($loginSent -and -not $passwordSent -and $tail -match 'Password:') {
                $port.Write("root`r")
                $passwordSent = $true
                $tail = ''
            }
        }
        Start-Sleep -Milliseconds 20
    }
} finally {
    $writer.Dispose()
    if ($port.IsOpen) { $port.Close() }
    $port.Dispose()
}

Write-Host "Boot log: $LogPath"
