$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Port = 8765
$Page = if ($args.Count -gt 0) { $args[0] } else { "model_showcase.html" }

Set-Location -LiteralPath $Root

function Read-DotEnv($key) {
    $envPath = Join-Path $Root ".env"
    if (-not (Test-Path -LiteralPath $envPath)) {
        return $null
    }
    foreach ($line in Get-Content -LiteralPath $envPath) {
        $trimmed = $line.Trim()
        if ($trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) {
            continue
        }
        $parts = $trimmed.Split("=", 2)
        if ($parts[0].Trim() -eq $key) {
            return $parts[1].Trim().Trim('"').Trim("'")
        }
    }
    return $null
}

function Test-WorkflowServer($candidatePort) {
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:$candidatePort/api/health" -UseBasicParsing -TimeoutSec 2
        return ($response.StatusCode -eq 200 -and $response.Content.Contains('"ok": true'))
    } catch {
        return $false
    }
}

function Test-PortFree($candidatePort) {
    return -not [bool](Get-NetTCPConnection -LocalPort $candidatePort -State Listen -ErrorAction SilentlyContinue)
}

if (-not (Test-WorkflowServer $Port)) {
    $pythonExe = Read-DotEnv "PYTHON_EXE"
    $python = if ($pythonExe -and (Test-Path -LiteralPath $pythonExe)) { [pscustomobject]@{ Source = $pythonExe; Name = Split-Path -Leaf $pythonExe } } else { Get-Command python -ErrorAction SilentlyContinue }
    $serverArgs = @("workflow_server.py", "--port", "$Port")
    if (-not $python) {
        $python = Get-Command py -ErrorAction SilentlyContinue
        $serverArgs = @("-3", "workflow_server.py", "--port", "$Port")
    }
    if (-not $python) {
        Write-Host "Python was not found. Cannot start the local workflow server."
        Write-Host "Set PYTHON_EXE in .env, for example: PYTHON_EXE=E:\app\anaconda\python.exe"
        Write-Host "Project path: $Root"
        Read-Host "Press Enter to exit"
        exit 1
    }

    if (-not (Test-PortFree $Port)) {
        foreach ($candidate in 8766..8780) {
            if ($candidate -eq 8787) {
                continue
            }
            if (Test-PortFree $candidate) {
                $Port = $candidate
                $serverArgs = if ($python.Name -eq "py.exe") { @("-3", "workflow_server.py", "--port", "$Port") } else { @("workflow_server.py", "--port", "$Port") }
                break
            }
        }
    }

    Start-Process -FilePath $python.Source -ArgumentList $serverArgs -WorkingDirectory $Root -WindowStyle Hidden
    Start-Sleep -Seconds 2
}

if (-not (Test-WorkflowServer $Port)) {
    Write-Host "Workflow server did not start correctly."
    Write-Host "Project path: $Root"
    Read-Host "Press Enter to exit"
    exit 1
}

$Url = "http://127.0.0.1:$Port/$Page"
cmd /c start "" $Url
Write-Host "Text to 3D Blender opened: ${Url}"
