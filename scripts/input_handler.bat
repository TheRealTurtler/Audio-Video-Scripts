@echo off
rem ============================================================
rem  INPUT HANDLER MODULE (DISPATCHER)
rem
rem  Provides routines:
rem      - HANDLE_INPUT_VIDEO
rem
rem  Responsibilities:
rem      - Initialize FILELIST
rem      - Handle interactive input if no arguments are given
rem ============================================================

rem Path to filter module
set "INPUT_FILTER=%~dp0input_filter_video.bat"

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


:HANDLE_INPUT_VIDEO
set "FILELIST="

rem No arguments → interactive
if "%~1"=="" (
    set /p USERINPUT=Enter path to file or folder:
    if not defined USERINPUT (
        echo No input provided.
        exit /b 1
    )
    call "%INPUT_FILTER%" FILTER_VIDEO "%USERINPUT%"
    goto VALIDATE
)

rem Arguments provided → loop
:ARG_LOOP
if "%~1"=="" goto VALIDATE
call "%INPUT_FILTER%" FILTER_VIDEO "%~1%"
shift
goto ARG_LOOP

:VALIDATE
if "%FILELIST%"=="" (
    echo No valid video files found.
    exit /b 1
)
exit /b 0
