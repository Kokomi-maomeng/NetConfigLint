[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Archive,
    [Parameter(Mandatory = $true)][string]$Version,
    [Parameter(Mandatory = $true)][string]$OutputRoot,
    [string]$ExpectedSha256 = ''
)

$ErrorActionPreference = 'Stop'
$archivePath = (Resolve-Path -LiteralPath $Archive).Path
$sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $archivePath).Hash.ToLowerInvariant()
if ($ExpectedSha256 -and $sha256 -ne $ExpectedSha256.ToLowerInvariant()) { throw 'Archive checksum mismatch.' }
New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null
$outputPath = (Resolve-Path -LiteralPath $OutputRoot).Path
$unicodeName = -join ([char[]]@(0x89e3, 0x538b, 0x9a8c, 0x6536))
$extractPath = Join-Path $outputPath ($unicodeName + ' 空格-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $extractPath | Out-Null

# Verify archive entry paths before extraction, including the absolute resolved target.
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [IO.Compression.ZipFile]::OpenRead($archivePath)
try {
    foreach ($entry in $zip.Entries) {
        $target = [IO.Path]::GetFullPath((Join-Path $extractPath $entry.FullName))
        if (-not $target.StartsWith($extractPath + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
            throw 'Archive contains an entry outside its extraction directory.'
        }
    }
}
finally { $zip.Dispose() }
Expand-Archive -LiteralPath $archivePath -DestinationPath $extractPath
$executables = @(Get-ChildItem -LiteralPath $extractPath -Recurse -File -Filter NetConfigLint.exe)
if ($executables.Count -ne 1) { throw 'Expected exactly one NetConfigLint.exe.' }
$exe = $executables[0].FullName
$appRoot = $executables[0].DirectoryName
$versionInfo = [Diagnostics.FileVersionInfo]::GetVersionInfo($exe)
$requestedVersion = [version]$Version
$expectedVersion = [version]::new($requestedVersion.Major, $requestedVersion.Minor, [Math]::Max(0, $requestedVersion.Build), [Math]::Max(0, $requestedVersion.Revision))
if ([version]$versionInfo.ProductVersion -ne $expectedVersion -or [version]$versionInfo.FileVersion -ne $expectedVersion) {
    throw 'Windows executable version metadata does not match the requested release.'
}
$pe = [IO.File]::ReadAllBytes($exe)
$peOffset = [BitConverter]::ToInt32($pe, 0x3c)
$machine = [BitConverter]::ToUInt16($pe, $peOffset + 4)
$subsystem = [BitConverter]::ToUInt16($pe, $peOffset + 24 + 68)
if ($machine -ne 0x8664 -or $subsystem -ne 2) { throw 'Expected x64 GUI-subsystem executable.' }

function Start-Portable([string[]]$AppArguments, [bool]$Software) {
    $start = [Diagnostics.ProcessStartInfo]::new()
    $start.FileName = $exe
    $start.WorkingDirectory = $appRoot
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.WindowStyle = [Diagnostics.ProcessWindowStyle]::Hidden
    # The normal-launch acceptance intentionally shows the application's real GUI.
    if ($AppArguments.Count -eq 0) { $start.WindowStyle = [Diagnostics.ProcessWindowStyle]::Normal }
    if ($null -ne $start.ArgumentList) {
        foreach ($argument in $AppArguments) { $start.ArgumentList.Add($argument) }
    }
    else {
        $start.Arguments = ($AppArguments | ForEach-Object { '"' + $_ + '"' }) -join ' '
    }
    $processEnvironment = $start.Environment
    if ($null -eq $processEnvironment) { $processEnvironment = $start.EnvironmentVariables }
    $processEnvironment['PATH'] = $env:SystemRoot + '\System32;' + $env:SystemRoot
    foreach ($key in @('PYTHONPATH', 'PYTHONHOME', 'QT_PLUGIN_PATH', 'QML2_IMPORT_PATH', 'QML_IMPORT_PATH', 'QT_QPA_PLATFORM', 'QSG_RHI_BACKEND', 'QT_QUICK_BACKEND')) {
        $processEnvironment.Remove($key) | Out-Null
    }
    if ($Software) { $processEnvironment['QT_QUICK_BACKEND'] = 'software' }
    return [Diagnostics.Process]::Start($start)
}

$smokes = @()
foreach ($backend in @('native', 'software')) {
    $smokePath = Join-Path $outputPath $backend
    New-Item -ItemType Directory -Path $smokePath -Force | Out-Null
    $process = Start-Portable @('--smoke-test', $smokePath) ($backend -eq 'software')
    try {
        if (-not $process.WaitForExit(45000)) { $process.Kill(); throw 'Portable smoke timed out.' }
        if ($process.ExitCode -ne 0) { throw "Portable $backend smoke failed." }
        $smoke = Get-Content -LiteralPath (Join-Path $smokePath 'smoke-result.json') -Raw -Encoding UTF8 | ConvertFrom-Json
        if (-not $smoke.passed -or $smoke.version -ne $Version -or $smoke.exports -ne 3 -or $smoke.qml_errors.Count -ne 0) {
            throw "Portable $backend smoke report did not pass."
        }
        if ([version]$Version -ge [version]'1.5.0' -and $smoke.default_mode -ne 'snippet') {
            throw 'Portable application did not verify the default snippet mode.'
        }
        foreach ($extension in @('json', 'md', 'txt')) {
            $report = Get-Content -LiteralPath (Join-Path $smokePath "synthetic-report.$extension") -Raw -Encoding UTF8
            if ($report -notmatch 'HUA-VLAN-001') { throw "Missing diagnostic in $extension export." }
        }
        $smokes += @{ Backend = $backend; Passed = $true; Exports = $smoke.exports; QmlErrors = @($smoke.qml_errors) }
    }
    finally {
        if (-not $process.HasExited) { $process.Kill(); $process.WaitForExit() }
        $process.Dispose()
    }
}

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { $python = (Get-Command python -ErrorAction Stop).Source }
$standardUser = @()
foreach ($backend in @('native', 'software')) {
    $standardOutput = Join-Path $outputPath ('standard-user-' + $backend)
    $arguments = @((Join-Path $PSScriptRoot 'verify_windows_standard_user.py'), $exe, '--output', $standardOutput, '--version', $Version)
    if ($backend -eq 'software') { $arguments += '--software' }
    & $python @arguments
    if ($LASTEXITCODE -ne 0) { throw "Portable $backend acceptance without elevation failed." }
    $standardUser += Get-Content -LiteralPath (Join-Path $standardOutput 'standard-user-result.json') -Raw -Encoding UTF8 | ConvertFrom-Json
}

$normal = Start-Portable @() $false
try {
    $timer = [Diagnostics.Stopwatch]::StartNew()
    while ($timer.Elapsed.TotalSeconds -lt 20 -and -not $normal.HasExited) {
        $normal.Refresh()
        if ($normal.MainWindowHandle -ne [IntPtr]::Zero) { break }
        Start-Sleep -Milliseconds 200
    }
    if ($normal.HasExited -or $normal.MainWindowHandle -eq [IntPtr]::Zero) { throw 'Normal launch did not create a window.' }
    if (-not $normal.Responding) { throw 'Normal window is not responding.' }
    $processes = @(Get-CimInstance Win32_Process | Select-Object ProcessId, ParentProcessId, Name)
    $descendantIds = [Collections.Generic.HashSet[uint32]]::new()
    $descendantIds.Add([uint32]$normal.Id) | Out-Null
    do {
        $added = $false
        foreach ($child in $processes) {
            if ($descendantIds.Contains([uint32]$child.ParentProcessId)) {
                if ($descendantIds.Add([uint32]$child.ProcessId)) { $added = $true }
            }
        }
    } while ($added)
    $consoles = @($processes | Where-Object {
        $descendantIds.Contains([uint32]$_.ProcessId) -and $_.Name -in @('cmd.exe', 'conhost.exe', 'powershell.exe', 'pwsh.exe')
    })
    if ($consoles.Count -ne 0) { throw 'Normal GUI launch spawned a console process.' }
    if (-not $normal.CloseMainWindow() -or -not $normal.WaitForExit(10000)) { throw 'Normal window did not exit cleanly.' }
    if ($normal.ExitCode -ne 0) { throw 'Normal window exited with an error.' }
    $historyCreated = Test-Path -LiteralPath (Join-Path $appRoot 'history/history.json')
    if ($historyCreated) { throw 'Launch created a history file without an analysis request.' }
    $result = [ordered]@{
        Version = $Version; SHA256 = $sha256; Passed = $true; Architecture = 'x64'; Subsystem = $subsystem
        Smokes = $smokes; Responsive = $true; WindowCreated = $true; ConsoleChildren = 0
        StandardUser = $standardUser
        HistoryCreated = $historyCreated; SystemOnlyPath = $true; UnicodeAndSpacePath = $true; ExitConfirmed = $true
    }
    $result | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $outputPath 'acceptance.json') -Encoding UTF8
    $result | ConvertTo-Json -Depth 6
}
finally {
    if (-not $normal.HasExited) { $normal.Kill(); $normal.WaitForExit() }
    $normal.Dispose()
}
