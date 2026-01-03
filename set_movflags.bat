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

rem Count files
set COUNT_TOTAL=0
set COUNT_CURRENT=0
for %%X in (%FILELIST%) do set /a COUNT_TOTAL+=1


rem ============================================================
rem  PROCESS FILES
rem ============================================================
for %%F in (%FILELIST%) do (
    call :PROCESS_FILE "%%~F"
    if errorlevel 1 goto CLEANUP
)
goto END


rem ============================================================
rem  PROCESS A SINGLE FILE
rem ============================================================
:PROCESS_FILE
set /a COUNT_CURRENT+=1
setlocal EnableDelayedExpansion

set "F=%~1"

echo ===========================================================
echo Processing (!COUNT_CURRENT! / !COUNT_TOTAL!) : !F!
echo ===========================================================

rem Switch to file directory
for %%X in ("!F!") do (
    pushd "%%~dpX"
    set "FILENAME=%%~nxX"
    set "BASENAME=%%~nX"
    set "EXT=%%~xX"
)

set "TEMPFILE=temp_!BASENAME!!EXT!"
set "BACKUP=!BASENAME!_backup!EXT!"


rem ============================================================
rem  APPLY MOVFLAGS +FASTSTART
rem ============================================================
ffmpeg -y -i "!FILENAME!" -c copy -map 0 -movflags +faststart "!TEMPFILE!" >nul 2>&1
if errorlevel 1 (
    echo Error applying faststart.
    set EXITCODE=1
    popd
    endlocal & goto :EOF
)


rem ============================================================
rem  BACKUP ORIGINAL
rem ============================================================
ren "!FILENAME!" "!BACKUP!" >nul 2>&1
if errorlevel 1 (
    echo Error renaming original file.
    set EXITCODE=1
    popd
    endlocal & goto :EOF
)


rem ============================================================
rem  REPLACE ORIGINAL WITH TEMP
rem ============================================================
ren "!TEMPFILE!" "!FILENAME!" >nul 2>&1
if errorlevel 1 (
    echo Error replacing original file.
    ren "!BACKUP!" "!FILENAME!" >nul 2>&1
    set EXITCODE=1
    popd
    endlocal & goto :EOF
)

rem Delete backup
del "!BACKUP!" >nul 2>&1

popd

echo Done.
echo.

endlocal & goto :EOF


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
