@echo off
setlocal

rem ============================================================================
rem  DESCRIPTION
rem ============================================================================
rem  This module validates a single file path and checks whether the file has
rem  a supported video extension.
rem ============================================================================


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


rem ============================================================================
rem  FILTER VIDEO FILES
rem ============================================================================
:FILTER_VIDEO
setlocal

rem Allowed extensions (without dot)
set "ALLOWED_EXT=mp4 mkv mov webm"

set "FILE=%~1"
if not exist "%FILE%" (
    endlocal & exit /b 1
)

rem Extract extension (remove leading dot)
set "EXT=%~x1"
set "EXT=%EXT:~1%"

rem Validate extension
for %%E in (%ALLOWED_EXT%) do (
    if /i "%%E"=="%EXT%" (
        endlocal & exit /b 0
    )
)

endlocal & exit /b 1
