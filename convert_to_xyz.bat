@echo off
setlocal EnableDelayedExpansion

rem ============================================================================
rem  DESCRIPTION
rem ============================================================================
rem  Generic conversion script using ab-av1 CRF search and final encode.
rem
rem  - Accepts files or folders
rem  - Uses convert_ab-av1.bat for CRF search and final encode
rem  - Output is stored in a user-defined subfolder
rem  - Output container matches the input container
rem  - Thread usage is controlled via CPU affinity (THREADS setting)
rem  - Failed files are logged in a user-defined log file
rem
rem  Dependencies:
rem      - ffmpeg.exe
rem      - ab-av1.exe
rem      - scripts/check_tool.bat
rem      - scripts/input_handler.bat
rem      - scripts/thread_limit.bat
rem      - scripts/convert_ab-av1.bat
rem      - set_thumbnail.bat
rem      - set_movflags.bat
rem ============================================================================


rem ---------------- USER PARAMETERS ----------------
set "ENCODER=%~1"
set "PRESET=%~2"
set "SETTINGS_ENCODE_ALWAYS=%~3"
set "SETTINGS_ENCODE_ANALYSIS=%~4"
set "SETTINGS_ENCODE_FINAL=%~5"
set "OUTPUT_DIR=%~6"
set "ERROR_LOG=%~7"
set "THREADS=%~8"

rem ============================================================================
rem  MODULES
rem ============================================================================
set "INPUT_HANDLER=%~dp0scripts\input_handler.bat"
set "THREAD_LIMIT=%~dp0scripts\thread_limit.bat"
set "CRF_MODULE=%~dp0scripts\convert_ab-av1.bat"
set "SET_THUMBNAIL=%~dp0set_thumbnail.bat"
set "SET_MOVFLAGS=%~dp0set_movflags.bat"


rem ============================================================================
rem  FIRST PASS: CALCULATE AFFINITY AND RESTART SCRIPT UNDER THAT AFFINITY
rem ============================================================================
if not defined AFFINITY_BOOTSTRAPPED (
    call "%THREAD_LIMIT%" CALC_AFFINITY %THREADS%
    if not !errorlevel! == 0 exit /b 1

    set "AFFINITY_BOOTSTRAPPED=1"
    start "" /affinity !AFFINITY! /b "%ComSpec%" /c ""%~f0" %*"
    exit /b
)


rem ============================================================================
rem  INPUT HANDLING
rem ============================================================================

rem Shift first 8 arguments so the original 9th parameter is accessed as %~1
for /L %%I in (1,1,8) do shift

rem --- Collect input files or folders ---
set "INPUTS="

:COLLECT_INPUTS
if "%~1"=="" goto DONE_INPUTS

set "CUR=%~1"

if not defined INPUTS (
    set INPUTS="%CUR%"
) else (
    set INPUTS=%INPUTS% "%CUR%"
)

shift
goto COLLECT_INPUTS

:DONE_INPUTS

call "%INPUT_HANDLER%" HANDLE_INPUT_VIDEO %INPUTS%
if not !errorlevel! == 0 exit /b 1

call "%INPUT_HANDLER%" INIT_FILE_ITERATOR


rem ============================================================================
rem  PROCESS FILES
rem ============================================================================
echo Starting Conversion with %ENCODER% Encoder... !FILECOUNT! files
echo.

set FAILED_LOG_CREATED=0

:LOOP
call "%INPUT_HANDLER%" GET_NEXT_FILE CURRENTFILE
if not defined CURRENTFILE goto DONE

for %%A in ("%CURRENTFILE%") do (
    echo ===========================================================
    echo Processing !FILEINDEX! / !FILECOUNT! : %%~nxA
    echo ===========================================================

    pushd "%%~dpA"
    call :PROCESS_FILE "%%~nxA"
    popd
)

goto LOOP

:DONE
echo.
echo All files processed.
if "!FAILED_LOG_CREATED!"=="1" (
    echo Some files failed. See %ERROR_LOG% in each source directory.
)
exit /b 0


rem ============================================================================
rem  PROCESS A SINGLE FILE
rem ============================================================================
:PROCESS_FILE
setlocal EnableDelayedExpansion

set "F=%~1"


rem --- CRF SEARCH ---
call "%CRF_MODULE%" CRF_SEARCH ".\!F!" %ENCODER% %PRESET% "%SETTINGS_ENCODE_ALWAYS%" "%SETTINGS_ENCODE_ANALYSIS%"
if not !errorlevel! == 0 (
    call :LOG_FAIL "!F!" "CRF search failed"
    endlocal & exit /b 1
)

set "BEST_CRF=%BEST_CRF%"
set "BEST_VMAF=%BEST_VMAF%"


rem --- Build output folder ---
for %%X in ("!F!") do set "OUTDIR=%%~dpX%OUTPUT_DIR%"
if not exist "!OUTDIR!" mkdir "!OUTDIR!"

for %%X in ("!F!") do (
    set "EXT=%%~xX"
    set "BASENAME=%%~nX"
)

set "OUTFILE=!OUTDIR!\!BASENAME!!EXT!"


rem --- FINAL ENCODE ---
call "%CRF_MODULE%" FINAL_ENCODE ".\!F!" %ENCODER% %PRESET% "%SETTINGS_ENCODE_ALWAYS%" "%SETTINGS_ENCODE_FINAL%" %BEST_CRF% "!OUTFILE!"
if not !errorlevel! == 0 (
    call :LOG_FAIL "!F!" "Final encode failed"
    endlocal & exit /b 1
)


rem --- Set thumbnail ---
echo Setting thumbnail...
call "%SET_THUMBNAIL%" "!OUTFILE!"
if not !errorlevel! == 0 (
    call :LOG_FAIL "!F!" "Thumbnail embedding failed"
    endlocal & exit /b 1
)

rem --- Apply movflags faststart ---
echo Setting movflags...
call "%SET_MOVFLAGS%" "!OUTFILE!"
if not !errorlevel! == 0 (
    call :LOG_FAIL "!F!" "Setting movflags failed"
    endlocal & exit /b 1
)

echo Done: !OUTFILE!
echo.

endlocal & exit /b 0


rem ============================================================================
rem  LOG FAIL
rem ============================================================================
:LOG_FAIL
set FAILED_LOG_CREATED=1
set "LOGFILE=%CD%\%ERROR_LOG%"
echo %~1 - %~2>> "%LOGFILE%"
exit /b
