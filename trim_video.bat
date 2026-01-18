@echo off
setlocal EnableDelayedExpansion

rem ============================================================
rem  DESCRIPTION
rem ============================================================
rem  This script trims video files losslessly using ffmpeg copy mode.
rem
rem  - Input can be: single files, multiple files, folders, or
rem    drag & drop arguments.
rem  - TRIM_FROM and TRIM_TO set the start and end times.
rem  - Output is written as "<basename>_trimmed<ext>".
rem  - The original file is never modified or replaced.
rem
rem  Dependencies:
rem      - ffmpeg.exe
rem      - input_handler.bat
rem      - check_tool.bat
rem ============================================================

set EXITCODE=0

rem ---------------- USER SETTINGS ----------------
set TRIM_FROM=
set TRIM_TO=

rem Validate trimming parameters
if not defined TRIM_FROM if not defined TRIM_TO (
	echo ERROR: At least one of TRIM_FROM or TRIM_TO must be set.
	set EXITCODE=1
	goto END
)


rem ============================================================
rem  MODULES
rem ============================================================
set "CHECK_TOOL=%~dp0scripts\check_tool.bat"
set "INPUT_HANDLER=%~dp0scripts\input_handler.bat"


rem ============================================================
rem  CHECK REQUIRED TOOLS
rem ============================================================
call "%CHECK_TOOL%" CHECK_FFMPEG
if not !errorlevel! == 0 goto END


rem ============================================================
rem  INPUT HANDLING
rem ============================================================
call "%INPUT_HANDLER%" HANDLE_INPUT_VIDEO %*
if not !errorlevel! == 0 goto END

call "%INPUT_HANDLER%" INIT_FILE_ITERATOR


rem ============================================================
rem  PROCESS FILES
rem ============================================================
:LOOP
call "%INPUT_HANDLER%" GET_NEXT_FILE CURRENTFILE
if not defined CURRENTFILE goto END

for %%A in ("%CURRENTFILE%") do (
    pushd "%%~dpA"

    echo ===========================================================
    echo Processing file !FILEINDEX! / !FILECOUNT! : %%~nxA
    echo ===========================================================

    call :PROCESS_FILE "%%~nxA"

    if not "!EXITCODE!"=="0" (
        call :LOG_ERROR "%%A"
        call :CLEANUP
    )

    popd
)

goto LOOP


rem ============================================================
rem  PROCESS_FILE
rem ============================================================
:PROCESS_FILE

set "FILENAME=%~1"
set "BASENAME=%~n1"
set "EXT=%~x1"

set "OUTFILE=%BASENAME%_trimmed%EXT%"

set "TRIM_ARGS="

if defined TRIM_FROM set "TRIM_ARGS=!TRIM_ARGS! -ss !TRIM_FROM!"
if defined TRIM_TO set "TRIM_ARGS=!TRIM_ARGS! -to !TRIM_TO!"

echo Trimming video...
set CMD=ffmpeg -y -xerror -i "%FILENAME%" %TRIM_ARGS% -c copy -map 0 "%OUTFILE%"
echo Executing: !CMD!

!CMD! >nul 2>&1
if not !errorlevel! == 0 (
    echo Error trimming video.
    set EXITCODE=1
    goto :EOF
)

echo Done: %OUTFILE%
echo.

goto :EOF


rem ============================================================
rem  CLEANUP
rem ============================================================
:CLEANUP
rem Nothing to clean up for this
