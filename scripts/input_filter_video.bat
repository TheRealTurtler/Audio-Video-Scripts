@echo off
rem ============================================================
rem  INPUT FILTER: VIDEO FILES
rem
rem  Provides routines:
rem      - FILTER_VIDEO
rem
rem  Usage:
rem      call input_filter_video.bat FILTER_VIDEO <path>
rem
rem  Behavior:
rem      - If folder: collects all video files
rem      - If file: adds it to FILELIST
rem ============================================================


rem --- Dispatcher ---
if "%~1" neq "" (
  2>nul >nul findstr /rc:"^ *:%~1\>" "%~f0" && (
    shift /1
    goto %1
  ) || (
    >&2 echo ERROR: routine %~1 not found
    exit /b 1
  )
) else (
  >&2 echo ERROR: missing routine
  exit /b 1
)
exit /b


:FILTER_VIDEO
set "TARGET=%~1"

if not defined VIDEO_EXTENSIONS (
    set "VIDEO_EXTENSIONS=*.mp4 *.mkv *.mov *.webm"
)

rem Normalize path
for /f "delims=" %%Z in ("%TARGET%") do set "TARGET=%%~fZ"

rem Folder
if exist "%TARGET%\" (
    pushd "%TARGET%" >nul
    for %%E in (%VIDEO_EXTENSIONS%) do (
        for %%F in (%%E) do (
            set "FILELIST=!FILELIST! "%%~fF""
        )
    )
    popd >nul
    exit /b 0
)

rem Single file
if exist "%TARGET%" (
    set "FILELIST=!FILELIST! "%TARGET%""
    exit /b 0
)

echo WARNING: Path not found: %TARGET%
exit /b 0
