# Audio-Video-Scripts

A collection of small automation scripts for working with audio and video files on Windows.

This repository contains Python scripts and batch helpers for tasks such as:
- adding or merging audio tracks into video files
- normalizing loudness with ffmpeg
- renaming and tagging MKV files based on XML metadata
- converting video files to common formats
- extracting audio tracks and generating thumbnails
- checking video file integrity

## Included scripts

### Python scripts
- `add_audio_track_mt.py`
  - Adds audio tracks to video files using metadata from `info.xml`
  - Supports optional loudness normalization via ffmpeg `loudnorm`
  - Multi-threaded processing for faster batch runs
- `add_audio_track_st.py`
  - Older single-threaded version of the audio track adder
  - Kept for reference; `add_audio_track_mt.py` can be configured with `MAX_THREADS = 1` for sequential processing
- `rename_video.py`
  - Renames multiple video files according to titles defined in `info.xml`
  - Updates MKV title tags using `mkvpropedit`

### Batch helpers
- `convert_to_av1.bat`
- `convert_to_h264.bat`
- `convert_to_h264_1080p.bat`
- `convert_to_h264_720p.bat`
- `convert_to_h265.bat`
- `convert_to_xyz.bat`
- `get_audio.bat`
- `get_audio_sample.bat`
- `trim_video.bat`
- `set_audio_to_german.bat`
- `set_movflags.bat`
- `set_thumbnail.bat`
- `check_video_corruption.bat`

These batch files are convenience wrappers for common ffmpeg and file operations in this repository.

## Configuration

Most Python scripts are configured by editing the settings at the top of the file.
Key settings include input/output paths, thread count, encoder options, and XML file locations.
The example configuration in `example/info.xml` shows the expected metadata format for episodes, seasons, and file names.

## Example

The `example/` folder contains a sample `info.xml` and example directory layout to demonstrate how the XML-based scripts expect media and audio files to be organized.

## Requirements

- Windows environment (scripts are written for Windows path handling and batch usage)
- [`ffmpeg.exe`](https://ffmpeg.org/) available in the repository root or on the system PATH
- [`ffprobe.exe`](https://ffmpeg.org/) available in the repository root or on the system PATH
- [`mkvpropedit.exe`](https://mkvtoolnix.download/) from MKVToolNix for MKV metadata updates
- [`ab-av1.exe`](https://github.com/alexheretic/ab-av1) available in the repository root or on the system PATH
- [Python 3.x](https://www.python.org/) for the `.py` scripts

## Notes

- Adjust paths and filenames in the Python scripts before running them.

## License

This repository is licensed under the MIT License.
