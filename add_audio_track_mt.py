import os
import subprocess
import xml.etree.ElementTree as ET
from multiprocessing.pool import ThreadPool
import threading
from datetime import datetime

# =========================== Settings ==================================================

# Empty list selects all seasons (specify as string)
seasons = ["01", "02"]
# Empty list selects all episodes (specify as string)
episodes = ["01"]

# Input path containing different season folders and info.xml
inputPath = "E:/Filme/JDownloader/Stargate Atlantis/"
# Output path
outputPath = "E:/Plex/Serien [DE-EN]/Stargate Atlantis (2004)/"

# Select title language (DE or EN)
titleLanguage = "DE"

# Normalize audio
enableNormalization = True

# Maximum number of simultaneous threads
MAX_THREADS = 6

# Additional audio track 'FPS'
# (fps of source video where the audio track is from)
# (25 for PAL)
audioFps = 25

# Application paths
ffmpeg = "ffmpeg.exe"
ffprobe = "ffprobe.exe"
ffmpegNormalize = "ffmpeg-normalize"		# Needs to be installed with pip3 install ffmpeg-normalize
mkvpropedit = "mkvpropedit.exe"

# Log file location
logFile = "logs/log_" \
		  + os.path.splitext(os.path.basename(__file__))[0] \
		  + datetime.today().now().strftime("%Y%m%d_%H%M%S") \
		  + ".txt"


# =========================== Functions =================================================

class SettingsEpisode:
	def __init__(
			self,
			_seasonPath,
			_fileVideo,
			_fileAudio,
			_titleDE,
			_titleEN,
			_filePrefix,
			_audioStart,
			_audioOffset
	):
		self.seasonPath  = _seasonPath
		self.fileVideo   = _fileVideo
		self.fileAudio   = _fileAudio
		self.titleDE     = _titleDE
		self.titleEN     = _titleEN
		self.filePrefix  = _filePrefix
		self.audioStart  = _audioStart
		self.audioOffset = _audioOffset


def logWrite(logStr):
	with threadLock:
		print(logStr)
		with open(logFile, 'a') as fileHandle:
			fileHandle.write(logStr + '\n')


def errorCritical(errorStr):
	logWrite("Error: " + errorStr)
	exit()


def processEpisode(ep):
	audioFilePath = inputPath + audioPath + ep.seasonPath + ep.fileAudio
	videoFilePath = inputPath + videoPath + ep.seasonPath + ep.fileVideo
	episodeFullTitle = outputFilePrefixShow \
					   + ep.filePrefix \
					   + ep.titleDE if titleLanguage == "DE" else ep.titleEN
	convertedVideoFilePath = outputPath + seasonPath + episodeFullTitle + ".mkv"
	tempFilePath = outputPath + ep.seasonPath + "temp_" + episodeFullTitle + ".mkv"
	audioSpeed = 1.0
	audioCodec = "aac"

	# Check if video and audio files exist
	if os.path.exists(videoFilePath):
		if os.path.exists(audioFilePath):
			logWrite("Checking framerate of \"" + videoFilePath + "\"...")

			probeOut = subprocess.check_output([
				ffprobe,
				"-v",										# Less output
				"quiet",
				"-print_format",							# Set print format to only return values, not keys
				"default=noprint_wrappers=1:nokey=1",
				"-show_entries",							# Filter specific entries
				"stream=avg_frame_rate",
				videoFilePath
			]).decode("utf-8")								# Decode bytes into text

			probeOut = probeOut.split("\r\n")

			if len(probeOut) > 0:
				probeOut = probeOut[0].split("/")
			else:
				errorCritical("Failed to get framerate from \"" + videoFilePath + "\"!")

			if len(probeOut) > 1:
				# Calculate factor by which the additional audio track needs to be slowed down
				audioSpeed = (int(probeOut[0]) / int(probeOut[1])) / audioFps
			else:
				errorCritical("Failed to get framerate from \"" + videoFilePath + "\"!")

			logWrite("Checking audio codec of \"" + audioFilePath + "\"...")

			probeOut = subprocess.check_output([
				ffprobe,
				"-v",  										# Less output
				"quiet",
				"-print_format", 							# Set print format to only return values, not keys
				"default=noprint_wrappers=1:nokey=1",
				"-show_entries",							# Filter specific entries
				"stream=codec_name",
				audioFilePath
			]).decode("utf-8")  # Decode bytes into text

			probeOut = probeOut.split("\r\n")

			if len(probeOut) > 0:
				audioCodec = probeOut[0]
			else:
				errorCritical("Failed to get audio codec from \"" + audioFilePath + "\"!")

			logWrite(
				"Adding audio track \""
				+ ep.seasonPath
				+ ep.fileAudio
				+ "\" to video file \""
				+ ep.seasonPath
				+ ep.fileVideo +
				"\"..."
			)

			# Add additional audio track with offset and speed adjustment
			subprocess.run([
				ffmpeg,
				"-hide_banner",			# Hide start info
				"-loglevel",			# Less output
				"error",
				"-y",					# Override files
				"-i",					# Input video
				videoFilePath,
				"-ss",					# Skip to .. in next input file
				ep.audioStart,
				"-itsoffset",			# Apply offset to next input file
				ep.audioOffset,
				"-i",					# Input audio
				audioFilePath,
				"-c:v",					# Copy video stream
				"copy",
				"-c:a:0",				# Copy original audio stream
				"copy",
				"-c:a:1",				# Re-encode additional audio stream with aac
				audioCodec,
				"-c:s",					# Copy subtitles
				"copy",
				"-map",					# Use everything from first input file
				"0",
				"-map",					# Use only audio from second input file
				"1:a",
				"-filter:a:1",			# Adjust speed of audio stream 1 (additional audio)
				"atempo=" + str(audioSpeed),
				"-metadata:s:a:0",		# Set audio stream language
				"language=eng",
				"-metadata:s:a:1",		# Set audio stream language
				"language=de",
				"-metadata:s:s:0",		# Set subtitle stream language
				"language=eng",
				tempFilePath if enableNormalization else convertedVideoFilePath			# Output video
			])
		else:
			errorCritical('"' + audioFilePath + "\" does not exist!")
	else:
		errorCritical('"' + videoFilePath + "\" does not exist!")

	if enableNormalization:
		# Check if temporary output file exists
		if os.path.exists(tempFilePath):
			logWrite("Normalizing loudness of file \"" + tempFilePath + "\"...")

			# Normalize loudness
			subprocess.run([
				ffmpegNormalize,
				"-q",						# Quiet
				#"-pr",						# Show progress bar
				"-f",						# Overwrite files
				tempFilePath,				# Input file
				"-c:a",						# Re-encode audio with aac
				audioCodec,
				"-o",						# Output file
				convertedVideoFilePath
			])

			# Delete temporary output file
			os.remove(tempFilePath)
		else:
			errorCritical('"' + videoFilePath + "\" does not exist!")

	# Check if output file exists
	if os.path.exists(convertedVideoFilePath):
		# Set title in video file properties
		subprocess.run([
			mkvpropedit,
			convertedVideoFilePath,
			"-e",
			"info",
			"-s",
			"title=" + episodeFullTitle,
			"--add-track-statistics-tags"
		])


# =========================== Start of Script ===========================================

# Create thread lock
threadLock = threading.Lock()

# Clear log file
open(logFile, 'w').close()

# Write name of script to log file
logWrite("This is " + os.path.basename(__file__))

# Get root element of XML file
root_node = ET.parse(inputPath + "info.xml").getroot()

# Get video and audio file paths from XML
videoPath = root_node.find("FilePathVideo").text
audioPath = root_node.find("FilePathAudio").text

# Get show prefix for output file name from XML
outputFilePrefixShow = root_node.find("PrefixShow").text

# List containing settings for each episode in this season
episodeSettings = []

# Loop over all seasons in XML file
for season in root_node.findall("Season"):
	# Check if only specific seasons should be processed
	skip = False
	if seasons:
		skip = True
		# Check if season was specified to be processed
		for seasonNumber in seasons:
			if seasonNumber in season.find("PrefixSeason").text:
				skip = False

	if skip:
		continue

	# Get path for season
	seasonPath = season.find("FilePathSeason").text

	# Check if output folder exists and create it if it doesn't
	if not os.path.isdir(outputPath + seasonPath):
		os.makedirs(outputPath + seasonPath)

	# Loop over all episodes within one season
	for episode in season.find("Episodes").findall("Episode"):
		# Check if only specific episodes should be processed
		skip = False
		if episodes:
			skip = True
			# Check if episode was specified to be processed
			for episodeNumber in episodes:
				if episodeNumber in episode.find("PrefixEpisode").text:
					skip = False

		if skip:
			continue

		episodeSettings.append(SettingsEpisode(
			seasonPath,
			episode.find("FileNameVideo").text,
			episode.find("FileNameAudio").text,
			episode.find("TitleDE").text,
			episode.find("TitleEN").text,
			season.find("PrefixSeason").text + episode.find("PrefixEpisode").text,
			season.find("AudioStart").text,
			episode.find("AudioOffset").text
		))

pool = ThreadPool(MAX_THREADS)
results = []

while episodeSettings:
	es = episodeSettings.pop()
	results.append(pool.apply_async(processEpisode, (es,)))

pool.close()
pool.join()
