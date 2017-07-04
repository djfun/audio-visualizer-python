from PIL import Image, ImageDraw
from PyQt5 import QtGui, QtCore, QtWidgets
import os
import math
import subprocess
import threading
from queue import PriorityQueue

from component import Component, BadComponentInit
from frame import BlankFrame
from toolkit import openPipe


class Video:
    '''Video Component Frame-Fetcher'''
    def __init__(self, **kwargs):
        mandatoryArgs = [
            'ffmpeg',     # path to ffmpeg, usually core.FFMPEG_BIN
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
            try:
                exec('self.%s = kwargs[arg]' % arg)
            except KeyError:
                raise BadComponentInit(arg, self.__doc__)

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
            '-filter:v', 'scale=%s:%s' % scale(
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
        pipe = openPipe(
            self.command, stdout=subprocess.PIPE,
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
            except AttributeError as e:
                self.parent.showMessage(
                    msg='%s couldn\'t be loaded. '
                        'This is a fatal error.' % os.path.basename(
                            self.videoPath
                        ),
                    detail=str(e),
                    icon='Warning'
                )
                self.parent.stopVideo()
                break

            self.currentFrame = pipe.stdout.read(self.chunkSize)
            if len(self.currentFrame) != 0:
                self.frameBuffer.put((self.frameNo, self.currentFrame))
                self.lastFrame = self.currentFrame


class Component(Component):
    '''Video'''

    modified = QtCore.pyqtSignal(int, dict)

    def widget(self, parent):
        self.parent = parent
        self.settings = parent.settings
        page = self.loadUi('video.ui')
        self.videoPath = ''
        self.x = 0
        self.y = 0
        self.loopVideo = False

        page.lineEdit_video.textChanged.connect(self.update)
        page.pushButton_video.clicked.connect(self.pickVideo)
        page.checkBox_loop.stateChanged.connect(self.update)
        page.checkBox_distort.stateChanged.connect(self.update)
        page.spinBox_scale.valueChanged.connect(self.update)
        page.spinBox_x.valueChanged.connect(self.update)
        page.spinBox_y.valueChanged.connect(self.update)

        self.page = page
        return page

    def update(self):
        self.videoPath = self.page.lineEdit_video.text()
        self.loopVideo = self.page.checkBox_loop.isChecked()
        self.distort = self.page.checkBox_distort.isChecked()
        self.scale = self.page.spinBox_scale.value()
        self.xPosition = self.page.spinBox_x.value()
        self.yPosition = self.page.spinBox_y.value()
        self.parent.drawPreview()
        super().update()

    def previewRender(self, previewWorker):
        self.videoFormats = previewWorker.core.videoFormats
        width = int(previewWorker.core.settings.value('outputWidth'))
        height = int(previewWorker.core.settings.value('outputHeight'))
        self.updateChunksize(width, height)
        frame = self.getPreviewFrame(width, height)
        if not frame:
            return BlankFrame(width, height)
        else:
            return frame

    def preFrameRender(self, **kwargs):
        super().preFrameRender(**kwargs)
        width = int(self.worker.core.settings.value('outputWidth'))
        height = int(self.worker.core.settings.value('outputHeight'))
        self.blankFrame_ = BlankFrame(width, height)
        self.updateChunksize(width, height)
        self.video = Video(
            ffmpeg=self.parent.core.FFMPEG_BIN, videoPath=self.videoPath,
            width=width, height=height, chunkSize=self.chunkSize,
            frameRate=int(self.settings.value("outputFrameRate")),
            parent=self.parent, loopVideo=self.loopVideo,
            component=self, scale=self.scale
        ) if os.path.exists(self.videoPath) else None

    def frameRender(self, moduleNo, arrayNo, frameNo):
        if self.video:
            return self.video.frame(frameNo)
        else:
            return self.blankFrame_

    def loadPreset(self, pr, presetName=None):
        super().loadPreset(pr, presetName)
        self.page.lineEdit_video.setText(pr['video'])
        self.page.checkBox_loop.setChecked(pr['loop'])
        self.page.checkBox_distort.setChecked(pr['distort'])
        self.page.spinBox_scale.setValue(pr['scale'])
        self.page.spinBox_x.setValue(pr['x'])
        self.page.spinBox_y.setValue(pr['y'])

    def savePreset(self):
        return {
            'preset': self.currentPreset,
            'video': self.videoPath,
            'loop': self.loopVideo,
            'distort': self.distort,
            'scale': self.scale,
            'x': self.xPosition,
            'y': self.yPosition,
        }

    def pickVideo(self):
        imgDir = self.settings.value("componentDir", os.path.expanduser("~"))
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self.page, "Choose Video",
            imgDir, "Video Files (%s)" % " ".join(self.videoFormats)
        )
        if filename:
            self.settings.setValue("componentDir", os.path.dirname(filename))
            self.page.lineEdit_video.setText(filename)
            self.update()

    def getPreviewFrame(self, width, height):
        if not self.videoPath or not os.path.exists(self.videoPath):
            return

        command = [
            self.parent.core.FFMPEG_BIN,
            '-thread_queue_size', '512',
            '-i', self.videoPath,
            '-f', 'image2pipe',
            '-pix_fmt', 'rgba',
            '-filter:v', 'scale=%s:%s' % scale(
                self.scale, width, height, str),
            '-vcodec', 'rawvideo', '-',
            '-ss', '90',
            '-vframes', '1',
        ]
        pipe = openPipe(
            command, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, bufsize=10**8
        )
        byteFrame = pipe.stdout.read(self.chunkSize)
        frame = finalizeFrame(self, byteFrame, width, height)
        pipe.stdout.close()
        pipe.kill()

        return frame

    def updateChunksize(self, width, height):
        if self.scale != 100 and not self.distort:
            width, height = scale(self.scale, width, height, int)
        self.chunkSize = 4*width*height

    def command(self, arg):
        if not arg.startswith('preset=') and '=' in arg:
            key, arg = arg.split('=', 1)
            if key == 'path' and os.path.exists(arg):
                if os.path.splitext(arg)[1] in self.core.videoFormats:
                    self.page.lineEdit_video.setText(arg)
                    self.page.spinBox_scale.setValue(100)
                    self.page.checkBox_loop.setChecked(True)
                    return
                else:
                    print("Not a supported video format")
                    quit(1)
        super().command(arg)

    def commandHelp(self):
        print('Load a video:\n    path=/filepath/to/video.mp4')


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
        return BlankFrame(width, height)

    if self.scale != 100 \
            or self.xPosition != 0 or self.yPosition != 0:
        frame = BlankFrame(width, height)
        frame.paste(image, box=(self.xPosition, self.yPosition))
    else:
        frame = image
    return frame
