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
rem  - All processing happens inside the video's own directory.
rem  - A thumbnail named "thumb_<filename>.jpg" is created.
rem  - A temporary output file "temp_<filename>.<ext>" is generated.
rem  - After successful processing, the original file is safely
rem    replaced using a backup-then-rename workflow.
rem
rem  Supported formats for folder scanning:
rem      *.mp4 *.mkv *.mov *.webm
rem
rem  Requirements:
rem      ffmpeg.exe must be available in PATH or next to this script.
rem ============================================================


rem ============================================================
rem  CHECK FOR FFMPEG
rem ============================================================

where ffmpeg.exe >nul 2>&1
if errorlevel 1 (
    echo Error: ffmpeg.exe not found.
    set EXITCODE=1
    goto END
)

rem ============================================================
rem  INPUT HANDLING
rem ============================================================

set "FILELIST="

if "%~1"=="" (
    set /p USERINPUT=Enter path to file or folder:
    if not defined USERINPUT (
        echo No input provided.
        set EXITCODE=1
        goto END
    )
    call :COLLECT_INPUT "%USERINPUT%"
) else (
    :ARG_LOOP
    if "%~1"=="" goto AFTER_INPUT
    call :COLLECT_INPUT "%~1%"
    shift
    goto ARG_LOOP
)

:AFTER_INPUT

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

    rem Switch to the file's directory
    pushd "%%~dpF"

    set "BASENAME=%%~nF"
    set "EXT=%%~xF"

    rem Local thumbnail name
    set "TEMPTHUMB=thumb_!BASENAME!.jpg"

    rem Extract thumbnail frame
    ffmpeg -y -i "%%~nxF" -ss 1 -vframes 1 "!TEMPTHUMB!" >nul 2>&1
    if errorlevel 1 (
        echo Error extracting thumbnail.
        set EXITCODE=1
        popd
        goto CLEANUP
    )

    rem Local temporary output file
    set "TEMPFILE=temp_!BASENAME!!EXT!"

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

    rem Safe replace original file
    set "BACKUP=!BASENAME!_backup!EXT!"

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
goto END


rem ============================================================
rem  INPUT COLLECTION FUNCTION
rem ============================================================

:COLLECT_INPUT
set "TARGET=%~1"

rem Normalize path
for /f "delims=" %%Z in ("%TARGET%") do set "TARGET=%%~fZ"

if exist "%TARGET%\" (
    rem Folder: collect video files
    pushd "%TARGET%" >nul
    for %%E in (*.mp4 *.mkv *.mov *.webm) do (
        set "FILELIST=!FILELIST! "%%~fE""
    )
    popd >nul
) else (
    rem Single file
    if exist "%TARGET%" (
        set "FILELIST=!FILELIST! "%TARGET%""
    )
)
exit /b


rem ============================================================
rem  END
rem ============================================================

:END
if exist "!TEMPTHUMB!" del "!TEMPTHUMB!" >nul 2>&1
echo.
echo Script finished with exit code %EXITCODE%.
exit /b %EXITCODE%
