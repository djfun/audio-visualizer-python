"""
Worker thread created to export a video. It has a slot to begin export using
an input file, output path, and component list.

Signals are emitted to update MainWindow's progress bar, detail text, and preview.
A Command object takes the place of MainWindow while in commandline mode.

Export can be cancelled with cancel()
"""

from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import pyqtSignal, pyqtSlot
from PIL import Image
from PIL.ImageQt import ImageQt
import numpy
import subprocess as sp
import sys
import os
import time
import signal
import logging

from .libcomponent import ComponentError
from .toolkit.frame import Checkerboard
from .toolkit.ffmpeg import (
    openPipe,
    readAudioFile,
    getAudioDuration,
    createFfmpegCommand,
)


log = logging.getLogger("AVP.VideoThread")


class Worker(QtCore.QObject):

    imageCreated = pyqtSignal("QImage")
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

    def createFfmpegCommand(self, duration):
        try:
            ffmpegCommand = createFfmpegCommand(
                self.inputFile,
                self.outputFile,
                self.components,
                duration,
                "info" if log.getEffectiveLevel() < logging.WARNING else "error",
            )
        except sp.CalledProcessError as e:
            # FIXME video_thread should own this error signal, not components
            self.components[0]._error.emit(
                "Ffmpeg could not be found. Is it installed?", str(e)
            )
            self.error = True
            return

        if not ffmpegCommand:
            # FIXME video_thread should own this error signal, not components
            self.components[0]._error.emit(
                "The FFmpeg command could not be generated.", ""
            )
            log.critical(
                "Cancelling render process due to failure while generating the ffmpeg command."
            )
            self.failExport()
            return
        return ffmpegCommand

    def determineAudioLength(self):
        """
        Returns audio length which determines length of final video, or False if failure occurs
        """
        if any(
            [True if "pcm" in comp.properties() else False for comp in self.components]
        ):
            self.progressBarSetText.emit("Loading audio file...")
            audioFileTraits = readAudioFile(self.inputFile, self)
            if audioFileTraits is None:
                self.cancelExport()
                return False
            self.completeAudioArray, duration = audioFileTraits
            self.audioArrayLen = len(self.completeAudioArray)
        else:
            duration = getAudioDuration(self.inputFile)
            self.completeAudioArray = []
            self.audioArrayLen = int(
                ((duration * self.hertz) + self.hertz) - self.sampleSize
            )
        return duration

    def preFrameRender(self):
        """
        Initializes components that need to pre-compute stuff.
        Also prerenders "static" components like text and merges them if possible
        """
        self.staticComponents = {}

        # Call preFrameRender on each component
        canceledByComponent = False
        initText = ", ".join(
            [
                "%s) %s" % (num, str(component))
                for num, component in enumerate(reversed(self.components))
            ]
        )
        print("Loaded Components:", initText)
        log.info("Calling preFrameRender for %s", initText)
        for compNo, comp in enumerate(reversed(self.components)):
            try:
                comp.preFrameRender(
                    audioFile=self.inputFile,
                    completeAudioArray=self.completeAudioArray,
                    audioArrayLen=self.audioArrayLen,
                    sampleSize=self.sampleSize,
                    progressBarUpdate=self.progressBarUpdate,
                    progressBarSetText=self.progressBarSetText,
                )
            except ComponentError:
                log.warning(
                    "#%s %s encountered an error in its preFrameRender method",
                    compNo,
                    comp,
                )

            compProps = comp.properties()
            if "error" in compProps or comp._lockedError is not None:
                self.cancel()
                self.canceled = True
                canceledByComponent = True
                compError = (
                    comp.error() if type(comp.error()) is tuple else (comp.error(), "")
                )
                errMsg = (
                    "Component #%s (%s) encountered an error!"
                    % (str(compNo), comp.name)
                    if comp.error() is None
                    else "Export cancelled by component #%s (%s): %s"
                    % (str(compNo), comp.name, compError[0])
                )
                log.error(errMsg)
                comp._error.emit(errMsg, compError[1])
                break
            if "static" in compProps:
                log.info("Saving static frame from #%s %s", compNo, comp)
                self.staticComponents[compNo] = comp.frameRender(0).copy()

        # Check if any errors occured
        log.debug("Checking if a component wishes to cancel the export...")
        if self.canceled:
            if canceledByComponent:
                log.error(
                    "Export cancelled by component #%s (%s): %s",
                    compNo,
                    comp.name,
                    (
                        "No message."
                        if comp.error() is None
                        else (
                            comp.error()
                            if type(comp.error()) is str
                            else comp.error()[0]
                        )
                    ),
                )
            self.cancelExport()

        # Merge static frames that can be merged to reduce workload
        def mergeConsecutiveStaticComponentFrames(self):
            log.info("Merging consecutive static component frames")
            for compNo in range(len(self.components)):
                if (
                    compNo not in self.staticComponents
                    or compNo + 1 not in self.staticComponents
                ):
                    continue
                self.staticComponents[compNo + 1] = Image.alpha_composite(
                    self.staticComponents.pop(compNo),
                    self.staticComponents[compNo + 1],
                )
                self.staticComponents[compNo] = None

        mergeConsecutiveStaticComponentFrames(self)

    def frameRender(self, audioI):
        """
        Renders a frame composited together from the frames returned by each component
        audioI is a multiple of self.sampleSize, which can be divided to determine frameNo
        """

        def err():
            self.closePipe()
            self.cancelExport()
            self.error = True
            msg = "A call to renderFrame in the video thread failed critically."
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
                        frame = Image.alpha_composite(frame, comp.frameRender(bgI))
            except Exception as e:
                err()
        return frame

    def showPreview(self, frame):
        """
        Receives a final frame that will be piped to FFmpeg,
        adds it to the MainWindow for the live preview
        """
        # We must store a reference to this QImage
        # or else Qt will garbage-collect it on the C++ side
        self.latestPreview = ImageQt(frame)
        self.imageCreated.emit(QtGui.QImage(self.latestPreview))

    @pyqtSlot()
    def createVideo(self):
        """
        1. Determine length of final video
        2. Call preFrameRender on each component
        3. Create the main FFmpeg command
        4. Open the out_pipe to FFmpeg process
        5. Iterate over the audio data array and call frameRender on the components to get frames
        6. Close the out_pipe
        7. Call postFrameRender on each component
        """
        log.debug("Video worker received signal to createVideo")
        log.debug("Video thread id: {}".format(int(QtCore.QThread.currentThreadId())))
        self.encoding.emit(True)
        self.extraAudio = []
        self.width = int(self.settings.value("outputWidth"))
        self.height = int(self.settings.value("outputHeight"))

        # Set core.Core.canceled to False and call .reset() on each component
        self.reset()
        # Initialize progress bar to 0
        progressBarValue = 0
        self.progressBarUpdate.emit(progressBarValue)

        # Determine longest length of audio which will be the final video's duration
        log.debug("Determining length of audio...")
        duration = self.determineAudioLength()
        if not duration:
            return

        # Call preFrameRender on each component to perform initialization
        self.progressBarUpdate.emit(0)
        self.progressBarSetText.emit("Starting components...")
        self.preFrameRender()
        if self.canceled:
            return

        # Create FFmpeg command
        ffmpegCommand = self.createFfmpegCommand(duration)
        if not ffmpegCommand:
            return
        cmd = " ".join(ffmpegCommand)
        print("###### FFMPEG COMMAND ######\n%s" % cmd)
        print("############################")
        log.info(cmd)

        # Open pipe to FFmpeg
        log.info("Opening pipe to FFmpeg")
        try:
            self.out_pipe = openPipe(
                ffmpegCommand,
                stdin=sp.PIPE,
                stdout=sys.stdout,
                stderr=sys.stdout,
            )
        except sp.CalledProcessError:
            log.critical("Out_Pipe to FFmpeg couldn't be created!", exc_info=True)
            raise

        # =~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~
        # START CREATING THE VIDEO
        # =~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~
        progressBarValue = 0
        self.progressBarUpdate.emit(progressBarValue)
        # Begin piping into ffmpeg!
        self.progressBarSetText.emit("Exporting video...")
        for audioI in range(0, self.audioArrayLen, self.sampleSize):
            if self.canceled:
                break
            # fetch the next frame & add to the FFmpeg pipe
            frame = self.frameRender(audioI)

            # Update live preview
            if self.previewEnabled:
                self.showPreview(frame)

            try:
                self.out_pipe.stdin.write(frame.tobytes())
            except Exception:
                break

            # increase progress bar value
            completion = (audioI / self.audioArrayLen) * 100
            if progressBarValue + 1 <= completion:
                progressBarValue = numpy.floor(completion).astype(int)
                msg = "Exporting video: %s%%" % str(int(progressBarValue))
                self.progressBarUpdate.emit(progressBarValue)
                self.progressBarSetText.emit(msg)

        # =~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~
        # Finished creating the video!
        # =~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~

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
            self.progressBarSetText.emit("Export Canceled")
        else:
            if self.error:
                self.failExport()
            else:
                print("\nExport Complete")
                self.progressBarUpdate.emit(100)
                self.progressBarSetText.emit("Export Complete")

        self.error = False
        self.canceled = False
        self.encoding.emit(False)
        self.videoCreated.emit()

    def closePipe(self):
        try:
            self.out_pipe.stdin.close()
        except (BrokenPipeError, OSError):
            log.debug("Broken pipe to FFmpeg!")
        if self.out_pipe.stderr is not None:
            log.error(self.out_pipe.stderr.read())
            self.out_pipe.stderr.close()
            self.error = True
        self.out_pipe.wait()

    def cancelExport(self, message="Export Canceled"):
        self.progressBarUpdate.emit(0)
        self.progressBarSetText.emit(message)
        self.encoding.emit(False)
        self.videoCreated.emit()

    def failExport(self):
        self.cancelExport("Export Failed")

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
