import glob
import os
import subprocess
from pymediainfo import MediaInfo
from mutagen.mp4 import MP4

# Settings
seasons = [2]
episodes = ["06"]	# Empty list selects all episodes

avidemuxSettings = "avidemux_settings.py"
outputLocation = "E:/Filme/Stargate Atlantis/"
logFile = "log.txt"


def logWrite(logStr):
	print(logStr)
	with open(logFile, 'a') as fileHandle:
		fileHandle.write(logStr + '\n')


def errorCritical(errorStr):
	logWrite("Error: " + errorStr)
	print()
	#input("Press any key to continue...")
	exit()


for season in seasons:
	# Audio Shifts Season 1
	if season == 1:
		audioStart = "00:00:05.000"
		audioShifts = (800, 1300, 700, 1500, 1700, 1500, 700, 1400, 800, 600, 800, 600, 700, 700, 800, 800, 800, 800, 750)
		#			   1+2  3     4    5     6     7     8    9     10   11   12   13   14   15   16   17   18   19   20
		titleRemoveSubstring = ""
	# Audio Shifts Season 2
	elif season == 2:
		audioStart = "00:00:00.000"
		audioShifts = (1000, 1000, 1000, 400, 1200, 800, 800, 600, 600, -600, 1000, 800, 800, 600, 800, 1200, 800, 800, 800, -400)
		#			   1     2     3     4    5     6    7    8    9    10    11    12   13   14   15   16    17   18   19   20
		titleRemoveSubstring = ""
	# Audio Shifts Season 3
	elif season == 3:
		audioStart = "00:00:00.000"
		audioShifts = (1000, 1000, 900, 1000, 800, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
		#			   1     2     3    4     5    6  7  8  9  10 11 12 13 14 15 16 17 18 19 20
		titleRemoveSubstring = ""
	# Audio Shifts Season 4
	elif season == 4:
		audioStart = "00:00:00.000"
		audioShifts = (-200, 800, 800, 800, 800, 800, 800, 800, 800, -200, 800, 800, 800, 800, 800, 800, 800, 800, 800, 800)
		#			   1     2    3    4    5    6    7    8    9    10    11   12   13   14   15   16   17   18   19   20
		titleRemoveSubstring = ""
	# Audio Shifts Season 5
	elif season == 5:
		audioStart = "00:00:00.000"
		audioShifts = (600, -200, 900, 700, 800, -200, 0, 0, 0, 0, 800, -200, -200, 800, 0, 0, -200, 0, 0, 0)
		#			   1    2     3    4    5    6     7  8  9  10 11   12    13    14   15 16 17    18 19 20
		titleRemoveSubstring = " / Encoded by Hunter | Crazy4TV.com"
	else:
		errorCritical("Season has to be a number between 1-5!")

	# Video file types to check
	fileTypes = ("*.mp4", "*.mkv")

	# Create a list containing all video file paths
	folderName = "Stargate Atlantis Season " + str(season)
	fileList = [f for f_ in [glob.glob(folderName + "/" + e) for e in fileTypes] for f in f_]

	# Clear log file
	open(logFile, 'w').close()

	# Iterate over video files
	for currentEpisode, videoPath in enumerate(fileList):
		# Get file name of video
		fileName = os.path.basename(videoPath)

		# Check if specific episodes are selected
		if episodes:
			skip = True
			# Check if file name contains episode number
			for e in episodes:
				if str(e) in fileName:
					skip = False

			# Skip current video if episode is not selected
			if skip:
				continue

		# Audio file paths
		audioPath_m4a = folderName + " German" + '/' + os.path.splitext(fileName)[0] + ".m4a"
		audioPath_aac = os.path.splitext(audioPath_m4a)[0] + ".aac"

		# Output video file path
		#outputPath = folderName + '/' + outputLocation + os.path.splitext(fileName)[0] + ".mp4"
		outputPath = outputLocation + '/' + "Staffel " + str(season) + '/' + os.path.splitext(fileName)[0] + ".mp4"

		# Check if output folder exists and create it if it doesn't
		#if not os.path.isdir(folderName + '/' + outputLocation):
		#	os.mkdir(folderName + '/' + outputLocation)
		if not os.path.isdir(outputLocation + '/' + "Staffel " + str(season) + '/'):
			os.mkdir(outputLocation + '/' + "Staffel " + str(season) + '/')

		# Check if audio file exists
		if os.path.exists(audioPath_m4a):
			# Extract .aac audio file from .m4a container
			logWrite("Extracting audio from " + '"' + audioPath_m4a + '"' + "...")
			subprocess.run([
				"ffmpeg",
				"-hide_banner",
				"-loglevel",
				"error",
				"-y",
				"-ss",
				audioStart,
				"-i",
				audioPath_m4a,
				"-acodec",
				"copy",
				audioPath_aac
			])
		else:
			errorCritical('"' + audioPath_m4a + '"' + " does not exist!")

		# Read settings file
		with open(avidemuxSettings, 'r') as file:
			data = file.readlines()

			for idx, line in enumerate(data):
				if "adm.audioAddExternal" in line:
					data[idx] = "adm.audioAddExternal(\"" + audioPath_aac + "\")\n"
				if "adm.audioSetShift(0" in line:
					data[idx] = "adm.audioSetShift(0, 1, " + str(audioShifts[currentEpisode]) + ")\n"

		# Write settings file
		with open(avidemuxSettings, 'w') as file:
			for line in data:
				file.write(line)

		# Check if video file exists
		if os.path.exists(audioPath_aac):
			# Add audio track to video
			logWrite("Adding audio track to video file " + '"' + videoPath + '"' + "...")
			subprocess.run([
				"E:\Program Files\Avidemux 2.7 VC++ 64bits\Avidemux.exe",
				"--load",
				videoPath,
				"--run",
				avidemuxSettings,
				"--save",
				outputPath,
				"--quit"
			])

			# Delete extracted audio
			os.remove(audioPath_aac)
		else:
			errorCritical('"' + audioPath_aac + '"' + " does not exist!")

		# Check if output file exists
		if os.path.exists(outputPath):
			# Set title in video file properties
			mediaInfo = MediaInfo.parse(videoPath)
			for track in mediaInfo.tracks:
				if track.track_type == "General":
					movieTags = MP4(outputPath)
					movieTags["\xa9nam"] = track.title.replace(titleRemoveSubstring, "")
					movieTags.save()
