import os
import subprocess
import xml.etree.ElementTree as ET
from multiprocessing.pool import ThreadPool
import threading
from datetime import datetime
from tqdm import tqdm
import re
import json


# =========================== Settings ==================================================


# Empty list selects all seasons (specify as string)
seasons = []
# Empty list selects all episodes (specify as string)
episodes = []

# Input path containing different season folders and info.xml
inputPath = "E:/Filme/JDownloader/Stargate Atlantis/"
# Output path
outputPath = "E:/Plex/Serien [DE-EN]/Stargate Atlantis (2004)/"

# Select title language (DE or EN)
titleLanguage = "DE"

# Normalize audio
enableNormalization = True
loudnessTarget = -23.0		# EBU recommendation: (-23.0)
loudnessTruePeak = -1.0		# EBU limit (-1.0)
loudnessRange = 18.0		# https://www.audiokinetic.com/library/edge/?source=Help&id=more_on_loudness_range_lra (18.0)

# Enable logging to file
enableLogFile = True
enableUniqueLogFile = False

# Maximum number of simultaneous threads
MAX_THREADS = 4

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
REGEX_MEDIA_STREAM		= r"Stream #(\d+):(\d+):\s*Video:"
REGEX_TOTAL_FRAMES		= r"NUMBER_OF_FRAMES\s*:\s*(\d+)"
REGEX_TOTAL_DURATION	= r"DURATION\s*:\s*(\d+):(\d+):(\d+.\d+)"
REGEX_CURRENT_FRAME		= r"frame\s*=\s*(\d+)"
REGEX_CURRENT_TIME		= r"time=(\d+):(\d+):(\d+).(\d+)"
REGEX_LOUDNORM			= r"\[Parsed_loudnorm_(\d+)"
REGEX_MKVPROPEDIT = r"Progress:\s*(\d+)%"

# Log file location
logFile = "logs/log_"
logFileFfmpeg = "logs/log_"
logFileSuffix = os.path.splitext(os.path.basename(__file__))[0]
logFileUniqueSuffix = datetime.today().now().strftime("%Y%m%d_%H%M%S")
logFileExtension = ".txt"

logFile += logFileSuffix
logFileFfmpeg += logFileSuffix
if enableUniqueLogFile:
	logFile += logFileUniqueSuffix
	logFileFfmpeg += logFileUniqueSuffix
logFile += logFileExtension

# Progress amount on the progress bar
progressAudioEncode = 100
progressMKVProperties = 10

audioCodecAAC = "libfdk_aac"

# Audio resampler (swr or soxr)
audioResampler = "soxr"
audioResamplerPrecision = 28		# Only used with soxr HQ = 20, vHQ = 28

validBitrates = [x * 32000 for x in range(1, 11)]


# =========================== Functions =================================================


class AudioCodecProfiles:
	aac_lc		= "aac_low"
	aac_he		= "aac_he"
	aac_he_v2	= "aac_he_v2"
	aac_ld		= "aac_ld"
	aac_eld		= "aac_eld"


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


def logWrite(logStr, logFile = logFile):
	if enableLogFile:
		with threadLock:
			# print(logStr)
			with open(logFile, 'a') as fileHandle:
				fileHandle.write(logStr + '\n')


def errorCritical(errorStr):
	logWrite("Error: " + errorStr)
	raise Exception(errorStr)


def getNearestValidBitrate(bitrate):
	validBitrate = 32000
	for br in validBitrates:
		if bitrate - br >= -32000 // 2:
			validBitrate = br
		else:
			break

	return validBitrate


def getAudioCodecProfile(codecProfile):
	if codecProfile == "LC":
		return AudioCodecProfiles.aac_lc
	elif codecProfile == "HE-AAC":
		return AudioCodecProfiles.aac_he
	else:
		errorCritical("Unknown audio codec profile: " + codecProfile)


def decodeFfmpegOutput(process, progressBar, maxProgress):
	captureTotalFrames = False
	jsonStart = False
	totalFrames = 0
	totalDurationS = 0
	percentCounter = 0
	regexPatternMediaStream		= re.compile(REGEX_MEDIA_STREAM)
	regexPatternTotalFrames		= re.compile(REGEX_TOTAL_FRAMES)
	regexPatternTotalDuration	= re.compile(REGEX_TOTAL_DURATION)
	regexPatternCurrentFrame	= re.compile(REGEX_CURRENT_FRAME)
	regexPatternCurrentTime		= re.compile(REGEX_CURRENT_TIME)

	# Normalization output
	regexPatternLoudNorm = re.compile(REGEX_LOUDNORM)
	jsonStrings = []

	# Log file buffer (avoid constant opening and closing of file)
	logFileBuffer = ""

	# Decode output from ffmpeg
	for line in process.stdout:
		# Ignore empty lines
		if line.strip() == "":
			continue
		# Print output to file
		if enableLogFile:
			logFileBuffer += line.strip() + "\n"
			if len(logFileBuffer) > 1024:
				logWrite(logFileBuffer[:-1], logFileFfmpeg + "_" + str(threading.get_ident()) + logFileExtension)
				logFileBuffer = ""
		# Update progress bar
		regexMatchFrame = regexPatternCurrentFrame.match(line.strip())
		regexMatchTime = regexPatternCurrentTime.search(line.strip())
		if regexMatchFrame:
			progress = int(((int(regexMatchFrame.group(1)) * maxProgress) / totalFrames) * (progressAudioEncode / 100))
			progressBar.update(progress - percentCounter)
			percentCounter = progress
			continue
		elif regexMatchTime:
			timeS  = int(regexMatchTime.group(1)) * 3600		# Hours
			timeS += int(regexMatchTime.group(2)) * 60			# Minutes
			timeS += float(regexMatchTime.group(3))				# Seconds
			progress = int(((timeS * maxProgress) / totalDurationS) * (progressAudioEncode / 100))
			progressBar.update(progress - percentCounter)
			percentCounter = progress
			continue

		# Check for video stream
		regexMatch = regexPatternMediaStream.match(line.strip())
		if regexMatch:
			if regexMatch.group(1) == "0" and regexMatch.group(2) == "0":
				captureTotalFrames = True
				continue

		# Get total frames of video stream
		if captureTotalFrames:
			regexMatch = regexPatternTotalFrames.match(line.strip())
			if regexMatch:
				totalFrames = int(regexMatch.group(1))
				captureTotalFrames = False
				continue

		# Get maximum total duration
		regexMatch = regexPatternTotalDuration.match(line.strip())
		if regexMatch:
			durationS  = int(regexMatch.group(1)) * 3600		# Hours
			durationS += int(regexMatch.group(2)) * 60			# Minutes
			durationS += float(regexMatch.group(3))				# Seconds
			if durationS > totalDurationS:
				totalDurationS = durationS
			continue

		# Get normalization output
		if enableNormalization:
			regexMatch = regexPatternLoudNorm.match(line.strip())
			if regexMatch:
				jsonStrings.append("")
				jsonStart = True
				continue
			elif jsonStart:
				jsonStrings[-1] += line
				continue

	# Flush remaining buffer to log file
	if enableLogFile:
		if len(logFileBuffer) > 0:
			logWrite(logFileBuffer[:-1], logFileFfmpeg + "_" + str(threading.get_ident()) + logFileExtension)
			logFileBuffer = ""

	# Add any missing percent value to progress bar
	progressBar.update(maxProgress - percentCounter)
	progressBar.refresh()

	# Return json output
	return [json.loads(s) for s in jsonStrings]


def processEpisode(ep):
	global threadProgress

	# Clear ffmpeg log file
	if not enableUniqueLogFile:
		open(logFileFfmpeg + "_" + str(threading.get_ident()) + logFileExtension, 'w').close()

	# File paths
	audioFilePath = inputPath + audioPath + ep.seasonPath + ep.fileAudio
	videoFilePath = inputPath + videoPath + ep.seasonPath + ep.fileVideo
	episodeFullTitle = outputFilePrefixShow \
					   + ep.filePrefix \
					   + ep.titleDE if titleLanguage == "DE" else ep.titleEN
	convertedVideoFilePath = outputPath + seasonPath + episodeFullTitle + ".mkv"

	audioSpeed = 1.0
	audioCodecs = []
	audioCodecProfiles = []
	audioBitRates = []
	audioSampleRates = []
	amountAudioStreams = [0, 0]
	amountSubtitleStreams = [0, 0]

	# Check if video and audio files exist
	if os.path.exists(videoFilePath):
		if os.path.exists(audioFilePath):
			logWrite("Checking framerate of \"" + videoFilePath + "\"...")

			# Get metadata of video file
			processOutJson = json.loads(subprocess.check_output([
				ffprobe,
				"-v",										# Less output
				"quiet",
				"-print_format",							# Set print format to json
				"json",
				"-show_streams",							# Output all entries
				videoFilePath
			]).decode("utf-8"))								# Decode bytes into text

			for stream in processOutJson["streams"]:
				# Check video fps and calculate audio speed for additional audio track
				if stream["codec_type"] == "video":
					avgFps = stream["avg_frame_rate"].split("/")
					audioSpeed = (int(avgFps[0]) / int(avgFps[1])) / audioFps
				# Get audio stream info
				elif stream["codec_type"] == "audio":
					amountAudioStreams[0] += 1

					# Get samplerate
					if "sample_rate" in stream and int(stream["sample_rate"]) > 0:
						audioSampleRates.append(int(stream["sample_rate"]))
					else:
						errorCritical("Could not get samplerate of audio stream " + stream["index"] + " in file \"" + videoFilePath + "\"")

					# Get bitrate
					if "bit_rate" in stream and int(stream["bit_rate"]) > 0:
						audioBitRates.append(getNearestValidBitrate(int(stream["bit_rate"])))
					elif "tags" in stream and "BPS" in stream["tags"] and int(stream["tags"]["BPS"]) > 0:
						audioBitRates.append(getNearestValidBitrate(int(stream["tags"]["BPS"])))
					else:
						errorCritical("Could not get bitrate of audio stream " + stream["index"] + " in file \"" + videoFilePath + "\"")

					# Get audio codec and profile
					if stream["codec_name"] == "aac":
						audioCodecs.append(audioCodecAAC)
						audioCodecProfiles.append(getAudioCodecProfile(stream["profile"]))
					else:
						errorCritical("Detected unknown codec " + stream["codec_name"] + " in file \"" + videoFilePath + "\"")
				# Get subtitle stream info
				elif stream["codec_type"] == "subtitle":
					amountSubtitleStreams[0] += 1

			logWrite("Checking audio codec of \"" + audioFilePath + "\"...")

			# Get metadata of audio file
			processOutJson = json.loads(subprocess.check_output([
				ffprobe,
				"-v",										# Less output
				"quiet",
				"-print_format",							# Set print format to json
				"json",
				"-show_streams",							# Output all entries
				audioFilePath
			]).decode("utf-8"))								# Decode bytes into text

			for stream in processOutJson["streams"]:
				# Get audio stream info
				if stream["codec_type"] == "audio":
					amountAudioStreams[1] += 1

					# Get samplerate
					if "sample_rate" in stream and int(stream["sample_rate"]) > 0:
						audioSampleRates.append(int(stream["sample_rate"]))
					else:
						errorCritical("Could not get samplerate of audio stream " + stream["index"] + " in file \"" + audioFilePath + "\"")

					# Get bitrate
					if "bit_rate" in stream and int(stream["bit_rate"]) > 0:
						audioBitRates.append(getNearestValidBitrate(int(stream["bit_rate"])))
					elif "tags" in stream and "BPS" in stream["tags"] and int(stream["tags"]["BPS"]) > 0:
						audioBitRates.append(getNearestValidBitrate(int(stream["tags"]["BPS"])))
					else:
						errorCritical("Could not get bitrate of audio stream " + stream["index"] + " in file \"" + audioFilePath + "\"")

					# Get codec and profile
					if stream["codec_name"] == "aac":
						audioCodecs.append(audioCodecAAC)
						audioCodecProfiles.append(getAudioCodecProfile(stream["profile"]))
					else:
						errorCritical("Detected unknown codec " + stream["codec_name"] + " in file \"" + audioFilePath + "\"")
				# Get subtitle stream info
				elif stream["codec_type"] == "subtitle":
					amountSubtitleStreams[0] += 1

			logWrite(
				"Adding audio track \""
				+ ep.seasonPath
				+ ep.fileAudio
				+ "\" to video file \""
				+ ep.seasonPath
				+ ep.fileVideo
				+ "\"..."
			)

			# Add thread progress to dictionary
			maxProgress = amountAudioStreams[1] * progressAudioEncode + progressMKVProperties
			if enableNormalization:
				maxProgress = (amountAudioStreams[0] + amountAudioStreams[1]) * 2 * progressAudioEncode + progressMKVProperties
			threadProgress[threading.get_ident()] = tqdm(
				total = maxProgress,
				desc = "Processing \"" + ep.seasonPath + ep.fileVideo + "\"",
				leave = False,
			)

			if enableNormalization:
				command = [
					ffmpeg,
					"-hide_banner",			# Hide start info
				]

				# Set codecs for all audio streams in first input file
				# FDK AAC seams to be bugged as decoder (removes silence and sets timestamps, but fails for the english audio)
				# for idxStream in range(amountAudioStreams[0]):
				# 	command.append("-c:a:" + str(idxStream))
				# 	command.append(audioCodecs[idxStream])

				command.extend([
					"-i",					# Input video
					videoFilePath,
				])

				# Set codecs for all audio streams in second input file
				# FDK AAC seams to be bugged as decoder (removes silence and sets timestamps, but fails for the english audio)
				# for idxStream in range(amountAudioStreams[1]):
				# 	command.append("-c:a:" + str(idxStream))
				# 	command.append(audioCodecs[idxStream + amountAudioStreams[0]])

				command.extend([
					"-ss",					# Skip specified time in next input file
					ep.audioStart,
					"-i",					# Input audio
					audioFilePath,
				])

				if enableNormalization:
					command.append("-filter_complex")
					filterStr = ""

					# Filter all audio streams of the two input files
					for idxFile in range(2):
						for idxStream in range(amountAudioStreams[idxFile]):
							filterStr += "[" + str(idxFile) + ":a:" + str(idxStream) + "]"
							filterStr += "loudnorm="
							filterStr += "I="		+ str(loudnessTarget)
							filterStr += ":LRA="	+ str(loudnessRange)
							filterStr += ":TP="		+ str(loudnessTruePeak)
							filterStr += ":print_format=json;"

					# Remove last ';'
					filterStr = filterStr[:-1]

					# Add filter to command
					command.append(filterStr)

					command.extend([
						# No output codec needed, output is discarded anyway and measured values stay the same
						"-vn",					# Discard video
						"-f",					# Only analyze file, don't create any output
						"null",
						"-"
					])

					# Analyze loudness of audio tracks
					process = subprocess.Popen(
						command,
						stdout = subprocess.PIPE,
						stderr = subprocess.STDOUT,
						universal_newlines = True,
						encoding = "utf-8"
					)

					# Decode ffmpeg output
					processOutJson = decodeFfmpegOutput(
						process,
						threadProgress[threading.get_ident()],
						(amountAudioStreams[0] + amountAudioStreams[1]) * progressAudioEncode
					)

					# Wait for process to finish
					process.wait()

			command = [
				ffmpeg,
				"-hide_banner",			# Hide start info
				"-y"					# Overwrite existing files
			]

			# Set codecs for all audio streams in first input file
			# FDK AAC seams to be bugged as decoder (removes silence and sets timestamps, but fails for the english audio)
			# for idxStream in range(amountAudioStreams[0]):
			# 	command.append("-c:a:" + str(idxStream))
			# 	command.append(audioCodecs[idxStream])

			command.extend([
				"-i",					# Input video
				videoFilePath,
			])

			# Set codecs for all audio streams in second input file
			# FDK AAC seams to be bugged as decoder (removes silence and sets timestamps, but fails for the english audio)
			# for idxStream in range(amountAudioStreams[1]):
			# 	command.append("-c:a:" + str(idxStream))
			# 	command.append(audioCodecs[idxStream + amountAudioStreams[0]])

			command.extend([
				"-ss",					# Skip specified time in next input file
				ep.audioStart,
				"-i",					# Input audio
				audioFilePath,
				"-filter_complex"		# Apply complex filter
			])

			# Filter all audio streams of the two input files
			filterStr = ""
			for idxFile in range(0 if enableNormalization else 1, 2):
				for idxStream in range(amountAudioStreams[idxFile]):
					idxStreamOut = idxFile * amountAudioStreams[0] + idxStream
					filterStr += "[" + str(idxFile) + ":a:" + str(idxStream) + "]"
					if enableNormalization:
						filterStr += "loudnorm="
						filterStr += "I="					+ str(loudnessTarget)
						filterStr += ":LRA="				+ str(loudnessRange)
						filterStr += ":TP="					+ str(loudnessTruePeak)
						filterStr += ":measured_I="			+ processOutJson[idxStreamOut]["input_i"]
						filterStr += ":measured_LRA="		+ processOutJson[idxStreamOut]["input_lra"]
						filterStr += ":measured_TP="		+ processOutJson[idxStreamOut]["input_tp"]
						filterStr += ":measured_thresh="	+ processOutJson[idxStreamOut]["input_thresh"]
						filterStr += ":offset="				+ processOutJson[idxStreamOut]["target_offset"]
						filterStr += ":linear=true"
						filterStr += ":print_format=json"
						filterStr += ",aresample="
						filterStr += "resampler="			+ audioResampler
						filterStr += ":out_sample_rate="	+ str(audioSampleRates[idxStreamOut])
						if audioResampler == "soxr":
							filterStr += ":precision="		+ str(audioResamplerPrecision)
					if idxFile == 1:
						if enableNormalization:
							filterStr += ","
						filterStr += "atempo="				+ str(audioSpeed)
						filterStr += ",adelay=delays="		+ ep.audioOffset
						filterStr += ":all=true"
					filterStr += "[out"						+ str(idxStreamOut)
					filterStr += "];"

			# Remove last ';'
			filterStr = filterStr[:-1]

			# Add filter to command
			command.append(filterStr)

			# Set audio codec, profile and bitrate
			for idxFile in range(2):
				for idxStream in range(amountAudioStreams[idxFile]):
					idxStreamOut = idxStream + idxFile * amountAudioStreams[idxFile]
					command.append("-c:a:" + str(idxStreamOut))
					if idxFile == 0 and not enableNormalization:
						command.append("copy")
					else:
						command.append(audioCodecs[idxStreamOut])
						command.append("-profile:a:" + str(idxStreamOut))
						command.append(audioCodecProfiles[idxStreamOut])
						command.append("-b:a:" + str(idxStreamOut))
						command.append(str(audioBitRates[idxStreamOut]))

			command.extend([
				"-c:v",					# Copy video
				"copy",
				"-c:s",					# Copy subtitles
				"copy",
				"-map",					# Map video from first input file to output
				"0:v",
			])

			# Map all filtered audio and corresponding metadata to output
			for idxFile in range(2):
				for idxStream in range(amountAudioStreams[idxFile]):
					idxStreamOut = idxStream + idxFile * amountAudioStreams[idxFile]
					if idxFile == 0 and not enableNormalization:
						command.append("-map")
						command.append(str(idxFile) + ":a:" + str(idxStream))
					else:
						command.append("-map")
						command.append("[out" + str(idxStreamOut) + "]")
					command.append("-map_metadata:s:a:" + str(idxStreamOut))
					command.append(str(idxFile) + ":s:a:" + str(idxStream))

			# Map all subtitle streams to output
			for idxFile in range(2):
				for idxStream in range(amountSubtitleStreams[idxFile]):
					idxStreamOut = idxStream + idxFile * amountAudioStreams[idxFile]
					command.append("-map")
					command.append(str(idxFile) + ":s:" + str(idxStream))
					command.append("-map_metadata:s:s:" + str(idxStreamOut))
					command.append(str(idxFile) + ":s:s:" + str(idxStream))

			command.extend([
				"-map_metadata:g",			# Map global metadata to output
				"0:g",
				"-max_interleave_delta",	# Needed for use with subtitles, otherwise audio has buffering issues
				"0"
			])

			# Mark all original audio streams as english
			for idxStream in range(amountAudioStreams[0]):
				command.append("-metadata:s:a:" + str(idxStream))
				command.append("language=eng")

			# Mark all additional audio streams as german
			for idxStream in range(amountAudioStreams[1]):
				command.append("-metadata:s:a:" + str(idxStream + amountAudioStreams[0]))
				command.append("language=deu")

			# Mark all original subtitle streams as english
			for idxStream in range(amountSubtitleStreams[0]):
				command.append("-metadata:s:s:" + str(idxStream))
				command.append("language=eng")

			# Mark all additional subtitle streams as german
			for idxStream in range(amountSubtitleStreams[1]):
				command.append("-metadata:s:s:" + str(idxStream + amountSubtitleStreams[0]))
				command.append("language=deu")

			command.extend([
				"-metadata",			# Set title
				"title=" + episodeFullTitle,
				convertedVideoFilePath	# Output video
			])

			# Add additional audio track with offset, speed adjustment and normalize loudness of all audio tracks
			process = subprocess.Popen(
				command,
				stdout = subprocess.PIPE,
				stderr = subprocess.STDOUT,
				universal_newlines = True,
				encoding = "utf-8"
			)

			# Decode ffmpeg output
			processOutJson = decodeFfmpegOutput(
				process,
				threadProgress[threading.get_ident()],
				(amountAudioStreams[0] * int(enableNormalization) + amountAudioStreams[1]) * progressAudioEncode
			)

			# Wait for process to finish
			process.wait()

			# Check exit code
			if process.returncode:
				errorCritical(
					"Failed to add audio track \""
					+ ep.seasonPath
					+ ep.fileAudio
					+ "\" to video file \""
					+ ep.seasonPath
					+ ep.fileVideo
					+ "\"! Exiting..."
				)

			# Check if linear normalization was successful
			if enableNormalization:
				for idxStream, outJson in enumerate(processOutJson):
					if outJson["normalization_type"] != "linear":
						if idxStream < amountAudioStreams[0]:
							logWrite(
								"Warning: "
								+ "Audio stream "
								+ str(idxStream)
								+ " in file \"" + videoFilePath + "\""
								+ " was normalized dynamically."
							)
						else:
							logWrite(
								"Warning: "
								+ "Audio stream "
								+ str(idxStream - amountAudioStreams[0])
								+ " in file \"" + audioFilePath + "\""
								+ " was normalized dynamically."
							)
		else:
			errorCritical('"' + audioFilePath + "\" does not exist!")
	else:
		errorCritical('"' + videoFilePath + "\" does not exist!")

	# Check if output file exists
	if os.path.exists(convertedVideoFilePath):
		logWrite("Updating metadata of file \"" + convertedVideoFilePath + "\"...")

		# Update track statistics
		process = subprocess.Popen([
			mkvpropedit,
			convertedVideoFilePath,
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

		# Check exit code
		if process.returncode:
			errorCritical(
				"Failed to update metadata of file \""
				+ convertedVideoFilePath
				+ "\"! Exiting..."
			)

		# Add any missing percent value to progress bar
		threadProgress[threading.get_ident()].update(progressMKVProperties - percentCounter)
		threadProgress[threading.get_ident()].refresh()

	# Remove thread progress from dictionary since thread is finished now
	threadProgress[threading.get_ident()].close()
	del threadProgress[threading.get_ident()]


# =========================== Start of Script ===========================================

# Clear log file
if not enableUniqueLogFile:
	open(logFile, 'w').close()

# Create thread lock
threadLock = threading.Lock()

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
