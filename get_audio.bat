@echo off

set input=%*

:: Get input path(s) if needed.
if not defined input set /p "input=Enter MKV/MP4 path(s): "

:: Exit if no input.
if not defined input exit /b

for %%A in (%input%) do call :step_1 "%%~A"
exit /b

:: Process a folder of MKV or MP4 files or a single file.
:step_1
2>nul pushd "%~1" && (
    for %%A in (*.mkv *.mp4) do call :step_2 "%%~A"
    popd
    goto exit_script
)

:: Exit if not MKV or MP4 file.
if /i not "%~x1" == ".mkv" if /i not "%~x1" == ".mp4" exit /b 1

:: Call single MKV or MP4 file.
call :step_2 "%~1"
exit /b

:step_2
ffmpeg -hide_banner -y -i "%~f1" -vn -c:a copy -map 0 "%~n1.m4a"
