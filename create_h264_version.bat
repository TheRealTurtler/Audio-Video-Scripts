:: Script to create a h.264 version of all input files
:: Conversion is done using constant quality 18

@echo off
setlocal enabledelayedexpansion

set /p input=Copy Subtitles? (y/n):
if /I "%input%"=="y" goto with_subtitles
goto without_subtitles

:with_subtitles:
for %%a in (%*) do (
	for /F "delims=" %%i in (%%a) do (
		set outfile=%%~di%%~pi%%~ni - H264%%~xi
		ffmpeg -hide_banner -y -i %%a -c:a copy -c:s copy -c:v h264_amf -rc_mode CQP -qp_i 18 -qp_p 18 -qp_b 18 -map 0 "!outfile!"
	)
)
goto exit

:without_subtitles
for %%a in (%*) do (
	for /F "delims=" %%i in (%%a) do (
		set outfile=%%~di%%~pi%%~ni - H264%%~xi
		ffmpeg -hide_banner -y -i %%a -c:a copy -c:v h264_amf -rc_mode CQP -qp_i 18 -qp_p 18 -qp_b 18 -map 0:v -map 0:a "!outfile!"
	)
)
goto exit

:exit
