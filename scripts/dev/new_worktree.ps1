<#
.SYNOPSIS
  Create an isolated lane for one Claude Code session: git worktree + branch + own databases, Redis DB and API port.
.DESCRIPTION
  Does, in order:
    1. git fetch origin; git worktree add D:\cc\<Name> -b <Branch> origin/tanuj
    2. copies the root .env into the worktree
    3. creates databases civicconnect_s<Slot> and civicconnect_test_s<Slot> in the civic-db container (postgis + vector extensions)
    4. writes DATABASE_URL, TEST_DATABASE_URL, REDIS_URL (redis://localhost:6379/<Slot>), TEST_REDIS_URL and API_PORT (8000+Slot) into the worktree .env AND into the
       "env" block of the worktree's .claude/settings.local.json (also sets attribution commit/pr to ""); both files are gitignored
    5. proves backend/ai import from the worktree, then runs python -m alembic upgrade head and python -m backend.scripts.seed_demo there
    6. prints the exact activate, uvicorn and claude commands
  Max 4 lanes at a time (slots 1..4). Prerequisite: scripts\dev\db_up.ps1 has been run (civic-db and civic-redis are up).
.EXAMPLE
  .\scripts\dev\new_worktree.ps1 -Name schema -Branch lane-schema -Slot 1
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidatePattern('^[A-Za-z0-9._-]+$')][string]$Name,
    [Parameter(Mandatory)][ValidatePattern('^[A-Za-z0-9._/-]+$')][string]$Branch,
    [Parameter(Mandatory)][ValidateRange(1, 4)][int]$Slot,
    [string]$Base = "origin/tanuj",
    [switch]$SkipSeed
)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_lane.ps1")

$main = Get-MainCheckout
$py = Join-Path $main ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { throw "Shared venv not found at $py (see CLAUDE.md, section 6)." }
$wt = Join-Path $script:LaneRoot $Name
$lane = Get-LaneInfo $Slot

Assert-LaneServices

# --- slot registry: one live lane per slot -------------------------------------------------------------------------------------------------------
$slotFile = Get-SlotFile $Slot
if (Test-Path $slotFile) {
    $owner = (Get-Content $slotFile -Raw).Trim()
    if ($owner -and (Test-Path (Join-Path $script:LaneRoot $owner))) { throw "Slot $Slot is in use by lane '$owner' ($($script:LaneRoot)\$owner). Remove it first: .\scripts\dev\remove_worktree.ps1 -Name $owner -Slot $Slot" }
}
if (Test-Path $wt) { throw "$wt already exists." }

# --- 1. worktree ---------------------------------------------------------------------------------------------------------------------------------
Write-Host "[1/6] git fetch origin; git worktree add $wt -b $Branch $Base"
$out = Invoke-Native git -C $main fetch origin
Assert-Native "git fetch origin" $out
New-Item -ItemType Directory -Force $script:LaneRoot | Out-Null
$out = Invoke-Native git -C $main worktree add $wt -b $Branch $Base
Assert-Native "git worktree add" $out
New-Item -ItemType Directory -Force (Split-Path $slotFile) | Out-Null
[System.IO.File]::WriteAllText($slotFile, $Name, (New-Object System.Text.UTF8Encoding $false))

# --- 2/4a. .env ----------------------------------------------------------------------------------------------------------------------------------
Write-Host "[2/6] .env: copy from the root checkout and write the lane variables (names only are shown)"
$envPath = Join-Path $wt ".env"
$rootEnv = Join-Path $main ".env"
if (Test-Path $rootEnv) { Copy-Item $rootEnv $envPath } else { Write-Warning "No root .env found ($rootEnv); copying .env.example. Fill the API keys in the ROOT .env and copy it here."; Copy-Item (Join-Path $main ".env.example") $envPath }

$laneVars = [ordered]@{
    DATABASE_URL = $lane.DATABASE_URL; TEST_DATABASE_URL = $lane.TEST_DATABASE_URL
    REDIS_URL = $lane.REDIS_URL; TEST_REDIS_URL = $lane.TEST_REDIS_URL; API_PORT = $lane.API_PORT
}
$text = [System.IO.File]::ReadAllText($envPath)
$kept = @($text -split "`r?`n" | Where-Object {
        $line = $_
        -not ($laneVars.Keys | Where-Object { $line -match "^\s*(export\s+)?$([regex]::Escape($_))\s*=" }) -and $line -notmatch "^# --- lane \d"
    })
$block = ($laneVars.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" }) -join "`n"
$newText = (($kept -join "`n").TrimEnd()) + "`n`n# --- lane $Slot (written by scripts/dev/new_worktree.ps1; gitignored, do not commit) ---`n$block`n"
[System.IO.File]::WriteAllText($envPath, $newText, (New-Object System.Text.UTF8Encoding $false))
Write-Host ("      lane variables: " + ($laneVars.Keys -join ", "))

# --- 3. databases --------------------------------------------------------------------------------------------------------------------------------
Write-Host "[3/6] databases $($lane.Database) and $($lane.TestDatabase) (postgis + vector)"
foreach ($db in @($lane.Database, $lane.TestDatabase)) {
    if (-not (Invoke-LanePsql "postgres" "SELECT 1 FROM pg_database WHERE datname = '$db'")) { Invoke-LanePsql "postgres" "CREATE DATABASE $db" | Out-Null }
    Invoke-LanePsql $db "CREATE EXTENSION IF NOT EXISTS postgis; CREATE EXTENSION IF NOT EXISTS vector;" | Out-Null
}

# --- 4b. .claude/settings.local.json ---------------------------------------------------------------------------------------------------------------
Write-Host "[4/6] .claude/settings.local.json: env block + empty attribution"
$claudeDir = Join-Path $wt ".claude"
New-Item -ItemType Directory -Force $claudeDir | Out-Null
$settings = @{}
$rootSettings = Join-Path $main ".claude\settings.local.json"
if (Test-Path $rootSettings) {                       # keep the root's permissions etc.; only env and attribution are set below
    $obj = Get-Content $rootSettings -Raw | ConvertFrom-Json
    foreach ($p in $obj.PSObject.Properties) { $settings[$p.Name] = $p.Value }
}
$envBlock = [ordered]@{}
if ($settings.ContainsKey("env") -and $settings["env"]) { foreach ($p in $settings["env"].PSObject.Properties) { $envBlock[$p.Name] = [string]$p.Value } }
foreach ($k in $laneVars.Keys) { $envBlock[$k] = $laneVars[$k] }
$envBlock["HF_HOME"] = "D:\ml-cache\hf"                  # TEMP/TMP cannot be set here (Claude Code ignores them in project/local settings)
$envBlock["TORCH_HOME"] = "D:\ml-cache\torch"
$settings["env"] = $envBlock
$settings["attribution"] = [ordered]@{ commit = ""; pr = ""; sessionUrl = $false }
[System.IO.File]::WriteAllText((Join-Path $claudeDir "settings.local.json"), (($settings | ConvertTo-Json -Depth 20) + "`n"), (New-Object System.Text.UTF8Encoding $false))

# --- 5. imports, migrations, seed (child processes get the lane's variables; the previous values are restored afterwards) -------------------------------
$saved = @{}
foreach ($k in $laneVars.Keys) { $saved[$k] = [Environment]::GetEnvironmentVariable($k, "Process"); [Environment]::SetEnvironmentVariable($k, $laneVars[$k], "Process") }
Push-Location $wt
try {
    Write-Host "[5/6] python -m backend.scripts.worktree_check  (backend/ai must resolve inside the worktree)"
    $out = Invoke-Native $py -m backend.scripts.worktree_check
    $out | ForEach-Object { Write-Host "      $_" }
    Assert-Native "worktree import check" $out
    Write-Host "      python -m alembic upgrade head"
    $out = Invoke-Native $py -m alembic upgrade head
    Assert-Native "alembic upgrade head" $out
    $out | Select-Object -Last 2 | ForEach-Object { Write-Host "      $_" }
    if (-not $SkipSeed) {
        Write-Host "      python -m backend.scripts.seed_demo"
        $out = Invoke-Native $py -m backend.scripts.seed_demo
        Assert-Native "seed_demo" $out
        $out | Select-Object -First 2 | ForEach-Object { Write-Host "      $_" }
    }
} finally {
    Pop-Location
    foreach ($k in $laneVars.Keys) { [Environment]::SetEnvironmentVariable($k, $saved[$k], "Process") }
}

# --- 6. how to use it ----------------------------------------------------------------------------------------------------------------------------
Write-Host ""
Write-Host "[6/6] Lane '$Name' (branch $Branch, slot $Slot) is ready: db $($lane.Database), test db $($lane.TestDatabase), Redis DB $Slot, API port $($lane.API_PORT)."
Write-Host ""
Write-Host "  cd $wt"
Write-Host "  & $main\.venv\Scripts\Activate.ps1"
Write-Host "  python -m uvicorn backend.main:app --port $($lane.API_PORT) --reload"
Write-Host "  python -m pytest ai backend -q"
Write-Host "  claude                                  # start Claude Code from $wt (it reads the lane's .claude\settings.local.json)"
Write-Host ""
Write-Host "  finish: git fetch origin; git rebase origin/tanuj; python -m pytest ai backend -q; git push origin HEAD:tanuj"
Write-Host "  remove: $main\scripts\dev\remove_worktree.ps1 -Name $Name -Slot $Slot"
