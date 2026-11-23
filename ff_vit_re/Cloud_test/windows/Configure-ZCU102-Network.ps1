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

$Adapters = @(Get-NetAdapter -ErrorAction Stop | Where-Object { $_.Name -ceq $InterfaceAlias })
if ($Adapters.Count -ne 1) {
    throw "InterfaceAlias must identify exactly one adapter by its literal, case-sensitive name."
}
$Adapter = $Adapters[0]
$DefaultRoutes = @(Get-NetRoute -InterfaceIndex $Adapter.ifIndex -AddressFamily IPv4 `
    -ErrorAction Stop | Where-Object DestinationPrefix -eq "0.0.0.0/0")
if ($DefaultRoutes.Count -gt 0) {
    throw "Refusing to modify an interface with a default route. Select the dedicated ZCU102 Ethernet adapter."
}

$BackupPath = Join-Path $PSScriptRoot "network-backup.json"
if (Test-Path $BackupPath) {
    throw "Backup already exists at $BackupPath. Restore or archive it before configuring again."
}
$IpInterface = Get-NetIPInterface -InterfaceIndex $Adapter.ifIndex -AddressFamily IPv4
$Addresses = @(Get-NetIPAddress -InterfaceIndex $Adapter.ifIndex -AddressFamily IPv4 `
    -ErrorAction Stop | Select-Object IPAddress, PrefixLength)
$Backup = [ordered]@{
    schema = "fvit-zcu102-win11-network-backup-v1"
    InterfaceAlias = $InterfaceAlias
    InterfaceIndex = $Adapter.ifIndex
    Dhcp = [string]$IpInterface.Dhcp
    Addresses = $Addresses
}
if ($PSCmdlet.ShouldProcess($InterfaceAlias, "Set dedicated ZCU102 address 192.168.10.1/24")) {
    $Backup | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 $BackupPath
    Set-NetIPInterface -InterfaceIndex $Adapter.ifIndex -AddressFamily IPv4 -Dhcp Disabled
    foreach ($Address in @(Get-NetIPAddress -InterfaceIndex $Adapter.ifIndex `
            -AddressFamily IPv4 -ErrorAction Stop)) {
        Remove-NetIPAddress -InputObject $Address -Confirm:$false
    }
    New-NetIPAddress -InterfaceIndex $Adapter.ifIndex -IPAddress 192.168.10.1 `
        -PrefixLength 24 -AddressFamily IPv4 | Out-Null
    Get-NetIPAddress -InterfaceIndex $Adapter.ifIndex -AddressFamily IPv4 -ErrorAction Stop
    Write-Host "NETWORK_CONFIGURED=192.168.10.1/24"
    Write-Host "NETWORK_BACKUP=$BackupPath"
}
else {
    Write-Host "NETWORK_CONFIGURED=NO_CHANGE"
}
