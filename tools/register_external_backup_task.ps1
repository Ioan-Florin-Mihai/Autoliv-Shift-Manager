[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)]
    [string]$TargetFolder,

    [Parameter(Mandatory = $false)]
    [ValidatePattern('^\d{2}:\d{2}$')]
    [string]$Time = "22:00",

    [Parameter(Mandatory = $false)]
    [string]$TaskName = "Autoliv Shift Manager External Backup"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$BackupCmd = Join-Path $ProjectRoot "external_backup.cmd"

if (-not (Test-Path -LiteralPath $BackupCmd)) {
    throw "Missing backup wrapper: $BackupCmd"
}

$ResolvedTarget = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($TargetFolder)
$StartTime = [datetime]::ParseExact($Time, "HH:mm", [Globalization.CultureInfo]::InvariantCulture)

$Action = New-ScheduledTaskAction -Execute $BackupCmd -Argument "`"$ResolvedTarget`"" -WorkingDirectory $ProjectRoot
$Trigger = New-ScheduledTaskTrigger -Daily -At $StartTime
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew

Write-Host "Task name: $TaskName"
Write-Host "Target folder: $ResolvedTarget"
Write-Host "Schedule time: $Time"
Write-Host "Command: $BackupCmd `"$ResolvedTarget`""

if ($PSCmdlet.ShouldProcess($TaskName, "Register or update scheduled external backup task")) {
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $Action `
        -Trigger $Trigger `
        -Settings $Settings `
        -Description "Creates optional external backups for Autoliv Shift Manager." `
        -Force | Out-Null
    Write-Host "[OK] Scheduled backup task registered."
} else {
    Write-Host "[OK] WhatIf completed. No scheduled task was registered."
}
