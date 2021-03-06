import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime

# =========================== Settings ==================================================

# Empty list selects all seasons (specify as string)
seasons = []
# Empty list selects all episodes (specify as string)
episodes = []

# Input path containing different season folders
inputPath = "H:/The Expanse/Englisch/"
infoPath = "H:/The Expanse/"
outputPath = "H:/The Expanse (2015)/"

# Select title language (DE or EN)
titleLanguage = "DE"

# Maximum number of simultaneous threads
MAX_THREADS = 10

# Application paths
ffmpeg = "ffmpeg.exe"
mkvpropedit = "mkvpropedit.exe"

# Log file location
logFile = "logs/log_" + os.path.splitext(os.path.basename(__file__))[0] + datetime.today().now().strftime("%Y%m%d_%H%M%S") + ".txt"


# =========================== Functions =================================================

class SettingsEpisode:
	def __init__(
			self,
			fileVideo,
			titleDE,
			titleEN,
			filePrefix,
	):
		self.fileVideo = fileVideo
		self.titleDE = titleDE
		self.titleEN = titleEN
		self.filePrefix = filePrefix


def logWrite(logStr):
	print(logStr)
	with open(logFile, 'a') as fileHandle:
		fileHandle.write(logStr + '\n')


def errorCritical(errorStr):
	logWrite("Error: " + errorStr)
	exit()


def listSearch(elementList, value):
	for element in elementList:
		if value in element:
			return element

	return ''


def processEpisode(_prefixShow, _prefixSeason, ep):
	# Check if video file exists
	inputFolderPath = inputPath + seasonPath
	outputFolderPath = outputPath + seasonPath
	episodeFullTitle = _prefixShow \
					   + _prefixSeason \
					   + ep.filePrefix \
					   + (ep.titleDE if titleLanguage == "DE" else ep.titleEN)
	fileExtension = os.path.splitext(inputFolderPath + ep.fileVideo)[1]

	# Rename file
	if os.path.exists(inputFolderPath + ep.fileVideo):
		# Rename existing if input == output
		if inputFolderPath == outputFolderPath:
			os.rename(inputFolderPath + ep.fileVideo, inputFolderPath + episodeFullTitle + fileExtension)
		# Copy otherwise
		else:
			# Check if output folder exists and create it if it doesn't
			if not os.path.isdir(outputPath + seasonPath):
				os.makedirs(outputPath + seasonPath)

			shutil.copyfile(inputFolderPath + ep.fileVideo, outputFolderPath + episodeFullTitle + fileExtension)

		# Set title in video file properties
		subprocess.run([
			mkvpropedit,
			outputFolderPath + episodeFullTitle + fileExtension,
			"-e",
			"info",
			"-s",
			"title=" + episodeFullTitle,
			"--add-track-statistics-tags"
		])

		logWrite("Info: " + "Renamed " + inputFolderPath + ep.fileVideo + " to " + outputFolderPath + episodeFullTitle + fileExtension)

	else:
		logWrite("Error: " + inputFolderPath + ep.fileVideo + "does not exist!")


# =========================== Start of Script ===========================================

# Clear log file
open(logFile, 'w').close()

# Write name of script to log file
logWrite("This is " + os.path.basename(__file__))

# Get root element of XML file
root_node = ET.parse(infoPath + "info.xml").getroot()

# Get show prefix for output file name from XML
prefixShow = root_node.find("PrefixShow").text

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
	prefixSeason = season.find("PrefixSeason").text

	# List containing settings for each episode in this season
	episodeSettings = []

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

		dirList = os.listdir(inputPath + seasonPath)

		episodeSettings.append(SettingsEpisode(
			listSearch(dirList, episode.find("FileNameVideoContains").text),
			episode.find("TitleDE").text,
			episode.find("TitleEN").text,
			episode.find("PrefixEpisode").text,
		))

	while episodeSettings:
		es = episodeSettings.pop()
		processEpisode(prefixShow, prefixSeason, es)
