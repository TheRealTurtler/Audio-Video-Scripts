import os
import subprocess
import xml.etree.ElementTree as ET
from multiprocessing.pool import ThreadPool
import threading

# Settings
seasons = ["1"]			# Empty list selects all seasons (specify as string)
episodes = ["04"]			# Empty list selects all episodes (specify as string)

MAX_THREADS = 10

titleLanguage = "DE"  # DE or EN

inputPath = "Stargate Universe/"
outputPath = "E:/Filme/Stargate Universe/"

ffmpeg = "ffmpeg.exe"
mkvpropedit = "mkvpropedit.exe"
avidemux = "E:/Program Files/Avidemux 2.7 VC++ 64bits/Avidemux.exe"
avidemuxSettings = "avidemux_settings.py"
logFile = "log.txt"

threadLock = threading.Lock()


class SettingsEpisode:
	def __init__(
			self,
			fileVideo,
			fileAudio,
			titleDE,
			titleEN,
			filePrefix,
			audioOffset
	):
		self.fileVideo = fileVideo
		self.fileAudio = fileAudio
		self.titleDE = titleDE
		self.titleEN = titleEN
		self.filePrefix = filePrefix
		self.audioOffset = audioOffset


def logWrite(logStr):
	with threadLock:
		print(logStr)
		with open(logFile, 'a') as fileHandle:
			fileHandle.write(logStr + '\n')


def errorCritical(errorStr):
	logWrite("Error: " + errorStr)
	exit()


def processEpisode(ep):
	# Check if audio file exists
	filePath = inputPath + audioPath + seasonPath + ep.fileAudio
	convertedAudioFilePath = inputPath + audioPath + seasonPath + os.path.splitext(ep.fileAudio)[0] + ".aac"
	if os.path.exists(filePath):
		# Extract .aac audio file from .m4a container
		logWrite("Extracting audio from " + '"' + filePath + '"' + "...")
		subprocess.run([
			ffmpeg,
			"-hide_banner",
			"-loglevel",
			"error",
			"-y",
			"-ss",
			audioStart,
			"-i",
			filePath,
			"-acodec",
			"copy",
			convertedAudioFilePath
		])
	else:
		errorCritical('"' + filePath + '"' + " does not exist!")

	# Read settings file
	with threadLock:
		with open(avidemuxSettings, 'r') as file:
			data = file.readlines()

			for idx, line in enumerate(data):
				if "adm.audioAddExternal" in line:
					data[idx] = "adm.audioAddExternal(\"" + convertedAudioFilePath + "\")\n"
				if "adm.audioSetShift(0" in line:
					data[idx] = "adm.audioSetShift(0, 1, " + ep.audioOffset + ")\n"

	modifiedAvidemuxSettings = os.path.splitext(avidemuxSettings)[0] + " - " + os.path.splitext(ep.fileVideo)[0] + ".py"

	# Write settings file
	with open(modifiedAvidemuxSettings, 'w') as file:
		for line in data:
			file.write(line)

	# Check if video file exists
	filePath = inputPath + videoPath + seasonPath + ep.fileVideo
	episodeFullTitle = outputFilePrefixShow \
					   + outputFilePrefixSeason \
					   + ep.filePrefix \
					   + ep.titleDE if titleLanguage == "DE" else ep.titleEN
	convertedVideoFilePath = outputPath + seasonPath + episodeFullTitle + ".mkv"
	if os.path.exists(filePath):
		# Add audio track to video
		logWrite("Adding audio track to video file " + '"' + filePath + '"' + "...")
		subprocess.run([
			avidemux,
			"--load",
			filePath,
			"--run",
			modifiedAvidemuxSettings,
			"--save",
			convertedVideoFilePath,
			"--quit"
		])

		# Delete extracted audio
		os.remove(convertedAudioFilePath)

		# Delete modified avidemux settings file
		os.remove(modifiedAvidemuxSettings)
	else:
		errorCritical('"' + filePath + '"' + " does not exist!")

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


# Clear log file
open(logFile, 'w').close()

# Get root element of XML file
root_node = ET.parse(inputPath + "info.xml").getroot()

# Get video and audio file paths from XML
videoPath = root_node.find("FilePathVideo").text
audioPath = root_node.find("FilePathAudio").text

# Get show prefix for output file name from XML
outputFilePrefixShow = root_node.find("PrefixShow").text

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

	# Get season prefix for output file name
	outputFilePrefixSeason = season.find("PrefixSeason").text

	# Get start time for audio
	audioStart = season.find("AudioStart").text

	# List containing settings for each episode in this season
	episodeSettings = []

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
			episode.find("FileNameVideo").text,
			episode.find("FileNameAudio").text,
			episode.find("TitleDE").text,
			episode.find("TitleEN").text,
			episode.find("PrefixEpisode").text,
			episode.find("AudioOffset").text
		))

	pool = ThreadPool(MAX_THREADS)
	results = []

	while episodeSettings:
		es = episodeSettings.pop()
		results.append(pool.apply_async(processEpisode, (es,)))

	pool.close()
	pool.join()
