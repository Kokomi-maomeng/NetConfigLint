[CmdletBinding()]
param([string]$Version = '2.0.0')

$ErrorActionPreference = 'Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or -not $env:RUNNER_TEMP) {
    throw 'This destructive installer acceptance script is restricted to an ephemeral GitHub Actions runner.'
}

$projectRoot = (Resolve-Path -LiteralPath (Split-Path -Parent $PSScriptRoot)).Path
$msi = Join-Path $projectRoot "release\NetConfigLint-$Version-windows-x64-unsigned.msi"
if (-not (Test-Path -LiteralPath $msi)) { throw "MSI not found: $msi" }
$uninstallRegistry = 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*'
$roamingRoot = Join-Path $env:APPDATA 'NetConfigLint'
$localRoot = Join-Path $env:LOCALAPPDATA 'NetConfigLint'
$settingsKey = 'HKCU:\Software\NetConfigLint'
$menuRoot = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\NetConfigLint'
$desktopShortcut = Join-Path ([Environment]::GetFolderPath('Desktop')) 'NetConfigLint.lnk'
$customBase = Join-Path $env:ProgramFiles 'NetConfigLintCITest'
$customExe = Join-Path $customBase 'NetConfigLint\NetConfigLint.exe'
$defaultExe = Join-Path $env:ProgramFiles 'NetConfigLint\NetConfigLint.exe'
$history = Join-Path $roamingRoot 'NetConfigLint\history\history.json'
$unrelated = Join-Path $env:LOCALAPPDATA 'NetConfigLintCITestUnrelated'

function Assert-State([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

function Get-InstalledProduct {
    @(Get-ItemProperty $uninstallRegistry -ErrorAction SilentlyContinue |
        Where-Object { $_.DisplayName -eq 'NetConfigLint' -and $_.DisplayVersion -eq $Version })
}

function Invoke-Msi([string[]]$Arguments, [string]$LogName) {
    $log = Join-Path $env:RUNNER_TEMP $LogName
    $process = Start-Process -FilePath "$env:SystemRoot\System32\msiexec.exe" -ArgumentList ($Arguments + @('/qn', '/norestart', '/L*v', ('"' + $log + '"'))) -Wait -PassThru -WindowStyle Hidden
    Assert-State ($process.ExitCode -eq 0) "msiexec failed with $($process.ExitCode); see $log"
}

Assert-State (@(Get-InstalledProduct).Count -eq 0) 'An existing NetConfigLint installation is present.'
foreach ($path in @($roamingRoot, $localRoot, $settingsKey, $customBase, $defaultExe, $unrelated)) {
    Assert-State (-not (Test-Path -LiteralPath $path)) "Pre-existing test target: $path"
}

Invoke-Msi -Arguments @('/i', ('"' + $msi + '"'), ('INSTALLBASE="' + $customBase + '"'), 'ADDLOCAL=ALL') -LogName 'msi-install-custom.log'
Assert-State (Test-Path -LiteralPath $customExe) 'Custom install did not append the product folder.'
Assert-State (Test-Path -LiteralPath (Join-Path $menuRoot 'NetConfigLint.lnk')) 'Start Menu shortcut missing.'
Assert-State (Test-Path -LiteralPath $desktopShortcut) 'Optional Desktop shortcut missing.'
& $customExe --smoke-test (Join-Path $env:RUNNER_TEMP 'msi-smoke-custom')
Assert-State ($LASTEXITCODE -eq 0) 'Custom-install executable smoke failed.'

New-Item -ItemType Directory -Path (Split-Path -Parent $history), $localRoot, $unrelated -Force | Out-Null
Set-Content -LiteralPath $history -Value '{"synthetic_msi_test":true}' -Encoding UTF8
Set-Content -LiteralPath (Join-Path $localRoot 'synthetic-cache.txt') -Value 'synthetic' -Encoding UTF8
Set-Content -LiteralPath (Join-Path $unrelated 'must-survive.txt') -Value 'synthetic' -Encoding UTF8
New-Item -Path (Join-Path $settingsKey 'NetConfigLint') -Force | Out-Null
New-ItemProperty -Path (Join-Path $settingsKey 'NetConfigLint') -Name SyntheticMsiTest -Value 1 -PropertyType DWord -Force | Out-Null
$beforeHash = (Get-FileHash -LiteralPath $history -Algorithm SHA256).Hash
$product = @(Get-InstalledProduct)
Assert-State ($product.Count -eq 1) 'Expected one installed product after custom installation.'
Invoke-Msi -Arguments @('/x', $product[0].PSChildName) -LogName 'msi-uninstall-keep.log'
Assert-State (-not (Test-Path -LiteralPath $customExe)) 'Keep-data uninstall left application files.'
Assert-State (-not (Test-Path -LiteralPath $menuRoot)) 'Keep-data uninstall left Start Menu shortcuts.'
Assert-State (-not (Test-Path -LiteralPath $desktopShortcut)) 'Keep-data uninstall left Desktop shortcut.'
Assert-State ((Get-FileHash -LiteralPath $history -Algorithm SHA256).Hash -eq $beforeHash) 'Keep-data uninstall changed history.'

Invoke-Msi -Arguments @('/i', ('"' + $msi + '"')) -LogName 'msi-install-default.log'
Assert-State (Test-Path -LiteralPath $defaultExe) 'Default installation executable missing.'
Assert-State (Test-Path -LiteralPath (Join-Path $menuRoot 'NetConfigLint.lnk')) 'Default Start Menu shortcut missing.'
Assert-State (-not (Test-Path -LiteralPath $desktopShortcut)) 'Optional Desktop shortcut unexpectedly installed.'
& $defaultExe --smoke-test (Join-Path $env:RUNNER_TEMP 'msi-smoke-default')
Assert-State ($LASTEXITCODE -eq 0) 'Default-install executable smoke failed.'
$product = @(Get-InstalledProduct)
Assert-State ($product.Count -eq 1) 'Expected one installed product after default installation.'
Invoke-Msi -Arguments @('/x', $product[0].PSChildName, 'REMOVEUSERDATA=1') -LogName 'msi-uninstall-delete.log'
Assert-State (-not (Test-Path -LiteralPath $defaultExe)) 'Delete-all uninstall left application files.'
Assert-State (-not (Test-Path -LiteralPath $menuRoot)) 'Delete-all uninstall left Start Menu shortcuts.'
Assert-State (-not (Test-Path -LiteralPath $roamingRoot)) 'Delete-all uninstall left Roaming data.'
Assert-State (-not (Test-Path -LiteralPath $localRoot)) 'Delete-all uninstall left Local data.'
Assert-State (-not (Test-Path -LiteralPath $settingsKey)) 'Delete-all uninstall left HKCU settings.'
Assert-State (Test-Path -LiteralPath (Join-Path $unrelated 'must-survive.txt')) 'Delete-all uninstall damaged an unrelated folder.'
Write-Output 'Windows MSI two-cycle acceptance passed.'
