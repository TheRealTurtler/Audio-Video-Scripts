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
seasons = ["01"]
# Empty list selects all episodes (specify as string)
episodes = ["03"]

# Input path containing different season folders and info.xml
inputPath = "E:/Filme/JDownloader/Stargate Atlantis/"
# Output path
#outputPath = "E:/Plex/Serien [DE-EN]/Stargate Atlantis (2004)/"
outputPath = "E:/Filme/JDownloader/Audio-Video-Scripts/Test/"

# Select title language (DE or EN)
titleLanguage = "DE"

# Normalize audio
enableNormalization = False
loudnessTarget = -23.0		# EBU recommendation: (-23.0)
loudnessTruePeak = -1.0		# EBU limit (-1.0)
loudnessRange = 18.0		# https://www.audiokinetic.com/library/edge/?source=Help&id=more_on_loudness_range_lra (18.0)

# Set file metadata using MKVPropedit
# TODO: remove mkvpropedit
enableMKVPropedit = False

# Enable logging to file
enableLogFile = False
enableUniqueLogFile = False

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
REGEX_MEDIA_STREAM = r"Stream #(\d+):(\d+):\s*Video:"
REGEX_TOTAL_FRAMES = r"NUMBER_OF_FRAMES\s*:\s*(\d+)"
REGEX_CURRENT_FRAME = r"frame\s*=\s*(\d+)"
REGEX_LOUDNORM = r"\[Parsed_loudnorm_(\d+)"

REGEX_NORMALIZATION = r"Stream\s*(\d+)/(\d+):\s*(\d+)%"
REGEX_NORMALIZATION_SECOND = r"Second Pass\s*:\s*(\d+)%"

REGEX_MKVPROPEDIT = r"Progress:\s*(\d+)%"

# Log file location
logFile = "logs/log_" + os.path.splitext(os.path.basename(__file__))[0] + ".txt"
if enableUniqueLogFile:
	logFile = "logs/log_" \
			  + os.path.splitext(os.path.basename(__file__))[0] \
			  + datetime.today().now().strftime("%Y%m%d_%H%M%S") \
			  + ".txt"

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
	aac_lc = "aac_low"
	aac_he = "aac_he"
	aac_he_v2 = "aac_he_v2"
	aac_ld = "aac_ld"
	aac_eld = "aac_eld"


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
	audioCodecs = []
	audioCodecProfiles = []
	audioBitRates = []
	audioSampleRates = []
	amountAudioStreams = [0, 0]

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
			threadProgress[threading.get_ident()] = tqdm(
				total = (amountAudioStreams[0] * (2 if enableNormalization else 0)
						 + amountAudioStreams[1] * (3 if enableNormalization else 1))
						* progressAudioEncode + progressMKVProperties,
				desc = "Processing \"" + ep.seasonPath + ep.fileVideo + "\"",
				leave = False
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

					# TODO: progress bar (extra function?)
					regexPattern = re.compile(REGEX_LOUDNORM)

					jsonStrings = []
					i = -1
					processFinished = False

					# Decode output of ffmpeg
					for line in process.stdout:
						print(line.strip())
						regexMatch = regexPattern.match(line.strip())
						if regexMatch:
							i += 1
							jsonStrings.append("")
							processFinished = True
						elif processFinished:
							jsonStrings[i] += line

					# Wait for process to finish
					process.wait()

					# Decode json output
					processOutJson = []
					for jsonString in jsonStrings:
						processOutJson.append(json.loads(jsonString))

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

			command.extend([
				"-map",						# Map subtitles from first input file to output
				"0:s",
				"-map_metadata:g",			# Map global metadata to output
				"0:g",
				# "-max_interleave_delta",	# Needed for use with subtitles, otherwise audio has buffering issues
				# "0"						# TODO: check if this is still needed
			])

			# Mark all original audio streams as english
			for idxStream in range(amountAudioStreams[0]):
				command.append("-metadata:s:a:" + str(idxStream))
				command.append("language=eng")

			# Mark all additional audio streams as german
			for idxStream in range(amountAudioStreams[1]):
				command.append("-metadata:s:a:" + str(idxStream + amountAudioStreams[0]))
				command.append("language=deu")

			command.extend([
				"-metadata:s:s:0",		# Set subtitle stream language
				"language=eng",
				"-metadata",			# Set title
				"title=" + episodeFullTitle,
				tempFilePath if enableNormalization else convertedVideoFilePath		# Output video
			])

			process = subprocess.Popen(
				command,
				stdout = subprocess.PIPE,
				stderr = subprocess.STDOUT,
				universal_newlines = True,
				encoding = "utf-8"
			)

			# TODO: progress bar (extra function?)
			regexPattern = re.compile(REGEX_LOUDNORM)

			jsonStrings = []
			i = -1
			processFinished = False

			# Decode output of ffmpeg
			for line in process.stdout:
				print(line.strip())
				if enableNormalization:
					regexMatch = regexPattern.match(line.strip())
					if regexMatch:
						i += 1
						jsonStrings.append("")
						processFinished = True
					elif processFinished:
						jsonStrings[i] += line

			process.wait()

			if enableNormalization:
				processOutJson = []
				for jsonString in jsonStrings:
					processOutJson.append(json.loads(jsonString))

				# for idxStream, outJson in enumerate(processOutJson):
				# 	if outJson["normalization_type"] != "linear":
				# 		if idxStream < amountAudioStreams[0]:
				# 			errorCritical(
				# 				"Unable to normalize audio stream "
				# 				+ str(idxStream)
				# 				+ " in file \"" + videoFilePath + "\"!"
				# 			)
				# 		else:
				# 			errorCritical(
				# 				"Unable to normalize audio stream "
				# 				+ str(idxStream - amountAudioStreams[0])
				# 				+ " in file \""
				# 				+ audioFilePath + "\"!"
				# 			)

			# TODO: Check if normalization was successful (all audio streams were normalized linearly, not dynamically)
			# TODO: Parse output
			# TODO: Progress bar

			raise Exception("DEBUG")

			# command = [
			# 	ffmpeg,
			# 	"-hide_banner",			# Hide start info
			# 	# "-loglevel",			# Less output
			# 	# "error",
			# 	"-y",  					# Override files
			# 	"-i",  					# Input video
			# 	videoFilePath,
			# 	"-ss",  				# Skip specified time in next input file
			# 	ep.audioStart,
			# 	"-i",  					# Input audio
			# 	audioFilePath,
			# 	"-filter_complex",  	# Adjust speed and delay of additional audio track
			# 	"[1:a]adelay=delays=" + ep.audioOffset + ":all=true,atempo=" + str(audioSpeed) + "[out]",
			# 	"-c:v",  				# Copy video stream
			# 	"copy"
			# ]

			# # Copy all original audio streams
			# for i in range(amountAudioStreams[0]):
			# 	command.append("-c:a:" + str(i))
			# 	command.append("copy")
			#
			# # Re-encode all additional audio streams
			# for i in range(amountAudioStreams[1]):
			# 	command.append("-c:a:" + str(i + amountAudioStreams[0]))
			# 	command.append(str(audioCodecs[amountAudioStreams[0] + i]))
			# 	command.append("-b:a:" + str(i + amountAudioStreams[0]))
			# 	command.append(str(audioBitRates[amountAudioStreams[0] + i]))

			# command.extend([
			# 	"-c:s",  				# Copy subtitles
			# 	"copy",
			# 	"-map",  				# Use everything from first input file
			# 	"0",
			# 	"-map",  				# Use filtered audio
			# 	"[out]",
			# 	"-max_interleave_delta",  # Needed for use with subtitles, otherwise audio has buffering issues
			# 	"0"
			# ])
			#
			# # Mark all original audio streams as english
			# for i in range(amountAudioStreams[0]):
			# 	command.append("-metadata:s:a:" + str(i))
			# 	command.append("language=eng")
			#
			# # Mark all additional audio streams as german
			# for i in range(amountAudioStreams[1]):
			# 	command.append("-metadata:s:a:" + str(i + amountAudioStreams[0]))
			# 	command.append("language=deu")
			#
			# command.extend([
			# 	"-metadata:s:s:0",  	# Set subtitle stream language
			# 	"language=eng",
			# 	"-metadata",  			# Set title
			# 	"title=" + episodeFullTitle,
			# 	tempFilePath if enableNormalization else convertedVideoFilePath  # Output video
			# ])

			# Add additional audio track with offset and speed adjustment
			process = subprocess.Popen(
				command,
				stdout = subprocess.PIPE,
				stderr = subprocess.STDOUT,
				universal_newlines = True,
				encoding = "utf-8"
			)

			captureTotalFrames = False
			totalFrames = 0
			percentCounter = 0
			maxPercent = amountAudioStreams[1] * progressAudioEncode
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
				"-ar",						# Sample rate for output file
				str(normalizedAudioSampleRate),
				tempFilePath,				# Input file
				"-c:a",						# Re-encode audio with aac
				#audioCodec,
				"aac"
				"-o",						# Output file
				convertedVideoFilePath
			],
				stdout = subprocess.PIPE,
				stderr = subprocess.STDOUT,
				universal_newlines = True,
				encoding = "utf-8"
			)

			percentCounter = 0
			maxPercent = (amountAudioStreams[0] + amountAudioStreams[1]) * progressAudioEncode * 2
			maxPercentFirstPass = (amountAudioStreams[0] + amountAudioStreams[1]) * progressAudioEncode
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
							   * (amountAudioStreams[1] + amountAudioStreams[1]) \
							   + maxPercentFirstPass)
					threadProgress[threading.get_ident()].update(progress - percentCounter)
					percentCounter = progress

			# Wait for process to finish
			process.wait()

			# Check exit code
			if process.returncode:
				errorCritical(
					"Failed to normalize loudness of file \""
					+ tempFilePath
					+ "\"! Exiting..."
				)

			# Add any missing percent value to progress bar
			threadProgress[threading.get_ident()].update(maxPercent - percentCounter)
			threadProgress[threading.get_ident()].refresh()

			# Delete temporary output file
			os.remove(tempFilePath)
		else:
			errorCritical('"' + videoFilePath + "\" does not exist!")

	if enableMKVPropedit:
		# Check if output file exists
		if os.path.exists(convertedVideoFilePath):
			logWrite("Updating metadata of file \"" + convertedVideoFilePath + "\"...")

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
if enableUniqueLogFile:
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
