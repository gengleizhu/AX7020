param(
    [string]$PortName = 'COM7',
    [Parameter(Mandatory = $true)][string]$Command,
    [int]$ReadMilliseconds = 3000
)

$ErrorActionPreference = 'Stop'
$port = [IO.Ports.SerialPort]::new(
    $PortName, 115200, [IO.Ports.Parity]::None, 8, [IO.Ports.StopBits]::One)
$port.Handshake = [IO.Ports.Handshake]::None
$port.DtrEnable = $false
$port.RtsEnable = $false
$port.ReadTimeout = 200

function Read-Serial([int]$Milliseconds) {
    $deadline = [DateTime]::UtcNow.AddMilliseconds($Milliseconds)
    $text = ''
    while ([DateTime]::UtcNow -lt $deadline) {
        $chunk = $port.ReadExisting()
        if ($chunk) {
            [Console]::Write($chunk)
            $text += $chunk
            if ($chunk.Contains("`e[6n")) { $port.Write("`e[1;1R") }
        }
        Start-Sleep -Milliseconds 20
    }
    return $text
}

try {
    $port.Open()
    $port.Write("`r")
    $initial = Read-Serial 700
    if ($initial -match 'login:') {
        $port.Write("root`r")
        $reply = Read-Serial 700
        if ($reply -match 'Password:') {
            $port.Write("root`r")
            [void](Read-Serial 900)
        }
    } elseif ($initial -match 'Password:') {
        $port.Write("root`r")
        [void](Read-Serial 900)
    }
    $marker = '__JOHN_UART_' + [Guid]::NewGuid().ToString('N') + '__'
    $port.Write($Command + "; rc=`$?; echo $marker`$rc`r")
    $output = Read-Serial $ReadMilliseconds
    if ($output -notmatch ([regex]::Escape($marker) + '(\d+)')) {
        throw "UART command did not return a completion marker"
    }
    if ([int]$Matches[1] -ne 0) {
        throw "Board command failed with rc=$($Matches[1])"
    }
} finally {
    if ($port.IsOpen) { $port.Close() }
    $port.Dispose()
}
