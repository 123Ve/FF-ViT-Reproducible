[CmdletBinding()]
param(
    [ValidateSet('Quick','Paper')][string]$Suite = 'Quick',
    [int]$GuiPort = 18082
)
$ErrorActionPreference = 'Stop'
$CloudRoot = Split-Path -Parent $PSScriptRoot
$Exe = Join-Path $CloudRoot 'dist\E07_Cloud_GUI\E07_Cloud_GUI.exe'
if (-not (Test-Path -LiteralPath $Exe -PathType Leaf)) {
    throw 'Build first: .\Cloud_test\windows\build_e07_windows.ps1'
}
if ($Suite -eq 'Quick') {
    # Four 15-second stages, one physical board connection.
    $RunArgs = @('--duration','15','--fps-list','10','--streams','2',
                 '--saturation','--repeats','1','--board-batches','10')
} else {
    # 3 trials x 3 stream counts x (4 rates + saturation) x 2 modes x 60 seconds = 90 min.
    $RunArgs = @('--duration','60','--fps-list','10','20','40','80','--streams','1','2','4',
                 '--saturation','--repeats','3','--board-batches','100')
}
Write-Host 'Stop all other collectors. Use the bundled V2.5 SD_CARD/BOOT.BIN (new firmware identity).'
Write-Host 'V2.5 adds bounded GEM recovery; physical qualification is still pending. Run Quick before Paper.'
Write-Host 'Power-cycle board only AFTER E07_COLLECTOR_LISTENING is printed.'
& $Exe @RunArgs --timeout 60 --gui-port $GuiPort --export-paper
exit $LASTEXITCODE
