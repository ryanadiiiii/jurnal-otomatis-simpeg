@echo off
REM ============================================
REM Setup Task Scheduler untuk Absensi Jumat
REM Jalankan sebagai Administrator!
REM ============================================

set SCRIPT_DIR=%~dp0
set PYTHON_PATH=C:\Users\acer\AppData\Local\Programs\Python\Python312\python.exe
set SCHEDULER_SCRIPT=%SCRIPT_DIR%scheduler.py

echo ============================================
echo  Setup Absensi Otomatis Jumat (WFH)
echo ============================================
echo.

REM --- Absen Datang: Jumat 07:00 WIB ---
echo [1/2] Membuat task: Absen Datang Jumat 07:00...
schtasks /Create /TN "SIMPEG Absen Datang Jumat" ^
    /TR "\"%PYTHON_PATH%\" \"%SCHEDULER_SCRIPT%\" --mode absen-datang" ^
    /SC WEEKLY /D FRI ^
    /ST 07:00 ^
    /RL HIGHEST ^
    /F

if %ERRORLEVEL% EQU 0 (
    echo    ✅ Absen Datang berhasil dibuat!
) else (
    echo    ❌ Gagal membuat Absen Datang!
)

echo.

REM --- Absen Pulang: Jumat 16:30 WIB ---
echo [2/2] Membuat task: Absen Pulang Jumat 16:30...
schtasks /Create /TN "SIMPEG Absen Pulang Jumat" ^
    /TR "\"%PYTHON_PATH%\" \"%SCHEDULER_SCRIPT%\" --mode absen-pulang" ^
    /SC WEEKLY /D FRI ^
    /ST 16:30 ^
    /RL HIGHEST ^
    /F

if %ERRORLEVEL% EQU 0 (
    echo    ✅ Absen Pulang berhasil dibuat!
) else (
    echo    ❌ Gagal membuat Absen Pulang!
)

echo.
echo ============================================
echo  SELESAI! Absensi Jumat sudah terjadwal:
echo  - Absen Datang : Jumat 07:00
echo  - Absen Pulang : Jumat 16:30
echo ============================================
echo.

REM --- Enable "Run task as soon as possible after scheduled start is missed" ---
echo Mengaktifkan opsi "jalankan segera jika terlambat"...

set XML_DATANG=%TEMP%\absen_datang.xml
set XML_PULANG=%TEMP%\absen_pulang.xml

schtasks /Query /TN "SIMPEG Absen Datang Jumat" /XML > "%XML_DATANG%" 2>nul
powershell -Command "(Get-Content '%XML_DATANG%') -replace '</Settings>', '  <StartWhenAvailable>true</StartWhenAvailable></Settings>' | Set-Content '%XML_DATANG%'"
schtasks /Create /TN "SIMPEG Absen Datang Jumat" /XML "%XML_DATANG%" /F >nul 2>&1

schtasks /Query /TN "SIMPEG Absen Pulang Jumat" /XML > "%XML_PULANG%" 2>nul
powershell -Command "(Get-Content '%XML_PULANG%') -replace '</Settings>', '  <StartWhenAvailable>true</StartWhenAvailable></Settings>' | Set-Content '%XML_PULANG%'"
schtasks /Create /TN "SIMPEG Absen Pulang Jumat" /XML "%XML_PULANG%" /F >nul 2>&1

echo ✅ Opsi "jalankan segera" diaktifkan.
echo.
pause
