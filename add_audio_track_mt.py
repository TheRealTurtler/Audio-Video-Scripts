import os
import subprocess
import xml.etree.ElementTree as ET
from multiprocessing.pool import ThreadPool
import threading
from datetime import datetime
from tqdm import tqdm
import re


# =========================== Settings ==================================================

# Empty list selects all seasons (specify as string)
seasons = ["01"]
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
loudnessTarget = -23.0		# EBU recommendation
loudnessTruePeak = -1.0		# EBU limit
loudnessRange = 18.0		# https://www.audiokinetic.com/library/edge/?source=Help&id=more_on_loudness_range_lra

# Enable logging to file
enableLogFile = False

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

# RegEx strings
REGEX_AVG_FPS = r"avg_frame_rate=(\d+)/(\d+)"
REGEX_AUDIO_CODEC = r"codec_name=(.*)"
REGEX_MEDIA_STREAM = r"Stream #(\d+):(\d+):\s*Video:"
REGEX_TOTAL_FRAMES = r"NUMBER_OF_FRAMES\s*:\s*(\d+)"
REGEX_CURRENT_FRAME = r"frame\s*=\s*(\d+)"
REGEX_NORMALIZATION = r"Stream\s*(\d+)/(\d+):\s*(\d+)%"
REGEX_NORMALIZATION_SECOND = r"Second Pass\s*:\s*(\d+)%"
REGEX_MKVPROPEDIT = r"Progress:\s*(\d+)%"

# Log file location
logFile = "logs/log_" \
		  + os.path.splitext(os.path.basename(__file__))[0] \
		  + datetime.today().now().strftime("%Y%m%d_%H%M%S") \
		  + ".txt"

# Progress amount on the progress bar
progressAudioEncode = 100
progressMKVProperties = 10


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
	if enableLogFile:
		with threadLock:
			# print(logStr)
			with open(logFile, 'a') as fileHandle:
				fileHandle.write(logStr + '\n')


def errorCritical(errorStr):
	logWrite("Error: " + errorStr)
	print()
	print("Error: " + errorStr)
	exit()


def processEpisode(ep):
	global threadProgress

	# File paths
	audioFilePath = inputPath + audioPath + ep.seasonPath + ep.fileAudio
	videoFilePath = inputPath + videoPath + ep.seasonPath + ep.fileVideo
	episodeFullTitle = outputFilePrefixShow \
					   + ep.filePrefix \
					   + ep.titleDE if titleLanguage == "DE" else ep.titleEN
	convertedVideoFilePath = outputPath + seasonPath + episodeFullTitle + ".mkv"
	tempFilePath = outputPath + ep.seasonPath + "temp_" + episodeFullTitle + ".mkv"

	audioSpeed = 1.0
	audioCodec = "aac"
	amountAudioStreamsVideoFile = 0
	amountAudioStreamsAudioFile = 0

	# Check if video and audio files exist
	if os.path.exists(videoFilePath):
		if os.path.exists(audioFilePath):
			logWrite("Checking framerate of \"" + videoFilePath + "\"...")

			# Get metadata of video file
			probeOut = subprocess.check_output([
				ffprobe,
				"-v",										# Less output
				"quiet",
				"-print_format",							# Set print format to only return values, not keys
				"default=noprint_wrappers=0:nokey=0",
				"-show_streams",							# Output all entries
				videoFilePath
			]).decode("utf-8")								# Decode bytes into text

			probeOut = probeOut.split("\r\n")

			# Count audio streams in file
			amountAudioStreamsVideoFile = probeOut.count("codec_type=audio")

			# Check video fps and calculate audio speed for additional audio track
			indexStart = probeOut.index("codec_type=video")
			indexEnd = probeOut.index("[/STREAM]", indexStart)
			regex = re.compile(REGEX_AVG_FPS)

			for idx in range(indexStart, indexEnd):
				regexMatch = regex.match(probeOut[idx])
				if regexMatch:
					audioSpeed = (int(regexMatch.group(1)) / int(regexMatch.group(2))) / audioFps
					break

			logWrite("Checking audio codec of \"" + audioFilePath + "\"...")

			# Get metadata of audio file
			probeOut = subprocess.check_output([
				ffprobe,
				"-v",  										# Less output
				"quiet",
				"-print_format", 							# Set print format to only return values, not keys
				"default=noprint_wrappers=0:nokey=0",
				"-show_streams",							# Output all entries
				audioFilePath
			]).decode("utf-8")  # Decode bytes into text

			probeOut = probeOut.split("\r\n")

			# Count audio streams in file
			amountAudioStreamsAudioFile = probeOut.count("codec_type=audio")

			# Get audio codec
			regex = re.compile(REGEX_AUDIO_CODEC)

			for element in probeOut:
				regexMatch = regex.match(element)
				if regexMatch:
					audioCodec = regexMatch.group(1)
					break

			logWrite(
				"Adding audio track \""
				+ ep.seasonPath
				+ ep.fileAudio
				+ "\" to video file \""
				+ ep.seasonPath
				+ ep.fileVideo +
				"\"..."
			)

			# Add thread progress to dictionary
			threadProgress[threading.get_ident()] = tqdm(
				total = (amountAudioStreamsVideoFile * (2 if enableNormalization else 0)
						 + amountAudioStreamsAudioFile * (3 if enableNormalization else 1))
						* progressAudioEncode + progressMKVProperties,
				desc = "Processing \"" + ep.seasonPath + ep.fileVideo + "\"",
				leave = False
			)

			# Add additional audio track with offset and speed adjustment
			process = subprocess.Popen([
				ffmpeg,
				"-hide_banner",			# Hide start info
				#"-loglevel",			# Less output
				#"error",
				"-y",					# Override files
				"-i",					# Input video
				videoFilePath,
				"-ss",					# Skip to .. in next input file
				ep.audioStart,
				#"-itsoffset",			# Apply offset to next input file
				#ep.audioOffset,
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
				"-filter_complex",
				"[1:a]adelay=delays=" + ep.audioOffset + ":all=1,atempo=" + str(audioSpeed) + "[out]",
				#"-filter:a:1",			# Adjust speed of audio stream 1 (additional audio)
				#"atempo=" + str(audioSpeed),
				"-map",  # Use everything from first input file
				"0",
				"-map",  # Use only audio from second input file
				#"1:a",
				"[out]",
				"-metadata:s:a:0",		# Set audio stream language
				"language=eng",
				"-metadata:s:a:1",		# Set audio stream language
				"language=deu",
				"-metadata:s:s:0",		# Set subtitle stream language
				"language=eng",
				tempFilePath if enableNormalization else convertedVideoFilePath			# Output video
			],
				stdout = subprocess.PIPE,
				stderr = subprocess.STDOUT,
				universal_newlines = True,
				encoding = "utf-8"
			)

			captureTotalFrames = False
			totalFrames = 0
			percentCounter = 0
			maxPercent = amountAudioStreamsAudioFile * progressAudioEncode
			regexPatternMediaStream = re.compile(REGEX_MEDIA_STREAM)
			regexPatternTotalFrames = re.compile(REGEX_TOTAL_FRAMES)
			regexPatternCurrentFrame = re.compile(REGEX_CURRENT_FRAME)

			# Decode output from ffmpeg
			for line in process.stdout:
				# Check for video stream
				regexMatch = regexPatternMediaStream.match(line.strip())
				if regexMatch:
					if regexMatch.group(1) == "0" and regexMatch.group(2) == "0":
						captureTotalFrames = True

				# Get total frames of video stream
				if captureTotalFrames:
					regexMatch = regexPatternTotalFrames.match(line.strip())
					if regexMatch:
						totalFrames = int(regexMatch.group(1))
						captureTotalFrames = False

				# Get last processed frame
				regexMatch = regexPatternCurrentFrame.match(line.strip())
				if regexMatch:
					progress = int(((int(regexMatch.group(1)) * maxPercent) / totalFrames) * (progressAudioEncode / 100))
					threadProgress[threading.get_ident()].update(progress - percentCounter)
					percentCounter = progress

			# Wait for process to finish
			process.wait()

			# Add any missing percent value to progress bar
			threadProgress[threading.get_ident()].update(maxPercent - percentCounter)
			threadProgress[threading.get_ident()].refresh()

		else:
			errorCritical('"' + audioFilePath + "\" does not exist!")
	else:
		errorCritical('"' + videoFilePath + "\" does not exist!")

	if enableNormalization:
		# Check if temporary output file exists
		if os.path.exists(tempFilePath):
			logWrite("Normalizing loudness of file \"" + tempFilePath + "\"...")

			# Normalize loudness
			process = subprocess.Popen([
				ffmpegNormalize,
				"-q",						# Quiet
				"-pr",						# Show progress bar
				"-f",						# Overwrite files
				"-t",						# Loudness target
				str(loudnessTarget),
				"-lrt",						# Loudness range
				str(loudnessRange),
				"-tp",						# Loudness true peak
				str(loudnessTruePeak),
				tempFilePath,				# Input file
				"-c:a",						# Re-encode audio with aac
				audioCodec,
				"-o",						# Output file
				convertedVideoFilePath
			],
				stdout = subprocess.PIPE,
				stderr = subprocess.STDOUT,
				universal_newlines = True,
				encoding = "utf-8"
			)

			percentCounter = 0
			maxPercent = (amountAudioStreamsVideoFile + amountAudioStreamsAudioFile) * progressAudioEncode * 2
			maxPercentFirstPass = (amountAudioStreamsVideoFile + amountAudioStreamsAudioFile) * progressAudioEncode
			regexPatternNormalization = re.compile(REGEX_NORMALIZATION)
			regexPatternNormalizationSecond = re.compile(REGEX_NORMALIZATION_SECOND)

			# Decode output from ffmpeg
			for line in process.stdout:
				# Get percentage of first pass
				regexMatch = regexPatternNormalization.match(line.strip())
				if regexMatch:
					progress = int(int(regexMatch.group(3)) * (progressAudioEncode / 100) \
							   + progressAudioEncode * (int(regexMatch.group(1)) - 1))
					threadProgress[threading.get_ident()].update(progress - percentCounter)
					percentCounter = progress
				else:
					# Get percentage of second pass
					regexMatch = regexPatternNormalizationSecond.match(line.strip())
					if regexMatch:
						break

			# Add any missing percent value to progress bar
			threadProgress[threading.get_ident()].update(maxPercentFirstPass - percentCounter)
			threadProgress[threading.get_ident()].refresh()
			percentCounter = maxPercentFirstPass

			# Decode output from ffmpeg
			for line in process.stdout:
				# Get percentage of second pass
				regexMatch = regexPatternNormalizationSecond.match(line.strip())
				if regexMatch:
					progress = int((int(regexMatch.group(1)) * (progressAudioEncode / 100)) \
							   * (amountAudioStreamsAudioFile + amountAudioStreamsAudioFile) \
							   + maxPercentFirstPass)
					threadProgress[threading.get_ident()].update(progress - percentCounter)
					percentCounter = progress

			# Wait for process to finish
			process.wait()

			# Add any missing percent value to progress bar
			threadProgress[threading.get_ident()].update(maxPercent - percentCounter)
			threadProgress[threading.get_ident()].refresh()

			# Delete temporary output file
			os.remove(tempFilePath)
		else:
			errorCritical('"' + videoFilePath + "\" does not exist!")

	# Check if output file exists
	if os.path.exists(convertedVideoFilePath):
		# Set title in video file properties
		process = subprocess.Popen([
			mkvpropedit,
			convertedVideoFilePath,
			"-e",
			"info",
			"-s",
			"title=" + episodeFullTitle,
			"--add-track-statistics-tags"
		],
			stdout = subprocess.PIPE,
			stderr = subprocess.STDOUT,
			universal_newlines = True,
			encoding = "utf-8"
		)

		percentCounter = 0
		regexPatternMKVPropEdit = re.compile(REGEX_MKVPROPEDIT)

		# Decode output from mkvpropedit
		for line in process.stdout:
			# Get percentage
			regexMatch = regexPatternMKVPropEdit.match(line.strip())
			if regexMatch:
				progress = int(int(regexMatch.group(1)) * (progressMKVProperties / 100))
				threadProgress[threading.get_ident()].update(progress - percentCounter)
				percentCounter = progress

		# Wait for process to finish
		process.wait()

		# Add any missing percent value to progress bar
		threadProgress[threading.get_ident()].update(progressMKVProperties - percentCounter)
		threadProgress[threading.get_ident()].refresh()

	# Remove thread progress from dictionary since thread is finished now
	threadProgress[threading.get_ident()].close()
	del threadProgress[threading.get_ident()]


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

# Dictionary containing thread identifier as key and thread progress as value
threadProgress = {}

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
jobs = []

while episodeSettings:
	es = episodeSettings.pop()
	jobs.append(pool.apply_async(processEpisode, (es,)))

pool.close()

result_list_progressBar = []
for job in tqdm(jobs, desc = "Processing Episodes"):
	result_list_progressBar.append(job.get())

pool.join()
