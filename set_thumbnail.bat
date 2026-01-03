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
if not "%errorlevel%"=="0" goto END


rem ============================================================
rem  INPUT HANDLING
rem ============================================================
rem TODO: add parameter for allowed extensions (thumbnails only work with mp4, NOT with mkv and ESPECIALLY NOT with webm)
call "%INPUT_HANDLER%" HANDLE_INPUT_VIDEO %*
if not "%errorlevel%"=="0" goto END

rem --- Count files ---
set COUNT_TOTAL=0
set COUNT_CURRENT=0
for %%X in (%FILELIST%) do set /a COUNT_TOTAL+=1


rem ============================================================
rem  PROCESS FILES
rem ============================================================
for %%F in (%FILELIST%) do (
    rem Switch to the file's directory
    pushd "%%~dpF"

    rem Process the file (only filename, no path)
    call :PROCESS_FILE "%%~nxF"

    rem If an error occurred, log it and clean up
    if not "!EXITCODE!"=="0" (
        call :LOG_ERROR "%%~fF"
        call :CLEANUP
    )

    rem Return to previous directory
    popd
)

goto END


rem ============================================================
rem  PROCESS_FILE
rem ============================================================
:PROCESS_FILE
set /a COUNT_CURRENT+=1

set "FILENAME=%~1"
set "BASENAME=%~n1"
set "EXT=%~x1"

set "TEMPTHUMB=thumb_%BASENAME%.jpg"
set "TEMPFILE=temp_%BASENAME%%EXT%"
set "BACKUP=%BASENAME%_backup%EXT%"

echo ===========================================================
echo Processing (!COUNT_CURRENT! / !COUNT_TOTAL!) : %FILENAME%
echo ===========================================================

rem Extract thumbnail frame
ffmpeg -y -xerror -i "%FILENAME%" -ss 1 -vframes 1 "%TEMPTHUMB%" >nul 2>&1
if not "%errorlevel%"=="0" (
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

if not "%errorlevel%"=="0" (
    echo Error embedding thumbnail.
    set EXITCODE=1
    goto :EOF
)

rem Rename original → backup
ren "%FILENAME%" "%BACKUP%" >nul 2>&1
if not "%errorlevel%"=="0" (
    echo Error renaming original file.
    set EXITCODE=1
    goto :EOF
)

rem Rename temp → original
ren "%TEMPFILE%" "%FILENAME%" >nul 2>&1
if not "%errorlevel%"=="0" (
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
