[CmdletBinding(SupportsShouldProcess=$true, ConfirmImpact="High")]
param(
    [Parameter(Mandatory=$true)]
    [string]$InterfaceAlias,
    [Parameter(Mandatory=$true)]
    [string]$ConfirmInterfaceAlias
)

$ErrorActionPreference = "Stop"
if ($InterfaceAlias -cne $ConfirmInterfaceAlias) {
    throw "InterfaceAlias and ConfirmInterfaceAlias must match exactly."
}
$Identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$Principal = [Security.Principal.WindowsPrincipal]::new($Identity)
if (-not $Principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run PowerShell as Administrator."
}

$BackupPath = Join-Path $PSScriptRoot "network-backup.json"
if (-not (Test-Path $BackupPath)) {
    throw "Missing network-backup.json; refusing to guess the previous network configuration."
}
$Backup = Get-Content -Raw $BackupPath | ConvertFrom-Json
if ($Backup.schema -ne "fvit-zcu102-win11-network-backup-v1" `
        -or $Backup.InterfaceAlias -cne $InterfaceAlias) {
    throw "Backup identity does not match InterfaceAlias."
}
$Adapters = @(Get-NetAdapter -ErrorAction Stop | Where-Object { $_.Name -ceq $InterfaceAlias })
if ($Adapters.Count -ne 1) {
    throw "InterfaceAlias must identify exactly one adapter by its literal, case-sensitive name."
}
$Adapter = $Adapters[0]
if ([int]$Backup.InterfaceIndex -ne $Adapter.ifIndex) {
    throw "Adapter index changed; restore manually after reviewing network-backup.json."
}
$DefaultRoutes = @(Get-NetRoute -InterfaceIndex $Adapter.ifIndex -AddressFamily IPv4 `
    -ErrorAction Stop | Where-Object DestinationPrefix -eq "0.0.0.0/0")
if ($DefaultRoutes.Count -gt 0) {
    throw "Refusing to restore an interface with a default route. Review the adapter manually."
}

if ($PSCmdlet.ShouldProcess($InterfaceAlias, "Restore saved IPv4 configuration")) {
    foreach ($Address in @(Get-NetIPAddress -InterfaceIndex $Adapter.ifIndex `
            -AddressFamily IPv4 -ErrorAction Stop)) {
        Remove-NetIPAddress -InputObject $Address -Confirm:$false
    }
    if ($Backup.Dhcp -eq "Enabled") {
        Set-NetIPInterface -InterfaceIndex $Adapter.ifIndex -AddressFamily IPv4 -Dhcp Enabled
    }
    else {
        Set-NetIPInterface -InterfaceIndex $Adapter.ifIndex -AddressFamily IPv4 -Dhcp Disabled
        foreach ($Address in @($Backup.Addresses)) {
            New-NetIPAddress -InterfaceIndex $Adapter.ifIndex `
                -IPAddress $Address.IPAddress -PrefixLength $Address.PrefixLength `
                -AddressFamily IPv4 | Out-Null
        }
    }
    Write-Host "NETWORK_RESTORED=$InterfaceAlias"
    Write-Host "Backup retained for audit: $BackupPath"
}
else {
    Write-Host "NETWORK_RESTORED=NO_CHANGE"
}
