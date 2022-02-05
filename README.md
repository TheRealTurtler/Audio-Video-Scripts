# Audio-Video-Scripts
Collection of various scripts to edit audio and/or video files.

Important settings are contained near the top of each script.

# add_audio_track_mt
Add an audio tracks to a video file and optionally normalizes the loudness using ffmpeg's `loudnorm` filter.
All settings are contained in an info.xml file.

Primary purpose is to add german audio tracks to english videos.

This version is multi-threaded.

# add_audio_track_st (deprecated)
Older version of add_audio_track_mt, but single threaded and only here for reference.

It is recommended to simply run add_audio_track_mt with `MAX_THREADS = 1` if you want sequential processing of your files.

# rename_video
Renames multiple video files according to a title specified in info.xml.

# Examples
For an example directory structure and info.xml file see the example folder.

# Additional Applications
The following applications are necessary for these scripts to function correctly and need to be placed inside the root directory:
  * [FFMPEG](https://ffmpeg.org/)
  * [MKVPropEdit](https://mkvtoolnix.download/index.html)

# IDE
This project was created using PyCharm 2020.3.5 (Community Edition) with Python 3.7.
