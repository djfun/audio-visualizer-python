'''
    Thread created to export a video. It has a slot to begin export using
    an input file, output path, and component list. During export multiple
    threads are created to render the video as quickly as possible. Signals
    are emitted to update MainWindow's progress bar, detail text, and preview.
    Export can be cancelled with cancel()
'''
from PyQt5 import QtCore, QtGui, uic
from PyQt5.QtCore import pyqtSignal, pyqtSlot
from PIL import Image, ImageDraw, ImageFont
from PIL.ImageQt import ImageQt
import numpy
import subprocess as sp
import sys
import os
from queue import Queue, PriorityQueue
from threading import Thread, Event
import time
import signal

import core
from toolkit import openPipe, checkOutput
from frame import Checkerboard


class Worker(QtCore.QObject):

    imageCreated = pyqtSignal(['QImage'])
    videoCreated = pyqtSignal()
    progressBarUpdate = pyqtSignal(int)
    progressBarSetText = pyqtSignal(str)
    encoding = pyqtSignal(bool)

    def __init__(self, parent=None):
        QtCore.QObject.__init__(self)
        self.core = parent.core
        self.settings = parent.core.settings
        self.modules = parent.core.modules
        self.parent = parent
        parent.videoTask.connect(self.createVideo)
        self.sampleSize = 1470  # 44100 / 30 = 1470
        self.canceled = False
        self.error = False
        self.stopped = False

    def renderNode(self):
        '''
            Grabs audio data indices at frames to export, from compositeQueue.
            Sends it to the components' frameRender methods in layer order
            to create subframes & composite them into the final frame.
            The resulting frames are collected in the renderQueue
        '''
        while not self.stopped:
            audioI = self.compositeQueue.get()
            bgI = int(audioI / self.sampleSize)
            frame = None
            for compNo, comp in reversed(list(enumerate(self.components))):
                layerNo = len(self.components) - compNo
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
                        frame = comp.frameRender(compNo, bgI)
                    else:
                        frame = Image.alpha_composite(
                            frame, comp.frameRender(compNo, bgI)
                        )

            self.renderQueue.put([audioI, frame])
            self.compositeQueue.task_done()

    def renderDispatch(self):
        '''
            Places audio data indices in the compositeQueue, to be used
            by a renderNode later. All indices are multiples of self.sampleSize
            sampleSize * frameNo = audioI, AKA audio data starting at frameNo
        '''
        print('Dispatching Frames for Compositing...')

        for audioI in range(0, len(self.completeAudioArray), self.sampleSize):
            self.compositeQueue.put(audioI)

    def previewDispatch(self):
        '''
            Grabs frames from the previewQueue, adds them to the checkerboard
            and emits a final QImage to the MainWindow for the live preview
        '''
        background = Checkerboard(self.width, self.height)

        while not self.stopped:
            audioI, frame = self.previewQueue.get()
            if time.time() - self.lastPreview >= 0.06 or audioI == 0:
                image = Image.alpha_composite(background.copy(), frame)
                self.imageCreated.emit(QtGui.QImage(ImageQt(image)))
                self.lastPreview = time.time()

            self.previewQueue.task_done()

    @pyqtSlot(str, str, list)
    def createVideo(self, inputFile, outputFile, components):
        numpy.seterr(divide='ignore')
        self.encoding.emit(True)
        self.components = components
        self.outputFile = outputFile
        self.extraAudio = []
        self.width = int(self.settings.value('outputWidth'))
        self.height = int(self.settings.value('outputHeight'))

        self.compositeQueue = Queue()
        self.compositeQueue.maxsize = 20
        self.renderQueue = PriorityQueue()
        self.renderQueue.maxsize = 20
        self.previewQueue = PriorityQueue()

        self.reset()
        progressBarValue = 0
        self.progressBarUpdate.emit(progressBarValue)

        # =~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~==~=~=~=~=~=~=~=~=~=~=~=~=~=~
        # READ AUDIO, INITIALIZE COMPONENTS, OPEN A PIPE TO FFMPEG
        # =~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~==~=~=~=~=~=~=~=~=~=~=~=~=~=~

        self.progressBarSetText.emit("Loading audio file...")
        self.completeAudioArray = self.core.readAudioFile(inputFile, self)

        self.progressBarUpdate.emit(0)
        self.progressBarSetText.emit("Starting components...")
        print('Loaded Components:', ", ".join([
            "%s) %s" % (num, str(component))
            for num, component in enumerate(reversed(self.components))
        ]))
        self.staticComponents = {}
        numComps = len(self.components)
        for compNo, comp in enumerate(reversed(self.components)):
            comp.preFrameRender(
                worker=self,
                completeAudioArray=self.completeAudioArray,
                sampleSize=self.sampleSize,
                progressBarUpdate=self.progressBarUpdate,
                progressBarSetText=self.progressBarSetText
            )

            if 'error' in comp.properties():
                self.cancel()
                self.canceled = True
                errMsg = "Component #%s encountered an error!" % compNo \
                    if comp.error() is None else 'Component #%s (%s): %s' % (
                        str(compNo),
                        str(comp),
                        comp.error()
                    )
                self.parent.showMessage(
                        msg=errMsg,
                        icon='Warning',
                        parent=None  # MainWindow is in a different thread
                    )
                break
            if 'static' in comp.properties():
                self.staticComponents[compNo] = \
                    comp.frameRender(compNo, 0).copy()

        if self.canceled:
            print('Export cancelled by component #%s (%s): %s' % (
                compNo, str(comp), comp.error()
            ))
            self.progressBarSetText.emit('Export Canceled')
            self.encoding.emit(False)
            self.videoCreated.emit()
            return

        # Merge consecutive static component frames together
        for compNo in range(len(self.components)):
            if compNo not in self.staticComponents \
                    or compNo + 1 not in self.staticComponents:
                continue
            self.staticComponents[compNo + 1] = Image.alpha_composite(
                self.staticComponents.pop(compNo),
                self.staticComponents[compNo + 1]
            )
            self.staticComponents[compNo] = None

        ffmpegCommand = self.core.createFfmpegCommand(inputFile, outputFile)
        print('###### FFMPEG COMMAND ######\n%s' % " ".join(ffmpegCommand))
        print('############################')
        self.out_pipe = openPipe(
            ffmpegCommand, stdin=sp.PIPE, stdout=sys.stdout, stderr=sys.stdout
        )

        # =~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~==~=~=~=~=~=~=~=~=~=~=~=~=~=~
        # START CREATING THE VIDEO
        # =~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~==~=~=~=~=~=~=~=~=~=~=~=~=~=~

        # Make three renderNodes in new threads to create the frames
        self.renderThreads = []
        for i in range(3):
            self.renderThreads.append(
                Thread(target=self.renderNode, name="Render Thread"))
            self.renderThreads[i].daemon = True
            self.renderThreads[i].start()

        self.dispatchThread = Thread(
            target=self.renderDispatch, name="Render Dispatch Thread")
        self.dispatchThread.daemon = True
        self.dispatchThread.start()

        self.lastPreview = 0.0
        self.previewDispatch = Thread(
            target=self.previewDispatch, name="Render Dispatch Thread")
        self.previewDispatch.daemon = True
        self.previewDispatch.start()

        # Begin piping into ffmpeg!
        frameBuffer = {}
        progressBarValue = 0
        self.progressBarUpdate.emit(progressBarValue)
        self.progressBarSetText.emit("Exporting video...")
        if not self.canceled:
            for audioI in range(
                    0, len(self.completeAudioArray), self.sampleSize):
                while True:
                    if audioI in frameBuffer or self.canceled:
                        # if frame's in buffer, pipe it to ffmpeg
                        break
                    # else fetch the next frame & add to the buffer
                    audioI_, frame = self.renderQueue.get()
                    frameBuffer[audioI_] = frame
                    self.renderQueue.task_done()
                if self.canceled:
                    break

                try:
                    self.out_pipe.stdin.write(frameBuffer[audioI].tobytes())
                    self.previewQueue.put([audioI, frameBuffer.pop(audioI)])
                except:
                    break

                # increase progress bar value
                completion = (audioI / len(self.completeAudioArray)) * 100
                if progressBarValue + 1 <= completion:
                    progressBarValue = numpy.floor(completion)
                    self.progressBarUpdate.emit(progressBarValue)
                    self.progressBarSetText.emit(
                        "Exporting video: %s%%" % str(int(progressBarValue))
                    )

        numpy.seterr(all='print')

        self.out_pipe.stdin.close()
        if self.out_pipe.stderr is not None:
            print(self.out_pipe.stderr.read())
            self.out_pipe.stderr.close()
            self.error = True
        # out_pipe.terminate() # don't terminate ffmpeg too early
        self.out_pipe.wait()
        if self.canceled:
            print("Export Canceled")
            try:
                os.remove(self.outputFile)
            except:
                pass
            self.progressBarUpdate.emit(0)
            self.progressBarSetText.emit('Export Canceled')

        else:
            if self.error:
                print("Export Failed")
                self.progressBarUpdate.emit(0)
                self.progressBarSetText.emit('Export Failed')
            else:
                print("Export Complete")
                self.progressBarUpdate.emit(100)
                self.progressBarSetText.emit('Export Complete')

        self.error = False
        self.canceled = False
        self.stopped = True
        self.encoding.emit(False)
        self.videoCreated.emit()

    def updateProgress(self, pStr, pVal):
        self.progressBarValue.emit(pVal)
        self.progressBarSetText.emit(pStr)

    def cancel(self):
        self.canceled = True
        self.stopped = True
        self.core.cancel()

        for comp in self.components:
            comp.cancel()

        try:
            self.out_pipe.send_signal(signal.SIGINT)
        except:
            pass

    def reset(self):
        self.core.reset()
        self.canceled = False
        for comp in self.components:
            comp.reset()
