@echo off
REM ============================================
REM Setup SEMUA Task Scheduler SIMPEG
REM (Jurnal Harian + Absensi Jumat)
REM Jalankan sebagai Administrator!
REM ============================================

set SCRIPT_DIR=%~dp0
if "%SCRIPT_DIR:~-1%"=="\" set SCRIPT_DIR=%SCRIPT_DIR:~0,-1%

set "PYTHON_PATH="
for /f "delims=" %%I in ('where.exe python 2^>nul') do (
    echo %%I | findstr /i "WindowsApps" >nul
    if errorlevel 1 (
        if not defined PYTHON_PATH set "PYTHON_PATH=%%I"
    )
)
if not defined PYTHON_PATH set PYTHON_PATH=python.exe

echo Menggunakan Folder : %SCRIPT_DIR%
echo Menggunakan Python : %PYTHON_PATH%

echo ============================================
echo  Setup Otomatis SIMPEG - Task Scheduler
echo ============================================
echo.

REM --- Hapus task lama jika ada ---
echo Membersihkan task lama...
schtasks /Delete /TN "SIMPEG_Jurnal_Otomatis" /F >nul 2>&1
schtasks /Delete /TN "SIMPEG Absen Datang Jumat" /F >nul 2>&1
schtasks /Delete /TN "SIMPEG Absen Pulang Jumat" /F >nul 2>&1
echo.

REM ============================================
REM 1. JURNAL HARIAN (Senin-Jumat 08:00)
REM ============================================
echo [1/3] Membuat task: Jurnal Harian Senin-Jumat 08:00...

set XML_JURNAL=%TEMP%\simpeg_jurnal.xml
(
echo ^<?xml version="1.0" encoding="UTF-16"?^>
echo ^<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task"^>
echo   ^<RegistrationInfo^>
echo     ^<Description^>SIMPEG Jurnal Harian Otomatis - Senin-Jumat jam 08:00^</Description^>
echo   ^</RegistrationInfo^>
echo   ^<Triggers^>
echo     ^<CalendarTrigger^>
echo       ^<StartBoundary^>2026-10-09T08:00:00^</StartBoundary^>
echo       ^<Enabled^>true^</Enabled^>
echo       ^<ScheduleByWeek^>
echo         ^<DaysOfWeek^>
echo           ^<Monday /^>
echo           ^<Tuesday /^>
echo           ^<Wednesday /^>
echo           ^<Thursday /^>
echo           ^<Friday /^>
echo         ^</DaysOfWeek^>
echo         ^<WeeksInterval^>1^</WeeksInterval^>
echo       ^</ScheduleByWeek^>
echo     ^</CalendarTrigger^>
echo   ^</Triggers^>
echo   ^<Principals^>
echo     ^<Principal id="Author"^>
echo       ^<LogonType^>InteractiveToken^</LogonType^>
echo       ^<RunLevel^>HighestAvailable^</RunLevel^>
echo     ^</Principal^>
echo   ^</Principals^>
echo   ^<Settings^>
echo     ^<MultipleInstancesPolicy^>IgnoreNew^</MultipleInstancesPolicy^>
echo     ^<DisallowStartIfOnBatteries^>false^</DisallowStartIfOnBatteries^>
echo     ^<StopIfGoingOnBatteries^>false^</StopIfGoingOnBatteries^>
echo     ^<AllowHardTerminate^>true^</AllowHardTerminate^>
echo     ^<StartWhenAvailable^>true^</StartWhenAvailable^>
echo     ^<RunOnlyIfNetworkAvailable^>false^</RunOnlyIfNetworkAvailable^>
echo     ^<AllowStartOnDemand^>true^</AllowStartOnDemand^>
echo     ^<Enabled^>true^</Enabled^>
echo     ^<Hidden^>false^</Hidden^>
echo     ^<ExecutionTimeLimit^>PT2H^</ExecutionTimeLimit^>
echo   ^</Settings^>
echo   ^<Actions Context="Author"^>
echo     ^<Exec^>
echo       ^<Command^>%PYTHON_PATH%^</Command^>
echo       ^<Arguments^>scheduler.py^</Arguments^>
echo       ^<WorkingDirectory^>%SCRIPT_DIR%^</WorkingDirectory^>
echo     ^</Exec^>
echo   ^</Actions^>
echo ^</Task^>
) > "%XML_JURNAL%"

schtasks /Create /TN "SIMPEG Jurnal Harian" /XML "%XML_JURNAL%" /F
if %ERRORLEVEL% EQU 0 (
    echo    OK Jurnal Harian berhasil dibuat!
) else (
    echo    GAGAL membuat Jurnal Harian!
)
echo.

REM ============================================
REM 2. ABSEN DATANG JUMAT (07:00)
REM ============================================
echo [2/3] Membuat task: Absen Datang Jumat 07:00...

set XML_DATANG=%TEMP%\simpeg_datang.xml
(
echo ^<?xml version="1.0" encoding="UTF-16"?^>
echo ^<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task"^>
echo   ^<RegistrationInfo^>
echo     ^<Description^>SIMPEG Absen Datang Otomatis - Jumat jam 07:00^</Description^>
echo   ^</RegistrationInfo^>
echo   ^<Triggers^>
echo     ^<CalendarTrigger^>
echo       ^<StartBoundary^>2026-10-09T07:00:00^</StartBoundary^>
echo       ^<Enabled^>true^</Enabled^>
echo       ^<ScheduleByWeek^>
echo         ^<DaysOfWeek^>
echo           ^<Friday /^>
echo         ^</DaysOfWeek^>
echo         ^<WeeksInterval^>1^</WeeksInterval^>
echo       ^</ScheduleByWeek^>
echo     ^</CalendarTrigger^>
echo   ^</Triggers^>
echo   ^<Principals^>
echo     ^<Principal id="Author"^>
echo       ^<LogonType^>InteractiveToken^</LogonType^>
echo       ^<RunLevel^>HighestAvailable^</RunLevel^>
echo     ^</Principal^>
echo   ^</Principals^>
echo   ^<Settings^>
echo     ^<MultipleInstancesPolicy^>IgnoreNew^</MultipleInstancesPolicy^>
echo     ^<DisallowStartIfOnBatteries^>false^</DisallowStartIfOnBatteries^>
echo     ^<StopIfGoingOnBatteries^>false^</StopIfGoingOnBatteries^>
echo     ^<AllowHardTerminate^>true^</AllowHardTerminate^>
echo     ^<StartWhenAvailable^>true^</StartWhenAvailable^>
echo     ^<RunOnlyIfNetworkAvailable^>false^</RunOnlyIfNetworkAvailable^>
echo     ^<AllowStartOnDemand^>true^</AllowStartOnDemand^>
echo     ^<Enabled^>true^</Enabled^>
echo     ^<Hidden^>false^</Hidden^>
echo     ^<ExecutionTimeLimit^>PT1H^</ExecutionTimeLimit^>
echo   ^</Settings^>
echo   ^<Actions Context="Author"^>
echo     ^<Exec^>
echo       ^<Command^>%PYTHON_PATH%^</Command^>
echo       ^<Arguments^>scheduler.py --mode absen-datang^</Arguments^>
echo       ^<WorkingDirectory^>%SCRIPT_DIR%^</WorkingDirectory^>
echo     ^</Exec^>
echo   ^</Actions^>
echo ^</Task^>
) > "%XML_DATANG%"

schtasks /Create /TN "SIMPEG Absen Datang Jumat" /XML "%XML_DATANG%" /F
if %ERRORLEVEL% EQU 0 (
    echo    OK Absen Datang Jumat berhasil dibuat!
) else (
    echo    GAGAL membuat Absen Datang Jumat!
)
echo.

REM ============================================
REM 3. ABSEN PULANG JUMAT (16:30)
REM ============================================
echo [3/3] Membuat task: Absen Pulang Jumat 16:30...

set XML_PULANG=%TEMP%\simpeg_pulang.xml
(
echo ^<?xml version="1.0" encoding="UTF-16"?^>
echo ^<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task"^>
echo   ^<RegistrationInfo^>
echo     ^<Description^>SIMPEG Absen Pulang Otomatis - Jumat jam 16:30^</Description^>
echo   ^</RegistrationInfo^>
echo   ^<Triggers^>
echo     ^<CalendarTrigger^>
echo       ^<StartBoundary^>2026-10-09T17:35:00^</StartBoundary^>
echo       ^<Enabled^>true^</Enabled^>
echo       ^<ScheduleByWeek^>
echo         ^<DaysOfWeek^>
echo           ^<Friday /^>
echo         ^</DaysOfWeek^>
echo         ^<WeeksInterval^>1^</WeeksInterval^>
echo       ^</ScheduleByWeek^>
echo     ^</CalendarTrigger^>
echo   ^</Triggers^>
echo   ^<Principals^>
echo     ^<Principal id="Author"^>
echo       ^<LogonType^>InteractiveToken^</LogonType^>
echo       ^<RunLevel^>HighestAvailable^</RunLevel^>
echo     ^</Principal^>
echo   ^</Principals^>
echo   ^<Settings^>
echo     ^<MultipleInstancesPolicy^>IgnoreNew^</MultipleInstancesPolicy^>
echo     ^<DisallowStartIfOnBatteries^>false^</DisallowStartIfOnBatteries^>
echo     ^<StopIfGoingOnBatteries^>false^</StopIfGoingOnBatteries^>
echo     ^<AllowHardTerminate^>true^</AllowHardTerminate^>
echo     ^<StartWhenAvailable^>true^</StartWhenAvailable^>
echo     ^<RunOnlyIfNetworkAvailable^>false^</RunOnlyIfNetworkAvailable^>
echo     ^<AllowStartOnDemand^>true^</AllowStartOnDemand^>
echo     ^<Enabled^>true^</Enabled^>
echo     ^<Hidden^>false^</Hidden^>
echo     ^<ExecutionTimeLimit^>PT1H^</ExecutionTimeLimit^>
echo   ^</Settings^>
echo   ^<Actions Context="Author"^>
echo     ^<Exec^>
echo       ^<Command^>%PYTHON_PATH%^</Command^>
echo       ^<Arguments^>scheduler.py --mode absen-pulang^</Arguments^>
echo       ^<WorkingDirectory^>%SCRIPT_DIR%^</WorkingDirectory^>
echo     ^</Exec^>
echo   ^</Actions^>
echo ^</Task^>
) > "%XML_PULANG%"

schtasks /Create /TN "SIMPEG Absen Pulang Jumat" /XML "%XML_PULANG%" /F
if %ERRORLEVEL% EQU 0 (
    echo    OK Absen Pulang Jumat berhasil dibuat!
) else (
    echo    GAGAL membuat Absen Pulang Jumat!
)

echo.
echo ============================================
echo  SELESAI! Task yang terdaftar:
echo  1. Jurnal Harian  : Senin-Jumat 08:00 WITA
echo  2. Absen Datang   : Jumat 07:00 WITA (06:00 WIB)
echo  3. Absen Pulang   : Jumat 17:35 WITA (16:35 WIB)
echo.
echo  Fitur:
echo  - Jalan di baterai (laptop)
echo  - Auto-jalan jika laptop terlambat nyala
echo  - Working directory sudah benar
echo  - Full path Python sudah benar
echo ============================================
echo.
pause

