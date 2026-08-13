[CmdletBinding()]
param(
    [string]$PythonExe = ".venv\Scripts\python.exe",
    [string]$BetaLabel = "beta1",
    [string]$OutputDirectory = "artifacts\windows",
    [switch]$SkipBuild,
    [switch]$SkipSmoke
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if (-not $IsWindows) {
    throw "The ProjektKraken Windows package must be built on Windows."
}
if ($BetaLabel -notmatch '^beta[1-9][0-9]*$') {
    throw "BetaLabel must match betaN, for example beta1."
}

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$repoPrefix = $repoRoot.TrimEnd('\') + '\'

function Get-SafeRepoPath {
    param([Parameter(Mandatory = $true)][string]$RelativePath)
    $fullPath = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $RelativePath))
    if (-not $fullPath.StartsWith($repoPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Packaging path escaped the repository: $fullPath"
    }
    return $fullPath
}

function Remove-SafeDirectory {
    param([Parameter(Mandatory = $true)][string]$Path)
    $fullPath = [System.IO.Path]::GetFullPath($Path)
    if (-not $fullPath.StartsWith($repoPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove a directory outside the repository: $fullPath"
    }
    if (Test-Path -LiteralPath $fullPath) {
        Remove-Item -LiteralPath $fullPath -Recurse -Force
    }
}

Push-Location $repoRoot
try {
    $pythonPath = (Resolve-Path -LiteralPath $PythonExe).Path
    $architecture = (& $pythonPath -c "import platform; print(platform.machine())").Trim()
    if ($LASTEXITCODE -ne 0 -or $architecture -notin @("AMD64", "x86_64")) {
        throw "Packaging requires 64-bit Python; found architecture '$architecture'."
    }

    $versionSource = Get-Content -Raw -LiteralPath "src\core\version.py"
    $versionMatch = [regex]::Match($versionSource, 'VERSION\s*=\s*"(?<value>\d+\.\d+\.\d+)"')
    if (-not $versionMatch.Success) {
        throw "Could not read VERSION from src/core/version.py."
    }
    $version = $versionMatch.Groups["value"].Value
    $projectSource = Get-Content -Raw -LiteralPath "pyproject.toml"
    $projectMatch = [regex]::Match($projectSource, '(?m)^version\s*=\s*"(?<value>\d+\.\d+\.\d+)"')
    if (-not $projectMatch.Success -or $projectMatch.Groups["value"].Value -ne $version) {
        throw "pyproject.toml and runtime versions do not match."
    }

    $packageName = "ProjektKraken-$version-$BetaLabel-windows-x64"
    $contract = Get-Content -Raw -LiteralPath `
        "packaging\windows\package-contract.json" | ConvertFrom-Json
    $buildRoot = Get-SafeRepoPath "build\windows-package"
    $distRoot = Get-SafeRepoPath "dist\windows-package"
    $artifactRoot = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $OutputDirectory))
    if (-not $artifactRoot.StartsWith($repoPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "OutputDirectory must remain inside the repository."
    }
    $stagingRoot = Join-Path $artifactRoot "staging"
    $packageRoot = Join-Path $stagingRoot $packageName
    $reportsRoot = Join-Path $artifactRoot "reports"
    $zipPath = Join-Path $artifactRoot "$packageName.zip"
    $checksumPath = "$zipPath.sha256"

    if (-not $SkipBuild) {
        Remove-SafeDirectory $buildRoot
        Remove-SafeDirectory $distRoot
        Remove-SafeDirectory $stagingRoot
        [System.IO.Directory]::CreateDirectory($buildRoot) | Out-Null
        [System.IO.Directory]::CreateDirectory($distRoot) | Out-Null
        [System.IO.Directory]::CreateDirectory($artifactRoot) | Out-Null
        [System.IO.Directory]::CreateDirectory($stagingRoot) | Out-Null

        $iconPath = Join-Path $buildRoot "ProjektKraken.ico"
        & $pythonPath scripts\generate_windows_icon.py `
            default_assets\icons\app_icons\Projekt_Kraken_Icon_32x32.png `
            $iconPath
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to generate the Windows executable icon."
        }

        $versionParts = $version.Split('.')
        $versionFilePath = Join-Path $buildRoot "windows-version-info.txt"
        $versionInfo = @"
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=($($versionParts[0]), $($versionParts[1]), $($versionParts[2]), 0),
    prodvers=($($versionParts[0]), $($versionParts[1]), $($versionParts[2]), 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable('040904B0', [
        StringStruct('CompanyName', 'ProjektKraken'),
        StringStruct('FileDescription', 'ProjektKraken worldbuilding application'),
        StringStruct('FileVersion', '$version'),
        StringStruct('InternalName', 'ProjektKraken'),
        StringStruct('OriginalFilename', 'ProjektKraken.exe'),
        StringStruct('ProductName', 'ProjektKraken'),
        StringStruct('ProductVersion', '$version $BetaLabel')
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"@
        Set-Content -LiteralPath $versionFilePath -Value $versionInfo -Encoding utf8

        $env:PK_WINDOWS_ICON = $iconPath
        $env:PK_WINDOWS_VERSION_FILE = $versionFilePath
        $buildLog = Join-Path $buildRoot "pyinstaller.log"
        & $pythonPath -m PyInstaller `
            --clean `
            --noconfirm `
            --distpath $distRoot `
            --workpath (Join-Path $buildRoot "work") `
            ProjektKraken.spec 2>&1 | Tee-Object -FilePath $buildLog
        if ($LASTEXITCODE -ne 0) {
            throw "PyInstaller failed. See $buildLog"
        }

        $allowedHiddenImportWarnings = @($contract.allowed_missing_hidden_imports)
        $unexpectedWarnings = Get-Content -LiteralPath $buildLog | Where-Object {
            if ($_ -match 'WARNING: Hidden import "(?<module>[^"]+)" not found') {
                $Matches["module"] -notin $allowedHiddenImportWarnings
            } else {
                $false
            }
        }
        if ($unexpectedWarnings) {
            throw "Unexpected hidden-import warnings:`n$($unexpectedWarnings -join "`n")"
        }

        $builtRoot = Join-Path $distRoot "ProjektKraken"
        if (-not (Test-Path -LiteralPath $builtRoot -PathType Container)) {
            throw "PyInstaller did not create the expected one-directory output."
        }
        Copy-Item -LiteralPath $builtRoot -Destination $packageRoot -Recurse -Force
    } elseif (-not (Test-Path -LiteralPath $packageRoot -PathType Container)) {
        throw "SkipBuild requested, but staged package does not exist: $packageRoot"
    }

    $stripDirectoryNames = @($contract.strip_and_forbid_recursive_directories)
    $stripDirectories = @(Get-ChildItem -LiteralPath $packageRoot -Recurse -Directory |
        Where-Object { $_.Name.ToLowerInvariant() -in $stripDirectoryNames } |
        Sort-Object { $_.FullName.Length } -Descending)
    foreach ($directory in $stripDirectories) {
        Remove-SafeDirectory $directory.FullName
    }
    $remainingForbiddenDirectories = @(Get-ChildItem `
        -LiteralPath $packageRoot -Recurse -Directory |
        Where-Object { $_.Name.ToLowerInvariant() -in $stripDirectoryNames })
    if ($remainingForbiddenDirectories) {
        throw "Test suites remain in the staged package."
    }

    foreach ($relativePath in $contract.required_package_paths) {
        $requiredPath = Join-Path $packageRoot $relativePath
        if (-not (Test-Path -LiteralPath $requiredPath)) {
            throw "Required package content is missing: $relativePath"
        }
    }

    $forbiddenNames = @($contract.forbidden_internal_directories)
    $forbidden = Get-ChildItem -LiteralPath (Join-Path $packageRoot "_internal") -Directory |
        Where-Object { $_.Name.ToLowerInvariant() -in $forbiddenNames }
    if ($forbidden) {
        throw "Development packages leaked into the bundle: $($forbidden.Name -join ', ')"
    }
    if (Get-ChildItem -LiteralPath $packageRoot -Recurse -File -Filter "python.exe") {
        throw "The package must not contain a Python command-line executable."
    }

    $exePath = Join-Path $packageRoot "ProjektKraken.exe"
    $stream = [System.IO.File]::OpenRead($exePath)
    $reader = $null
    try {
        $reader = [System.IO.BinaryReader]::new($stream)
        $stream.Position = 0x3c
        $peOffset = $reader.ReadInt32()
        $stream.Position = $peOffset + 4
        $machine = $reader.ReadUInt16()
    } finally {
        if ($reader) { $reader.Dispose() }
        $stream.Dispose()
    }
    if ($machine -ne 0x8664) {
        throw ('ProjektKraken.exe is not Windows x64; PE machine is 0x{0:X4}.' -f $machine)
    }

    $commit = (& git rev-parse HEAD).Trim()
    $pythonVersion = (& $pythonPath -c "import platform; print(platform.python_version())").Trim()
    $pyInstallerVersion = (& $pythonPath -c "import PyInstaller; print(PyInstaller.__version__)").Trim()
    $payloadFiles = Get-ChildItem -LiteralPath $packageRoot -Recurse -File
    $payloadBytes = ($payloadFiles | Measure-Object -Property Length -Sum).Sum
    $buildInfo = [ordered]@{
        product = "ProjektKraken"
        version = $version
        beta_label = $BetaLabel
        package_name = $packageName
        commit = $commit
        platform = "windows-x64"
        architecture = "x64"
        python_version = $pythonVersion
        pyinstaller_version = $pyInstallerVersion
        file_count = $payloadFiles.Count + 1
        payload_bytes = $payloadBytes
        unsigned = $true
    }
    $buildInfo | ConvertTo-Json -Depth 4 | Set-Content `
        -LiteralPath (Join-Path $packageRoot "build-info.json") `
        -Encoding utf8

    if (-not $SkipSmoke) {
        Remove-SafeDirectory $reportsRoot
        & (Join-Path $PSScriptRoot "test_packaged_windows.ps1") `
            -PackageRoot $packageRoot `
            -OutputDirectory $reportsRoot
        if ($LASTEXITCODE -ne 0) {
            throw "Packaged two-launch smoke failed."
        }
    }

    foreach ($runtimeDirectory in @("worlds", "logs")) {
        $runtimePath = Join-Path $packageRoot $runtimeDirectory
        if (Test-Path -LiteralPath $runtimePath) {
            Remove-SafeDirectory $runtimePath
        }
    }

    if (Test-Path -LiteralPath $zipPath) {
        Remove-Item -LiteralPath $zipPath -Force
    }
    if (Test-Path -LiteralPath $checksumPath) {
        Remove-Item -LiteralPath $checksumPath -Force
    }
    Compress-Archive -LiteralPath $packageRoot -DestinationPath $zipPath -CompressionLevel Optimal
    $hash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
    [System.IO.File]::WriteAllText(
        $checksumPath,
        "$hash  $([System.IO.Path]::GetFileName($zipPath))`n",
        [System.Text.UTF8Encoding]::new($false)
    )

    Write-Host "Windows package created: $zipPath"
    Write-Host "SHA-256: $hash"
    Write-Host "Checksum file: $checksumPath"
} finally {
    Remove-Item Env:PK_WINDOWS_ICON -ErrorAction SilentlyContinue
    Remove-Item Env:PK_WINDOWS_VERSION_FILE -ErrorAction SilentlyContinue
    Pop-Location
}
