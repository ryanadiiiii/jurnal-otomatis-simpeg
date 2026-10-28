# Remove LogonTrigger dari SIMPEG Jurnal Harian
# JALANKAN SEBAGAI ADMINISTRATOR!

Write-Host "Removing LogonTrigger from SIMPEG Jurnal Harian..." -ForegroundColor Yellow

$task = Get-ScheduledTask -TaskName "SIMPEG Jurnal Harian" -ErrorAction Stop

# Keep only CalendarTrigger (weekly), remove LogonTrigger
$calendarTriggers = $task.Triggers | Where-Object { $_.CimClass.CimClassName -ne 'MSFT_TaskLogonTrigger' }

if ($calendarTriggers.Count -eq $task.Triggers.Count) {
    Write-Host "No LogonTrigger found - nothing to remove." -ForegroundColor Green
} else {
    Set-ScheduledTask -TaskName "SIMPEG Jurnal Harian" -Trigger $calendarTriggers
    Write-Host "LogonTrigger REMOVED! Task will only run at 08:00 Mon-Fri." -ForegroundColor Green
}

# Verify
$task2 = Get-ScheduledTask -TaskName "SIMPEG Jurnal Harian"
Write-Host "`nCurrent triggers:" -ForegroundColor Cyan
$task2.Triggers | ForEach-Object { Write-Host "  - $($_.CimClass.CimClassName): Enabled=$($_.Enabled)" }

Write-Host "`nWakeToRun: $($task2.Settings.WakeToRun)" -ForegroundColor Cyan
Write-Host ""
Read-Host "Tekan Enter untuk keluar"

