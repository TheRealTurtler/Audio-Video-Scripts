import os
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime

# =========================== Settings ==================================================

# Empty list selects all seasons (specify as string)
seasons = []
# Empty list selects all episodes (specify as string)
episodes = []

# Input path containing different season folders and info.xml
inputPath = ""
# Output path
outputPath = ""

# Select title language (DE or EN)
titleLanguage = "DE"

# Application paths
ffmpeg = "../ffmpeg.exe"
mkvpropedit = "../mkvpropedit.exe"
avidemux = "E:/Program Files/Avidemux 2.7 VC++ 64bits/Avidemux.exe"
avidemuxSettings = "settings/avidemux_settings.py"

# Log file location
logFile = "logs/log_" + os.path.splitext(os.path.basename(__file__))[0] + datetime.today().now().strftime("%Y%m%d_%H%M%S") + ".txt"


# =========================== Functions =================================================

def logWrite(logStr):
	print(logStr)
	with open(logFile, 'a') as fileHandle:
		fileHandle.write(logStr + '\n')


def errorCritical(errorStr):
	logWrite("Error: " + errorStr)
	print()
	exit()


# =========================== Start of Script ===========================================

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

# Loop over all seasons in XML file
for season in root_node.findall("Season"):
	# Check if only specific seasons should be processed
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

	# Loop over all episodes within one season
	for episode in season.find("Episodes").findall("Episode"):
		# Check if only specific episodes should be processed
		if episodes:
			skip = True
			# Check if episode was specified to be processed
			for episodeNumber in episodes:
				if episodeNumber in episode.find("PrefixEpisode").text:
					skip = False

		if skip:
			continue

		# Get episode properties
		episodeFileVideo = episode.find("FileNameVideo").text
		episodeFileAudio = episode.find("FileNameAudio").text
		episodeTitleDE = episode.find("TitleDE").text
		episodeTitleEN = episode.find("TitleEN").text
		outputFilePrefixEpisode = episode.find("PrefixEpisode").text
		episodeAudioOffset = episode.find("AudioOffset").text

		# Check if output folder exists and create it if it doesn't
		if not os.path.isdir(outputPath + seasonPath):
			os.makedirs(outputPath + seasonPath)

		# Check if audio file exists
		filePath = inputPath + audioPath + seasonPath + episodeFileAudio
		convertedAudioFilePath = inputPath + audioPath + seasonPath + "temp.aac"
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
		with open(avidemuxSettings, 'r') as file:
			data = file.readlines()

			for idx, line in enumerate(data):
				if "adm.audioAddExternal" in line:
					data[idx] = "adm.audioAddExternal(\"" + convertedAudioFilePath + "\")\n"
				if "adm.audioSetShift(0" in line:
					data[idx] = "adm.audioSetShift(0, 1, " + episodeAudioOffset + ")\n"

		# Write settings file
		with open(avidemuxSettings, 'w') as file:
			for line in data:
				file.write(line)

		# Check if video file exists
		filePath = inputPath + videoPath + seasonPath + episodeFileVideo
		episodeFullTitle = outputFilePrefixShow \
						   + outputFilePrefixSeason \
						   + outputFilePrefixEpisode \
						   + episodeTitleDE if titleLanguage == "DE" else episodeTitleEN
		convertedVideoFilePath = outputPath + seasonPath + episodeFullTitle + ".mkv"
		if os.path.exists(filePath):
			# Add audio track to video
			logWrite("Adding audio track to video file " + '"' + filePath + '"' + "...")
			subprocess.run([
				avidemux,
				"--load",
				filePath,
				"--run",
				avidemuxSettings,
				"--save",
				convertedVideoFilePath,
				"--quit"
			])

			# Delete extracted audio
			os.remove(convertedAudioFilePath)
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
				'title="' + episodeFullTitle + '"',
				"--add-track-statistics-tags"
			])
