[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Program,
    [string]$InterfaceAlias = '以太网',
    [switch]$DisableAppBlock
)
$ErrorActionPreference = 'Stop'
$ResolvedProgram = (Resolve-Path -LiteralPath $Program).Path
if (-not (Test-Path -LiteralPath $ResolvedProgram -PathType Leaf)) { throw 'Program must be an existing file.' }
$Blocked = @(Get-NetFirewallRule -PolicyStore PersistentStore -Enabled True -Direction Inbound -Action Block |
    Where-Object {
        $Rule = $_
        $App = $Rule | Get-NetFirewallApplicationFilter
        $Port = $Rule | Get-NetFirewallPortFilter
        ($App.Program -ieq $ResolvedProgram) -and ($Port.Protocol -in @('TCP','6','Any'))
    })
if ($Blocked.Count -gt 0) {
    $Blocked | Format-Table Name,DisplayName,Enabled,Action
    if (-not $DisableAppBlock) {
        throw 'Matching application Block rules found. Inspect them; rerun with -DisableAppBlock to disable only these rules.'
    }
    # Reversible: rules remain present and can be restored with Enable-NetFirewallRule -Name <Name>.
    $Blocked | Disable-NetFirewallRule
}
$RuleName = 'E07-V23-Board-TCP5001'
$Existing = Get-NetFirewallRule -Name $RuleName -ErrorAction SilentlyContinue
if ($Existing) {
    $Existing | Set-NetFirewallRule -Enabled True -Direction Inbound -Action Allow -Program $ResolvedProgram `
        -Protocol TCP -LocalAddress 192.168.10.1 -LocalPort 5001 -RemoteAddress 192.168.10.2 `
        -InterfaceAlias $InterfaceAlias -Profile Any
} else {
    New-NetFirewallRule -Name $RuleName -DisplayName 'E07 V2.3 board TCP5001' -Enabled True `
        -Direction Inbound -Action Allow -Program $ResolvedProgram -Protocol TCP `
        -LocalAddress 192.168.10.1 -LocalPort 5001 -RemoteAddress 192.168.10.2 `
        -InterfaceAlias $InterfaceAlias -Profile Any | Out-Null
}
Get-NetFirewallRule -Name $RuleName | Format-Table Name,Enabled,Direction,Action
