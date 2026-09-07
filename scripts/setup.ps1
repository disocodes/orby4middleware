param(
    [string[]]$Profile = @(),
    [string[]]$SkipService = @(),
    [switch]$DryRun,
    [switch]$Reconcile
)
$ErrorActionPreference = "Stop"

function Invoke-OrbyCommand([string[]]$Args) {
    if ($DryRun) { Write-Host ("DRYRUN docker " + ($Args -join " ")); return }
    & docker @Args
    if ($LASTEXITCODE -ne 0) { throw "docker $($Args -join ' ') failed with exit code $LASTEXITCODE" }
}

try {
    & docker compose version | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Docker Compose is unavailable" }

    $Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
    Set-Location $Root

    if (-not (Test-Path ".env")) {
        if (-not (Test-Path ".env.example")) { throw ".env and .env.example are both missing" }
        if ($DryRun) { Write-Host "CREATE .env from .env.example" }
        else { Copy-Item ".env.example" ".env"; Write-Host "CREATE .env from .env.example" }
    } else { Write-Host "SKIP   .env exists" }

    $ComposePrefix = @("compose")
    foreach ($p in $Profile) { $ComposePrefix += @("--profile", $p) }

    $desired = @(& docker @ComposePrefix config --services)
    if ($LASTEXITCODE -ne 0) { throw "Unable to read Compose services" }
    $existing = @(& docker @ComposePrefix ps -a --services 2>$null)
    $running = @(& docker @ComposePrefix ps --services --status running 2>$null)

    $order = [System.Collections.Generic.List[string]]::new()
    foreach ($s in @("postgres", "orby", "orthanc", "hapi-fhir")) { if ($desired -contains $s) { $order.Add($s) } }
    foreach ($s in $desired) { if (-not $order.Contains($s)) { $order.Add($s) } }

    foreach ($service in $order) {
        if ($SkipService -contains $service) {
            Write-Host "SKIP   $service (externally managed; ensure Orby connection settings point to it)"
            continue
        }

        if ($service -eq "orby" -and -not ($SkipService -contains "postgres") -and -not $DryRun) {
            $ready = $false
            for ($i=0; $i -lt 40; $i++) {
                & docker @ComposePrefix exec -T postgres pg_isready -U orby -d orby *> $null
                if ($LASTEXITCODE -eq 0) { $ready = $true; break }
                Start-Sleep -Seconds 2
            }
            if (-not $ready) { throw "postgres did not become ready; inspect docker compose logs postgres" }
        }

        if ($Reconcile) {
            Write-Host "RECONCILE $service"
            Invoke-OrbyCommand ($ComposePrefix + @("up", "-d", "--no-deps", $service))
        } elseif ($running -contains $service) {
            Write-Host "SKIP   $service already running"
        } elseif ($existing -contains $service) {
            Write-Host "START  existing $service"
            Invoke-OrbyCommand ($ComposePrefix + @("start", $service))
        } else {
            Write-Host "CREATE $service"
            Invoke-OrbyCommand ($ComposePrefix + @("up", "-d", "--no-deps", $service))
        }
    }

    if ($DryRun) { Write-Host "Dry run complete; no resources were changed." }
    else { Write-Host "orby4middleware setup complete."; & docker @ComposePrefix ps }
}
catch {
    Write-Error "orby4middleware setup FAILED: $($_.Exception.Message)"
    exit 1
}
