param(
  [Parameter(Mandatory = $true)]
  [string] $OldPath,

  [Parameter(Mandatory = $true)]
  [string] $NewPath,

  [string] $CodexHome = "$env:USERPROFILE\.codex",

  [switch] $Apply,

  [string] $Python = "python"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repairScript = Join-Path $scriptDir "codex_path_repair.py"

if (-not (Test-Path -LiteralPath $repairScript)) {
  throw "Could not find $repairScript"
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

