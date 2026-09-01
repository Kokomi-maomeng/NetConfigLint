[CmdletBinding()]
param(
    [string]$Version = '1.3.0',
    [string]$NumericVersion = '1.3.0.0',
    [string]$CertificateThumbprint = '',
    [switch]$SkipAppBuild
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot

if (-not $SkipAppBuild) {
    & (Join-Path $PSScriptRoot 'build_windows.ps1')
    if ($LASTEXITCODE -ne 0) { throw 'Application build failed.' }
}

$isccCandidates = @(
    (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),
    (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe')
)
$iscc = $isccCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $iscc) { throw 'Inno Setup 6 is required to build the Windows installer.' }

$arguments = @(
    "/DAppVersion=$Version",
    "/DNumericVersion=$NumericVersion"
)
$signed = $false
if ($CertificateThumbprint) {
    $certificate = Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert |
        Where-Object Thumbprint -eq $CertificateThumbprint |
        Where-Object { $_.HasPrivateKey -and $_.NotAfter -gt (Get-Date) } |
        Select-Object -First 1
    if (-not $certificate) { throw 'No usable current-user code-signing certificate matches the thumbprint.' }

    $signTool = Get-ChildItem -Path (Join-Path ${env:ProgramFiles(x86)} 'Windows Kits\10\bin') `
        -Filter signtool.exe -File -Recurse -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending |
        Select-Object -First 1
    if (-not $signTool) { throw 'SignTool was not found. Install the Windows SDK signing tools.' }
    $signCommand = '$q' + $signTool.FullName + '$q sign /sha1 ' + $CertificateThumbprint +
        ' /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 $f'
    $arguments += "/Snetconfiglint=$signCommand", '/DSignedBuild=1'
    $signed = $true
}
$arguments += (Join-Path $projectRoot 'installer\NetConfigLint.iss')

& $iscc @arguments
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed with exit code $LASTEXITCODE" }

$installer = Get-ChildItem -LiteralPath (Join-Path $projectRoot 'release') `
    -Filter "NetConfigLint-$Version-windows-x64-setup.exe" |
    Select-Object -First 1
if (-not $installer) { throw 'Installer output was not created.' }
$signature = Get-AuthenticodeSignature -LiteralPath $installer.FullName
if ($signed -and $signature.Status -ne 'Valid') {
    throw "Installer signature validation failed: $($signature.Status)"
}
if (-not $signed) {
    $unsignedPath = Join-Path $installer.DirectoryName `
        "NetConfigLint-$Version-windows-x64-setup-unsigned.exe"
    Move-Item -LiteralPath $installer.FullName -Destination $unsignedPath -Force
    $installer = Get-Item -LiteralPath $unsignedPath
    $signature = Get-AuthenticodeSignature -LiteralPath $installer.FullName
}
[pscustomobject]@{
    Installer = $installer.FullName
    Bytes = $installer.Length
    SHA256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $installer.FullName).Hash
    SignatureStatus = $signature.Status
} | Format-List
