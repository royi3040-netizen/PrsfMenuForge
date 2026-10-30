$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Assert-OK([string]$Task) {
    if ($LASTEXITCODE -ne 0) { throw "$Task failed, exit code $LASTEXITCODE" }
}

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$BuildRoot = $env:PRSFCOMPILATION_BUILD_WORK_DIR
$CacheRoot = $env:PRSFCOMPILATION_BUILD_CACHE_DIR
$Artifact = $env:PRSFCOMPILATION_BUILD_OUTPUT
if ([string]::IsNullOrWhiteSpace($BuildRoot) -or [string]::IsNullOrWhiteSpace($CacheRoot) -or [string]::IsNullOrWhiteSpace($Artifact)) {
    throw 'Launch this build through PrsfCompilation so managed DATA paths are provided.'
}

$Interpreter = Get-Command python.exe -ErrorAction SilentlyContinue
if ($null -eq $Interpreter) { throw 'Python 3.11 or newer must be available as python.exe.' }
$Venv = Join-Path $CacheRoot 'python-build-venv'
$Python = Join-Path $Venv 'Scripts/python.exe'
if (-not (Test-Path -LiteralPath $Python)) {
    New-Item -ItemType Directory -Force -Path $CacheRoot | Out-Null
    & $Interpreter.Source -m venv $Venv
    Assert-OK 'Python virtual environment'
}
$env:PIP_CACHE_DIR = Join-Path $CacheRoot 'pip-cache'
$env:PYINSTALLER_CONFIG_DIR = Join-Path $CacheRoot 'pyinstaller-cache'
$env:PYTHONPYCACHEPREFIX = Join-Path $CacheRoot 'python-pycache'
foreach ($Path in @($env:PIP_CACHE_DIR, $env:PYINSTALLER_CONFIG_DIR, $env:PYTHONPYCACHEPREFIX)) {
    New-Item -ItemType Directory -Force -Path $Path | Out-Null
}

$Requirements = Join-Path $ProjectRoot 'requirements.txt'
$Entry = Join-Path $ProjectRoot 'main.py'
foreach ($Path in @($Requirements, $Entry)) {
    if (-not (Test-Path -LiteralPath $Path)) { throw "Required source file is missing: $Path" }
}
& $Python -m pip install --disable-pip-version-check -r $Requirements 'pyinstaller>=6,<7'
Assert-OK 'PySide6 requirements and PyInstaller installation'

$Work = Join-Path $BuildRoot 'PrsfMenuForge'
if (Test-Path -LiteralPath $Work) { Remove-Item -LiteralPath $Work -Recurse -Force }
$Args = @(
    '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile', '--windowed',
    '--name', 'PrsfMenuForge', '--distpath', (Join-Path $Work 'dist'),
    '--workpath', (Join-Path $Work 'work'), '--specpath', (Join-Path $Work 'spec'),
    $Entry
)
& $Python @Args
Assert-OK 'PyInstaller'
$Exe = Join-Path $Work 'dist/PrsfMenuForge.exe'
if (-not (Test-Path -LiteralPath $Exe)) { throw 'Expected EXE was not created.' }
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Artifact) | Out-Null
Copy-Item -LiteralPath $Exe -Destination $Artifact -Force
Write-Host "SUCCESS: $Artifact"
