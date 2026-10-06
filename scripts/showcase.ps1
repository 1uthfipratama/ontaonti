# Switch the hub between a clean showcase database and your usual (test) data.
#
#   .\scripts\showcase.ps1 on      clean demo data (created and seeded on first use)
#   .\scripts\showcase.ps1 off     back to your usual database
#   .\scripts\showcase.ps1 reset   wipe the showcase database and seed it again
#
# Your usual data is never touched: the showcase lives in its own database
# ("onti_showcase") next to it. The choice is stored as ONTI_DB in .env, so it
# survives restarts until you switch back. Same sign-in as always.
param([Parameter(Mandatory = $true)][ValidateSet("on", "off", "reset")][string]$Mode)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$Db = "onti_showcase"

function Set-EnvDb([string]$Value) {
    # Rewrite .env without a BOM and with its own line endings, so Docker reads it.
    $path = Join-Path (Get-Location) ".env"
    $raw = [IO.File]::ReadAllText($path)
    $nl = if ($raw -match "`r`n") { "`r`n" } else { "`n" }
    $lines = @($raw -split "\r?\n" | Where-Object { $_ -notmatch '^ONTI_DB=' })
    while ($lines.Count -and $lines[-1] -eq "") { $lines = @($lines[0..($lines.Count - 2)]) }
    if ($Value) { $lines += "ONTI_DB=$Value" }
    [IO.File]::WriteAllText($path, (($lines -join $nl) + $nl), (New-Object Text.UTF8Encoding $false))
}

function Wait-Api {
    for ($i = 0; $i -lt 60; $i++) {
        try {
            if ((Invoke-WebRequest -UseBasicParsing http://localhost:8000/health -TimeoutSec 3).StatusCode -eq 200) { return }
        } catch { }
        Start-Sleep -Seconds 3
    }
    throw "The API didn't come up. Check: docker compose logs api"
}

function Invoke-Docker([string[]]$CommandArgs, [switch]$Quiet) {
    # Docker writes progress to stderr; Windows PowerShell would treat that as an
    # error, so judge success by the exit code instead.
    $old = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $out = & docker @CommandArgs 2>&1 | ForEach-Object { "$_" }
    $code = $LASTEXITCODE
    $ErrorActionPreference = $old
    if ($code -ne 0) { $out | Out-Host; throw "docker $($CommandArgs -join ' ') failed" }
    if (-not $Quiet) { $out | Out-Host }
    return
}

function Get-DockerOutput([string[]]$CommandArgs) {
    $old = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $out = & docker @CommandArgs 2>$null
    $ErrorActionPreference = $old
    return "$out".Trim()
}

if ($Mode -eq "off") {
    Set-EnvDb ""
    Invoke-Docker @("compose", "up", "-d") -Quiet
    Wait-Api
    Write-Host "Back on your usual data: http://localhost:3000"
    exit 0
}

Invoke-Docker @("compose", "up", "-d", "--wait", "db") -Quiet
if ($Mode -eq "reset") {
    Invoke-Docker @("compose", "stop", "api", "worker", "backup") -Quiet
    Invoke-Docker @("compose", "exec", "-T", "db", "dropdb", "-U", "onti", "--if-exists", $Db)
}
$exists = Get-DockerOutput @("compose", "exec", "-T", "db", "psql", "-U", "onti", "-d", "postgres", "-tAc", "select 1 from pg_database where datname = '$Db'")
if ($exists -ne "1") {
    Invoke-Docker @("compose", "exec", "-T", "db", "createdb", "-U", "onti", $Db)
    Write-Host "Created the showcase database."
}
Set-EnvDb $Db
Invoke-Docker @("compose", "up", "-d") -Quiet
Wait-Api
Invoke-Docker @("compose", "exec", "-T", "api", "python", "scripts/seed_demo.py")
Write-Host "Showcase is on: http://localhost:3000 (switch back: .\scripts\showcase.ps1 off)"
