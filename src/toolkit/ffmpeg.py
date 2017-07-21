'''
    Tools for using ffmpeg
'''
import numpy
import sys
import os
import subprocess as sp

from toolkit.common import Core, checkOutput, openPipe


def findFfmpeg():
    if getattr(sys, 'frozen', False):
        # The application is frozen
        if sys.platform == "win32":
            return os.path.join(Core.wd, 'ffmpeg.exe')
        else:
            return os.path.join(Core.wd, 'ffmpeg')

    else:
        if sys.platform == "win32":
            return "ffmpeg"
        else:
            try:
                with open(os.devnull, "w") as f:
                    checkOutput(
                        ['ffmpeg', '-version'], stderr=f
                    )
                return "ffmpeg"
            except sp.CalledProcessError:
                return "avconv"


def createFfmpegCommand(inputFile, outputFile, components, duration=-1):
    '''
        Constructs the major ffmpeg command used to export the video
    '''
    if duration == -1:
        duration = getAudioDuration(inputFile)

    safeDuration = "{0:.3f}".format(duration - 0.05)  # used by filters
    duration = "{0:.3f}".format(duration + 0.1)  # used by input sources

    # Test if user has libfdk_aac
    encoders = checkOutput(
        "%s -encoders -hide_banner" % Core.FFMPEG_BIN, shell=True
    )
    encoders = encoders.decode("utf-8")

    acodec = Core.settings.value('outputAudioCodec')

    options = Core.encoderOptions
    containerName = Core.settings.value('outputContainer')
    vcodec = Core.settings.value('outputVideoCodec')
    vbitrate = str(Core.settings.value('outputVideoBitrate'))+'k'
    acodec = Core.settings.value('outputAudioCodec')
    abitrate = str(Core.settings.value('outputAudioBitrate'))+'k'

    for cont in options['containers']:
        if cont['name'] == containerName:
            container = cont['container']
            break

    vencoders = options['video-codecs'][vcodec]
    aencoders = options['audio-codecs'][acodec]

    for encoder in vencoders:
        if encoder in encoders:
            vencoder = encoder
            break

    for encoder in aencoders:
        if encoder in encoders:
            aencoder = encoder
            break

    ffmpegCommand = [
        Core.FFMPEG_BIN,
        '-thread_queue_size', '512',
        '-y',  # overwrite the output file if it already exists.

        # INPUT VIDEO
        '-f', 'rawvideo',
        '-vcodec', 'rawvideo',
        '-s', '%sx%s' % (
            Core.settings.value('outputWidth'),
            Core.settings.value('outputHeight'),
        ),
        '-pix_fmt', 'rgba',
        '-r', Core.settings.value('outputFrameRate'),
        '-t', duration,
        '-i', '-',  # the video input comes from a pipe
        '-an',  # the video input has no sound

        # INPUT SOUND
        '-t', duration,
        '-i', inputFile
    ]

    # Add extra audio inputs and any needed avfilters
    # NOTE: Global filters are currently hard-coded here for debugging use
    globalFilters = 0  # increase to add global filters
    extraAudio = [
        comp.audio for comp in components
        if 'audio' in comp.properties
    ]
    if extraAudio or globalFilters > 0:
        # Add -i options for extra input files
        extraFilters = {}
        for streamNo, params in enumerate(reversed(extraAudio)):
            extraInputFile, params = params
            ffmpegCommand.extend([
                '-t', safeDuration,
                # Tell ffmpeg about shorter clips (seemingly not needed)
                #   streamDuration = getAudioDuration(extraInputFile)
                #   if  streamDuration > float(safeDuration)
                #   else "{0:.3f}".format(streamDuration),
                '-i', extraInputFile
            ])
            # Construct dataset of extra filters we'll need to add later
            for ffmpegFilter in params:
                if streamNo + 2 not in extraFilters:
                    extraFilters[streamNo + 2] = []
                extraFilters[streamNo + 2].append((
                    ffmpegFilter, params[ffmpegFilter]
                ))

        # Start creating avfilters! Popen-style, so don't use semicolons;
        extraFilterCommand = []

        if globalFilters <= 0:
            # Dictionary of last-used tmp labels for a given stream number
            tmpInputs = {streamNo: -1 for streamNo in extraFilters}
        else:
            # Insert blank entries for global filters into extraFilters
            # so the per-stream filters know what input to source later
            for streamNo in range(len(extraAudio), 0, -1):
                if streamNo + 1 not in extraFilters:
                    extraFilters[streamNo + 1] = []
            # Also filter the primary audio track
            extraFilters[1] = []
            tmpInputs = {
                streamNo: globalFilters - 1
                for streamNo in extraFilters
            }

            # Add the global filters!
            # NOTE: list length must = globalFilters, currently hardcoded
            if tmpInputs:
                extraFilterCommand.extend([
                    '[%s:a] ashowinfo [%stmp0]' % (
                        str(streamNo),
                        str(streamNo)
                    )
                    for streamNo in tmpInputs
                ])

        # Now add the per-stream filters!
        for streamNo, paramList in extraFilters.items():
            for param in paramList:
                source = '[%s:a]' % str(streamNo) \
                    if tmpInputs[streamNo] == -1 else \
                    '[%stmp%s]' % (
                        str(streamNo), str(tmpInputs[streamNo])
                    )
                tmpInputs[streamNo] = tmpInputs[streamNo] + 1
                extraFilterCommand.append(
                    '%s %s%s [%stmp%s]' % (
                        source, param[0], param[1], str(streamNo),
                        str(tmpInputs[streamNo])
                    )
                )

        # Join all the filters together and combine into 1 stream
        extraFilterCommand = "; ".join(extraFilterCommand) + '; ' \
            if tmpInputs else ''
        ffmpegCommand.extend([
            '-filter_complex',
            extraFilterCommand +
            '%s amix=inputs=%s:duration=first [a]'
            % (
                "".join([
                    '[%stmp%s]' % (str(i), tmpInputs[i])
                    if i in extraFilters else '[%s:a]' % str(i)
                    for i in range(1, len(extraAudio) + 2)
                ]),
                str(len(extraAudio) + 1)
            ),
        ])

        # Only map audio from the filters, and video from the pipe
        ffmpegCommand.extend([
            '-map', '0:v',
            '-map', '[a]',
        ])

    ffmpegCommand.extend([
        # OUTPUT
        '-vcodec', vencoder,
        '-acodec', aencoder,
        '-b:v', vbitrate,
        '-b:a', abitrate,
        '-pix_fmt', Core.settings.value('outputVideoFormat'),
        '-preset', Core.settings.value('outputPreset'),
        '-f', container
    ])

    if acodec == 'aac':
        ffmpegCommand.append('-strict')
        ffmpegCommand.append('-2')

    ffmpegCommand.append(outputFile)
    return ffmpegCommand


def getAudioDuration(filename):
    command = [Core.FFMPEG_BIN, '-i', filename]

    try:
        fileInfo = checkOutput(command, stderr=sp.STDOUT)
    except sp.CalledProcessError as ex:
        fileInfo = ex.output

    info = fileInfo.decode("utf-8").split('\n')
    for line in info:
        if 'Duration' in line:
            d = line.split(',')[0]
            d = d.split(' ')[3]
            d = d.split(':')
            duration = float(d[0])*3600 + float(d[1])*60 + float(d[2])
    return duration


def readAudioFile(filename, parent):
    duration = getAudioDuration(filename)

    command = [
        Core.FFMPEG_BIN,
        '-i', filename,
        '-f', 's16le',
        '-acodec', 'pcm_s16le',
        '-ar', '44100',  # ouput will have 44100 Hz
        '-ac', '1',  # mono (set to '2' for stereo)
        '-']
    in_pipe = openPipe(
        command, stdout=sp.PIPE, stderr=sp.DEVNULL, bufsize=10**8
    )

    completeAudioArray = numpy.empty(0, dtype="int16")

    progress = 0
    lastPercent = None
    while True:
        if Core.canceled:
            return
        # read 2 seconds of audio
        progress += 4
        raw_audio = in_pipe.stdout.read(88200*4)
        if len(raw_audio) == 0:
            break
        audio_array = numpy.fromstring(raw_audio, dtype="int16")
        completeAudioArray = numpy.append(completeAudioArray, audio_array)

        percent = int(100*(progress/duration))
        if percent >= 100:
            percent = 100

        if lastPercent != percent:
            string = 'Loading audio file: '+str(percent)+'%'
            parent.progressBarSetText.emit(string)
            parent.progressBarUpdate.emit(percent)

        lastPercent = percent

    in_pipe.kill()
    in_pipe.wait()

    # add 0s the end
    completeAudioArrayCopy = numpy.zeros(
        len(completeAudioArray) + 44100, dtype="int16")
    completeAudioArrayCopy[:len(completeAudioArray)] = completeAudioArray
    completeAudioArray = completeAudioArrayCopy

    return (completeAudioArray, duration)
