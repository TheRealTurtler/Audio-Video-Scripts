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

rem Additional settings when encoding (analysis and final encode)
set ENCODER_SETTINGS=--enc x265-params=aq-mode=3

rem Additional settings when encoding (analysis only)
set ANALYSIS_SETTINGS=--max-encoded-percent=1000

set OUTPUT_DIR=h265
set ERROR_LOG=h265-failed.txt

rem Number of threads to use (-1 = all)
set THREADS=8


call "%~dp0convert_to_xyz.bat" ^
    %ENCODER% ^
    %PRESET% ^
    "%ENCODER_SETTINGS%" ^
    "%ANALYSIS_SETTINGS%" ^
    %OUTPUT_DIR% ^
    %ERROR_LOG% ^
    %THREADS% ^
    %*
