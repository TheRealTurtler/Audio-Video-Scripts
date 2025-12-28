@echo off
rem ============================================================
rem  THREAD LIMIT MODULE (DISPATCHER)
rem
rem  Provides routines:
rem      - CALC_AFFINITY
rem      - DEC_TO_HEX
rem
rem  Responsibilities:
rem      - Determine number of logical CPUs
rem      - Clamp THREADS to valid range
rem      - Build CPU affinity bitmask
rem      - Convert bitmask to hex
rem      - Export AFFINITY variable to caller
rem
rem  Usage:
rem      call thread_limit.bat CALC_AFFINITY <THREADS>
rem      Result: AFFINITY contains hex mask
rem ============================================================

rem --- Dispatcher ---
if "%~1" neq "" (
  2>nul >nul findstr /rc:"^ *:%~1\>" "%~f0" && (
    shift /1
    goto %1
  ) || (
    >&2 echo ERROR: routine %~1 not found
    exit /b 1
  )
) else (
  >&2 echo ERROR: missing routine
  exit /b 1
)
exit /b


rem ============================================================
rem  CALCULATE CPU AFFINITY MASK
rem ============================================================
:CALC_AFFINITY
setlocal EnableDelayedExpansion

set "THREADS=%~1"

rem Get total logical processors
for /f "tokens=2 delims==" %%a in ('
    wmic cpu get NumberOfLogicalProcessors /value ^| find "="
') do set "TOTAL=%%a"

rem THREADS = -1 → use all
if "!THREADS!"=="-1" (
    set /a USE=!TOTAL!
) else (
    set /a USE=!THREADS!
)

rem Clamp to valid range
if !USE! GTR !TOTAL! set USE=!TOTAL!
if !USE! LSS 1 set USE=1

rem Build bitmask manually
set MASK=0
for /l %%i in (1,1,!USE!) do (
    set /a MASK=MASK*2+1
)

rem Convert decimal mask to hex string
call "%~f0" DEC_TO_HEX !MASK! HEX

endlocal & set "AFFINITY=%HEX%"
exit /b 0


rem ============================================================
rem  DECIMAL TO HEX STRING
rem ============================================================
:DEC_TO_HEX
setlocal EnableDelayedExpansion

set /a A=%1
set "MAP=0123456789ABCDEF"
set "H="

:HEX_LOOP
set /a B=A %% 16
set /a A=A / 16
set "H=!MAP:~%B%,1!!H!"
if !A! GTR 0 goto HEX_LOOP

endlocal & set "%2=%H%"
exit /b 0
