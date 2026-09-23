[CmdletBinding()]
param(
    [string]$Version = '2.0.0',
    [string]$CertificateThumbprint = '',
    [string]$PfxPath = '',
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
Set-Content -LiteralPath (Join-Path $stagingRoot 'portable.flag') -Encoding ASCII -Value 'portable'
Set-Content -LiteralPath (Join-Path $history 'README.txt') -Encoding UTF8 -Value @(
    'NetConfigLint stores optional privacy-minimized local history in this directory.'
    'Configuration text, filenames, object names, and addresses are not stored here.'
)

$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { $python = (Get-Command python).Source }
& $python (Join-Path $PSScriptRoot 'assemble_licenses.py') $stagingRoot
if ($LASTEXITCODE -ne 0) { throw 'Portable license assembly failed.' }
$signed = $false
if ($CertificateThumbprint -or $PfxPath) {
    $signTool = Get-ChildItem -Path (Join-Path ${env:ProgramFiles(x86)} 'Windows Kits\10\bin') -Filter signtool.exe -File -Recurse -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1
    if (-not $signTool) { throw 'SignTool was not found.' }
    $signArgs = @('sign', '/fd', 'SHA256', '/tr', 'http://timestamp.digicert.com', '/td', 'SHA256')
    if ($CertificateThumbprint) { $signArgs += @('/sha1', $CertificateThumbprint) }
    else {
        if (-not (Test-Path -LiteralPath $PfxPath)) { throw 'The requested PFX file does not exist.' }
        $signArgs += @('/f', (Resolve-Path -LiteralPath $PfxPath).Path)
        if ($env:WINDOWS_SIGNING_PASSWORD) { $signArgs += @('/p', $env:WINDOWS_SIGNING_PASSWORD) }
    }
    $executable = Join-Path $stagingRoot 'NetConfigLint.exe'
    & $signTool.FullName @signArgs $executable
    if ($LASTEXITCODE -ne 0) { throw 'Portable executable signing failed.' }
    $signature = Get-AuthenticodeSignature -LiteralPath $executable
    if ($signature.Status -ne 'Valid') { throw "Portable executable signature validation failed: $($signature.Status)" }
    $signed = $true
}
Compress-Archive -LiteralPath $stagingRoot -DestinationPath $archivePath -CompressionLevel Optimal
& $python (Join-Path $PSScriptRoot 'assemble_licenses.py') $archivePath --verify-archive
if ($LASTEXITCODE -ne 0) { throw 'Final ZIP license gate failed.' }
$archive = Get-Item -LiteralPath $archivePath
[pscustomobject]@{
    Archive = $archive.FullName
    Bytes = $archive.Length
    SHA256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $archive.FullName).Hash
    ExecutableSigned = $signed
} | Format-List
