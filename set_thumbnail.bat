@echo off
setlocal EnableDelayedExpansion

rem ============================================================
rem  SET THUMBNAIL TOOL
rem
rem  This script extracts a thumbnail frame from each input video
rem  and embeds it as an attached cover image inside the same file.
rem
rem  - Input can be: files, folders, drag & drop
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


rem ============================================================
rem  PROCESS FILES
rem ============================================================
for %%F in (%FILELIST%) do (
    echo ===========================================================
    echo Processing: %%~F
    echo ===========================================================

    rem Switch to the file's directory
    pushd "%%~dpF"

    set "BASENAME=%%~nF"
    set "EXT=%%~xF"
    set "TEMPTHUMB=thumb_!BASENAME!.jpg"
    set "TEMPFILE=temp_!BASENAME!!EXT!"
    set "BACKUP=!BASENAME!_backup!EXT!"

    rem Extract thumbnail frame
    ffmpeg -y -i "%%~nxF" -ss 1 -vframes 1 "!TEMPTHUMB!" >nul 2>&1
    if errorlevel 1 (
        echo Error extracting thumbnail.
        set EXITCODE=1
        popd
        goto CLEANUP
    )

    rem Remux with embedded cover art
    ffmpeg -y -i "%%~nxF" -i "!TEMPTHUMB!" ^
        -map 0:v -map 0:a? -map 1:v ^
        -c copy -c:v:1 mjpeg ^
        -disposition:v:1 attached_pic ^
        -metadata:s:v:1 title="Cover" ^
        -metadata:s:v:1 comment="Cover (front)" ^
        "!TEMPFILE!" >nul 2>&1

    if errorlevel 1 (
        echo Error embedding thumbnail.
        set EXITCODE=1
        popd
        goto CLEANUP
    )

	rem Rename original → backup
    ren "%%~nxF" "!BACKUP!" >nul 2>&1
    if errorlevel 1 (
        echo Error renaming original file.
        set EXITCODE=1
        popd
        goto CLEANUP
    )

    rem Rename temp → original
    ren "!TEMPFILE!" "%%~nxF" >nul 2>&1
    if errorlevel 1 (
        echo Error replacing original file.
        ren "!BACKUP!" "%%~nxF" >nul 2>&1
        set EXITCODE=1
        popd
        goto CLEANUP
    )

    rem Delete backup and thumbnail
    del "!BACKUP!" >nul 2>&1
    del "!TEMPTHUMB!" >nul 2>&1

    popd
    echo Done.
    echo.
)

set EXITCODE=0
goto END


rem ============================================================
rem  CLEANUP
rem ============================================================

:CLEANUP
if exist "!TEMPTHUMB!" del "!TEMPTHUMB!" >nul 2>&1

rem ============================================================
rem  END
rem ============================================================

:END
exit /b %EXITCODE%
