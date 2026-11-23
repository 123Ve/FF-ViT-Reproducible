[CmdletBinding()]
param([string]$PythonCommand = 'py')
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') { throw 'Build this executable on Windows x64.' }
$WindowsRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$CloudRoot = Split-Path -Parent $WindowsRoot
$Venv = Join-Path $WindowsRoot '.venv-build-win'
$Python = Join-Path $Venv 'Scripts\python.exe'
if (-not (Test-Path $Python)) {
    & $PythonCommand -3.13 -m venv $Venv
    if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.13 x64 or reuse a supported build venv.' }
}
& $Python -m pip install -r (Join-Path $WindowsRoot 'requirements-build.txt')
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
Push-Location $CloudRoot
try {
    & $Python -m PyInstaller --clean --noconfirm (Join-Path $WindowsRoot 'E07_Cloud_GUI.spec')
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed.' }
} finally { Pop-Location }
$Release = Join-Path $CloudRoot 'dist\E07_Cloud_GUI'
foreach ($File in @('Configure-ZCU102-Network.ps1', 'Restore-ZCU102-Network.ps1')) {
    Copy-Item (Join-Path $WindowsRoot $File) $Release -Force
}
Write-Host "E07_RELEASE=$Release"
Write-Host 'Run: .\E07_Cloud_GUI.exe --duration 60 --fps 10 --streams 1 2 4 --gui-port 18082'
