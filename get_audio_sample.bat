@echo off
setlocal enabledelayedexpansion

for %%a in (%*) do (
	ffmpeg -hide_banner -y -ss 09:00 -t 05:00 -i %%a -c copy -map 0:a "audioSample.mkv"
)
