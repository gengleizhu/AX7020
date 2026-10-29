$ErrorActionPreference = 'Stop'

$workspaceRoot = [System.IO.Path]::GetFullPath('E:\zhugenglei.work\john').TrimEnd('\')
$targetNames = @(
    '.ax7020_vendor_tmp',
    'john-pynq-bcrypt',
    'john-pynq-descrypt',
    'john-pynq-descrypt8',
    'john-pynq-md5crypt8',
    'john-pynq-sha256crypt8',
    'john-pynq-sha512crypt4',
    'vcu118_fpga_1g_vivado2018_3',
    'vcu118_udp_compute',
    'john_hash_resource_eval'
)

$resolvedTargets = @()
$totalBytes = 0L

foreach ($name in $targetNames) {
    $candidate = Join-Path $workspaceRoot $name
    if (-not (Test-Path -LiteralPath $candidate -PathType Container)) {
        continue
    }

    $item = Get-Item -LiteralPath $candidate -Force
    $resolved = [System.IO.Path]::GetFullPath($item.FullName).TrimEnd('\')

    if (-not $resolved.StartsWith($workspaceRoot + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing target outside workspace: $resolved"
    }
    if ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
        throw "Refusing reparse-point target: $resolved"
    }
    if ($item.Name -ne $name) {
        throw "Target name mismatch: $resolved"
    }

    $bytes = (Get-ChildItem -LiteralPath $resolved -File -Recurse -Force | Measure-Object -Property Length -Sum).Sum
    $totalBytes += [long]$bytes
    $resolvedTargets += $resolved
}

foreach ($resolved in $resolvedTargets) {
    Remove-Item -LiteralPath $resolved -Recurse -Force
    Write-Output "REMOVED $resolved"
}

Write-Output ("RECLAIMED_GB_APPROX={0:N3}" -f ($totalBytes / 1GB))

$remaining = $targetNames | Where-Object {
    Test-Path -LiteralPath (Join-Path $workspaceRoot $_)
}
if ($remaining) {
    Write-Output 'REMAINING_TARGETS'
    $remaining
    exit 1
}

Write-Output 'CLEANUP_VERIFIED'
