import os
import subprocess
import xml.etree.ElementTree as ET

# Settings
seasons = ["1"]			# Empty list selects all seasons (specify as string)
episodes = []			# Empty list selects all episodes (specify as string)

titleLanguage = "EN"  # DE or EN

inputPath = "E:/Filme/The Expanse/"

ffmpeg = "ffmpeg.exe"
mkvpropedit = "mkvpropedit.exe"
logFile = "log.txt"


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
	folderPath = inputPath + seasonPath
	episodeFullTitle = _prefixShow \
					   + _prefixSeason \
					   + ep.filePrefix \
					   + (ep.titleDE if titleLanguage == "DE" else ep.titleEN)
	fileExtension = os.path.splitext(folderPath + ep.fileVideo)[1]

	# Rename file
	if os.path.exists(folderPath + ep.fileVideo):
		os.rename(folderPath + ep.fileVideo, folderPath + episodeFullTitle + fileExtension)

		# Set title in video file properties
		subprocess.run([
			mkvpropedit,
			folderPath + episodeFullTitle + fileExtension,
			"-e",
			"info",
			"-s",
			"title=" + episodeFullTitle,
			"--add-track-statistics-tags"
		])

		logWrite("Info: " + "Renamed " + folderPath + ep.fileVideo + " to " + folderPath + episodeFullTitle + fileExtension)

	else:
		logWrite("Error: " + folderPath + ep.fileVideo + "does not exist!")


# Clear log file
open(logFile, 'w').close()

# Get root element of XML file
root_node = ET.parse(inputPath + "info.xml").getroot()

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
