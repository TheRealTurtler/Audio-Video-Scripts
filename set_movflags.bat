@echo off

set input=%*

:: Get input path(s) if needed.
if not defined input set /p "input=Enter Video path(s): "

:: Exit if no input.
if not defined input exit /b

for %%A in (%input%) do call :step_1 "%%~A"
goto exit_script

:: Process a folder of Video files or a single file.
:step_1
2>nul pushd "%~1" && (
    for %%A in (*.mkv *.mp4 *.webm) do call :step_2 "%%~A"
    popd
    goto exit_script
)

:: Exit if not MKV or MP4 file.
if /i not "%~x1" == ".mkv" if /i not "%~x1" == ".mp4" if /i not "%~x1" == ".webm" goto exit_script

:: Call single MKV or MP4 file.
call :step_2 "%~1"
goto exit_script

:step_2
mkdir "%~d1%~p1..\temp"
ffmpeg -hide_banner -y -i "%~f1" -c copy -map 0 -movflags +faststart "%~d1%~p1..\temp\temp_%~n1%~x1"
if %errorlevel% equ 0 move /y "%~d1%~p1..\temp\temp_%~n1%~x1" "%~f1"
for /F %%i in ('dir /b "%~d1%~p1..\temp\*.*"') do (
   echo Folder temp is not empty.
   goto exit_script
)
call :delete_temp_folder "%~d1%~p1..\temp\"
goto exit_script

:delete_temp_folder
rmdir /q "%~f1"
exit /b

:exit_script
pause
exit /b