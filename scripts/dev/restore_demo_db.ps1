<#
.SYNOPSIS
  Restores a demo snapshot made by snapshot_demo_db.ps1: DROPS the target database and recreates it from the dump (extensions postgis and vector come with the dump).
.DESCRIPTION
  Needs -Yes because it destroys the target database's current content. Stored embeddings are part of the snapshot, so a restore NEVER re-embeds the cases (the embedding quota is
  1000 inputs a day): nothing here calls a provider, and it does not start the backfill. Stop the API first (an open connection is terminated, DROP ... WITH (FORCE)). Database names are lowercase letters, digits and _ only. The container must be a local one. -Snapshot is a path or a snapshot name
  (default: the newest in D:\ml-cache\snapshots). Afterwards run `python -m alembic current` if you restore into a different checkout.
#>
param(
    [string]$Snapshot = "",
    [ValidatePattern('^[a-z0-9_]+$')][string]$Database = "civicconnect",
    [ValidatePattern('^[A-Za-z0-9_.-]+$')][string]$Container = "civic-db",
    [string]$Dir = "D:\ml-cache\snapshots",
    [switch]$Yes
)
$ErrorActionPreference = "Stop"
if (-not $Yes) { throw "This drops database '$Database' and restores the snapshot over it. Re-run with -Yes." }
if ($Snapshot -eq "") { $file = Get-ChildItem $Dir -Filter *.dump | Sort-Object LastWriteTime -Descending | Select-Object -First 1; if (-not $file) { throw "no snapshot in $Dir" }; $path = $file.FullName }
elseif (Test-Path $Snapshot) { $path = (Resolve-Path $Snapshot).Path }
else { if ($Snapshot -notmatch '^[A-Za-z0-9_-]+$') { throw "snapshot names use letters, digits, _ and - only (or pass a path to an existing file)" }; $path = Join-Path $Dir "$Snapshot.dump"; if (-not (Test-Path $path)) { throw "snapshot not found: $Snapshot" } }
$sw = [Diagnostics.Stopwatch]::StartNew()
docker cp $path "${Container}:/tmp/restore.dump"
if ($LASTEXITCODE -ne 0) { throw "docker cp failed (is $Container running?)" }
"target: $Container / $Database (dropped and recreated from $path)"
docker exec $Container psql -U postgres -d postgres -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS $Database WITH (FORCE)" -c "CREATE DATABASE $Database"
if ($LASTEXITCODE -ne 0) { throw "could not recreate $Database" }
docker exec $Container pg_restore -U postgres -d $Database --no-owner /tmp/restore.dump
if ($LASTEXITCODE -ne 0) { Write-Warning "pg_restore reported errors (exit $LASTEXITCODE): check the counts below" }
docker exec $Container rm -f /tmp/restore.dump | Out-Null
$rows = docker exec $Container psql -U postgres -d $Database -tAc "select (select count(*) from civic_cases) || ' cases, ' || (select count(*) from case_embeddings) || ' embeddings, ' || (select count(*) from case_embeddings where embedding_vec is not null) || ' pgvector values'"
"restored $path into $Database ($rows) in $([math]::Round($sw.Elapsed.TotalSeconds, 1)) s; no embedding was requested"
