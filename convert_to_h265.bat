@echo off

rem ============================================================================
rem  DESCRIPTION
rem ============================================================================
rem  Wrapper script for running convert_to_xyz.bat with fixed encoder settings.
rem
rem  ab-av1 is used to determine the optimal CRF based on VMAF analysis.
rem  After the best CRF is found, all input files are encoded to H.265 (x265).
rem ============================================================================


rem Encoder settings
set ENCODER=libx265
set PRESET=slow

rem Additional settings for encoding (analysis and final encode)
set SETTINGS_ENCODE_ALWAYS=--enc x265-params=aq-mode=3 --enc x265-params=aq-strength=1.3 --enc x265-params=tune=film

rem Additional settings for analysis only
set SETTINGS_ENCODE_ANALYSIS=

rem Additional settings for final encoding only
set SETTINGS_ENCODE_FINAL=

set OUTPUT_DIR=h265
set ERROR_LOG=h265-failed.txt

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
