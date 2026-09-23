[CmdletBinding()]
param(
    [string]$Version = '2.0.0',
    [string]$CertificateThumbprint = '',
    [string]$PfxPath = '',
    [string]$WixBin = '',
    [switch]$SkipAppBuild
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath (Split-Path -Parent $PSScriptRoot)).Path
Set-Location -LiteralPath $projectRoot
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { $python = (Get-Command python -ErrorAction Stop).Source }

if (-not $SkipAppBuild) {
    & (Join-Path $PSScriptRoot 'build_windows.ps1')
    if ($LASTEXITCODE -ne 0) { throw 'Application build failed.' }
}

$distribution = Get-ChildItem -LiteralPath (Join-Path $projectRoot 'dist') -Directory -Filter '*.dist' | Select-Object -First 1
if (-not $distribution -or -not (Test-Path -LiteralPath (Join-Path $distribution.FullName 'NetConfigLint.exe'))) {
    throw 'A Windows standalone distribution containing NetConfigLint.exe is required.'
}

$installedCandle = Get-Command candle.exe -ErrorAction SilentlyContinue
$installedWix = if ($installedCandle) { Split-Path -Parent $installedCandle.Source } else { '' }
$wixCandidates = @(
    $WixBin,
    $installedWix,
    (Join-Path ${env:ProgramFiles(x86)} 'WiX Toolset v3.14\bin'),
    (Join-Path ${env:ProgramFiles(x86)} 'WiX Toolset v3.11\bin')
) | Where-Object { $_ -and (Test-Path -LiteralPath (Join-Path $_ 'candle.exe')) }
$wix = $wixCandidates | Select-Object -First 1
if (-not $wix) { throw 'WiX Toolset v3.11 or v3.14 is required to build the MSI.' }

$buildRoot = Join-Path $projectRoot 'build\msi'
$sourceRoot = Join-Path $buildRoot 'source'
$objectRoot = Join-Path $buildRoot 'obj'
New-Item -ItemType Directory -Path $buildRoot,$objectRoot,(Join-Path $projectRoot 'release') -Force | Out-Null
if (Test-Path -LiteralPath $sourceRoot) {
    $resolved = (Resolve-Path -LiteralPath $sourceRoot).Path
    if (-not $resolved.StartsWith((Resolve-Path -LiteralPath $buildRoot).Path + [IO.Path]::DirectorySeparatorChar)) {
        throw 'Refusing to replace an MSI source outside build\msi.'
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force
}
Copy-Item -LiteralPath $distribution.FullName -Destination $sourceRoot -Recurse
Copy-Item -LiteralPath (Join-Path $projectRoot 'LICENSE') -Destination $sourceRoot
Copy-Item -LiteralPath (Join-Path $projectRoot 'THIRD_PARTY_NOTICES.md') -Destination $sourceRoot
& $python (Join-Path $PSScriptRoot 'assemble_licenses.py') $sourceRoot
if ($LASTEXITCODE -ne 0) { throw 'MSI payload license assembly failed.' }

$licenseRtf = Join-Path $buildRoot 'LICENSE.rtf'
& $python (Join-Path $PSScriptRoot 'license_to_rtf.py') (Join-Path $projectRoot 'LICENSE') $licenseRtf
if ($LASTEXITCODE -ne 0) { throw 'Could not generate the MSI license page.' }

$signTool = Get-ChildItem -Path (Join-Path ${env:ProgramFiles(x86)} 'Windows Kits\10\bin') -Filter signtool.exe -File -Recurse -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1
$signed = $false
$signArgs = @()
if ($CertificateThumbprint -or $PfxPath) {
    if (-not $signTool) { throw 'SignTool was not found.' }
    $signArgs = @('sign', '/fd', 'SHA256', '/tr', 'http://timestamp.digicert.com', '/td', 'SHA256')
    if ($CertificateThumbprint) { $signArgs += @('/sha1', $CertificateThumbprint) }
    else {
        if (-not (Test-Path -LiteralPath $PfxPath)) { throw 'The requested PFX file does not exist.' }
        $signArgs += @('/f', (Resolve-Path -LiteralPath $PfxPath).Path)
        if ($env:WINDOWS_SIGNING_PASSWORD) { $signArgs += @('/p', $env:WINDOWS_SIGNING_PASSWORD) }
    }
    & $signTool.FullName @signArgs (Join-Path $sourceRoot 'NetConfigLint.exe')
    if ($LASTEXITCODE -ne 0) { throw 'Executable signing failed.' }
    $exeSignature = Get-AuthenticodeSignature -LiteralPath (Join-Path $sourceRoot 'NetConfigLint.exe')
    if ($exeSignature.Status -ne 'Valid') { throw "Executable signature validation failed: $($exeSignature.Status)" }
}

$heat = Join-Path $wix 'heat.exe'
$candle = Join-Path $wix 'candle.exe'
$light = Join-Path $wix 'light.exe'
$harvest = Join-Path $buildRoot 'ApplicationFiles.wxs'
& $heat dir $sourceRoot -nologo -cg ApplicationFiles -dr INSTALLFOLDER -gg -scom -sfrag -srd -sreg -var var.SourceDir -out $harvest
if ($LASTEXITCODE -ne 0) { throw 'WiX payload harvesting failed.' }

$defines = @("-dSourceDir=$sourceRoot", "-dProjectRoot=$projectRoot", "-dAppVersion=$Version", "-dLicenseRtf=$licenseRtf")
& $candle -nologo -arch x64 @defines -out "$objectRoot\" (Join-Path $projectRoot 'installer\NetConfigLint.wxs') $harvest
if ($LASTEXITCODE -ne 0) { throw 'WiX compilation failed.' }
$output = Join-Path $projectRoot "release\NetConfigLint-$Version-windows-x64.msi"
& $light -nologo -ext WixUIExtension -cultures:en-us -out $output (Join-Path $objectRoot 'NetConfigLint.wixobj') (Join-Path $objectRoot 'ApplicationFiles.wixobj')
if ($LASTEXITCODE -ne 0) { throw 'WiX linking failed.' }

if ($CertificateThumbprint -or $PfxPath) {
    & $signTool.FullName @signArgs $output
    if ($LASTEXITCODE -ne 0) { throw 'MSI signing failed.' }
    $signed = $true
}
if (-not $signed) {
    $unsigned = $output -replace '\.msi$', '-unsigned.msi'
    Move-Item -LiteralPath $output -Destination $unsigned -Force
    $output = $unsigned
}
$signature = Get-AuthenticodeSignature -LiteralPath $output
if ($signed -and $signature.Status -ne 'Valid') { throw "MSI signature validation failed: $($signature.Status)" }
[pscustomobject]@{
    Installer = $output
    Bytes = (Get-Item -LiteralPath $output).Length
    SHA256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $output).Hash
    SignatureStatus = $signature.Status
} | Format-List
