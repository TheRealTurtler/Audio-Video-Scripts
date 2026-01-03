@echo off
rem ============================================================
rem  DESCRIPTION
rem ============================================================
rem  Handles input paths and builds a clean file list.
rem
rem  - Accepts files or folders
rem  - Expands folders into individual files
rem  - Sends each file to the filter for validation
rem  - Only valid files are added to FILELIST_1..N
rem  - Provides iterator API:
rem        INIT_FILE_ITERATOR
rem        GET_NEXT_FILE <var>
rem ============================================================

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
set FILECOUNT=0

rem No arguments → interactive
if "%~1"=="" (
    set /p USERINPUT=Enter path to file or folder:
    if not defined USERINPUT exit /b 1
    call :PROCESS_PATH "%USERINPUT%"
    goto VALIDATE
)

rem Arguments provided → loop
:ARG_LOOP
if "%~1"=="" goto VALIDATE
call :PROCESS_PATH "%~1%"
shift
goto ARG_LOOP

:VALIDATE
if %FILECOUNT%==0 exit /b 1
exit /b 0


rem ============================================================
rem  PROCESS_PATH — expand folder or accept file
rem ============================================================
:PROCESS_PATH
set "TARGET=%~1"

rem Normalize path
for /f "delims=" %%Z in ("%TARGET%") do set "TARGET=%%~fZ"

rem Folder?
if exist "%TARGET%\" (
    for %%F in ("%TARGET%\*") do (
        if exist "%%~fF" (
            call :CHECK_AND_ADD "%%~fF"
        )
    )
    exit /b 0
)

rem Single file?
if exist "%TARGET%" (
    call :CHECK_AND_ADD "%TARGET%"
    exit /b 0
)

echo WARNING: Path not found: %TARGET%
exit /b 0


rem ============================================================
rem  CHECK_AND_ADD — send file to filter
rem ============================================================
:CHECK_AND_ADD
set "CANDIDATE=%~1"

call "%INPUT_FILTER%" FILTER_VIDEO "%CANDIDATE%"
if errorlevel 1 (
    rem rejected → skip
    exit /b 0
)

rem accepted → add to list
set /a FILECOUNT+=1
set "FILELIST_%FILECOUNT%=%CANDIDATE%"
exit /b 0


rem ============================================================
rem  ITERATOR API
rem ============================================================
:INIT_FILE_ITERATOR
set FILEINDEX=0
exit /b 0

:GET_NEXT_FILE
set /a FILEINDEX+=1
if %FILEINDEX% GTR %FILECOUNT% (
    set "%~1="
    exit /b 0
)
set "%~1=!FILELIST_%FILEINDEX%!"
exit /b 0
