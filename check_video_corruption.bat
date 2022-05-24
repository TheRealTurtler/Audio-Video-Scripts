@echo off
setlocal enabledelayedexpansion

for %%a in (%*) do (
	for /F "delims=" %%i in (%%a) do (
		set logfile=%~dp0script_output\%%~ni.log
		echo "!logfile!"
		ffmpeg -v error -i %%a -f null - > "!logfile!" 2>&1
	)
)
