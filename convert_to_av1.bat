@echo off

rem ============================================================================
rem  DESCRIPTION
rem ============================================================================
rem  Wrapper script for running convert_to_xyz.bat with fixed encoder settings.
rem
rem  ab-av1 is used to determine the optimal CRF based on VMAF analysis.
rem  After the best CRF is found, all input files are encoded to AV1.
rem ============================================================================


rem Encoder settings
set ENCODER=libsvtav1
set PRESET=4

rem Additional settings for encoding (analysis and final encode)
set SETTINGS_ENCODE_ALWAYS=--svt enable-variance-boost=1

rem Additional settings for analysis only
set SETTINGS_ENCODE_ANALYSIS=--enc vsync=passthrough

rem Additional settings for final encoding only
set SETTINGS_ENCODE_FINAL=

set OUTPUT_DIR=av1
set ERROR_LOG=av1-failed.txt

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
