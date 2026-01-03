@echo off
setlocal EnableDelayedExpansion

rem ============================================================
rem  DESCRIPTION
rem ============================================================
rem  This script extracts a thumbnail frame from each input video
rem  and embeds it as an attached cover image inside the same file.
rem
rem  - Input can be: single files, multiple files, folders, or
rem    drag & drop arguments.
rem  - After successful processing, the original file is safely
rem    replaced using a backup-then-rename workflow.
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

set "TEMPTHUMB=thumb_%BASENAME%.jpg"
set "TEMPFILE=temp_%BASENAME%%EXT%"
set "BACKUP=%BASENAME%_backup%EXT%"

rem Extract thumbnail frame
ffmpeg -y -xerror -i "%FILENAME%" -ss 1 -vframes 1 "%TEMPTHUMB%" >nul 2>&1
if not !errorlevel! == 0 (
    echo Error extracting thumbnail.
    set EXITCODE=1
    goto :EOF
)

rem Remux with embedded cover art
ffmpeg -y -xerror -i "%FILENAME%" -i "%TEMPTHUMB%" ^
    -map 0:v:0 ^
    -map 0:a? ^
    -map 1:v ^
    -c copy -c:v:1 mjpeg ^
    -disposition:v:1 attached_pic ^
    -metadata:s:v:1 title="Cover" ^
    -metadata:s:v:1 comment="Cover (front)" ^
    "%TEMPFILE%" >nul 2>&1

if not !errorlevel! == 0 (
    echo Error embedding thumbnail.
    set EXITCODE=1
    goto :EOF
)

rem Rename original → backup
ren "%FILENAME%" "%BACKUP%" >nul 2>&1
if not !errorlevel! == 0 (
    echo Error renaming original file.
    set EXITCODE=1
    goto :EOF
)

rem Rename temp → original
ren "%TEMPFILE%" "%FILENAME%" >nul 2>&1
if not !errorlevel! == 0 (
    echo Error replacing original file.
    ren "%BACKUP%" "%FILENAME%" >nul 2>&1
    set EXITCODE=1
    goto :EOF
)

rem Delete backup and thumbnail
del "%BACKUP%" >nul 2>&1
del "%TEMPTHUMB%" >nul 2>&1

echo Done.
echo.

goto :EOF


rem ============================================================
rem  CLEANUP
rem ============================================================
:CLEANUP
echo Cleaning up...

if exist "%TEMPTHUMB%" del "%TEMPTHUMB%" >nul 2>&1
if exist "%TEMPFILE%" del "%TEMPFILE%" >nul 2>&1

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
