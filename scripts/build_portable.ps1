[CmdletBinding()]
param(
    [string]$Version = '1.2.0',
    [switch]$SkipAppBuild
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath (Split-Path -Parent $PSScriptRoot)).Path
$releaseRoot = Join-Path $projectRoot 'release'
$packageName = "NetConfigLint-$Version-windows-x64-portable"
$stagingRoot = Join-Path $releaseRoot $packageName
$archivePath = Join-Path $releaseRoot "$packageName.zip"

if (-not $SkipAppBuild) {
    & (Join-Path $PSScriptRoot 'build_windows.ps1')
    if ($LASTEXITCODE -ne 0) { throw 'Application build failed.' }
}

$distribution = Get-ChildItem -LiteralPath (Join-Path $projectRoot 'dist') -Directory -Filter '*.dist' |
    Select-Object -First 1
if (-not $distribution) { throw 'No standalone distribution was found under dist.' }
if (-not (Test-Path -LiteralPath (Join-Path $distribution.FullName 'NetConfigLint.exe'))) {
    throw 'The standalone distribution does not contain NetConfigLint.exe.'
}

New-Item -ItemType Directory -Path $releaseRoot -Force | Out-Null
$resolvedReleaseRoot = (Resolve-Path -LiteralPath $releaseRoot).Path
if (-not $stagingRoot.StartsWith($resolvedReleaseRoot + [IO.Path]::DirectorySeparatorChar)) {
    throw 'Refusing to stage outside the release directory.'
}
if (Test-Path -LiteralPath $stagingRoot) { Remove-Item -LiteralPath $stagingRoot -Recurse -Force }
if (Test-Path -LiteralPath $archivePath) { Remove-Item -LiteralPath $archivePath -Force }

Copy-Item -LiteralPath $distribution.FullName -Destination $stagingRoot -Recurse
Copy-Item -LiteralPath (Join-Path $projectRoot 'LICENSE') -Destination $stagingRoot
Copy-Item -LiteralPath (Join-Path $projectRoot 'THIRD_PARTY_NOTICES.md') -Destination $stagingRoot
$history = Join-Path $stagingRoot 'history'
New-Item -ItemType Directory -Path $history | Out-Null
Set-Content -LiteralPath (Join-Path $history 'README.txt') -Encoding UTF8 -Value @(
    'NetConfigLint stores optional privacy-minimized local history in this directory.'
    'Configuration text, filenames, object names, and addresses are not stored here.'
)

Compress-Archive -LiteralPath $stagingRoot -DestinationPath $archivePath -CompressionLevel Optimal
$archive = Get-Item -LiteralPath $archivePath
[pscustomobject]@{
    Archive = $archive.FullName
    Bytes = $archive.Length
    SHA256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $archive.FullName).Hash
} | Format-List
