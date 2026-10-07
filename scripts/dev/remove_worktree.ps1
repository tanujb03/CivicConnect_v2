<#
.SYNOPSIS
  Remove a lane created by new_worktree.ps1: git worktree remove, drop both databases, flush the lane's Redis DB, free the slot.
.DESCRIPTION
  Refuses to remove a worktree that has uncommitted or untracked changes unless -Force is given. The branch is NOT deleted (it may hold unpushed commits);
  delete it yourself with `git branch -d <branch>` once it is merged/pushed.
.EXAMPLE
  .\scripts\dev\remove_worktree.ps1 -Name schema -Slot 1
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidatePattern('^[A-Za-z0-9._-]+$')][string]$Name,
    [Parameter(Mandatory)][ValidateRange(1, 4)][int]$Slot,
    [switch]$Force
)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_lane.ps1")

$main = Get-MainCheckout
$wt = Join-Path $script:LaneRoot $Name
$lane = Get-LaneInfo $Slot
$slotFile = Get-SlotFile $Slot

if ((Test-Path $slotFile) -and -not $Force) {
    $owner = (Get-Content $slotFile -Raw).Trim()
    if ($owner -and $owner -ne $Name) { throw "Slot $Slot belongs to lane '$owner', not '$Name'. Check the arguments (or use -Force)." }
}

# --- worktree ------------------------------------------------------------------------------------------------------------------------------------
if (Test-Path $wt) {
    if (-not $Force) {
        $dirty = Invoke-Native git -C $wt status --porcelain
        Assert-Native "git status" $dirty
        if ($dirty) { throw "$wt has uncommitted or untracked changes:`n$(($dirty | Select-Object -First 10) -join "`n")`nCommit/push them or pass -Force." }
    }
    Write-Host "git worktree remove $wt"
    $forceArgs = if ($Force) { @("--force") } else { @() }
    $out = Invoke-Native git -C $main worktree remove @forceArgs $wt
    Assert-Native "git worktree remove" $out
} else {
    Write-Host "$wt does not exist; pruning stale worktree records."
    $out = Invoke-Native git -C $main worktree prune
}

# --- databases and Redis --------------------------------------------------------------------------------------------------------------------------
$out = Invoke-Native docker exec $script:DbContainer pg_isready -h 127.0.0.1 -U postgres
if ($script:NativeExit -eq 0) {
    foreach ($db in @($lane.Database, $lane.TestDatabase)) {
        Invoke-LanePsql "postgres" "DROP DATABASE IF EXISTS $db WITH (FORCE)" | Out-Null
        Write-Host "dropped database $db"
    }
} else { Write-Warning "$($script:DbContainer) is not running; databases were not dropped." }
$out = Invoke-Native docker exec $script:RedisContainer redis-cli -n $Slot FLUSHDB
if ($script:NativeExit -eq 0) { Write-Host "flushed Redis DB $Slot ($(($out -join '').Trim()))" } else { Write-Warning "$($script:RedisContainer) is not running; Redis DB $Slot was not flushed." }

if (Test-Path $slotFile) { Remove-Item $slotFile -Force }
Write-Host 'The branch was kept: list with git branch, delete with git branch -d <branch> once merged or pushed.'; Write-Host "Slot $Slot is free."
