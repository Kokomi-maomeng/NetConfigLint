[CmdletBinding()]
param(
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot

$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$deploy = Join-Path $projectRoot '.venv\Scripts\pyside6-deploy.exe'
$scripts = Join-Path $projectRoot '.venv\Scripts'
if (-not (Test-Path -LiteralPath $python) -or -not (Test-Path -LiteralPath $deploy)) {
    throw 'Create .venv and install .[dev,gui] before packaging.'
}

$svg = Join-Path $projectRoot 'netconfiglint\resources\icons\app.svg'
$ico = Join-Path $projectRoot 'netconfiglint\resources\icons\app.ico'
if (-not (Test-Path -LiteralPath $ico)) {
    & $python -c "from PySide6.QtGui import QImage; import sys; image=QImage(sys.argv[1]); image=image.scaled(256,256); raise SystemExit(0 if image.save(sys.argv[2]) else 1)" $svg $ico
    if ($LASTEXITCODE -ne 0) { throw 'Could not generate the Windows icon.' }
}

$env:PATH = $scripts + [IO.Path]::PathSeparator + $env:PATH
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$ignored = '.venv,.mypy_cache,.pytest_cache,.ruff_cache,build,dist,deployment,tests,docs,examples,scripts'
$arguments = @('-c', 'pysidedeploy.spec', '--force', "--extra-ignore-dirs=$ignored")
if ($DryRun) { $arguments += '--dry-run' }
$specPath = Join-Path $projectRoot 'pysidedeploy.spec'
$specSnapshot = [IO.File]::ReadAllText($specPath, [Text.Encoding]::UTF8)
try {
    & $deploy @arguments
    $deployExitCode = $LASTEXITCODE
}
finally {
    [IO.File]::WriteAllText($specPath, $specSnapshot, [Text.UTF8Encoding]::new($false))
    $generatedNestedSpec = Join-Path $projectRoot 'netconfiglint\pysidedeploy.spec'
    if (Test-Path -LiteralPath $generatedNestedSpec) {
        Remove-Item -LiteralPath $generatedNestedSpec
    }
}
if ($deployExitCode -ne 0) { throw "pyside6-deploy failed with exit code $deployExitCode" }

if (-not $DryRun) {
    $dist = Join-Path $projectRoot 'dist'
    if (-not (Test-Path -LiteralPath $dist)) { throw 'Packaging did not create the dist directory.' }

    # PySide6 6.11 + Nuitka may omit ABI/runtime DLLs when Visual Studio dumpbin is unavailable.
    # Copy the wheel-provided runtimes so the standalone build remains reproducible on clean builders.
    $distributionDirs = Get-ChildItem -LiteralPath $dist -Directory -Filter '*.dist'
    foreach ($distribution in $distributionDirs) {
        $pysideTarget = Join-Path $distribution.FullName 'PySide6'
        $shibokenTarget = Join-Path $distribution.FullName 'shiboken6'
        Get-ChildItem -LiteralPath (Join-Path $projectRoot '.venv\Lib\site-packages\PySide6') -Filter '*.dll' |
            Copy-Item -Destination $pysideTarget -Force
        Get-ChildItem -LiteralPath (Join-Path $projectRoot '.venv\Lib\site-packages\shiboken6') -Filter '*.dll' |
            Copy-Item -Destination $shibokenTarget -Force

        $generatedExe = Join-Path $distribution.FullName 'deploy_main.exe'
        $namedExe = Join-Path $distribution.FullName 'NetConfigLint.exe'
        if (Test-Path -LiteralPath $generatedExe) {
            Move-Item -LiteralPath $generatedExe -Destination $namedExe -Force
        }
    }

    $executables = Get-ChildItem -LiteralPath $dist -Filter '*.exe' -Recurse
    if (-not $executables) { throw 'Packaging completed without producing an executable.' }
    $executables | Select-Object FullName, Length, LastWriteTime
}
