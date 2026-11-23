[CmdletBinding()]
param(
    [string]$PythonCommand = "py"
)

$ErrorActionPreference = "Stop"
if ($env:OS -ne "Windows_NT") {
    throw "This script must run on Windows 11 x64."
}

$WindowsRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$CloudRoot = Split-Path -Parent $WindowsRoot
$VenvRoot = Join-Path $WindowsRoot ".venv-build-win"
$VenvPython = Join-Path $VenvRoot "Scripts\python.exe"
$Spec = Join-Path $WindowsRoot "E06_Cloud_GUI.spec"
$Requirements = Join-Path $WindowsRoot "requirements-build.txt"
$ReleaseDir = Join-Path $CloudRoot "dist\E06_Cloud_GUI"
$ZipPath = Join-Path $CloudRoot "dist\E06_Cloud_GUI_Win11_x64.zip"

if (-not (Test-Path $VenvPython)) {
    & $PythonCommand -3 -m venv $VenvRoot
    if ($LASTEXITCODE -ne 0) { throw "Failed to create the build virtual environment." }
}

$PythonBits = (& $VenvPython -c "import struct; print(struct.calcsize('P') * 8)").Trim()
if ($LASTEXITCODE -ne 0) { throw "Failed to inspect Python architecture." }
if ($PythonBits -ne "64") {
    throw "Python must be a 64-bit interpreter; detected $PythonBits-bit."
}
$PythonMachine = (& $VenvPython -c "import platform; print(platform.machine())").Trim()
if ($LASTEXITCODE -ne 0) { throw "Failed to inspect Python machine architecture." }
if ($PythonMachine -notin @("AMD64", "x86_64")) {
    throw "Python must target AMD64/x86_64; detected $PythonMachine."
}
$PythonVersionOk = (& $VenvPython -c "import sys; print(str((3, 11) <= sys.version_info[:2] < (3, 14)).lower())").Trim()
if ($LASTEXITCODE -ne 0) { throw "Failed to inspect Python version." }
if ($PythonVersionOk -ne "true") {
    throw "Python 3.11, 3.12, or 3.13 is required."
}

& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Failed to upgrade pip." }
& $VenvPython -m pip install --requirement $Requirements
if ($LASTEXITCODE -ne 0) { throw "Failed to install build requirements." }

Push-Location $CloudRoot
try {
    & $VenvPython -m PyInstaller --clean --noconfirm $Spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }
}
finally {
    Pop-Location
}

foreach ($Name in @(
    "README_WIN11_CN.md",
    "Start_E06_Cloud_GUI.bat",
    "Configure-ZCU102-Network.ps1",
    "Restore-ZCU102-Network.ps1"
)) {
    Copy-Item -Force (Join-Path $WindowsRoot $Name) $ReleaseDir
}

$HashFile = Join-Path $ReleaseDir "SHA256SUMS.txt"
$ReleasePrefix = $ReleaseDir.TrimEnd('\') + '\'
$Lines = Get-ChildItem -Path $ReleaseDir -File -Recurse |
    Where-Object { $_.FullName -ne $HashFile } |
    Sort-Object FullName |
    ForEach-Object {
        $Relative = $_.FullName.Substring($ReleasePrefix.Length).Replace('\', '/')
        $Digest = (Get-FileHash -Algorithm SHA256 $_.FullName).Hash.ToLowerInvariant()
        "$Digest  $Relative"
    }
[System.IO.File]::WriteAllLines($HashFile, $Lines, [System.Text.UTF8Encoding]::new($false))

if (Test-Path $ZipPath) {
    Remove-Item -Force $ZipPath
}
Compress-Archive -Path $ReleaseDir -DestinationPath $ZipPath -CompressionLevel Optimal

Write-Host "WINDOWS_RELEASE_DIR=$ReleaseDir"
Write-Host "WINDOWS_RELEASE_ZIP=$ZipPath"
Write-Host "Run dist\E06_Cloud_GUI\Start_E06_Cloud_GUI.bat after configuring the dedicated Ethernet adapter."
