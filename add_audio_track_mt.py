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
inputPath = r''
# Output path
outputPath = r'script_output\The Super Mario Bros Movie (2023)'

inputPath += "\\"
outputPath += "\\"

# Select title language (DE or EN)
titleLanguage = "DE"

# Normalize audio
enableNormalization = False
loudnessTarget = -23.0		# EBU recommendation: (-23.0)
loudnessTruePeak = -1.0		# EBU limit (-1.0)
loudnessRange = 18.0		# https://www.audiokinetic.com/library/edge/?source=Help&id=more_on_loudness_range_lra (18.0)

# Format of file name
fileNameFormat = "{TITLE} [{RESOLUTION} {VIDEO_CODEC} {HDR} en-{EN_AUDIO_CODEC}-{EN_AUDIO_CHANNELS} de-{DE_AUDIO_CODEC}-{DE_AUDIO_CHANNELS}].mkv"

# Enable logging to file
enableLogFile = True
enableFfmpegLogFile = True
enableUniqueLogFile = False

# Maximum number of simultaneous threads
MAX_THREADS = 1

# Additional audio track 'FPS'
# (fps of source video where the audio track is from)
# (25 for PAL. 24000/1001 for NTSC, 0 if audio file fps = video file fps)
audioFps = 0

# Application paths
ffmpeg = "ffmpeg.exe"
ffprobe = "ffprobe.exe"
mkvpropedit = "mkvpropedit.exe"

# RegEx strings
REGEX_MEDIA_STREAM		= r"Stream #(\d+):(\d+).*:\s*([a-zA-z]*)\s*:"
REGEX_TOTAL_FRAMES		= r"NUMBER_OF_FRAMES\s*:\s*(\d+)"
REGEX_TOTAL_DURATION	= r"\s*DURATION\s*:\s*(\d+):(\d+):(\d+.\d+)"
REGEX_CURRENT_FRAME		= r"frame\s*=\s*(\d+)"
REGEX_CURRENT_TIME		= r"time=(\d+):(\d+):(\d+).(\d+)"
REGEX_LOUDNORM			= r"\[Parsed_loudnorm_(\d+)"
REGEX_MKVPROPEDIT		= r"Progress:\s*(\d+)%"
REGEX_FFMPEG_FILTER		= r"\[[0-9]*:a:[0-9]\](.*)\[out[0-9]*\]"

# Log file location
logFile = "logs/log_"
logFileFfmpeg = logFile + "ffmpeg_"
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

audioEncoderAAC = "libfdk_aac"
audioEncoderAC3 = "ac3"
audioEncoderOPUS = "libopus"

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
		self.seasonPath			= _seasonPath
		self.fileVideo			= _fileVideo
		self.fileAudio			= _fileAudio
		self.titleDE			= _titleDE
		self.titleEN			= _titleEN
		self.filePrefix			= _filePrefix
		self.audioStart			= _audioStart
		self.audioOffset		= _audioOffset


class InfoVideo:
	def __init__(self):
		self.width				= None
		self.height				= None
		self.codec				= None
		self.profile			= None
		self.color_space		= None
		self.color_transfer		= None
		self.color_primaries	= None
		self.duration			= None
		self.framerate			= None


class InfoAudio:
	def __init__(self):
		self.codec				= None
		self.profile			= None
		self.bitrate			= None
		self.samplerate			= None
		self.language 			= None
		self.channels			= None
		self.channel_layout		= None


class InfoSubtitle:
	def __init__(self):
		self.language	= None


# TODO: use logging module
def logWrite(logStr, logFile = logFile):
	if enableLogFile:
		with threadLock:
			# print(logStr)
			try:
				with open(logFile, 'a', encoding = "utf-8") as fileHandle:
					fileHandle.write(logStr + '\n')
			except Exception as e:
				print("Error writing log file: " + logFile + "! Exception: ", e)


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


def getAudioEncoder(codec):
	if codec == "aac":
		return audioEncoderAAC
	elif codec == "ac3":
		return audioEncoderAC3
	elif codec == "opus":
		return audioEncoderOPUS
	else:
		errorCritical("Unknown audio codec: " + codec)


def getAudioEncoderProfile(codec, profile):
	if codec == "aac":
		if profile == "LC":
			return AudioCodecProfiles.aac_lc
		elif profile == "HE-AAC":
			return AudioCodecProfiles.aac_he
		else:
			errorCritical("Unknown audio profile: " + profile)
	else:
		return None


def secondsToTimeString(seconds):
	hours = int(seconds // 3600)
	minutes = int((seconds % 3600) // 60)
	seconds -= hours * 3600 + minutes * 60

	return f"{hours:02}:{minutes:02}:{seconds:06.3f}"


def timeStringToSeconds(timeStr):
	isNegative = timeStr.startswith("-")
	timeStr.removeprefix("-")

	timeList = timeStr.split(":")
	seconds = int(timeList[0]) * 3600 + int(timeList[1]) * 60 + float(timeList[2])

	if isNegative:
		seconds *= -1

	return seconds


def listSearch(elementList, value):
	for element in elementList:
		if value in element:
			return element

	return ""


def get_resolution(widht, height):
	if height <= 240:
		return "240p"
	elif height <= 360:
		return "360p"
	elif height <= 480:
		return "480p"
	elif height <= 720:
		return "720p"
	elif height <= 1080:
		return "1080p"
	elif height <= 1440:	# 2K
		return "1440p"
	elif height <= 2160:	# 4K
		return "2160p"
	elif height <= 2880:	# 5K
		return "2880p"
	elif height <= 3384:	# 6K
		return "3384p"
	elif height <= 4320:	# 8K
		return "4320p"


def get_hdr(color_space, color_transfer, color_promaries):
	if color_space == "bt2020nc" and color_transfer == "smpte2084" and color_promaries == "bt2020":
		return "HDR"
	else:
		return "SDR"


def get_audio_channels(channels, layout):
	if channels == 6 and "5.1" in layout:
		return "5.1"
	elif channels == 2:
		return "2"
	else:
		errorCritical("Unknown channel layout! Channels: " + channels + " Layout: " + layout)


def get_audio_codec(codec, profile):
	if codec == "aac":
		if "HE" in profile:
			return "AAC-HE"
		else:
			return "AAC-LC"
	else:
		return codec.upper()


def decodeFfmpegOutput(process, progressBar, maxProgress):
	captureTotalFrames = False
	jsonStart = False
	totalFrames = 0
	totalDurationS = 0
	percentCounter = 0
	regexPatternMediaStream		= re.compile(REGEX_MEDIA_STREAM)
	regexPatternTotalFrames		= re.compile(REGEX_TOTAL_FRAMES)
	regexPatternTotalDuration	= re.compile(REGEX_TOTAL_DURATION, re.IGNORECASE)
	regexPatternCurrentFrame	= re.compile(REGEX_CURRENT_FRAME)
	regexPatternCurrentTime		= re.compile(REGEX_CURRENT_TIME)

	# Normalization output
	regexPatternLoudNorm = re.compile(REGEX_LOUDNORM)
	jsonStrings = []

	# Log file buffer (avoid constant opening and closing of file)
	logFileBuffer = ""

	# Decode output from ffmpeg
	for line in process.stdout:
		# Stop decoding if process finished
		if process.poll() is not None:
			break

		# Ignore empty lines
		if line.strip() == "":
			continue

		# Print output to file
		if enableFfmpegLogFile:
			logFileBuffer += line.strip() + "\n"
			if len(logFileBuffer) > 1024:
				logWrite(logFileBuffer[:-1], logFileFfmpeg + "_" + str(threading.get_ident()) + logFileExtension)
				logFileBuffer = ""

		# Update progress bar
		regexMatchFrame = regexPatternCurrentFrame.match(line.strip())
		regexMatchTime = regexPatternCurrentTime.search(line.strip())
		if regexMatchFrame and totalFrames > 0:
			progress = int(((int(regexMatchFrame.group(1)) * maxProgress) / totalFrames) * (progressAudioEncode / 100))
			progressBar.update(progress - percentCounter)
			percentCounter = progress
			continue
		elif regexMatchTime and totalDurationS > 0:
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
			if regexMatch.group(3).lower() == "video":
				captureTotalFrames = True
			else:
				captureTotalFrames = False
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
				if "}" in line:
					jsonStart = False
				continue

	# Flush remaining buffer to log file
	if enableFfmpegLogFile:
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
	# TODO: Unique log files per episode, not per thread
	# if not enableUniqueLogFile:
	# 	open(logFileFfmpeg + "_" + str(threading.get_ident()) + logFileExtension, 'w').close()

	# File paths
	audioFilePath = inputPath + audioPath + ep.seasonPath + ep.fileAudio
	videoFilePath = inputPath + videoPath + ep.seasonPath + ep.fileVideo
	episodeFullTitle = outputFilePrefixShow \
					   + ep.filePrefix \
					   + ep.titleDE if titleLanguage == "DE" else ep.titleEN
	convertedVideoFilePath = outputPath + ep.seasonPath

	infoVideo = InfoVideo()
	infoAudio = []
	infoSubtitle = []

	audioSpeed = 1.0
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
					infoVideo.framerate = int(avgFps[0]) / int(avgFps[1])

					if audioFps > 0:
						audioSpeed = infoVideo.framerate / audioFps

					# Get video duration
					if "tags" in stream and "DURATION" in stream["tags"] and timeStringToSeconds(stream["tags"]["DURATION"]) > 0:
						infoVideo.duration = timeStringToSeconds(stream["tags"]["DURATION"])
					elif "tags" in stream and "DURATION-eng" in stream["tags"] and timeStringToSeconds(stream["tags"]["DURATION-eng"]) > 0:
						infoVideo.duration = timeStringToSeconds(stream["tags"]["DURATION-eng"])
					else:
						errorCritical("Could not get duration of video stream " + stream["index"] + " in file \"" + videoFilePath + "\"")

					infoVideo.width = stream["width"]
					infoVideo.height = stream["height"]
					infoVideo.codec = stream["codec_name"]
					infoVideo.profile = stream["profile"]
					infoVideo.color_space = stream["color_space"]
					infoVideo.color_transfer = stream["color_transfer"]
					infoVideo.color_primaries = stream["color_primaries"]


				# Get audio stream info
				elif stream["codec_type"] == "audio":
					amountAudioStreams[0] += 1
					infoStream = InfoAudio()

					# Get samplerate
					if "sample_rate" in stream and int(stream["sample_rate"]) > 0:
						infoStream.samplerate =int(stream["sample_rate"])
					else:
						errorCritical("Could not get samplerate of audio stream " + stream["index"] + " in file \"" + videoFilePath + "\"")

					# Get bitrate
					if "bit_rate" in stream and int(stream["bit_rate"]) > 0:
						infoStream.bitrate = int(stream["bit_rate"])
					elif "tags" in stream and "BPS" in stream["tags"] and int(stream["tags"]["BPS"]) > 0:
						infoStream.bitrate = int(stream["tags"]["BPS"])
					elif "tags" in stream and "BPS-eng" in stream["tags"] and int(stream["tags"]["BPS-eng"]) > 0:
						infoStream.bitrate = int(stream["tags"]["BPS-eng"])
					else:
						errorCritical("Could not get bitrate of audio stream " + stream["index"] + " in file \"" + videoFilePath + "\"")

					# Get audio codec and profile
					if "codec_name" in stream:
						infoStream.codec = stream["codec_name"]

					if "profile" in stream:
						infoStream.profile = stream["profile"]

					# Get audio language
					if "tags" in stream and "language" in stream["tags"]:
						infoStream.language = stream["tags"]["language"]

					# Get audio channels
					if "channels" in stream:
						infoStream.channels = stream["channels"]

					if "channel_layout" in stream:
						infoStream.channel_layout = stream["channel_layout"]

					infoAudio.append(infoStream)

				# Get subtitle stream info
				elif stream["codec_type"] == "subtitle":
					amountSubtitleStreams[0] += 1

					infoStream = InfoSubtitle()

					# Get subtitle language
					if "tags" in stream and "language" in stream["tags"]:
						infoStream.language = stream["tags"]["language"]

					infoSubtitle.append(infoStream)

			logWrite("Using audio speed " + str(audioSpeed) + " for \"" + audioFilePath + "\"")
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
					infoStream = InfoAudio()

					# Get samplerate
					if "sample_rate" in stream and int(stream["sample_rate"]) > 0:
						infoStream.samplerate = int(stream["sample_rate"])
					else:
						errorCritical("Could not get samplerate of audio stream " + stream[
							"index"] + " in file \"" + videoFilePath + "\"")

					# Get bitrate
					if "bit_rate" in stream and int(stream["bit_rate"]) > 0:
						infoStream.bitrate = int(stream["bit_rate"])
					elif "tags" in stream and "BPS" in stream["tags"] and int(stream["tags"]["BPS"]) > 0:
						infoStream.bitrate = int(stream["tags"]["BPS"])
					else:
						errorCritical("Could not get bitrate of audio stream " + stream[
							"index"] + " in file \"" + videoFilePath + "\"")

					# Get audio codec and profile
					if "codec_name" in stream:
						infoStream.codec = stream["codec_name"]

					if "profile" in stream:
						infoStream.profile = stream["profile"]

					# Get audio language
					if "tags" in stream and "language" in stream["tags"]:
						infoStream.language = stream["tags"]["language"]

					# Get audio channels
					if "channels" in stream:
						infoStream.channels = stream["channels"]

					if "channel_layout" in stream:
						infoStream.channel_layout = stream["channel_layout"]

					infoAudio.append(infoStream)

				# Get subtitle stream info
				elif stream["codec_type"] == "subtitle":
					amountSubtitleStreams[1] += 1

					infoStream = InfoSubtitle()

					# Get subtitle language
					if "tags" in stream and "language" in stream["tags"]:
						infoStream.language = stream["tags"]["language"]

					infoSubtitle.append(infoStream)

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

				commandStr = ""

				for elem in command:
					commandStr += elem
					commandStr += ' '

				logWrite("Executing command: " + commandStr)

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

				# Check exit code
				if process.returncode:
					errorCritical(
						"Failed to get audio normalization values for \""
						+ ep.seasonPath
						+ ep.fileVideo
						+ "\"!"
					)

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
				audioFilePath
			])

			# Filter all audio streams of the two input files
			# File 1: Video + Original Audio
			# File 2: Audio to be added
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
						filterStr += ":out_sample_rate="	+ str(infoAudio[idxStreamOut].samplerate)
						if audioResampler == "soxr":
							filterStr += ":precision="		+ str(audioResamplerPrecision)
						filterStr += ","
					if idxFile == 1:
						if audioSpeed != 1:
							filterStr += "atempo="			+ str(audioSpeed)
							filterStr += ","
						if timeStringToSeconds(ep.audioOffset) > 0:
							filterStr += "adelay=delays="	+ str(int(timeStringToSeconds(ep.audioOffset) * 1000))
							filterStr += ":all=true"
					if filterStr[-1] == ",":
						filterStr = filterStr[:-1]
					filterStr += "[out"						+ str(idxStreamOut)
					filterStr += "];"

			# Remove last ';'
			filterStr = filterStr[:-1]

			# Add filter to command
			regexPatternFilter = re.compile(REGEX_FFMPEG_FILTER)
			regexMatchFilter = regexPatternFilter.match(filterStr)

			if regexMatchFilter and regexMatchFilter.group(1) != "":
				command.extend([
					"-filter_complex",  # Apply complex filter
					filterStr
				])

			# Set audio codec, profile and bitrate
			for idxFile in range(2):
				for idxStream in range(amountAudioStreams[idxFile]):
					idxStreamOut = idxFile * amountAudioStreams[0] + idxStream
					command.append("-c:a:" + str(idxStreamOut))

					encoder = None
					profile = None
					bitrate = None

					if idxFile == 0 and not enableNormalization:
						encoder = "copy"
					else:
						encoder = getAudioEncoder(infoAudio[idxStreamOut].codec)
						profile = getAudioEncoderProfile(infoAudio[idxStreamOut].codec, infoAudio[idxStreamOut].profile)
						bitrate = getNearestValidBitrate(infoAudio[idxStreamOut].bitrate)

					command.append(encoder)

					if profile is not None:
						command.append("-profile:a:" + str(idxStreamOut))
						command.append(profile)

					if bitrate is not None:
						command.append("-b:a:" + str(idxStreamOut))
						command.append(str(bitrate))

			command.extend([
				"-c:v",					# Copy video
				"copy",
				"-c:s",					# Copy subtitles
				"copy",
				"-map",					# Map video from first input file to output
				"0:v"
			])

			# Map all filtered audio and corresponding metadata to output
			for idxFile in range(2):
				for idxStream in range(amountAudioStreams[idxFile]):
					idxStreamOut = idxFile * amountAudioStreams[0] + idxStream
					if (idxFile == 0 and not enableNormalization) or regexMatchFilter.group(1) == "":
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
					idxStreamOut = idxFile * amountAudioStreams[0] + idxStream
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

			# Assume the first audio stream is english if not specified
			if amountAudioStreams[0] > 0:
				lang = infoAudio[0].language
				if lang is None or lang == "" or lang == "und":
					infoAudio[0].language = "eng"

			# Assume the second audio stream is german if not specified
			if amountAudioStreams[1] > 0:
				lang = infoAudio[amountAudioStreams[0]].language
				if lang is None or lang == "" or lang == "und":
					infoAudio[amountAudioStreams[0]].language = "deu"

			# Set audio languages
			for idxStream in range(amountAudioStreams[0]):
				lang = infoAudio[idxStream].language
				if lang is not None and lang != "":
					command.append("-metadata:s:a:" + str(idxStream))
					command.append("language=" + lang)

			for idxStream in range(amountAudioStreams[1]):
				lang = infoAudio[idxStream + amountAudioStreams[0]].language
				if lang is not None and lang != "":
					command.append("-metadata:s:a:" + str(idxStream + amountAudioStreams[0]))
					command.append("language=" + lang)

			# Mark all original subtitle streams as english
			# for idxStream in range(amountSubtitleStreams[0]):
			# 	command.append("-metadata:s:s:" + str(idxStream))
			# 	command.append("language=eng")

			# Mark all additional subtitle streams as german
			# for idxStream in range(amountSubtitleStreams[1]):
			# 	command.append("-metadata:s:s:" + str(idxStream + amountSubtitleStreams[0]))
			# 	command.append("language=deu")

			fileName = fileNameFormat
			fileName = fileName.replace("{TITLE}",				episodeFullTitle)
			fileName = fileName.replace("{RESOLUTION}",			get_resolution(infoVideo.width, infoVideo.height))
			fileName = fileName.replace("{VIDEO_CODEC}",			str(infoVideo.codec).upper())
			fileName = fileName.replace("{HDR}",					get_hdr(infoVideo.color_space, infoVideo.color_transfer, infoVideo.color_primaries))
			fileName = fileName.replace("{EN_AUDIO_CODEC}",		get_audio_codec(infoAudio[0].codec, infoAudio[0].profile))
			fileName = fileName.replace("{EN_AUDIO_CHANNELS}",	get_audio_channels(infoAudio[0].channels, infoAudio[0].channel_layout))
			fileName = fileName.replace("{DE_AUDIO_CODEC}", 		get_audio_codec(infoAudio[amountAudioStreams[0]].codec, infoAudio[amountAudioStreams[0]].profile))
			fileName = fileName.replace("{DE_AUDIO_CHANNELS}",	get_audio_channels(infoAudio[amountAudioStreams[0]].channels, infoAudio[amountAudioStreams[0]].channel_layout))

			convertedVideoFilePath += fileName

			command.extend([
				"-metadata",					# Set title
				"title=" + episodeFullTitle,
				"-t",							# Duration of video to correctly truncate audio
				secondsToTimeString(infoVideo.duration),
				convertedVideoFilePath			# Output video
			])

			commandStr = ""

			for elem in command:
				commandStr += elem
				commandStr += ' '

			logWrite("Executing command: " + commandStr)

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
					+ "\"!"
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
	else:
		errorCritical("Output file \"" + convertedVideoFilePath + "\" does not exist!")

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
outputFilePrefixShow = ""

if root_node.find("PrefixShow") is not None:
	outputFilePrefixShow = root_node.find("PrefixShow").text

if outputFilePrefixShow is None:
	outputFilePrefixShow = ""

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
			prefix = ""

			if season.find("PrefixSeason") is not None:
				prefix = season.find("PrefixSeason").text

			if prefix is None:
				prefix = ""

			if seasonNumber in prefix:
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
				prefix = ""

				if episode.find("PrefixEpisode"):
					prefix = episode.find("PrefixEpisode").text

				if episodeNumber in prefix:
					skip = False

		if skip:
			continue

		audioStart = timeStringToSeconds(season.find("AudioStart").text)
		audioDelay = timeStringToSeconds(episode.find("AudioOffset").text)
		videoFile = ""
		audioFile = ""

		if episode.find("FileNameVideo"):
			videoFile = episode.find("FileNameVideo").text
		else:
			dirList = os.listdir(inputPath + videoPath + seasonPath)
			videoFile = listSearch(dirList, episode.find("FileNameVideoContains").text)

		if episode.find("FileNameAudio"):
			audioFile = episode.find("FileNameAudio").text
		else:
			dirList = os.listdir(inputPath + audioPath + seasonPath)
			audioFile = listSearch(dirList, episode.find("FileNameAudioContains").text)

		if audioDelay < 0:
			audioStart += abs(audioDelay)
			audioDelay = 0

		prefixSeason = ""

		if season.find("PrefixSeason") is not None:
			prefixSeason = season.find("PrefixSeason").text

		if prefixSeason is None:
			prefixSeason = ""

		prefixEpisode = ""

		if episode.find("PrefixEpisode") is not None:
			prefixEpisode = episode.find("PrefixEpisode").text

		if prefixEpisode is None:
			prefixEpisode = ""

		episodeSettings.append(SettingsEpisode(
			seasonPath,
			videoFile,
			audioFile,
			episode.find("TitleDE").text,
			episode.find("TitleEN").text,
			prefixSeason + prefixEpisode,
			secondsToTimeString(audioStart),
			secondsToTimeString(audioDelay)
		))

progressBarTotal = tqdm(desc = "Processing Episodes", total = len(episodeSettings))
updateProgressBarTotal = lambda a : progressBarTotal.update(1)

pool = None
jobs = None

if MAX_THREADS > 1:
	pool = ThreadPool(MAX_THREADS)
	jobs = []

while episodeSettings:
	es = episodeSettings.pop(0)

	if pool is not None:
		jobs.append(pool.apply_async(processEpisode, args = (es,), callback = updateProgressBarTotal))
	else:
		processEpisode(es)

if pool is not None:
	pool.close()
	pool.join()

logWrite("Finished")
