@echo off
REM ============================================
REM SIMPEG Jurnal Harian Otomatis
REM Setup Windows Task Scheduler
REM ============================================
REM Script ini akan mendaftarkan tugas terjadwal di Windows
REM yang menjalankan scheduler.py setiap hari Senin-Jumat pukul 08:00
REM
REM Jalankan sebagai Administrator!
REM ============================================

set TASK_NAME=SIMPEG_Jurnal_Otomatis
set PYTHON_PATH=python
set SCRIPT_PATH=%~dp0scheduler.py
set WORKING_DIR=%~dp0

echo ============================================
echo   SIMPEG Jurnal Harian Otomatis
echo   Setup Task Scheduler
echo ============================================
echo.
echo Task Name  : %TASK_NAME%
echo Script     : %SCRIPT_PATH%
echo Jadwal     : Senin-Jumat, 08:00
echo.

REM Hapus task lama jika ada
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

REM Buat task baru: Senin-Jumat pukul 08:00
schtasks /create ^
    /tn "%TASK_NAME%" ^
    /tr "\"%PYTHON_PATH%\" \"%SCRIPT_PATH%\"" ^
    /sc weekly ^
    /d MON,TUE,WED,THU,FRI ^
    /st 08:00 ^
    /rl HIGHEST ^
    /f

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ============================================
    echo   Task berhasil didaftarkan!
    echo   Bot akan jalan otomatis Senin-Jumat 08:00
    echo ============================================
    echo.
    echo Langkah selanjutnya:
    echo 1. Pastikan file .env sudah diisi dengan benar
    echo 2. Cek Task Scheduler: taskschd.msc
    echo 3. Test manual: python scheduler.py --dry-run
    echo.
) else (
    echo.
    echo ============================================
    echo   GAGAL mendaftarkan task!
    echo   Coba jalankan CMD sebagai Administrator
    echo ============================================
)

pause
