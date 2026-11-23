[CmdletBinding()]
param(
    [ValidateRange(0.01, 86400)][double]$Duration = 20,
    [ValidateSet(1, 2, 4)][int[]]$Streams = @(1, 2, 4),
    [ValidateRange(0.01, 10000)][double]$Fps = 30,
    [ValidateRange(1, 10000)][int]$QueueSize = 3,
    [ValidateRange(1, 1000)][int]$Repeats = 1,
    [ValidateRange(0.01, 3600)][double]$Timeout = 60,
    [ValidateRange(0.01, 3600)][double]$DrainTimeout = 5,
    [string]$Python,
    [string]$OutputRoot,
    [switch]$Simulate,
    [ValidateRange(0.01, 60000)][double]$SimServiceMs = 12
)
$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$BuildPython = Join-Path $PSScriptRoot '.venv-build-win\Scripts\python.exe'
if ($Python) {
    $PythonExe = (Get-Command $Python -ErrorAction Stop).Source
} elseif (Test-Path -LiteralPath $BuildPython -PathType Leaf) {
    $PythonExe = $BuildPython
} else {
    $PythonExe = (Get-Command python -ErrorAction Stop).Source
}
$Culture = [Globalization.CultureInfo]::InvariantCulture
$RunnerArgs = @('-m', 'Cloud_test.run_e07_multicamera',
    '--duration', $Duration.ToString($Culture), '--fps', $Fps.ToString($Culture),
    '--queue-size', [string]$QueueSize, '--repeats', [string]$Repeats,
    '--timeout', $Timeout.ToString($Culture), '--drain-timeout', $DrainTimeout.ToString($Culture),
    '--streams')
foreach ($Count in $Streams) { $RunnerArgs += [string]$Count }
if ($OutputRoot) { $RunnerArgs += @('--output-root', $OutputRoot) }
if ($Simulate) {
    $RunnerArgs += @('--simulate', '--sim-service-ms', $SimServiceMs.ToString($Culture))
    Write-Host 'HOST_SIMULATION only: no FPGA or network throughput evidence.'
} else {
    Write-Host 'Stop every other collector. Keep the V2.5 SD card unchanged.'
    Write-Host 'Power-cycle the board only AFTER E07_COLLECTOR_LISTENING appears.'
}
Write-Host "Python: $PythonExe"
Write-Host "Active capture time: $($Duration * $Streams.Count * $Repeats) seconds, plus setup and drain."
$RunnerExit = 1
Push-Location -LiteralPath $ProjectRoot
try {
    & $PythonExe @RunnerArgs
    $RunnerExit = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $RunnerExit
