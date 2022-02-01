# Audio-Video-Scripts
Collection of various scripts to edit audio and/or video files.

# add_audio_track_mt
Adds an audio track to a video file. All settings are contained in a info.xml file.
Primary purpose is to add german audio tracks to english videos.
This version is multi-threaded.

# add_audio_track_st
Same as add_audio_track_st, but single threaded.

# rename_video
Renames multiple video files according to a title specified in info.xml.

# Examples
For a example directory structure and info.xml file see the example folder.

# Additional Applications
The following applications are necessary for these scripts to function correctly and need to be placed inside the root directory:
  * [FFMPEG](https://ffmpeg.org/)
  * [FFMPEG-Normalize](https://github.com/slhck/ffmpeg-normalize)
  * [MKVPropEdit](https://mkvtoolnix.download/index.html)
