@echo off
setlocal EnableDelayedExpansion

rem ============================================================================
rem  ab-av1 CRF Analysis + Encoding Script
rem
rem  - Accepts files or folders (drag & drop or manual input)
rem  - Runs CRF analysis using ab-av1
rem  - Encodes using the detected CRF
rem  - Output is stored in a "Converted" subfolder
rem  - Output container matches the input container
rem  - Thread usage controlled via CPU affinity (THREADS setting)
rem  - Failed files are logged in "av1-failed.txt" in the source directory
rem ============================================================================


rem ---------------- USER SETTINGS ----------------
set PRESET=4
set ENCODE_SETTINGS=
set ANALYSIS_SETTINGS=--enc vsync=passthrough
set VALID_EXTENSIONS=*.mp4 *.mkv *.mov *.webm

set OUTPUT_DIR=Converted

rem Number of threads to use (-1 = all)
set THREADS=8


rem ============================================================================
rem  MODULES
rem ============================================================================
set "CHECK_TOOL=%~dp0scripts\check_tool.bat"
set "INPUT_HANDLER=%~dp0scripts\input_handler.bat"
set "THREAD_LIMIT=%~dp0scripts\thread_limit.bat"


rem ============================================================================
rem  FIRST PASS: CALCULATE AFFINITY AND RESTART SCRIPT UNDER THAT AFFINITY
rem ============================================================================
if not defined AFFINITY_BOOTSTRAPPED (
    call "%THREAD_LIMIT%" CALC_AFFINITY %THREADS%

    set "AFFINITY_BOOTSTRAPPED=1"
    start "" /affinity !AFFINITY! /b cmd /c "%~f0" %*
    exit /b
)


rem ============================================================================
rem  CHECK FOR ab-av1
rem ============================================================================
call "%CHECK_TOOL%" CHECK_ABAV1
if errorlevel 1 exit /b 1


rem ============================================================================
rem  INPUT HANDLING
rem ============================================================================
call "%INPUT_HANDLER%" HANDLE_INPUT_VIDEO %*
if errorlevel 1 exit /b 1


rem --- Count files ---
set COUNT_TOTAL=0
set COUNT_CURRENT=0
for %%X in (%FILELIST%) do set /a COUNT_TOTAL+=1


rem ============================================================================
rem  PROCESS FILES
rem ============================================================================
echo Starting AV1 Conversion... !COUNT_TOTAL! files

set FAILED_LOG_CREATED=0

for %%F in (%FILELIST%) do call :PROCESS_FILE "%%~F"

echo.
echo All files processed.
if "!FAILED_LOG_CREATED!"=="1" (
    echo Some files failed. See av1-failed.txt in each source directory.
)
exit /b 0



rem ============================================================================
rem  PROCESS A SINGLE FILE
rem ============================================================================
:PROCESS_FILE
set /a COUNT_CURRENT+=1
setlocal EnableDelayedExpansion

set "F=%~1"

rem --- Change working directory to the folder of the current file ---
for %%X in ("!F!") do pushd "%%~dpX"

echo ===========================================================
echo Processing (!COUNT_CURRENT! / !COUNT_TOTAL!) : !F!
echo ===========================================================

rem --- CRF SEARCH ---
set CMD=ab-av1.exe crf-search -i "!F!" %ENCODE_SETTINGS% %ANALYSIS_SETTINGS% --preset %PRESET%
echo Executing: !CMD!

set "CMD_OUT="
for /f "delims=" %%a in ('!CMD!') do (
    set "CMD_OUT=%%a"
)

rem --- PARSE CRF-SEARCH OUTPUT ---
set "BEST_CRF="
set "BEST_VMAF="

for /f "tokens=1-12" %%a in ("!CMD_OUT!") do (
    if /i "%%a"=="crf" (
        set "BEST_CRF=%%b"
    )
    if /i "%%c"=="VMAF" (
        set "BEST_VMAF=%%d"
    )
)

rem --- VALIDATE CRF ---
echo(!BEST_CRF!| findstr /r "^[0-9.][0-9.]*$" >nul
if errorlevel 1 (
    call :LOG_FAIL "!F!" "CRF parsing failed! Output: !CMD_OUT!"
    echo ERROR: CRF parsing failed
    echo.
    popd
    endlocal & goto :EOF
)

for /f "tokens=1 delims=." %%x in ("!BEST_CRF!") do set "CRF_INT=%%x"

if !CRF_INT! LSS 1 (
    call :LOG_FAIL "!F!" "CRF too small: !BEST_CRF!"
    echo ERROR: CRF too small
    echo.
    popd
    endlocal & goto :EOF
)

if !CRF_INT! GTR 63 (
    call :LOG_FAIL "!F!" "CRF too big: !BEST_CRF!"
    echo ERROR: CRF too big
    echo.
    popd
    endlocal & goto :EOF
)

rem --- Build output folder ---
for %%X in ("!F!") do set "OUTDIR=%%~dpX%OUTPUT_DIR%"
if not exist "!OUTDIR!" mkdir "!OUTDIR!"

rem --- Determine output container ---
for %%X in ("!F!") do (
    set "EXT=%%~xX"
    set "BASENAME=%%~nX"
)

set "OUTFILE=!OUTDIR!\!BASENAME!_av1!EXT!"

rem --- FINAL ENCODE ---
set CMD=ab-av1.exe encode -i "!F!" --crf !BEST_CRF! %ENCODE_SETTINGS% --preset %PRESET% -o "!OUTFILE!"
echo Executing: !CMD!

!CMD!

if errorlevel 1 (
    call :LOG_FAIL "!F!" "Final encode failed"
    echo ERROR: Final encode failed.
    echo.
    popd
    endlocal & goto :EOF
)

echo Done: !OUTFILE!
echo.

popd
endlocal & goto :EOF



rem ============================================================================
rem  LOG FAIL FUNCTION
rem ============================================================================
:LOG_FAIL
set FAILED_LOG_CREATED=1

set "LOGFILE=%CD%\av1-failed.txt"
echo %~1 - %~2>> "%LOGFILE%"

exit /b
