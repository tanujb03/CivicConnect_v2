# Shared helpers for scripts/dev/new_worktree.ps1 and remove_worktree.ps1 (dot-source this file; it is not meant to be run on its own).
#
# Lane scheme (max 4 parallel sessions): every session gets its own git worktree D:\cc\<Name>, its own branch, and a SLOT 1..4 that owns
#   database  civicconnect_s<Slot>        (dev database, migrated + seeded)
#   database  civicconnect_test_s<Slot>   (PostgreSQL integration tests)
#   Redis DB  <Slot>                      (redis://localhost:6379/<Slot>)
#   API port  8000 + <Slot>
# The databases live in the shared civic-db container (scripts/dev/db_up.ps1, host port 5433) and the Redis DBs in civic-redis.

$script:LaneRoot = if ($env:CIVIC_LANE_ROOT) { $env:CIVIC_LANE_ROOT } else { "D:\cc" }
$script:DbContainer = "civic-db"
$script:RedisContainer = "civic-redis"
$script:DbPort = if ($env:CIVIC_DB_PORT) { [int]$env:CIVIC_DB_PORT } else { 5433 }
$script:DbPassword = if ($env:CIVIC_DB_PASSWORD) { $env:CIVIC_DB_PASSWORD } else { "postgres" }
$script:NativeExit = 0

# Windows PowerShell 5.1 turns a native command's stderr (alembic and docker log there) into errors under $ErrorActionPreference = Stop; merge stderr and judge by exit code.
# Deliberately a SIMPLE function (no param block / [Parameter] attributes): an advanced function would swallow native flags such as `psql -v` as -Verbose.
function Invoke-Native {
    $exe = $args[0]
    $rest = if ($args.Count -gt 1) { @($args[1..($args.Count - 1)]) } else { @() }
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $out = & $exe @rest 2>&1 | ForEach-Object { if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.Exception.Message } else { "$_" } }
        $script:NativeExit = $LASTEXITCODE
    } finally { $ErrorActionPreference = $prev }
    $out
}

function Assert-Native([string]$What, $Output) {
    if ($script:NativeExit -ne 0) { throw "$What failed (exit $($script:NativeExit)): $(($Output | Select-Object -Last 8) -join ' | ')" }
}

# The main checkout is the parent of the common .git directory, whichever worktree this script runs from.
function Get-MainCheckout {
    $common = (Invoke-Native git -C $PSScriptRoot rev-parse --path-format=absolute --git-common-dir | Select-Object -First 1)
    Assert-Native "git rev-parse" $common
    (Split-Path (Resolve-Path $common).Path -Parent)
}

function Get-LaneInfo([int]$Slot) {
    $base = "postgresql+psycopg2://postgres:$($script:DbPassword)@localhost:$($script:DbPort)"
    [ordered]@{
        Slot            = $Slot
        Database        = "civicconnect_s$Slot"
        TestDatabase    = "civicconnect_test_s$Slot"
        DATABASE_URL    = "$base/civicconnect_s$Slot"
        TEST_DATABASE_URL = "$base/civicconnect_test_s$Slot"
        REDIS_URL       = "redis://localhost:6379/$Slot"
        TEST_REDIS_URL  = "redis://localhost:6379/$Slot"
        API_PORT        = [string](8000 + $Slot)
    }
}

function Invoke-LanePsql([string]$Db, [string]$Sql) {
    $out = Invoke-Native docker exec $script:DbContainer psql -h 127.0.0.1 -U postgres -d $Db -v ON_ERROR_STOP=1 -tAc $Sql
    Assert-Native "psql ($Sql)" $out
    (($out) -join "`n").Trim()
}

function Assert-LaneServices {
    $out = Invoke-Native docker exec $script:DbContainer pg_isready -h 127.0.0.1 -U postgres
    if ($script:NativeExit -ne 0) { throw "The $($script:DbContainer) container is not running. Start it with: .\scripts\dev\db_up.ps1" }
    $out = Invoke-Native docker exec $script:RedisContainer redis-cli ping
    if ($script:NativeExit -ne 0 -or -not (($out -join "") -match "PONG")) { throw "The $($script:RedisContainer) container is not running. Start it with: .\scripts\dev\db_up.ps1" }
}

function Get-SlotFile([int]$Slot) { Join-Path (Join-Path $script:LaneRoot ".slots") "slot$Slot.txt" }
