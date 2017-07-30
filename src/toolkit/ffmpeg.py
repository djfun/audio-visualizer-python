'''
    Tools for using ffmpeg
'''
import numpy
import sys
import os
import subprocess
import threading
import signal
from queue import PriorityQueue

import core
from toolkit.common import checkOutput, pipeWrapper
from component import ComponentError


class FfmpegVideo:
    '''Opens a pipe to ffmpeg and stores a buffer of raw video frames.'''

    # error from the thread used to fill the buffer
    threadError = None

    def __init__(self, **kwargs):
        mandatoryArgs = [
            'inputPath',
            'filter_',
            'width',
            'height',
            'frameRate',  # frames per second
            'chunkSize',  # number of bytes in one frame
            'parent',     # mainwindow object
            'component',  # component object
        ]
        for arg in mandatoryArgs:
            setattr(self, arg, kwargs[arg])

        self.frameNo = -1
        self.currentFrame = 'None'
        self.map_ = None
        self.debug = False

        if 'loopVideo' in kwargs and kwargs['loopVideo']:
            self.loopValue = '-1'
        else:
            self.loopValue = '0'
        if 'filter_' in kwargs:
            if kwargs['filter_'][0] != '-filter_complex':
                kwargs['filter_'].insert(0, '-filter_complex')
        else:
            kwargs['filter_'] = None
        if 'debug' in kwargs:
            self.debug = True

        self.command = [
            core.Core.FFMPEG_BIN,
            '-thread_queue_size', '512',
            '-r', str(self.frameRate),
            '-stream_loop', self.loopValue,
            '-i', self.inputPath,
            '-f', 'image2pipe',
            '-pix_fmt', 'rgba',
        ]
        if type(kwargs['filter_']) is list:
            self.command.extend(
                kwargs['filter_']
            )
        self.command.extend([
            '-codec:v', 'rawvideo', '-',
        ])

        self.frameBuffer = PriorityQueue()
        self.frameBuffer.maxsize = self.frameRate
        self.finishedFrames = {}

        self.thread = threading.Thread(
            target=self.fillBuffer,
            name='FFmpeg Frame-Fetcher'
        )
        self.thread.daemon = True
        self.thread.start()

    def frame(self, num):
        while True:
            if num in self.finishedFrames:
                image = self.finishedFrames.pop(num)
                return image

            i, image = self.frameBuffer.get()
            self.finishedFrames[i] = image
            self.frameBuffer.task_done()

    def fillBuffer(self):
        if self.debug:
            print(" ".join([word for word in self.command]))
            err = sys.__stdout__
        else:
            err = subprocess.DEVNULL

        self.pipe = openPipe(
            self.command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=err, bufsize=10**8
        )
        while True:
            if self.parent.canceled:
                break
            self.frameNo += 1

            # If we run out of frames, use the last good frame and loop.
            try:
                if len(self.currentFrame) == 0:
                    self.frameBuffer.put((self.frameNo-1, self.lastFrame))
                    continue
            except AttributeError:
                FfmpegVideo.threadError = ComponentError(self.component, 'video')
                break

            self.currentFrame = self.pipe.stdout.read(self.chunkSize)
            if len(self.currentFrame) != 0:
                self.frameBuffer.put((self.frameNo, self.currentFrame))
                self.lastFrame = self.currentFrame


@pipeWrapper
def openPipe(commandList, **kwargs):
    return subprocess.Popen(commandList, **kwargs)


def closePipe(pipe):
    pipe.stdout.close()
    pipe.send_signal(signal.SIGINT)


def findFfmpeg():
    if getattr(sys, 'frozen', False):
        # The application is frozen
        if sys.platform == "win32":
            return os.path.join(core.Core.wd, 'ffmpeg.exe')
        else:
            return os.path.join(core.Core.wd, 'ffmpeg')

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
            except subprocess.CalledProcessError:
                return "avconv"


def createFfmpegCommand(inputFile, outputFile, components, duration=-1):
    '''
        Constructs the major ffmpeg command used to export the video
    '''
    if duration == -1:
        duration = getAudioDuration(inputFile)
    safeDuration = "{0:.3f}".format(duration - 0.05)  # used by filters
    duration = "{0:.3f}".format(duration + 0.1)  # used by input sources
    Core = core.Core

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

    extraAudio = [
        comp.audio for comp in components
        if 'audio' in comp.properties()
    ]
    segment = createAudioFilterCommand(extraAudio, safeDuration)
    ffmpegCommand.extend(segment)
    if segment:
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


def createAudioFilterCommand(extraAudio, duration):
    '''Add extra inputs and any needed filters to the main ffmpeg command.'''
    # NOTE: Global filters are currently hard-coded here for debugging use
    globalFilters = 0  # increase to add global filters

    if not extraAudio and not globalFilters:
        return []

    ffmpegCommand = []
    # Add -i options for extra input files
    extraFilters = {}
    for streamNo, params in enumerate(reversed(extraAudio)):
        extraInputFile, params = params
        ffmpegCommand.extend([
            '-t', duration,
            # Tell ffmpeg about shorter clips (seemingly not needed)
            #   streamDuration = getAudioDuration(extraInputFile)
            #   if streamDuration and streamDuration > float(safeDuration)
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
    return ffmpegCommand


def testAudioStream(filename):
    '''Test if an audio stream definitely exists'''
    audioTestCommand = [
        core.Core.FFMPEG_BIN,
        '-i', filename,
        '-vn', '-f', 'null', '-'
    ]
    try:
        checkOutput(audioTestCommand, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return False
    else:
        return True


def getAudioDuration(filename):
    '''Try to get duration of audio file as float, or False if not possible'''
    command = [core.Core.FFMPEG_BIN, '-i', filename]

    try:
        fileInfo = checkOutput(command, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as ex:
        fileInfo = ex.output

    try:
        info = fileInfo.decode("utf-8").split('\n')
    except UnicodeDecodeError as e:
        print('Unicode error:', str(e))
        return False

    for line in info:
        if 'Duration' in line:
            d = line.split(',')[0]
            d = d.split(' ')[3]
            d = d.split(':')
            duration = float(d[0])*3600 + float(d[1])*60 + float(d[2])
            break
    else:
        # String not found in output
        return False
    return duration


def readAudioFile(filename, videoWorker):
    '''
        Creates the completeAudioArray given to components
        and used to draw the classic visualizer.
    '''
    duration = getAudioDuration(filename)
    if not duration:
        print('Audio file doesn\'t exist or unreadable.')
        return

    command = [
        core.Core.FFMPEG_BIN,
        '-i', filename,
        '-f', 's16le',
        '-acodec', 'pcm_s16le',
        '-ar', '44100',  # ouput will have 44100 Hz
        '-ac', '1',  # mono (set to '2' for stereo)
        '-']
    in_pipe = openPipe(
        command,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=10**8
    )

    completeAudioArray = numpy.empty(0, dtype="int16")

    progress = 0
    lastPercent = None
    while True:
        if core.Core.canceled:
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
            videoWorker.progressBarSetText.emit(string)
            videoWorker.progressBarUpdate.emit(percent)

        lastPercent = percent

    in_pipe.kill()
    in_pipe.wait()

    # add 0s the end
    completeAudioArrayCopy = numpy.zeros(
        len(completeAudioArray) + 44100, dtype="int16")
    completeAudioArrayCopy[:len(completeAudioArray)] = completeAudioArray
    completeAudioArray = completeAudioArrayCopy

    return (completeAudioArray, duration)
