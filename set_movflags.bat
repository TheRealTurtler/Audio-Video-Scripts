@echo off
setlocal EnableDelayedExpansion

rem ============================================================
rem  DESCRIPTION
rem ============================================================
rem  This script rewrites video files with -movflags +faststart
rem  using a safe backup-then-rename workflow.
rem
rem  - Input can be: single files, multiple files, folders, or
rem    drag & drop arguments.
rem
rem  Dependencies:
rem      - ffmpeg.exe
rem      - input_handler.bat
rem      - check_tool.bat
rem ============================================================

set EXITCODE=0

rem ============================================================
rem  MODULES
rem ============================================================
set "CHECK_TOOL=%~dp0scripts\check_tool.bat"
set "INPUT_HANDLER=%~dp0scripts\input_handler.bat"


rem ============================================================
rem  CHECK REQUIRED TOOLS
rem ============================================================
call "%CHECK_TOOL%" CHECK_FFMPEG
if not !errorlevel! == 0 (
    set EXITCODE=1
    goto END
)


rem ============================================================
rem  INPUT HANDLING
rem ============================================================
call "%INPUT_HANDLER%" HANDLE_INPUT_VIDEO %*
if not !errorlevel! == 0 (
    set EXITCODE=1
    goto END
)

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
rem  PROCESS A SINGLE FILE
rem ============================================================
:PROCESS_FILE

set "FILENAME=%~1"
set "BASENAME=%~n1"
set "EXT=%~x1"

rem Temp and backup names
set "TEMPFILE=temp_!BASENAME!!EXT!"
set "BACKUP=!BASENAME!_backup!EXT!"

rem Apply faststart
set CMD=ffmpeg -y -xerror -i "!FILENAME!" -c copy -map 0 -movflags +faststart "!TEMPFILE!"
echo Executing: !CMD!

!CMD! >nul 2>&1
if not !errorlevel! == 0 (
    echo Error applying faststart.
    set EXITCODE=1
	goto :EOF
)

rem Backup original
ren "!FILENAME!" "!BACKUP!" >nul 2>&1
if not !errorlevel! == 0 (
    echo Error renaming original file.
    set EXITCODE=1
	goto :EOF
)

rem Replace original with temp
ren "!TEMPFILE!" "!FILENAME!" >nul 2>&1
if not !errorlevel! == 0 (
    echo Error replacing original file.
    ren "!BACKUP!" "!FILENAME!" >nul 2>&1
    set EXITCODE=1
    goto :EOF
)

del "!BACKUP!" >nul 2>&1

echo Done.
echo.

endlocal & exit /b 0


rem ============================================================
rem  CLEANUP
rem ============================================================
:CLEANUP
echo Cleaning up...

if exist "%TEMPFILE%" del "%TEMPFILE%" >nul 2>&1
if exist "%BACKUP%" del "%BACKUP%" >nul 2>&1

goto :EOF


rem ============================================================
rem  LOG_ERROR
rem ============================================================
:LOG_ERROR
echo ERROR processing file: %~1
rem TODO: implement error logging
goto :EOF


rem ============================================================
rem  END
rem ============================================================
:END
exit /b %EXITCODE%
