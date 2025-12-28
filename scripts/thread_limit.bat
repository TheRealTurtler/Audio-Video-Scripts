@echo off
rem ============================================================
rem  DESCRIPTION
rem ============================================================
rem  This module calculates a CPU affinity bitmask based on a
rem  requested thread count and the system's available logical CPUs.
rem
rem  - Accepts a desired thread count as a parameter
rem  - Falls back to the global THREADS variable if no parameter
rem    is provided
rem  - Clamps the requested thread count to a valid range
rem  - Builds a binary bitmask representing the allowed CPU cores
rem  - Converts the bitmask to a hexadecimal affinity value
rem  - Exports the final affinity mask via the AFFINITY variable
rem
rem  Usage:
rem      call thread_limit.bat CALC_AFFINITY <THREADS>
rem      echo %AFFINITY%
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


:CALC_AFFINITY
setlocal EnableDelayedExpansion

set "THREADS=%~1"

for /f "tokens=2 delims==" %%a in ('
    wmic cpu get NumberOfLogicalProcessors /value ^| find "="
') do set "TOTAL=%%a"

if "!THREADS!"=="-1" (
    set /a USE=TOTAL
) else (
    set /a USE=THREADS
)

rem --- numeric clamp ---
set /a DIFF=USE-TOTAL
if !DIFF! GTR 0 set /a USE=TOTAL
if !USE! LSS 1 set /a USE=1

set MASK=0
for /l %%i in (1,1,!USE!) do set /a MASK=MASK*2+1

call "%~f0" DEC_TO_HEX !MASK! HEX

endlocal & set "AFFINITY=%HEX%"
exit /b 0


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
