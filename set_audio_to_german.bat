@echo off

set input=%*

:: Get input path(s) if needed.
if not defined input set /p "input=Enter MKV path(s): "

:: Exit if no input.
if not defined input exit /b

for %%A in (%input%) do call :step_1 "%%~A"
exit /b

:: Process a folder of MKV files or a single file.
:step_1
2>nul pushd "%~1" && (
    for %%A in (*.mkv *.mp4) do call :step_2 "%%~A"
    popd
    goto exit_script
)

:: Exit if not MKV file.
if /i not "%~x1" == ".mkv" exit /b 1

:: Call single MKV file.
call :step_2 "%~1"
exit /b

:step_2
mkdir "%~d1%~p1..\temp"
ffmpeg -hide_banner -y -i "%~f1" -c copy -metadata:s:a language=deu "%~d1%~p1..\temp\temp_%~n1%~x1"
if %errorlevel% equ 0 move /y "%~d1%~p1..\temp\temp_%~n1%~x1" "%~f1"
for /F %%i in ('dir /b "%~d1%~p1..\temp\*.*"') do (
   echo Folder temp is not empty.
   exit /b
)
call :delete_temp_folder "%~d1%~p1..\temp\"
exit /b

:delete_temp_folder
rmdir /q "%~f1"
exit /b
