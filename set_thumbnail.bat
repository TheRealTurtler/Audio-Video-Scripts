@echo off
setlocal enabledelayedexpansion

rem ============================================================
rem  DESCRIPTION
rem ============================================================
echo This script creates a thumbnail from a video file and
echo embeds it as cover art (attached_pic) into an MP4 container
echo so that Windows Explorer can show a thumbnail.
echo.

rem ============================================================
rem  CHECK FOR FFMPEG
rem ============================================================

where ffmpeg.exe >nul 2>&1
if errorlevel 1 (
    echo Error: ffmpeg.exe not found.
    echo Place ffmpeg.exe in the same folder as this script or in PATH.
    set EXITCODE=1
    goto END
)

rem ============================================================
rem  INPUT VALIDATION / INTERACTIVE MODE
rem ============================================================

if "%~1"=="" (
    set /p USERINPUT=Enter path to the video file: 
    if not defined USERINPUT (
        echo No input provided.
        set EXITCODE=1
        goto END
    )
    set "ARGS=!USERINPUT!"
) else (
    set ARGS=%*
)

rem ============================================================
rem  FILE COLLECTION
rem ============================================================

set FILELIST=

for %%A in (%ARGS%) do (
    if exist "%%~A" (
        set FILELIST=!FILELIST! "%%~A"
    )
)

if "%FILELIST%"=="" (
    echo No valid files found.
    set EXITCODE=1
    goto END
)

rem ============================================================
rem  PROCESS FILES
rem ============================================================

for %%F in (%FILELIST%) do (
    echo ===========================================================
    echo Processing: %%~F
    echo ===========================================================

    rem --- CREATE TEMP THUMBNAIL ---
    set "TEMPTHUMB=%TEMP%\thumb_!RANDOM!.jpg"

    echo Extracting thumbnail frame...
    ffmpeg -y -i "%%~F" -ss 1 -vframes 1 "!TEMPTHUMB!" >nul 2>&1
    if errorlevel 1 (
        echo Error extracting thumbnail.
        set EXITCODE=1
        goto CLEANUP
    )

    rem --- BUILD OUTPUT PATH (MP4 with cover) ---
    set "OUTDIR=%%~dpFconverted"
    set "OUTFILE=!OUTDIR!\%%~nF-thumb.mp4"

    if not exist "!OUTDIR!" mkdir "!OUTDIR!"

    rem --- REMUX AND EMBED COVER ---
    echo Embedding thumbnail as cover art...
    ffmpeg -y -i "%%~F" -i "!TEMPTHUMB!" ^
        -map 0:v -map 0:a? -map 1:v ^
        -c copy -c:v:1 mjpeg ^
        -disposition:v:1 attached_pic ^
        -metadata:s:v:1 title="Cover" ^
        -metadata:s:v:1 comment="Cover (front)" ^
        "!OUTFILE!" >nul 2>&1

    if errorlevel 1 (
        echo Error embedding thumbnail.
        set EXITCODE=1
        goto CLEANUP
    )

    echo Done: !OUTFILE!
    echo.
)

set EXITCODE=0
goto END

rem ============================================================
rem  CLEANUP
rem ============================================================

:CLEANUP
if exist "!TEMPTHUMB!" del "!TEMPTHUMB!" >nul 2>&1
goto END

rem ============================================================
rem  END
rem ============================================================

:END
if exist "!TEMPTHUMB!" del "!TEMPTHUMB!" >nul 2>&1
echo.
echo Script finished with exit code %EXITCODE%.
pause
exit /b %EXITCODE%
