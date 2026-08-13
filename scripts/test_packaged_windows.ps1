[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$PackageRoot,
    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory,
    [int]$TimeoutSeconds = 300
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$packagePath = (Resolve-Path -LiteralPath $PackageRoot).Path
$exePath = Join-Path $packagePath "ProjektKraken.exe"
if (-not (Test-Path -LiteralPath $exePath -PathType Leaf)) {
    throw "Packaged executable not found: $exePath"
}

$reportDirectory = [System.IO.Path]::GetFullPath($OutputDirectory)
[System.IO.Directory]::CreateDirectory($reportDirectory) | Out-Null
$firstReportPath = Join-Path $reportDirectory "package-smoke-first-run.json"
$restartReportPath = Join-Path $reportDirectory "package-smoke-restart.json"
$summaryPath = Join-Path $reportDirectory "package-smoke-summary.json"

foreach ($runtimeDirectory in @("worlds", "logs")) {
    $runtimePath = Join-Path $packagePath $runtimeDirectory
    if (Test-Path -LiteralPath $runtimePath) {
        throw "Candidate package is not clean; found runtime directory: $runtimePath"
    }
}

function Invoke-PackagedSmoke {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,
        [Parameter(Mandatory = $true)]
        [string]$Phase
    )

    # CI runners and virtual machines do not provide a reliable GPU context.
    # Exercise the real Qt/WebEngine widgets through Qt's supported software
    # renderer; the clean-VM gate separately covers an ordinary double-click.
    $previousQtOpenGl = $env:QT_OPENGL
    $previousQuickBackend = $env:QSG_RHI_BACKEND
    $previousChromiumFlags = $env:QTWEBENGINE_CHROMIUM_FLAGS
    try {
        $env:QT_OPENGL = "software"
        $env:QSG_RHI_BACKEND = "software"
        $env:QTWEBENGINE_CHROMIUM_FLAGS = "--disable-gpu"
        $process = Start-Process `
            -FilePath $exePath `
            -ArgumentList $Arguments `
            -WorkingDirectory $packagePath `
            -WindowStyle Hidden `
            -PassThru
    }
    finally {
        $env:QT_OPENGL = $previousQtOpenGl
        $env:QSG_RHI_BACKEND = $previousQuickBackend
        $env:QTWEBENGINE_CHROMIUM_FLAGS = $previousChromiumFlags
    }
    if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
        Stop-Process -Id $process.Id -Force
        $logPath = Join-Path $packagePath "logs\kraken.log"
        if (Test-Path -LiteralPath $logPath -PathType Leaf) {
            Write-Host "Packaged $Phase smoke log tail:"
            Get-Content -LiteralPath $logPath -Tail 100 | Write-Host
        }
        throw "Packaged $Phase smoke timed out after $TimeoutSeconds seconds."
    }
    if ($process.ExitCode -ne 0) {
        throw "Packaged $Phase smoke exited with code $($process.ExitCode)."
    }
}

Invoke-PackagedSmoke -Phase "first-run" -Arguments @(
    "--reset-settings",
    "--package-smoke-phase", "first-run",
    "--package-smoke-report", $firstReportPath
)
if (-not (Test-Path -LiteralPath $firstReportPath -PathType Leaf)) {
    throw "First-run smoke report was not created."
}
$first = Get-Content -Raw -LiteralPath $firstReportPath | ConvertFrom-Json
if (-not $first.success -or [string]::IsNullOrWhiteSpace($first.world_id)) {
    throw "First-run smoke failed: $($first.errors -join '; ')"
}

Invoke-PackagedSmoke -Phase "restart" -Arguments @(
    "--package-smoke-phase", "restart",
    "--package-smoke-report", $restartReportPath,
    "--package-smoke-expected-world-id", $first.world_id
)
if (-not (Test-Path -LiteralPath $restartReportPath -PathType Leaf)) {
    throw "Restart smoke report was not created."
}
$restart = Get-Content -Raw -LiteralPath $restartReportPath | ConvertFrom-Json
if (-not $restart.success) {
    throw "Restart smoke failed: $($restart.errors -join '; ')"
}
if ($restart.world_id -ne $first.world_id) {
    throw "Restart opened world $($restart.world_id), expected $($first.world_id)."
}

$summary = [ordered]@{
    success = $true
    executable = $exePath
    version = $first.version
    world_id = $first.world_id
    world_name = $first.world_name
    first_run_report = $firstReportPath
    restart_report = $restartReportPath
    python_invoked_after_build = $false
}
$summary | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $summaryPath -Encoding utf8
Write-Host "Packaged two-launch smoke passed for world $($first.world_id)."
Write-Host "Summary: $summaryPath"
