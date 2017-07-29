from PIL import Image
from PyQt5 import QtGui, QtCore, QtWidgets
from PyQt5.QtGui import QColor
import os
import math
import subprocess

from component import Component, ComponentError
from toolkit.frame import BlankFrame
from toolkit import openPipe, checkOutput, rgbFromString
from toolkit.ffmpeg import FfmpegVideo


class Component(Component):
    name = 'Waveform'
    version = '1.0.0'

    def widget(self, *args):
        self.color = (255, 255, 255)
        super().widget(*args)

        self.page.lineEdit_color.setText('%s,%s,%s' % self.color)
        btnStyle = "QPushButton { background-color : %s; outline: none; }" \
            % QColor(*self.color1).name()
        self.page.lineEdit_color.setStylesheet(btnStyle)
        self.page.pushButton_color.clicked.connect(lambda: self.pickColor())

        self.trackWidgets(
            {
                'mode': self.page.comboBox_mode,
                'x': self.page.spinBox_x,
                'y': self.page.spinBox_y,
                'mirror': self.page.checkBox_mirror,
                'scale': self.page.spinBox_scale,
            }
        )

    def update(self):
        self.color = rgbFromString(self.page.lineEdit_color.text())
        btnStyle = "QPushButton { background-color : %s; outline: none; }" \
            % QColor(*self.color).name()
        self.page.pushButton_color.setStyleSheet(btnStyle)
        super().update()

    def previewRender(self):
        self.updateChunksize()
        frame = self.getPreviewFrame(self.width, self.height)
        if not frame:
            return BlankFrame(self.width, self.height)
        else:
            return frame

    def preFrameRender(self, **kwargs):
        super().preFrameRender(**kwargs)
        self.updateChunksize()
        self.video = FfmpegVideo(
            inputPath=self.audioFile,
            filter_=makeFfmpegFilter(),
            width=self.width, height=self.height,
            chunkSize=self.chunkSize,
            frameRate=int(self.settings.value("outputFrameRate")),
            parent=self.parent, component=self,
        )

    def frameRender(self, frameNo):
        if FfmpegVideo.threadError is not None:
            raise FfmpegVideo.threadError
        return finalizeFrame(self.video.frame(frameNo))

    def postFrameRender(self):
        closePipe(self.video.pipe)

    def getPreviewFrame(self, width, height):
        inputFile = self.parent.window.lineEdit_audioFile.text()
        if not inputFile or not os.path.exists(inputFile):
            return

        command = [
            self.core.FFMPEG_BIN,
            '-thread_queue_size', '512',
            '-i', inputFile,
            '-f', 'image2pipe',
            '-pix_fmt', 'rgba',
        ]
        command.extend(self.makeFfmpegFilter())
        command.extend([
            '-vcodec', 'rawvideo', '-',
            '-ss', '90',
            '-frames:v', '1',
        ])
        pipe = openPipe(
            command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, bufsize=10**8
        )
        byteFrame = pipe.stdout.read(self.chunkSize)
        closePipe(pipe)

        frame = finalizeFrame(self, byteFrame, width, height)
        return frame

    def makeFfmpegFilter(self):
        w, h = scale(self.scale, self.width, self.height, str)
        return [
            '-filter_complex',
            '[0:a] showwaves=s=%sx%s:mode=%s,format=rgba [v]' % (
                w, h, self.mode,
            ),
            '-map', '[v]',
            '-map', '0:a',
        ]

    def updateChunksize(self):
        if self.scale != 100:
            width, height = scale(self.scale, self.width, self.height, int)
        else:
            width, height = self.width, self.height
        self.chunkSize = 4 * width * height


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
    # frombytes goes here
    if self.scale != 100 \
            or self.x != 0 or self.y != 0:
        frame = BlankFrame(width, height)
        frame.paste(image, box=(self.x, self.y))
    else:
        frame = image
    return frame
