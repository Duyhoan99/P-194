[CmdletBinding()]
param(
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$frontendRoot = Join-Path $repoRoot "frontend"
$packageJson = Join-Path $frontendRoot "package.json"
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"

try {
    if (Test-Path -LiteralPath $venvPython) {
        $pythonCommand = $venvPython
    }
    else {
        $pythonCommand = (Get-Command python.exe -ErrorAction Stop).Source
    }

    $npmCommand = (Get-Command npm.cmd -ErrorAction Stop).Source

    if (-not (Test-Path -LiteralPath $packageJson)) {
        throw "Frontend package manifest was not found at $packageJson."
    }

    $nodeModules = Join-Path $frontendRoot "node_modules"
    if (-not (Test-Path -LiteralPath $nodeModules)) {
        throw "Frontend dependencies are missing. Run 'npm.cmd --prefix frontend install' first."
    }
}
catch {
    Write-Error $_
    exit 1
}

Write-Output "Validation passed."

if ($CheckOnly) {
    exit 0
}

$backendProcess = $null
$frontendProcess = $null
$exitCode = 0

try {
    if ([string]::IsNullOrWhiteSpace($env:NEXT_PUBLIC_API_URL)) {
        $env:NEXT_PUBLIC_API_URL = "http://localhost:8000"
    }

    $backendProcess = Start-Process `
        -FilePath $pythonCommand `
        -ArgumentList @(
            "-m",
            "uvicorn",
            "src.main:app",
            "--reload",
            "--host",
            "0.0.0.0",
            "--port",
            "8000"
        ) `
        -WorkingDirectory $repoRoot `
        -NoNewWindow `
        -PassThru

    $frontendProcess = Start-Process `
        -FilePath $npmCommand `
        -ArgumentList @("--prefix", "frontend", "run", "dev") `
        -WorkingDirectory $repoRoot `
        -NoNewWindow `
        -PassThru

    Write-Output "Backend:  http://localhost:8000"
    Write-Output "Frontend: http://localhost:3000"
    Write-Output "Press Ctrl+C to stop both services."

    while ($true) {
        Start-Sleep -Milliseconds 250
        $backendProcess.Refresh()
        $frontendProcess.Refresh()

        if ($backendProcess.HasExited) {
            $exitCode = [int]$backendProcess.ExitCode
            Write-Warning "Backend stopped with exit code $exitCode."
            break
        }

        if ($frontendProcess.HasExited) {
            $exitCode = [int]$frontendProcess.ExitCode
            Write-Warning "Frontend stopped with exit code $exitCode."
            break
        }
    }
}
catch {
    Write-Error $_
    $exitCode = 1
}
finally {
    foreach ($childProcess in @($backendProcess, $frontendProcess)) {
        if ($null -ne $childProcess) {
            $childProcess.Refresh()
            if (-not $childProcess.HasExited) {
                Stop-Process -Id $childProcess.Id -Force -ErrorAction SilentlyContinue
            }
        }
    }
}

exit $exitCode
