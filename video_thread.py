from PyQt4 import QtCore, QtGui, uic
from PyQt4.QtCore import pyqtSignal, pyqtSlot
from PIL import Image, ImageDraw, ImageFont
from PIL.ImageQt import ImageQt
import core
import numpy
import subprocess as sp
import sys
import os
from queue import Queue, PriorityQueue
from threading import Thread, Event
import time
from copy import copy
import signal


class Worker(QtCore.QObject):

    imageCreated = pyqtSignal(['QImage'])
    videoCreated = pyqtSignal()
    progressBarUpdate = pyqtSignal(int)
    progressBarSetText = pyqtSignal(str)
    encoding = pyqtSignal(bool)

    def __init__(self, parent=None):
        QtCore.QObject.__init__(self)
        self.core = core.Core()
        self.core.settings = parent.settings
        self.modules = parent.core.modules
        self.parent = parent
        parent.videoTask.connect(self.createVideo)
        self.sampleSize = 1470  # 44100 / 30 = 1470
        self.canceled = False
        self.error = False
        self.stopped = False

    def renderNode(self):
        while not self.stopped:
            i = self.compositeQueue.get()
            frame = None

            for compNo, comp in reversed(list(enumerate(self.components))):
                if compNo in self.staticComponents and \
                        self.staticComponents[compNo] is not None:
                    if frame is None:
                        frame = self.staticComponents[compNo]
                    else:
                        frame = Image.alpha_composite(
                            frame, self.staticComponents[compNo])
                else:
                    if frame is None:
                        frame = comp.frameRender(compNo, i[0], i[1])
                    else:
                        frame = Image.alpha_composite(
                            frame, comp.frameRender(compNo, i[0], i[1]))

            self.renderQueue.put([i[0], frame])
            self.compositeQueue.task_done()

    def renderDispatch(self):
        print('Dispatching Frames for Compositing...')

        for i in range(0, len(self.completeAudioArray), self.sampleSize):
            self.compositeQueue.put([i, self.bgI])
            # increment tracked video frame for next iteration
            self.bgI += 1

    def previewDispatch(self):
        background = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
        background.paste(Image.open(os.path.join(
            self.core.wd, "background.png")))
        background = background.resize((self.width, self.height))

        while not self.stopped:
            i = self.previewQueue.get()
            if time.time() - self.lastPreview >= 0.06 or i[0] == 0:
                image = copy(background)
                image = Image.alpha_composite(image, i[1])
                self._image = ImageQt(image)
                self.imageCreated.emit(QtGui.QImage(self._image))
                self.lastPreview = time.time()

            self.previewQueue.task_done()

    @pyqtSlot(str, str, list)
    def createVideo(self, inputFile, outputFile, components):
        self.encoding.emit(True)
        self.components = components
        self.outputFile = outputFile
        self.bgI = 0  # tracked video frame
        self.reset()
        self.width = int(self.core.settings.value('outputWidth'))
        self.height = int(self.core.settings.value('outputHeight'))
        progressBarValue = 0
        self.progressBarUpdate.emit(progressBarValue)

        self.progressBarSetText.emit('Loading audio file...')
        self.completeAudioArray = self.core.readAudioFile(inputFile, self)

        # test if user has libfdk_aac
        encoders = sp.check_output(
            self.core.FFMPEG_BIN + " -encoders -hide_banner",
            shell=True)

        encoders = encoders.decode("utf-8")

        acodec = self.core.settings.value('outputAudioCodec')

        options = self.core.encoder_options
        containerName = self.core.settings.value('outputContainer')
        vcodec = self.core.settings.value('outputVideoCodec')
        vbitrate = str(self.core.settings.value('outputVideoBitrate'))+'k'
        acodec = self.core.settings.value('outputAudioCodec')
        abitrate = str(self.core.settings.value('outputAudioBitrate'))+'k'

        for cont in options['containers']:
            if cont['name'] == containerName:
                container = cont['container']
                break

        vencoders = options['video-codecs'][vcodec]
        aencoders = options['audio-codecs'][acodec]

        #print(encoders)
        for encoder in vencoders:
            #print(encoder)
            if encoder in encoders:
                vencoder = encoder
                break

        for encoder in aencoders:
            #print(encoder)
            if encoder in encoders:
                aencoder = encoder
                break

        ffmpegCommand = [
            self.core.FFMPEG_BIN,
            '-thread_queue_size', '512',
            '-y',  # overwrite the output file if it already exists.
            '-f', 'rawvideo',
            '-vcodec', 'rawvideo',
            '-s', str(self.width)+'x'+str(self.height),  # size of one frame
            '-pix_fmt', 'rgba',

            # frames per second
            '-r', self.core.settings.value('outputFrameRate'),
            '-i', '-',  # The input comes from a pipe
            '-an',
            '-i', inputFile,
            '-vcodec', vencoder,
            '-acodec', aencoder,  # output audio codec
            '-b:v', vbitrate,
            '-b:a', abitrate,
            '-pix_fmt', self.core.settings.value('outputVideoFormat'),
            '-preset', self.core.settings.value('outputPreset'),
            '-f', container
        ]

        if acodec == 'aac':
            ffmpegCommand.append('-strict')
            ffmpegCommand.append('-2')

        ffmpegCommand.append(outputFile)

        # ### Now start creating video for output ###
        numpy.seterr(divide='ignore')

        # Call preFrameRender on all components
        print('Loaded Components:', ", ".join(
            ["%s) %s" % (num, str(component)) \
                for num, component in enumerate(reversed(self.components))
            ]))
        self.staticComponents = {}
        numComps = len(self.components)
        for compNo, comp in enumerate(self.components):
            pStr = "Analyzing audio..."
            self.progressBarSetText.emit(pStr)
            properties = None
            properties = comp.preFrameRender(
                worker=self,
                completeAudioArray=self.completeAudioArray,
                sampleSize=self.sampleSize,
                progressBarUpdate=self.progressBarUpdate,
                progressBarSetText=self.progressBarSetText
            )

            if properties and 'static' in properties:
                self.staticComponents[compNo] = copy(
                    comp.frameRender(compNo, 0, 0))
            self.progressBarUpdate.emit(100)

        # Create ffmpeg pipe and queues for frames
        self.out_pipe = sp.Popen(
            ffmpegCommand, stdin=sp.PIPE, stdout=sys.stdout, stderr=sys.stdout)
        self.compositeQueue = Queue()
        self.compositeQueue.maxsize = 20
        self.renderQueue = PriorityQueue()
        self.renderQueue.maxsize = 20
        self.previewQueue = PriorityQueue()

        # Threads to render frames and send them back here for piping out
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

        self.previewDispatch = Thread(
            target=self.previewDispatch, name="Render Dispatch Thread")
        self.previewDispatch.daemon = True
        self.previewDispatch.start()

        frameBuffer = {}
        self.lastPreview = 0.0
        self.progressBarUpdate.emit(0)
        pStr = "Exporting video..."
        self.progressBarSetText.emit(pStr)
        if not self.canceled:
            for i in range(0, len(self.completeAudioArray), self.sampleSize):
                while True:
                    if i in frameBuffer or self.canceled:
                        # if frame's in buffer, pipe it to ffmpeg
                        break
                    # else fetch the next frame & add to the buffer
                    data = self.renderQueue.get()
                    frameBuffer[data[0]] = data[1]
                    self.renderQueue.task_done()
                if self.canceled:
                    break

                try:
                    self.out_pipe.stdin.write(frameBuffer[i].tobytes())
                    self.previewQueue.put([i, frameBuffer[i]])
                    del frameBuffer[i]
                except:
                    break

                # increase progress bar value
                if progressBarValue + 1 <= (i / len(self.completeAudioArray)) \
                        * 100:
                    progressBarValue = numpy.floor(
                        (i / len(self.completeAudioArray)) * 100)
                    self.progressBarUpdate.emit(progressBarValue)
                    pStr = "Exporting video: " + str(int(progressBarValue)) \
                        + "%"
                    self.progressBarSetText.emit(pStr)

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
