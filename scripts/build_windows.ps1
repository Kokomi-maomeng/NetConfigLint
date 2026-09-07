[CmdletBinding()]
param(
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot

# Nuitka can retain obsolete data files in an existing standalone directory.
# Rebuild that generated payload so removed QML cannot reappear in a release.
if (-not $DryRun) {
    $distRoot = Join-Path $projectRoot 'dist'
    if (Test-Path -LiteralPath $distRoot) {
        $resolvedDistRoot = (Resolve-Path -LiteralPath $distRoot).Path
        foreach ($generatedDir in (Get-ChildItem -LiteralPath $resolvedDistRoot -Directory -Filter '*.dist')) {
            $resolvedGeneratedDir = (Resolve-Path -LiteralPath $generatedDir.FullName).Path
            if (-not $resolvedGeneratedDir.StartsWith($resolvedDistRoot + [IO.Path]::DirectorySeparatorChar)) {
                throw 'Refusing to clean a distribution outside dist.'
            }
            Remove-Item -LiteralPath $resolvedGeneratedDir -Recurse -Force
        }
    }
}

$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$deploy = Join-Path $projectRoot '.venv\Scripts\pyside6-deploy.exe'
if (-not (Test-Path -LiteralPath $python)) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCommand) { throw 'Python is required for packaging.' }
    $python = $pythonCommand.Source
}
if (-not (Test-Path -LiteralPath $deploy)) {
    $deployCommand = Get-Command pyside6-deploy -ErrorAction SilentlyContinue
    if (-not $deployCommand) { throw 'Install the gui dependencies before packaging.' }
    $deploy = $deployCommand.Source
}
$scripts = Split-Path -Parent $deploy

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

    # Resolve the PE import graph when Visual Studio dumpbin is unavailable. This avoids copying
    # every DLL from the PySide wheel while retaining a verifiable standalone dependency closure.
    $distributionDirs = Get-ChildItem -LiteralPath $dist -Directory -Filter '*.dist'
    foreach ($distribution in $distributionDirs) {
        $pruner = Join-Path $projectRoot 'scripts\prepare_windows_runtime.py'
        & $python $pruner $distribution.FullName
        if ($LASTEXITCODE -ne 0) { throw 'Could not prune the broad Qt deployment payload.' }

        $resolver = Join-Path $projectRoot 'scripts\resolve_windows_dlls.py'
        $sitePackages = & $python -c "import pathlib, site; print(next(path for path in map(pathlib.Path, site.getsitepackages()) if (path / 'PySide6').is_dir()))"
        & $python $resolver $distribution.FullName $sitePackages
        if ($LASTEXITCODE -ne 0) { throw 'Could not resolve the standalone DLL dependency closure.' }

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
