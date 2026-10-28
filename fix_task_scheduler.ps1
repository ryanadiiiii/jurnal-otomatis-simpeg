# =============================================================
# Fix SIMPEG Jurnal Harian Task Scheduler
# JALANKAN SEBAGAI ADMINISTRATOR!
# Right-click PowerShell -> Run as Administrator
# Lalu: cd "d:\CODING\Jurnal Harian Otomatis"
#       .\fix_task_scheduler.ps1
# =============================================================

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Fix SIMPEG Task Scheduler" -ForegroundColor Cyan  
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. Enable wake timers on battery
Write-Host "[1/4] Enabling wake timers (AC + Battery)..." -ForegroundColor Yellow
powercfg /SETDCVALUEINDEX SCHEME_CURRENT SUB_SLEEP RTCWAKE 1
powercfg /SETACVALUEINDEX SCHEME_CURRENT SUB_SLEEP RTCWAKE 1
powercfg /SETACTIVE SCHEME_CURRENT
Write-Host "  OK - Wake timers enabled" -ForegroundColor Green

# 2. Update task settings
Write-Host "[2/4] Updating SIMPEG Jurnal Harian task..." -ForegroundColor Yellow
$task = Get-ScheduledTask -TaskName "SIMPEG Jurnal Harian" -ErrorAction Stop

# Enable WakeToRun
$task.Settings.WakeToRun = $true
$task.Settings.IdleSettings.StopOnIdleEnd = $false
$task.Settings.IdleSettings.RestartOnIdle = $false

# Keep existing weekly trigger + add logon trigger as backup
$weeklyTrigger = $task.Triggers[0]
$logonTrigger = New-ScheduledTaskTrigger -AtLogOn
$logonTrigger.Delay = 'PT3M'

Set-ScheduledTask -TaskName "SIMPEG Jurnal Harian" -Settings $task.Settings -Trigger @($weeklyTrigger, $logonTrigger)
Write-Host "  OK - WakeToRun enabled, logon trigger added" -ForegroundColor Green

# 3. Verify
Write-Host "[3/4] Verifying..." -ForegroundColor Yellow
$xml = schtasks /query /tn "SIMPEG Jurnal Harian" /xml 2>$null
$hasWake = $xml -match 'WakeToRun.*true'
$hasLogon = $xml -match 'LogonTrigger'
if ($hasWake) { Write-Host "  OK - WakeToRun = true" -ForegroundColor Green } 
else { Write-Host "  FAIL - WakeToRun not set!" -ForegroundColor Red }
if ($hasLogon) { Write-Host "  OK - LogonTrigger present" -ForegroundColor Green }
else { Write-Host "  FAIL - LogonTrigger not found!" -ForegroundColor Red }

# 4. Also fix absensi tasks if they exist
Write-Host "[4/4] Fixing absensi tasks..." -ForegroundColor Yellow
foreach ($taskName in @("SIMPEG Absen Datang Jumat", "SIMPEG Absen Pulang Jumat")) {
    $t = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($t) {
        $t.Settings.WakeToRun = $true
        $t.Settings.DisallowStartIfOnBatteries = $false
        $t.Settings.StopIfGoingOnBatteries = $false
        $t.Settings.IdleSettings.StopOnIdleEnd = $false
        Set-ScheduledTask -TaskName $taskName -Settings $t.Settings
        Write-Host "  OK - $taskName updated" -ForegroundColor Green
    } else {
        Write-Host "  SKIP - $taskName not found" -ForegroundColor DarkGray
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " DONE! Task akan:" -ForegroundColor Green
Write-Host "  1. Bangunkan laptop dari sleep jam 08:00" -ForegroundColor White
Write-Host "  2. Jalan otomatis saat login (backup)" -ForegroundColor White
Write-Host "  3. Tetap jalan walau pakai baterai" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Tekan Enter untuk keluar..." -ForegroundColor Gray
Read-Host

