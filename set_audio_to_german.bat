@echo off
setlocal enabledelayedexpansion

for %%a in (%*) do (
	for /F "delims=" %%i in (%%a) do (
		set tempfile=%%~di%%~pitemp_%%~ni%%~xi
		ffmpeg -hide_banner -y -i %%a -c copy -metadata:s:a language=deu "!tempfile!"
		if !errorlevel! equ 0 (
			del %%a
			rename "!tempfile!" "%%~ni%%~xi"
		)
	)
)
