@echo off
rem ============================================================
rem  DESCRIPTION
rem ============================================================
rem  This module handles incoming input paths and prepares a list
rem  of files for further processing.
rem
rem  - Initializes FILELIST for the caller
rem  - Accepts one or more file or folder paths as arguments
rem  - If no arguments are provided, interactive input is requested
rem  - Delegates path filtering to the appropriate input filter
rem  - Ensures FILELIST contains only valid paths
rem
rem  Usage:
rem      call input_handler.bat HANDLE_INPUT_VIDEO <paths...>
rem
rem  Dependencies:
rem      - input_filter_video.bat
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
