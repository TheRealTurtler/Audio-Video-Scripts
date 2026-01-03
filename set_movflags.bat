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


rem ============================================================
rem  MODULES
rem ============================================================
set "CHECK_TOOL=%~dp0scripts\check_tool.bat"
set "INPUT_HANDLER=%~dp0scripts\input_handler.bat"


rem ============================================================
rem  CHECK REQUIRED TOOLS
rem ============================================================
call "%CHECK_TOOL%" CHECK_FFMPEG
if errorlevel 1 goto END


rem ============================================================
rem  INPUT HANDLING
rem ============================================================
call "%INPUT_HANDLER%" HANDLE_INPUT_VIDEO %*
if errorlevel 1 goto END

call "%INPUT_HANDLER%" INIT_FILE_ITERATOR


rem ============================================================
rem  PROCESS FILES
rem ============================================================
:LOOP
call "%INPUT_HANDLER%" GET_NEXT_FILE CURRENTFILE
if not defined CURRENTFILE goto END

for %%A in ("%CURRENTFILE%") do (
    echo ===========================================================
    echo Processing !FILEINDEX! / !FILECOUNT! : %%~nxA
    echo ===========================================================

    pushd "%%~dpA"
    call :PROCESS_FILE "%%~nxA"
    popd

    if errorlevel 1 goto CLEANUP
)

goto LOOP


rem ============================================================
rem  PROCESS A SINGLE FILE
rem ============================================================
:PROCESS_FILE
setlocal EnableDelayedExpansion

rem Input filename
set "FILENAME=%~1"
set "BASENAME=%~n1"
set "EXT=%~x1"

rem Temp and backup names
set "TEMPFILE=temp_!BASENAME!!EXT!"
set "BACKUP=!BASENAME!_backup!EXT!"

rem Apply faststart
ffmpeg -y -i "!FILENAME!" -c copy -map 0 -movflags +faststart "!TEMPFILE!" >nul 2>&1
if errorlevel 1 (
    echo Error applying faststart.
    endlocal & exit /b 1
)

rem Backup original
ren "!FILENAME!" "!BACKUP!" >nul 2>&1
if errorlevel 1 (
    echo Error renaming original file.
    endlocal & exit /b 1
)

rem Replace original with temp
ren "!TEMPFILE!" "!FILENAME!" >nul 2>&1
if errorlevel 1 (
    echo Error replacing original file.
    ren "!BACKUP!" "!FILENAME!" >nul 2>&1
    endlocal & exit /b 1
)

rem Remove backup
del "!BACKUP!" >nul 2>&1

echo Done.
echo.

endlocal & exit /b 0


rem ============================================================
rem  CLEANUP
rem ============================================================
:CLEANUP
goto END


rem ============================================================
rem  END
rem ============================================================
:END
exit /b %EXITCODE%
