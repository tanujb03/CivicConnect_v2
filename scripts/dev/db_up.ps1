<#
.SYNOPSIS
  Build the CivicConnect Postgres image (PostGIS + pgvector) and (re)create the civic-db container on port 5433 with a named volume.
  Also makes sure the civic-redis container (redis:7, port 6379) exists and runs.
.DESCRIPTION
  Port 5433 because a host PostgreSQL service may own 5432. Data lives in the named volume (default civic-pgdata) and survives container re-creation;
  pass -ResetData to drop it. Per-lane databases are created by scripts/dev/new_worktree.ps1.
.EXAMPLE
  .\scripts\dev\db_up.ps1
  .\scripts\dev\db_up.ps1 -PostgisTag 16-3.4 -Volume civic-pgdata-16 -ResetData
#>
[CmdletBinding()]
param(
    [string]$PostgisTag = "18-3.6",
    [string]$Image = "civicconnect-postgres:local",
    [string]$Container = "civic-db",
    [string]$Volume = "civic-pgdata",
    [int]$Port = 5433,
    [string]$Password = $(if ($env:POSTGRES_PASSWORD) { $env:POSTGRES_PASSWORD } else { "civic_dev_pwd" }),
    [string]$Database = "civicconnect",
    [switch]$ResetData
)
$ErrorActionPreference = "Stop"
$repo = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$script:DockerExit = 0

# Run docker and return its output lines; the exit code is left in $script:DockerExit. Windows PowerShell 5.1 turns a native command's stderr (docker build progress, psql
# NOTICE lines) into errors under $ErrorActionPreference = Stop, so stderr is merged and judged by exit code only.
function Dk {
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $out = & docker @args 2>&1 | ForEach-Object { if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.Exception.Message } else { "$_" } }
        $script:DockerExit = $LASTEXITCODE
    } finally { $ErrorActionPreference = $prev }
    $out
}

function Invoke-Docker {
    $out = Dk @args
    if ($script:DockerExit -ne 0) { throw "docker $($args -join ' ') failed (exit $($script:DockerExit)): $($out -join ' ')" }
    $out | ForEach-Object { Write-Host $_ }
}

function Psql([string]$Sql, [string]$Db = $Database) {
    ((Dk exec $Container psql -h 127.0.0.1 -U postgres -d $Db -v ON_ERROR_STOP=1 -tAc $Sql) -join "`n").Trim()
}

Invoke-Docker info --format "{{.ServerVersion}}"

Write-Host "Building $Image from postgis/postgis:$PostgisTag ..."
Invoke-Docker build -t $Image --build-arg "POSTGIS_TAG=$PostgisTag" (Join-Path $repo "infra\docker\postgres")

if (Dk ps -a --filter "name=^/$Container$" --format "{{.Names}}") {
    Write-Host "Removing existing container $Container (the data volume $Volume is kept)."
    Invoke-Docker rm -f $Container
}
if ($ResetData -and (Dk volume ls --filter "name=^$Volume$" --format "{{.Name}}")) {
    Write-Host "Dropping volume $Volume (-ResetData)."
    Invoke-Docker volume rm $Volume
}

# PostgreSQL 18+ images keep PGDATA under /var/lib/postgresql/<major>/docker, so the volume is mounted one level higher than before.
$major = [int]($PostgisTag -split "-")[0]
$mount = if ($major -ge 18) { "/var/lib/postgresql" } else { "/var/lib/postgresql/data" }
Write-Host "Starting $Container on port $Port (volume $Volume -> $mount) ..."
Invoke-Docker run -d --name $Container --restart unless-stopped -p "${Port}:5432" -e "POSTGRES_PASSWORD=$Password" -e "POSTGRES_DB=$Database" -v "${Volume}:$mount" $Image

# Ready over TCP (-h 127.0.0.1): the image's one-time init server only listens on the unix socket and restarts before the real server comes up.
for ($i = 0; $i -lt 90; $i++) {
    Dk exec $Container pg_isready -h 127.0.0.1 -U postgres -d $Database | Out-Null
    if ($script:DockerExit -eq 0) { break }
    Start-Sleep -Seconds 1
}
if ($script:DockerExit -ne 0) { throw "$Container did not become ready in 90 s (docker logs $Container)" }

Psql "CREATE EXTENSION IF NOT EXISTS postgis; CREATE EXTENSION IF NOT EXISTS vector;" | Out-Null
if ($script:DockerExit -ne 0) { throw "could not create the postgis/vector extensions in $Database" }

if (-not (Dk ps -a --filter "name=^/civic-redis$" --format "{{.Names}}")) {
    Invoke-Docker run -d --name civic-redis --restart unless-stopped -p 6379:6379 redis:7
} elseif (-not (Dk ps --filter "name=^/civic-redis$" --format "{{.Names}}")) {
    Invoke-Docker start civic-redis
}

Write-Host ""
Write-Host "PostgreSQL : $(Psql 'select version()')"
Write-Host "PostGIS    : $(Psql 'select postgis_version()')"
Write-Host "pgvector   : $(Psql "select extversion from pg_extension where extname='vector'")"
Write-Host "DATABASE_URL=postgresql+psycopg2://postgres:$Password@localhost:${Port}/$Database"
