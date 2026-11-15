$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$PyInstaller = Join-Path $Root ".venv\Scripts\pyinstaller.exe"
if (-not (Test-Path $PyInstaller)) {
    throw "PyInstaller introuvable dans .venv. Lancez: .\.venv\Scripts\pip.exe install pyinstaller"
}

Write-Host "1/4 Verification des tests..."
& (Join-Path $Root ".venv\Scripts\python.exe") -m pytest -q

Write-Host "2/4 Compilation PyInstaller (Grimoire.exe)..."
if (Test-Path "$Root\dist\Grimoire") { Remove-Item -Recurse -Force "$Root\dist\Grimoire" }
if (Test-Path "$Root\build") { Remove-Item -Recurse -Force "$Root\build" }

& $PyInstaller --noconfirm --windowed --onedir --noupx `
    --name "Grimoire" `
    --icon "$Root\assets\grimoire.ico" `
    --paths "$Root\src" `
    --add-data "$Root\data;data" `
    --collect-submodules "bworkgrimoire" `
    --collect-all "PySide6.QtWebEngineWidgets" `
    --collect-all "PySide6.QtWebChannel" `
    "$Root\main.py"

Write-Host "3/4 Creation de l'installateur Inno Setup (Grimoire-Setup.exe)..."
$IsccCandidates = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
)
$Iscc = $IsccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Iscc) {
    throw "Inno Setup 6 (ISCC.exe) introuvable."
}
& $Iscc "$Root\installer\Grimoire.iss"

Write-Host "4/4 Creation du zip portable et SHA256SUMS.txt..."
$ZipPath = "$Root\dist\Grimoire-Windows.zip"
if (Test-Path $ZipPath) { Remove-Item -Force $ZipPath }
Compress-Archive -Path "$Root\dist\Grimoire\*" -DestinationPath $ZipPath

$SetupPath = "$Root\dist\Grimoire-Setup.exe"
$SetupHash = (Get-FileHash $SetupPath -Algorithm SHA256).Hash.ToLower()
$ZipHash = (Get-FileHash $ZipPath -Algorithm SHA256).Hash.ToLower()
@(
    "$SetupHash  Grimoire-Setup.exe",
    "$ZipHash  Grimoire-Windows.zip"
) | Out-File -Encoding ascii "$Root\dist\SHA256SUMS.txt"

Write-Host "Termine !"
Get-Content "$Root\dist\SHA256SUMS.txt"
