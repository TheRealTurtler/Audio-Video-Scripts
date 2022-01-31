#PY  <- Needed to identify #
#--automatically built--

adm = Avidemux()
adm.videoCodec("Copy")
adm.audioClearTracks()
adm.setSourceTrackLanguage(0,"eng")
adm.audioAddExternal("Stargate Atlantis/Deutsch/Staffel 1/temp.aac")
adm.setSourceTrackLanguage(1,"deu")
if adm.audioTotalTracksCount() <= 1:
    raise("Cannot add audio track 1, total tracks: " + str(adm.audioTotalTracksCount()))
adm.audioAddTrack(1)
adm.audioCodec(0, "FDK_AAC")
adm.audioSetDrc(0, 0)
adm.audioSetShift(0, 1, 1500)
adm.audioSetPal2Film(0, 1)
adm.audioSetNormalize2(0, 1, 10, -50)
if adm.audioTotalTracksCount() <= 0:
    raise("Cannot add audio track 0, total tracks: " + str(adm.audioTotalTracksCount()))
adm.audioAddTrack(0)
adm.audioCodec(1, "copy")
adm.audioSetDrc(1, 0)
adm.audioSetShift(1, 0, 0)
adm.setContainer("MKV", "forceAspectRatio=False", "displayWidth=1280", "displayAspectRatio=2", "addColourInfo=False", "colMatrixCoeff=2", "colRange=0", "colTransfer=2", "colPrimaries=2")
