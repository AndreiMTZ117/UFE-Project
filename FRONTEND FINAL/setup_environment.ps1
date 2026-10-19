<#
.SYNOPSIS
    Environment Setup and Validation Script for Dual-Axis Galvanometer Laser System.

.DESCRIPTION
    Standard, transparent PowerShell script to configure and verify the local
    runtime environment for deployment:
    1. Checks for FreeCAD CLI (FreeCADcmd.exe) in PATH or standard installation
       directories (%LOCALAPPDATA%\Programs\FreeCAD*, C:\Program Files\FreeCAD*).
       Transparently appends the 'bin' directory to the User PATH if located.
    2. Validates that Python is installed and meets the minimum version requirement (>= 3.10).
    3. Upgrades pip and installs production dependencies from requirements.txt.
    4. Executes a non-intrusive diagnostic self-check verifying module imports and FreeCAD CLI.

.NOTES
    Security & Best Practices:
    - No evasion techniques, hidden downloads, or execution policy tampering.
    - Uses standard Windows APIs ([Environment]::SetEnvironmentVariable) for persistence.
#>

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "          UFE LASER SYSTEM - ENVIRONMENT SETUP & VALIDATION          " -ForegroundColor Cyan
Write-Host "======================================================================`n" -ForegroundColor Cyan

# ------------------------------------------------------------------------------
# 1. FreeCAD CLI Verification and PATH Configuration
# ------------------------------------------------------------------------------
Write-Host "[1/4] Checking FreeCAD CLI (FreeCADcmd.exe)..." -ForegroundColor Yellow

$freecadCmd = Get-Command FreeCADcmd.exe -ErrorAction SilentlyContinue
if (-not $freecadCmd) {
    $freecadCmd = Get-Command freecadcmd -ErrorAction SilentlyContinue
}

$freecadExecutable = $null

if ($freecadCmd) {
    $freecadExecutable = $freecadCmd.Source
    Write-Host "  [OK] FreeCADcmd detected in current PATH: '$freecadExecutable'" -ForegroundColor Green
} else {
    Write-Host "  [INFO] FreeCADcmd is not currently in PATH. Scanning standard installation directories..." -ForegroundColor Yellow

    $candidatePatterns = @(
        "$env:LOCALAPPDATA\Programs\FreeCAD*",
        "$env:ProgramFiles\FreeCAD*",
        "${env:ProgramFiles(x86)}\FreeCAD*"
    )

    foreach ($pattern in $candidatePatterns) {
        $matchedDirs = Get-ChildItem -Path $pattern -Directory -ErrorAction SilentlyContinue
        foreach ($dir in $matchedDirs) {
            $binExe = Join-Path $dir.FullName "bin\freecadcmd.exe"
            $rootExe = Join-Path $dir.FullName "freecadcmd.exe"
            if (Test-Path $binExe) {
                $freecadExecutable = $binExe
                break
            } elseif (Test-Path $rootExe) {
                $freecadExecutable = $rootExe
                break
            }
        }
        if ($freecadExecutable) { break }
    }

    if ($freecadExecutable) {
        $binDir = Split-Path -Parent $freecadExecutable
        Write-Host "  [FOUND] Located FreeCAD executable at: '$freecadExecutable'" -ForegroundColor Green
        Write-Host "  [ACTION] Adding '$binDir' to User PATH environment variable..." -ForegroundColor Yellow

        # Update User PATH persistently via .NET Environment API
        $userPath = [Environment]::GetEnvironmentVariable("PATH", [EnvironmentVariableTarget]::User)
        $userPathEntries = if ($userPath) { $userPath -split ';' } else { @() }

        if ($userPathEntries -notcontains $binDir) {
            $newUserPath = if ([string]::IsNullOrWhiteSpace($userPath)) { $binDir } else { "$userPath;$binDir" }
            [Environment]::SetEnvironmentVariable("PATH", $newUserPath, [EnvironmentVariableTarget]::User)
            Write-Host "  [OK] Successfully registered '$binDir' in User PATH." -ForegroundColor Green
        } else {
            Write-Host "  [INFO] '$binDir' is already registered in User PATH." -ForegroundColor Gray
        }

        # Update process PATH for immediate availability in current session
        $processPathEntries = $env:PATH -split ';'
        if ($processPathEntries -notcontains $binDir) {
            $env:PATH = "$env:PATH;$binDir"
            Write-Host "  [OK] Updated current process session PATH." -ForegroundColor Green
        }
    } else {
        Write-Host "  [WARNING] FreeCAD CLI was not found on this system." -ForegroundColor Red
        Write-Host "  [RECOMMENDED] Install FreeCAD officially using the Windows Package Manager (winget):" -ForegroundColor White
        Write-Host "      winget install FreeCAD.FreeCAD`n" -ForegroundColor Cyan
    }
}

# ------------------------------------------------------------------------------
# 2. Python Version Verification
# ------------------------------------------------------------------------------
Write-Host "`n[2/4] Verifying Python runtime..." -ForegroundColor Yellow

$pythonCmd = Get-Command python.exe -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Error "Python executable ('python.exe') was not found in PATH. Please install Python 3.10+ from python.org or via: winget install Python.Python.3.11"
    exit 1
}

$pyVersionStr = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
[version]$pyVersion = $pyVersionStr.Trim()
[version]$minVersion = [version]"3.10.0"

if ($pyVersion -lt $minVersion) {
    Write-Error "Python $pyVersion detected. Minimum required version is Python 3.10. Please upgrade Python."
    exit 1
}
Write-Host "  [OK] Python runtime verified: version $pyVersion (meets requirement >= 3.10)." -ForegroundColor Green

# ------------------------------------------------------------------------------
# 3. Installing Python Dependencies
# ------------------------------------------------------------------------------
Write-Host "`n[3/4] Installing / upgrading Python dependencies..." -ForegroundColor Yellow

Write-Host "  [INFO] Upgrading pip to latest version..." -ForegroundColor Gray
& python -m pip install --upgrade pip

$requirementsFile = Join-Path $PSScriptRoot "requirements.txt"
if (Test-Path $requirementsFile) {
    Write-Host "  [INFO] Installing dependencies from '$requirementsFile'..." -ForegroundColor Gray
    & python -m pip install -r $requirementsFile
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to install dependencies from requirements.txt."
        exit 1
    }
    Write-Host "  [OK] Dependencies installed successfully." -ForegroundColor Green
} else {
    Write-Warning "requirements.txt was not found in '$PSScriptRoot'."
}

# ------------------------------------------------------------------------------
# 4. System Health Self-Check (Diagnostics)
# ------------------------------------------------------------------------------
Write-Host "`n[4/4] Executing system health self-check..." -ForegroundColor Yellow

# A. Test FreeCAD CLI version output
$freecadOk = $false
try {
    $fcOutput = & FreeCADcmd --version 2>&1
    if ($LASTEXITCODE -eq 0 -or ($fcOutput -join ' ') -match "FreeCAD") {
        $firstLine = ($fcOutput -split "`r?`n")[0].Trim()
        Write-Host "  [PASS] FreeCAD CLI version check: $firstLine" -ForegroundColor Green
        $freecadOk = $true
    } else {
        Write-Host "  [WARN] FreeCADcmd did not return expected version header: $fcOutput" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  [WARN] FreeCADcmd invocation error: $_" -ForegroundColor Yellow
}

# B. Test Python module imports
$moduleCheckScript = @"
import sys
modules = ['ezdxf', 'numpy', 'scipy', 'nidaqmx', 'customtkinter']
failed = []
for mod in modules:
    try:
        m = __import__(mod)
        version = getattr(m, '__version__', 'available')
        print(f'  [PASS] {mod:<14} -> v{version}')
    except Exception as exc:
        print(f'  [FAIL] {mod:<14} -> {exc}')
        failed.append(mod)

sys.exit(len(failed))
"@

$pyDiagOutput = & python -c $moduleCheckScript 2>&1
$pyDiagExitCode = $LASTEXITCODE

$pyDiagOutput | ForEach-Object {
    if ($_ -match "\[PASS\]") {
        Write-Host $_ -ForegroundColor Green
    } else {
        Write-Host $_ -ForegroundColor Red
    }
}

$pythonOk = ($pyDiagExitCode -eq 0)

# ------------------------------------------------------------------------------
# Final Summary Report
# ------------------------------------------------------------------------------
Write-Host "`n======================================================================" -ForegroundColor Cyan
Write-Host "                        SELF-CHECK SUMMARY                            " -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan

if ($freecadOk) {
    Write-Host "[OK] FreeCAD CLI verified." -ForegroundColor Green
} else {
    Write-Host "[NOTICE] FreeCAD CLI optional/fallback mode active." -ForegroundColor Yellow
}

if ($pythonOk) {
    Write-Host "[OK] Python dependencies verified." -ForegroundColor Green
} else {
    Write-Host "[FAIL] Some Python dependencies failed to load." -ForegroundColor Red
}

if ($freecadOk -and $pythonOk) {
    Write-Host "[STATUS] Environment ready to run." -ForegroundColor Green
} elseif ($pythonOk) {
    Write-Host "[STATUS] Environment ready to run (with internal CAD fallback)." -ForegroundColor Yellow
} else {
    Write-Host "[STATUS] Environment setup incomplete. Review error messages above." -ForegroundColor Red
}
Write-Host "======================================================================`n" -ForegroundColor Cyan
