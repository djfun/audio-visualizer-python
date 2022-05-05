'''
    Thread created to export a video. It has a slot to begin export using
    an input file, output path, and component list. During export multiple
    threads are created to render the video as quickly as possible. Signals
    are emitted to update MainWindow's progress bar, detail text, and preview.
    Export can be cancelled with cancel()
'''
from PyQt5 import QtCore, QtGui
from PyQt5.QtCore import pyqtSignal, pyqtSlot
from PIL import Image
from PIL.ImageQt import ImageQt
import numpy
import subprocess as sp
import sys
import os
import time
import signal
import logging

from .component import ComponentError
from .toolkit.frame import Checkerboard
from .toolkit.ffmpeg import (
    openPipe, readAudioFile,
    getAudioDuration, createFfmpegCommand
)


log = logging.getLogger("AVP.VideoThread")


class Worker(QtCore.QObject):

    imageCreated = pyqtSignal('QImage')
    videoCreated = pyqtSignal()
    progressBarUpdate = pyqtSignal(int)
    progressBarSetText = pyqtSignal(str)
    encoding = pyqtSignal(bool)

    def __init__(self, parent, inputFile, outputFile, components):
        super().__init__()
        self.core = parent.core
        self.settings = parent.settings
        self.modules = parent.core.modules
        parent.createVideo.connect(self.createVideo)
        self.previewEnabled = type(parent.core).previewEnabled

        self.components = components
        self.outputFile = outputFile
        self.inputFile = inputFile

        self.hertz = 44100
        self.sampleSize = 1470  # 44100 / 30 = 1470
        self.canceled = False
        self.error = False

    def renderFrame(self, audioI):
        '''
            Grabs audio data indices at frames to export, from compositeQueue.
            Sends it to the components' frameRender methods in layer order
            to create subframes & composite them into the final frame.
            The resulting frames are collected in the renderQueue
        '''
        def err():
            self.closePipe()
            self.cancelExport()
            self.error = True
            msg = 'A call to renderFrame in the video thread failed critically.'
            log.critical(msg)
            comp._error.emit(msg, str(e))

        bgI = int(audioI / self.sampleSize)
        frame = None
        for layerNo, comp in enumerate(reversed((self.components))):
            if self.canceled:
                break
            try:
                if layerNo in self.staticComponents:
                    if self.staticComponents[layerNo] is None:
                        # this layer was merged into a following layer
                        continue
                    # static component
                    if frame is None:  # bottom-most layer
                        frame = self.staticComponents[layerNo]
                    else:
                        frame = Image.alpha_composite(
                            frame, self.staticComponents[layerNo]
                        )

                else:
                    # animated component
                    if frame is None:  # bottom-most layer
                        frame = comp.frameRender(bgI)
                    else:
                        frame = Image.alpha_composite(
                            frame, comp.frameRender(bgI)
                        )
            except Exception as e:
                err()
        return frame

    def showPreview(self, frame):
        '''
            Receives a final frame that will be piped to FFmpeg,
            adds it to the checkerboard and emits a final QImage
            to the MainWindow for the live preview
        '''
        # We must store a reference to this QImage
        # or else Qt will garbage-collect it on the C++ side
        self.latestPreview = ImageQt(frame)
        self.imageCreated.emit(QtGui.QImage(self.latestPreview))
        self.lastPreview = time.time()

    @pyqtSlot()
    def createVideo(self):
        log.debug("Video worker received signal to createVideo")
        log.debug(
            'Video thread id: {}'.format(int(QtCore.QThread.currentThreadId())))
        numpy.seterr(divide='ignore')
        self.encoding.emit(True)
        self.extraAudio = []
        self.width = int(self.settings.value('outputWidth'))
        self.height = int(self.settings.value('outputHeight'))

        # set Core.canceled to False and call .reset() on each component
        self.reset()
        # initialize progress bar
        progressBarValue = 0
        self.progressBarUpdate.emit(progressBarValue)

        # =~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~==~=~=~=~=~=~=~=~=~=~=~=~=~=~
        # READ AUDIO, INITIALIZE COMPONENTS, OPEN A PIPE TO FFMPEG
        # =~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~==~=~=~=~=~=~=~=~=~=~=~=~=~=~
        log.debug("Determining length of audio...")
        if any([
                True if 'pcm' in comp.properties() else False
                for comp in self.components
                ]):
            self.progressBarSetText.emit("Loading audio file...")
            audioFileTraits = readAudioFile(
                self.inputFile, self
            )
            if audioFileTraits is None:
                self.cancelExport()
                return
            self.completeAudioArray, duration = audioFileTraits
            self.audioArrayLen = len(self.completeAudioArray)
        else:
            duration = getAudioDuration(self.inputFile)
            self.completeAudioArray = []
            self.audioArrayLen = int(
                ((duration * self.hertz) +
                    self.hertz) - self.sampleSize)

        self.progressBarUpdate.emit(0)
        self.progressBarSetText.emit("Starting components...")
        canceledByComponent = False
        initText = ", ".join([
            "%s) %s" % (num, str(component))
            for num, component in enumerate(reversed(self.components))
        ])
        print('Loaded Components:', initText)
        log.info('Calling preFrameRender for %s', initText)
        self.staticComponents = {}
        for compNo, comp in enumerate(reversed(self.components)):
            try:
                comp.preFrameRender(
                    audioFile=self.inputFile,
                    completeAudioArray=self.completeAudioArray,
                    audioArrayLen=self.audioArrayLen,
                    sampleSize=self.sampleSize,
                    progressBarUpdate=self.progressBarUpdate,
                    progressBarSetText=self.progressBarSetText
                )
            except ComponentError:
                log.warning(
                    '#%s %s encountered an error in its preFrameRender method',
                    compNo,
                    comp
                )

            compProps = comp.properties()
            if 'error' in compProps or comp._lockedError is not None:
                self.cancel()
                self.canceled = True
                canceledByComponent = True
                compError = comp.error() \
                    if type(comp.error()) is tuple else (comp.error(), '')
                errMsg = (
                    "Component #%s (%s) encountered an error!" % (
                        str(compNo), comp.name
                    )
                    if comp.error() is None else
                    'Export cancelled by component #%s (%s): %s' % (
                        str(compNo),
                        comp.name,
                        compError[0]
                    )
                )
                log.error(errMsg)
                comp._error.emit(errMsg, compError[1])
                break
            if 'static' in compProps:
                log.info('Saving static frame from #%s %s', compNo, comp)
                self.staticComponents[compNo] = \
                    comp.frameRender(0).copy()

        log.debug("Checking if a component wishes to cancel the export...")
        if self.canceled:
            if canceledByComponent:
                log.error(
                    'Export cancelled by component #%s (%s): %s',
                    compNo,
                    comp.name,
                    'No message.' if comp.error() is None else (
                        comp.error() if type(comp.error()) is str
                        else comp.error()[0]
                    )
                )
            self.cancelExport()
            return

        log.info("Merging consecutive static component frames")
        for compNo in range(len(self.components)):
            if compNo not in self.staticComponents \
                    or compNo + 1 not in self.staticComponents:
                continue
            self.staticComponents[compNo + 1] = Image.alpha_composite(
                self.staticComponents.pop(compNo),
                self.staticComponents[compNo + 1]
            )
            self.staticComponents[compNo] = None

        try:
            ffmpegCommand = createFfmpegCommand(
                self.inputFile, self.outputFile, self.components, duration
            )
        except sp.CalledProcessError as e:
            #FIXME video_thread should own this error signal, not components
            self.components[0]._error.emit("Ffmpeg could not be found. Is it installed?", str(e))
            self.error = True
            return

        cmd = " ".join(ffmpegCommand)
        print('###### FFMPEG COMMAND ######\n%s' % cmd)
        print('############################')
        if not cmd:
            #FIXME video_thread should own this error signal, not components
            self.components[0]._error.emit("The ffmpeg command could not be generated.", "")
            log.critical("Cancelling render process due to failure while generating the ffmpeg command.")
            self.failExport()
            return

        log.info('Opening pipe to ffmpeg')
        log.info(cmd)
        try:
            self.out_pipe = openPipe(
                ffmpegCommand,
                stdin=sp.PIPE, stdout=sys.stdout, stderr=sys.stdout
            )
        except sp.CalledProcessError:
            log.critical('Ffmpeg pipe couldn\'t be created!', exc_info=True)
            raise

        # =~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~==~=~=~=~=~=~=~=~=~=~=~=~=~=~
        # START CREATING THE VIDEO
        # =~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~==~=~=~=~=~=~=~=~=~=~=~=~=~=~

        # Last time preview was drawn
        self.lastPreview = time.time()

        # Begin piping into ffmpeg!
        progressBarValue = 0
        self.progressBarUpdate.emit(progressBarValue)
        self.progressBarSetText.emit("Exporting video...")
        for audioI in range(0, self.audioArrayLen, self.sampleSize):
            if self.canceled:
                break
            # fetch the next frame & add to the FFmpeg pipe
            frame = self.renderFrame(audioI)

            # Update live preview
            if self.previewEnabled and time.time() - self.lastPreview > 0.5:
                self.showPreview(frame)

            try:
                self.out_pipe.stdin.write(frame.tobytes())
            except Exception:
                break

            # increase progress bar value
            completion = (audioI / self.audioArrayLen) * 100
            if progressBarValue + 1 <= completion:
                progressBarValue = numpy.floor(completion).astype(int)
                self.progressBarUpdate.emit(progressBarValue)
                self.progressBarSetText.emit(
                    "Exporting video: %s%%" % str(int(progressBarValue))
                )


        numpy.seterr(all='print')

        self.closePipe()

        for comp in reversed(self.components):
            comp.postFrameRender()

        if self.canceled:
            print("Export Canceled")
            try:
                os.remove(self.outputFile)
            except Exception:
                pass
            self.progressBarUpdate.emit(0)
            self.progressBarSetText.emit('Export Canceled')
        else:
            if self.error:
                self.failExport()
            else:
                print("Export Complete")
                self.progressBarUpdate.emit(100)
                self.progressBarSetText.emit('Export Complete')

        self.error = False
        self.canceled = False
        self.encoding.emit(False)
        self.videoCreated.emit()

    def closePipe(self):
        try:
            self.out_pipe.stdin.close()
        except (BrokenPipeError, OSError):
            log.error('Broken pipe to FFmpeg!')
        if self.out_pipe.stderr is not None:
            log.error(self.out_pipe.stderr.read())
            self.out_pipe.stderr.close()
            self.error = True
        self.out_pipe.wait()

    def cancelExport(self, message='Export Canceled'):
        self.progressBarUpdate.emit(0)
        self.progressBarSetText.emit(message)
        self.encoding.emit(False)
        self.videoCreated.emit()

    def failExport(self):
        self.cancelExport('Export Failed')

    def updateProgress(self, pStr, pVal):
        self.progressBarValue.emit(pVal)
        self.progressBarSetText.emit(pStr)

    def cancel(self):
        self.canceled = True
        self.core.cancel()

        for comp in self.components:
            comp.cancel()

        try:
            self.out_pipe.send_signal(signal.SIGTERM)
        except Exception:
            pass

    def reset(self):
        self.core.reset()
        self.canceled = False
        for comp in self.components:
            comp.reset()
