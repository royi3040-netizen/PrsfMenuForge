$ErrorActionPreference = 'Stop'

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$BuildRoot = $env:PRSFCOMPILATION_BUILD_WORK_DIR
$CacheRoot = $env:PRSFCOMPILATION_BUILD_CACHE_DIR
$Artifact = $env:PRSFCOMPILATION_BUILD_OUTPUT
if (-not $BuildRoot -or -not $CacheRoot -or -not $Artifact) {
    throw 'PrsfCompilation build environment variables are missing.'
}

$Venv = Join-Path $CacheRoot 'venv'
$Python = Join-Path $Venv 'Scripts/python.exe'
$env:PIP_CACHE_DIR = Join-Path $CacheRoot 'pip-cache'
$env:PYINSTALLER_CONFIG_DIR = Join-Path $CacheRoot 'pyinstaller'
New-Item -ItemType Directory -Force -Path $CacheRoot, $env:PIP_CACHE_DIR, $env:PYINSTALLER_CONFIG_DIR, $BuildRoot | Out-Null

if (-not (Test-Path -LiteralPath $Python)) {
    python -m venv $Venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the build virtual environment.' }
}
& $Python -m pip install --disable-pip-version-check -r (Join-Path $ProjectRoot 'requirements.txt') pyinstaller
if ($LASTEXITCODE -ne 0) { throw 'Installing Python build dependencies failed.' }

$Work = Join-Path $BuildRoot 'PrsfMenuForge'
if (Test-Path -LiteralPath $Work) { Remove-Item -LiteralPath $Work -Recurse -Force }
New-Item -ItemType Directory -Force -Path $Work | Out-Null
$Args = @(
    '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile', '--windowed',
    '--name', 'PrsfMenuForge', '--distpath', (Join-Path $Work 'dist'),
    '--workpath', (Join-Path $Work 'work'), '--specpath', (Join-Path $Work 'spec'),
    (Join-Path $ProjectRoot 'main.py')
)
& $Python @Args
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed to build PrsfMenuForge.' }

$Exe = Join-Path $Work 'dist/PrsfMenuForge.exe'
if (-not (Test-Path -LiteralPath $Exe)) { throw 'Expected EXE was not created.' }
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Artifact) | Out-Null
Copy-Item -LiteralPath $Exe -Destination $Artifact -Force
