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
from frame import FloodFrame


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
                if compNo in self.staticComponents and \
                        self.staticComponents[compNo] is not None:
                    # static component
                    if frame is None:  # bottom-most layer
                        frame = self.staticComponents[compNo]
                    else:
                        frame = Image.alpha_composite(
                            frame, self.staticComponents[compNo]
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
        background = FloodFrame(1920, 1080, (0, 0, 0, 0))
        background.paste(Image.open(os.path.join(
            self.core.wd, "background.png")))
        background = background.resize((self.width, self.height))

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
        self.width = int(self.core.settings.value('outputWidth'))
        self.height = int(self.core.settings.value('outputHeight'))

        self.compositeQueue = Queue()
        self.compositeQueue.maxsize = 20
        self.renderQueue = PriorityQueue()
        self.renderQueue.maxsize = 20
        self.previewQueue = PriorityQueue()

        self.reset()
        progressBarValue = 0
        self.progressBarUpdate.emit(progressBarValue)

        # =~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~==~=~=~=~=~=~=~=~=~=~=~=~=~=~
        # READ AUDIO AND INITIALIZE COMPONENTS
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
        for compNo, comp in enumerate(self.components):
            properties = None
            properties = comp.preFrameRender(
                worker=self,
                completeAudioArray=self.completeAudioArray,
                sampleSize=self.sampleSize,
                progressBarUpdate=self.progressBarUpdate,
                progressBarSetText=self.progressBarSetText
            )

            if properties:
                if 'static' in properties:
                    self.staticComponents[compNo] = \
                        comp.frameRender(compNo, 0).copy()
                if 'audio' in properties:
                    self.extraAudio.append(comp.audio())

        # =~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~==~=~=~=~=~=~=~=~=~=~=~=~=~=~
        # DEDUCE ENCODERS
        # =~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~==~=~=~=~=~=~=~=~=~=~=~=~=~=~

        # test if user has libfdk_aac
        encoders = checkOutput(
            "%s -encoders -hide_banner" % self.core.FFMPEG_BIN, shell=True
        )
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

        for encoder in vencoders:
            if encoder in encoders:
                vencoder = encoder
                break

        for encoder in aencoders:
            if encoder in encoders:
                aencoder = encoder
                break

        # =~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~==~=~=~=~=~=~=~=~=~=~=~=~=~=~
        # CREATE PIPE TO FFMPEG
        # =~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~==~=~=~=~=~=~=~=~=~=~=~=~=~=~

        ffmpegCommand = [
            self.core.FFMPEG_BIN,
            '-thread_queue_size', '512',
            '-y',  # overwrite the output file if it already exists.

            # INPUT VIDEO
            '-f', 'rawvideo',
            '-vcodec', 'rawvideo',
            '-s', str(self.width)+'x'+str(self.height),  # size of one frame
            '-pix_fmt', 'rgba',
            '-r', self.core.settings.value('outputFrameRate'),
            '-i', '-',  # the video input comes from a pipe
            '-an',  # the video input has no sound

            # INPUT SOUND
            '-i', inputFile
        ]

        if self.extraAudio:
            for extraInputFile in self.extraAudio:
                ffmpegCommand.extend([
                    '-i', extraInputFile
                ])
            ffmpegCommand.extend([
                '-filter_complex',
                'amix=inputs=%s:duration=longest:dropout_transition=3' % str(
                    len(self.extraAudio) + 1
                )
            ])

        ffmpegCommand.extend([
            # OUTPUT
            '-vcodec', vencoder,
            '-acodec', aencoder,
            '-b:v', vbitrate,
            '-b:a', abitrate,
            '-pix_fmt', self.core.settings.value('outputVideoFormat'),
            '-preset', self.core.settings.value('outputPreset'),
            '-f', container
        ])
        print(ffmpegCommand)

        if acodec == 'aac':
            ffmpegCommand.append('-strict')
            ffmpegCommand.append('-2')

        ffmpegCommand.append(outputFile)
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
