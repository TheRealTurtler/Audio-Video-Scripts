@echo off
setlocal EnableDelayedExpansion

rem ============================================================================
rem  ab-av1 CRF Analysis + Encoding Script
rem
rem  - Accepts files or folders (drag & drop or manual input)
rem  - Runs CRF analysis using ab-av1
rem  - Encodes using the detected CRF
rem  - Output is stored in a "Converted" subfolder
rem  - Output container matches the input container
rem  - Thread usage controlled via CPU affinity (THREADS setting)
rem  - Failed files are logged in "failed.txt" in the source directory
rem ============================================================================

rem ---------------- USER SETTINGS ----------------
set PRESET=4
set ENCODE_SETTINGS=
set ANALYSIS_SETTINGS=--enc vsync=passthrough
set VALID_EXTENSIONS=*.mp4 *.mkv *.mov *.webm

set OUTPUT_DIR=Converted

rem Number of threads to use (-1 = all)
set THREADS=8


rem ============================================================================
rem  FIRST PASS: CALCULATE AFFINITY AND RESTART SCRIPT UNDER THAT AFFINITY
rem ============================================================================

if not defined AFFINITY_BOOTSTRAPPED (
    call :CALC_AFFINITY

    rem Restart this script under the calculated CPU affinity
    set "AFFINITY_BOOTSTRAPPED=1"
    start "" /affinity !AFFINITY! /b cmd /c "%~f0" %*
    exit /b
)

rem From here on, the script is already running under the correct CPU affinity

rem ============================================================================
rem  CHECK FOR ab-av1
rem ============================================================================

where ab-av1.exe >nul 2>&1
if errorlevel 1 (
    echo ab-av1.exe not found.
    exit /b 1
)


rem ============================================================================
rem  INPUT VALIDATION / INTERACTIVE MODE
rem ============================================================================

if "%~1"=="" (
    set /p USERINPUT=Enter path to the file or folder you want to convert: 
    if not defined USERINPUT exit /b 1
    set "ARGS=!USERINPUT!"
) else (
    set ARGS=%*
)


rem ============================================================================
rem  CHANGE WORKING DIRECTORY TO INPUT LOCATION
rem ============================================================================

for %%A in (%ARGS%) do (
    if exist "%%~A\" (
        rem Input is a folder
        cd /d "%%~fA"
    ) else (
        rem Input is a file
        cd /d "%%~dpA"
    )
    goto :CD_DONE
)
:CD_DONE


rem ============================================================================
rem  FILE COLLECTION
rem ============================================================================

set FILELIST=

for %%A in (%ARGS%) do (
    if exist "%%~A\" (
        rem Folder input: collect all matching files
        for %%E in (%VALID_EXTENSIONS%) do (
            for %%F in ("%%~A\%%E") do (

                rem --- Skip files inside OUTPUT_DIR subfolder ---
                for %%P in ("%%~dpF.") do (
                    if /i "%%~nxP"=="%OUTPUT_DIR%" (
                        rem skip this file
                    ) else (
                        if exist "%%~F" set FILELIST=!FILELIST! "%%~F"
                    )
                )

            )
        )
    ) else (
        rem Single file input
        if exist "%%~A" set FILELIST=!FILELIST! "%%~A"
    )
)

if "%FILELIST%"=="" exit /b 1

rem --- Count files ---
set COUNT_TOTAL=0
set COUNT_CURRENT=0
for %%X in (%FILELIST%) do set /a COUNT_TOTAL+=1


rem ============================================================================
rem  PROCESS FILES
rem ============================================================================

echo Starting AV1 Conversion... !COUNT_TOTAL! files

set FAILED_LOG_CREATED=0

for %%F in (%FILELIST%) do call :PROCESS_FILE "%%~F"

echo.
echo All files processed.
if "!FAILED_LOG_CREATED!"=="1" (
    echo Some files failed. See failed.txt in source directory.
)
exit /b 0


rem ============================================================================
rem  PROCESS A SINGLE FILE
rem ============================================================================
:PROCESS_FILE
set /a COUNT_CURRENT+=1
setlocal EnableDelayedExpansion

set "F=%~1"

echo ===========================================================
echo Processing (!COUNT_CURRENT! / !COUNT_TOTAL!) : !F!
echo ===========================================================

rem --- CRF SEARCH ---
set CMD=ab-av1.exe crf-search -i "!F!" %ENCODE_SETTINGS% %ANALYSIS_SETTINGS% --preset %PRESET%
echo Executing: !CMD!

for /f "delims=" %%a in ('!CMD!') do (
	SET CMD_OUT=%%a
)

rem --- PARSE CRF-SEARCH OUTPUT ---
set "BEST_CRF="
set "BEST_VMAF="

for /f "tokens=1-12" %%a in ("!CMD_OUT!") do (
    if /i "%%a"=="crf" (
        set "BEST_CRF=%%b"
    )
    if /i "%%c"=="VMAF" (
        set "BEST_VMAF=%%d"
    )
)

rem --- VALIDATE CRF ---
echo(!BEST_CRF!| findstr /r "^[0-9.][0-9.]*$" >nul
if errorlevel 1 (
    call :LOG_FAIL "!F!" "CRF parsing failed! Output: !CMD_OUT!"
    echo ERROR: CRF parsing failed
    echo.
    endlocal & goto :EOF
)

for /f "tokens=1 delims=." %%x in ("!BEST_CRF!") do set "CRF_INT=%%x"

if !CRF_INT! LSS 1 (
    call :LOG_FAIL "!F!" "CRF too small: !BEST_CRF!"
    echo ERROR: CRF too small
    echo.
    endlocal & goto :EOF
)

if !CRF_INT! GTR 63 (
    call :LOG_FAIL "!F!" "CRF too big: !BEST_CRF!"
    echo ERROR: CRF too big
    echo.
    endlocal & goto :EOF
)

rem --- Build output folder ---
for %%X in ("!F!") do set "OUTDIR=%%~dpX%OUTPUT_DIR%"
if not exist "!OUTDIR!" mkdir "!OUTDIR!"

rem --- Determine output container (same as input) ---
for %%X in ("!F!") do (
    set "EXT=%%~xX"
    set "BASENAME=%%~nX"
)

set "OUTFILE=!OUTDIR!\!BASENAME!_av1!EXT!"

rem --- FINAL ENCODE ---
set CMD=ab-av1.exe encode -i "!F!" --crf !BEST_CRF! %ENCODE_SETTINGS% --preset %PRESET% -o "!OUTFILE!"
echo Executing: !CMD!

!CMD!

if errorlevel 1 (
    call :LOG_FAIL "!F!" "Final encode failed"
    echo ERROR: Final encode failed.
    echo.
    endlocal & goto :EOF
)

echo Done: !OUTFILE!
echo.
endlocal & goto :EOF



rem ============================================================================
rem  CALCULATE CPU AFFINITY MASK
rem ============================================================================
:CALC_AFFINITY
setlocal EnableDelayedExpansion

rem Get total logical processors
for /f "tokens=2 delims==" %%a in ('
    wmic cpu get NumberOfLogicalProcessors /value ^| find "="
') do set "TOTAL=%%a"

rem THREADS = -1 → use all
if "%THREADS%"=="-1" (
    set /a USE=%TOTAL%
) else (
    set /a USE=%THREADS%
)

rem Clamp to valid range
if %USE% GTR %TOTAL% set USE=%TOTAL%
if %USE% LSS 1 set USE=1

rem Build bitmask manually
set MASK=0
for /l %%i in (1,1,%USE%) do (
    set /a MASK=MASK*2+1
)

rem Convert decimal mask to hex string
call :DEC_TO_HEX !MASK! HEX

endlocal & set "AFFINITY=%HEX%"
exit /b



rem ============================================================================
rem  DECIMAL TO HEX STRING
rem ============================================================================
:DEC_TO_HEX
setlocal EnableDelayedExpansion

set /a A=%1
set "MAP=0123456789ABCDEF"
set "H="

:HEX_LOOP
set /a B=A %% 16
set /a A=A / 16
set "H=!MAP:~%B%,1!!H!"
if !A! GTR 0 goto HEX_LOOP

endlocal & set "%2=%H%"
exit /b



rem ============================================================================
rem  LOG FAIL FUNCTION
rem ============================================================================
:LOG_FAIL
set FAILED_LOG_CREATED=1

set "LOGFILE=%CD%\av1-failed.txt"
echo %~1 - %~2>> "%LOGFILE%"

exit /b
