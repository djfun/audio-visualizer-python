from PIL import Image, ImageDraw
from PyQt5 import QtGui, QtCore, QtWidgets
import os
import math
import subprocess
import signal
import threading
from queue import PriorityQueue

from component import Component, ComponentError
from toolkit.frame import BlankFrame
from toolkit.ffmpeg import testAudioStream
from toolkit import openPipe, checkOutput


class Video:
    '''Opens a pipe to ffmpeg and stores a buffer of raw video frames.'''

    # error from the thread used to fill the buffer
    threadError = None

    def __init__(self, **kwargs):
        mandatoryArgs = [
            'ffmpeg',     # path to ffmpeg, usually self.core.FFMPEG_BIN
            'videoPath',
            'width',
            'height',
            'scale',      # percentage scale
            'frameRate',  # frames per second
            'chunkSize',  # number of bytes in one frame
            'parent',     # mainwindow object
            'component',  # component object
        ]
        for arg in mandatoryArgs:
            setattr(self, arg, kwargs[arg])

        self.frameNo = -1
        self.currentFrame = 'None'
        if 'loopVideo' in kwargs and kwargs['loopVideo']:
            self.loopValue = '-1'
        else:
            self.loopValue = '0'
        self.command = [
            self.ffmpeg,
            '-thread_queue_size', '512',
            '-r', str(self.frameRate),
            '-stream_loop', self.loopValue,
            '-i', self.videoPath,
            '-f', 'image2pipe',
            '-pix_fmt', 'rgba',
            '-filter_complex', '[0:v] scale=%s:%s' % scale(
                self.scale, self.width, self.height, str),
            '-vcodec', 'rawvideo', '-',
        ]

        self.frameBuffer = PriorityQueue()
        self.frameBuffer.maxsize = self.frameRate
        self.finishedFrames = {}

        self.thread = threading.Thread(
            target=self.fillBuffer,
            name=self.__doc__
        )
        self.thread.daemon = True
        self.thread.start()

    def frame(self, num):
        while True:
            if num in self.finishedFrames:
                image = self.finishedFrames.pop(num)
                return finalizeFrame(
                    self.component, image, self.width, self.height)

            i, image = self.frameBuffer.get()
            self.finishedFrames[i] = image
            self.frameBuffer.task_done()

    def fillBuffer(self):
        self.pipe = openPipe(
            self.command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, bufsize=10**8
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
                Video.threadError = ComponentError(self.component, 'video')
                break

            self.currentFrame = self.pipe.stdout.read(self.chunkSize)
            if len(self.currentFrame) != 0:
                self.frameBuffer.put((self.frameNo, self.currentFrame))
                self.lastFrame = self.currentFrame


class Component(Component):
    name = 'Video'
    version = '1.0.0'

    def widget(self, *args):
        self.videoPath = ''
        self.badVideo = False
        self.badAudio = False
        self.x = 0
        self.y = 0
        self.loopVideo = False
        super().widget(*args)
        self.page.pushButton_video.clicked.connect(self.pickVideo)
        self.trackWidgets(
            {
                'videoPath': self.page.lineEdit_video,
                'loopVideo': self.page.checkBox_loop,
                'useAudio': self.page.checkBox_useAudio,
                'distort': self.page.checkBox_distort,
                'scale': self.page.spinBox_scale,
                'volume': self.page.spinBox_volume,
                'xPosition': self.page.spinBox_x,
                'yPosition': self.page.spinBox_y,
            }, presetNames={
                'videoPath': 'video',
                'loopVideo': 'loop',
                'xPosition': 'x',
                'yPosition': 'y',
            }
        )

    def update(self):
        if self.page.checkBox_useAudio.isChecked():
            self.page.label_volume.setEnabled(True)
            self.page.spinBox_volume.setEnabled(True)
        else:
            self.page.label_volume.setEnabled(False)
            self.page.spinBox_volume.setEnabled(False)
        super().update()

    def previewRender(self):
        self.updateChunksize()
        frame = self.getPreviewFrame(self.width, self.height)
        if not frame:
            return BlankFrame(self.width, self.height)
        else:
            return frame

    def properties(self):
        props = []

        if not self.videoPath:
            self.lockError("There is no video selected.")
        elif self.badVideo:
            self.lockError("Could not identify an audio stream in this video.")
        elif not os.path.exists(self.videoPath):
            self.lockError("The video selected does not exist!")
        elif (os.path.realpath(self.videoPath) ==
                os.path.realpath(
                    self.parent.window.lineEdit_outputFile.text())):
            self.lockError("Input and output paths match.")

        if self.useAudio:
            props.append('audio')
            if not testAudioStream(self.videoPath) \
                    and self.error() is None:
                self.lockError(
                    "Could not identify an audio stream in this video.")

        return props

    def audio(self):
        params = {}
        if self.volume != 1.0:
            params['volume'] = '=%s:replaygain_noclip=0' % str(self.volume)
        return (self.videoPath, params)

    def preFrameRender(self, **kwargs):
        super().preFrameRender(**kwargs)
        self.updateChunksize()
        self.video = Video(
            ffmpeg=self.core.FFMPEG_BIN, videoPath=self.videoPath,
            width=self.width, height=self.height, chunkSize=self.chunkSize,
            frameRate=int(self.settings.value("outputFrameRate")),
            parent=self.parent, loopVideo=self.loopVideo,
            component=self, scale=self.scale
        ) if os.path.exists(self.videoPath) else None

    def frameRender(self, frameNo):
        if Video.threadError is not None:
            raise Video.threadError
        return self.video.frame(frameNo)

    def renderFinished(self):
        self.video.pipe.stdout.close()
        self.video.pipe.send_signal(signal.SIGINT)

    def pickVideo(self):
        imgDir = self.settings.value("componentDir", os.path.expanduser("~"))
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self.page, "Choose Video",
            imgDir, "Video Files (%s)" % " ".join(self.core.videoFormats)
        )
        if filename:
            self.settings.setValue("componentDir", os.path.dirname(filename))
            self.page.lineEdit_video.setText(filename)
            self.update()

    def getPreviewFrame(self, width, height):
        if not self.videoPath or not os.path.exists(self.videoPath):
            return

        command = [
            self.core.FFMPEG_BIN,
            '-thread_queue_size', '512',
            '-i', self.videoPath,
            '-f', 'image2pipe',
            '-pix_fmt', 'rgba',
            '-filter_complex', '[0:v] scale=%s:%s' % scale(
                self.scale, width, height, str),
            '-vcodec', 'rawvideo', '-',
            '-ss', '90',
            '-vframes', '1',
        ]
        pipe = openPipe(
            command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, bufsize=10**8
        )
        byteFrame = pipe.stdout.read(self.chunkSize)
        pipe.stdout.close()
        pipe.send_signal(signal.SIGINT)

        frame = finalizeFrame(self, byteFrame, width, height)
        return frame

    def updateChunksize(self):
        if self.scale != 100 and not self.distort:
            width, height = scale(self.scale, self.width, self.height, int)
        self.chunkSize = 4 * width * height

    def command(self, arg):
        if '=' in arg:
            key, arg = arg.split('=', 1)
            if key == 'path' and os.path.exists(arg):
                if '*%s' % os.path.splitext(arg)[1] in self.core.videoFormats:
                    self.page.lineEdit_video.setText(arg)
                    self.page.spinBox_scale.setValue(100)
                    self.page.checkBox_loop.setChecked(True)
                    return
                else:
                    print("Not a supported video format")
                    quit(1)
        elif arg == 'audio':
            if not self.page.lineEdit_video.text():
                print("'audio' option must follow a video selection")
                quit(1)
            self.page.checkBox_useAudio.setChecked(True)
            return
        super().command(arg)

    def commandHelp(self):
        print('Load a video:\n    path=/filepath/to/video.mp4')
        print('Using audio:\n    path=/filepath/to/video.mp4 audio')


def scale(scale, width, height, returntype=None):
    width = (float(width) / 100.0) * float(scale)
    height = (float(height) / 100.0) * float(scale)
    if returntype == str:
        return (str(math.ceil(width)), str(math.ceil(height)))
    elif returntype == int:
        return (math.ceil(width), math.ceil(height))
    else:
        return (width, height)


def finalizeFrame(self, imageData, width, height):
    try:
        if self.distort:
            image = Image.frombytes(
                'RGBA',
                (width, height),
                imageData)
        else:
            image = Image.frombytes(
                'RGBA',
                scale(self.scale, width, height, int),
                imageData)

    except ValueError:
        print(
            '### BAD VIDEO SELECTED ###\n'
            'Video will not export with these settings'
        )
        self.badVideo = True
        return BlankFrame(width, height)

    if self.scale != 100 \
            or self.xPosition != 0 or self.yPosition != 0:
        frame = BlankFrame(width, height)
        frame.paste(image, box=(self.xPosition, self.yPosition))
    else:
        frame = image
    self.badVideo = False
    return frame
