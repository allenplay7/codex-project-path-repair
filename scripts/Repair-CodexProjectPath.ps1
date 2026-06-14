param(
  [Parameter(Mandatory = $false)]
  [string] $OldPath,

  [Parameter(Mandatory = $false)]
  [string] $NewPath,

  [string] $CodexHome = "$env:USERPROFILE\.codex",

  [switch] $Apply,

  [switch] $Wizard,

  [string] $Python = "python"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repairScript = Join-Path $scriptDir "codex_path_repair.py"

if (-not (Test-Path -LiteralPath $repairScript)) {
  throw "Could not find $repairScript"
}

function Resolve-Python {
  param([string] $Requested)

  $candidates = @($Requested, "py", "python3", "python")
  foreach ($candidate in $candidates | Select-Object -Unique) {
    try {
      $null = & $candidate --version 2>$null
      if ($LASTEXITCODE -eq 0) {
        return $candidate
      }
    } catch {
    }
  }
  throw "Python was not found. Install Python 3 from https://www.python.org/downloads/ or the Microsoft Store, then run this again."
}

$Python = Resolve-Python -Requested $Python

if ($Wizard -or -not $OldPath -or -not $NewPath) {
  & $Python $repairScript --wizard --codex-home $CodexHome
  exit $LASTEXITCODE
}

$args = @(
  $repairScript,
  "--old", $OldPath,
  "--new", $NewPath,
  "--codex-home", $CodexHome
)

if ($Apply) {
  $args += "--apply"
}

& $Python @args
exit $LASTEXITCODE
