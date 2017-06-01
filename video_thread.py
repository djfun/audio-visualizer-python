from PyQt4 import QtCore, QtGui, uic
from PyQt4.QtCore import pyqtSignal, pyqtSlot
from PIL import Image, ImageDraw, ImageFont
from PIL.ImageQt import ImageQt
import core
import numpy
import subprocess as sp
import sys
from queue import Queue, PriorityQueue
from threading import Thread
import time

class Worker(QtCore.QObject):

    imageCreated = pyqtSignal(['QImage'])
    videoCreated = pyqtSignal()
    progressBarUpdate = pyqtSignal(int)
    progressBarSetText = pyqtSignal(str)

    def __init__(self, parent=None):
        QtCore.QObject.__init__(self)
        self.core = core.Core()
        self.core.settings = parent.settings
        self.modules = parent.modules
        self.stackedWidget = parent.window.stackedWidget
        self.parent = parent
        parent.videoTask.connect(self.createVideo)
        self.sampleSize = 1470

    def renderNode(self):
        while True:
            i = self.compositeQueue.get()

            frame = Image.new(
                "RGBA",
                (self.width, self.height),
                (0, 0, 0, 255)
            )

            if self.imBackground is not None:
                frame.paste(self.imBackground)
            else:
                frame.paste(self.getBackgroundAtIndex(i[1]))

            for compNo, comp in enumerate(self.components):
                if compNo in self.staticComponents and self.staticComponents[compNo] != None:
                    frame = Image.alpha_composite(frame, self.staticComponents[compNo])
                else:
                    frame = Image.alpha_composite(frame, comp.frameRender(compNo, i[0]))

                # frame.paste(compFrame, mask=compFrame)

            self.renderQueue.put([i[0], frame])
            self.compositeQueue.task_done()

    def renderDispatch(self):
        print('Dispatching Frames for Compositing...')
        if not self.imBackground:
            # increment background video frame for next iteration
            if self.bgI < len(self.backgroundFrames)-1 and i != 0:
                self.bgI += 1

        for i in range(0, len(self.completeAudioArray), self.sampleSize):
            self.compositeQueue.put([i, self.bgI])
        self.compositeQueue.join()
        print('Compositing Complete.')

    def previewDispatch(self):
        while True:
            i = self.previewQueue.get()
            if time.time() - self.lastPreview >= 0.05 or i[0] == 0:
                self._image = ImageQt(i[1])
                self.imageCreated.emit(QtGui.QImage(self._image))
                self.lastPreview = time.time()

            self.previewQueue.task_done()
        

    def getBackgroundAtIndex(self, i):
        return self.core.drawBaseImage(self.backgroundFrames[i])

    @pyqtSlot(str, str, str, list)
    def createVideo(self, backgroundImage, inputFile, outputFile, components):
        self.width = int(self.core.settings.value('outputWidth'))
        self.height = int(self.core.settings.value('outputHeight'))
        # print('worker thread id: {}'.format(QtCore.QThread.currentThreadId()))
        self.components = components
        progressBarValue = 0
        self.progressBarUpdate.emit(progressBarValue)
        self.progressBarSetText.emit('Loading background image…')

        self.backgroundImage = backgroundImage

        self.backgroundFrames = self.core.parseBaseImage(backgroundImage)
        if len(self.backgroundFrames) < 2:
            # the base image is not a video so we can draw it now
            self.imBackground = self.getBackgroundAtIndex(0)
        else:
            # base images will be drawn while drawing the audio bars
            self.imBackground = None
        self.bgI = 0

        self.progressBarSetText.emit('Loading audio file…')
        self.completeAudioArray = self.core.readAudioFile(inputFile)

        # test if user has libfdk_aac
        encoders = sp.check_output(self.core.FFMPEG_BIN + " -encoders -hide_banner", shell=True)
        acodec = self.core.settings.value('outputAudioCodec')

        if b'libfdk_aac' in encoders and acodec == 'aac':
            acodec = 'libfdk_aac'

        ffmpegCommand = [
            self.core.FFMPEG_BIN,
            '-y',  # (optional) means overwrite the output file if it already exists.
            '-f', 'rawvideo',
            '-vcodec', 'rawvideo',
            '-s', str(self.width)+'x'+str(self.height),  # size of one frame
            '-pix_fmt', 'rgba',
            '-r', self.core.settings.value('outputFrameRate'),  # frames per second
            '-i', '-',  # The input comes from a pipe
            '-an',
            '-i', inputFile,
            '-acodec', acodec,  # output audio codec
            '-b:a', self.core.settings.value('outputAudioBitrate'),
            '-vcodec', self.core.settings.value('outputVideoCodec'),
            '-pix_fmt', self.core.settings.value('outputVideoFormat'),
            '-preset', self.core.settings.value('outputPreset'),
            '-f', self.core.settings.value('outputFormat')
        ]

        if acodec == 'aac':
            ffmpegCommand.append('-strict')
            ffmpegCommand.append('-2')

        ffmpegCommand.append(outputFile)
        out_pipe = sp.Popen(ffmpegCommand, stdin=sp.PIPE,stdout=sys.stdout, stderr=sys.stdout)

        # create video for output
        numpy.seterr(divide='ignore')

        # initialize components
        print('loaded components:',
              ["%s%s" % (num, str(component)) for num, component in enumerate(components)])
        self.staticComponents = {}
        for compNo, comp in enumerate(components):
            properties = None
            properties = comp.preFrameRender(
                worker=self,
                completeAudioArray=self.completeAudioArray,
                sampleSize=self.sampleSize
            )

            if properties and 'static' in properties:
                self.staticComponents[compNo] = comp.frameRender(compNo, 0)

        self.compositeQueue = Queue()
        self.compositeQueue.maxsize = 20
        self.renderQueue = PriorityQueue()
        self.renderQueue.maxsize = 20
        self.previewQueue = PriorityQueue()

        # create threads to render frames and send them back here for piping out
        for i in range(2):
            t = Thread(target=self.renderNode, name="Render Thread")
            t.daemon = True
            t.start()

        self.dispatchThread = Thread(target=self.renderDispatch, name="Render Dispatch Thread")
        self.dispatchThread.daemon = True
        self.dispatchThread.start()

        self.previewDispatch = Thread(target=self.previewDispatch, name="Render Dispatch Thread")
        self.previewDispatch.daemon = True
        self.previewDispatch.start()

        frameBuffer = {}
        self.lastPreview = 0.0

        for i in range(0, len(self.completeAudioArray), self.sampleSize):
            while True:
                if i in frameBuffer:
                    # if frame's in buffer, pipe it to ffmpeg
                    break
                # else fetch the next frame & add to the buffer
                data = self.renderQueue.get()
                frameBuffer[data[0]] = data[1]
                self.renderQueue.task_done()

            try:
                out_pipe.stdin.write(frameBuffer[i].tobytes())
                self.previewQueue.put([i, frameBuffer[i]])
                del frameBuffer[i]
            finally:
                True

            # increase progress bar value
            if progressBarValue + 1 <= (i / len(self.completeAudioArray)) * 100:
                progressBarValue = numpy.floor((i / len(self.completeAudioArray)) * 100)
                self.progressBarUpdate.emit(progressBarValue)
                self.progressBarSetText.emit('%s%%' % str(int(progressBarValue)))

        numpy.seterr(all='print')

        out_pipe.stdin.close()
        if out_pipe.stderr is not None:
            print(out_pipe.stderr.read())
            out_pipe.stderr.close()
        # out_pipe.terminate() # don't terminate ffmpeg too early
        out_pipe.wait()
        print("Video file created")
        self.parent.drawPreview()
        self.core.deleteTempDir()
        self.progressBarUpdate.emit(100)
        self.progressBarSetText.emit('100%')
        self.videoCreated.emit()
