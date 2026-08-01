@echo off
rem ============================================================
rem  DESCRIPTION
rem ============================================================
rem  This module provides routines for CRF search and final encode
rem  using ab-av1. It acts as a dispatcher similar to check_tool.bat.
rem
rem  - CRF_SEARCH performs ab-av1 crf-search and extracts
rem    CRF and VMAF as "BEST_CRF" and "BEST_VMAF"
rem  - FINAL_ENCODE performs the actual encode using the specified CRF
rem  - All encoder settings are passed as parameters
rem
rem  Usage:
rem      call convert_crf_encode.bat CRF_SEARCH <INPUTFILE> <ENCODER> <PRESET> <ENCODE_SETTINGS> <ANALYSIS_SETTINGS>
rem      call convert_crf_encode.bat FINAL_ENCODE <INPUTFILE> <ENCODER> <PRESET> <ENCODE_SETTINGS> <CRF> <OUTPUTFILE>
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
:CRF_SEARCH
rem PARAMETERS:
rem   %1 = INPUTFILE
rem   %2 = ENCODER
rem   %3 = PRESET
rem   %4 = ENCODE_SETTINGS
rem   %5 = ANALYSIS_SETTINGS

setlocal EnableDelayedExpansion

set "INPUT=%~1"
set "ENCODER=%~2"
set "PRESET=%~3"
set "ENCODE_SETTINGS=%~4"
set "ANALYSIS_SETTINGS=%~5"

echo Searching for best CRF...
set CMD=ab-av1.exe crf-search -i "%INPUT%" -e %ENCODER% %ENCODE_SETTINGS% %ANALYSIS_SETTINGS% --preset %PRESET%
echo Executing: !CMD!

set "CMD_OUT="
for /f "delims=" %%a in ('!CMD!') do set "CMD_OUT=%%a"

rem --- PARSE CRF-SEARCH OUTPUT ---
set "BEST_CRF="
set "BEST_VMAF="

for /f "tokens=1-12" %%a in ("!CMD_OUT!") do (
    if /i "%%a"=="crf" set "BEST_CRF=%%b"
    if /i "%%c"=="VMAF" set "BEST_VMAF=%%d"
)

rem --- VALIDATE CRF ---
echo(!BEST_CRF!| findstr /r "^[0-9.][0-9.]*$" >nul
if errorlevel 1 (
    >&2 echo ERROR: CRF parsing failed
    endlocal & exit /b 1
)

for /f "tokens=1 delims=." %%x in ("!BEST_CRF!") do set "CRF_INT=%%x"

if !CRF_INT! LSS 1 (
    >&2 echo ERROR: CRF too small
    endlocal & exit /b 1
)

if !CRF_INT! GTR 63 (
    >&2 echo ERROR: CRF too big
    endlocal & exit /b 1
)

echo Best CRF : !BEST_CRF!
echo Best VMAF: !BEST_VMAF!

endlocal & (
    set "BEST_CRF=%BEST_CRF%"
    set "BEST_VMAF=%BEST_VMAF%"
)
exit /b 0


rem ============================================================
:FINAL_ENCODE
rem PARAMETERS:
rem   %1 = INPUTFILE
rem   %2 = ENCODER
rem   %3 = PRESET
rem   %4 = ENCODE_SETTINGS
rem   %5 = CRF
rem   %6 = OUTPUTFILE

setlocal EnableDelayedExpansion

set "INPUT=%~1"
set "ENCODER=%~2"
set "PRESET=%~3"
set "ENCODE_SETTINGS=%~4"
set "CRF=%~5"
set "OUTPUT=%~6"

echo Encoding with CRF %CRF%...
set CMD=ab-av1.exe encode -i "%INPUT%" -e %ENCODER% --crf %CRF% %ENCODE_SETTINGS% --preset %PRESET% -o "%OUTPUT%"
echo Executing: !CMD!

!CMD!
if errorlevel 1 (
    >&2 echo ERROR: Final encode failed
    endlocal & exit /b 1
)

endlocal & exit /b 0
