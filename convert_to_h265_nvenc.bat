@echo off

rem ============================================================================
rem  DESCRIPTION
rem ============================================================================
rem  Wrapper script for running convert_to_xyz.bat with fixed encoder settings.
rem
rem  ab-av1 is used to determine the optimal CRF based on VMAF analysis.
rem  After the best CRF is found, all input files are encoded to H.265 (hevc_nvenc).
rem
rem  NOTE: File sizes will be larger than with x265!
rem ============================================================================


rem Encoder settings
set ENCODER=hevc_nvenc
set PRESET=slow

rem Additional settings for encoding (analysis and final encode)
set SETTINGS_ENCODE_ALWAYS=--enc spatial-aq=1 --enc temporal-aq=1 --enc aq-strength=8 --enc rc-lookahead=32 --enc rc=vbr

rem Additional settings for analysis only
set SETTINGS_ENCODE_ANALYSIS=

rem Additional settings for final encoding only
set SETTINGS_ENCODE_FINAL=

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
