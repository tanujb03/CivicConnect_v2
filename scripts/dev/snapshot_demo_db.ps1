<#
.SYNOPSIS
  Dumps the demo database (pg_dump custom format, from the civic-db container) to D:\ml-cache\snapshots so a broken demo can be put back in under a minute.
.DESCRIPTION
  The dump holds EVERYTHING in the database, case_embeddings included (the json vectors and the pgvector column). Restoring it therefore never needs a re-embed: the embedding
  quota is 1000 inputs a day and 30K tokens a minute. Restore with scripts\dev\restore_demo_db.ps1. Takes the database name (default civicconnect) and a snapshot name
  (default: a timestamp). Needs the civic-db container to be running (Docker Desktop, then scripts\dev\db_up.ps1).
  THE DUMP HOLDS EVERY USER ROW INCLUDING PASSWORD HASHES (demo data only in this project): keep it on D:\ml-cache, do not commit or share it.
#>
param(
    [ValidatePattern('^[a-z0-9_]+$')][string]$Database = "civicconnect",
    [ValidatePattern('^[A-Za-z0-9_-]+$')][string]$Name = (Get-Date -Format "yyyyMMdd_HHmmss"),
    [ValidatePattern('^[A-Za-z0-9_.-]+$')][string]$Container = "civic-db",
    [string]$Dir = "D:\ml-cache\snapshots"
)
$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force $Dir | Out-Null
$inside = "/tmp/$Name.dump"
$sw = [Diagnostics.Stopwatch]::StartNew()
docker exec $Container pg_dump -U postgres -Fc -d $Database -f $inside
if ($LASTEXITCODE -ne 0) { throw "pg_dump failed (is $Container running?)" }
$target = Join-Path $Dir "$Name.dump"
docker cp "${Container}:$inside" $target
if ($LASTEXITCODE -ne 0) { throw "docker cp failed" }
docker exec $Container rm -f $inside | Out-Null
$rows = docker exec $Container psql -U postgres -d $Database -tAc "select (select count(*) from civic_cases) || ' cases, ' || (select count(*) from case_embeddings) || ' embeddings'"
"snapshot $target ($([math]::Round((Get-Item $target).Length / 1MB, 1)) MB, $rows) in $([math]::Round($sw.Elapsed.TotalSeconds, 1)) s"
