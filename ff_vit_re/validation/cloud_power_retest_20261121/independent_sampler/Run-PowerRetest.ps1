[CmdletBinding()]
param(
    [switch]$CheckOnly,
    [switch]$PrepareSD,
    [switch]$Acceptance,
    [switch]$Formal,
    [switch]$Target120Only,
    [switch]$Diagnostic17,
    [switch]$Diagnostic16,
    [switch]$Analyze,
    [string]$Session,
    [string]$SDRoot,
    [string]$SDReceipt,
    [string]$AcceptanceSession,
    [string]$Output,
    [string]$BoardId,
    [string]$Controls,
    [string]$Listen = '192.168.10.1',
    [int]$Port = 5001,
    [int]$Seconds = 120,
    [int]$Repetitions = 5,
    [int]$Timeout = 15,
    [string]$Python,
    [switch]$Help
)
$ErrorActionPreference = 'Stop'
if ($Diagnostic17 -and $Diagnostic16) { throw 'Choose only one diagnostic scope.' }
$launchers = @()
if ($Python) { $launchers += ,@($Python) }
if ($env:VIRTUAL_ENV) { $launchers += ,@((Join-Path $env:VIRTUAL_ENV 'Scripts/python.exe')) }
if ($env:CONDA_PREFIX) { $launchers += ,@((Join-Path $env:CONDA_PREFIX 'python.exe')) }
$launchers += ,@('py', '-3')
$launchers += ,@('python')
$chosen = $null
foreach ($candidate in $launchers) {
    $exe = $candidate[0]
    $prefix = @($candidate | Select-Object -Skip 1)
    if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
    try {
        & $exe @prefix -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' 2>$null
        if ($LASTEXITCODE -eq 0) { $chosen = $candidate; break }
    } catch { continue }
}
if (-not $chosen) { throw 'Python 3.11+ not found. Activate Python or use -Python full-path.' }
$cli = @('-B', '-S', (Join-Path $PSScriptRoot 'host/collect.py'))
if ($Help) { $cli += '--help' }
else {
    $actions = @($CheckOnly, $PrepareSD, $Acceptance, $Formal, $Analyze) | Where-Object { $_ }
    if ($actions.Count -ne 1) { throw 'Choose exactly one: -CheckOnly, -PrepareSD, -Acceptance, -Formal, -Analyze. Use -Help.' }
    if ($Analyze) {
        if (-not $Session -or -not $Output -or $Target120Only) { throw 'Analysis requires -Session and -Output.' }
        $cli = @('-B', '-S', (Join-Path $PSScriptRoot 'host/analyze.py'), $Session, '--output', $Output)
        if ($Diagnostic17) { $cli += '--diagnostic17' }
        if ($Diagnostic16) { $cli += '--diagnostic16' }
        if ($AcceptanceSession) { $cli += @('--acceptance-session', $AcceptanceSession) }
        $program = $chosen[0]
        $prefix = @($chosen | Select-Object -Skip 1)
        & $program @prefix @cli
        exit $LASTEXITCODE
    }
    if ($Diagnostic17) { $cli += '--diagnostic17' }
    if ($Diagnostic16) { $cli += '--diagnostic16' }
    if ($CheckOnly) { $cli += '--check-only' }
    if ($PrepareSD) { $cli += '--prepare-sd' }
    if ($Acceptance) { $cli += '--acceptance' }
    if ($Formal) { $cli += '--formal' }
    if ($Target120Only) {
        if (-not $Formal) { throw '-Target120Only requires -Formal.' }
        $cli += '--target120-only'
    }
    $pairs = @(
        @('--sd-root', $SDRoot), @('--sd-receipt', $SDReceipt),
        @('--acceptance-session', $AcceptanceSession), @('--output', $Output),
        @('--board-id', $BoardId), @('--controls', $Controls)
    )
    foreach ($pair in $pairs) { if ($pair[1]) { $cli += @($pair[0], $pair[1]) } }
    $cli += @('--listen', $Listen, '--port', "$Port", '--seconds', "$Seconds", '--repetitions', "$Repetitions", '--timeout', "$Timeout")
}
$program = $chosen[0]
$prefix = @($chosen | Select-Object -Skip 1)
# Argument arrays preserve spaces without manual shell-quoting or Invoke-Expression.
& $program @prefix @cli
exit $LASTEXITCODE
