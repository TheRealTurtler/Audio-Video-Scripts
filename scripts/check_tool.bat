@echo off
rem ============================================================
rem  TOOL CHECK MODULE
rem
rem  This module provides routines to check for required tools:
rem      - CHECK_FFMPEG
rem      - CHECK_FFPROBE
rem      - CHECK_ABAV1
rem      - CHECK_MKVPROPEDIT
rem
rem  Usage:
rem      call check_tool.bat CHECK_FFMPEG
rem      if errorlevel 1 echo ffmpeg missing
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


:CHECK_FFMPEG
where ffmpeg.exe >nul 2>&1
if errorlevel 1 (
    echo Error: ffmpeg.exe not found.
    exit /b 1
)
exit /b 0


:CHECK_FFPROBE
where ffprobe.exe >nul 2>&1
if errorlevel 1 (
    echo Error: ffprobe.exe not found.
    exit /b 1
)
exit /b 0


:CHECK_ABAV1
call "%~f0" CHECK_FFMPEG
if errorlevel 1 exit /b 1

where ab-av1.exe >nul 2>&1
if errorlevel 1 (
    echo Error: ab-av1.exe not found.
    exit /b 1
)
exit /b 0


:CHECK_MKVPROPEDIT
where mkvpropedit.exe >nul 2>&1
if errorlevel 1 (
    echo Error: mkvpropedit.exe not found.
    exit /b 1
)
exit /b 0
