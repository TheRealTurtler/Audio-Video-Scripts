@echo off

rem ============================================================================
rem  DESCRIPTION
rem ============================================================================
rem  Wrapper script for running convert_to_xyz.bat with fixed encoder settings.
rem
rem  ab-av1 is used to determine the optimal CRF based on VMAF analysis.
rem  After the best CRF is found, all input files are encoded to H.264 (x264).
rem
rem  This version also forces 720p output.
rem ============================================================================


rem Encoder settings
set ENCODER=libx264
set PRESET=slow

rem Additional settings for encoding (analysis and final encode)
set SETTINGS_ENCODE_ALWAYS=--enc x264-params=aq-mode=2 --enc x264-params=aq-strength=1.3 --enc x264-params=tune=film --pix-format yuv420p --vfilter scale=1280:-2 --enc profile:v=high --enc level:v=3.1

rem Additional settings for analysis only
set SETTINGS_ENCODE_ANALYSIS=--max-encoded-percent=1000

rem Additional settings for final encoding only
set SETTINGS_ENCODE_FINAL=--acodec libfdk_aac

set OUTPUT_DIR=h264
set ERROR_LOG=h264-failed.txt

rem Number of threads to use (-1 = all)
set THREADS=8


call "%~dp0convert_to_xyz.bat" ^
    %ENCODER% ^
    %PRESET% ^
    "%SETTINGS_ENCODE_ALWAYS%" ^
    "%SETTINGS_ENCODE_ANALYSIS%" ^
    "%SETTINGS_ENCODE_FINAL%" ^
    %OUTPUT_DIR% ^
    %ERROR_LOG% ^
    %THREADS% ^
    %*
